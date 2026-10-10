#!/usr/bin/env node
/** Captures privacy-conscious CSS/layout metadata + visual evidence. Does not change app code. */
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const base=process.env.UI_BASE_URL||'http://127.0.0.1:3000';
const origin=new URL(base).origin;
const routes=(process.env.UI_ROUTES||'/').split(',').map(s=>s.trim()).filter(Boolean);
const dest=path.resolve(process.env.UI_DESIGN_CAPTURE_DIR||'artifacts/design-capture');
const viewports=[{name:'mobile-390',width:390,height:844},{name:'tablet-768',width:768,height:1024},{name:'desktop-1440',width:1440,height:900}];
const allowCross=process.env.UI_ALLOW_CROSS_ORIGIN==='1';
if(routes.length===0||routes.length>15)throw Error('UI_ROUTES must contain 1–15 routes.');
for(const route of routes)if(!allowCross&&new URL(route,base).origin!==origin)throw Error(`Cross-origin route denied: ${route}`);
await fs.mkdir(dest,{recursive:true});
const browser=await chromium.launch({headless:true});
const captures=[];
try{
 for(const route of routes) for(const vp of viewports){
  const context=await browser.newContext({viewport:{width:vp.width,height:vp.height},reducedMotion:'reduce',deviceScaleFactor:1,colorScheme:'light'});
  const page=await context.newPage();
  const capture={route,viewport:vp.name,screenshot:null,metadata:null,status:'error',errors:[]};
  try{
   const url=new URL(route,base).toString();
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});
   if(!allowCross&&new URL(page.url()).origin!==origin)throw Error('Cross-origin redirect blocked.');
   if((response?.status()||200)>=400)throw Error(`HTTP ${response.status()}`);
   await page.evaluate(()=>document.fonts.ready);
   if(process.env.UI_CAPTURE_READY_SELECTOR)await page.locator(process.env.UI_CAPTURE_READY_SELECTOR).first().waitFor({timeout:10000});
   await page.addStyleTag({content:'*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important;caret-color:transparent!important}'});
   const meta=await page.evaluate(()=>{
    const selectors=['header','nav','main','footer','h1','h2','h3','button','input','select','textarea','a[href]','[role="dialog"]','[data-ui]'];
    const nodes=[...document.querySelectorAll(selectors.join(','))].slice(0,150);
    const sample=nodes.map((el,i)=>{
     const st=getComputedStyle(el),r=el.getBoundingClientRect();
     return {index:i,tag:el.tagName.toLowerCase(),role:el.getAttribute('role'),component:el.getAttribute('data-ui'),type:el.getAttribute('type'),rect:{x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)},style:{fontSize:st.fontSize,fontWeight:st.fontWeight,lineHeight:st.lineHeight,color:st.color,backgroundColor:st.backgroundColor,gap:st.gap,padding:st.padding,borderRadius:st.borderRadius,display:st.display}};
    });
    const body=getComputedStyle(document.body);
    return {titleLength:document.title.length,documentLang:document.documentElement.lang||null,landmarks:{main:document.querySelectorAll('main').length,nav:document.querySelectorAll('nav').length,h1:document.querySelectorAll('h1').length},bodyStyle:{fontFamily:body.fontFamily,fontSize:body.fontSize,color:body.color,backgroundColor:body.backgroundColor},documentWidth:document.documentElement.scrollWidth,viewportWidth:document.documentElement.clientWidth,sampledElements:sample};
   });
   const key=crypto.createHash('sha256').update(route+vp.name).digest('hex').slice(0,14);
   const shot=path.join(dest,`${key}.png`);
   await page.screenshot({path:shot,fullPage:true,animations:'disabled',timeout:20000});
   capture.screenshot=path.basename(shot);capture.metadata=meta;capture.status='ok';
  }catch(error){capture.errors.push(String(error));}
  finally{captures.push(capture);await context.close();}
 }
}finally{await browser.close()}
const report={version:'4.0.0',origin,createdAt:new Date().toISOString(),captures};
await fs.writeFile(path.join(dest,'capture.json'),JSON.stringify(report,null,2)+'\n');
console.log(`Captured ${captures.filter(c=>c.status==='ok').length}/${captures.length} route/viewport states: ${dest}`);
if(captures.some(c=>c.status!=='ok'))process.exitCode=1;
