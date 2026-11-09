const fs = require('fs');
const path = require('path');

/**
 * Tìm kiếm thư mục gốc của project (chứa GEMINI.md hoặc .git).
 * Tránh lỗi lệch đường dẫn khi chạy từ thư mục con.
 */
function getProjectRoot() {
  if (process.env.ANTIGRAVITY_ROOT && fs.existsSync(process.env.ANTIGRAVITY_ROOT)) {
    return path.resolve(process.env.ANTIGRAVITY_ROOT);
  }
  let curr = __dirname;
  for (let i = 0; i < 6; i++) {
    if (fs.existsSync(path.join(curr, 'GEMINI.md')) || fs.existsSync(path.join(curr, '.git'))) {
      return curr;
    }
    const parent = path.dirname(curr);
    if (parent === curr) break;
    curr = parent;
  }
  return path.resolve(__dirname, '..', '..', '..', '..');
}

/**
 * Lấy đường dẫn thư mục output an toàn, tự tạo nếu chưa có.
 */
function outDir(subdir = '') {
  const root = getProjectRoot();
  const dir = subdir ? path.join(root, 'output', subdir) : path.join(root, 'output');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * Parse arguments CLI dạng --key value và --flag, đồng thời thu thập danh sách tệp lẻ.
 */
function parseArgs(defaults = {}) {
  const argv = process.argv.slice(2);
  const args = { ...defaults, files: [] };
  for (let i = 0; i < argv.length; i++) {
    const item = argv[i];
    if (item.startsWith('--')) {
      const key = item.slice(2);
      if (i + 1 < argv.length && !argv[i + 1].startsWith('--')) {
        const nextVal = argv[i + 1];
        if (nextVal === 'true') args[key] = true;
        else if (nextVal === 'false') args[key] = false;
        else if (/^\d+$/.test(nextVal)) args[key] = parseInt(nextVal, 10);
        else args[key] = nextVal;
        i++;
      } else {
        args[key] = true;
      }
    } else {
      args.files.push(item);
    }
  }
  return args;
}

/**
 * Tạo slug an toàn cho tên file/thư mục.
 */
function slug(text) {
  if (!text) return 'unknown';
  return String(text)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 50);
}

/**
 * Rút gọn chuỗi thành 1 dòng với độ dài tối đa.
 */
function short(text, maxLen = 120) {
  if (!text) return '';
  const clean = String(text).replace(/\s+/g, ' ').trim();
  return clean.length > maxLen ? clean.slice(0, maxLen) + '...' : clean;
}

/**
 * Đếm số lượng theo giá trị của thuộc tính hoặc hàm trích xuất.
 */
function count(arr, keyFn) {
  const res = {};
  for (const item of arr) {
    const k = typeof keyFn === 'function' ? keyFn(item) : item[keyFn];
    if (k) res[k] = (res[k] || 0) + 1;
  }
  return res;
}

function normalizeAdItem(a) {
  if (!a || typeof a !== 'object') return a;
  const days = a.days_running != null ? a.days_running : (a.days_active != null ? a.days_active : 0);
  const vars = a.variants != null ? a.variants : (a.variant_count != null ? a.variant_count : 1);
  const fmt = a.format || a.media_type || 'IMAGE';
  const cta = a.cta || a.cta_text || '';
  const body = a.body || a.body_text || '';
  const adId = String(a.ad_id || a.ad_archive_id || a.id || '');
  const libUrl = a.library_url || a.ad_snapshot_url || (adId ? 'https://www.facebook.com/ads/library/?id=' + adId : '');
  const link = a.link_url || '';
  const images = Array.isArray(a.images) ? a.images : (Array.isArray(a.media_urls) ? a.media_urls.filter(u => !u.includes('.mp4')) : []);
  const videos = Array.isArray(a.videos) ? a.videos : (Array.isArray(a.media_urls) ? a.media_urls.filter(u => u.includes('.mp4')) : []);

  return {
    ...a,
    ad_id: adId,
    page_id: String(a.page_id || ''),
    page_name: a.page_name || 'Chưa rõ',
    days_running: days,
    variants: vars,
    format: fmt.toUpperCase(),
    cta,
    body,
    title: a.title || '',
    link_url: link,
    library_url: libUrl,
    images,
    videos,
  };
}

/**
 * Nạp danh sách quảng cáo từ 1 hoặc nhiều file JSON.
 */
function loadAds(fileOrFiles, matchRegex = null) {
  const files = Array.isArray(fileOrFiles) ? fileOrFiles : [fileOrFiles];
  const allAds = [];
  for (const f of files) {
    if (!f || !fs.existsSync(f)) continue;
    try {
      const content = fs.readFileSync(f, 'utf8');
      const data = JSON.parse(content);
      const ads = Array.isArray(data) ? data : (data.ads || []);
      for (const rawAd of ads) {
        const ad = normalizeAdItem(rawAd);
        if (matchRegex) {
          const haystack = `${ad.page_name || ''} ${ad.title || ''} ${ad.body || ''} ${ad.link_caption || ''}`;
          if (!matchRegex.test(haystack)) continue;
        }
        allAds.push(ad);
      }
    } catch (e) {
      console.error(`Không thể đọc tệp ${f}:`, e.message);
    }
  }
  return allAds;
}

