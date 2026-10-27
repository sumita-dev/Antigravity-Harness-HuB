#!/usr/bin/env python3
"""Measure and enforce bundle size budgets (raw and gzip) for web performance.

Dune Invariant (Điều 3): Enforce bundle size limits with deterministic measurements.
Google CWV Target: JS bundle <= 170 KB gzip, total bundle <= 300 KB gzip.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def measure_file(path: Path) -> dict:
    raw_bytes = path.read_bytes()
    raw_size = len(raw_bytes)
    gzip_size = len(gzip.compress(raw_bytes))
    return {
        "file": str(path),
        "name": path.name,
        "extension": path.suffix.lower(),
        "raw_bytes": raw_size,
        "raw_kb": round(raw_size / 1024, 2),
        "gzip_bytes": gzip_size,
        "gzip_kb": round(gzip_size / 1024, 2),
    }


def scan_bundle(target_dir: Path) -> Tuple[List[dict], dict]:
    file_records: List[dict] = []
    summary = {
        "total_files": 0,
        "total_raw_kb": 0.0,
        "total_gzip_kb": 0.0,
        "by_extension": {},
    }

    if not target_dir.exists():
        return file_records, summary

    candidates: List[Path] = []
    if target_dir.is_file():
        candidates = [target_dir]
    else:
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "node_modules", ".cache"}]
            for f in files:
                p = Path(root) / f
                if p.suffix.lower() in {".js", ".mjs", ".cjs", ".css", ".html", ".wasm", ".json"}:
                    candidates.append(p)

    for p in sorted(candidates):
        try:
            rec = measure_file(p)
            file_records.append(rec)
            ext = rec["extension"]
            ext_sum = summary["by_extension"].setdefault(ext, {"count": 0, "raw_kb": 0.0, "gzip_kb": 0.0})
            ext_sum["count"] += 1
            ext_sum["raw_kb"] = round(ext_sum["raw_kb"] + rec["raw_kb"], 2)
            ext_sum["gzip_kb"] = round(ext_sum["gzip_kb"] + rec["gzip_kb"], 2)
            summary["total_raw_kb"] = round(summary["total_raw_kb"] + rec["raw_kb"], 2)
            summary["total_gzip_kb"] = round(summary["total_gzip_kb"] + rec["gzip_kb"], 2)
        except (OSError, PermissionError):
            continue

    summary["total_files"] = len(file_records)
    return file_records, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Check web asset bundle sizes against performance budgets.")
    parser.add_argument("--dir", default="dist", help="Directory or file to measure (default: dist)")
    parser.add_argument("--max-js-gzip-kb", type=float, default=170.0, help="Max JS gzip size in KB (default: 170.0 KB)")
    parser.add_argument("--max-css-gzip-kb", type=float, default=50.0, help="Max CSS gzip size in KB (default: 50.0 KB)")
    parser.add_argument("--max-total-gzip-kb", type=float, default=300.0, help="Max total gzip bundle size in KB (default: 300.0 KB)")
    parser.add_argument("--max-single-raw-kb", type=float, default=500.0, help="Max single file raw size in KB (default: 500.0 KB)")
    parser.add_argument("--require-files", action="store_true", help="Fail if no bundle files found")
    parser.add_argument("--warn-only", action="store_true", help="Warn but exit with code 0 on budget exceed")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()
    target = Path(args.dir).resolve()

    file_records, summary = scan_bundle(target)

    violations: List[str] = []

    if summary["total_files"] == 0:
        if args.require_files:
            violations.append(f"No bundle files found in {target}")
    else:
        if summary["total_gzip_kb"] > args.max_total_gzip_kb:
            violations.append(f"Total gzip size {summary['total_gzip_kb']} KB exceeds budget of {args.max_total_gzip_kb} KB")

        for rec in file_records:
            ext = rec["extension"]
            if ext in {".js", ".mjs", ".cjs"} and rec["gzip_kb"] > args.max_js_gzip_kb:
                violations.append(f"JS file '{rec['name']}' ({rec['gzip_kb']} KB gzip) exceeds JS budget of {args.max_js_gzip_kb} KB")
            elif ext == ".css" and rec["gzip_kb"] > args.max_css_gzip_kb:
                violations.append(f"CSS file '{rec['name']}' ({rec['gzip_kb']} KB gzip) exceeds CSS budget of {args.max_css_gzip_kb} KB")
            if rec["raw_kb"] > args.max_single_raw_kb:
                violations.append(f"File '{rec['name']}' ({rec['raw_kb']} KB raw) exceeds single file limit of {args.max_single_raw_kb} KB")

    if args.json:
        result = {
            "target": str(target),
            "summary": summary,
            "violations": violations,
            "files": file_records,
            "pass": len(violations) == 0,
        }
        print(json.dumps(result, indent=2))
    else:
        print("=== WebPerf: Asset Bundle Size & Budget Auditor ===")
        print(f"Target path:        {target}")
        print(f"Total assets found: {summary['total_files']}")
        print(f"Total bundle size:  {summary['total_raw_kb']} KB (raw) | {summary['total_gzip_kb']} KB (gzip)")
        if summary["by_extension"]:
            print("Breakdown by file type:")
            for ext, data in summary["by_extension"].items():
                print(f"  {ext.upper():<6} {data['count']:>3} files | {data['raw_kb']:>8} KB raw | {data['gzip_kb']:>8} KB gzip")
        print("---------------------------------------------------")
        if violations:
            print("[BUDGET VIOLATIONS DETECTED]")
            for v in violations:
                print(f"  [EXCEEDED] {v}")
        else:
            print("[OK] All assets are within performance budgets.")

    if violations and not args.warn_only:
        print(f"\n[FAIL] Performance budget exceeded ({len(violations)} violations).", file=sys.stderr)
        return 1

    print("\n[PASS] Performance budget verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
