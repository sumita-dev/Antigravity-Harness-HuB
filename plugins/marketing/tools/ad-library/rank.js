#!/usr/bin/env node
/**
 * Xếp hạng ad thắng từ 1 hoặc nhiều file JSON của scrape.js:
 * Chạy lâu + nhiều biến thể = đang được đầu tư ngân sách lớn.
 *
 * Dùng:
 *   node plugins/marketing/tools/ad-library/rank.js output/<file>.json [--top 15] [--min-days 7] [--test-variants 3] [--match "chống nắng"]
 *   node plugins/marketing/tools/ad-library/rank.js output/file1.json output/file2.json --top 20
 */
const { parseArgs, loadAds, rankAds } = require('./lib');

const args = parseArgs({
  top: 15,
  'min-days': 7,
  'test-variants': 3,
});

const files = args.files;
const top = parseInt(args.top, 10) || 15;
const minDays = parseInt(args['min-days'], 10) || 7;
const testVariants = parseInt(args['test-variants'], 10) || 3;
const matchStr = args.match;
const matchRegex = matchStr ? new RegExp(matchStr, 'i') : null;

if (!files || files.length === 0) {
  console.error('Thiếu file json đầu vào.');
  console.error('Cách dùng: node rank.js output/file1.json [output/file2.json ...] [--top 15] [--min-days 7] [--test-variants 3]');
  process.exit(1);
}

const allAds = loadAds(files, matchRegex);
if (!allAds.length) {
  console.error('Không tìm thấy quảng cáo nào trong các tệp đã cung cấp.');
  process.exit(0);
}

const result = rankAds(allAds, {
  top,
  minDays,
  match: matchRegex,
  testVariants,
});

if (args.json) {
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

console.log(`# Top ad (điểm = ngày chạy + 2×biến thể, từ ${minDays} ngày trở lên) [Tổng: ${result.total} ads, ${result.collapsedCount} creative gốc]\n`);

if (!result.ranked.length) {
  console.log(`(Chưa có ad nào đủ ${minDays} ngày chạy. Thử --min-days nhỏ hơn hoặc lấy nhiều ad hơn.)\n`);
} else {
  result.ranked.forEach((a, i) => {
    console.log(`${i + 1}. [${a.page_name}] ${a.format || 'MEDIA'} | ${a.days_running || 0}d | ${a.variants || 1} biến thể | CTA: ${a.cta || '-'}`);
    console.log(`   Hook: ${(a.body || '').replace(/\s+/g, ' ').slice(0, 160)}`);
    console.log(`   ${a.library_url}`);
  });
}

if (result.testing.length) {
  console.log(`\n# Đang test (mới < ${minDays} ngày, >= ${testVariants} biến thể)`);
  result.testing.forEach((a, i) => {
    console.log(`${i + 1}. [${a.page_name}] ${a.format || 'MEDIA'} | ${a.days_running || 0}d | ${a.variants || 1} biến thể | ${(a.body || '').replace(/\s+/g, ' ').slice(0, 120)}`);
    console.log(`   ${a.library_url}`);
  });
}

console.log('\nPhân bổ Format:', JSON.stringify(result.stats.fmt));
console.log('Phân bổ CTA:', JSON.stringify(result.stats.cta));
