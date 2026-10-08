// Offline browser regression: no service requests or real publishing.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const http = require('node:http');
const {chromium} = require('playwright');
const fixture = require('./fixtures/marketing-dashboard-malicious.json');
const {generateHtmlDashboard} = require('../plugins/marketing/skills/yt-competitor-analyzer/scripts/analyze.js');

async function run() {
  const output = path.resolve(process.argv[2] || '.brain/artifacts/harness-completion/tools-browser');
  fs.mkdirSync(output, {recursive:true});
  const html = generateHtmlDashboard(fixture.channels, fixture.videos, fixture.meta);
  fs.writeFileSync(path.join(output, 'dashboard.html'), html);
  const server = http.createServer((request, response) => {response.writeHead(200, {'Content-Type':'text/html;charset=utf-8'}); response.end(html);});
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  const evidence = {fixture: 'tests/fixtures/marketing-dashboard-malicious.json', externalRequests: [], errors: [], screenshots: [], interactions: []};
  try {
    browser = await chromium.launch({channel:'chrome', headless:true});
    for (const [name, viewport] of [['desktop',{width:1440,height:1000}], ['mobile',{width:390,height:844}]]) {
      const page = await browser.newPage({viewport});
      page.on('pageerror', error => evidence.errors.push({name,message:error.message}));
      page.on('console', message => {if (message.type() === 'error') evidence.errors.push({name,message:message.text()});});
      await page.route('**/*', route => {
        if (route.request().url().startsWith('http://127.0.0.1:')) return route.continue();
        evidence.externalRequests.push(route.request().url());
        return route.fulfill({status:200,contentType:route.request().resourceType() === 'script' ? 'application/javascript' : 'text/css',body:''});
      });
      await page.goto(`http://127.0.0.1:${server.address().port}/`, {waitUntil:'networkidle'});
      assert.equal(await page.evaluate(() => globalThis.ATTACKER), undefined);
      assert(!(await page.locator('body').innerText()).includes('Đã quét toàn diện'));
      assert(!(await page.locator('body').innerText()).includes('Toàn bộ video các kênh'));
      assert(await page.getByRole('button', {name:'Đổi giao diện'}).isVisible());
      assert.equal(await page.locator('#tbodyChannels tr').count(), 1);
      await page.locator('[data-action="videos"]').click();
      assert.equal(await page.locator('#f_vid_channel').inputValue(), fixture.channels[0].name);
      // This hostile fixture deliberately uses a different channel label on its video.
      await page.evaluate(() => resetVideoFilters());
      assert.equal(await page.locator('#tbodyVideos tr').count(), 1);
      await page.locator('[data-action="description"]').click();
      assert((await page.locator('#modalContent').innerText()).includes('</script>'));
      await page.evaluate(() => closeModal());
      await page.locator('[data-tag-index="0"]').click();
      assert.equal(await page.locator('#tbodyVideos tr').count(), 1);
      await page.evaluate(() => resetVideoFilters());
      await page.locator('#globalVideoSearch').fill('no matching video');
      await page.locator('#globalVideoSearch').dispatchEvent('input');
      assert((await page.locator('#tbodyVideos').innerText()).includes('Không tìm thấy'));
      await page.locator('#globalVideoSearch').fill('Test video');
      await page.locator('#globalVideoSearch').dispatchEvent('input');
      assert.equal(await page.locator('#tbodyVideos tr').count(), 1);
      const download = page.waitForEvent('download');
      await page.evaluate(() => exportJSON());
      const downloaded = await download;
      await downloaded.saveAs(path.join(output, `${name}-export.json`));
      const exported = JSON.parse(fs.readFileSync(path.join(output, `${name}-export.json`), 'utf8'));
      assert.equal(exported.videos[0].title, fixture.videos[0].title);
      assert.equal(exported.meta.coverage.complete, false);
      const csvDownload = page.waitForEvent('download');
      await page.evaluate(() => downloadVideosCSV(RAW_VIDEOS, 'fixture'));
      await (await csvDownload).saveAs(path.join(output, `${name}-export.csv`));
      assert(fs.readFileSync(path.join(output, `${name}-export.csv`), 'utf8').includes('"N/A"'));
      assert.equal(await page.evaluate(() => globalThis.ATTACKER), undefined);
      assert.equal(await page.locator('a[href^="javascript:"],img[src^="javascript:"],img[src^="data:"]').count(), 0);
      const size = await page.evaluate(() => ({viewport:innerWidth,body:document.body.scrollWidth}));
      assert(size.body <= size.viewport + 2, JSON.stringify(size));
      await page.evaluate(() => document.querySelectorAll('.overflow-x-auto').forEach(element => {element.scrollLeft=0;}));
      await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true});
      evidence.screenshots.push(path.join(output,`${name}.png`));
      evidence.interactions.push({name, sentinel:'not executed', channelFilter:'PASS', description:'PASS', hashtag:'PASS', search:'PASS', jsonExport:'PASS', csvExport:'PASS', layout:size});
      await page.close();
    }
    assert.deepEqual(evidence.errors, []);
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output,'evidence.json'), JSON.stringify(evidence,null,2));
  }
  console.log(JSON.stringify(evidence, null, 2));
}
run().catch(error => {console.error(error); process.exitCode=1;});
