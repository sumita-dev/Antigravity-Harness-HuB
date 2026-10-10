#!/usr/bin/env node
/** Approved design decisions are explicit and version-controlled, not silently inferred. */
import fs from 'node:fs/promises';
import path from 'node:path';
const args=process.argv.slice(2);
const flag=name=>{const i=args.indexOf(name);return i<0?null:args[i+1]};
const cmd=args[0];
const read=async f=>JSON.parse(await fs.readFile(f,'utf8'));
const memory=path.resolve(flag('--memory')||'design-system/design-memory.json');
const validate=doc=>{
 if(doc.schemaVersion!==1 || !Array.isArray(doc.decisions) || typeof doc.project!=='object')throw Error('Invalid design memory format.');
 for(const d of doc.decisions){if(!d.id||!d.decision||!d.rationale||!d.approvedBy||!d.approvedAt||!d.sourceRef||d.status!=='approved')throw Error(`Invalid approved decision: ${d.id}`)};
 if(new Set(doc.decisions.map(d=>d.id)).size!==doc.decisions.length)throw Error('Duplicate decision id.');
 return doc;
};
try{
 if(cmd==='validate') {const doc=validate(await read(memory));console.log(`Valid memory: ${doc.decisions.length} approved decisions.`);}
 else if(cmd==='approve') {
  if(flag('--confirm')!=='APPROVE'||!flag('--approved-by'))throw Error('Explicit --approved-by NAME and --confirm APPROVE required.');
  const proposed=await read(flag('--proposal')||'');
  for(const key of ['id','decision','rationale','sourceRef'])if(typeof proposed[key]!=='string'||!proposed[key].trim())throw Error(`Proposal requires ${key}`);
  const doc=validate(await read(memory));
  if(doc.decisions.some(d=>d.id===proposed.id))throw Error('Decision already exists; use a new ID and reference superseded decision.');
  doc.decisions.push({id:proposed.id,decision:proposed.decision,rationale:proposed.rationale,sourceRef:proposed.sourceRef,scope:proposed.scope||'project',status:'approved',approvedBy:flag('--approved-by'),approvedAt:new Date().toISOString()});
  const tmp=memory+'.tmp';await fs.writeFile(tmp,JSON.stringify(doc,null,2)+'\n');await fs.rename(tmp,memory);
  console.log(`Approved decision ${proposed.id}. Commit this file for team review.`);
 } else throw Error('Usage: node design-system/memory-cli.mjs validate [--memory FILE]\n   or: node design-system/memory-cli.mjs approve --proposal FILE --memory FILE --approved-by PERSON --confirm APPROVE');
}catch(error){console.error(error.message);process.exitCode=2;}
