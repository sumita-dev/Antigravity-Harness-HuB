#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]
WIKI_DIR = BASE_DIR / "wiki"
RAW_DIR = BASE_DIR / "Raw"

WIKI_LINT_REPORT = BASE_DIR / "wiki_lint_report.json"
CONFLICT_REPORT = BASE_DIR / "wiki_conflict_overlap_report.json"
METADATA_REPORT = BASE_DIR / "wiki_metadata_audit.json"
DAILY_REPORT = BASE_DIR / "wiki_daily_ingest_report.json"
WEEKLY_REPORT = BASE_DIR / "wiki_weekly_ops_report.json"
MONTHLY_REPORT = BASE_DIR / "wiki_monthly_rollup.json"

ORPHAN_EXCLUDE_STEMS = {
    "_index",
    "_inbox",
    "_reports",
    "_TEMPLATE",
    "README",
    "README (1)",
    "README (2)",
    "README (3)",
    "README (4)",
}

REQUIRED_METADATA = ["linh_vuc", "do_uu_tien", "trang_thai", "ngay_cap_nhat"]
CONFLICT_KEYWORDS = ["summary", "workflow", "checklist", "cross_ref", "risk"]


def _now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def _today_iso() -> str:
    return dt.date.today().isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _wiki_md_files() -> List[Path]:
    return sorted(WIKI_DIR.rglob("*.md"))


def _wiki_root_md_files() -> List[Path]:
    return sorted(WIKI_DIR.glob("*.md"))


def _raw_md_files() -> List[Path]:
    return sorted(RAW_DIR.glob("*.md"))


def _wiki_rel(path: Path) -> str:
    return path.relative_to(WIKI_DIR).as_posix()


def _is_write_content_file(path: Path) -> bool:
    return _wiki_rel(path).startswith("Write-Content/")


def _is_orphan_excluded(rel_path: str) -> bool:
    if rel_path in {f"{x}.md" for x in ORPHAN_EXCLUDE_STEMS}:
        return True
    if rel_path.startswith("Write-Content/"):
        return True
    return False


def _parse_wikilinks(text: str) -> List[str]:
    # Loại bỏ code blocks (```...```) và inline code spans (`...`) để tránh parse cú pháp ví dụ
    text_clean = re.sub(r"```[\s\S]*?```", "", text)
    text_clean = re.sub(r"`[^`\n]+`", "", text_clean)
    return [x.strip() for x in re.findall(r"\[\[([^\]|#]+)", text_clean)]


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    if len(lines) < 3:
        return text
    if lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).lstrip("\n")
    return text


