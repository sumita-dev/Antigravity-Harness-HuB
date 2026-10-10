#!/usr/bin/env node
/** Explicitly opted-in repair orchestrator. NOT a security sandbox. Never updates baselines. */
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const argv=process.argv.slice(2);
const get=k=>{const i=argv.indexOf(k);return i<0?null:argv[i+1]};
const read=async f=>JSON.parse(await fs.readFile(f,'utf8'));
const repo=path.resolve(get('--repo')||process.cwd());
const out=path.resolve(get('--out')||path.join(os.tmpdir(),'apple-design-v4-loop'));
const issuesFile=get('--issues');const initialScoreFile=get('--score');
const execute=argv.includes('--execute');
const run=(args,cwd=repo,env=process.env)=>{
 if(!Array.isArray(args)||!args.length||args.some(x=>typeof x!=='string'||!x))throw Error('Commands must be non-empty JSON arrays of strings.');
 const proc=spawnSync(args[0],args.slice(1),{cwd,env,encoding:'utf8',timeout:120000,maxBuffer:1024*1024*3,shell:false});
 if(proc.error)throw proc.error;
 if(proc.status!==0)throw Error(`Command ${args[0]} exited ${proc.status}: ${(proc.stderr||proc.stdout||'').slice(-1800)}`);
 return proc.stdout;
};
const git=args=>run(['git',...args]);
const changedFiles=()=>git(['status','--porcelain','--untracked-files=all']).split('\n').filter(Boolean).map(s=>s.slice(3).split(' -> ').at(-1));
const isAllowed=(file,prefixes)=>{
 const f=file.replaceAll('\\','/');
 const forbidden=/(^|\/)(\.github|\.git|__snapshots__|snapshots|design-memory\.json|\.env[^/]*|package-lock\.json|tokens\.css)(\/|$)/i;
 return !forbidden.test(f) && prefixes.some(p=>f.startsWith(p.endsWith('/')?p:p+'/'));
};
try {
 if(!issuesFile||!initialScoreFile)throw Error('Usage: node improvement/guarded-loop.mjs --repo APP --issues issues.json --score score.json [--out DIR] [--execute]');
 const issues=await read(issuesFile), baseline=await read(initialScoreFile);
 if(!Array.isArray(issues))throw Error('Issues must be a JSON array.');
 const safe=issues.filter(i=>['medium','low'].includes(i.severity)&&i.requiresApproval===false&&typeof i.recommendation==='string'&&i.recommendation.trim()&&i.confidence>=0.8&&Array.isArray(i.evidence)&&i.evidence.length);
 await fs.mkdir(out,{recursive:true});
 const plan={version:'4.0.0',repo,sourceIssues:path.resolve(issuesFile),tasks:safe.map(i=>({id:i.id,route:i.route,category:i.category,confidence:i.confidence,recommendation:i.recommendation,evidence:i.evidence})),excluded:issues.length-safe.length,policy:'Only low/medium, high-confidence evidence-backed recommendations. No baseline or design memory changes without human approval.'};
 const planFile=path.join(out,'repair-plan.json');await fs.writeFile(planFile,JSON.stringify(plan,null,2)+'\n');
 console.log(`Repair plan: ${safe.length} eligible tasks; ${issues.length-safe.length} require human/other review. ${planFile}`);
 if(!execute){console.log('PLAN ONLY. No source files changed. Use --execute with explicit safety settings to enable external fixer.');process.exit(0);}
 if(!safe.length)throw Error('No eligible tasks. Automatic execution refused.');
 if(process.env.UI_ENABLE_AUTO_FIX!=='1')throw Error('Set UI_ENABLE_AUTO_FIX=1 to explicitly enable execution.');
 if(!baseline.trustworthyScore||baseline.technicalGate!=='pass'||baseline.overallScore===null)throw Error('Cannot start automatic repair without a validated passing technical baseline and sufficient design coverage.');
 const prefixes=(process.env.UI_ALLOWED_EDIT_PREFIXES||'').split(',').map(x=>x.trim()).filter(Boolean);
 if(!prefixes.length||prefixes.some(x=>x.startsWith('/')||x.includes('..')||x==='.'||x==='*'))throw Error('Provide conservative UI_ALLOWED_EDIT_PREFIXES (e.g. src/components,app/dashboard).');
 const maxCycles=Number(process.env.UI_MAX_CYCLES||3);
 if(!Number.isInteger(maxCycles)||maxCycles<1||maxCycles>3)throw Error('UI_MAX_CYCLES must be 1..3.');
 const fix=JSON.parse(process.env.UI_FIX_COMMAND_JSON||'null');
 const verify=JSON.parse(process.env.UI_VERIFY_COMMAND_JSON||'null');
 const scorePath=process.env.UI_SCORE_RESULT?path.resolve(repo,process.env.UI_SCORE_RESULT):null;
 if(!scorePath)throw Error('Set UI_SCORE_RESULT to JSON output of the verification step.');
 if(path.resolve(git(['rev-parse','--show-toplevel']).trim())!==repo)throw Error('The --repo path must point to the Git repository root.');
 if(git(['status','--porcelain']).trim())throw Error('Git working tree must be clean before automatic repair.');
 let prior=baseline.overallScore, priorCoverage=baseline.coverage;
 const history=[];
 for(let cycle=1;cycle<=maxCycles;cycle++){
  const env={...process.env,UI_REPAIR_PLAN:planFile,UI_REPAIR_CYCLE:String(cycle)};
  run(fix,repo,env);
  const changed=changedFiles();
  if(!changed.length)throw Error('Fix command made no file changes.');
  const disallowed=changed.filter(f=>!isAllowed(f,prefixes));
  if(disallowed.length)throw Error(`Unauthorized file changes detected: ${disallowed.join(', ')}. Review manually; script will not revert files.`);
  run(verify,repo,env);
  const postVerifyChanges=changedFiles();
  const verifierDisallowed=postVerifyChanges.filter(f=>!isAllowed(f,prefixes));
  if(verifierDisallowed.length)throw Error(`Verifier touched unauthorized files: ${verifierDisallowed.join(', ')}. Review manually.`);
  const next=await read(scorePath);
  if(!Number.isFinite(next.overallScore)||!Number.isFinite(next.coverage)||next.coverage<0||next.coverage>100)throw Error('Verifier returned invalid score or coverage.');
  if(Array.isArray(baseline.results) && Array.isArray(next.results)){
   const scopes=r=>r.results.map(x=>`${x.route}::${x.viewport}`).sort().join('|');
   if(scopes(baseline)!==scopes(next))throw Error('Verification used different routes/viewports; comparisons are not valid.');
  }
  history.push({cycle,score:next.overallScore,coverage:next.coverage,technicalGate:next.technicalGate,changed});
  await fs.writeFile(path.join(out,'loop-history.json'),JSON.stringify(history,null,2)+'\n');
  if(next.technicalGate!=='pass'||!next.trustworthyScore||next.coverage<priorCoverage)throw Error('Verification failed: technical gate, trust coverage or assessed scope regressed. Changes left for review.');
  if(!(next.overallScore>prior+0.1))throw Error('Score failed to improve meaningfully; stopped. Changes left for human review.');
  console.log(`Cycle ${cycle}: ${prior} -> ${next.overallScore}; coverage ${next.coverage}%.`);
  prior=next.overallScore;priorCoverage=next.coverage;
  if(next.overallScore>=Number(process.env.UI_TARGET_SCORE||90))break;
 }
 console.log('Finished bounded repair attempt. Changes are uncommitted: inspect diff and approve manually.');
}catch(error){console.error('Guarded loop stopped:',error.message);process.exitCode=2;}
