#!/usr/bin/env node
/**
 * score.mjs — chấm điểm SEO / AEO / GEO cho một bài viết markdown.
 *
 * Bản Node của `scripts/score.py`; hai script phải cho KẾT QUẢ GIỐNG HỆT NHAU.
 * Cài đặt trung thành `references/checklist.md` (bảng tiêu chí + trọng số + ngưỡng).
 *
 *   điểm = tổng(trọng số × hệ số) / tổng(trọng số) × 100
 *   hệ số: pass = 1, warn = 0.5, fail = 0
 *   tổng trọng số: SEO 96, AEO 100, GEO 90 (102 nếu có nhóm bản dịch)
 * Ngưỡng publish: SEO >= 75 VÀ AEO >= 70 VÀ GEO >= 70.
 *
 * Dùng: node score.mjs bai.md [--keyword "…"] [--locale vi] [--json] [--translation-group vi,en]
 * Exit code: 0 = đạt cả ba ngưỡng, 2 = chưa đạt, 1 = lỗi đọc file.
 */

import { readFileSync } from "node:fs";

const MARK = /[\u0300-\u036f]/g;

const fold = (s) => s.normalize("NFD").replace(MARK, "").replace(/đ/g, "d").replace(/Đ/g, "d").toLowerCase();

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function kwPattern(keyword) {
  // Python re.escape() escape cả dấu cách -> khoảng trắng thành bộ phân cách linh hoạt
  // (khớp được cả khi keyword bị ngắt dòng). Node phải làm y hệt.
  const body = escapeRe(fold(keyword)).replace(/\s+/g, "[\\s\\-_]+");
  return new RegExp("(?<![0-9a-z])" + body + "(?![0-9a-z])", "g");
}

const countKw = (text, keyword) => (keyword ? (fold(text).match(kwPattern(keyword)) || []).length : 0);
const hasKw = (text, keyword) => countKw(text, keyword) > 0;

function stripGuard(text) {
  let m = text.match(/^===+\s*BAT DAU NOI DUNG.*?===+\s*$/m);
  if (m) text = text.slice(m.index + m[0].length);
  m = text.match(/^===+\s*HET NOI DUNG.*?===+\s*$/m);
  if (m) text = text.slice(0, m.index);
  return text;
}

function parseFrontmatter(raw) {
  const meta = {};
  let body = raw;
  const m = raw.match(/^\s*---\s*\n([\s\S]*?)\n---\s*\n?/);
  if (m) {
    body = raw.slice(m[0].length);
    for (const line of m[1].split("\n")) {
      const mm = line.match(/^([A-Za-z_]+)\s*:\s*"?(.*?)"?\s*$/);
      if (mm) meta[mm[1].toLowerCase()] = mm[2].trim();
    }
  }
  return [meta, body];
}

// ---------------------------------------------- marker theo ngôn ngữ (10 locale)
const MARKERS = {
  vi: {
    quickAnswer: "trả lời nhanh|tóm tắt|tóm lại|tl;dr|nói ngắn gọn",
    entity: "là gì|là một|là những|được hiểu là|được định nghĩa|nghĩa là|định nghĩa",
    update: "cập nhật|mới nhất",
    question: "tại sao|làm sao|làm thế nào|khi nào|có nên|là gì|cách|bao nhiêu",
  },
  en: {
    quickAnswer: "in short|quick answer|tl;dr|in summary|key takeaway|bottom line",
    entity: "is an?\\b|are an?\\b|refers to|is defined as|stands for|means",
    update: "updated|last updated",
    question: "how|what|why|when|which|who|where|should",
  },
  zh: { quickAnswer: "简而言之|总结|要点|快速回答|概括", entity: "是什么|是一种|是指|指的是|定义为|定义", update: "更新|最新", question: "为什么|如何|怎么|什么|何时|是否" },
  ja: { quickAnswer: "要するに|要約|結論から|まとめ|一言で", entity: "とは|である|を指す|の定義|意味します", update: "更新|アップデート|最終更新", question: "なぜ|どうやって|どのように|いつ|何|べき" },
  ko: { quickAnswer: "요약|결론부터|한마디로|핵심", entity: "란|이란|를 의미|을 의미|정의|이다", update: "업데이트|갱신|최신", question: "왜|어떻게|무엇|언제|어디|해야" },
  fr: { quickAnswer: "en bref|en résumé|réponse rapide|pour résumer|en somme", entity: "qu'est-ce que|est une|sont des|se réfère|désigne|signifie|défini comme", update: "mis à jour|mise à jour|dernière mise à jour", question: "pourquoi|comment|quand|quel|quelle|combien|devrait" },
  de: { quickAnswer: "kurz gesagt|zusammenfassung|schnelle antwort|auf den punkt", entity: "ist eine|sind|bezeichnet|bedeutet|definiert als|versteht man", update: "aktualisiert|aktualisierung|zuletzt aktualisiert", question: "warum|wie|wann|welche|welcher|wie viele|sollte" },
  id: { quickAnswer: "singkatnya|ringkasnya|jawaban singkat|kesimpulan", entity: "adalah|merupakan|didefinisikan|berarti|mengacu pada", update: "diperbarui|pembaruan|terbaru", question: "mengapa|bagaimana|kapan|apa|berapa|haruskah" },
  hi: { quickAnswer: "संक्षेप में|सारांश|त्वरित उत्तर|मुख्य बात", entity: "क्या है|एक है|को संदर्भित|का अर्थ|परिभाषित", update: "अपडेट|अद्यतन|नवीनतम", question: "क्यों|कैसे|कब|क्या|कितना|चाहिए" },
  th: { quickAnswer: "สรุป|กล่าวโดยย่อ|คำตอบสั้น|ใจความสำคัญ", entity: "คืออะไร|คือ|หมายถึง|นิยาม|อ้างถึง", update: "อัปเดต|ปรับปรุง|ล่าสุด", question: "ทำไม|อย่างไร|เมื่อไร|อะไร|เท่าไร|ควร" },
};

