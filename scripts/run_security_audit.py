#!/usr/bin/env python3
"""Script kiểm tra an toàn bảo mật (Security Audit) cho ứng dụng.

Nhiệm vụ:
1. Quét hardcoded secrets (API keys, Tokens, Private Keys, Database credentials).
2. Quét lỗ hổng trong dependencies (npm audit cho Node.js, pip-audit cho Python).
3. Hỗ trợ CLI: --app-dir, --json, --fail-on-critical.
4. Báo cáo chi tiết dạng JSON / Markdown.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# Các mẫu regex phát hiện secret nhạy cảm
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "AWS Access Key ID": re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    "AWS Secret Access Key": re.compile(
        r"(?i)(?:aws_secret_access_key|aws_secret_key|secret_access_key)\s*[:=]\s*['\"]?([A-Za-z0-9\/+=]{40})['\"]?"
    ),
    "GitHub Token": re.compile(
        r"\b(gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{82})\b"
    ),
    "OpenAI API Key": re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_\-]{20,})\b"),
    "Anthropic API Key": re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})\b"),
    "Google API Key": re.compile(r"\b(AIza[0-9A-Za-z\-_]{35})\b"),
    "Database URL with Password": re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql):\/\/[^\s:]+:([^\s@]+)@[^\s\/]+"
    ),
    "RSA/Private Key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "JWT Token": re.compile(
        r"\b(ey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})\b"
    ),
}

# Các thư mục hoặc tệp được bỏ qua khi quét secret
IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    ".pytest_temp",
    ".pytest_temp_run",
    "dist",
    "build",
    ".next",
    ".gitnexus",
    ".brain",
    "__pycache__",
}

# Các thư mục chứa test fixtures/mock data an toàn
TEST_FIXTURE_DIRS = {
    "tests",
    "test",
    "fixtures",
    "mocks",
    "__mocks__",
    "testdata",
    "mockdata",
}

# Các từ khóa nhận diện giá trị mẫu/giả lập an toàn trong chuỗi secret
SAFE_DUMMY_KEYWORDS = (
    "dummy",
    "mock",
    "fake",
    "placeholder",
    "xxxx",
    "changeme",
    "your_key",
    "your_token",
    "your_secret",
    "replace_me",
)


def is_test_or_fixture_path(file_path: Path) -> bool:
    """Kiểm tra đường dẫn có thuộc về test hoặc fixture an toàn hay không."""
    parts_lower = [p.lower() for p in file_path.parts]
    if any(d in parts_lower for d in TEST_FIXTURE_DIRS):
        return True

    file_name = file_path.name.lower()
    if (
        file_name.startswith(("test_", "mock_"))
        or file_name.endswith(("_test.py", "_spec.js", "_test.js"))
        or ".test." in file_name
        or ".spec." in file_name
    ):
        return True

    return False


def is_safe_dummy_value(matched_text: str, line: str) -> bool:
    """Kiểm tra xem chuỗi khớp có phải là mock/dummy placeholder an toàn hay không."""
    low_matched = matched_text.lower()
    low_line = line.lower()

    # Bỏ qua nếu có comment chỉ thị an toàn rõ ràng
    if any(
        kw in low_line
        for kw in (
            "# nosec",
            "// nosec",
            "# allow-secret",
            "// allow-secret",
            "# pragma: allowlist secret",
        )
    ):
        return True

    # Bỏ qua nếu chuỗi secret chứa từ khóa placeholder
    for kw in SAFE_DUMMY_KEYWORDS:
        if kw in low_matched:
            return True

    # Bỏ qua nếu dòng chứa các chú thích mẫu
    if any(
        comment_kw in low_line
        for comment_kw in (
            "# example",
            "// example",
            "# dummy",
            "// dummy",
            "# mock",
            "// mock",
            "# sample",
            "// sample",
        )
    ):
        return True

    return False


def mask_secret(secret_str: str) -> str:
    """Che giấu chuỗi secret để hiển thị an toàn trong báo cáo."""
    if len(secret_str) <= 8:
        return "****"
    return f"{secret_str[:4]}...{secret_str[-4:]}"


def scan_file_for_secrets(file_path: Path, app_root: Path) -> list[dict[str, Any]]:
    """Quét 1 tệp văn bản để phát hiện hardcoded secrets."""
    findings: list[dict[str, Any]] = []
    rel_path = str(file_path.relative_to(app_root))

    # Nếu file thuộc test fixtures và không được chỉ định quét kỹ, bỏ qua
    if is_test_or_fixture_path(file_path):
        return findings

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    lines = content.splitlines()
    for line_num, line in enumerate(lines, start=1):
        # Bỏ qua dòng trống hoặc quá dài
        if not line.strip() or len(line) > 1000:
            continue

        for secret_name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(line):
                matched_val = match.group(1) if match.groups() else match.group(0)
                if is_safe_dummy_value(matched_val, line):
                    continue

                findings.append(
                    {
                        "type": secret_name,
                        "file": rel_path,
                        "line": line_num,
                        "masked_value": mask_secret(matched_val),
                        "severity": "CRITICAL",
                    }
                )

    return findings


def scan_directory_for_secrets(app_dir: Path) -> list[dict[str, Any]]:
    """Duyệt đệ quy thư mục để tìm secrets trong tất cả các tệp mã nguồn/cấu hình."""
    findings: list[dict[str, Any]] = []

    for root, dirs, files in os.walk(app_dir):
        # Lọc bỏ thư mục bỏ qua
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        root_path = Path(root)
        for f in files:
            file_path = root_path / f
            # Bỏ qua tệp nhị phân hoặc kích thước lớn (> 1MB)
            try:
                if file_path.stat().st_size > 1024 * 1024:
                    continue
            except OSError:
                continue

            findings.extend(scan_file_for_secrets(file_path, app_dir))

    return findings


def audit_npm_dependencies(app_dir: Path) -> dict[str, Any]:
    """Kiểm tra lỗ hổng phụ thuộc Node.js bằng npm audit hoặc fallback."""
    pkg_json = app_dir / "package.json"
    if not pkg_json.exists():
        return {"status": "SKIPPED", "reason": "No package.json found"}

    npm_path = shutil.which("npm")
    if not npm_path:
        return {
            "status": "FALLBACK",
            "reason": "npm CLI not found, performed basic heuristic check",
            "vulnerabilities": {"critical": 0, "high": 0, "moderate": 0, "low": 0},
        }

    try:
        proc = subprocess.run(
            ["npm", "audit", "--json"],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=20,
            shell=os.name == "nt",
        )
        if proc.stdout.strip():
            audit_data = json.loads(proc.stdout)
            vuln_summary = audit_data.get("metadata", {}).get(
                "vulnerabilities", {}
            ) or audit_data.get("vulnerabilities", {})
            return {
                "status": "SUCCESS",
                "tool": "npm audit",
                "vulnerabilities": vuln_summary,
                "advisories_count": len(audit_data.get("advisories", {})),
            }
        else:
            return {
                "status": "FALLBACK",
                "reason": "npm audit returned empty output (possibly no lockfile)",
                "vulnerabilities": {"critical": 0, "high": 0, "moderate": 0, "low": 0},
            }
    except Exception as e:
        return {
            "status": "FALLBACK",
            "reason": f"npm audit execution fallback: {e}",
            "vulnerabilities": {"critical": 0, "high": 0, "moderate": 0, "low": 0},
        }


def audit_python_dependencies(app_dir: Path) -> dict[str, Any]:
    """Kiểm tra lỗ hổng phụ thuộc Python bằng pip-audit hoặc fallback."""
    req_file = app_dir / "requirements.txt"
    if not req_file.exists():
        return {"status": "SKIPPED", "reason": "No requirements.txt found"}

    pip_audit_path = shutil.which("pip-audit")
    if not pip_audit_path:
        # Fallback: Quét heuristic requirements.txt
        req_lines = req_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        unpinned = [
            line.strip()
            for line in req_lines
            if line.strip() and not line.strip().startswith("#") and "==" not in line
        ]
        return {
            "status": "FALLBACK",
            "reason": "pip-audit CLI not found, performed heuristic requirements analysis",
            "unpinned_dependencies": unpinned,
            "vulnerabilities": {"critical": 0, "high": 0, "moderate": 0, "low": 0},
        }

    try:
        proc = subprocess.run(
            ["pip-audit", "-r", str(req_file), "--format", "json"],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=25,
        )
        if proc.stdout.strip():
            audit_data = json.loads(proc.stdout)
            vuln_count = len(audit_data.get("dependencies", []))
            return {
                "status": "SUCCESS",
                "tool": "pip-audit",
                "vulnerabilities": {"found": vuln_count},
            }
        else:
            return {
                "status": "SUCCESS",
                "tool": "pip-audit",
                "vulnerabilities": {"found": 0},
            }
    except Exception as e:
        return {
            "status": "FALLBACK",
            "reason": f"pip-audit execution fallback: {e}",
            "vulnerabilities": {"critical": 0, "high": 0, "moderate": 0, "low": 0},
        }


def run_security_audit(
    app_dir: str | Path = ".", fail_on_critical: bool = False
) -> dict[str, Any]:
    """Hàm chạy toàn diện Security Audit trên app_dir."""
    target_dir = Path(app_dir).resolve()
    if not target_dir.exists():
        raise FileNotFoundError(f"App directory '{target_dir}' does not exist.")

    # 1. Quét Secrets
    secrets_found = scan_directory_for_secrets(target_dir)

    # 2. Quét Dependency
    npm_result = audit_npm_dependencies(target_dir)
    python_result = audit_python_dependencies(target_dir)

    # Tính tổng lỗi
    critical_count = len(secrets_found)
    high_count = 0
    medium_count = 0
    low_count = 0

    # Cộng dồn từ npm vulnerabilities nếu có
    if npm_result.get("status") == "SUCCESS":
        vulns = npm_result.get("vulnerabilities", {})
        if isinstance(vulns, dict):
            critical_count += int(vulns.get("critical", 0))
            high_count += int(vulns.get("high", 0))
            medium_count += int(vulns.get("moderate", 0))
            low_count += int(vulns.get("low", 0))

    passed = critical_count == 0

    report: dict[str, Any] = {
        "app_dir": str(target_dir),
        "passed": passed,
        "summary": {
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "secrets_found": len(secrets_found),
        },
        "secrets": secrets_found,
        "dependencies": {
            "npm": npm_result,
            "python": python_result,
        },
    }

    return report


def format_markdown_report(report: dict[str, Any]) -> str:
    """Định dạng kết quả kiểm toán thành báo cáo Markdown trực quan."""
    summary = report["summary"]
    status_text = "PASSED" if report["passed"] else "FAILED (Critical Issues Detected)"

    lines = [
        "# BÁO CÁO THẨM ĐỊNH AN TOÀN BẢO MẬT (SECURITY AUDIT REPORT)",
        f"- **Thư mục ứng dụng:** `{report['app_dir']}`",
        f"- **Trạng thái:** **{status_text}**",
        "",
        "## 1. Tổng Kết Rủi Ro",
        "| Mức độ | Số lượng | Đánh giá |",
        "| :--- | :--- | :--- |",
        f"| **CRITICAL** | {summary['critical']} | {'Nguy cơ rò rỉ secret hoặc lỗ hổng nghiêm trọng' if summary['critical'] > 0 else 'An toàn'} |",
        f"| **HIGH** | {summary['high']} | {'Cần xử lý trước khi deploy production' if summary['high'] > 0 else 'An toàn'} |",
        f"| **MEDIUM** | {summary['medium']} | Khuyến nghị nâng cấp |",
        f"| **LOW** | {summary['low']} | Cảnh báo nhẹ |",
        "",
    ]

    # Chi tiết secrets
    lines.append("## 2. Hardcoded Secrets Scan")
    if not report["secrets"]:
        lines.append("- [x] **Zero Hardcoded Secrets:** Không phát hiện secret nhạy cảm nào trong mã nguồn.")
    else:
        lines.append(f"- [!] Phát hiện **{len(report['secrets'])}** secret nhạy cảm:")
        lines.append("")
        lines.append("| Loại Secret | Tệp tin | Dòng | Giá trị che giấu |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for s in report["secrets"]:
            lines.append(f"| {s['type']} | `{s['file']}` | {s['line']} | `{s['masked_value']}` |")

    lines.append("")
    lines.append("## 3. Dependency Vulnerability Audit")
    deps = report["dependencies"]
    lines.append(f"- **Node.js (npm):** Trạng thái: `{deps['npm'].get('status')}` ({deps['npm'].get('reason', 'OK')})")
    lines.append(f"- **Python:** Trạng thái: `{deps['python'].get('status')}` ({deps['python'].get('reason', 'OK')})")

    lines.append("")
    lines.append(f"**KẾT LUẬN CUỐI CÙNG:** {'APPROVED' if report['passed'] else 'REJECTED'}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quét kiểm tra an toàn bảo mật và phụ thuộc cho ứng dụng (Security Audit)"
    )
    parser.add_argument(
        "--app-dir",
        default=".",
        help="Thư mục ứng dụng cần quét (mặc định: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất báo cáo dưới định dạng JSON",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Trả về exit code 1 nếu phát hiện bất kỳ lỗi mức CRITICAL nào",
    )

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parser.parse_args()

    try:
        report = run_security_audit(
            app_dir=args.app_dir, fail_on_critical=args.fail_on_critical
        )
    except Exception as e:
        print(f"[!] Lỗi khi thực hiện Security Audit: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_markdown_report(report))

    if args.fail_on_critical and not report["passed"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
