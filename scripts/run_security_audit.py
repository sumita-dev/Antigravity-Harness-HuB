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
    # Suppress only explicit token prefixes or deliberate inline allowlisting.
    if re.search(r"(?:#|//)\s*(?:nosec|allow-secret|pragma: allowlist secret)\b", line, re.I):
        return True
    return bool(re.fullmatch(
        r"(?:sk-(?:proj-|ant-)?|gh[pousr]_)?(?:dummy|fake|mock|placeholder|xxxx|changeme|your_key|your_token|your_secret|replace_me)[A-Za-z0-9_-]*",
        matched_text, re.I,
    ))


def mask_secret(secret_str: str) -> str:
    """Che giấu chuỗi secret để hiển thị an toàn trong báo cáo."""
    if len(secret_str) <= 8:
        return "****"
    return f"{secret_str[:4]}...{secret_str[-4:]}"


def scan_file_for_secrets(file_path: Path, app_root: Path) -> list[dict[str, Any]]:
    """Quét 1 tệp văn bản để phát hiện hardcoded secrets."""
    findings: list[dict[str, Any]] = []
    rel_path = str(file_path.relative_to(app_root))

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        raise

    lines = content.splitlines()
    for line_num, line in enumerate(lines, start=1):
        # Bỏ qua dòng trống hoặc quá dài
        if not line.strip():
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

    def fail_walk(error: OSError) -> None:
        raise error

    for root, dirs, files in os.walk(app_dir, onerror=fail_walk):
        # Lọc bỏ thư mục bỏ qua
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        root_path = Path(root)
        for f in files:
            file_path = root_path / f
            # Bỏ qua tệp nhị phân hoặc kích thước lớn (> 1MB)
            try:
                if file_path.stat().st_size > 1024 * 1024:
                    raise OSError(f"Secret scan size limit exceeded: {file_path}")
            except OSError:
                raise

            findings.extend(scan_file_for_secrets(file_path, app_dir))

    return findings


def _scan_dependencies(app_dir: Path, ecosystem: str) -> dict[str, Any]:
    """Accept only validated scanner results; exit 1 can mean findings."""
    npm = ecosystem == "npm"
    manifest = app_dir / ("package.json" if npm else "requirements.txt")
    manifest_names = {"package.json"} if npm else {"requirements.txt", "pyproject.toml", "Pipfile", "poetry.lock", "Pipfile.lock", "setup.py", "setup.cfg"}
    unsupported = []
    def fail_walk(error: OSError) -> None:
        raise error
    for root, dirs, files in os.walk(app_dir, onerror=fail_walk):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for name in files:
            if name not in manifest_names and not (not npm and name.startswith("requirements") and name.endswith((".txt", ".in"))):
                continue
            candidate = Path(root) / name
            if candidate != manifest:
                unsupported.append(str(candidate.relative_to(app_dir)))
    if unsupported:
        return {"status": "NOT_VERIFIED", "required": True,
                "reason": "Unsupported or nested dependency manifests require separate audits", "manifests": unsupported}
    if not manifest.exists():
        return {"status": "NOT_VERIFIED", "required": False, "reason": f"No {manifest.name} found"}
    tool = shutil.which("npm" if npm else "pip-audit")
    if not tool:
        return {"status": "NOT_VERIFIED", "required": True, "reason": "Required scanner not installed"}
    command = [tool, "audit", "--json"] if npm else [tool, "-r", str(manifest), "--format", "json"]
    try:
        proc = subprocess.run(command, cwd=str(app_dir), capture_output=True, text=True, timeout=25,
                              shell=npm and os.name == "nt")
        if proc.returncode not in (0, 1):
            raise ValueError(f"Scanner exit code {proc.returncode}")
        data = json.loads(proc.stdout)
        counts = dict.fromkeys(("critical", "high", "moderate", "low", "unknown"), 0)
        if npm:
            if not isinstance(data, dict) or "error" in data:
                raise ValueError("Invalid npm audit response")
            summary = data.get("metadata", {}).get("vulnerabilities")
            if not isinstance(summary, dict) or not all(key in summary for key in ("critical", "high", "moderate", "low")):
                raise ValueError("Missing npm vulnerability summary")
            for key in counts:
                value = summary.get(key, 0)
                if type(value) is not int or value < 0:
                    raise ValueError("Invalid vulnerability count")
                counts[key] = value
        else:
            deps = data.get("dependencies") if isinstance(data, dict) else data
            if not isinstance(deps, list) or (isinstance(data, dict) and "error" in data):
                raise ValueError("Missing Python dependency results")
            targets = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
            if targets and not deps:
                raise ValueError("Empty Python results for nonempty requirements")
            for dep in deps:
                if not isinstance(dep, dict) or not isinstance(dep.get("vulns"), list) or not isinstance(dep.get("name"), str) or not dep["name"].strip() or dep.get("skip_reason"):
                    raise ValueError("Incomplete Python dependency result")
                for vuln in dep["vulns"]:
                    if not isinstance(vuln, dict) or not vuln.get("id"):
                        raise ValueError("Invalid Python vulnerability")
                    severity = str(vuln.get("severity", "unknown")).lower()
                    severity = "moderate" if severity == "medium" else severity
                    counts[severity if severity in counts else "unknown"] += 1
            normalize = lambda name: re.sub(r"[-_.]+", "-", name).lower()
            expected = set()
            for target in targets:
                requirement = re.split(r"\s+#", target, maxsplit=1)[0].strip()
                match = re.fullmatch(
                    r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9_,. -]+\])?"
                    r"(?:\s*(?:===|~=|==|!=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+(?:\s*,\s*(?:===|~=|==|!=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+)*)?",
                    requirement,
                )
                if not match:
                    return {"status": "NOT_VERIFIED", "required": True,
                            "reason": "Unsupported requirement syntax prevents dependency coverage verification",
                            "tool": "pip-audit", "returncode": proc.returncode,
                            "vulnerabilities": {**counts, "found": sum(counts.values())}}
                expected.add(normalize(match.group(1)))
            actual = {normalize(dep["name"]) for dep in deps}
            if not expected.issubset(actual):
                raise ValueError("Python results do not cover named requirement targets")
        found = sum(counts.values())
        if proc.returncode == 1 and not found:
            raise ValueError("Scanner exit 1 without vulnerability findings")
        return {"status": "FAIL" if found else "PASS", "required": True,
                "tool": "npm audit" if npm else "pip-audit", "returncode": proc.returncode,
                "vulnerabilities": {**counts, "found": found}}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as exc:
        return {"status": "ERROR", "required": True, "reason": f"Scanner failed: {exc}"}


