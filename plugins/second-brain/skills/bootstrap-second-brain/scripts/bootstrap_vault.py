#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bootstrap_vault.py — Khởi tạo Second Brain Vault từ thư mục nguồn hỗn hợp.
- Kiểm tra / cài đặt Microsoft MarkItDown nếu thiếu.
- Dựng cấu trúc Vault chuẩn (Raw/, wiki/, templates/, ops/, memory/, AGENTS.md, CLAUDE.md).
- Sao chép nguồn gốc vào Raw/ (bất biến), convert tài liệu bằng MarkItDown sang .md.
- Xuất JSON thống kê & danh sách ảnh (.png/.jpg/.jpeg/.webp) chờ AI Vision trích xuất.
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

MARKITDOWN_EXTS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx",
    ".html", ".htm", ".csv", ".tsv", ".json", ".xml", ".zip", ".epub",
}
TEXT_EXTS = {".txt"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_TIMEOUT_SEC = 45


def ensure_markitdown(auto_install: bool) -> Tuple[bool, str]:
    """Ensure microsoft/markitdown is importable; install if requested."""
    try:
        import markitdown  # noqa: F401
        return True, "already_installed"
    except ImportError:
        if not auto_install:
            return False, "markitdown not installed (pass --install-markitdown)"
        cmd = [sys.executable, "-m", "pip", "install", "--quiet", "markitdown[all]"]
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            return False, f"pip install failed: {proc.stderr.strip()}"
        return True, "installed"


def clean_markdown(content: str) -> str:
    """Normalize line endings, form-feeds, and excessive blank lines."""
    if not content:
        return ""
    content = content.replace("\x0c\n", "\n").replace("\x0c", "\n")
    lines = [line.rstrip() for line in content.splitlines()]
    out: List[str] = []
    blanks = 0
    for line in lines:
        if not line.strip():
            blanks += 1
            if blanks <= 2:
                out.append("")
        else:
            blanks = 0
            out.append(line)
    return "\n".join(out).strip() + "\n"


def write_if_missing(path: Path, content: str) -> None:
    """Create file with UTF-8 No-BOM only if it does not already exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def scaffold_vault(vault_dir: Path, today: str) -> None:
    """Create minimal Karpathy 3-layer Obsidian Second Brain structure."""
    for sub in ["Raw", "wiki", "templates", "ops", "memory/facts/global", "memory/facts/projects", "Inbox"]:
        (vault_dir / sub).mkdir(parents=True, exist_ok=True)

    agents_md = (
        "# Vault Schema (Second Brain Obsidian)\n\n"
        "> Mục tiêu: biến vault thành wiki tích luỹ (compounding) theo mô hình 3 lớp của Andrej Karpathy.\n\n"
        "## 1. Ba lớp\n"
        "- `Raw/`: Tài liệu gốc (BẤT BIẾN với AI — chỉ đọc, được phép kèm file `.md` chuyển đổi).\n"
        "- `wiki/`: Tri thức đã chưng cất, có `[[wikilink]]` và trích dẫn `[[Raw/...]]`.\n"
        "- `CLAUDE.md` / `AGENTS.md`: Quy ước vận hành cho AI.\n\n"
        "## 2. Frontmatter bắt buộc cho `wiki/`\n"
        "`linh_vuc`, `do_uu_tien`, `trang_thai`, `ngay_cap_nhat` (UTF-8 No-BOM, không bọc dấu nháy kép).\n"
    )
    write_if_missing(vault_dir / "AGENTS.md", agents_md)
    write_if_missing(vault_dir / "CLAUDE.md", agents_md)

    index_md = (
        "---\n"
        "linh_vuc: ops\n"
        "do_uu_tien: cao\n"
        "trang_thai: active\n"
        f"ngay_cap_nhat: {today}\n"
        "---\n\n"
        "# Wiki Index\n\n"
        "## Chủ đề chính\n"
        "_(AI tự cập nhật khi ingest tài liệu từ `Raw/`)_\n\n"
        "## Trang vận hành\n"
        "- [[log]] — nhật ký thay đổi\n"
        "- [[_open-questions]] — câu hỏi mở / mâu thuẫn\n"
        "- [[_session-handoff]] — bàn giao phiên\n"
    )
    write_if_missing(vault_dir / "wiki" / "_index.md", index_md)
    write_if_missing(vault_dir / "wiki" / "index.md", index_md)

    log_md = (
        "---\n"
        "linh_vuc: ops\n"
        "do_uu_tien: cao\n"
        "trang_thai: active\n"
        f"ngay_cap_nhat: {today}\n"
        "---\n\n"
        "# Wiki Log\n\n"
        f"## [{today}] init | Khởi tạo Second Brain Vault\n"
        "- Thiết lập cấu trúc 3 lớp (`Raw/`, `wiki/`, `AGENTS.md`).\n"
    )
    write_if_missing(vault_dir / "wiki" / "log.md", log_md)

    open_q = (
        "---\n"
        "linh_vuc: ops\n"
        "do_uu_tien: trung_binh\n"
        "trang_thai: active\n"
        f"ngay_cap_nhat: {today}\n"
        "---\n\n"
        "# Open Questions\n\n"
        "_(Các câu hỏi mở hoặc mâu thuẫn giữa các nguồn sẽ được ghi tại đây)_\n"
    )
    write_if_missing(vault_dir / "wiki" / "_open-questions.md", open_q)

    handoff = (
        "---\n"
        "linh_vuc: ops\n"
        "do_uu_tien: trung_binh\n"
        "trang_thai: active\n"
        f"ngay_cap_nhat: {today}\n"
        "---\n\n"
        "# Session Handoff\n\n"
        "- **Status**: clear\n"
    )
    write_if_missing(vault_dir / "wiki" / "_session-handoff.md", handoff)

    tpl_wiki = (
        "---\n"
        "linh_vuc: khac\n"
        "do_uu_tien: trung_binh\n"
        "trang_thai: active\n"
        f"ngay_cap_nhat: {today}\n"
        "---\n\n"
        "# {{Tiêu đề}}\n\n"
        "## Tóm tắt\n\n"
        "## Nội dung chính\n\n"
        "## Liên kết\n\n"
        "## Nguồn\n"
        "- [[Raw/...]]\n"
    )
    write_if_missing(vault_dir / "templates" / "wiki-page.md", tpl_wiki)

    for mode in ["daily", "weekly", "monthly"]:
        ps1 = (
            "$ErrorActionPreference = \"Stop\"\n"
            "$vaultRoot = Split-Path -Parent $PSScriptRoot\n"
            "Set-Location -LiteralPath $vaultRoot\n"
            f"python .\\ops\\wiki_ops.py {mode}\n"
        )
        write_if_missing(vault_dir / "ops" / f"run-{mode}.ps1", ps1)

    res_wiki_ops = Path(__file__).resolve().parent.parent / "resources" / "wiki_ops.py"
    if res_wiki_ops.exists() and not (vault_dir / "ops" / "wiki_ops.py").exists():
        shutil.copy2(res_wiki_ops, vault_dir / "ops" / "wiki_ops.py")


def copy_sources_to_raw(source_dir: Path, raw_dir: Path, overwrite: bool) -> int:
    """Copy source files into Raw/ preserving relative paths without mutating originals."""
    if source_dir.resolve() == raw_dir.resolve():
        return 0
    copied = 0
    for item in source_dir.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(source_dir)
        dest = raw_dir / rel
        if dest.exists() and not overwrite:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
        copied += 1
    return copied


def convert_with_markitdown(file_path: Path, md_path: Path, converter, timeout_sec: int) -> Tuple[bool, str]:
    """Convert a single document to Markdown using MarkItDown with timeout protection."""
    def _run() -> str:
        return converter.convert(str(file_path)).text_content or ""

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            raw_text = pool.submit(_run).result(timeout=timeout_sec)
        cleaned = clean_markdown(raw_text)
        if not cleaned.strip():
            return False, "empty output"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(cleaned, encoding="utf-8", newline="\n")
        return True, f"ok ({len(cleaned)} chars)"
    except concurrent.futures.TimeoutError:
        return False, f"timeout > {timeout_sec}s"
    except Exception as exc:
        return False, str(exc)


def process_raw_directory(raw_dir: Path, overwrite: bool, timeout_sec: int) -> Dict[str, object]:
    """Convert documents in Raw/ to .md and collect images needing AI Vision extraction."""
    from markitdown import MarkItDown

    converter = MarkItDown()
    converted: List[Dict[str, str]] = []
    skipped_existing: List[str] = []
    failed: List[Dict[str, str]] = []
    pending_images: List[Dict[str, str]] = []
    existing_md: List[str] = []

    for item in sorted(raw_dir.rglob("*")):
        if not item.is_file():
            continue
        ext = item.suffix.lower()
        rel_str = item.relative_to(raw_dir).as_posix()

        if ext == ".md":
            existing_md.append(rel_str)
            continue

        target_md = item.with_suffix(".md")
        if ext in IMAGE_EXTS:
            if not target_md.exists() or overwrite:
                pending_images.append({
                    "image": rel_str,
                    "target_md": target_md.relative_to(raw_dir).as_posix(),
                })
            else:
                skipped_existing.append(rel_str)
            continue

        if ext in TEXT_EXTS:
            if target_md.exists() and not overwrite:
                skipped_existing.append(rel_str)
                continue
            text = item.read_text(encoding="utf-8", errors="replace")
            target_md.write_text(clean_markdown(text), encoding="utf-8", newline="\n")
            converted.append({"source": rel_str, "md": target_md.relative_to(raw_dir).as_posix(), "engine": "text"})
            continue

        if ext in MARKITDOWN_EXTS:
            if target_md.exists() and not overwrite:
                skipped_existing.append(rel_str)
                continue
            ok, msg = convert_with_markitdown(item, target_md, converter, timeout_sec)
            if ok:
                converted.append({"source": rel_str, "md": target_md.relative_to(raw_dir).as_posix(), "engine": "markitdown", "detail": msg})
            else:
                failed.append({"source": rel_str, "error": msg})

    return {
        "existing_md_count": len(existing_md),
        "converted_count": len(converted),
        "skipped_existing_count": len(skipped_existing),
        "failed_count": len(failed),
        "pending_images_count": len(pending_images),
        "converted": converted,
        "failed": failed,
        "pending_images": pending_images,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Second Brain Vault from mixed source directory")
    parser.add_argument("--source", required=True, help="Source directory containing raw documents/images")
    parser.add_argument("--vault", required=True, help="Target Obsidian Second Brain vault directory")
    parser.add_argument("--install-markitdown", action="store_true", help="Auto-install markitdown[all] if missing")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing converted .md files in Raw/")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC, help="Per-file MarkItDown timeout in seconds")
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    vault_dir = Path(args.vault).resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        print(json.dumps({"error": f"Source directory not found: {source_dir}"}, ensure_ascii=False))
        return 1

    ok_pkg, pkg_status = ensure_markitdown(args.install_markitdown)
    if not ok_pkg:
        print(json.dumps({"error": pkg_status}, ensure_ascii=False))
        return 1

    today = dt.date.today().strftime("%Y-%m-%d")
    scaffold_vault(vault_dir, today)
    raw_dir = vault_dir / "Raw"
    copied = copy_sources_to_raw(source_dir, raw_dir, overwrite=args.overwrite)
    report = process_raw_directory(raw_dir, overwrite=args.overwrite, timeout_sec=args.timeout)

    output = {
        "vault": str(vault_dir),
        "source": str(source_dir),
        "markitdown_status": pkg_status,
        "copied_to_raw": copied,
        **report,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if report["failed_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
