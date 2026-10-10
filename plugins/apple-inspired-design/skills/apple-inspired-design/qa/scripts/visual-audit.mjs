#!/usr/bin/env node
// Deterministic, read-only visual audit. The coding agent, not this script, decides edits.
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:3000';
const routes = (process.env.UI_ROUTES || '/').split(',').map(x=>x.trim()).filter(Boolean);
const out = path.resolve(process.env.UI_AUDIT_DIR || 'artifacts/visual-qa');
const maxRoutes=Number(process.env.UI_MAX_ROUTES || 15);
const allowCrossOrigin=process.env.UI_ALLOW_CROSS_ORIGIN==='1';
const allowedOrigin=new URL(base).origin;
if(!Number.isInteger(maxRoutes)||maxRoutes<1)throw Error('UI_MAX_ROUTES must be a positive integer');
if(routes.length>maxRoutes)throw Error(`Too many routes: ${routes.length} > ${maxRoutes}`);
for(const route of routes){
 const url=new URL(route,base);if(!allowCrossOrigin&&url.origin!==allowedOrigin)throw Error(`Cross-origin route blocked: ${url}`);
}
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const results=[];
const viewports=[{id:'mobile',width:390,height:844},{id:'tablet',width:768,height:1024},{id:'desktop',width:1440,height:900}];
try {
 for(const route of routes){
  for(const vp of viewports){
   const context=await browser.newContext({viewport:{width:vp.width,height:vp.height},deviceScaleFactor:1,reducedMotion:'reduce',colorScheme:'light'});
   const page=await context.newPage();
   const errors=[];
   page.on('pageerror',err=>errors.push(err.message));
   const url=new URL(route,base).toString();
   const id=(new URL(route,base).pathname.replace(/[^\w-]/g,'_')||'root')+'-'+vp.id;
   const entry={route,viewport:vp,finalUrl:null,status:null,issues:[],screenshot:null};
   try{
    const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});
    entry.finalUrl=page.url();entry.status=response?.status()??null;
    if(!allowCrossOrigin&&new URL(page.url()).origin!==allowedOrigin)throw Error('Redirected to another origin');
    await page.evaluate(()=>document.fonts.ready);
    await page.addStyleTag({content:'*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important;caret-color:transparent!important}'});
    if(entry.status>=400)entry.issues.push({severity:'blocker',kind:'http',details:`HTTP ${entry.status}`});
    const layout=await page.evaluate(()=>{
      const doc=document.documentElement;
      const viewport=document.documentElement.clientWidth;
      const overflowing=[...document.querySelectorAll('body *')].filter(el=>{
       const rect=el.getBoundingClientRect();const style=getComputedStyle(el);
       return style.position!=='fixed'&&rect.width>0&&(rect.right>viewport+2||rect.left< -2)&&style.visibility!=='hidden';
      }).slice(0,10).map(el=>({tag:el.tagName.toLowerCase(),className:typeof el.className==='string'?el.className.slice(0,120):'',outer:el.outerHTML.slice(0,220)}));
      return {scrollWidth:doc.scrollWidth,clientWidth:viewport,overflowing};
    });
    if(layout.scrollWidth>layout.clientWidth+2)entry.issues.push({severity:'high',kind:'horizontal-overflow',details:layout});
    const violations=(await new AxeBuilder({page}).analyze()).violations;
    for(const v of violations){entry.issues.push({severity:['critical','serious'].includes(v.impact)?'high':'medium',kind:'accessibility',rule:v.id,impact:v.impact,details:v.nodes.slice(0,5).map(n=>({target:n.target,summary:n.failureSummary}))});}
    for(const err of errors)entry.issues.push({severity:'high',kind:'runtime-exception',details:err});
    const shot=path.join(out,`${id}.png`);await page.screenshot({path:shot,fullPage:true,animations:'disabled'});entry.screenshot=path.relative(process.cwd(),shot);
   } catch(err){entry.issues.push({severity:'blocker',kind:'capture-failure',details:String(err)});}
   finally{results.push(entry);await context.close();}
  }
 }
} finally{await browser.close();}
const summary={createdAt:new Date().toISOString(),baseURL:base,routeCount:routes.length,results,totalIssues:results.reduce((n,r)=>n+r.issues.length,0),blockingIssues:results.reduce((n,r)=>n+r.issues.filter(i=>['blocker','high'].includes(i.severity)).length,0)};
await fs.writeFile(path.join(out,'audit.json'),JSON.stringify(summary,null,2));
const lines=['# Visual QA Report','',`Origin: ${base}`,`Routes: ${routes.length}; captures: ${results.length}; issues: ${summary.totalIssues}; high/blocker: ${summary.blockingIssues}`,''];
for(const r of results){lines.push(`## ${r.route} / ${r.viewport.id}`,`Screenshot: ${r.screenshot||'not captured'}`,`HTTP: ${r.status??'unknown'}`,...(r.issues.length?r.issues.map(i=>`- **${i.severity}** ${i.kind}${i.rule?' ('+i.rule+')':''}: ${JSON.stringify(i.details).slice(0,700)}`):['- No automated findings']), '');}
await fs.writeFile(path.join(out,'report.md'),lines.join('\n'));
console.log(`Visual QA: ${summary.totalIssues} issues (${summary.blockingIssues} high/blocker). Report: ${path.join(out,'report.md')}`);
if(summary.blockingIssues)process.exitCode=1;
