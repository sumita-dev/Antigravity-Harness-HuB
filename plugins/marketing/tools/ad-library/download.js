#!/usr/bin/env node
/**
 * Tải trọn bộ media (ảnh HD, video, thumbnail preview) của các ad thắng về ổ cứng:
 * Phòng tránh rủi ro Meta CDN token hết hạn (HTTP 403 / 410 Expired).
 *
 * Dùng:
 *   node plugins/marketing/tools/ad-library/download.js output/<file>.json [--top 5] [--min-days 7]
 */
const fs = require('fs');
const path = require('path');
const { parseArgs, loadAds, rankAds, slug, outDir, download } = require('./lib');

const args = parseArgs({
  top: 5,
  'min-days': 7,
});

const files = args.files;
const top = parseInt(args.top, 10) || 5;
const minDays = parseInt(args['min-days'], 10) || 7;

if (!files || files.length === 0) {
  console.error('Thiếu file json đầu vào.');
  console.error('Cách dùng: node download.js output/<file>.json [--top 5] [--min-days 7] [--out-dir <dir>]');
  process.exit(1);
}

const allAds = loadAds(files);
if (!allAds.length) {
  console.error('Không có quảng cáo nào trong file đã cung cấp.');
  process.exit(0);
}

const { ranked } = rankAds(allAds, { top, minDays });
const targetAds = ranked.length ? ranked : allAds.slice(0, top);

const today = new Date().toISOString().slice(0, 10);
const baseCreativeDir = args['out-dir'] ? path.resolve(args['out-dir']) : path.join(outDir(), 'creative', today);

(async () => {
  console.log(`Bắt đầu tải media cho Top ${targetAds.length} quảng cáo vào ${baseCreativeDir}...\n`);
  const downloadedReport = [];

  for (let i = 0; i < targetAds.length; i++) {
    const a = targetAds[i];
    const rankNum = String(i + 1).padStart(2, '0');
    const pageSlug = slug(a.page_name || 'page');
    const adFolder = path.join(baseCreativeDir, `${rankNum}-${pageSlug}-${a.ad_id}`);
    fs.mkdirSync(adFolder, { recursive: true });

    const downloadedFiles = [];

    // 1. Tải ảnh
    const images = Array.isArray(a.images) ? a.images : [];
    for (let imgIdx = 0; imgIdx < images.length; imgIdx++) {
      const imgUrl = images[imgIdx];
      const ext = imgUrl.includes('.png') ? 'png' : 'jpg';
      const destName = `image_${imgIdx + 1}.${ext}`;
      const destPath = path.join(adFolder, destName);
      process.stdout.write(`- [${i + 1}/${targetAds.length}] Tải ảnh ${imgIdx + 1}/${images.length}... `);
      const ok = await download(imgUrl, destPath);
      if (ok) {
        console.log('OK');
        downloadedFiles.push(destPath);
      } else {
        console.log('FAIL (bỏ qua)');
      }
    }

    // 2. Tải video
    const videos = Array.isArray(a.videos) ? a.videos : [];
    for (let vidIdx = 0; vidIdx < videos.length; vidIdx++) {
      const vidUrl = videos[vidIdx];
      const destName = `video_${vidIdx + 1}.mp4`;
      const destPath = path.join(adFolder, destName);
      process.stdout.write(`- [${i + 1}/${targetAds.length}] Tải video ${vidIdx + 1}/${videos.length}... `);
      const ok = await download(vidUrl, destPath);
      if (ok) {
        console.log('OK');
        downloadedFiles.push(destPath);
      } else {
        console.log('FAIL (bỏ qua)');
      }
    }

    // 3. Tải video preview thumbnail nếu có
    if (a.video_preview && !images.includes(a.video_preview)) {
      const previewPath = path.join(adFolder, 'video_preview.jpg');
      process.stdout.write(`- [${i + 1}/${targetAds.length}] Tải video preview thumbnail... `);
      const ok = await download(a.video_preview, previewPath);
      if (ok) {
        console.log('OK');
        downloadedFiles.push(previewPath);
      } else {
        console.log('FAIL (bỏ qua)');
      }
    }

    // 4. Ghi file info.txt
    const infoContent = [
      `================================================================================`,
      `THÔNG TIN QUẢNG CÁO META ADS (AD ARCHIVE ID: ${a.ad_id})`,
      `================================================================================`,
      `Fanpage: ${a.page_name} (Page ID: ${a.page_id || 'N/A'})`,
      `Thư viện quảng cáo: ${a.library_url || 'https://www.facebook.com/ads/library/?id=' + a.ad_id}`,
      `Trang đích (Link URL): ${a.link_url || 'N/A'}`,
      `CTA Button: ${a.cta || 'N/A'}`,
      `Định dạng: ${a.format || 'N/A'}`,
      `Ngày bắt đầu chạy: ${a.start_date || 'N/A'}`,
      `Số ngày chạy liên tục: ${a.days_running || 0} ngày`,
      `Số biến thể (Collation count): ${a.variants || 1}`,
      `Nền tảng hiển thị: ${(a.platforms || []).join(', ') || 'N/A'}`,
      ``,
      `Tiêu đề (Headline): ${a.title || 'N/A'}`,
      `Phụ đề (Caption): ${a.link_caption || 'N/A'}`,
      ``,
      `Nội dung quảng cáo (Body text):`,
      `--------------------------------------------------------------------------------`,
      a.body || '(Trống)',
      `--------------------------------------------------------------------------------`,
      ``,
      `Tệp media đã tải về cục bộ (${downloadedFiles.length} tệp):`,
      ...downloadedFiles.map((f) => `- ${path.basename(f)} (${f})`),
      ``,
      `Thời gian tải: ${new Date().toISOString()}`,
    ].join('\n');

    fs.writeFileSync(path.join(adFolder, 'info.txt'), infoContent, { encoding: 'utf8' });

    downloadedReport.push({
      ad_id: a.ad_id,
      page_name: a.page_name,
      folder: adFolder,
      files: downloadedFiles,
    });
  }

  console.log(`\n[OK] Đã tải xong media cho ${downloadedReport.length} quảng cáo.`);
  if (args.json) {
    console.log(JSON.stringify(downloadedReport, null, 2));
  }
  process.exit(0);
})().catch((err) => {
  console.error('LỖI:', err.message);
  process.exit(1);
});
