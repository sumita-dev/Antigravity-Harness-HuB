#!/usr/bin/env node
/**
 * Xếp hạng Fanpage đối thủ trong ngách từ dữ liệu cào:
 * Đo lường mức độ vít ngân sách, số ad mới 7 ngày (new_7d), định dạng và CTA chủ đạo.
 *
 * Dùng:
 *   node plugins/marketing/tools/ad-library/pages.js output/<file>.json [--top 10] [--watchlist]
 *   node plugins/marketing/tools/ad-library/pages.js output/*.json --top 20 --watchlist
 */
const fs = require('fs');
const path = require('path');
const { parseArgs, loadAds, rankPages, getProjectRoot } = require('./lib');

const args = parseArgs({
  top: 10,
  'min-days': 0,
});

const files = args.files;
const top = parseInt(args.top, 10) || 10;
const minDays = parseInt(args['min-days'], 10) || 0;
const matchStr = args.match;
const matchRegex = matchStr ? new RegExp(matchStr, 'i') : null;
const isWatchlist = Boolean(args.watchlist);

if (!files || files.length === 0) {
  console.error('Thiếu file json đầu vào.');
  console.error('Cách dùng: node pages.js output/<file>.json [output/file2.json ...] [--top 10] [--watchlist]');
  process.exit(1);
}

const allAds = loadAds(files, matchRegex);
if (!allAds.length) {
  console.error('Không tìm thấy quảng cáo nào trong các tệp đã cung cấp.');
  process.exit(0);
}

const pages = rankPages(allAds, {
  top,
  minDays,
  match: matchRegex,
});

if (args.json) {
  console.log(JSON.stringify(pages, null, 2));
} else {
  console.log(`# Xếp Hạng Fanpage Đối Thủ (Top ${pages.length})\n`);
  console.log('| Top | Fanpage | Page ID | Ads | Creative | Mới 7d | Ngày max | Ngày TB | Format Top | CTA Top | Điểm |');
  console.log('| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |');
  pages.forEach((p, i) => {
    console.log(
      `| ${i + 1} | [${p.page_name}](${p.library_url || '#'}) | ${p.page_id || '-'} | ${p.total_ads} | ${p.creatives_count} | ${p.new_7d} | ${p.max_days}d | ${p.avg_days}d | ${p.top_format} | ${p.top_cta} | ${p.score} |`
    );
  });
}

if (isWatchlist && pages.length > 0) {
  const root = getProjectRoot();
  const defaultWatchlistPath = path.join(root, 'plugins', 'marketing', 'tools', 'ad-library', 'watchlist.json');
  const outPath = args['out-watchlist'] ? path.resolve(args['out-watchlist']) : defaultWatchlistPath;

  const watchlistData = {
    updated_at: new Date().toISOString(),
    targets: pages.map((p) => ({
      page_id: p.page_id,
      page_name: p.page_name,
      note: `Scale score ${p.score} | ${p.total_ads} ads (${p.new_7d} mới 7d) | Top format: ${p.top_format}`,
      library_url: p.library_url,
      last_checked: null,
    })),
  };

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(watchlistData, null, 2), { encoding: 'utf8' });
  console.log(`\n[OK] Đã xuất danh sách theo dõi Watchlist (${pages.length} pages) -> ${outPath}`);
}
