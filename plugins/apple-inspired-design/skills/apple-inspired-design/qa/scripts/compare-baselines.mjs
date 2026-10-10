#!/usr/bin/env node
// Explicit baseline comparison is owned by Playwright toHaveScreenshot snapshots.
// Prevent accidental updates in CI. Human review required before updating approved images.
import { spawnSync } from 'node:child_process';
if(process.env.CI && process.argv.includes('--update-snapshots')){
 console.error('Baseline updates are forbidden in CI.');process.exit(2);
}
const args=['playwright','test',...process.argv.slice(2)];
const r=spawnSync(process.platform==='win32'?'npx.cmd':'npx',args,{stdio:'inherit',env:{...process.env,UI_VISUAL:'1'}});
process.exit(r.status??1);
