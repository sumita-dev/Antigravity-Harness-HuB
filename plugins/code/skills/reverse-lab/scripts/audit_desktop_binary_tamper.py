#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plugins/code/skills/reverse-lab/scripts/audit_desktop_binary_tamper.py

Scaffolding Script Thẩm Định An Toàn & Chống Kỹ Thuật Dịch Ngược (Dune Invariant).
Quét mã nguồn và bundle ứng dụng Desktop để phát hiện:
1. Chuỗi nhạy cảm, Hardcoded Tokens, Private Keys, JWT.
2. Cờ Debug (Debug Flags) bị bỏ quên: DEBUG=True, --inspect, remote-debugging-port.
3. Lệnh can thiệp bộ nhớ nhạy cảm (Insecure Memory Calls): VirtualProtect, WriteProcessMemory, ptrace.

CLI:
  python audit_desktop_binary_tamper.py [FILES...] [--dir PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class TamperFinding:
    file_path: str
    line_number: int
    category: str  # "SENSITIVE_STRING", "DEBUG_FLAG", "INSECURE_MEMORY"
    severity: str  # "ERROR" hoặc "WARN"
    code: str
    message: str
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Patterns phát hiện Tokens & Chuỗi nhạy cảm
SENSITIVE_PATTERNS = [
    (
        re.compile(r"-----BEGIN\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY-----"),
        "ERR_HARDCODED_PRIVATE_KEY",
        "ERROR",
        "Phát hiện Private Key nhúng trực tiếp trong mã nguồn/binary.",
    ),
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "ERR_HARDCODED_AWS_KEY",
        "ERROR",
        "Phát hiện AWS Access Key ID trong mã nguồn.",
    ),
    (
        re.compile(r"\bghp_[0-9a-zA-Z]{36}\b|\bgithub_pat_[0-9a-zA-Z_]{50,}\b"),
        "ERR_HARDCODED_GITHUB_TOKEN",
        "ERROR",
        "Phát hiện GitHub Personal Access Token trong mã nguồn.",
    ),
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"),
        "ERR_HARDCODED_JWT_TOKEN",
        "ERROR",
        "Phát hiện Hardcoded JWT Token.",
    ),
    (
        re.compile(r"\b(?:api_key|apiKey|secret_key|master_key)\s*[:=]\s*['\"][a-zA-Z0-9_-]{16,}['\"]"),
        "ERR_HARDCODED_SECRET_KEY",
        "ERROR",
        "Phát hiện secret/API key gán tĩnh trong mã nguồn.",
    ),
]

# Patterns phát hiện Debug Flags
DEBUG_PATTERNS = [
    (
        re.compile(r"(?i)\bDEBUG\s*=\s*True\b|\bdebug\s*:\s*true\b"),
        "WARN_DEBUG_ENABLED",
        "WARN",
        "Cờ DEBUG được bật trong cấu hình xuất xưởng.",
    ),
    (
        re.compile(r"--inspect(?:-brk)?|--remote-debugging-port=\d+"),
        "ERR_DEBUG_PORT_EXPOSED",
        "ERROR",
        "Phát hiện cổng debug Node.js / V8 mở ra ngoài (--inspect / remote-debugging-port).",
    ),
    (
        re.compile(r"ELECTRON_ENABLE_LOGGING"),
        "WARN_ELECTRON_LOGGING",
        "WARN",
        "Biến môi trường ELECTRON_ENABLE_LOGGING có thể rò rỉ thông tin nội bộ.",
    ),
    (
        re.compile(r"(?i)\b(?:DisableAntiDebug|SkipSignatureVerification)\s*=\s*True\b"),
        "ERR_BYPASS_PROTECTION",
        "ERROR",
        "Phát hiện cơ chế tắt bảo vệ Anti-Debug hoặc bỏ qua kiểm tra chữ ký số.",
    ),
]

# Patterns phát hiện Insecure Memory Calls
MEMORY_PATTERNS = [
    (
        re.compile(r"\b(?:VirtualProtect|VirtualAllocEx|WriteProcessMemory|CreateRemoteThread)\b"),
        "ERR_INSECURE_MEMORY_CALL",
        "ERROR",
        "Phát hiện hàm Win32 can thiệp bộ nhớ nhạy cảm (thường dùng trong memory patch/hook injection).",
    ),
    (
        re.compile(r"\bptrace\s*\(\s*PTRACE_TRACEME\b|\bmprotect\b"),
        "WARN_NATIVE_PTRACE_CALL",
        "WARN",
        "Phát hiện lệnh ptrace/mprotect native cần được mã hóa hoặc bảo vệ chống bypass.",
    ),
    (
        re.compile(r"\bctypes\.windll\.kernel32\.VirtualProtect\b|\bctypes\.memmove\b"),
        "WARN_PYTHON_MEMORY_PATCH",
        "WARN",
        "Phát hiện can thiệp bộ nhớ mức thấp thông qua Python ctypes.",
    ),
]


