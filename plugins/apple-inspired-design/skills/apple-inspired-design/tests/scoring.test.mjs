import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {evaluate, markdown} from '../evaluation/scoring-engine.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const rubric=JSON.parse(await fs.readFile(path.join(root,'evaluation/rubric.json')));
const evidence=[{type:'manual',ref:'review-001',observation:'A human reviewed each state of this test fixture.'}];
const input=(score=4)=>({source:'unit-test',technicalGate:'pass',reviews:[{route:'/dashboard',viewport:'desktop-1440',metrics:Object.fromEntries(rubric.categories.map(c=>[c.id,{score,confidence:0.88,summary:'Verified in this sample test.',recommendation:'Retest after changes.',evidence}]))}]});

test('full documented coverage gives weighted 80/100 and trustworthy result',()=>{
 const result=evaluate(input(),rubric);
 assert.equal(result.overallScore,80);
 assert.equal(result.coverage,100);
 assert.equal(result.trustworthyScore,true);
 assert.equal(result.results[0].metrics.length,8);
 assert.match(markdown(result),/80 \/ 100/);
});
test('missing evidence is unassessed, not zero',()=>{
 const x=input();delete x.reviews[0].metrics.interactionUX;delete x.reviews[0].metrics.motionPolish;
 const result=evaluate(x,rubric);
 assert.equal(result.coverage,85);assert.equal(result.overallScore,80);
 assert.equal(result.results[0].metrics.find(m=>m.id==='interactionUX').score,null);
});
test('unverified technical gate cannot be approved regardless of score',()=>{
 const x=input(5);x.technicalGate='unverified';const r=evaluate(x,rubric);
 assert.equal(r.overallScore,100);assert.equal(r.trustworthyScore,false);
});
test('evidence and confidence required for rated metric',()=>{
 const x=input();x.reviews[0].metrics.typography.evidence=[];
 assert.throws(()=>evaluate(x,rubric),/Invalid typography/);
 x.reviews[0].metrics.typography.evidence=evidence;x.reviews[0].metrics.typography.confidence=0.25;
 assert.throws(()=>evaluate(x,rubric),/Invalid typography/);
});
test('a legitimate zero score is distinguishable from no assessment',()=>{
 const r=evaluate(input(0),rubric);assert.equal(r.overallScore,0);assert.equal(r.coverage,100);
});
test('CLI writes report and issue JSON',async()=>{
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'skill-score-'));
 try{
  const inp=path.join(temp,'input.json');const out=path.join(temp,'out');
  await fs.writeFile(inp,JSON.stringify(input(3)));
  const p=spawnSync('node',[path.join(root,'evaluation/scoring-engine.mjs'),'--input',inp,'--out',out],{encoding:'utf8'});
  assert.equal(p.status,0,p.stderr);
  assert.equal((await JSON.parse(await fs.readFile(path.join(out,'issues.json')))).length,8);
  assert.match(await fs.readFile(path.join(out,'report.md'),'utf8'),/Prioritized recommendations/);
 }finally{await fs.rm(temp,{recursive:true,force:true})}
});
