#!/usr/bin/env python3
"""Verify official documentation citations and reference links in source or markdown.

Source-Driven Development (SDD): Ensure implementation decisions are grounded
in authoritative official documentation rather than assumptions or hallucinations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Recognized official documentation domains
OFFICIAL_DOC_DOMAINS = {
    # Python ecosystem
    "docs.python.org", "peps.python.org", "pypi.org", "pytest.org", "docs.pytest.org",
    "docs.pydantic.dev", "fastapi.tiangolo.com", "flask.palletsprojects.com", "docs.sqlalchemy.org",
    "mypy.readthedocs.io", "ruff.rs", "docs.astral.sh",
    # JavaScript / TypeScript / Web
    "developer.mozilla.org", "nodejs.org", "typescriptlang.org", "react.dev", "reactjs.org",
    "nextjs.org", "vuejs.org", "angular.dev", "vitejs.dev", "tailwindcss.com",
    "web.dev", "w3.org", "whatwg.org", "tc39.es", "playwright.dev",
    # Google Ecosystem
    "ai.google.dev", "developers.google.com", "cloud.google.com", "firebase.google.com",
    "developer.android.com", "golang.org", "go.dev",
    # General authoritative
    "github.com", "raw.githubusercontent.com", "microsoft.com", "learn.microsoft.com",
    "docs.docker.com", "kubernetes.io", "postgresql.org", "sqlite.org",
}

URL_REGEX = re.compile(r"https?://[^\s'\"<>()]+", re.IGNORECASE)


def extract_urls(text: str) -> List[str]:
    raw_urls = URL_REGEX.findall(text)
    clean_urls = []
    for u in raw_urls:
        u = u.rstrip(".,;:)>]}")
        if u:
            clean_urls.append(u)
    return clean_urls


def is_official(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if ":" in domain:
            domain = domain.split(":")[0]
        for official in OFFICIAL_DOC_DOMAINS:
            if domain == official or domain.endswith("." + official):
                return True
        return False
    except Exception:
        return False


def verify_sources(target_path: Path) -> Tuple[List[dict], int, int]:
    records: List[dict] = []
    official_count = 0
    unofficial_count = 0

    files_to_scan = []
    if target_path.is_file():
        files_to_scan = [target_path]
    elif target_path.is_dir():
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "__pycache__", "node_modules", ".brain"}]
            for f in files:
                if f.endswith((".py", ".md", ".ts", ".js", ".json")):
                    files_to_scan.append(Path(root) / f)

    for file_path in files_to_scan:
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        urls = extract_urls(content)
        if not urls:
            continue

        for url in set(urls):
            official = is_official(url)
            if official:
                official_count += 1
            else:
                unofficial_count += 1
            records.append({
                "file": str(file_path),
                "url": url,
                "is_official": official,
                "domain": urlparse(url).netloc.lower(),
            })

    return records, official_count, unofficial_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify official documentation references.")
    parser.add_argument("--path", default=".", help="File or directory to check (default: current directory)")
    parser.add_argument("--min-sources", type=int, default=0, help="Minimum number of official citations required")
    parser.add_argument("--allow-empty", action="store_true", help="Allow zero citations without failure")
    parser.add_argument("--strict", action="store_true", help="Fail if any unofficial or untrusted source is found")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()
    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: Path {target} does not exist.", file=sys.stderr)
        return 1

    records, official_count, unofficial_count = verify_sources(target)

    if args.json:
        result = {
            "path": str(target),
            "official_sources": official_count,
            "unofficial_sources": unofficial_count,
            "records": records,
        }
        print(json.dumps(result, indent=2))
    else:
        print("=== Source-Driven Development: Documentation Verifier ===")
        print(f"Target: {target}")
        print(f"Authoritative Official Citations: {official_count}")
        print(f"Other / Unofficial Sources:       {unofficial_count}")
        print("---------------------------------------------------------")
        for r in records[:15]:
            status = "[OFFICIAL]" if r["is_official"] else "[UNOFFICIAL]"
            print(f"{status} {r['file']} -> {r['url']}")
        if len(records) > 15:
            print(f"... and {len(records) - 15} more citations.")

    if not args.allow_empty and args.min_sources > 0 and official_count < args.min_sources:
        print(f"\n[FAIL] Insufficient official documentation citations ({official_count} < {args.min_sources}).", file=sys.stderr)
        return 1

    if args.strict and unofficial_count > 0:
        print(f"\n[FAIL] Strict mode: found {unofficial_count} unofficial documentation citations.", file=sys.stderr)
        return 1

    print("\n[PASS] Documentation citations verified successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
