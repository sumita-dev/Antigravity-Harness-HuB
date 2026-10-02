#!/usr/bin/env node

/**
 * YouTube Competitor Analyzer
 * SubAgent Skill Automation Script - Full Channel Scrape Edition
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const DEFAULT_API_KEY = process.env.YOUTUBE_API_KEY || 'YOUR_YOUTUBE_API_KEY';

// Helper to make HTTPS GET requests
function getRequest(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error(parsed.error.message || JSON.stringify(parsed.error)));
          } else {
            resolve(parsed);
          }
        } catch (e) {
          reject(new Error(`JSON Parse error: ${e.message} - Data: ${data.slice(0, 200)}`));
        }
      });
    }).on('error', reject);
  });
}

// Extract Video IDs from text or URLs
function extractVideoIds(content) {
  const ids = new Set();
  const urlRegex = /(?:v=|youtu\.be\/|shorts\/|embed\/)([a-zA-Z0-9_-]{11})/g;
  let match;
  while ((match = urlRegex.exec(content)) !== null) {
    ids.add(match[1]);
  }

  if (ids.size === 0) {
    const rawIds = content.split(/[\s,;\r\n]+/).map(s => s.trim()).filter(s => /^[a-zA-Z0-9_-]{11}$/.test(s));
    rawIds.forEach(id => ids.add(id));
  }

  return Array.from(ids);
}

// Fetch video details in chunks
async function fetchVideos(videoIds, apiKey) {
  const allVideos = [];
  const chunkSize = 50;
  for (let i = 0; i < videoIds.length; i += chunkSize) {
    const chunk = videoIds.slice(i, i + chunkSize);
    const url = `https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id=${chunk.join(',')}&key=${apiKey}`;
    const res = await getRequest(url);
    if (res.items) {
      allVideos.push(...res.items);
    }
  }
  return allVideos;
}

// Fetch channel details
async function fetchChannels(channelIds, apiKey) {
  const allChannels = [];
  const chunkSize = 50;
  for (let i = 0; i < channelIds.length; i += chunkSize) {
    const chunk = channelIds.slice(i, i + chunkSize);
    const url = `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails,brandingSettings&id=${chunk.join(',')}&key=${apiKey}`;
    const res = await getRequest(url);
    if (res.items) {
      allChannels.push(...res.items);
    }
  }
  return allChannels;
}

// Fetch ALL video IDs from a channel's uploads playlist
async function fetchAllVideoIdsFromUploads(uploadsPlaylistId, apiKey, maxPerChannel = 1000) {
  const videoIds = [];
  let pageToken = '';
  while (videoIds.length < maxPerChannel) {
    let url = `https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId=${uploadsPlaylistId}&maxResults=50&key=${apiKey}`;
    if (pageToken) {
      url += `&pageToken=${pageToken}`;
    }
    const res = await getRequest(url);
    if (!res.items || res.items.length === 0) break;
    res.items.forEach(item => {
      if (item.contentDetails && item.contentDetails.videoId) {
        videoIds.push(item.contentDetails.videoId);
      }
    });
    pageToken = res.nextPageToken;
    if (!pageToken) break;
  }
  return videoIds;
}

// Extract hashtags
function extractHashtags(title = '', description = '', tags = []) {
  const set = new Set();
  const text = `${title} ${description}`;
  const regex = /#([a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]+)/g;
  let m;
  while ((m = regex.exec(text)) !== null) {
    set.add('#' + m[1]);
  }
  if (Array.isArray(tags)) {
    tags.slice(0, 8).forEach(t => {
      const formatted = t.trim().startsWith('#') ? t.trim() : '#' + t.trim().replace(/\s+/g, '');
      set.add(formatted);
    });
  }
  return Array.from(set);
}

// Generate Dashboard HTML
function generateHtmlDashboard(channelData, videoData, meta) {
  return `<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>YouTube Competitor Intelligence Dashboard (Full Channel Scan)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 500: '#ff0033', 600: '#cc0029', 700: '#99001f' },
            darkbg: '#0f172a',
            cardbg: '#1e293b',
            bordercol: '#334155'
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen custom-scrollbar transition-colors duration-200">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-wrap justify-between items-center gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-red-600 to-rose-400 flex items-center justify-center shadow-lg shadow-red-500/30">
          <i class="fa-brands fa-youtube text-xl text-white"></i>
        </div>
        <div>
          <h1 class="text-xl font-bold text-white flex items-center gap-2">
            YouTube Competitor Intelligence
            <span class="text-xs px-2.5 py-0.5 rounded-full bg-red-500/20 text-red-400 font-semibold border border-red-500/30">Toàn Bộ Video Kênh</span>
          </h1>
          <p class="text-xs text-slate-400">Quét toàn bộ video • Cập nhật: ${meta.generatedAt}</p>
        </div>
      </div>

      <div class="flex items-center gap-2.5">
        <button onclick="exportCSV('channels')" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5">
          <i class="fa-solid fa-file-csv text-emerald-400"></i> Xuất Kênh (CSV)
        </button>
        <button onclick="openExportModal()" class="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold shadow-md shadow-red-500/20 transition flex items-center gap-1.5">
          <i class="fa-solid fa-file-export"></i> Xuất Video (CSV)
        </button>
        <button onclick="exportJSON()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5">
          <i class="fa-solid fa-code text-amber-400"></i> JSON
        </button>
        <button onclick="toggleTheme()" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">
          <i id="themeIcon" class="fa-solid fa-sun"></i>
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
    <!-- Metric KPI Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="p-5 rounded-2xl bg-slate-800/60 border border-slate-700/80 shadow-sm relative overflow-hidden group">
        <div class="absolute -right-2 -bottom-2 opacity-10 text-6xl text-blue-400 group-hover:scale-110 transition"><i class="fa-solid fa-tv"></i></div>
        <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Tổng Số Kênh</span>
        <div class="text-3xl font-extrabold text-white mt-1" id="kpiChannels">${channelData.length}</div>
        <div class="text-xs text-emerald-400 mt-2 font-medium flex items-center gap-1">
          <i class="fa-solid fa-circle-check"></i> Đã quét toàn diện
        </div>
      </div>

      <div class="p-5 rounded-2xl bg-slate-800/60 border border-slate-700/80 shadow-sm relative overflow-hidden group">
        <div class="absolute -right-2 -bottom-2 opacity-10 text-6xl text-rose-400 group-hover:scale-110 transition"><i class="fa-solid fa-video"></i></div>
        <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Tổng Video Đã Quét</span>
        <div class="text-3xl font-extrabold text-white mt-1" id="kpiVideos">${videoData.length.toLocaleString('vi-VN')}</div>
        <div class="text-xs text-rose-400 mt-2 font-medium">Toàn bộ video các kênh</div>
      </div>

      <div class="p-5 rounded-2xl bg-slate-800/60 border border-slate-700/80 shadow-sm relative overflow-hidden group">
        <div class="absolute -right-2 -bottom-2 opacity-10 text-6xl text-amber-400 group-hover:scale-110 transition"><i class="fa-solid fa-fire"></i></div>
        <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Tổng Video Outlier</span>
        <div class="text-3xl font-extrabold text-amber-300 mt-1" id="kpiOutliers">${meta.totalOutliers.toLocaleString('vi-VN')}</div>
        <div class="text-xs text-amber-400 mt-2 font-medium" title="Đây là các video có lượt xem =2 lần số subcriber của kênh">
          Lượt xem ≥ 2x Subscriber
        </div>
      </div>

      <div class="p-5 rounded-2xl bg-slate-800/60 border border-slate-700/80 shadow-sm relative overflow-hidden group">
        <div class="absolute -right-2 -bottom-2 opacity-10 text-6xl text-cyan-400 group-hover:scale-110 transition"><i class="fa-solid fa-bolt"></i></div>
        <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Video View/Ngày Đỉnh Nhất</span>
        <div class="text-base font-bold text-cyan-300 mt-1 truncate" title="${meta.topVpdVideo.title}">${meta.topVpdVideo.title}</div>
        <div class="text-xs text-cyan-400 mt-2 font-medium">+${meta.topVpdVideo.viewsPerDay.toLocaleString('vi-VN')} view / ngày</div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="flex items-center justify-between border-b border-slate-800">
      <div class="flex space-x-2">
        <button onclick="switchTab('channels')" id="tabBtnChannels" class="px-5 py-3 text-sm font-semibold border-b-2 border-red-500 text-red-400 transition flex items-center gap-2">
          <i class="fa-solid fa-chart-pie"></i> Bảng 1: Thông Tin Chung Kênh (${channelData.length})
        </button>
        <button onclick="switchTab('videos')" id="tabBtnVideos" class="px-5 py-3 text-sm font-semibold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition flex items-center gap-2">
          <i class="fa-solid fa-clapperboard"></i> Bảng 2: Chi Tiết Toàn Bộ Video (${videoData.length.toLocaleString('vi-VN')})
        </button>
      </div>

      <div class="text-xs text-slate-400 flex items-center gap-2 pb-2">
        <i class="fa-solid fa-filter text-slate-500"></i> Bộ lọc tại từng tiêu đề cột & Sắp xếp tự động
      </div>
    </div>

    <!-- TAB 1: CHANNELS OVERVIEW -->
    <div id="tabContentChannels" class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="relative w-full sm:w-80">
          <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
          <input type="text" id="globalChannelSearch" placeholder="Tìm kiếm nhanh tên kênh..." 
            oninput="applyChannelFilters()" 
            class="w-full pl-9 pr-4 py-2 text-sm rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-red-500 transition">
        </div>

        <button onclick="resetChannelFilters()" class="text-xs text-slate-400 hover:text-red-400 transition flex items-center gap-1.5">
          <i class="fa-solid fa-rotate-right"></i> Đặt lại tất cả bộ lọc kênh
        </button>
      </div>

      <!-- Table 1 -->
      <div class="rounded-2xl border border-slate-800 bg-slate-800/40 backdrop-blur overflow-hidden shadow-xl">
        <div class="overflow-x-auto custom-scrollbar">
          <table class="w-full text-left border-collapse text-sm" id="tableChannels">
            <thead>
              <tr class="bg-slate-800/90 text-slate-300 font-semibold border-b border-slate-700">
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white" onclick="sortChannels('name')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Tên Kênh</span>
                    <i id="sortIcon_chan_name" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white" onclick="sortChannels('subscribers')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Subscribers</span>
                    <i id="sortIcon_chan_subscribers" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white" onclick="sortChannels('views')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Views (Toàn kênh)</span>
                    <i id="sortIcon_chan_views" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white" onclick="sortChannels('comments')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Comments</span>
                    <i id="sortIcon_chan_comments" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white" onclick="sortChannels('viewsPerDay')">
                  <div class="flex items-center justify-between gap-2">
                    <span>View / Day</span>
                    <i id="sortIcon_chan_viewsPerDay" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white" onclick="sortChannels('commentViewRatio')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Comment / View</span>
                    <i id="sortIcon_chan_commentViewRatio" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <!-- NEW COLUMN: OUTLIER -->
                <th class="py-3 px-4 cursor-pointer select-none hover:text-white group relative" onclick="sortChannels('outlierCount')" title="Đây là các video có lượt xem =2 lần số subcriber của kênh">
                  <div class="flex items-center justify-between gap-1.5">
                    <span class="flex items-center gap-1.5 text-amber-300">
                      <i class="fa-solid fa-fire text-amber-400"></i> Outlier
                      <i class="fa-solid fa-circle-question text-slate-400 text-xs group-hover:text-amber-300"></i>
                    </span>
                    <i id="sortIcon_chan_outlierCount" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-4 text-center">Hành Động</th>
              </tr>
              <!-- Filter Row -->
              <tr class="bg-slate-900/60 border-b border-slate-700/80">
                <th class="p-2">
                  <input type="text" id="f_chan_name" placeholder="Lọc tên..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_chan_sub" placeholder="Min sub..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_chan_views" placeholder="Min view..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_chan_comments" placeholder="Min cmt..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_chan_vpd" placeholder="Min view/ngày..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="text" id="f_chan_cvr" placeholder="Lọc tỷ lệ..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <!-- Filter for Outlier -->
                <th class="p-2">
                  <input type="number" id="f_chan_outlier" placeholder="Min outlier..." oninput="applyChannelFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2 text-center text-xs text-slate-500">--</th>
              </tr>
            </thead>
            <tbody id="tbodyChannels" class="divide-y divide-slate-800">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 2: VIDEOS DETAILS -->
    <div id="tabContentVideos" class="space-y-4 hidden">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="flex flex-wrap items-center gap-3">
          <div class="relative w-full sm:w-80">
            <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
            <input type="text" id="globalVideoSearch" placeholder="Tìm tiêu đề, hashtag, mô tả..." 
              oninput="applyVideoFilters()" 
              class="w-full pl-9 pr-4 py-2 text-sm rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-red-500 transition">
          </div>

          <!-- Quick Filter Outlier Button -->
          <button id="btnQuickOutlier" onclick="toggleQuickOutlier()" class="px-3 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1.5">
            <i class="fa-solid fa-fire text-amber-400"></i> Chỉ Video Outlier
          </button>
        </div>

        <div class="flex items-center gap-3">
          <span class="text-xs text-slate-400" id="videoCounter">Hiển thị: 0 video</span>
          <select id="pageSizeSelect" onchange="changePageSize(this.value)" class="px-2.5 py-1.5 text-xs rounded-xl bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none">
            <option value="25">25 dòng/trang</option>
            <option value="50" selected>50 dòng/trang</option>
            <option value="100">100 dòng/trang</option>
            <option value="99999">Tất cả</option>
          </select>
          <button onclick="resetVideoFilters()" class="text-xs text-slate-400 hover:text-red-400 transition flex items-center gap-1.5">
            <i class="fa-solid fa-rotate-right"></i> Đặt lại bộ lọc
          </button>
        </div>
      </div>

      <!-- Table 2 -->
      <div class="rounded-2xl border border-slate-800 bg-slate-800/40 backdrop-blur overflow-hidden shadow-xl">
        <div class="overflow-x-auto custom-scrollbar">
          <table class="w-full text-left border-collapse text-sm" id="tableVideos">
            <thead>
              <tr class="bg-slate-800/90 text-slate-300 font-semibold border-b border-slate-700">
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" onclick="sortVideos('channelTitle')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Kênh</span>
                    <i id="sortIcon_vid_channelTitle" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" style="min-width: 260px;" onclick="sortVideos('title')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Tiêu Đề Video</span>
                    <i id="sortIcon_vid_title" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" onclick="sortVideos('views')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Views</span>
                    <i id="sortIcon_vid_views" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" onclick="sortVideos('comments')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Comments</span>
                    <i id="sortIcon_vid_comments" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <!-- Views/Day -->
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" onclick="sortVideos('viewsPerDay')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Views / Day</span>
                    <i id="sortIcon_vid_viewsPerDay" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" onclick="sortVideos('date')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Date (Ngày đăng)</span>
                    <i id="sortIcon_vid_date" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <th class="py-3 px-3 cursor-pointer select-none hover:text-white" onclick="sortVideos('day')">
                  <div class="flex items-center justify-between gap-2">
                    <span>Day (Số ngày)</span>
                    <i id="sortIcon_vid_day" class="fa-solid fa-sort text-slate-500 text-xs"></i>
                  </div>
                </th>
                <!-- Hashtags & Descriptions pushed to end -->
                <th class="py-3 px-3 select-none" style="min-width: 140px;">Hashtags</th>
                <th class="py-3 px-3 text-center select-none" style="width: 100px;">Descriptions</th>
              </tr>
              <!-- Filter Row -->
              <tr class="bg-slate-900/60 border-b border-slate-700/80">
                <th class="p-2">
                  <select id="f_vid_channel" onchange="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                    <option value="">Tất cả kênh</option>
                    ${channelData.map(c => `<option value="${c.name}">${c.name}</option>`).join('')}
                  </select>
                </th>
                <th class="p-2">
                  <input type="text" id="f_vid_title" placeholder="Lọc tiêu đề..." oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_vid_views" placeholder="Min view..." oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_vid_comments" placeholder="Min cmt..." oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_vid_vpd" placeholder="Min view/ngày..." oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="text" id="f_vid_date" placeholder="YYYY-MM-DD" oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="number" id="f_vid_day" placeholder="Max ngày..." oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2">
                  <input type="text" id="f_vid_tag" placeholder="Lọc #tag..." oninput="applyVideoFilters()" class="w-full px-2 py-1 text-xs rounded bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-red-500">
                </th>
                <th class="p-2 text-center text-xs text-slate-500">--</th>
              </tr>
            </thead>
            <tbody id="tbodyVideos" class="divide-y divide-slate-800">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>

        <!-- Pagination Controls -->
        <div class="px-4 py-3 bg-slate-900/80 border-t border-slate-800 flex flex-wrap justify-between items-center gap-3">
          <div class="text-xs text-slate-400" id="paginationInfo">Trang 1 / 1</div>
          <div class="flex items-center space-x-1" id="paginationBtns">
            <!-- Rendered via JS -->
          </div>
        </div>
      </div>
    </div>
  </main>

  <!-- Description Modal -->
  <div id="descModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm hidden items-center justify-center p-4">
    <div class="bg-slate-800 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[80vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-150">
      <div class="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/80">
        <h3 id="modalTitle" class="font-bold text-base text-white truncate pr-4">Mô tả Video</h3>
        <button onclick="closeModal()" class="w-8 h-8 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition">
          <i class="fa-solid fa-xmark text-lg"></i>
        </button>
      </div>
      <div class="p-5 overflow-y-auto custom-scrollbar flex-1">
        <pre id="modalContent" class="text-xs text-slate-300 font-sans whitespace-pre-wrap leading-relaxed"></pre>
      </div>
      <div class="p-3 border-t border-slate-700 bg-slate-900/40 text-right">
        <button onclick="closeModal()" class="px-4 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold">Đóng</button>
      </div>
    </div>
  </div>

  <!-- Export Video CSV Modal -->
  <div id="exportModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm hidden items-center justify-center p-4">
    <div class="bg-slate-800 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in duration-150">
      <div class="flex justify-between items-center border-b border-slate-700 pb-3">
        <div class="flex items-center gap-2.5">
          <i class="fa-solid fa-file-csv text-emerald-400 text-xl"></i>
          <h3 class="font-bold text-lg text-white">Xuất Danh Sách Video (CSV)</h3>
        </div>
        <button onclick="closeExportModal()" class="text-slate-400 hover:text-white">
          <i class="fa-solid fa-xmark text-lg"></i>
        </button>
      </div>

      <p class="text-xs text-slate-300 leading-relaxed">
        File CSV xuất ra sẽ bao gồm <span class="text-emerald-400 font-semibold">toàn bộ các cột dữ liệu</span> của Bảng 2: Kênh, Tiêu Đề Video, URL Video, Views, Comments, Views/Day, Ngày Đăng, Số Ngày, Outlier, Hashtags, và Toàn văn Description.
      </p>

      <div class="space-y-3">
        <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider">Chọn phạm vi xuất dữ liệu:</label>
        
        <button onclick="executeExportCSV('all')" class="w-full p-3 rounded-xl bg-slate-700/60 hover:bg-slate-700 border border-slate-600/80 text-left transition flex items-center justify-between group">
          <div>
            <div class="text-sm font-bold text-white group-hover:text-emerald-300 transition">1. Toàn bộ Video của TẤT CẢ các kênh</div>
            <div class="text-xs text-slate-400">Xuất toàn bộ ${videoData.length.toLocaleString('vi-VN')} video đã quét</div>
          </div>
          <i class="fa-solid fa-cloud-arrow-down text-emerald-400 text-base"></i>
        </button>

        <button onclick="executeExportCSV('filtered')" class="w-full p-3 rounded-xl bg-slate-700/60 hover:bg-slate-700 border border-slate-600/80 text-left transition flex items-center justify-between group">
          <div>
            <div class="text-sm font-bold text-white group-hover:text-cyan-300 transition">2. Theo bộ lọc hiện tại trên Bảng 2</div>
            <div class="text-xs text-slate-400" id="exportFilteredCount">Đang lọc: ${videoData.length.toLocaleString('vi-VN')} video</div>
          </div>
          <i class="fa-solid fa-filter text-cyan-400 text-base"></i>
        </button>

        <div class="p-3 rounded-xl bg-slate-700/60 border border-slate-600/80 space-y-2">
          <div class="text-sm font-bold text-white">3. Xuất riêng cho một kênh cụ thể:</div>
          <div class="flex items-center gap-2">
            <select id="exportSelectChannel" class="flex-1 px-3 py-1.5 text-xs rounded-lg bg-slate-800 border border-slate-600 text-white focus:outline-none">
              ${channelData.map(c => `<option value="${c.id}">${c.name} (${c.scannedVideoCount || 0} video)</option>`).join('')}
            </select>
            <button onclick="executeExportCSV('singleChannel')" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold">
              Xuất
            </button>
          </div>
        </div>
      </div>

      <div class="text-right pt-2 border-t border-slate-700">
        <button onclick="closeExportModal()" class="px-4 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold">Đóng</button>
      </div>
    </div>
  </div>

  <script>
    const RAW_CHANNELS = ${JSON.stringify(channelData)};
    const RAW_VIDEOS = ${JSON.stringify(videoData)};

    let currentChannels = [...RAW_CHANNELS];
    let currentVideos = [...RAW_VIDEOS];

    let chanSort = { key: 'subscribers', asc: false };
    let vidSort = { key: 'viewsPerDay', asc: false };

    let currentPage = 1;
    let pageSize = 50;
    let onlyOutliers = false;

    function formatNum(num) {
      if (num === undefined || num === null) return '0';
      return Number(num).toLocaleString('vi-VN');
    }

    function switchTab(tab) {
      const tabC = document.getElementById('tabContentChannels');
      const tabV = document.getElementById('tabContentVideos');
      const btnC = document.getElementById('tabBtnChannels');
      const btnV = document.getElementById('tabBtnVideos');

      if (tab === 'channels') {
        tabC.classList.remove('hidden');
        tabV.classList.add('hidden');
        btnC.className = "px-5 py-3 text-sm font-semibold border-b-2 border-red-500 text-red-400 transition flex items-center gap-2";
        btnV.className = "px-5 py-3 text-sm font-semibold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition flex items-center gap-2";
      } else {
        tabC.classList.add('hidden');
        tabV.classList.remove('hidden');
        btnV.className = "px-5 py-3 text-sm font-semibold border-b-2 border-red-500 text-red-400 transition flex items-center gap-2";
        btnC.className = "px-5 py-3 text-sm font-semibold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition flex items-center gap-2";
      }
    }

    function filterVideosByChannel(channelName) {
      switchTab('videos');
      document.getElementById('f_vid_channel').value = channelName;
      onlyOutliers = false;
      updateQuickOutlierBtn();
      applyVideoFilters();
    }

    function filterOutliersByChannel(channelName) {
      switchTab('videos');
      document.getElementById('f_vid_channel').value = channelName;
      onlyOutliers = true;
      updateQuickOutlierBtn();
      applyVideoFilters();
    }

    function toggleQuickOutlier() {
      onlyOutliers = !onlyOutliers;
      updateQuickOutlierBtn();
      applyVideoFilters();
    }

    function updateQuickOutlierBtn() {
      const btn = document.getElementById('btnQuickOutlier');
      if (onlyOutliers) {
        btn.className = "px-3 py-2 text-xs font-semibold rounded-xl bg-amber-500 text-slate-900 border border-amber-400 shadow-md shadow-amber-500/20 transition flex items-center gap-1.5";
      } else {
        btn.className = "px-3 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1.5";
      }
    }

    // Channels logic
    function applyChannelFilters() {
      const q = document.getElementById('globalChannelSearch').value.toLowerCase();
      const fName = document.getElementById('f_chan_name').value.toLowerCase();
      const fSub = parseFloat(document.getElementById('f_chan_sub').value) || 0;
      const fViews = parseFloat(document.getElementById('f_chan_views').value) || 0;
      const fComments = parseFloat(document.getElementById('f_chan_comments').value) || 0;
      const fVpd = parseFloat(document.getElementById('f_chan_vpd').value) || 0;
      const fCvr = document.getElementById('f_chan_cvr').value.toLowerCase();
      const fOutlier = parseFloat(document.getElementById('f_chan_outlier').value) || 0;

      currentChannels = RAW_CHANNELS.filter(c => {
        const matchesGlobal = !q || c.name.toLowerCase().includes(q) || (c.handle && c.handle.toLowerCase().includes(q));
        const matchesName = !fName || c.name.toLowerCase().includes(fName) || (c.handle && c.handle.toLowerCase().includes(fName));
        const matchesSub = c.subscribers >= fSub;
        const matchesViews = c.views >= fViews;
        const matchesComments = c.comments >= fComments;
        const matchesVpd = c.viewsPerDay >= fVpd;
        const matchesCvr = !fCvr || (c.commentViewRatio + '%').toLowerCase().includes(fCvr);
        const matchesOutlier = c.outlierCount >= fOutlier;

        return matchesGlobal && matchesName && matchesSub && matchesViews && matchesComments && matchesVpd && matchesCvr && matchesOutlier;
      });

      sortChannels(chanSort.key, true);
    }

    function resetChannelFilters() {
      document.getElementById('globalChannelSearch').value = '';
      document.getElementById('f_chan_name').value = '';
      document.getElementById('f_chan_sub').value = '';
      document.getElementById('f_chan_views').value = '';
      document.getElementById('f_chan_comments').value = '';
      document.getElementById('f_chan_vpd').value = '';
      document.getElementById('f_chan_cvr').value = '';
      document.getElementById('f_chan_outlier').value = '';
      applyChannelFilters();
    }

    function sortChannels(key, keepDir = false) {
      if (!keepDir) {
        if (chanSort.key === key) {
          chanSort.asc = !chanSort.asc;
        } else {
          chanSort.key = key;
          chanSort.asc = (key === 'name');
        }
      }

      currentChannels.sort((a, b) => {
        let va = a[key];
        let vb = b[key];
        if (key === 'commentViewRatio') {
          va = parseFloat(va) || 0;
          vb = parseFloat(vb) || 0;
        }
        if (typeof va === 'string') {
          return chanSort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        return chanSort.asc ? (va - vb) : (vb - va);
      });

      renderChannelsTable();
    }

    function renderChannelsTable() {
      const tbody = document.getElementById('tbodyChannels');
      tbody.innerHTML = '';

      ['name', 'subscribers', 'views', 'comments', 'viewsPerDay', 'commentViewRatio', 'outlierCount'].forEach(k => {
        const el = document.getElementById('sortIcon_chan_' + k);
        if (el) {
          if (chanSort.key === k) {
            el.className = chanSort.asc ? "fa-solid fa-sort-up text-red-400 text-xs" : "fa-solid fa-sort-down text-red-400 text-xs";
          } else {
            el.className = "fa-solid fa-sort text-slate-500 text-xs";
          }
        }
      });

      if (currentChannels.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="py-8 text-center text-slate-400">Không tìm thấy kênh phù hợp với bộ lọc</td></tr>';
        return;
      }

      currentChannels.forEach(c => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/80 transition-colors";
        tr.innerHTML = \`
          <td class="py-3 px-4 font-semibold text-white">
            <div class="flex items-center space-x-3">
              \${c.avatar ? \`<img src="\${c.avatar}" class="w-8 h-8 rounded-full border border-slate-700 flex-shrink-0">\` : ''}
              <div>
                <a href="\${c.channelUrl}" target="_blank" class="hover:text-red-400 transition hover:underline flex items-center gap-1.5">
                  \${c.name} <i class="fa-solid fa-arrow-up-right-from-square text-[10px] opacity-70"></i>
                </a>
                <div class="text-[11px] text-slate-400 font-normal">\${c.handle || ''}</div>
              </div>
            </div>
          </td>
          <td class="py-3 px-4 text-slate-300 font-medium">\${formatNum(c.subscribers)}</td>
          <td class="py-3 px-4 text-slate-300 font-medium">\${formatNum(c.views)}</td>
          <td class="py-3 px-4 text-slate-300 font-medium">\${formatNum(c.comments)}</td>
          <td class="py-3 px-4 text-emerald-400 font-medium">+\${formatNum(c.viewsPerDay)}/ngày</td>
          <td class="py-3 px-4 text-cyan-300 font-medium">\${c.commentViewRatio}%</td>
          <!-- NEW COLUMN: Outlier with Tooltip Hint -->
          <td class="py-3 px-4 text-center">
            <button onclick="filterOutliersByChannel('\${c.name.replace(/'/g, "\\\\'")}')" 
              title="Đây là các video có lượt xem =2 lần số subcriber của kênh (Bấm để xem danh sách video)"
              class="px-2.5 py-1 rounded-full text-xs font-bold \${c.outlierCount > 0 ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 shadow-sm' : 'bg-slate-800 text-slate-500 border border-slate-700'} transition inline-flex items-center gap-1.5">
              <i class="fa-solid fa-fire text-[10px]"></i> \${c.outlierCount} video
            </button>
          </td>
          <td class="py-3 px-4 text-center whitespace-nowrap">
            <div class="flex items-center justify-center gap-1.5">
              <button onclick="filterVideosByChannel('\${c.name.replace(/'/g, "\\\\'")}')" 
                class="px-2.5 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-medium border border-red-500/30 transition flex items-center gap-1">
                <i class="fa-solid fa-filter"></i> Xem Video (\${c.scannedVideoCount || 0})
              </button>
              <button onclick="exportCSVForChannel('\${c.id}', '\${c.name.replace(/'/g, "\\\\'")}')" 
                title="Xuất toàn bộ \${c.scannedVideoCount || 0} video của kênh này ra file CSV"
                class="px-2 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/30 transition flex items-center gap-1">
                <i class="fa-solid fa-file-csv"></i> CSV
              </button>
            </div>
          </td>
        \`;
        tbody.appendChild(tr);
      });
    }

    // Videos logic
    function applyVideoFilters() {
      const q = document.getElementById('globalVideoSearch').value.toLowerCase();
      const fChan = document.getElementById('f_vid_channel').value;
      const fTitle = document.getElementById('f_vid_title').value.toLowerCase();
      const fViews = parseFloat(document.getElementById('f_vid_views').value) || 0;
      const fComments = parseFloat(document.getElementById('f_vid_comments').value) || 0;
      const fVpd = parseFloat(document.getElementById('f_vid_vpd').value) || 0;
      const fTag = document.getElementById('f_vid_tag').value.toLowerCase();
      const fDate = document.getElementById('f_vid_date').value.trim();
      const fDay = parseFloat(document.getElementById('f_vid_day').value) || 0;

      currentVideos = RAW_VIDEOS.filter(v => {
        const matchesGlobal = !q || v.title.toLowerCase().includes(q) || v.channelTitle.toLowerCase().includes(q) || (v.description && v.description.toLowerCase().includes(q)) || (v.hashtags && v.hashtags.some(t => t.toLowerCase().includes(q)));
        const matchesChan = !fChan || v.channelTitle === fChan;
        const matchesTitle = !fTitle || v.title.toLowerCase().includes(fTitle);
        const matchesViews = v.views >= fViews;
        const matchesComments = v.comments >= fComments;
        const matchesVpd = v.viewsPerDay >= fVpd;
        const matchesTag = !fTag || (v.hashtags && v.hashtags.some(t => t.toLowerCase().includes(fTag)));
        const matchesDate = !fDate || v.date.includes(fDate);
        const matchesDay = !fDay || v.day <= fDay;
        const matchesOutlier = !onlyOutliers || v.isOutlier;

        return matchesGlobal && matchesChan && matchesTitle && matchesViews && matchesComments && matchesVpd && matchesTag && matchesDate && matchesDay && matchesOutlier;
      });

      currentPage = 1;
      sortVideos(vidSort.key, true);
    }

    function resetVideoFilters() {
      document.getElementById('globalVideoSearch').value = '';
      document.getElementById('f_vid_channel').value = '';
      document.getElementById('f_vid_title').value = '';
      document.getElementById('f_vid_views').value = '';
      document.getElementById('f_vid_comments').value = '';
      document.getElementById('f_vid_vpd').value = '';
      document.getElementById('f_vid_tag').value = '';
      document.getElementById('f_vid_date').value = '';
      document.getElementById('f_vid_day').value = '';
      onlyOutliers = false;
      updateQuickOutlierBtn();
      applyVideoFilters();
    }

    function sortVideos(key, keepDir = false) {
      if (!keepDir) {
        if (vidSort.key === key) {
          vidSort.asc = !vidSort.asc;
        } else {
          vidSort.key = key;
          vidSort.asc = (key === 'title' || key === 'channelTitle');
        }
      }

      currentVideos.sort((a, b) => {
        let va = a[key];
        let vb = b[key];
        if (typeof va === 'string') {
          return vidSort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        return vidSort.asc ? (va - vb) : (vb - va);
      });

      renderVideosTable();
    }

    function changePageSize(val) {
      pageSize = parseInt(val, 10);
      currentPage = 1;
      renderVideosTable();
    }

    function renderVideosTable() {
      const tbody = document.getElementById('tbodyVideos');
      tbody.innerHTML = '';

      ['channelTitle', 'title', 'views', 'comments', 'viewsPerDay', 'date', 'day'].forEach(k => {
        const el = document.getElementById('sortIcon_vid_' + k);
        if (el) {
          if (vidSort.key === k) {
            el.className = vidSort.asc ? "fa-solid fa-sort-up text-red-400 text-xs" : "fa-solid fa-sort-down text-red-400 text-xs";
          } else {
            el.className = "fa-solid fa-sort text-slate-500 text-xs";
          }
        }
      });

      document.getElementById('videoCounter').innerText = \`Hiển thị: \${formatNum(currentVideos.length)} / \${formatNum(RAW_VIDEOS.length)} video\`;
      const filteredEl = document.getElementById('exportFilteredCount');
      if (filteredEl) filteredEl.innerText = \`Đang lọc: \${formatNum(currentVideos.length)} video\`;

      if (currentVideos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="py-8 text-center text-slate-400">Không tìm thấy video phù hợp với bộ lọc</td></tr>';
        renderPagination(0);
        return;
      }

      const totalPages = Math.ceil(currentVideos.length / pageSize);
      if (currentPage > totalPages) currentPage = totalPages;
      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = Math.min(startIdx + pageSize, currentVideos.length);

      const pageSlice = currentVideos.slice(startIdx, endIdx);

      pageSlice.forEach((v) => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/80 transition-colors";
        
        const tagBadges = (v.hashtags || []).slice(0, 3).map(t => 
          \`<span onclick="filterByTag('\${t}')" class="cursor-pointer inline-block px-1.5 py-0.5 rounded text-[11px] bg-slate-800 text-slate-300 hover:text-red-400 border border-slate-700 mr-1 mb-1 font-mono">\${t}</span>\`
        ).join('');

        const outlierBadge = v.isOutlier 
          ? \`<span class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30" title="Đây là các video có lượt xem =2 lần số subcriber của kênh"><i class="fa-solid fa-fire"></i> Outlier</span>\`
          : '';

        tr.innerHTML = \`
          <td class="py-3 px-3 font-medium text-slate-300 whitespace-nowrap">
            <span class="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
              \${v.channelTitle}
            </span>
          </td>
          <td class="py-3 px-3 font-semibold text-white">
            <div class="flex items-start space-x-2.5">
              \${v.thumbnail ? \`<img src="\${v.thumbnail}" class="w-14 h-9 object-cover rounded border border-slate-700 flex-shrink-0 mt-0.5">\` : ''}
              <div>
                <a href="\${v.videoUrl}" target="_blank" class="hover:text-red-400 transition hover:underline line-clamp-2 text-xs sm:text-sm">
                  \${v.title}
                </a>
                <div class="mt-0.5 flex items-center gap-1">\${outlierBadge}</div>
              </div>
            </div>
          </td>
          <td class="py-3 px-3 text-emerald-400 font-semibold whitespace-nowrap">\${formatNum(v.views)}</td>
          <td class="py-3 px-3 text-amber-300 font-semibold whitespace-nowrap">\${formatNum(v.comments)}</td>
          <!-- Views/Day -->
          <td class="py-3 px-3 text-cyan-400 font-semibold whitespace-nowrap">+\${formatNum(v.viewsPerDay)}</td>
          <td class="py-3 px-3 text-slate-400 font-mono text-xs whitespace-nowrap">\${v.date}</td>
          <td class="py-3 px-3 text-slate-300 font-mono text-xs whitespace-nowrap">\${v.day} ngày</td>
          <!-- Hashtags & Descriptions pushed to end -->
          <td class="py-3 px-3" style="max-width: 160px;">
            <div class="flex flex-wrap">\${tagBadges || '<span class="text-xs text-slate-500">--</span>'}</div>
          </td>
          <td class="py-3 px-3 text-center whitespace-nowrap">
            <button onclick="openModalById('\${v.id}')" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs">
              <i class="fa-regular fa-file-lines text-blue-400"></i> Xem
            </button>
          </td>
        \`;
        tbody.appendChild(tr);
      });

      renderPagination(totalPages);
    }

    function renderPagination(totalPages) {
      const info = document.getElementById('paginationInfo');
      const btns = document.getElementById('paginationBtns');
      btns.innerHTML = '';

      if (totalPages <= 1) {
        info.innerText = \`Hiển thị \${currentVideos.length} kết quả\`;
        return;
      }

      info.innerText = \`Trang \${currentPage} / \${totalPages} (Tổng \${formatNum(currentVideos.length)} video)\`;

      const prevBtn = document.createElement('button');
      prevBtn.className = "px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-xs hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed";
      prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
      prevBtn.disabled = currentPage === 1;
      prevBtn.onclick = () => { currentPage--; renderVideosTable(); };
      btns.appendChild(prevBtn);

      let startP = Math.max(1, currentPage - 2);
      let endP = Math.min(totalPages, currentPage + 2);

      for (let p = startP; p <= endP; p++) {
        const pBtn = document.createElement('button');
        pBtn.className = p === currentPage 
          ? "px-2.5 py-1 rounded bg-red-600 text-white font-bold text-xs border border-red-500"
          : "px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300 text-xs hover:bg-slate-700";
        pBtn.innerText = p;
        pBtn.onclick = () => { currentPage = p; renderVideosTable(); };
        btns.appendChild(pBtn);
      }

      const nextBtn = document.createElement('button');
      nextBtn.className = "px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-xs hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed";
      nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
      nextBtn.disabled = currentPage === totalPages;
      nextBtn.onclick = () => { currentPage++; renderVideosTable(); };
      btns.appendChild(nextBtn);
    }

    function filterByTag(tag) {
      document.getElementById('f_vid_tag').value = tag;
      applyVideoFilters();
    }

    function openModalById(id) {
      const v = RAW_VIDEOS.find(item => item.id === id);
      if (!v) return;
      document.getElementById('modalTitle').innerText = v.title;
      document.getElementById('modalContent').innerText = v.description || 'Không có mô tả.';
      document.getElementById('descModal').classList.remove('hidden');
      document.getElementById('descModal').classList.add('flex');
    }

    function closeModal() {
      document.getElementById('descModal').classList.add('hidden');
      document.getElementById('descModal').classList.remove('flex');
    }

    // Modal Export
    function openExportModal() {
      document.getElementById('exportModal').classList.remove('hidden');
      document.getElementById('exportModal').classList.add('flex');
    }

    function closeExportModal() {
      document.getElementById('exportModal').classList.add('hidden');
      document.getElementById('exportModal').classList.remove('flex');
    }

    // Export CSV Handlers
    function executeExportCSV(mode) {
      let videosToExport = [];
      let filenamePrefix = "all_videos";

      if (mode === 'all') {
        videosToExport = RAW_VIDEOS;
        filenamePrefix = "all_channels_videos";
      } else if (mode === 'filtered') {
        videosToExport = currentVideos;
        filenamePrefix = "filtered_videos";
      } else if (mode === 'singleChannel') {
        const selectedChanId = document.getElementById('exportSelectChannel').value;
        const selectedChanObj = RAW_CHANNELS.find(c => c.id === selectedChanId || c.name === selectedChanId);
        const selectedChanName = selectedChanObj ? selectedChanObj.name : selectedChanId;
        videosToExport = RAW_VIDEOS.filter(v => v.channelId === selectedChanId || v.channelTitle === selectedChanName);
        filenamePrefix = "channel_" + (selectedChanName || 'channel').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]/g, '_');
      }

      downloadVideosCSV(videosToExport, filenamePrefix);
      closeExportModal();
    }

    function exportCSVForChannel(channelId, channelName) {
      const vids = RAW_VIDEOS.filter(v => v.channelId === channelId || v.channelTitle === channelName);
      const filenamePrefix = "channel_" + (channelName || 'channel').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]/g, '_');
      downloadVideosCSV(vids, filenamePrefix);
    }

    function downloadVideosCSV(videosList, filenamePrefix) {
      if (!videosList || videosList.length === 0) {
        alert("Không có video nào để xuất!");
        return;
      }

      const rows = [
        ["Kênh", "Tiêu Đề Video", "URL Video", "Views", "Comments", "Views/Day", "Ngày Đăng", "Số Ngày Đã Trôi Qua", "Outlier (>=2x Sub)", "Hashtags", "Descriptions"]
      ];

      videosList.forEach(v => {
        const safeChan = (v.channelTitle || '').replace(/"/g, '""');
        const safeTitle = (v.title || '').replace(/"/g, '""');
        const safeUrl = (v.videoUrl || '').replace(/"/g, '""');
        const views = v.views !== undefined ? v.views : 0;
        const comments = v.comments !== undefined ? v.comments : 0;
        const viewsPerDay = v.viewsPerDay !== undefined ? v.viewsPerDay : 0;
        const date = v.date || '';
        const day = v.day !== undefined ? v.day : 0;
        const isOutlier = v.isOutlier ? "Yes" : "No";
        const tags = (v.hashtags || []).join(' ').replace(/"/g, '""');
        // Replace newlines with space to keep each video record on a single clean row in Excel
        const safeDesc = (v.description || '').replace(/"/g, '""').split(String.fromCharCode(10)).join(' ').split(String.fromCharCode(13)).join(' ');

        rows.push([
          '"' + safeChan + '"',
          '"' + safeTitle + '"',
          '"' + safeUrl + '"',
          views,
          comments,
          viewsPerDay,
          '"' + date + '"',
          day,
          '"' + isOutlier + '"',
          '"' + tags + '"',
          '"' + safeDesc + '"'
        ]);
      });

      const newline = String.fromCharCode(13, 10);
      const csvContent = "\uFEFF" + rows.map(r => r.join(',')).join(newline);

      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", filenamePrefix + "_" + new Date().toISOString().slice(0,10) + ".csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function exportCSV(type) {
      if (type === 'channels') {
        const rows = [
          ["Tên Kênh", "Subscribers", "Views", "Comments", "View/Day", "Comment/View %", "Outlier Videos", "Tổng Video Quét", "URL Kênh"]
        ];
        currentChannels.forEach(c => {
          const safeName = (c.name || '').replace(/"/g, '""');
          rows.push([
            '"' + safeName + '"',
            c.subscribers,
            c.views,
            c.comments,
            c.viewsPerDay,
            '"' + c.commentViewRatio + '%"',
            c.outlierCount,
            (c.scannedVideoCount || 0),
            '"' + c.channelUrl + '"'
          ]);
        });
        const newline = String.fromCharCode(13, 10);
        const csvContent = "\uFEFF" + rows.map(r => r.join(',')).join(newline);

        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "youtube_competitor_channels_" + new Date().toISOString().slice(0,10) + ".csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else {
        openExportModal();
      }
    }

    function exportJSON() {
      const exportData = {
        meta: ${JSON.stringify(meta)},
        channels: currentChannels,
        videos: currentVideos
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", "youtube_competitor_full_data_" + new Date().toISOString().slice(0,10) + ".json");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    function toggleTheme() {
      const html = document.documentElement;
      const icon = document.getElementById('themeIcon');
      if (html.classList.contains('dark')) {
        html.classList.remove('dark');
        icon.className = "fa-solid fa-moon";
      } else {
        html.classList.add('dark');
        icon.className = "fa-solid fa-sun";
      }
    }

    document.addEventListener('DOMContentLoaded', () => {
      renderChannelsTable();
      renderVideosTable();
    });
  </script>
</body>
</html>`;
}

// Main execution function
async function main() {
  const args = process.argv.slice(2);
  let inputFile = null;
  let rawUrls = null;
  let outputFile = path.join(process.cwd(), 'competitor_analysis_dashboard.html');
  let apiKey = DEFAULT_API_KEY;
  let maxVideosPerChannel = 1000;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--input' || args[i] === '-i') {
      inputFile = args[++i];
    } else if (args[i] === '--urls' || args[i] === '-u') {
      rawUrls = args[++i];
    } else if (args[i] === '--output' || args[i] === '-o') {
      outputFile = args[++i];
    } else if (args[i] === '--apiKey' || args[i] === '-k') {
      apiKey = args[++i];
    } else if (args[i] === '--maxPerChannel') {
      maxVideosPerChannel = parseInt(args[++i], 10);
    }
  }

  let content = '';
  if (inputFile) {
    if (!fs.existsSync(inputFile)) {
      console.error(`Error: File "${inputFile}" does not exist.`);
      process.exit(1);
    }
    content = fs.readFileSync(inputFile, 'utf8');
  } else if (rawUrls) {
    content = rawUrls;
  } else {
    try {
      content = fs.readFileSync(0, 'utf8');
    } catch (e) {}
  }

  if (!content || !content.trim()) {
    console.log(`
Usage:
  node analyze.js --input <path_to_urls_file> [--output <output.html>] [--apiKey <key>]
  node analyze.js --urls "https://youtu.be/xxx,https://youtube.com/watch?v=yyy"
    `);
    process.exit(1);
  }

  console.log('🔍 Bước 1: Trích xuất các Video ID từ dữ liệu đầu vào...');
  const seedVideoIds = extractVideoIds(content);
  if (seedVideoIds.length === 0) {
    console.error('❌ Không tìm thấy video YouTube hợp lệ nào.');
    process.exit(1);
  }

  console.log(`✅ Tìm thấy ${seedVideoIds.length} video mẫu. Đang truy vấn kênh sở hữu...`);
  const seedVideos = await fetchVideos(seedVideoIds, apiKey);

  // Extract unique channel IDs
  const channelIdSet = new Set();
  seedVideos.forEach(v => {
    if (v.snippet && v.snippet.channelId) {
      channelIdSet.add(v.snippet.channelId);
    }
  });

  const channelIds = Array.from(channelIdSet);
  console.log(`📡 Tìm thấy ${channelIds.length} kênh đối thủ riêng biệt. Đang thu thập thông tin kênh...`);
  const rawChannels = await fetchChannels(channelIds, apiKey);

  // Build map of channelId -> subCount
  const channelSubMap = new Map();
  rawChannels.forEach(c => {
    const sub = parseInt(c.statistics?.subscriberCount || '0', 10);
    channelSubMap.set(c.id, sub);
  });

  // For each channel, fetch ALL videos from uploads playlist
  console.log(`🚀 Bước 2: Quét TOÀN BỘ video của ${rawChannels.length} kênh từ uploads playlist...`);
  const channelVideosMap = new Map();
  let totalAllVideoIds = [];

  for (const c of rawChannels) {
    const uploadsId = c.contentDetails?.relatedPlaylists?.uploads;
    if (uploadsId) {
      process.stdout.write(`   ↳ Đang quét kênh "${c.snippet.title}"... `);
      const vids = await fetchAllVideoIdsFromUploads(uploadsId, apiKey, maxVideosPerChannel);
      channelVideosMap.set(c.id, vids);
      totalAllVideoIds.push(...vids);
      console.log(`xong (${vids.length} videos)`);
    } else {
      channelVideosMap.set(c.id, []);
    }
  }

  // Deduplicate video IDs
  totalAllVideoIds = Array.from(new Set(totalAllVideoIds));
  console.log(`📊 Tổng cộng tìm thấy ${totalAllVideoIds.length} video trên tất cả các kênh.`);
  console.log(`⏳ Đang tải chi tiết và chỉ số thống kê (Views, Comments, Likes, Descriptions, Tags)...`);

  const allRawVideos = await fetchVideos(totalAllVideoIds, apiKey);
  console.log(`✅ Đã tải thành công ${allRawVideos.length} video.`);

  const now = Date.now();

  // Process Table 2: Videos Details
  const videoData = allRawVideos.map(v => {
    const pubDate = new Date(v.snippet.publishedAt);
    const ageDays = Math.max(0, Math.floor((now - pubDate.getTime()) / (1000 * 60 * 60 * 24)));
    const views = parseInt(v.statistics?.viewCount || '0', 10);
    const comments = parseInt(v.statistics?.commentCount || '0', 10);
    const viewsPerDay = Math.round(views / Math.max(1, ageDays));
    const hashtags = extractHashtags(v.snippet.title, v.snippet.description, v.snippet.tags);
    const chanSub = channelSubMap.get(v.snippet.channelId) || 0;
    // Outlier: views >= 2 * subscribers
    const isOutlier = chanSub > 0 && views >= (2 * chanSub);

    return {
      id: v.id,
      title: v.snippet.title,
      videoUrl: `https://www.youtube.com/watch?v=${v.id}`,
      channelTitle: v.snippet.channelTitle,
      channelId: v.snippet.channelId,
      thumbnail: v.snippet.thumbnails?.medium?.url || v.snippet.thumbnails?.default?.url || '',
      views,
      comments,
      viewsPerDay,
      date: v.snippet.publishedAt.slice(0, 10),
      day: ageDays,
      isOutlier,
      hashtags,
      description: v.snippet.description || ''
    };
  });

  // Group videos by channel to calculate aggregate metrics
  const videosByChannel = new Map();
  videoData.forEach(v => {
    if (!videosByChannel.has(v.channelId)) {
      videosByChannel.set(v.channelId, []);
    }
    videosByChannel.get(v.channelId).push(v);
  });

  let totalOutliersAcrossChannels = 0;

  // Process Table 1: Channels Overview
  const channelData = rawChannels.map(c => {
    const subCount = parseInt(c.statistics?.subscriberCount || '0', 10);
    const viewCount = parseInt(c.statistics?.viewCount || '0', 10);
    
    // Sum video comments and calculate Outliers
    const chanVideos = videosByChannel.get(c.id) || [];
    const sumAllVideoComments = chanVideos.reduce((acc, v) => acc + v.comments, 0);
    const channelApiComments = parseInt(c.statistics?.commentCount || '0', 10);
    const totalComments = channelApiComments > 0 ? channelApiComments : sumAllVideoComments;

    // Outlier: videos with views >= 2 * subscriberCount
    const outlierVideos = chanVideos.filter(v => v.isOutlier);
    const outlierCount = outlierVideos.length;
    totalOutliersAcrossChannels += outlierCount;

    const publishedAt = new Date(c.snippet.publishedAt).getTime();
    const ageDays = Math.max(1, Math.floor((now - publishedAt) / (1000 * 60 * 60 * 24)));
    const viewsPerDay = Math.round(viewCount / ageDays);
    const commentViewRatio = viewCount > 0 ? ((totalComments / viewCount) * 100).toFixed(4) : '0';

    return {
      id: c.id,
      name: c.snippet.title,
      handle: c.snippet.customUrl || '',
      channelUrl: c.snippet.customUrl ? `https://www.youtube.com/${c.snippet.customUrl}` : `https://www.youtube.com/channel/${c.id}`,
      subscribers: subCount,
      views: viewCount,
      comments: totalComments,
      viewsPerDay,
      commentViewRatio,
      outlierCount,
      avatar: c.snippet.thumbnails?.default?.url || '',
      scannedVideoCount: chanVideos.length
    };
  });

  channelData.sort((a, b) => b.subscribers - a.subscribers);

  // Top metric highlights
  const topSubChannel = [...channelData].sort((a, b) => b.subscribers - a.subscribers)[0] || { name: 'N/A', subscribers: 0 };
  const topGrowthChannel = [...channelData].sort((a, b) => b.viewsPerDay - a.viewsPerDay)[0] || { name: 'N/A', viewsPerDay: 0 };
  const topVpdVideo = [...videoData].sort((a, b) => b.viewsPerDay - a.viewsPerDay)[0] || { title: 'N/A', viewsPerDay: 0 };

  const meta = {
    generatedAt: new Date().toLocaleString('vi-VN'),
    totalChannels: channelData.length,
    totalVideos: videoData.length,
    totalOutliers: totalOutliersAcrossChannels,
    topSubChannel,
    topGrowthChannel,
    topVpdVideo
  };

  console.log('🎨 Bước 3: Đang kết xuất Dashboard HTML trực quan...');
  const html = generateHtmlDashboard(channelData, videoData, meta);

  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  fs.writeFileSync(outputFile, html, 'utf8');

  console.log(`\n🎉 Hoàn thành! File Dashboard đã được xuất ra tại:`);
  console.log(`👉 ${outputFile}\n`);
}

main().catch(err => {
  console.error('❌ Lỗi xử lý:', err);
  process.exit(1);
});
