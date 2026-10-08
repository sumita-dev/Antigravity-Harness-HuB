const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const tool = require('../plugins/marketing/skills/yt-competitor-analyzer/scripts/analyze.js');

async function run() {
  assert.equal(typeof tool.generateHtmlDashboard, 'function', 'import must expose renderer without CLI execution');
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/marketing-dashboard-malicious.json'), 'utf8'));
  const html = tool.generateHtmlDashboard(fixture.channels, fixture.videos, fixture.meta);
  assert(!html.includes('</script><script>globalThis.ATTACKER'));
  assert(!html.includes('<img src=x onerror='));
  assert(html.includes('\\u003c/script\\u003e'));
  assert.equal(tool.safeUrl('javascript:alert(1)'), '');
  assert.equal(tool.safeUrl('data:image/svg+xml,test'), '');
  assert.equal(tool.safeUrl('https://example.test/a'), 'https://example.test/a');
  const capped = await tool.fetchAllVideoIdsFromUploads('uploads', '', 3, async () => ({items: Array.from({length: 5}, (_, i) => ({contentDetails:{videoId:'video' + i}})),nextPageToken:'more'}));
  assert.equal(capped.length, 3);
  assert.equal(capped.coverage.truncated, true);
  let page = 0;
  const partial = await tool.fetchAllVideoIdsFromUploads('uploads', '', 100, async () => {
    if (++page === 2) throw Error('quota');
    return {items:[{contentDetails:{videoId:'one'}}],nextPageToken:'second'};
  });
  assert.equal(partial.length, 1);
  assert.equal(partial.coverage.failed, 1);
  assert.equal(partial.coverage.complete, false);
  const details = await tool.fetchVideos(['one','missing'], '', async () => ({items:[{id:'one',statistics:{viewCount:'1'}}]}));
  assert.deepEqual(details.coverage.missing_ids, ['missing']);
  assert(details.coverage.missing_metrics.some(m => m.id === 'one' && m.metric === 'commentCount'));
  assert.equal(details.coverage.complete, false);
  const hidden = await tool.fetchChannels(['channel'], '', async () => ({items:[{id:'channel',statistics:{viewCount:'0',hiddenSubscriberCount:true}}]}));
  assert.equal(hidden.coverage.complete, false);
  assert.equal(tool.metricValue(undefined), null);
  assert.equal(tool.metricValue('0'), 0);
  assert.equal(tool.csvCell(null), '"N/A"');
  assert.equal(tool.csvCell('=HYPERLINK("bad")'), '"\'=HYPERLINK(""bad"")"');
  const out = process.argv[2];
  if (out) fs.writeFileSync(out, html);
  console.log('analyzer offline regressions passed');
}
run().catch(e => {console.error(e); process.exitCode = 1;});