def audit_tamper_content(content: str, filename: str = "binary_source.py") -> List[TamperFinding]:
    """Phân tích nội dung nguồn hoặc file cấu hình."""
    findings: List[TamperFinding] = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, 1):
        clean_line = line.strip()
        if not clean_line or clean_line.startswith(("//", "#", "/*")):
            # Bỏ qua dòng comment đơn giản nếu không chứa private key
            if "PRIVATE KEY" not in clean_line:
                continue

        # 1. Quét chuỗi nhạy cảm & Hardcoded Tokens
        for regex, code, severity, msg in SENSITIVE_PATTERNS:
            if regex.search(line):
                findings.append(
                    TamperFinding(
                        file_path=filename,
                        line_number=idx,
                        category="SENSITIVE_STRING",
                        severity=severity,
                        code=code,
                        message=msg,
                        snippet=clean_line,
                    )
                )

        # 2. Quét Debug Flags
        for regex, code, severity, msg in DEBUG_PATTERNS:
            if regex.search(line):
                findings.append(
                    TamperFinding(
                        file_path=filename,
                        line_number=idx,
                        category="DEBUG_FLAG",
                        severity=severity,
                        code=code,
                        message=msg,
                        snippet=clean_line,
                    )
                )

        # 3. Quét Insecure Memory Calls
        for regex, code, severity, msg in MEMORY_PATTERNS:
            if regex.search(line):
                findings.append(
                    TamperFinding(
                        file_path=filename,
                        line_number=idx,
                        category="INSECURE_MEMORY",
                        severity=severity,
                        code=code,
                        message=msg,
                        snippet=clean_line,
                    )
                )

    return findings


def audit_tamper_file(path: Path) -> List[TamperFinding]:
    """Kiểm tra một file cụ thể."""
    if not path.is_file():
        return []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [
            TamperFinding(
                file_path=str(path),
                line_number=1,
                category="FILE_ERROR",
                severity="ERROR",
                code="ERR_READ_FILE",
                message=f"Không thể đọc file: {exc}",
            )
        ]

    return audit_tamper_content(content, filename=str(path))


def audit_tamper(paths: Sequence[Path]) -> Dict[str, Any]:
    """Kiểm tra danh sách các file hoặc thư mục."""
    all_findings: List[TamperFinding] = []
    files_checked = 0

    valid_extensions = {".py", ".js", ".ts", ".json", ".cs", ".cpp", ".c", ".h", ".go", ".rs", ".yml", ".yaml"}

    for p in paths:
        if p.is_file():
            findings = audit_tamper_file(p)
            all_findings.extend(findings)
            files_checked += 1
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in valid_extensions:
                    findings = audit_tamper_file(f)
                    all_findings.extend(findings)
                    files_checked += 1

    unresolved_errors = [f for f in all_findings if f.severity == "ERROR"]

    return {
        "files_checked": files_checked,
        "finding_count": len(all_findings),
        "errors": len(unresolved_errors),
        "warnings": len(all_findings) - len(unresolved_errors),
        "is_safe": len(unresolved_errors) == 0,
        "findings": [f.to_dict() for f in all_findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Desktop Binary Tamper & Anti-Crack Auditor")
    parser.add_argument("files", nargs="*", help="Danh sách file nguồn/binary cần thẩm định")
    parser.add_argument("--dir", type=str, default=None, help="Thư mục chứa mã nguồn/bundle ứng dụng")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON")

    args = parser.parse_args()

    target_paths: List[Path] = []
    if args.dir:
        target_paths.append(Path(args.dir).resolve())
    for f in args.files:
        target_paths.append(Path(f).resolve())

    if not target_paths:
        print("Không có tệp hoặc thư mục nào được chỉ định để kiểm tra.")
        return 0

    result = audit_tamper(target_paths)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print("ANTIGRAVITY DESKTOP BINARY TAMPER & ANTI-CRACK AUDITOR")
        print("=" * 65)
        print(f"- Số file đã kiểm tra: {result['files_checked']}")
        print(f"- Trạng thái: {'🟢 AN TOÀN (CLEAN)' if result['is_safe'] else '🔴 PHÁT HIỆN LỖ HỔNG (VULNERABLE)'}")
        print(f"- Tổng số phát hiện: {result['finding_count']} (Lỗi: {result['errors']}, Cảnh báo: {result['warnings']})")

        for f in result["findings"]:
            icon = "🔴" if f["severity"] == "ERROR" else "🟡"
            print(f"\n  {icon} [{f['code']}] {f['file_path']}:{f['line_number']}")
            print(f"     Danh mục: {f['category']}")
            print(f"     Thông điệp: {f['message']}")
            if f["snippet"]:
                print(f"     Mã nguồn: {f['snippet']}")
        print("=" * 65)

    return 0 if result["is_safe"] else 1


if __name__ == "__main__":
    sys.exit(main())
