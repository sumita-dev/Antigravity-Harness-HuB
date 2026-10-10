import { defineConfig, devices } from '@playwright/test';
const baseURL=process.env.UI_BASE_URL || 'http://127.0.0.1:3000';
export default defineConfig({testDir:'./tests',timeout:30000,expect:{timeout:10000,toHaveScreenshot:{animations:'disabled',caret:'hide',maxDiffPixelRatio:0.01}},fullyParallel:true,retries:process.env.CI?2:0,reporter:[['list'],['html',{open:'never'}]],use:{baseURL,trace:'retain-on-failure',screenshot:'only-on-failure'},projects:[{name:'desktop',use:{...devices['Desktop Chrome']}},{name:'mobile',use:{...devices['iPhone 13'],browserName:'chromium'}}]});