def run_wiki_lint() -> dict:
    files = _wiki_md_files()
    rel_paths = [_wiki_rel(f) for f in files]
    rel_set = set(rel_paths)
    inbound = {rel: 0 for rel in rel_paths}
    stem_index: Dict[str, List[str]] = {}
    for rel in rel_paths:
        stem_index.setdefault(Path(rel).stem, []).append(rel)
    broken_links: List[dict] = []

    for f in files:
        src_rel = _wiki_rel(f)
        text = _read_text(f)
        for link in _parse_wikilinks(text):
            if not link:
                continue

            normalized = link.replace("\\", "/")

            # 1. Trỏ tới Raw/
            if normalized.startswith("Raw/"):
                target_raw = BASE_DIR / normalized
                if not target_raw.exists():
                    name = Path(normalized).name
                    if not any(RAW_DIR.rglob(name)):
                        broken_links.append({"file": src_rel, "link": link})
                continue

            # 2. Xử lý tiền tố wiki/ nếu có
            stripped_wiki = normalized[5:] if normalized.startswith("wiki/") else normalized

            # 3. Kiểm tra file .md trong wiki/
            target_rel = stripped_wiki if stripped_wiki.endswith(".md") else f"{stripped_wiki}.md"
            if target_rel in rel_set:
                inbound[target_rel] += 1
                continue

            # 4. Kiểm tra các định dạng khác trong wiki/ (.base, .canvas, v.v.)
            if (WIKI_DIR / stripped_wiki).exists():
                continue

            # 5. Kiểm tra theo stem trong wiki/
            candidates = stem_index.get(stripped_wiki, [])
            if len(candidates) == 1:
                inbound[candidates[0]] += 1
                continue
            elif len(candidates) > 1:
                root_candidates = [c for c in candidates if "/" not in c]
                if len(root_candidates) == 1:
                    inbound[root_candidates[0]] += 1
                    continue
                else:
                    broken_links.append(
                        {
                            "file": src_rel,
                            "link": link,
                            "reason": "ambiguous_wikilink",
                            "candidates": candidates[:10],
                        }
                    )
                    continue

            # 6. Kiểm tra ngoài wiki/ trong Vault (memory/, facts/, root)
            vault_target = BASE_DIR / normalized
            vault_target_md = BASE_DIR / f"{normalized}.md"
            vault_mem_fact = BASE_DIR / "memory" / "facts" / f"{normalized}.md"
            vault_mem = BASE_DIR / "memory" / f"{normalized}.md"

            if vault_target.exists() or vault_target_md.exists() or vault_mem_fact.exists() or vault_mem.exists():
                continue

            broken_links.append({"file": src_rel, "link": link})

    # Raw chưa được trích dẫn bởi bất kỳ trang wiki nào qua [[Raw/ten-file.md]]
    raw_names = {x.name for x in _raw_md_files()}
    wiki_blob = "\n".join(_read_text(f) for f in files)
    raw_uncited = sorted(
        name for name in raw_names if f"[[Raw/{name}]]" not in wiki_blob
    )

    orphan_pages = [
        rel
        for rel, count in inbound.items()
        if count == 0 and not _is_orphan_excluded(rel)
    ]

    report = {
        "generated_at": _now_iso(),
        "wiki_files": len(files),
        "raw_files": len(raw_names),
        "broken_links": len(broken_links),
        "orphan_pages": len(orphan_pages),
        "missing_source_pages": len(raw_uncited),
        "broken_link_samples": broken_links[:50],
        "orphan_samples": orphan_pages[:50],
        "missing_source_samples": raw_uncited[:50],
    }
    _write_json(WIKI_LINT_REPORT, report)
    return report


def _extract_frontmatter(text: str) -> Dict[str, str]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}

    payload: Dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        val = v.strip().strip('"').strip("'")
        payload[k.strip()] = val
    return payload


def _is_metadata_excluded(path: Path) -> bool:
    rel = _wiki_rel(path)
    return (
        rel.startswith("Write-Content/")
        or rel.startswith("archive/")
        or rel == "agy-doctor-latest.md"
    )


def run_metadata_audit() -> dict:
    files = _wiki_md_files()
    audit_files = [f for f in files if not _is_metadata_excluded(f)]
    missing: List[dict] = []
    linh_vuc_counter = Counter()
    priority_counter = Counter()
    status_counter = Counter()

    for f in audit_files:
        data = _extract_frontmatter(_read_text(f))
        miss = [k for k in REQUIRED_METADATA if not data.get(k)]
        if miss:
            missing.append({"file": _wiki_rel(f), "missing": miss})

        linh_vuc_counter[data.get("linh_vuc", "unknown")] += 1
        priority_counter[data.get("do_uu_tien", "unknown")] += 1
        status_counter[data.get("trang_thai", "unknown")] += 1

    report = {
        "generated_at": _now_iso(),
        "files_total": len(audit_files),
        "files_excluded": len(files) - len(audit_files),
        "files_valid_metadata": len(audit_files) - len(missing),
        "files_missing_metadata": len(missing),
        "linh_vuc_distribution": dict(sorted(linh_vuc_counter.items())),
        "priority_distribution": dict(sorted(priority_counter.items())),
        "status_distribution": dict(sorted(status_counter.items())),
        "missing_samples": missing[:50],
    }
    _write_json(METADATA_REPORT, report)
    return report


