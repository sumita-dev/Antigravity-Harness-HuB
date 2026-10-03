#!/usr/bin/env python3
"""score.py — chấm điểm SEO / AEO / GEO cho một bài viết markdown.

Đây là bản cài đặt trung thành của `references/checklist.md` của skill
`viet-content-seo-geo-v5` (bảng tiêu chí + trọng số + ngưỡng pass/warn/fail).
Không thêm tiêu chí ngoài checklist.

Công thức (theo checklist mục F):
    điểm = tổng(trọng số × hệ số) / tổng(trọng số) × 100
    hệ số: pass = 1, warn = 0.5, fail = 0
    tổng trọng số: SEO 96, AEO 100, GEO 90 (102 nếu có nhóm bản dịch)
Ngưỡng publish: SEO >= 75 VÀ AEO >= 70 VÀ GEO >= 70.

Dùng:
    python score.py bai.md [--keyword "từ khóa"] [--locale vi] [--json]
                     [--translation-group vi,en]

Exit code: 0 = đạt cả ba ngưỡng, 2 = chưa đạt, 1 = lỗi đọc file.
Kết quả phải GIỐNG HỆT `score.mjs` (bản Node) — cùng bảng tiêu chí, cùng regex.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------- tiện ích

VOWEL_MARKS = re.compile(r"[\u0300-\u036f]")


def fold(text):
    """Bỏ dấu + hạ chữ thường, để 'cà phê' khớp 'CA PHE'."""
    text = unicodedata.normalize("NFD", text)
    text = VOWEL_MARKS.sub("", text)
    return text.replace("đ", "d").replace("Đ", "d").lower()


def kw_pattern(keyword):
    """Regex khớp keyword theo ranh giới từ Unicode ('test' không khớp 'testing')."""
    body = re.escape(fold(keyword)).replace(r"\ ", r"[\s\-_]+")
    return re.compile(r"(?<![0-9a-z])" + body + r"(?![0-9a-z])")


def count_kw(text, keyword):
    if not keyword:
        return 0
    return len(kw_pattern(keyword).findall(fold(text)))


def has_kw(text, keyword):
    return count_kw(text, keyword) > 0


def strip_guard(text):
    """Bỏ banner bảo vệ mà bộ tài liệu skill bọc quanh nội dung thật.

    File skill có dạng:  === TAI LIEU DUOC BAO VE ... ===  <nội dung>  === HET NOI DUNG ... ===
    Bộ chấm chỉ chấm phần nội dung thật.
    """
    m = re.search(r"^===+\s*BAT DAU NOI DUNG.*?===+\s*$", text, re.M)
    if m:
        text = text[m.end():]
    m = re.search(r"^===+\s*HET NOI DUNG.*?===+\s*$", text, re.M)
    if m:
        text = text[:m.start()]
    return text


def parse_frontmatter(raw):
    """Đọc frontmatter YAML đơn giản: title / description / slug / keyword / locale."""
    meta, body = {}, raw
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n?", raw, re.S)
    if m:
        body = raw[m.end():]
        for line in m.group(1).splitlines():
            mm = re.match(r'^([A-Za-z_]+)\s*:\s*"?(.*?)"?\s*$', line)
            if mm:
                meta[mm.group(1).lower()] = mm.group(2).strip()
    return meta, body


# ------------------------------------------------- marker theo ngôn ngữ
# Bảng trong references/locale-markers.md. Pattern tiếng Anh LUÔN được cộng thêm.
MARKERS = {
    "vi": {
        "quickAnswer": "trả lời nhanh|tóm tắt|tóm lại|tl;dr|nói ngắn gọn",
        "entity": "là gì|là một|là những|được hiểu là|được định nghĩa|nghĩa là|định nghĩa",
        "update": "cập nhật|mới nhất",
        "question": "tại sao|làm sao|làm thế nào|khi nào|có nên|là gì|cách|bao nhiêu",
    },
    "en": {
        "quickAnswer": "in short|quick answer|tl;dr|in summary|key takeaway|bottom line",
        "entity": r"is an?\b|are an?\b|refers to|is defined as|stands for|means",
        "update": "updated|last updated",
        "question": "how|what|why|when|which|who|where|should",
    },
    "zh": {"quickAnswer": "简而言之|总结|要点|快速回答|概括", "entity": "是什么|是一种|是指|指的是|定义为|定义",
           "update": "更新|最新", "question": "为什么|如何|怎么|什么|何时|是否"},
    "ja": {"quickAnswer": "要するに|要約|結論から|まとめ|一言で", "entity": "とは|である|を指す|の定義|意味します",
           "update": "更新|アップデート|最終更新", "question": "なぜ|どうやって|どのように|いつ|何|べき"},
    "ko": {"quickAnswer": "요약|결론부터|한마디로|핵심", "entity": "란|이란|를 의미|을 의미|정의|이다",
           "update": "업데이트|갱신|최신", "question": "왜|어떻게|무엇|언제|어디|해야"},
    "fr": {"quickAnswer": "en bref|en résumé|réponse rapide|pour résumer|en somme",
           "entity": r"qu'est-ce que|est une|sont des|se réfère|désigne|signifie|défini comme",
           "update": "mis à jour|mise à jour|dernière mise à jour",
           "question": "pourquoi|comment|quand|quel|quelle|combien|devrait"},
    "de": {"quickAnswer": "kurz gesagt|zusammenfassung|schnelle antwort|auf den punkt",
           "entity": r"ist eine|sind|bezeichnet|bedeutet|definiert als|versteht man",
           "update": "aktualisiert|aktualisierung|zuletzt aktualisiert",
           "question": "warum|wie|wann|welche|welcher|wie viele|sollte"},
    "id": {"quickAnswer": "singkatnya|ringkasnya|jawaban singkat|kesimpulan",
           "entity": "adalah|merupakan|didefinisikan|berarti|mengacu pada",
           "update": "diperbarui|pembaruan|terbaru",
           "question": "mengapa|bagaimana|kapan|apa|berapa|haruskah"},
    "hi": {"quickAnswer": "संक्षेप में|सारांश|त्वरित उत्तर|मुख्य बात",
           "entity": r"क्या है|एक है|को संदर्भित|का अर्थ|परिभाषित",
           "update": "अपडेट|अद्यतन|नवीनतम", "question": "क्यों|कैसे|कब|क्या|कितना|चाहिए"},
    "th": {"quickAnswer": "สรุป|กล่าวโดยย่อ|คำตอบสั้น|ใจความสำคัญ",
           "entity": r"คืออะไร|คือ|หมายถึง|นิยาม|อ้างถึง",
           "update": "อัปเดต|ปรับปรุง|ล่าสุด", "question": "ทำไม|อย่างไร|เมื่อไร|อะไร|เท่าไร|ควร"},
}


def markers_for(locale):
    """markersFor(): cắt vùng (en-US -> en), fallback 'en', luôn cộng thêm tiếng Anh."""
    loc = fold((locale or "vi").split("-")[0].split("_")[0])
    base = MARKERS.get(loc, MARKERS["en"])
    out = {}
    for key in ("quickAnswer", "entity", "update", "question"):
        parts = [base[key]]
        if loc != "en":
            parts.append(MARKERS["en"][key])
        out[key] = re.compile("|".join(fold(x) for x in parts), re.I)
    return out


# ------------------------------------------------------- các phép đo văn bản

def blocks_of(body):
    """Tách khối theo dòng trống."""
    return [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]


def is_paragraph(block):
    """Đoạn văn xuôi: loại khối bắt đầu bằng #, >, |, -, *, hoặc '1.'."""
    first = block.lstrip().splitlines()[0].lstrip()
    if not first:
        return False
    if first[0] in "#>|":
        return False
    if re.match(r"^[-*+]\s", first):      # bullet thật (không phải **bold**)
        return False
    if re.match(r"^-{3,}\s*$", first):    # đường kẻ ngang
        return False
    if re.match(r"^\d+[.)]\s", first):
        return False
    if first.startswith("```"):
        return False
    if re.match(r"^===+", first):
        return False
    return True


