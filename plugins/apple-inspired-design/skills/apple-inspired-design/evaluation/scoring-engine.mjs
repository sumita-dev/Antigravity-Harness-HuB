#!/usr/bin/env node
/** Deterministic design-score aggregator. No model calls and no code modifications. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const own = path.dirname(fileURLToPath(import.meta.url));
const defaultRubric = path.join(own, 'rubric.json');
const required = (v, message) => { if (!v) throw new Error(message); return v; };
const json = async file => JSON.parse(await fs.readFile(file, 'utf8'));
const finite = (v, min, max) => typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max;
const clean = s => String(s ?? '').replace(/[\r\n|]/g, ' ').slice(0, 400);

export function evaluate(input, rubric) {
  if (!Array.isArray(input.reviews) || input.reviews.length === 0) throw Error('reviews must contain at least one page/viewport.');
  const cats = rubric.categories;
  const weights = cats.reduce((s,c) => s+c.weight, 0);
  if (weights !== 100 || new Set(cats.map(c => c.id)).size !== cats.length) throw Error('Rubric must contain unique metric keys totaling 100 weight.');
  if (!['pass', 'fail', 'unverified'].includes(input.technicalGate)) throw Error('technicalGate must be pass, fail or unverified.');
  const results = input.reviews.map((review,index) => {
    if (typeof review.route !== 'string' || !review.route || typeof review.viewport !== 'string' || !review.viewport) throw Error(`reviews[${index}] requires route and viewport.`);
    if (!review.metrics || typeof review.metrics !== 'object' || Array.isArray(review.metrics)) throw Error(`reviews[${index}] requires metrics.`);
    const unknown = Object.keys(review.metrics).filter(id => !cats.some(c=>c.id===id));
    if (unknown.length) throw Error(`Unknown metric(s): ${unknown.join(', ')}`);
    let measuredWeight=0, weighted=0, weightedConfidence=0;
    const items=[];
    const issues=[];
    for (const c of cats) {
      const m=review.metrics[c.id];
      const validEvidence=Array.isArray(m?.evidence) && m.evidence.length>0 && m.evidence.every(e=>e && ['screenshot','dom','test','interaction','token','manual'].includes(e.type) && typeof e.ref==='string' && e.ref.trim() && typeof e.observation==='string' && e.observation.trim());
      const assessed=m && m.score!==null && finite(m.score,0,5) && finite(m.confidence,0,1) && m.confidence>=rubric.minimumConfidence && validEvidence && typeof m.summary==='string' && !!m.summary.trim();
      if (m && m.score!==null && m.score!==undefined && !assessed) throw Error(`Invalid ${c.id} for ${review.route} ${review.viewport}: rated metrics require 0–5 score, confidence >= ${rubric.minimumConfidence}, summary and verifiable evidence.`);
      if (!assessed) {
        items.push({id:c.id,label:c.label,weight:c.weight,score:null,reason:m?.reason || 'Not evaluated: insufficient evidence.'});
        continue;
      }
      weighted+=c.weight*(m.score/5); measuredWeight+=c.weight; weightedConfidence+=m.confidence*c.weight;
      items.push({id:c.id,label:c.label,weight:c.weight,score:m.score,confidence:m.confidence,points:Math.round(c.weight*m.score/5*100)/100,summary:m.summary,evidence:m.evidence});
      if (m.score<4) {
        const severity=m.score<=2?'high':m.score<3.5?'medium':'low';
        issues.push({id:`review-${index}-${c.id}`,route:review.route,viewport:review.viewport,category:c.id,severity,confidence:m.confidence,summary:m.summary,recommendation:typeof m.recommendation==='string'?m.recommendation:'Request a focused design review before changing UI.',evidence:m.evidence,requiresApproval:severity==='high'||m.confidence<0.8,source:'design-review'});
      }
    }
    return {route:review.route,viewport:review.viewport,score:measuredWeight?Math.round(weighted/measuredWeight*10000)/100:null,coverage:measuredWeight,confidence:measuredWeight?Math.round(weightedConfidence/measuredWeight*100)/100:null,metrics:items,issues};
  });
  const sumWeight=results.reduce((s,r)=>s+r.coverage,0);
  const overall=sumWeight?Math.round(results.reduce((s,r)=>s+(r.score??0)*r.coverage,0)/sumWeight*100)/100:null;
  const coverage=Math.round(sumWeight/results.length*100)/100;
  const issues=results.flatMap(r=>r.issues);
  const meaningful=overall!==null && coverage>=75 && input.technicalGate==='pass';
  return {version:'4.0.0',source:input.source||'manual',technicalGate:input.technicalGate,overallScore:overall,coverage,trustworthyScore:meaningful,minimumConfidence:rubric.minimumConfidence,reviewCount:results.length,results,issues,summary: meaningful?`Design score ${overall}/100 with ${coverage}% coverage; technical gate passed.`:`PROVISIONAL score (or unavailable): coverage ${coverage}% and technical gate ${input.technicalGate}; do not claim design approval.`};
}

export function markdown(result) {
  const lines=['# Design Quality Audit','',`> ${result.summary}`,'',`- **Overall:** ${result.overallScore??'Not assessable'} / 100` ,`- **Coverage:** ${result.coverage}% of rubric weight on average`,`- **Technical gate:** ${result.technicalGate}`,`- **Assessment:** ${result.trustworthyScore?'Eligible for human review':'PROVISIONAL / incomplete evidence'}`,'', '| Route | Viewport | Score | Coverage |', '|---|---|---:|---:|'];
  for (const r of result.results) lines.push(`| ${clean(r.route)} | ${clean(r.viewport)} | ${r.score??'N/A'} | ${r.coverage}% |`);
  for (const r of result.results) {
    lines.push('',`## ${clean(r.route)} — ${clean(r.viewport)}`,'', '| Category | Rating | Evidence |','|---|---:|---|');
    for (const m of r.metrics) lines.push(`| ${m.label} | ${m.score===null?'Unassessed':m.score+'/5'} | ${m.evidence?.map(e=>clean(e.ref)).join(', ')||clean(m.reason)} |`);
  }
  lines.push('','## Prioritized recommendations','');
  for(const i of result.issues.sort((a,b)=>({high:0,medium:1,low:2}[a.severity])-({high:0,medium:1,low:2}[b.severity]))) lines.push(`- **${i.severity} · ${i.category} · ${clean(i.route)} (${clean(i.viewport)})**: ${clean(i.summary)}. Next: ${clean(i.recommendation)}. ${i.requiresApproval?'Human approval required.':''}`);
  if (!result.issues.length) lines.push('No rated metric below 4/5. This does not prove usability, visual quality, or accessibility.');
  lines.push('','Scores are from an independent, partly subjective rubric; not an Apple rating, WCAG certification, or guarantee of UX quality.');
  return lines.join('\n')+'\n';
}

async function main() {
  const args=process.argv.slice(2), arg=(key,def)=>{const i=args.indexOf(key);return i>=0?required(args[i+1],`${key} requires a value`):def;};
  const infile=required(arg('--input',null),'Usage: node evaluation/scoring-engine.mjs --input file.json [--out directory]');
  const out=path.resolve(arg('--out','artifacts/design-quality'));
  const result=evaluate(await json(infile), await json(arg('--rubric',defaultRubric)));
  await fs.mkdir(out,{recursive:true});
  await Promise.all([
    fs.writeFile(path.join(out,'score.json'),JSON.stringify(result,null,2)+'\n'),
    fs.writeFile(path.join(out,'issues.json'),JSON.stringify(result.issues,null,2)+'\n'),
    fs.writeFile(path.join(out,'report.md'),markdown(result))
  ]);
  console.log(result.summary);console.log(`Reports: ${out}`);
  if(args.includes('--strict') && !result.trustworthyScore)process.exitCode=2;
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) main().catch(e=>{console.error(e.message);process.exitCode=2});
