#!/usr/bin/env python3
"""Tự động cài đặt Git Pre-Push Hook cho Antigravity Harness Hub.

Chốt chặn này chạy tự động mỗi khi người dùng gõ `git push`.
Nếu hệ thống chưa vượt qua toàn bộ các kiểm thử (bao gồm AST dependency guard),
lệnh push sẽ tự động bị từ chối ngay tại máy cục bộ.
"""

import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".git" / "hooks"

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
    if not HOOKS_DIR.exists():
        print(f"[ERROR] Khong tim thay thu muc {HOOKS_DIR}.")
        sys.exit(1)

    hook_file = HOOKS_DIR / "pre-push"
    hook_file.write_text(PRE_PUSH_SCRIPT, encoding="utf-8")
    
    # Cấp quyền thực thi nếu chạy trên POSIX
    try:
        hook_file.chmod(0o755)
    except Exception:
        pass

    print(f"[OK] Da cai dat thanh cong Git Pre-Push Hook tai: {hook_file.relative_to(REPO_ROOT)}")
    print("Tu nay, moi khi go 'git push', he thong se tu dong chay pre_push_check.py!")

if __name__ == "__main__":
    install_hook()
