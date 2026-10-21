#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/safe_com_runner.py

Chốt chặn cấp độ Script / Thực thi:
Wrapper an toàn cho các thao tác COM Automation (Microsoft Word, Microsoft Excel) trên Windows.
- Ngăn chặn triệt để tình trạng treo vô hạn do modal dialog ngầm / PDF reflow.
- Áp dụng Hard Timeout cứng (30s - 60s / file).
- Tự động dọn dẹp tiến trình WINWORD.EXE / EXCEL.EXE mồ côi nếu xảy ra sự cố.
- CẤM TUYỆT ĐỐI dùng Word COM để mở trực tiếp file PDF (nguyên nhân gây deadlock modal).
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Tuple, Optional


DEFAULT_COM_TIMEOUT = 30.0  # seconds


def cleanup_com_processes(app_name: str = "all") -> None:
    """Dọn dẹp triệt để các tiến trình Office mồ côi bị treo."""
    if os.name != "nt":
        return

    targets = []
    if app_name in ("word", "all"):
        targets.append("WINWORD.EXE")
    if app_name in ("excel", "all"):
        targets.append("EXCEL.EXE")

    for proc in targets:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except Exception:
            pass


def _worker_convert_doc_to_docx(input_doc: str, output_docx: str) -> None:
    """Chạy trong sub-process độc lập để cô lập sự cố COM của Word."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # wdAlertsNone

        doc = word.Documents.Open(
            str(Path(input_doc).resolve()),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False
        )
        # 16 = wdFormatXMLDocument (.docx)
        doc.SaveAs2(str(Path(output_docx).resolve()), FileFormat=16)
        doc.Close(False)
    finally:
        if word is not None:
            try:
                word.Quit(0)
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _worker_convert_xls_to_xlsx(input_xls: str, output_xlsx: str) -> None:
    """Chạy trong sub-process độc lập để cô lập sự cố COM của Excel."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        wb = excel.Workbooks.Open(
            str(Path(input_xls).resolve()),
            ReadOnly=True,
            UpdateLinks=False
        )
        # 51 = xlOpenXMLWorkbook (.xlsx)
        wb.SaveAs(str(Path(output_xlsx).resolve()), FileFormat=51)
        wb.Close(False)
    finally:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def safe_convert_doc(
    input_file: Path,
    output_file: Optional[Path] = None,
    timeout_sec: float = DEFAULT_COM_TIMEOUT
) -> Tuple[bool, str]:
    """Chuyển đổi file .doc cũ sang .docx an toàn với process isolation & hard timeout."""
    input_path = Path(input_file).resolve()
    if input_path.suffix.lower() == ".pdf":
        return False, "CẤM: Không được sử dụng Word COM để mở PDF (gây deadlock modal reflow)!"

    if not input_path.exists():
        return False, f"File không tồn tại: {input_path}"

    out_path = Path(output_file).resolve() if output_file else input_path.with_suffix(".docx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-c",
        f"from scripts.safe_com_runner import _worker_convert_doc_to_docx; _worker_convert_doc_to_docx(r'{input_path}', r'{out_path}')"
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            _, stderr = proc.communicate(timeout=timeout_sec)
            if proc.returncode == 0 and out_path.exists():
                return True, str(out_path)
            return False, f"Lỗi chuyển đổi doc: {stderr.strip()}"
        except subprocess.TimeoutExpired:
            proc.kill()
            cleanup_com_processes("word")
            return False, f"TIMEOUT: Quá thời gian {timeout_sec}s khi mở {input_path.name}. Đã tự động diệt WINWORD.EXE"
    except Exception as exc:
        cleanup_com_processes("word")
        return False, f"Lỗi thực thi COM: {exc}"


def safe_convert_xls(
    input_file: Path,
    output_file: Optional[Path] = None,
    timeout_sec: float = DEFAULT_COM_TIMEOUT
) -> Tuple[bool, str]:
    """Chuyển đổi file .xls cũ sang .xlsx an toàn với process isolation & hard timeout."""
    input_path = Path(input_file).resolve()
    if not input_path.exists():
        return False, f"File không tồn tại: {input_path}"

    out_path = Path(output_file).resolve() if output_file else input_path.with_suffix(".xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-c",
        f"from scripts.safe_com_runner import _worker_convert_xls_to_xlsx; _worker_convert_xls_to_xlsx(r'{input_path}', r'{out_path}')"
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            _, stderr = proc.communicate(timeout=timeout_sec)
            if proc.returncode == 0 and out_path.exists():
                return True, str(out_path)
            return False, f"Lỗi chuyển đổi xls: {stderr.strip()}"
        except subprocess.TimeoutExpired:
            proc.kill()
            cleanup_com_processes("excel")
            return False, f"TIMEOUT: Quá thời gian {timeout_sec}s khi mở {input_path.name}. Đã tự động diệt EXCEL.EXE"
    except Exception as exc:
        cleanup_com_processes("excel")
        return False, f"Lỗi thực thi COM: {exc}"


def main():
    parser = argparse.ArgumentParser(
        description="Safe COM Runner: Wrapper an toàn có Hard Timeout cho Word/Excel COM"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doc to docx
    p_doc = subparsers.add_parser("doc2docx", help="Chuyển đổi an toàn .doc sang .docx")
    p_doc.add_argument("input", help="Đường dẫn file .doc")
    p_doc.add_argument("-o", "--output", help="Đường dẫn file .docx đầu ra")
    p_doc.add_argument("-t", "--timeout", type=float, default=DEFAULT_COM_TIMEOUT, help="Timeout tính bằng giây")

    # xls to xlsx
    p_xls = subparsers.add_parser("xls2xlsx", help="Chuyển đổi an toàn .xls sang .xlsx")
    p_xls.add_argument("input", help="Đường dẫn file .xls")
    p_xls.add_argument("-o", "--output", help="Đường dẫn file .xlsx đầu ra")
    p_xls.add_argument("-t", "--timeout", type=float, default=DEFAULT_COM_TIMEOUT, help="Timeout tính bằng giây")

    # cleanup
    p_clean = subparsers.add_parser("cleanup", help="Dọn dẹp các tiến trình WINWORD / EXCEL bị mồ côi")
    p_clean.add_argument("--app", choices=["word", "excel", "all"], default="all")

    args = parser.parse_args()

    if args.command == "cleanup":
        cleanup_com_processes(args.app)
        print(f"[OK] Đã dọn dẹp tiến trình COM: {args.app}")
        sys.exit(0)
    elif args.command == "doc2docx":
        ok, res = safe_convert_doc(Path(args.input), Path(args.output) if args.output else None, args.timeout)
        if ok:
            print(f"[SUCCESS] {res}")
            sys.exit(0)
        else:
            print(f"[FAILED] {res}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "xls2xlsx":
        ok, res = safe_convert_xls(Path(args.input), Path(args.output) if args.output else None, args.timeout)
        if ok:
            print(f"[SUCCESS] {res}")
            sys.exit(0)
        else:
            print(f"[FAILED] {res}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