def _count_heading(text: str, level: int) -> int:
    pattern = rf"^{'#' * level}\s+"
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def _extract_years(text: str) -> List[str]:
    return sorted(set(re.findall(r"20\d{2}", text)))


def _extract_numbers(text: str) -> set:
    return set(re.findall(r"(?<!\w)\d+(?:\.\d+)?", text))


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _load_conflict_pairs() -> List[Tuple[str, str, bool]]:
    if CONFLICT_REPORT.exists():
        try:
            data = json.loads(CONFLICT_REPORT.read_text(encoding="utf-8"))
            pairs = []
            for x in data.get("pairs", []):
                g = x.get("global")
                v = x.get("vn")
                if g and v:
                    pairs.append((g, v, bool(x.get("manual_pair", False))))
            # unique by (g, v)
            seen = set()
            unique_pairs = []
            for item in pairs:
                key = (item[0], item[1])
                if key in seen:
                    continue
                seen.add(key)
                unique_pairs.append(item)
            return unique_pairs
        except Exception:
            pass

    # Fallback rules if report file is missing/corrupted.
    fallback_pairs = [
        ("00-marketing-plan-global.md", "00-ke-hoach-mkt.md", True),
        ("01-content-calendar-global.md", "01-lich-noi-dung.md", True),
        ("02-campaign-brief-global.md", "02-brief-chien-dich.md", True),
        ("03-performance-eval-global.md", "03-danh-gia-hieu-suat.md", True),
        ("04-script-video-global.md", "04-script-video.md", True),
        ("05-ad-copy-global.md", "05-copy-quang-cao.md", True),
        ("06-ugc-egc-brief-global.md", "06-brief-ugc-egc.md", True),
        ("07-marketing-report-global.md", "07-bao-cao-marketing.md", True),
        ("08-competitor-research-global.md", "08-nghien-cuu-doi-thu.md", True),
        ("09-customer-insight-global.md", "09-insight-khach-hang.md", True),
        ("10-reverse-kpi-global.md", "10-tinh-kpi-nguoc.md", True),
        ("11-channel-setup-global.md", "11-thiet-lap-kenh.md", True),
        ("12-landing-page-brief-global.md", "12-brief-landing-page.md", True),
        ("13-data-analysis-global.md", "13-phan-tich-du-lieu.md", True),
        ("14-email-marketing-global.md", "14-email-marketing.md", True),
        ("15-social-listening-global.md", "15-social-listening.md", True),
        ("16-marketing-psychology-global.md", "16-marketing-psychology.md", True),
        ("17-pricing-strategy-global.md", "17-pricing-strategy.md", True),
        ("18-referral-program-global.md", "18-referral-program.md", True),
        ("19-ab-test-setup-global.md", "19-ab-test-setup.md", True),
        ("20-client-intake-brief-global.md", "20-brief-client-intake.md", True),
        ("21-ads-audit-global.md", "21-audit-ads-performance.md", True),
        ("22-personal-brand-context-global.md", "22-personal-brand-context.md", True),
        ("23-personal-brand-strategy-global.md", "23-personal-brand-strategy.md", True),
        ("24-ai-avatar-production-global.md", "24-ai-avatar-production.md", True),
        ("25-voice-clone-podcast-global.md", "25-voice-clone-podcast.md", True),
        ("26-thought-leadership-content-global.md", "26-thought-leadership-content.md", True),
        ("27-personal-brand-monetize-global.md", "27-personal-brand-monetize.md", True),
        ("28-community-building-global.md", "28-community-building.md", True),
        ("29-dropshipping-mastery-global.md", "29-xuat-khau-b2b.md", False),
        ("ai-video-disclosure-global.md", "ai-video-disclosure-vn.md", True),
        ("dropshipping-tools-global.md", "ai-avatar-tools-vn.md", False),
        ("hook-formulas-global.md", "hook-formulas-vn.md", True),
        ("product-marketing-context-global.md", "product-marketing-context.md", True),
        ("voice-clone-prompts-global.md", "voice-clone-prompts-vn.md", True),
    ]
    return fallback_pairs