/**
 * Gộp các biến thể trùng creative theo collation_id hoặc ad_id.
 */
function collapse(ads) {
  const groups = new Map();
  for (const a of ads) {
    const k = a.collation_id || a.ad_id;
    const g = groups.get(k);
    if (!g) {
      groups.set(k, { ...a });
    } else {
      const daysA = a.days_running || 0;
      const daysG = g.days_running || 0;
      const variantsA = a.variants || 1;
      const variantsG = g.variants || 1;
      if (daysA > daysG) {
        groups.set(k, { ...a, variants: Math.max(variantsA, variantsG) });
      } else {
        g.variants = Math.max(variantsA, variantsG);
      }
    }
  }
  return [...groups.values()];
}

/**
 * Tính điểm winning ad: ngày chạy + min(biến thể, 30) * 2.
 */
function score(ad) {
  return (ad.days_running || 0) + Math.min(ad.variants || 1, 30) * 2;
}

/**
 * Xếp hạng ad thắng và phát hiện các ad đang test.
 */
function rankAds(ads, { top = 15, minDays = 7, match = null, testVariants = 3 } = {}) {
  const regex = match ? (typeof match === 'string' ? new RegExp(match, 'i') : match) : null;
  const filtered = regex ? ads.filter(a => regex.test(`${a.page_name || ''} ${a.title || ''} ${a.body || ''}`)) : ads;
  const collapsed = collapse(filtered);
  const ranked = collapsed
    .filter(a => (a.days_running || 0) >= minDays)
    .sort((a, b) => score(b) - score(a))
    .slice(0, top);

  const testing = collapsed
    .filter(a => (a.days_running || 0) < minDays && (a.variants || 1) >= testVariants)
    .sort((a, b) => (b.variants || 1) - (a.variants || 1))
    .slice(0, 10);

  const fmt = count(filtered, 'format');
  const cta = count(filtered, 'cta');

  return { ranked, testing, stats: { fmt, cta }, total: filtered.length, collapsedCount: collapsed.length };
}

/**
 * Xếp hạng Fanpage đối thủ trong ngách.
 */
function rankPages(ads, { top = 10, minDays = 0, match = null } = {}) {
  const regex = match ? (typeof match === 'string' ? new RegExp(match, 'i') : match) : null;
  const filtered = regex ? ads.filter(a => regex.test(`${a.page_name || ''} ${a.title || ''} ${a.body || ''}`)) : ads;

  const pageMap = new Map();
  for (const ad of filtered) {
    const pid = String(ad.page_id || ad.page_name || 'unknown');
    if (!pageMap.has(pid)) {
      pageMap.set(pid, {
        page_id: ad.page_id || '',
        page_name: ad.page_name || 'Chưa rõ',
        ads: [],
        collations: new Set(),
      });
    }
    const p = pageMap.get(pid);
    p.ads.push(ad);
    p.collations.add(ad.collation_id || ad.ad_id);
  }

  const results = [];
  for (const [, p] of pageMap.entries()) {
    const totalAds = p.ads.length;
    const totalVariants = p.ads.reduce((acc, a) => acc + (a.variants || 1), 0);
    const new7d = p.ads.filter(a => (a.days_running || 0) <= 7).length;
    const maxDays = p.ads.reduce((max, a) => Math.max(max, a.days_running || 0), 0);
    const avgDays = Math.round(p.ads.reduce((acc, a) => acc + (a.days_running || 0), 0) / (totalAds || 1));

    const formats = count(p.ads, 'format');
    const ctas = count(p.ads, 'cta');
    const topFormat = Object.entries(formats).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A';
    const topCta = Object.entries(ctas).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A';

    // Điểm scale: tổng ad x 2 + ad mới 7d x 3 + ngày chạy tối đa
    const pageScore = totalAds * 2 + new7d * 3 + maxDays;

    if (maxDays >= minDays) {
      results.push({
        page_id: p.page_id,
        page_name: p.page_name,
        total_ads: totalAds,
        total_variants: totalVariants,
        creatives_count: p.collations.size,
        new_7d: new7d,
        max_days: maxDays,
        avg_days: avgDays,
        top_format: topFormat,
        top_cta: topCta,
        score: pageScore,
        library_url: p.page_id ? `https://www.facebook.com/ads/library/?view_all_page_id=${p.page_id}` : '',
      });
    }
  }

  results.sort((a, b) => b.score - a.score);
  return results.slice(0, top);
}

/**
 * Tải file an toàn qua fetch, có timeout và không throw exception.
 */
async function download(url, destPath) {
  if (!url || !destPath) return false;
  fs.mkdirSync(path.dirname(destPath), { recursive: true });

  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) {
      return false;
    }
    const arrayBuffer = await res.arrayBuffer();
    fs.writeFileSync(destPath, Buffer.from(arrayBuffer));
    return true;
  } catch (err) {
    return false;
  }
}

module.exports = {
  getProjectRoot,
  outDir,
  parseArgs,
  slug,
  short,
  count,
  loadAds,
  collapse,
  score,
  rankAds,
  rankPages,
  download,
};
