#!/usr/bin/env node
/**
 * Soi Landing Page di động (Mobile Landing Page Spy) bằng Playwright:
 * Bóc tách giá, ưu đãi, form chốt đơn SĐT, nút CTA, và kênh liên hệ.
 *
 * Dùng:
 *   node plugins/marketing/tools/ad-library/lp.js output/<file>.json [--top 5] [--out <file.json>]
 *   node plugins/marketing/tools/ad-library/lp.js --url "https://example.com/landing-page"
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { parseArgs, loadAds, outDir } = require('./lib');

const args = parseArgs({
  top: 5,
});

const files = args.files;
const singleUrl = args.url;
const top = parseInt(args.top, 10) || 5;

let targetUrls = [];

if (singleUrl) {
  targetUrls.push({ url: singleUrl, ad_id: 'manual', page_name: 'Manual' });
} else if (files && files.length > 0) {
  const allAds = loadAds(files);
  const seenUrls = new Set();

  for (const ad of allAds) {
    const rawUrl = (ad.link_url || '').trim();
    if (!rawUrl || !rawUrl.startsWith('http')) continue;
    // Bỏ qua các link nội bộ mạng xã hội không phải landing page bán hàng
    if (rawUrl.includes('facebook.com') || rawUrl.includes('fb.me') || rawUrl.includes('m.me')) {
      continue;
    }
    // Chuẩn hóa bỏ query tracking fbclid, utm_ để deduplicate
    try {
      const u = new URL(rawUrl);
      const cleanKey = `${u.hostname}${u.pathname}`;
      if (!seenUrls.has(cleanKey)) {
        seenUrls.add(cleanKey);
        targetUrls.push({
          url: rawUrl,
          ad_id: ad.ad_id,
          page_name: ad.page_name,
        });
      }
    } catch {
      if (!seenUrls.has(rawUrl)) {
        seenUrls.add(rawUrl);
        targetUrls.push({
          url: rawUrl,
          ad_id: ad.ad_id,
          page_name: ad.page_name,
        });
      }
    }
    if (targetUrls.length >= top) break;
  }
} else {
  console.error('Thiếu file json hoặc tham số --url.');
  console.error('Cách dùng: node lp.js output/<file>.json [--top 5] [--out <result.json>]');
  process.exit(1);
}

if (!targetUrls.length) {
  console.log('Không tìm thấy link landing page hợp lệ nào để quét.');
  process.exit(0);
}

(async () => {
  console.log(`Bắt đầu soi ${targetUrls.length} landing page bằng Playwright Mobile Viewport...\n`);

  const browser = await chromium.launch({
    headless: !args.headed,
    args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
  });

  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    locale: 'vi-VN',
    ignoreHTTPSErrors: true,
  });

  const page = await context.newPage();
  const results = [];

  for (let i = 0; i < targetUrls.length; i++) {
    const item = targetUrls[i];
    console.log(`[${i + 1}/${targetUrls.length}] Đang mở: ${item.url} (${item.page_name})...`);

    const pageResult = {
      ad_id: item.ad_id,
      page_name: item.page_name,
      requested_url: item.url,
      final_url: null,
      title: null,
      meta_description: null,
      headings: [],
      prices: [],
      offers: [],
      has_phone_form: false,
      buttons: [],
      contact_links: {
        zalo: null,
        messenger: null,
        hotline: null,
      },
      status: 'pending',
      error: null,
    };

    try {
      const response = await page.goto(item.url, {
        waitUntil: 'domcontentloaded',
        timeout: 30000,
      });

      pageResult.status = response ? response.status() : 200;
      pageResult.final_url = page.url();

      // Đợi render dynamic client-side (Ladipage, WordPress Elementor, React...)
      await page.waitForTimeout(2500);

      const parsed = await page.evaluate(() => {
        const title = document.title || '';
        const metaDesc =
          document.querySelector('meta[name="description"]')?.getAttribute('content') ||
          document.querySelector('meta[property="og:description"]')?.getAttribute('content') ||
          '';

        const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
          .map((h) => (h.textContent || '').trim().replace(/\s+/g, ' '))
          .filter((t) => t.length > 5 && t.length < 150)
          .slice(0, 15);

        const bodyText = document.body ? document.body.innerText || '' : '';

        // Trích xuất giá cả
        const priceRegex = /(?:\b\d{1,3}(?:[.,]\d{3})+|\b\d{2,4}[kK])\s*(?:đ|vnd|vnđ|đồng)?/gi;
        const rawPrices = (bodyText.match(priceRegex) || [])
          .map((p) => p.trim())
          .filter((p) => !/^\d{4}$/.test(p) && p.length <= 15); // lọc bỏ số năm như 2024, 2025
        const prices = [...new Set(rawPrices)].slice(0, 8);

        // Trích xuất ưu đãi
        const offerRegex = /(?:giảm|sale|khuyến mãi|ưu đãi|tặng|freeship|miễn phí|mua \d+ tặng \d+|combo)\s*[^\n,.<>]{2,50}/gi;
        const rawOffers = (bodyText.match(offerRegex) || []).map((o) => o.trim().replace(/\s+/g, ' '));
        const offers = [...new Set(rawOffers)].slice(0, 8);

        // Phát hiện form điền số điện thoại
        const phoneInputs = document.querySelectorAll(
          'input[type="tel"], input[name*="phone" i], input[placeholder*="điện thoại" i], input[placeholder*="sđt" i]'
        );
        const hasPhoneForm = phoneInputs.length > 0;

        // Trích xuất CTA buttons
        const buttonTexts = Array.from(document.querySelectorAll('button, a.btn, [class*="button"], [class*="btn"]'))
          .map((el) => (el.textContent || '').trim().replace(/\s+/g, ' '))
          .filter((t) => t.length >= 2 && t.length <= 40)
          .filter((t) =>
            /(?:đặt|mua|nhận|tư vấn|gọi|ngay|xem|đăng ký|gửi|chốt|liên hệ)/i.test(t)
          );
        const buttons = [...new Set(buttonTexts)].slice(0, 6);

        // Trích xuất kênh liên hệ
        const allLinks = Array.from(document.querySelectorAll('a[href]')).map((a) => a.getAttribute('href') || '');
        const zaloLink = allLinks.find((h) => h.includes('zalo.me')) || null;
        const messengerLink = allLinks.find((h) => h.includes('m.me') || h.includes('facebook.com/messages')) || null;
        const telLink = allLinks.find((h) => h.startsWith('tel:'))?.replace(/^tel:/, '').trim() || null;

        return {
          title,
          metaDesc,
          headings,
          prices,
          offers,
          hasPhoneForm,
          buttons,
          contactLinks: {
            zalo: zaloLink,
            messenger: messengerLink,
            hotline: telLink,
          },
        };
      });

      pageResult.title = parsed.title;
      pageResult.meta_description = parsed.metaDesc;
      pageResult.headings = parsed.headings;
      pageResult.prices = parsed.prices;
      pageResult.offers = parsed.offers;
      pageResult.has_phone_form = parsed.hasPhoneForm;
      pageResult.buttons = parsed.buttons;
      pageResult.contact_links = parsed.contactLinks;

      console.log(`  -> Title: ${pageResult.title.slice(0, 60)}`);
      console.log(`  -> Giá: ${pageResult.prices.join(', ') || 'Không tìm thấy'}`);
      console.log(`  -> Ưu đãi: ${pageResult.offers.slice(0, 3).join(' | ') || 'N/A'}`);
      console.log(`  -> Form SĐT: ${pageResult.has_phone_form ? 'CÓ (Chốt đơn qua form)' : 'Không'}`);
      console.log(`  -> CTA: ${pageResult.buttons.join(' | ') || 'N/A'}`);
    } catch (err) {
      console.log(`  -> LỖI CÀO: ${err.message}`);
      pageResult.error = err.message;
      pageResult.status = 'failed';
    }

    results.push(pageResult);
  }

  await page.close();
  await browser.close();

  const outDirectory = outDir();
  const today = new Date().toISOString().slice(0, 10);
  const defaultOutputFile = path.join(outDirectory, `lp-spy-${today}.json`);
  const finalOut = args.out ? path.resolve(args.out) : defaultOutputFile;

  fs.mkdirSync(path.dirname(finalOut), { recursive: true });
  fs.writeFileSync(finalOut, JSON.stringify(results, null, 2), { encoding: 'utf8' });

  console.log(`\n[OK] Đã hoàn tất soi ${results.length} landing page -> ${finalOut}`);
  if (args.json) {
    console.log(JSON.stringify(results, null, 2));
  }

  process.exit(0);
})().catch((err) => {
  console.error('LỖI CHUNG:', err.message);
  process.exit(1);
});