def run_conflict_lint() -> dict:
    pairs = _load_conflict_pairs()
    rows = []

    for global_name, vn_name, manual_pair in pairs:
        gp = WIKI_DIR / global_name
        vp = WIKI_DIR / vn_name
        if not gp.exists() or not vp.exists():
            continue

        g_text = _read_text(gp)
        v_text = _read_text(vp)
        g_body = _strip_frontmatter(g_text)
        v_body = _strip_frontmatter(v_text)

        years_g = _extract_years(g_body)
        years_v = _extract_years(v_body)
        nums_g = _extract_numbers(g_body)
        nums_v = _extract_numbers(v_body)

        g_low = g_body.lower()
        v_low = v_body.lower()
        flags = []
        for k in CONFLICT_KEYWORDS:
            if (k in g_low) != (k in v_low):
                flags.append(f"keyword_mismatch:{k}")
        if years_g != years_v:
            flags.append("year_set_mismatch")

        if len(flags) == 0:
            severity = "ok"
        elif len(flags) == 1:
            severity = "low"
        elif len(flags) == 2:
            severity = "medium"
        else:
            severity = "high"

        rows.append(
            {
                "global": global_name,
                "vn": vn_name,
                "h2_global": _count_heading(g_body, 2),
                "h2_vn": _count_heading(v_body, 2),
                "h3_global": _count_heading(g_body, 3),
                "h3_vn": _count_heading(v_body, 3),
                "h2_ratio": round(
                    min(_count_heading(g_body, 2), _count_heading(v_body, 2))
                    / max(_count_heading(g_body, 2), _count_heading(v_body, 2), 1),
                    3,
                ),
                "h3_ratio": round(
                    min(_count_heading(g_body, 3), _count_heading(v_body, 3))
                    / max(_count_heading(g_body, 3), _count_heading(v_body, 3), 1),
                    3,
                ),
                "years_global": years_g,
                "years_vn": years_v,
                "numeric_jaccard": round(_jaccard(nums_g, nums_v), 3),
                "flags": flags,
                "severity": severity,
                "manual_pair": manual_pair,
            }
        )

    summary = {
        "pairs_total": len(rows),
        "ok": sum(1 for x in rows if x["severity"] == "ok"),
        "low": sum(1 for x in rows if x["severity"] == "low"),
        "medium": sum(1 for x in rows if x["severity"] == "medium"),
        "high": sum(1 for x in rows if x["severity"] == "high"),
    }
    focus = [x for x in rows if x["severity"] in ("medium", "high")]

    # Scan real wiki pages for "## Mâu thuẫn" sections and open questions
    contradiction_sections = []
    for f in _wiki_md_files():
        rel = _wiki_rel(f)
        txt = _read_text(f)
        if re.search(r"^##\s+Mâu\s+thuẫn\b", txt, flags=re.IGNORECASE | re.MULTILINE):
            contradiction_sections.append(rel)

    open_questions: List[str] = []
    oq_path = WIKI_DIR / "_open-questions.md"
    if oq_path.exists():
        for line in _read_text(oq_path).splitlines():
            s = line.strip()
            if s.startswith("- [ ]") and "(YYYY-MM-DD)" not in s:
                open_questions.append(s)

    report = {
        "generated_at": _now_iso(),
        "summary": summary,
        "contradiction_sections_count": len(contradiction_sections),
        "contradiction_sections": contradiction_sections,
        "open_questions_count": len(open_questions),
        "open_questions": open_questions,
        "pairs": rows,
        "focus_list": focus,
    }
    _write_json(CONFLICT_REPORT, report)
    return report