def audit_npm_dependencies(app_dir: Path) -> dict[str, Any]:
    return _scan_dependencies(app_dir, "npm")


def audit_python_dependencies(app_dir: Path) -> dict[str, Any]:
    return _scan_dependencies(app_dir, "python")


def run_security_audit(app_dir: str | Path = ".", fail_on_critical: bool = False) -> dict[str, Any]:
    """Default report blocks CRITICAL, HIGH and UNKNOWN; flag selects critical-only policy."""
    target_dir = Path(app_dir).resolve()
    if not target_dir.is_dir():
        raise FileNotFoundError(f"App directory '{target_dir}' does not exist.")
    scan_error = None
    secrets = []
    deps = {}
    try:
        secrets = scan_directory_for_secrets(target_dir)
        deps = {"npm": audit_npm_dependencies(target_dir), "python": audit_python_dependencies(target_dir)}
    except OSError as exc:
        scan_error = f"Incomplete filesystem scan: {exc}"

    summary = dict.fromkeys(("critical", "high", "medium", "low", "unknown"), 0)
    summary["critical"] = len(secrets)
    summary["secrets_found"] = len(secrets)
    for result in deps.values():
        for severity in ("critical", "high", "moderate", "low", "unknown"):
            summary["medium" if severity == "moderate" else severity] += result.get("vulnerabilities", {}).get(severity, 0)
    incomplete = [r for r in deps.values() if r["required"] and r["status"] in ("ERROR", "NOT_VERIFIED")]
    blocking = ["CRITICAL", "UNKNOWN"] if fail_on_critical else ["CRITICAL", "HIGH", "UNKNOWN"]
    status = ("ERROR" if any(r["status"] == "ERROR" for r in incomplete) else "NOT_VERIFIED") if incomplete else (
        "FAIL" if any(summary[k.lower()] for k in blocking) else "PASS")
    if scan_error:
        status = "ERROR"
    return {"app_dir": str(target_dir), "status": status, "scan_error": scan_error, "passed": status == "PASS",
            "policy": {"blocking_severities": blocking, "required_scans_must_complete": True},
            "summary": summary, "secrets": secrets, "dependencies": deps}


def format_markdown_report(report: dict[str, Any]) -> str:
    """Định dạng kết quả kiểm toán thành báo cáo Markdown trực quan."""
    summary = report["summary"]
    status_text = report["status"]

    lines = [
        "# BÁO CÁO THẨM ĐỊNH AN TOÀN BẢO MẬT (SECURITY AUDIT REPORT)",
        f"- **Thư mục ứng dụng:** `{report['app_dir']}`",
        f"- **Trạng thái:** **{status_text}**",
        "",
        f"Policy: block {', '.join(report['policy']['blocking_severities'])}; required dependency scans must complete successfully.",
        "--fail-on-critical selects CRITICAL and UNKNOWN blocking policy; incomplete scans always fail.",
        "",
        "## 1. Tổng Kết Rủi Ro",
        "| Mức độ | Số lượng | Đánh giá |",
        "| :--- | :--- | :--- |",
        f"| **CRITICAL** | {summary['critical']} | {'Nguy cơ rò rỉ secret hoặc lỗ hổng nghiêm trọng' if summary['critical'] > 0 else 'An toàn'} |",
        f"| **HIGH** | {summary['high']} | {'Cần xử lý trước khi deploy production' if summary['high'] > 0 else 'An toàn'} |",
        f"| **MEDIUM** | {summary['medium']} | Khuyến nghị nâng cấp |",
        f"| **UNKNOWN** | {summary['unknown']} | Requires severity verification |",
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
    lines.append(f"- **Node.js (npm):** Trạng thái: `{deps.get('npm', {}).get('status', 'ERROR')}` ({deps.get('npm', {}).get('reason', report.get('scan_error') or 'OK')})")
    lines.append(f"- **Python:** Trạng thái: `{deps.get('python', {}).get('status', 'ERROR')}` ({deps.get('python', {}).get('reason', report.get('scan_error') or 'OK')})")

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

    if not report["passed"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