def paragraphs_of(body):
    return [b for b in blocks_of(body) if is_paragraph(b)]


def words_of(text):
    """Đếm từ trên toàn markdown (kể cả heading, alt ảnh, ô bảng)."""
    clean = re.sub(r"```.*?```", " ", text, flags=re.S)
    return len(re.findall(r"[\w'’-]+", clean, re.UNICODE))


def headings_of(body, levels=(2, 3)):
    pat = re.compile(r"^(#{2,3})\s+(.*)$", re.M)
    return [(m.group(2).strip()) for m in pat.finditer(body) if len(m.group(1)) in levels]


def count_internal_links(body):
    """[x](/path) hoặc [x](#anchor) — không tính ảnh."""
    pat = re.compile(r"(?<!!)\[[^\]]*\]\(\s*(?:/[^)\s]*|#[^)\s]*)\s*\)")
    return len(pat.findall(body))


def count_external_links(body):
    """[x](https://…) — không tính ảnh, không tính link nội bộ."""
    pat = re.compile(r"(?<!!)\[[^\]]*\]\(\s*https?://[^)\s]*\s*\)")
    return len(pat.findall(body))


def count_images_with_alt(body):
    return len(re.findall(r"!\[[^\]]*[^\s\]][^\]]*\]\([^)\s]+\)", body))