def run_daily_ingest_scan() -> dict:
    """Map Raw → wiki bằng liên kết [[Raw/ten-file.md]], không bắt buộc trùng tên file."""
    raw_names = sorted(x.name for x in _raw_md_files())
    wiki_files = _wiki_md_files()
    wiki_blob = "\n".join(_read_text(f) for f in wiki_files)

    cited = [name for name in raw_names if f"[[Raw/{name}]]" in wiki_blob]
    missing_in_wiki = [name for name in raw_names if name not in set(cited)]

    ops_stems = {
        "_index",
        "_inbox",
        "_reports",
        "monthly-review",
        "huong-dan-su-dung",
        "README",
    }
    wiki_without_raw_link: List[str] = []
    for f in wiki_files:
        rel = _wiki_rel(f)
        if Path(rel).stem in ops_stems or rel.startswith("Write-Content/"):
            continue
        text = _read_text(f)
        if "[[Raw/" not in text:
            wiki_without_raw_link.append(rel)

    # Thống kê tài liệu non-.md trong Raw/ để tránh điểm mù
    non_md_exts = {".pdf", ".docx", ".doc", ".xlsx", ".csv", ".txt", ".html"}
    raw_non_md_by_ext: Dict[str, int] = {}
    raw_non_md_uncited = 0
    for f in RAW_DIR.rglob("*"):
        if f.is_file() and f.suffix.lower() in non_md_exts:
            ext = f.suffix.lower()
            raw_non_md_by_ext[ext] = raw_non_md_by_ext.get(ext, 0) + 1
            rel = f.relative_to(RAW_DIR).as_posix()
            if not (
                f"[[Raw/{rel}" in wiki_blob
                or f"[[Raw/{f.name}" in wiki_blob
                or f"[[{f.stem}]]" in wiki_blob
                or f"[[{f.stem}|" in wiki_blob
            ):
                raw_non_md_uncited += 1

    # Phân tích các thư mục con trong Raw/ (ví dụ Raw/Luat Dat Dai/)
    subdirs_summary = {}
    for sub in sorted(RAW_DIR.iterdir()):
        if sub.is_dir() and not sub.name.startswith("."):
            sub_mds = list(sub.rglob("*.md"))
            sub_cited = []
            for f in sub_mds:
                rel = f.relative_to(RAW_DIR).as_posix()
                if (
                    f"[[Raw/{rel}]]" in wiki_blob
                    or f"[[Raw/{rel}|" in wiki_blob
                    or f"[[Raw/{sub.name}/{f.name}]]" in wiki_blob
                    or f"[[Raw/{sub.name}/{f.name}|" in wiki_blob
                    or f"[[Raw/{f.name}]]" in wiki_blob
                    or f"[[Raw/{f.name}|" in wiki_blob
                    or f"[[{f.stem}]]" in wiki_blob
                    or f"[[{f.stem}|" in wiki_blob
                ):
                    sub_cited.append(f.name)
            sub_non_md = [
                f for f in sub.rglob("*") if f.is_file() and f.suffix.lower() in non_md_exts
            ]
            subdirs_summary[sub.name] = {
                "total_md": len(sub_mds),
                "cited_in_wiki": len(sub_cited),
                "pending_ingest": len(sub_mds) - len(sub_cited),
                "total_non_md_docs": len(sub_non_md),
            }

    report = {
        "generated_at": _now_iso(),
        "raw_files": len(raw_names),
        "raw_non_md_docs": sum(raw_non_md_by_ext.values()),
        "raw_non_md_uncited": raw_non_md_uncited,
        "raw_non_md_by_ext": dict(sorted(raw_non_md_by_ext.items())),
        "raw_subdirs": subdirs_summary,
        "wiki_files": len(_wiki_root_md_files()),
        "wiki_files_recursive": len(wiki_files),
        "raw_cited_in_wiki_count": len(cited),
        "raw_missing_in_wiki_count": len(missing_in_wiki),
        "raw_missing_in_wiki": missing_in_wiki,
        "wiki_pages_without_raw_link_count": len(wiki_without_raw_link),
        "wiki_pages_without_raw_link_samples": wiki_without_raw_link[:50],
        "scan_mode": "raw_wikilink_citation",
    }
    _write_json(DAILY_REPORT, report)
    return report