function markersFor(locale) {
  const loc = fold((locale || "vi").split("-")[0].split("_")[0]);
  const base = MARKERS[loc] || MARKERS.en;
  const out = {};
  for (const key of ["quickAnswer", "entity", "update", "question"]) {
    const parts = [base[key]];
    if (loc !== "en") parts.push(MARKERS.en[key]);
    out[key] = new RegExp(parts.map(fold).join("|"), "i");
  }
  return out;
}

// --------------------------------------------------------- phép đo văn bản
const blocksOf = (body) => body.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);

function isParagraph(block) {
  const first = block.replace(/^\s+/, "").split("\n")[0].replace(/^\s+/, "");
  if (!first) return false;
  if ("#>|".includes(first[0])) return false;
  if (/^[-*+]\s/.test(first)) return false;
  if (/^-{3,}\s*$/.test(first)) return false;
  if (/^\d+[.)]\s/.test(first)) return false;
  if (first.startsWith("```")) return false;
  if (/^===+/.test(first)) return false;
  return true;
}

const paragraphsOf = (body) => blocksOf(body).filter(isParagraph);

function wordsOf(text) {
  const clean = text.replace(/```[\s\S]*?```/g, " ");
  return (clean.match(/[\p{L}\p{N}_'’-]+/gu) || []).length;
}

const headingsOf = (body) => [...body.matchAll(/^(#{2,3})\s+(.*)$/gm)].map((m) => m[2].trim());

const countInternalLinks = (b) => (b.match(/(?<!!)\[[^\]]*\]\(\s*(?:\/[^)\s]*|#[^)\s]*)\s*\)/g) || []).length;
const countExternalLinks = (b) => (b.match(/(?<!!)\[[^\]]*\]\(\s*https?:\/\/[^)\s]*\s*\)/g) || []).length;
const countImagesWithAlt = (b) => (b.match(/!\[[^\]]*[^\s\]][^\]]*\]\([^)\s]+\)/g) || []).length;

const hasListOrTable = (b) => /^\s*(?:[-*+]\s+|\d+[.)]\s+)/m.test(b) || /^\s*\|.*\|\s*$/m.test(b);

function maxNumberedRun(body) {
  let best = 0, run = 0;
  for (const line of body.split("\n")) {
    const s = line.trim();
    if (/^\d+[.)]\s+\S/.test(s)) { run += 1; best = Math.max(best, run); }
    else if (s === "") continue;
    else run = 0;
  }
  return best;
}

function countStats(body) {
  let hits = 0;
  hits += (body.match(/\d+(?:[.,]\d+)?\s*%/g) || []).length;
  hits += (body.match(/\d{1,3}(?:[.,]\d{3})+/g) || []).length;
  hits += (body.match(/\d+(?:[.,]\d+)?\s*(?:triệu|nghìn|tỷ|tỉ|billion|million|thousand|usd|vnd|đồng|đ(?![\p{L}]))/giu) || []).length;
  const re = /(?<![\d.,])(\d{4,})(?![\d.,%])/g;
  let m;
  while ((m = re.exec(body)) !== null) {
    const before = body.slice(Math.max(0, m.index - 12), m.index);
    const after = body.slice(m.index + m[0].length, m.index + m[0].length + 12);
    if (/\d[.,]$/.test(before) || /^[.,]\d/.test(after)) continue;
    if (/^\s*(?:triệu|nghìn|tỷ|tỉ|usd|vnd|đồng|đ\b|%)/i.test(after)) continue;
    const n = parseInt(m[1], 10);
    if (n >= 1900 && n <= 2099) continue; // năm đứng một mình
    hits += 1;
  }
  return hits;
}

