import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const routes=(process.env.UI_ROUTES||'/').split(',').map(s=>s.trim()).filter(Boolean);
for(const route of routes){
 test.describe(`UI quality: ${route}`,()=>{
  test('loads without document horizontal overflow',async({page})=>{
   const response=await page.goto(route);expect(response?.status()).toBeLessThan(400);
   await expect(page.locator('body')).toBeVisible();
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+2);
   expect(overflow,'document wider than viewport').toBe(false);
  });
  test('has no serious or critical axe violations',async({page})=>{
   await page.goto(route);
   const results=await new AxeBuilder({page}).analyze();
   const severe=results.violations.filter(v=>['serious','critical'].includes(v.impact||''));
   expect(severe,JSON.stringify(severe,null,2)).toEqual([]);
  });
  test('matches human-approved visual baseline',async({page})=>{
   test.skip(process.env.UI_VISUAL!=='1','Set UI_VISUAL=1 for visual regression');
   await page.goto(route);await page.evaluate(()=>document.fonts.ready);
   await expect(page).toHaveScreenshot(`${route.replace(/[^a-z0-9]+/gi,'-')||'home'}.png`,{fullPage:true});
  });
 });
}