def has_list_or_table(body):
    if re.search(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", body):
        return True
    return bool(re.search(r"(?m)^\s*\|.*\|\s*$", body))


def max_numbered_run(body):
    """Chuỗi >= 3 dòng đánh số liên tiếp. Dòng trống không ngắt, văn xuôi thì ngắt."""
    best = run = 0
    for line in body.splitlines():
        s = line.strip()
        if re.match(r"^\d+[.)]\s+\S", s):
            run += 1
            best = max(best, run)
        elif s == "":
            continue
        else:
            run = 0
    return best


def count_stats(body):
    """Số điểm dữ liệu theo quy tắc statsCount (mục C của checklist)."""
    hits = 0
    for m in re.finditer(r"\d+(?:[.,]\d+)?\s*%", body):
        hits += 1
    for m in re.finditer(r"\d{1,3}(?:[.,]\d{3})+", body):
        hits += 1
    for m in re.finditer(
        r"\d+(?:[.,]\d+)?\s*(?:triệu|nghìn|tỷ|tỉ|billion|million|thousand|usd|vnd|đồng|đ\b)",
        body, re.I):
        hits += 1
    for m in re.finditer(r"(?<![\d.,])(\d{4,})(?![\d.,%])", body):
        # số nguyên >= 4 chữ số, nhưng loại năm đứng một mình (1900-2099)
        before = body[max(0, m.start() - 12):m.start()]
        after = body[m.end():m.end() + 12]
        if re.search(r"\d[.,]$", before) or re.match(r"^[.,]\d", after):
            continue
        if re.match(r"^\s*(?:triệu|nghìn|tỷ|tỉ|usd|vnd|đồng|đ\b|%)", after, re.I):
            continue
        year = 1900 <= int(m.group(1)) <= 2099
        if year:
            continue
        hits += 1
    return hits


# ------------------------------------------------------------ 13+11 tiêu chí

def evaluate(body, meta, keyword, locale, translation_group):
    mk = markers_for(locale or meta.get("locale") or "vi")
    title = meta.get("title") or ""
    if not title:
        h1 = re.search(r"(?m)^#\s+(.*)$", body)
        title = h1.group(1).strip() if h1 else ""
    desc = meta.get("description") or ""
    slug = meta.get("slug") or ""
    heads = headings_of(body)
    paras = paragraphs_of(body)
    first = paras[0] if paras else ""
    plain = re.sub(r"[*_`\[\]]", "", body)
    folded_all = fold(body)
    wc = words_of(body)
    kw_words = max(1, len(keyword.split())) if keyword else 1
    density = (count_kw(body, keyword) * kw_words / wc * 100) if wc else 0
    avg_para_words = (sum(words_of(p) for p in paras) / len(paras)) if paras else 0
    short_paras = [p for p in paras if len(p) <= 600]
    concise_ratio = (len(short_paras) / len(paras)) if paras else 0
    snippet = any(35 <= words_of(p) <= 65 for p in paras)
    q_head = [h for h in heads if h.rstrip().endswith("?") or mk["question"].search(fold(h))]
    first100 = " ".join(re.findall(r"[\w'’-]+", re.sub(r"[#*_`\[\]|>]", " ", body))[:100])
    return {
        "title": title, "desc": desc, "slug": slug, "heads": heads, "paras": paras,
        "first": first, "plain": plain, "wc": wc, "density": density,
        "avg_para_words": avg_para_words, "concise_ratio": concise_ratio,
        "snippet": snippet, "q_head": q_head, "first100": first100, "mk": mk,
        "kw_in_title": has_kw(title, keyword), "kw_in_desc": has_kw(desc, keyword),
        "kw_in_slug": has_kw(fold(slug).replace("-", " "), keyword.replace("-", " ")),
        "kw_in_head": any(has_kw(h, keyword) for h in heads),
        "kw_first100": has_kw(first100, keyword),
        "kw_first_para": has_kw(first, keyword),
        "internal": count_internal_links(body), "external": count_external_links(body),
        "images": count_images_with_alt(body), "stats": count_stats(body),
        "howto_run": max_numbered_run(body),
        "has_faq_heading": bool(re.search(r"(?m)^#{2,3}\s*FAQ\b", body, re.I)),
        "has_question_mark": ("?" in body) or ("faq" in folded_all),
        "has_list_table": has_list_or_table(body),
        "entity": bool(mk["entity"].search(folded_all)),
        "quick_anywhere": bool(mk["quickAnswer"].search(folded_all)),
        "fresh": bool(mk["update"].search(folded_all)) or bool(re.search(r"©\s*20\d\d", body)),
        "total_words": wc, "translation_group": translation_group,
        "hreflang_ok": _hreflang_ok(body, translation_group),
    }


def _hreflang_ok(body, group):
    """Chỉ tính khi có nhóm bản dịch: cần hreflang + x-default (đối xứng kiểm ở cấp site)."""
    if not group:
        return "pass"
    tags = re.findall(r'<link[^>]+rel=["\']alternate["\'][^>]*>', body, re.I)
    langs = [re.search(r'hreflang=["\']([^"\']+)', t, re.I) for t in tags]
    langs = [m.group(1).lower() for m in langs if m]
    if not langs or "x-default" not in langs:
        return "warn"
    return "pass"


def build_criteria(m):
    """Bảng tiêu chí + trọng số, đúng theo references/checklist.md."""
    kw = m["kwp"] if "kwp" in m else None  # không dùng, giữ chỗ để tránh lệch khoá
    seo = []
    L = len(m["title"])
    seo.append(("title", 12, "pass" if (L and L <= 60 and m["kw_in_title"]) else ("warn" if L <= 70 else "fail"),
                f"{L} ký tự" + ("" if m["kw_in_title"] else ", thiếu keyword")))
    dl = len(m["desc"])
    st = "pass" if 120 <= dl <= 155 else ("warn" if 1 <= dl <= 170 else "fail")
    seo.append(("meta", 8, st, f"{dl} ký tự"))
    seo.append(("kwInMeta", 5, "pass" if m["kw_in_desc"] else "fail", "có keyword" if m["kw_in_desc"] else "không có keyword"))
    sl = len(m["slug"])
    st = "pass" if (sl and sl <= 60 and m["kw_in_slug"]) else ("warn" if sl <= 60 else "fail")
    seo.append(("slug", 6, st, f"{sl} ký tự" + ("" if m["kw_in_slug"] else ", thiếu keyword")))
    h = len(m["heads"])
    seo.append(("headings", 8, "pass" if h >= 3 else ("warn" if h >= 1 else "fail"), f"{h} heading H2/H3"))
    seo.append(("kwInHeading", 7, "pass" if m["kw_in_head"] else "fail", "có" if m["kw_in_head"] else "không"))
    seo.append(("kwFirst100", 8, "pass" if m["kw_first100"] else "fail", "có" if m["kw_first100"] else "không"))
    wc = m["wc"]
    seo.append(("coverage", 12, "pass" if wc >= 800 else ("warn" if wc >= 400 else "fail"), f"{wc} từ"))
    il = m["internal"]
    seo.append(("internalLinks", 8, "pass" if il >= 2 else ("warn" if il == 1 else "fail"), f"{il} link nội bộ"))
    seo.append(("outbound", 6, "pass" if m["external"] else "fail", f"{m['external']} link ngoài"))
    seo.append(("images", 7, "pass" if m["images"] else "fail", f"{m['images']} ảnh có alt"))
    seo.append(("readability", 5, "pass" if m["avg_para_words"] <= 80 else "warn", f"TB {m['avg_para_words']:.0f} từ/đoạn"))
    seo.append(("density", 4, "pass" if m["density"] <= 3.5 else "warn", f"{m['density']:.2f}%"))

    fp = m["first"]
    aeo = []
    up = bool(m["mk"]["quickAnswer"].search(fold(fp))) or (40 <= len(fp) <= 360 and m["kw_first_para"])
    aeo.append(("answerUpfront", 16, "pass" if up else "fail", f"{len(fp)} ký tự đoạn đầu"))
    aeo.append(("snippetLength", 10, "pass" if m["snippet"] else "warn", "có" if m["snippet"] else "không có đoạn 35-65 từ"))
    qn = len(m["q_head"])
    aeo.append(("questionHeadings", 12, "pass" if qn >= 2 else ("warn" if qn == 1 else "fail"), f"{qn} heading câu hỏi"))
    if m["has_faq_heading"]:
        faq = "pass"
    elif m["has_question_mark"]:
        faq = "warn"
    else:
        faq = "fail"
    aeo.append(("faq", 12, faq, "có ## FAQ" if m["has_faq_heading"] else "không có khối FAQ"))
    aeo.append(("definition", 9, "pass" if m["entity"] else "warn", "khớp marker" if m["entity"] else "không khớp marker"))
    aeo.append(("listOrTable", 9, "pass" if m["has_list_table"] else "fail", "có" if m["has_list_table"] else "không"))
    hr = m["howto_run"]
    aeo.append(("howto", 8, "pass" if hr >= 3 else "warn", f"chuỗi {hr} bước"))
    qm = "pass" if (m["kw_in_head"] or m["kw_first_para"]) else ("warn" if has_kw(m["plain"], m["keyword"]) else "fail")
    aeo.append(("queryMatch", 9, qm, "keyword ở heading/đoạn đầu" if qm == "pass" else "keyword chỉ ở thân bài" if qm == "warn" else "không có keyword"))
    aeo.append(("summary", 7, "pass" if m["quick_anywhere"] else "warn", "có" if m["quick_anywhere"] else "không"))
    aeo.append(("concise", 8, "pass" if m["concise_ratio"] >= 0.6 else "warn", f"{m['concise_ratio']*100:.0f}% đoạn ngắn"))

    geo = []
    q = bool(m["mk"]["quickAnswer"].search(fold(fp))) or (41 <= len(fp) <= 319 and m["kw_first_para"])
    geo.append(("quotable", 14, "pass" if q else "fail", f"{len(fp)} ký tự đoạn đầu"))
    geo.append(("qa", 10, "pass" if m["has_question_mark"] else "warn", "có" if m["has_question_mark"] else "không"))
    geo.append(("entity", 8, "pass" if m["entity"] else "warn", "khớp marker" if m["entity"] else "không khớp"))
    geo.append(("sources", 12, "pass" if m["external"] else "fail", f"{m['external']} nguồn ngoài"))
    geo.append(("format", 9, "pass" if m["has_list_table"] else "fail", "có" if m["has_list_table"] else "không"))
    geo.append(("schema", 9, "pass" if m["has_faq_heading"] else "fail", "có ## FAQ" if m["has_faq_heading"] else "không"))
    s = m["stats"]
    geo.append(("stats", 7, "pass" if s >= 2 else "warn", f"{s} điểm dữ liệu"))
    geo.append(("questionHeading", 6, "pass" if qn >= 1 else "warn", f"{qn} heading câu hỏi"))
    geo.append(("freshness", 7, "pass" if m["fresh"] else "warn", "có" if m["fresh"] else "không"))
    c = len(m["heads"])
    geo.append(("completeness", 8, "pass" if c >= 4 else "warn", f"{c} heading H2/H3"))
    if m["translation_group"]:
        ok = _hreflang_ok(m.get("_body", ""), m["translation_group"])
        geo.append(("hreflang", 12, ok, "có x-default" if ok == "pass" else "thiếu/lệch hreflang"))
    return seo, aeo, geo


FACTOR = {"pass": 1.0, "warn": 0.5, "fail": 0.0}


def score_group(items):
    total = sum(w for _, w, _, _ in items)
    got = sum(w * FACTOR[st] for _, w, st, _ in items)
    return (round(got / total * 100) if total else 0), total, got


def run(path, keyword=None, locale=None, translation_group=None):
    raw = strip_guard(Path(path).read_text(encoding="utf-8"))
    meta, body = parse_frontmatter(raw)
    keyword = keyword or meta.get("keyword") or ""
    locale = locale or meta.get("locale") or "vi"
    m = evaluate(body, meta, keyword, locale, translation_group)
    m["keyword"] = keyword
    m["_body"] = body
    seo, aeo, geo = build_criteria(m)
    s_seo, t_seo, g_seo = score_group(seo)
    s_aeo, t_aeo, g_aeo = score_group(aeo)
    s_geo, t_geo, g_geo = score_group(geo)
    ok = s_seo >= 75 and s_aeo >= 70 and s_geo >= 70
    return {
        "file": str(path), "keyword": keyword, "locale": locale,
        "scores": {"seo": s_seo, "aeo": s_aeo, "geo": s_geo},
        "thresholds": {"seo": 75, "aeo": 70, "geo": 70},
        "publish": ok,
        "words": m["wc"],
        "groups": {
            "SEO": [{"id": i, "weight": w, "status": st, "detail": d} for i, w, st, d in seo],
            "AEO": [{"id": i, "weight": w, "status": st, "detail": d} for i, w, st, d in aeo],
            "GEO": [{"id": i, "weight": w, "status": st, "detail": d} for i, w, st, d in geo],
        },
        "weights": {"SEO": t_seo, "AEO": t_aeo, "GEO": t_geo},
    }


ROI_ORDER = ["answerUpfront", "quotable", "sources", "faq", "schema",
             "questionHeadings", "coverage", "title", "meta", "slug",
             "internalLinks", "images", "stats", "freshness"]


def render_human(r):
    icon = {"pass": "✓", "warn": "!", "fail": "✗"}
    out = ["=== CHẤM ĐIỂM SEO + AEO + GEO ===",
           f"File: {r['file']}",
           f"Keyword: {r['keyword'] or '(không có)'} | Locale: {r['locale']} | {r['words']} từ", ""]
    for g in ("SEO", "AEO", "GEO"):
        out.append(f"[{g}] {r['scores'][g.lower()]}/100  (tổng trọng số {r['weights'][g]})")
        for it in r["groups"][g]:
            pts = it["weight"] * FACTOR[it["status"]]
            out.append(f"   {icon[it['status']]} {it['id']:<20} {pts:>5.1f}/{it['weight']:<3} {it['detail']}")
        out.append("")
    out.append(f"KẾT LUẬN: {'ĐẠT — có thể publish' if r['publish'] else 'CHƯA ĐẠT'} "
               f"(ngưỡng: SEO ≥ 75, AEO ≥ 70, GEO ≥ 70)")
    todo = [it for g in ("AEO", "GEO", "SEO") for it in r["groups"][g] if it["status"] != "pass"]
    if todo:
        todo.sort(key=lambda it: ROI_ORDER.index(it["id"]) if it["id"] in ROI_ORDER else 99)
        out.append("Vá theo ROI cao → thấp: " + ", ".join(f"{it['id']} ({it['weight']}đ)" for it in todo))
    return "\n".join(out)


def main(argv):
    args, flags, opts = argv[1:], set(), {}
    files = []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            if key in ("keyword", "locale", "translation-group"):
                opts[key] = args[i + 1] if i + 1 < len(args) else ""
                i += 2
                continue
            flags.add(key)
        else:
            files.append(a)
        i += 1
    if not files:
        print("Dùng: python score.py bai.md [--keyword \"...\"] [--locale vi] [--json] [--translation-group vi,en]",
              file=sys.stderr)
        return 1
    try:
        r = run(files[0], opts.get("keyword"), opts.get("locale"), opts.get("translation-group"))
    except OSError as e:
        print(f"LỖI ĐỌC FILE: {e}", file=sys.stderr)
        return 1
    if "json" in flags:
        print(json.dumps({k: v for k, v in r.items()}, ensure_ascii=False, indent=2))
    else:
        print(render_human(r))
    return 0 if r["publish"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
