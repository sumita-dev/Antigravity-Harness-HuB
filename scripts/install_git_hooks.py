#!/usr/bin/env python3
"""Tự động cài đặt Git Pre-Push Hook cho Antigravity Harness Hub.

Chốt chặn này chạy tự động mỗi khi người dùng gõ `git push`.
Nếu hệ thống chưa vượt qua toàn bộ các kiểm thử (bao gồm AST dependency guard),
lệnh push sẽ tự động bị từ chối ngay tại máy cục bộ.
"""

import subprocess
import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".git" / "hooks"
GITHOOKS_DIR = REPO_ROOT / ".githooks"

PRE_PUSH_SCRIPT = """#!/bin/sh
# Antigravity Pre-Push Verification Hook
echo "================================================================="
echo "[HOOK] ANTIGRAVITY AUTOMATED PRE-PUSH VERIFICATION HOOK"
echo "================================================================="

python scripts/pre_push_check.py
RESULT=$?

if [ $RESULT -ne 0 ]; then
    echo ""
    echo "[PUSH ABORTED] Kiem thu truoc khi push khong dat yeu cau!"
    echo "Ngan chan push len GitHub de bao ve trang thai CI xanh."
    echo "================================================================="
    exit 1
fi

echo "[PUSH APPROVED] Kiem tra thanh cong! Dang tien hanh push len GitHub..."
echo "================================================================="
exit 0
"""

def install_hook():
    # 1. Cài đặt trực tiếp vào .githooks (được theo dõi trong git trên GitHub)
    if not GITHOOKS_DIR.exists():
        GITHOOKS_DIR.mkdir(parents=True, exist_ok=True)
    tracked_hook = GITHOOKS_DIR / "pre-push"
    tracked_hook.write_text(PRE_PUSH_SCRIPT, encoding="utf-8")
    try:
        tracked_hook.chmod(0o755)
    except Exception:
        pass

    # 2. Cấu hình git config core.hooksPath trỏ vào .githooks
    try:
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=REPO_ROOT, check=True)
        print("[OK] Da cau hinh Git tu dong doc hooks tu: .githooks/")
    except Exception as e:
        print(f"[WARN] Khong the cau hinh core.hooksPath: {e}")

    # 3. Đồng bộ dự phòng vào .git/hooks/pre-push
    if HOOKS_DIR.exists():
        fallback_hook = HOOKS_DIR / "pre-push"
        fallback_hook.write_text(PRE_PUSH_SCRIPT, encoding="utf-8")
        try:
            fallback_hook.chmod(0o755)
        except Exception:
            pass
        print(f"[OK] Da cai dat ban sao du phong tai: {fallback_hook.relative_to(REPO_ROOT)}")

    print("\n[SUCCESS] Tu nay, moi khi go 'git push', he thong se tu dong chay pre_push_check.py!")

if __name__ == "__main__":
    install_hook()
