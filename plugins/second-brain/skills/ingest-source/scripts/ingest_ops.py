#!/usr/bin/env python3
"""Deterministic pre-processing (prepare) and post-verification (verify) for Second Brain ingest."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SECRET_PATTERNS = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{20,}\b")),
    ("auth_kv", re.compile(r"(?i)\b(api_key|secret_key|sessionid|access_token)\s*[:=]\s*['\"]?[A-Za-z0-9._-]{12,}")),
]

REQUIRED_FRONTMATTER_KEYS = ("linh_vuc", "do_uu_tien", "trang_thai", "ngay_cap_nhat")
INDEX_FILENAMES = {"index.md", "readme.md", "00_index_chinh_sach.md", "00_he_thong_hoa_creator_affiliate.md"}


def normalize_for_hash(text: str) -> str:
    """Strip volatile URL query tokens and normalize whitespace for deduplication."""
    cleaned = re.sub(r"https?://[^\s)\]]+", lambda m: m.group(0).split("?")[0], text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def scan_secrets(text: str) -> list[str]:
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(label)
    return findings


def cmd_prepare(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    source = Path(args.source).resolve()
    if not source.exists():
        print(json.dumps({"error": f"Source path not found: {source}"}, ensure_ascii=False))
        return 1

    md_files = sorted(source.rglob("*.md"))
    seen_hashes: dict[str, str] = {}
    duplicates: list[dict[str, str]] = []
    stubs: list[dict[str, Any]] = []
    index_files: list[str] = []
    secret_warnings: list[dict[str, Any]] = []
    clean_items: list[dict[str, Any]] = []

    for fp in md_files:
        try:
            rel_vault = fp.relative_to(vault).as_posix()
        except ValueError:
            rel_vault = fp.as_posix()

        raw_bytes = fp.read_bytes()
        size_bytes = len(raw_bytes)
        text = raw_bytes.decode("utf-8", errors="replace")

        secrets = scan_secrets(text)
        if secrets:
            secret_warnings.append({"path": rel_vault, "types": secrets})

        if fp.name.lower() in INDEX_FILENAMES:
            index_files.append(rel_vault)
            continue

        body_hash = hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()
        if body_hash in seen_hashes:
            duplicates.append({"path": rel_vault, "duplicate_of": seen_hashes[body_hash]})
            continue
        seen_hashes[body_hash] = rel_vault

        if size_bytes < args.stub_bytes:
            stubs.append({"path": rel_vault, "bytes": size_bytes})

        clean_items.append({
            "path": rel_vault,
            "bytes": size_bytes,
            "lines": text.count("\n") + 1,
            "is_stub": size_bytes < args.stub_bytes,
        })

    # Byte-balanced sharding
    max_bytes = args.max_kb * 1024
    shards: list[dict[str, Any]] = []
    cur_files: list[dict[str, Any]] = []
    cur_bytes = 0

    for item in clean_items:
        would_exceed_count = len(cur_files) >= args.max_files
        would_exceed_bytes = (cur_bytes + item["bytes"] > max_bytes) and len(cur_files) > 0
        if would_exceed_count or would_exceed_bytes:
            shards.append({
                "shard_id": len(shards) + 1,
                "file_count": len(cur_files),
                "total_kb": round(cur_bytes / 1024, 2),
                "files": cur_files,
            })
            cur_files = []
            cur_bytes = 0
        cur_files.append(item)
        cur_bytes += item["bytes"]

    if cur_files:
        shards.append({
            "shard_id": len(shards) + 1,
            "file_count": len(cur_files),
            "total_kb": round(cur_bytes / 1024, 2),
            "files": cur_files,
        })

    manifest = {
        "vault_path": str(vault),
        "source_path": str(source),
        "total_md_scanned": len(md_files),
        "index_files": index_files,
        "duplicates_removed": len(duplicates),
        "duplicates": duplicates,
        "stub_files_count": len(stubs),
        "secret_warnings": secret_warnings,
        "clean_files_count": len(clean_items),
        "total_clean_kb": round(sum(i["bytes"] for i in clean_items) / 1024, 2),
        "shard_limits": {"max_files": args.max_files, "max_kb": args.max_kb},
        "shard_count": len(shards),
        "shards": shards,
    }

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {k: v for k, v in manifest.items() if k not in ("shards", "duplicates")}
    summary["manifest_path"] = str(out_path)

    tmpl_path = Path(__file__).resolve().with_name("ingest_workflow.tmpl")
    if tmpl_path.exists():
        wf_out = out_path.parent / "workflow_run.py"
        wf_out.write_text(tmpl_path.read_text(encoding="utf-8"), encoding="utf-8")
        summary["workflow_script"] = str(wf_out)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def cmd_verify(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    wiki_dir = vault / "wiki"

    target_paths: list[Path] = []
    for pattern in args.files:
        p = Path(pattern)
        if not p.is_absolute():
            p = vault / pattern
        matched = glob.glob(str(p), recursive=True)
        if matched:
            target_paths.extend(Path(m) for m in sorted(matched))
        elif p.exists():
            target_paths.append(p)
        else:
            print(json.dumps({"error": f"Target not found: {pattern}"}, ensure_ascii=False))
            return 1

    bom_errors: list[str] = []
    frontmatter_errors: list[dict[str, Any]] = []
    missing_raw_refs: list[dict[str, str]] = []
    missing_wiki_refs: list[dict[str, str]] = []
    cited_raw_paths: set[str] = set()

    for fp in target_paths:
        raw_bytes = fp.read_bytes()
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            bom_errors.append(fp.name)
        text = raw_bytes.decode("utf-8", errors="replace")

        meta = parse_frontmatter(text)
        missing_keys = [k for k in REQUIRED_FRONTMATTER_KEYS if not meta.get(k)]
        if missing_keys:
            frontmatter_errors.append({"file": fp.name, "missing_keys": missing_keys})

        for match in re.findall(r"\[\[([^\]]+)\]\]", text):
            target = match.split("|")[0].split("#")[0].strip()
            if not target:
                continue
            if target.startswith("Raw/"):
                cited_raw_paths.add(target)
                if not (vault / target).exists():
                    missing_raw_refs.append({"file": fp.name, "ref": target})
            else:
                cand1 = wiki_dir / f"{target}.md"
                cand2 = wiki_dir / target
                if not (cand1.exists() or cand2.exists()):
                    missing_wiki_refs.append({"file": fp.name, "ref": target})

    coverage: dict[str, Any] | None = None
    if args.manifest:
        m_data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        clean_paths = {
            item["path"]
            for shard in m_data.get("shards", [])
            for item in shard.get("files", [])
            if not item.get("is_stub")
        }
        uncited = sorted(clean_paths - cited_raw_paths)
        covered = len(clean_paths) - len(uncited)
        coverage = {
            "non_stub_clean_files": len(clean_paths),
            "cited_in_verified_wiki": covered,
            "coverage_pct": round((covered / len(clean_paths) * 100), 1) if clean_paths else 100.0,
            "uncited_count": len(uncited),
            "uncited_sample": uncited[:20],
        }

    ok = not (bom_errors or frontmatter_errors or missing_raw_refs or missing_wiki_refs)
    report = {
        "status": "PASS" if ok else "FAIL",
        "verified_files_count": len(target_paths),
        "bom_errors": bom_errors,
        "frontmatter_errors": frontmatter_errors,
        "missing_raw_refs": missing_raw_refs,
        "missing_wiki_refs": missing_wiki_refs,
        "total_unique_raw_cited": len(cited_raw_paths),
        "coverage": coverage,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Second Brain ingest prepare & verify helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Deduplicate, scan secrets, and shard Raw files.")
    p_prep.add_argument("--source", required=True, help="Source folder inside Raw/")
    p_prep.add_argument("--vault", required=True, help="Vault root directory")
    p_prep.add_argument("--out", default="ingest_manifest.json", help="Output manifest JSON path")
    p_prep.add_argument("--max-files", type=int, default=15, help="Max files per shard")
    p_prep.add_argument("--max-kb", type=int, default=150, help="Max KB per shard")
    p_prep.add_argument("--stub-bytes", type=int, default=1200, help="Threshold in bytes to flag stub files")

    p_ver = sub.add_parser("verify", help="Verify wiki frontmatter, links, and Raw coverage.")
    p_ver.add_argument("--vault", required=True, help="Vault root directory")
    p_ver.add_argument("--files", nargs="+", required=True, help="Wiki file paths or globs (relative to vault or abs)")
    p_ver.add_argument("--manifest", help="Optional ingest_manifest.json for coverage check")

    parsed = parser.parse_args()
    if parsed.cmd == "prepare":
        return cmd_prepare(parsed)
    return cmd_verify(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
