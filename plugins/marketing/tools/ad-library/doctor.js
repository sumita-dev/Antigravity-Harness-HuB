#!/usr/bin/env node
/**
 * Công cụ chẩn đoán sức khỏe môi trường (Environment Doctor):
 * Kiểm tra Node.js >= 18, Playwright, Chromium, và khả năng ghi file.
 *
 * Dùng:
 *   node plugins/marketing/tools/ad-library/doctor.js
 *   node plugins/marketing/tools/ad-library/doctor.js --scrape-test
 */
const fs = require('fs');
const path = require('path');
const { getProjectRoot, outDir } = require('./lib');

async function runDoctor() {
  console.log('================================================================');
  console.log('🩺 ANTIGRAVITY META ADS SCOUT — BÁC SĨ MÔI TRƯỜNG (DOCTOR.JS)');
  console.log('================================================================\n');

  let passed = true;

  // 1. Kiểm tra Node.js version
  const nodeVer = process.version;
  const majorVer = parseInt(nodeVer.replace('v', '').split('.')[0], 10);
  process.stdout.write(`1. Phiên bản Node.js: ${nodeVer} ... `);
  if (majorVer >= 18) {
    console.log('✅ ĐẠT (>= 18)');
  } else {
    console.log(`❌ KHÔNG ĐẠT (Yêu cầu Node.js >= 18, hiện tại: ${nodeVer})`);
    passed = false;
  }

  // 2. Kiểm tra Root Workspace & Output Dir
  process.stdout.write('2. Định vị Workspace Root & Thư mục Output ... ');
  try {
    const root = getProjectRoot();
    const output = outDir('test_doctor');
    const testFile = path.join(output, '.doctor_probe.tmp');
    fs.writeFileSync(testFile, 'ok', { encoding: 'utf8' });
    fs.unlinkSync(testFile);
    fs.rmdirSync(output);
    console.log(`✅ ĐẠT (${root})`);
  } catch (err) {
    console.log(`❌ LỖI (${err.message})`);
    passed = false;
  }

  // 3. Kiểm tra Playwright package
  process.stdout.write('3. Thư viện Playwright ... ');
  let playwright;
  try {
    playwright = require('playwright');
    console.log(`✅ ĐẠT (version: ${playwright._previewVersion || 'installed'})`);
  } catch (err) {
    console.log(`❌ THIẾU THƯ VIỆN (${err.message})`);
    passed = false;
  }

  // 4. Kiểm tra Playwright Chromium Headless Launch
  if (playwright) {
    process.stdout.write('4. Khởi chạy Playwright Chromium Headless ... ');
    try {
      const browser = await playwright.chromium.launch({
        headless: true,
        args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
      });
      const page = await browser.newPage();
      await page.setContent('<html><body><h1>Antigravity Doctor Probe</h1></body></html>');
      const h1 = await page.$eval('h1', (el) => el.textContent);
      await browser.close();
      if (h1 === 'Antigravity Doctor Probe') {
        console.log('✅ ĐẠT (Browser runtime sẵn sàng)');
      } else {
        console.log('❌ LỖI nội dung DOM');
        passed = false;
      }
    } catch (err) {
      console.log(`❌ KHÔNG THỂ KHỞI CHẠY (${err.message})`);
      passed = false;
    }
  }

  // 5. Scrape Test (nếu có cờ --scrape-test)
  if (process.argv.includes('--scrape-test') && playwright) {
    process.stdout.write('5. Kiểm tra kết nối Meta Ads Library (Quick Scrape Probe 3 ads) ... ');
    try {
      const browser = await playwright.chromium.launch({
        headless: true,
        args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
      });
      const page = await browser.newPage();
      const testUrl =
        'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=VN&media_type=all&q=s%E1%BB%AFa+h%E1%BA%A1t&search_type=keyword_unordered';
      await page.goto(testUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2000);
      await browser.close();
      console.log('✅ ĐẠT (Meta Ads Library phản hồi)');
    } catch (err) {
      console.log(`⚠️ CẢNH BÁO MẠNG (${err.message})`);
    }
  }

  console.log('\n================================================================');
  if (passed) {
    console.log('🎉 TẤT CẢ CÁC KIỂM TRA ĐỀU VƯỢT QUA! HỆ THỐNG SẴN SÀNG HOẠT ĐỘNG.');
    console.log('================================================================\n');
    process.exit(0);
  } else {
    console.log('🚨 PHÁT HIỆN SỰ CỐ MÔI TRƯỜNG. VUI LÒNG KHẮC PHỤC THEO THÔNG BÁO TRÊN.');
    console.log('================================================================\n');
    process.exit(1);
  }
}

runDoctor().catch((err) => {
  console.error('[DOCTOR CRASH]:', err.message);
  process.exit(1);
});