function hreflangOk(body, group) {
  if (!group) return "pass";
  const tags = body.match(/<link[^>]+rel=["']alternate["'][^>]*>/gi) || [];
  const langs = tags.map((t) => (t.match(/hreflang=["']([^"']+)/i) || [])[1]).filter(Boolean).map((x) => x.toLowerCase());
  if (!langs.length || !langs.includes("x-default")) return "warn";
  return "pass";
}

export function run(path, keyword, locale, translationGroup) {
  // Python đọc text-mode tự chuẩn hoá CRLF -> Node phải làm tương tự để kết quả khớp
  const raw = stripGuard(readFileSync(path, "utf8").replace(/\r\n?/g, "\n"));
  const [meta, body] = parseFrontmatter(raw);
  keyword = keyword || meta.keyword || "";
  locale = locale || meta.locale || "vi";
  const mk = markersFor(locale);
  let title = meta.title || "";
  if (!title) {
    const h1 = body.match(/^#\s+(.*)$/m);
    title = h1 ? h1[1].trim() : "";
  }
  const desc = meta.description || "";
  const slug = meta.slug || "";
  const heads = headingsOf(body);
  const paras = paragraphsOf(body);
  const first = paras.length ? paras[0] : "";
  const plain = body.replace(/[*_`\[\]]/g, "");
  const foldedAll = fold(body);
  const wc = wordsOf(body);
  const kwWords = keyword ? Math.max(1, keyword.split(/\s+/).length) : 1;
  const density = wc ? (countKw(body, keyword) * kwWords / wc) * 100 : 0;
  const avgParaWords = paras.length ? paras.reduce((a, p) => a + wordsOf(p), 0) / paras.length : 0;
  const shortParas = paras.filter((p) => p.length <= 600).length;
  const conciseRatio = paras.length ? shortParas / paras.length : 0;
  const snippet = paras.some((p) => wordsOf(p) >= 35 && wordsOf(p) <= 65);
  const qHead = heads.filter((h) => h.trimEnd().endsWith("?") || mk.question.test(fold(h))).length;
  const first100 = (body.replace(/[#*_`\[\]|>]/g, " ").match(/[\p{L}\p{N}_'’-]+/gu) || []).slice(0, 100).join(" ");

  const m = {
    title, desc, slug, heads, paras, first, plain, wc, density,
    avgParaWords, conciseRatio, snippet, qHead, first100, mk, keyword,
    kw_in_title: hasKw(title, keyword), kw_in_desc: hasKw(desc, keyword),
    kw_in_slug: hasKw(fold(slug).replace(/-/g, " "), keyword.replace(/-/g, " ")),
    kw_in_head: heads.some((h) => hasKw(h, keyword)), kw_first100: hasKw(first100, keyword),
    kw_first_para: hasKw(first, keyword),
    internal: countInternalLinks(body), external: countExternalLinks(body),
    images: countImagesWithAlt(body), stats: countStats(body),
    howto_run: maxNumberedRun(body),
    has_faq_heading: /^#{2,3}\s*FAQ\b/im.test(body),
    has_question_mark: body.includes("?") || foldedAll.includes("faq"),
    has_list_table: hasListOrTable(body),
    entity: mk.entity.test(foldedAll),
    quick_anywhere: mk.quickAnswer.test(foldedAll),
    fresh: mk.update.test(foldedAll) || /©\s*20\d\d/.test(body),
    translation_group: translationGroup, _body: body,
  };
  m.hreflang_ok = hreflangOk(body, translationGroup);

  const seo = [];
  const L = m.title.length;
  seo.push(["title", 12, L && L <= 60 && m.kw_in_title ? "pass" : L <= 70 ? "warn" : "fail", `${L} ký tự${m.kw_in_title ? "" : ", thiếu keyword"}`]);
  const dl = m.desc.length;
  seo.push(["meta", 8, dl >= 120 && dl <= 155 ? "pass" : dl >= 1 && dl <= 170 ? "warn" : "fail", `${dl} ký tự`]);
  seo.push(["kwInMeta", 5, m.kw_in_desc ? "pass" : "fail", m.kw_in_desc ? "có keyword" : "không có keyword"]);
  const sl = m.slug.length;
  seo.push(["slug", 6, sl && sl <= 60 && m.kw_in_slug ? "pass" : sl <= 60 ? "warn" : "fail", `${sl} ký tự${m.kw_in_slug ? "" : ", thiếu keyword"}`]);
  const h = m.heads.length;
  seo.push(["headings", 8, h >= 3 ? "pass" : h >= 1 ? "warn" : "fail", `${h} heading H2/H3`]);
  seo.push(["kwInHeading", 7, m.kw_in_head ? "pass" : "fail", m.kw_in_head ? "có" : "không"]);
  seo.push(["kwFirst100", 8, m.kw_first100 ? "pass" : "fail", m.kw_first100 ? "có" : "không"]);
  seo.push(["coverage", 12, m.wc >= 800 ? "pass" : m.wc >= 400 ? "warn" : "fail", `${m.wc} từ`]);
  seo.push(["internalLinks", 8, m.internal >= 2 ? "pass" : m.internal === 1 ? "warn" : "fail", `${m.internal} link nội bộ`]);
  seo.push(["outbound", 6, m.external ? "pass" : "fail", `${m.external} link ngoài`]);
  seo.push(["images", 7, m.images ? "pass" : "fail", `${m.images} ảnh có alt`]);
  seo.push(["readability", 5, m.avgParaWords <= 80 ? "pass" : "warn", `TB ${Math.round(m.avgParaWords)} từ/đoạn`]);
  seo.push(["density", 4, m.density <= 3.5 ? "pass" : "warn", `${m.density.toFixed(2)}%`]);

  const fp = m.first;
  const aeo = [];
  const up = m.mk.quickAnswer.test(fold(fp)) || (fp.length >= 40 && fp.length <= 360 && m.kw_first_para);
  aeo.push(["answerUpfront", 16, up ? "pass" : "fail", `${fp.length} ký tự đoạn đầu`]);
  aeo.push(["snippetLength", 10, m.snippet ? "pass" : "warn", m.snippet ? "có" : "không có đoạn 35-65 từ"]);
  aeo.push(["questionHeadings", 12, m.qHead >= 2 ? "pass" : m.qHead === 1 ? "warn" : "fail", `${m.qHead} heading câu hỏi`]);
  aeo.push(["faq", 12, m.has_faq_heading ? "pass" : m.has_question_mark ? "warn" : "fail", m.has_faq_heading ? "có ## FAQ" : "không có khối FAQ"]);
  aeo.push(["definition", 9, m.entity ? "pass" : "warn", m.entity ? "khớp marker" : "không khớp marker"]);
  aeo.push(["listOrTable", 9, m.has_list_table ? "pass" : "fail", m.has_list_table ? "có" : "không"]);
  aeo.push(["howto", 8, m.howto_run >= 3 ? "pass" : "warn", `chuỗi ${m.howto_run} bước`]);
  const qm = m.kw_in_head || m.kw_first_para ? "pass" : hasKw(m.plain, m.keyword) ? "warn" : "fail";
  aeo.push(["queryMatch", 9, qm, qm === "pass" ? "keyword ở heading/đoạn đầu" : qm === "warn" ? "keyword chỉ ở thân bài" : "không có keyword"]);
  aeo.push(["summary", 7, m.quick_anywhere ? "pass" : "warn", m.quick_anywhere ? "có" : "không"]);
  aeo.push(["concise", 8, m.conciseRatio >= 0.6 ? "pass" : "warn", `${Math.round(m.conciseRatio * 100)}% đoạn ngắn`]);

  const geo = [];
  const q = m.mk.quickAnswer.test(fold(fp)) || (fp.length >= 41 && fp.length <= 319 && m.kw_first_para);
  geo.push(["quotable", 14, q ? "pass" : "fail", `${fp.length} ký tự đoạn đầu`]);
  geo.push(["qa", 10, m.has_question_mark ? "pass" : "warn", m.has_question_mark ? "có" : "không"]);
  geo.push(["entity", 8, m.entity ? "pass" : "warn", m.entity ? "khớp marker" : "không khớp"]);
  geo.push(["sources", 12, m.external ? "pass" : "fail", `${m.external} nguồn ngoài`]);
  geo.push(["format", 9, m.has_list_table ? "pass" : "fail", m.has_list_table ? "có" : "không"]);
  geo.push(["schema", 9, m.has_faq_heading ? "pass" : "fail", m.has_faq_heading ? "có ## FAQ" : "không"]);
  geo.push(["stats", 7, m.stats >= 2 ? "pass" : "warn", `${m.stats} điểm dữ liệu`]);
  geo.push(["questionHeading", 6, m.qHead >= 1 ? "pass" : "warn", `${m.qHead} heading câu hỏi`]);
  geo.push(["freshness", 7, m.fresh ? "pass" : "warn", m.fresh ? "có" : "không"]);
  const c = m.heads.length;
  geo.push(["completeness", 8, c >= 4 ? "pass" : "warn", `${c} heading H2/H3`]);
  if (translationGroup) {
    const ok = hreflangOk(body, translationGroup);
    geo.push(["hreflang", 12, ok, ok === "pass" ? "có x-default" : "thiếu/lệch hreflang"]);
  }

  const FACTOR = { pass: 1, warn: 0.5, fail: 0 };
  const sg = (items) => {
    const total = items.reduce((a, i) => a + i[1], 0);
    const got = items.reduce((a, i) => a + i[1] * FACTOR[i[2]], 0);
    return [total ? Math.round(got / total * 100) : 0, total];
  };
  const [sSeo, tSeo] = sg(seo), [sAeo, tAeo] = sg(aeo), [sGeo, tGeo] = sg(geo);
  const publish = sSeo >= 75 && sAeo >= 70 && sGeo >= 70;
  const pack = (items) => items.map(([id, weight, status, detail]) => ({ id, weight, status, detail }));
  return {
    file: path, keyword, locale,
    scores: { seo: sSeo, aeo: sAeo, geo: sGeo },
    thresholds: { seo: 75, aeo: 70, geo: 70 },
    publish, words: m.wc,
    groups: { SEO: pack(seo), AEO: pack(aeo), GEO: pack(geo) },
    weights: { SEO: tSeo, AEO: tAeo, GEO: tGeo },
  };
}

const ROI_ORDER = ["answerUpfront", "quotable", "sources", "faq", "schema", "questionHeadings",
  "coverage", "title", "meta", "slug", "internalLinks", "images", "stats", "freshness"];

const ICON = { pass: "✓", warn: "!", fail: "✗" };

function renderHuman(r) {
  const out = ["=== CHẤM ĐIỂM SEO + AEO + GEO ===", `File: ${r.file}`,
    `Keyword: ${r.keyword || "(không có)"} | Locale: ${r.locale} | ${r.words} từ`, ""];
  for (const g of ["SEO", "AEO", "GEO"]) {
    out.push(`[${g}] ${r.scores[g.toLowerCase()]}/100  (tổng trọng số ${r.weights[g]})`);
    for (const it of r.groups[g]) {
      out.push(`   ${ICON[it.status]} ${it.id.padEnd(20)} ${(it.weight * { pass: 1, warn: 0.5, fail: 0 }[it.status]).toFixed(1).padStart(5)}/${String(it.weight).padEnd(3)} ${it.detail}`);
    }
    out.push("");
  }
  out.push(`KẾT LUẬN: ${r.publish ? "ĐẠT — có thể publish" : "CHƯA ĐẠT"} (ngưỡng: SEO ≥ 75, AEO ≥ 70, GEO ≥ 70)`);
  const todo = ["AEO", "GEO", "SEO"].flatMap((g) => r.groups[g].filter((it) => it.status !== "pass"));
  if (todo.length) {
    todo.sort((a, b) => (ROI_ORDER.indexOf(a.id) + 99) % 999 - (ROI_ORDER.indexOf(b.id) + 99) % 999);
    out.push("Vá theo ROI cao → thấp: " + todo.map((it) => `${it.id} (${it.weight}đ)`).join(", "));
  }
  return out.join("\n");
}

function main(argv) {
  const files = [];
  const flags = new Set();
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      if (["keyword", "locale", "translation-group"].includes(key)) { opts[key] = argv[++i] ?? ""; continue; }
      flags.add(key);
    } else files.push(a);
  }
  if (!files.length) {
    console.error("Dùng: node score.mjs bai.md [--keyword \"...\"] [--locale vi] [--json] [--translation-group vi,en]");
    return 1;
  }
  let r;
  try {
    r = run(files[0], opts.keyword, opts.locale, opts["translation-group"]);
  } catch (e) {
    console.error(`LỖI ĐỌC FILE: ${e.message}`);
    return 1;
  }
  console.log(flags.has("json") ? JSON.stringify(r, null, 2) : renderHuman(r));
  return r.publish ? 0 : 2;
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("score.mjs")) {
  process.exit(main(process.argv.slice(2)));
}
