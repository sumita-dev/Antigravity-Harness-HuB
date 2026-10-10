import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const nodeFile=(p,args=[],options={})=>spawnSync('node',[p,...args],{encoding:'utf8',...options});
const issue={id:'test-01',route:'/',viewport:'desktop-1440',category:'layoutSpacing',severity:'medium',confidence:0.95,recommendation:'Use consistent gaps.',evidence:[{type:'dom',ref:'gap-ref',observation:'Gap uneven'}],requiresApproval:false};
const score={overallScore:75,coverage:100,trustworthyScore:true,technicalGate:'pass'};

test('plan mode excludes high severity and never modifies repository',async()=>{
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'skill-plan-'));
 try{
  const issues=path.join(tmp,'issues.json'),scoreFile=path.join(tmp,'score.json');
  await fs.writeFile(issues,JSON.stringify([issue,{...issue,id:'high',severity:'high',requiresApproval:true}]));
  await fs.writeFile(scoreFile,JSON.stringify(score));
  const p=nodeFile(path.join(root,'improvement/guarded-loop.mjs'),['--repo',tmp,'--issues',issues,'--score',scoreFile,'--out',path.join(tmp,'out')]);
  assert.equal(p.status,0,p.stderr);
  const plan=JSON.parse(await fs.readFile(path.join(tmp,'out','repair-plan.json')));
  assert.equal(plan.tasks.length,1);assert.equal(plan.excluded,1);
 } finally {await fs.rm(tmp,{recursive:true,force:true})}
});
test('execution is opt-in and guarded with Git, scope and score verification',async()=>{
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'skill-repair-'));
 try{
  const repo=path.join(tmp,'repo');await fs.mkdir(path.join(repo,'src/ui'),{recursive:true});await fs.mkdir(path.join(repo,'scripts'));
  await fs.writeFile(path.join(repo,'src/ui/button.css'),'padding: 8px;\n');
  await fs.writeFile(path.join(repo,'scripts/fix.mjs'),"import fs from 'node:fs'; fs.appendFileSync('src/ui/button.css','/* improved */\\n');\n");
  const result=path.join(tmp,'verified.json');
  await fs.writeFile(path.join(repo,'scripts/verify.mjs'),`import fs from 'node:fs';fs.writeFileSync(${JSON.stringify(result)},JSON.stringify({overallScore:81,coverage:100,trustworthyScore:true,technicalGate:'pass'}));`);
  const git=(a)=>spawnSync('git',a,{cwd:repo,encoding:'utf8'});
  assert.equal(git(['init']).status,0);
  assert.equal(git(['add','.']).status,0);
  assert.equal(spawnSync('git',['-c','user.email=test@example.com','-c','user.name=Test','commit','-m','baseline'],{cwd:repo}).status,0);
  const issues=path.join(tmp,'issues.json'),scoreFile=path.join(tmp,'score.json'),out=path.join(tmp,'out');
  await fs.writeFile(issues,JSON.stringify([issue]));await fs.writeFile(scoreFile,JSON.stringify(score));
  const args=['--repo',repo,'--issues',issues,'--score',scoreFile,'--out',out,'--execute'];
  const denied=nodeFile(path.join(root,'improvement/guarded-loop.mjs'),args);
  assert.equal(denied.status,2);assert.match(denied.stderr,/UI_ENABLE_AUTO_FIX/);
  const yes=nodeFile(path.join(root,'improvement/guarded-loop.mjs'),args,{env:{...process.env,UI_ENABLE_AUTO_FIX:'1',UI_ALLOWED_EDIT_PREFIXES:'src/ui',UI_FIX_COMMAND_JSON:'["node","scripts/fix.mjs"]',UI_VERIFY_COMMAND_JSON:'["node","scripts/verify.mjs"]',UI_SCORE_RESULT:result,UI_TARGET_SCORE:'80'}});
  assert.equal(yes.status,0,yes.stderr);
  const history=JSON.parse(await fs.readFile(path.join(out,'loop-history.json')));
  assert.equal(history.length,1);assert.equal(history[0].score,81);
  assert.match(await fs.readFile(path.join(repo,'src/ui/button.css'),'utf8'),/improved/);
 }finally{await fs.rm(tmp,{recursive:true,force:true})}
});
