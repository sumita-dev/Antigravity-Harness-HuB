#!/usr/bin/env python3
"""Antigravity Pre-Push Verification Gate.

Chốt chặn tự động kiểm tra tính toàn vẹn đa nền tảng, rò rỉ dependency,
và hồi quy kiểm thử TRƯỚC KHI git push lên GitHub.
Vận hành phân tầng Fast-Tier Test Suite đảm bảo đối soát trong 15-20s thay vì phải chờ lâu.
"""

import os
import subprocess
import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_step(step_name: str, cmd: list) -> bool:
    print(f"\n[PRE-PUSH] -> {step_name}...")
    try:
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            print(f"  [PASS] {step_name}")
            return True
        else:
            print(f"  [FAIL] {step_name} (Exit code {res.returncode})")
            if res.stdout:
                print(res.stdout.strip())
            if res.stderr:
                print(res.stderr.strip())
            return False
    except Exception as e:
        print(f"  [ERROR] {step_name}: ({e})")
        return False


def main():
    print("=" * 65)
    print("ANTIGRAVITY HERMETIC PRE-PUSH VERIFICATION GATE (FAST TIER)")
    print("=" * 65)

    fast_test_cmd = (
        [sys.executable, "scripts/run_pytest_windows.py", "--tier", "fast", "-q"]
        if os.name == "nt"
        else [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_harness_doctor.py",
            "tests/test_skill_router_ranking.py",
            "tests/test_clean_state_cli.py",
            "tests/test_anti_hallucination.py",
            "tests/test_deterministic_rules.py",
            "-q",
        ]
    )

    steps = [
        ("1. Rà soát cấu trúc & cú pháp kỹ năng (Skill Linter)", [sys.executable, "scripts/lint_harness_skills.py"]),
        ("2. Kiểm định Fast-Tier Test Suite (5 Test Cốt Lõi)", fast_test_cmd),
        ("3. Rà soát rò rỉ Dependency & Tính toàn vẹn Repo", [sys.executable, "-m", "pytest", "tests/test_repo_integrity.py", "-q"]),
    ]

    for name, cmd in steps:
        if not run_step(name, cmd):
            print("\n" + "=" * 65)
            print("PRE-PUSH CHECK FAILED!")
            print("Lệnh 'git push' bị chặn lại để bảo vệ nhánh CI trên GitHub.")
            print("Vui lòng sửa lỗi theo thông báo chi tiết ở trên rồi thử lại.")
            print("=" * 65)
            sys.exit(1)

    print("\n" + "=" * 65)
    print("ALL PRE-PUSH CHECKS PASSED (100% HERMETIC & GREEN)!")
    print("Hệ thống sẵn sàng và an toàn tuyệt đối để push lên GitHub.")
    print("=" * 65)
    sys.exit(0)


if __name__ == "__main__":
    main()