def run_weekly_ops() -> dict:
    lint = run_wiki_lint()
    conflict = run_conflict_lint()
    metadata = run_metadata_audit()
    daily = run_daily_ingest_scan()

    report = {
        "generated_at": _now_iso(),
        "lint": lint,
        "conflict": conflict.get("summary", {}),
        "metadata": {
            "files_total": metadata.get("files_total", 0),
            "files_missing_metadata": metadata.get("files_missing_metadata", 0),
        },
        "daily": {
            "raw_missing_in_wiki_count": daily.get("raw_missing_in_wiki_count", 0),
        },
    }
    _write_json(WEEKLY_REPORT, report)
    return report


def _upsert_monthly_review(month: str, payload: dict) -> None:
    review_path = WIKI_DIR / "monthly-review.md"
    marker = f"### {month}"

    block_lines = [
        marker,
        f"- Ngày cập nhật: {payload['generated_at']}",
        f"- Raw thiếu trong wiki: `{payload['daily']['raw_missing_in_wiki_count']}`",
        f"- Broken links: `{payload['lint']['broken_links']}`",
        f"- Orphan pages: `{payload['lint']['orphan_pages']}`",
        f"- Missing source pages: `{payload['lint']['missing_source_pages']}`",
        f"- Conflict pairs (`low+`): `{payload['conflict_low_plus']}`",
        f"- Metadata thiếu: `{payload['metadata']['files_missing_metadata']}`",
        "",
    ]
    block = "\n".join(block_lines)

    if not review_path.exists():
        return

    text = _read_text(review_path)
    pattern = rf"(?ms)^### {re.escape(month)}\n.*?(?=^### |\Z)"
    if re.search(pattern, text):
        text = re.sub(pattern, block, text)
    else:
        text = text.rstrip() + "\n\n" + block

    review_path.write_text(text, encoding="utf-8", newline="")


def run_monthly_rollup(month: str) -> dict:
    lint = run_wiki_lint()
    conflict = run_conflict_lint()
    metadata = run_metadata_audit()
    daily = run_daily_ingest_scan()

    conflict_summary = conflict.get("summary", {})
    conflict_low_plus = (
        conflict_summary.get("low", 0)
        + conflict_summary.get("medium", 0)
        + conflict_summary.get("high", 0)
    )

    payload = {
        "generated_at": _now_iso(),
        "month": month,
        "lint": {
            "broken_links": lint["broken_links"],
            "orphan_pages": lint["orphan_pages"],
            "missing_source_pages": lint["missing_source_pages"],
        },
        "conflict": conflict_summary,
        "conflict_low_plus": conflict_low_plus,
        "metadata": {
            "files_total": metadata["files_total"],
            "files_missing_metadata": metadata["files_missing_metadata"],
        },
        "daily": {
            "raw_missing_in_wiki_count": daily["raw_missing_in_wiki_count"],
        },
    }

    _write_json(MONTHLY_REPORT, payload)
    _upsert_monthly_review(month, payload)
    return payload


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Obsidian wiki ops runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("daily", help="Daily ingest scan")
    sub.add_parser("weekly", help="Weekly ops (lint + conflict + metadata + daily scan)")

    monthly = sub.add_parser("monthly", help="Monthly rollup")
    monthly.add_argument(
        "--month",
        default=dt.date.today().strftime("%Y-%m"),
        help="Month key, format YYYY-MM",
    )

    args = parser.parse_args()

    if args.cmd == "daily":
        _print_json(run_daily_ingest_scan())
        return

    if args.cmd == "weekly":
        _print_json(run_weekly_ops())
        return

    if args.cmd == "monthly":
        _print_json(run_monthly_rollup(args.month))
        return

    raise RuntimeError("Unsupported command")


if __name__ == "__main__":
    main()
