import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const cli=path.join(root,'design-system/memory-cli.mjs');

test('memory proposal requires explicit approval, then records provenance',async()=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'skill-memory-'));
 try{
  const memory=path.join(dir,'memory.json'),proposal=path.join(dir,'proposal.json');
  await fs.writeFile(memory,JSON.stringify({schemaVersion:1,project:{},decisions:[]}));
  await fs.writeFile(proposal,JSON.stringify({id:'rule-01',decision:'Readable tables',rationale:'Review outcome',sourceRef:'issue-99'}));
  const call=(args)=>spawnSync('node',[cli,...args],{encoding:'utf8'});
  const denied=call(['approve','--proposal',proposal,'--memory',memory]);assert.equal(denied.status,2);
  assert.equal(JSON.parse(await fs.readFile(memory,'utf8')).decisions.length,0);
  const approved=call(['approve','--proposal',proposal,'--memory',memory,'--approved-by','Reviewer','--confirm','APPROVE']);assert.equal(approved.status,0,approved.stderr);
  const state=JSON.parse(await fs.readFile(memory,'utf8'));assert.equal(state.decisions.length,1);assert.equal(state.decisions[0].sourceRef,'issue-99');
  assert.equal(call(['validate','--memory',memory]).status,0);
 }finally{await fs.rm(dir,{recursive:true,force:true})}
});
