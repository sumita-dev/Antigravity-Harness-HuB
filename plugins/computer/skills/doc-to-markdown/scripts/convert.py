#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doc-to-markdown: Utility to convert documents (PDF, DOCX, XLSX, PPTX, HTML, etc.)
to clean Markdown using MarkItDown.
Supports single-file conversion and batch folder conversion.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx",
    ".html", ".htm", ".csv", ".tsv", ".json", ".xml"
}

def clean_markdown_content(content: str, clean_pagebreaks: bool = True) -> str:
    """Cleans unnecessary artifacts from markdown content."""
    if not content:
        return ""
    
    if clean_pagebreaks:
        # Form feed character '\x0c' is often produced at page boundaries in PDFs
        content = content.replace("\x0c\n", "\n").replace("\x0c", "\n")
    
    # Strip trailing whitespace on each line while preserving indentation
    lines = [line.rstrip() for line in content.splitlines()]
    
    # Collapse 3+ consecutive empty lines into 2 empty lines
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                cleaned_lines.append("")
        else:
            blank_count = 0
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines) + "\n"

def convert_single_file(
    input_path: Path,
    output_path: Path,
    md_converter,
    clean_pagebreaks: bool = True
) -> Tuple[bool, str]:
    """Converts a single document to markdown."""
    try:
        result = md_converter.convert(str(input_path))
        text_content = result.text_content
        
        cleaned = clean_markdown_content(text_content, clean_pagebreaks=clean_pagebreaks)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
            
        return True, f"OK ({len(cleaned.encode('utf-8'))} bytes, {len(cleaned.splitlines())} lines)"
    except Exception as e:
        return False, str(e)

def process_batch(
    target_dir: Path,
    output_dir: Path,
    md_converter,
    recursive: bool = False,
    clean_pagebreaks: bool = True
) -> List[Tuple[Path, bool, str]]:
    """Batch converts all supported files in a directory."""
    results = []
    pattern = "**/*" if recursive else "*"
    
    files_to_process = [
        p for p in target_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    
    if not files_to_process:
        return results
        
    for file_path in files_to_process:
        if output_dir:
            if recursive:
                rel_path = file_path.relative_to(target_dir)
                out_file = (output_dir / rel_path).with_suffix(".md")
            else:
                out_file = output_dir / f"{file_path.stem}.md"
        else:
            out_file = file_path.with_suffix(".md")
            
        success, msg = convert_single_file(file_path, out_file, md_converter, clean_pagebreaks)
        results.append((file_path, success, msg))
        
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Convert documents (PDF, Word, Excel, PowerPoint, HTML...) to Markdown (.md)"
    )
    parser.add_argument(
        "target",
        help="Path to an input file or directory to convert"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to output markdown file (for single file) or output directory (for batch)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan subdirectories recursively when target is a folder"
    )
    parser.add_argument(
        "--no-clean-pagebreaks",
        action="store_true",
        help="Do not clean form-feed pagebreaks (\\x0c)"
    )
    
    args = parser.parse_args()
    
    try:
        from markitdown import MarkItDown
    except ImportError:
        print("[ERROR] markitdown is not installed. Install via: pip install markitdown", file=sys.stderr)
        sys.exit(1)
        
    md_converter = MarkItDown()
    clean_pagebreaks = not args.no_clean_pagebreaks
    target_path = Path(args.target).resolve()
    
    if not target_path.exists():
        print(f"[ERROR] Path not found: {target_path}", file=sys.stderr)
        sys.exit(1)
        
    if target_path.is_file():
        ext = target_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"[WARN] Extension '{ext}' is not in known extensions, proceeding anyway...", file=sys.stderr)
            
        out_path = Path(args.output).resolve() if args.output else target_path.with_suffix(".md")
        print(f"[CONVERTING] {target_path} -> {out_path}")
        success, msg = convert_single_file(target_path, out_path, md_converter, clean_pagebreaks)
        if success:
            print(f"[SUCCESS] {msg}")
            sys.exit(0)
        else:
            print(f"[FAILED] {msg}", file=sys.stderr)
            sys.exit(2)
            
    elif target_path.is_dir():
        out_dir = Path(args.output).resolve() if args.output else None
        print(f"[BATCH SCAN] Scanning: {target_path} (Recursive={args.recursive})")
        results = process_batch(
            target_path,
            out_dir,
            md_converter,
            recursive=args.recursive,
            clean_pagebreaks=clean_pagebreaks
        )
        
        if not results:
            print("[INFO] No supported document files found in directory.")
            sys.exit(0)
            
        success_count = sum(1 for _, ok, _ in results if ok)
        fail_count = len(results) - success_count
        
        print("\n--- KẾT QUẢ CHUYỂN ĐỔI BATCH ---")
        for fpath, ok, msg in results:
            status = "OK" if ok else "FAIL"
            print(f"[{status}] {fpath.name}: {msg}")
            
        print(f"\nTổng kết: Hoàn tất {success_count}/{len(results)} file (Thất bại: {fail_count})")
        if fail_count > 0:
            sys.exit(2)
        sys.exit(0)

if __name__ == "__main__":
    main()
