#!/usr/bin/env node
/**
 * Xếp hạng ad thắng từ file của scrape.js: chạy lâu + nhiều biến thể = đang được đầu tư tiền.
 *   node tools/ad-library/rank.js output/<file>.json [--top 15] [--min-days 7] [--match "chống nắng|spf"]
 */
const fs = require('fs');
const f = process.argv[2];
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const top = parseInt(opt('top', '15'), 10);
const minDays = parseInt(opt('min-days', '7'), 10);           // ad mới < N ngày chưa đủ tín hiệu thắng
const match = opt('match') && new RegExp(opt('match'), 'i');  // lọc theo tên page / tiêu đề / nội dung
if (!f || f.startsWith('--')) { console.error('Thiếu file json, vd: node tools/ad-library/rank.js output/<file>.json'); process.exit(1); }
const all = JSON.parse(fs.readFileSync(f, 'utf8')).ads;
const ads = match ? all.filter(a => match.test(`${a.page_name} ${a.title} ${a.body}`)) : all;

// gộp theo collation (cùng creative nhân bản) để không đếm trùng
const groups = new Map();
for (const a of ads) {
  const k = a.collation_id || a.ad_id;
  const g = groups.get(k);
  if (!g || (a.days_running || 0) > (g.days_running || 0)) groups.set(k, { ...a, variants: Math.max(a.variants || 1, g ? g.variants : 1) });
}
const score = a => (a.days_running || 0) + Math.min(a.variants || 1, 30) * 2;
const list = [...groups.values()];
const ranked = list.filter(a => (a.days_running || 0) >= minDays).sort((a, b) => score(b) - score(a)).slice(0, top);
// ad mới nhân bản nhiều = đối thủ đang test, chưa phải ad thắng
const testing = list.filter(a => (a.days_running || 0) < minDays && (a.variants || 1) >= 5).sort((a, b) => b.variants - a.variants).slice(0, 5);

console.log(`# Top ad (điểm = ngày chạy + 2×biến thể, từ ${minDays} ngày trở lên)\n`);
if (!ranked.length) console.log('(Chưa có ad nào đủ ngày chạy. Thử --min-days nhỏ hơn hoặc lấy nhiều ad hơn.)');
ranked.forEach((a, i) => {
  console.log(`${i + 1}. [${a.page_name}] ${a.format} | ${a.days_running}d | ${a.variants} biến thể | CTA: ${a.cta || '-'}`);
  console.log(`   Hook: ${(a.body || '').replace(/\s+/g, ' ').slice(0, 160)}`);
  console.log(`   ${a.library_url}`);
});
if (testing.length) {
  console.log('\n# Đang test (mới < ' + minDays + ' ngày, nhiều biến thể)');
  testing.forEach(a => console.log(`- [${a.page_name}] ${a.format} | ${a.days_running}d | ${a.variants} biến thể | ${(a.body || '').replace(/\s+/g, ' ').slice(0, 100)}\n  ${a.library_url}`));
}
const fmt = {}; ads.forEach(a => fmt[a.format] = (fmt[a.format] || 0) + 1);
const cta = {}; ads.forEach(a => a.cta && (cta[a.cta] = (cta[a.cta] || 0) + 1));
console.log('\nFormat:', JSON.stringify(fmt), '\nCTA:', JSON.stringify(cta));
