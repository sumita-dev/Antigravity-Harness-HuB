#!/usr/bin/env node
/**
 * Lấy quảng cáo từ Meta Ad Library (thư viện quảng cáo Facebook).
 * Bắt gói tin trực tiếp từ Meta Ad Library qua Playwright.
 *
 * Dùng:
 *   node plugins/marketing/tools/ad-library/scrape.js --q "kem chống nắng" --max 60 --sort top
 *   node plugins/marketing/tools/ad-library/scrape.js --page-id 123456789 --status all --max 100
 * Tham số:
 *   --country VN (mặc định) | --status active|inactive|all (mặc định active)
 *   --media all|image|video | --out file.json | --headed (hiện trình duyệt)
 *   --sort top|new|relevance (mặc định top: total_impressions)
 *   --loose (tìm kiếm mở rộng thay vì cụm từ chính xác)
 *   --cdp-port 9222 (gắn vào Chrome đang mở sẵn với --remote-debugging-port)
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { getProjectRoot, outDir, slug } = require('./lib');

const argv = process.argv.slice(2);
const arg = (k, d) => {
  const i = argv.indexOf('--' + k);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : d;
};
const flag = (k) => argv.includes('--' + k);

const q = arg('q');
const pageId = arg('page-id');
const country = arg('country', 'VN').toUpperCase();
const status = arg('status', 'active');
const media = arg('media', 'all');
const max = parseInt(arg('max', '50'), 10);
const cdpPort = arg('cdp-port');
const sortParam = arg('sort', 'top').toLowerCase();
const isLoose = flag('loose');

if (!q && !pageId) {
  console.error('Thiếu --q "từ khóa" hoặc --page-id <id>');
  process.exit(1);
}

// Xác định chế độ sort_data[mode]
let sortMode = 'total_impressions';
if (sortParam === 'new') {
  sortMode = 'relevancy_monthly_grouped';
} else if (sortParam === 'relevance') {
  sortMode = 'relevancy_monthly_grouped';
} else if (sortParam === 'top' || sortParam === 'total_impressions') {
  sortMode = 'total_impressions';
}

const params = new URLSearchParams({
  active_status: status,
  ad_type: 'all',
  country,
  media_type: media,
});

if (pageId) {
  params.set('view_all_page_id', pageId);
  params.set('search_type', 'page');
} else if (isLoose) {
  params.set('q', q);
  params.set('search_type', 'keyword_unordered');
} else {
  // Mặc định tìm kiếm chính xác theo cụm từ (Exact phrase match)
  const clean = q.replace(/^"+|"+$/g, '').trim();
  params.set('q', `"${clean}"`);
  params.set('search_type', 'keyword_exact_phrase');
}

const url = `https://www.facebook.com/ads/library/?${params.toString()}&sort_data[direction]=desc&sort_data[mode]=${sortMode}`;

const ads = new Map();

function walk(node) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) return node.forEach(walk);
  if (node.ad_archive_id && node.snapshot) addAd(node);
  for (const k in node) walk(node[k]);
}

const imgUrl = (x) =>
  (typeof x === 'string'
    ? x
    : x && (x.original_image_url || x.resized_image_url || x.watermarked_resized_image_url)) || null;

function addAd(a) {
  const s = a.snapshot || {};
  const cards = s.cards || [];
  const c0 = cards[0] || {};
  const id = String(a.ad_archive_id);
  const prev = ads.get(id);
  const startMs = a.start_date ? a.start_date * 1000 : null;
  const endMs = a.end_date && !a.is_active ? a.end_date * 1000 : null;
  const days = startMs ? Math.max(1, Math.round(((endMs || Date.now()) - startMs) / 86400000)) : null;

  const row = {
    ad_id: id,
    library_url: 'https://www.facebook.com/ads/library/?id=' + id,
    page_id: String(a.page_id || s.page_id || ''),
    page_name: a.page_name || s.page_name || '',
    is_active: a.is_active,
    start_date: startMs ? new Date(startMs).toISOString().slice(0, 10) : null,
    end_date: endMs ? new Date(endMs).toISOString().slice(0, 10) : null,
    days_running: days,
    variants: a.collation_count || 1,
    collation_id: a.collation_id || null,
    platforms: a.publisher_platform || [],
    format: s.display_format || null,
    body: (s.body && s.body.text) || c0.body || '',
    title: s.title || c0.title || '',
    cta: s.cta_text || c0.cta_text || '',
    link_url: s.link_url || c0.link_url || '',
    link_caption: s.caption || c0.caption || '',
    images: [...new Set([...(s.images || []), ...cards].map(imgUrl).filter(Boolean))],
    videos: [...new Set([...(s.videos || []), ...cards].map((v) => v.video_hd_url || v.video_sd_url).filter(Boolean))],
    video_preview: (s.videos && s.videos[0] && s.videos[0].video_preview_image_url) || c0.video_preview_image_url || null,
    card_count: cards.length,
  };

  if (prev) {
    for (const k in row) {
      if (row[k] == null || row[k] === '' || (Array.isArray(row[k]) && !row[k].length)) {
        row[k] = prev[k];
      }
    }
  }
  ads.set(id, row);
}

function parseText(t) {
  if (!t || !t.includes('ad_archive_id')) return;
  for (const line of t.replace(/^for \(;;\);/, '').split('\n')) {
    try {
      walk(JSON.parse(line));
    } catch {
      // Bỏ qua dòng không phải JSON thuần
    }
  }
}

(async () => {
  const browser = cdpPort
    ? await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`)
    : await chromium.launch({
        headless: !flag('headed'),
        args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
      });
  const ctx = cdpPort
    ? browser.contexts()[0]
    : await browser.newContext({ locale: 'vi-VN', viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();

  page.on('response', async (r) => {
    try {
      if (r.url().includes('/api/graphql')) parseText(await r.text());
    } catch {
      // response bị hủy
    }
  });

  console.error('Mở:', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(4000);

  // Lô đầu tiên có thể nằm sẵn trong script application/json
  const scripts = await page.$$eval('script[type="application/json"]', (els) =>
    els.map((e) => e.textContent).filter((t) => t.includes('ad_archive_id'))
  );
  for (const s of scripts) {
    try {
      walk(JSON.parse(s));
    } catch {
      // bỏ qua
    }
  }

  let stale = 0,
    last = -1;
  while (ads.size < max && stale < 6) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2500);
    if (ads.size === last) stale++;
    else {
      stale = 0;
      last = ads.size;
    }
    console.error('...', ads.size, 'ads');
  }

  const out = [...ads.values()].slice(0, max);
  const outDirectory = outDir();
  const fileSlug = pageId ? `page-${pageId}` : slug(q);
  const defaultFile = path.join(outDirectory, `${fileSlug}-${country}-${new Date().toISOString().slice(0, 10)}.json`);
  const finalFile = arg('out', defaultFile);

  fs.mkdirSync(path.dirname(path.resolve(finalFile)), { recursive: true });
  fs.writeFileSync(
    finalFile,
    JSON.stringify(
      {
        query: { q, pageId, country, status, media, sort: sortMode, loose: isLoose },
        scraped_at: new Date().toISOString(),
        total: out.length,
        ads: out,
      },
      null,
      2
    ),
    { encoding: 'utf8' }
  );

  console.log(`OK ${out.length} ads -> ${finalFile}`);

  await page.close();
  if (!cdpPort) await browser.close();
  process.exit(0);
})().catch((e) => {
  console.error('LỖI:', e.message);
  process.exit(1);
});
