#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Autocomplete / Search Suggestions Fetcher
Standard library only: urllib, json, argparse, csv, sys, time, random, re.
"""

import argparse
import csv
import json
import os
import random
import re
import string
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

VI_PREFIX_MODIFIERS = [
    "cách", "hướng dẫn", "kinh nghiệm", "review", "so sánh",
    "tự học", "khóa học", "top", "tổng quan"
]

VI_SUFFIX_MODIFIERS = [
    "là gì", "cho người mới bắt đầu", "cho người mới", "lừa đảo", "uy tín",
    "ở đâu", "như thế nào", "kiếm tiền", "kinh nghiệm", "hiệu quả",
    "miễn phí", "có thật không", "mới nhất"
]

EN_PREFIX_MODIFIERS = [
    "how to", "best", "tutorial", "top", "why", "what is", "learn"
]

EN_SUFFIX_MODIFIERS = [
    "for beginners", "review", "vs", "explained", "strategy",
    "tips and tricks", "step by step", "free"
]


def fetch_raw_suggestions(
    query: str,
    lang: str = "vi",
    geo: str = "vn",
    timeout: float = 6.0
) -> List[str]:
    """Fetch raw autocomplete suggestions for a given query from YouTube API."""
    encoded_query = urllib.parse.quote(query)
    url = (
        f"https://suggestqueries.google.com/complete/search"
        f"?client=firefox&ds=yt&q={encoded_query}&hl={lang}&gl={geo}"
    )
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": f"{lang},{lang}-{geo};q=0.9,en;q=0.8",
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            content = response.read().decode(charset, errors="replace")
            data = json.loads(content)
            # Response format: [query, [sug1, sug2, ...], ...]
            if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                return [str(item).strip() for item in data[1] if str(item).strip()]
    except Exception as exc:
        # In case of network timeout or rate limit, log to stderr and return empty list
        sys.stderr.write(f"[WARN] Failed fetching query '{query}': {exc}\n")
    
    return []


def build_query_plan(
    seed: str,
    mode: str,
    lang: str = "vi"
) -> List[Tuple[str, str]]:
    """
    Build a list of (search_query, pattern_label) to execute.
    """
    seed_clean = seed.strip()
    queries: List[Tuple[str, str]] = []

    # 1. Base seed is always included
    queries.append((seed_clean, "seed"))

    if mode == "basic":
        return queries

    if mode in ("alphabet", "deep"):
        # Alphabet soup: seed + a..z, plus numbers 0..9
        for char in string.ascii_lowercase:
            queries.append((f"{seed_clean} {char}", f"alphabet: {char}"))
        for digit in "0123456789":
            queries.append((f"{seed_clean} {digit}", f"digit: {digit}"))

    if mode in ("modifiers", "deep"):
        is_vi = lang.lower().startswith("vi")
        prefixes = VI_PREFIX_MODIFIERS if is_vi else EN_PREFIX_MODIFIERS
        suffixes = VI_SUFFIX_MODIFIERS if is_vi else EN_SUFFIX_MODIFIERS

        for p in prefixes:
            queries.append((f"{p} {seed_clean}", f"prefix: {p}"))
        for s in suffixes:
            queries.append((f"{seed_clean} {s}", f"suffix: {s}"))

    return queries


def collect_suggestions(
    seed: str,
    mode: str = "basic",
    lang: str = "vi",
    geo: str = "vn",
    delay_min: float = 0.1,
    delay_max: float = 0.25,
) -> List[Dict[str, str]]:
    """
    Executes queries with deduplication, order preservation, and delay throttling.
    """
    plan = build_query_plan(seed, mode, lang)
    results: List[Dict[str, str]] = []
    seen: set = set()

    for idx, (query_text, pattern_label) in enumerate(plan):
        raw_items = fetch_raw_suggestions(query_text, lang=lang, geo=geo)
        for item in raw_items:
            norm = item.lower()
            if norm not in seen:
                seen.add(norm)
                results.append({
                    "rank": len(results) + 1,
                    "keyword": item,
                    "source_query": query_text,
                    "pattern": pattern_label,
                })

        # Throttle between requests
        if idx < len(plan) - 1:
            time.sleep(random.uniform(delay_min, delay_max))

    # Deep mode: expand top 3 non-identical suggestions recursively
    if mode == "deep":
        top_candidates = [
            r["keyword"] for r in results
            if r["keyword"].lower() != seed.strip().lower()
        ][:3]
        for candidate in top_candidates:
            time.sleep(random.uniform(delay_min, delay_max))
            sub_items = fetch_raw_suggestions(candidate, lang=lang, geo=geo)
            for item in sub_items:
                norm = item.lower()
                if norm not in seen:
                    seen.add(norm)
                    results.append({
                        "rank": len(results) + 1,
                        "keyword": item,
                        "source_query": candidate,
                        "pattern": f"deep_recursive: {candidate[:20]}",
                    })

    return results


def export_results(
    results: List[Dict[str, str]],
    output_path: str,
    output_format: str,
    seed: str,
    mode: str,
    lang: str,
    geo: str
) -> None:
    """Exports results to CSV or JSON with full UTF-8 support."""
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if output_format.lower() == "csv":
        # utf-8-sig ensures Excel opens Vietnamese accents seamlessly
        with open(output_path, mode="w", encoding="utf-8-sig", newline="") as f:
            fieldnames = ["rank", "keyword", "seed", "mode", "source_query", "pattern"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow({
                    "rank": row["rank"],
                    "keyword": row["keyword"],
                    "seed": seed,
                    "mode": mode,
                    "source_query": row["source_query"],
                    "pattern": row.get("pattern", "")
                })
    else:
        payload = {
            "seed": seed,
            "mode": mode,
            "lang": lang,
            "geo": geo,
            "total": len(results),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "suggestions": results,
        }
        with open(output_path, mode="w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def print_table(results: List[Dict[str, str]], seed: str, mode: str, lang: str, geo: str, limit: int = 15) -> None:
    """Prints a styled CLI summary table."""
    header = f"YOUTUBE SEARCH SUGGESTIONS: '{seed}' [Mode: {mode} | {lang}-{geo}]"
    divider = "=" * max(len(header), 64)
    print("\n" + divider)
    print(header)
    print(divider)
    print(f"{'Rank':>5} | {'Keyword':<42} | {'Pattern':<15}")
    print("-" * 5 + "-+-" + "-" * 42 + "-+-" + "-" * 15)

    display_items = results[:limit]
    for r in display_items:
        kw = r["keyword"]
        if len(kw) > 40:
            kw = kw[:37] + "..."
        pat = r.get("pattern", "")
        if len(pat) > 15:
            pat = pat[:13] + ".."
        print(f"{r['rank']:>5} | {kw:<42} | {pat:<15}")

    if len(results) > limit:
        print(f"{'...':>5} | {f'and {len(results) - limit} more keywords...':<42} |")

    print(divider)
    print(f"Total unique keywords collected: {len(results)}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch YouTube search autocomplete suggestions (Alphabet Soup, Modifiers, Deep crawl)."
    )
    parser.add_argument(
        "-k", "--keyword", required=True,
        help="Seed keyword to collect suggestions for"
    )
    parser.add_argument(
        "-m", "--mode", choices=["basic", "alphabet", "modifiers", "deep"], default="basic",
        help="Crawl mode: 'basic' (quick), 'alphabet' (A-Z), 'modifiers' (questions/prefixes), 'deep' (combined)"
    )
    parser.add_argument(
        "-l", "--lang", default="vi",
        help="Language code (e.g., 'vi', 'en', 'fr'). Default: 'vi'"
    )
    parser.add_argument(
        "-g", "--geo", default="vn",
        help="Country/Region code (e.g., 'vn', 'us'). Default: 'vn'"
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output file path (.csv or .json)"
    )
    parser.add_argument(
        "-f", "--format", choices=["csv", "json"], default=None,
        help="Explicit output format ('csv' or 'json'). Inferred from output extension if omitted."
    )
    parser.add_argument(
        "--delay-min", type=float, default=0.1,
        help="Minimum request delay in seconds (default: 0.1)"
    )
    parser.add_argument(
        "--delay-max", type=float, default=0.25,
        help="Maximum request delay in seconds (default: 0.25)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seed = args.keyword.strip()
    if not seed:
        sys.stderr.write("[ERROR] Keyword cannot be empty.\n")
        return 1

    results = collect_suggestions(
        seed=seed,
        mode=args.mode,
        lang=args.lang,
        geo=args.geo,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
    )

    print_table(results, seed, args.mode, args.lang, args.geo, limit=15)

    if args.output:
        fmt = args.format
        if not fmt:
            ext = os.path.splitext(args.output)[1].lower()
            fmt = "json" if ext == ".json" else "csv"
        export_results(results, args.output, fmt, seed, args.mode, args.lang, args.geo)
        print(f"[OK] Exported {len(results)} keywords to: {os.path.abspath(args.output)} ({fmt.upper()})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
