"""Antigravity Doctor Periodic Watcher (Cron Runner).

Chạy định kỳ audit_antigravity.py, ghi kết quả ra Obsidian Vault
và gửi Windows Notification khi phát hiện trạng thái ATTENTION.
Vận hành 100% Read-Only, Zero-Token.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
AUDIT_SCRIPT = Path(__file__).resolve().parent / "audit_antigravity.py"
DEFAULT_VAULT_PATH = Path(
    os.getenv("OBSIDIAN_VAULT_PATH") or Path.home() / "Obsidian"
)


def send_windows_notification(title: str, message: str) -> None:
    """Gửi Windows Balloon/Toast notification nhẹ không cần admin."""
    ps_cmd = (
        f"[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
        f"$notify = New-Object System.Windows.Forms.NotifyIcon; "
        f"$notify.Icon = [System.Drawing.SystemIcons]::Warning; "
        f"$notify.BalloonTipTitle = '{title}'; "
        f"$notify.BalloonTipText = '{message}'; "
        f"$notify.Visible = $True; "
        f"$notify.ShowBalloonTip(6000); "
        f"Start-Sleep -s 7; "
        f"$notify.Dispose()"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        pass


def run_doctor_audit() -> int:
    """Thực thi chẩn đoán và kết xuất vào Obsidian Vault."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Đảm bảo thư mục wiki trong Vault tồn tại
    target_dir = DEFAULT_VAULT_PATH / "wiki"
    target_dir.mkdir(parents=True, exist_ok=True)
    report_file = target_dir / "agy-doctor-latest.md"

    # Chạy audit_antigravity.py
    cmd = [sys.executable, str(AUDIT_SCRIPT), "--markdown"]
    result = subprocess.run(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    report_content = result.stdout or ""
    if not report_content and result.stderr:
        report_content = f"Lỗi thực thi audit:\n```\n{result.stderr}\n```\n"

    # Ghi nhận thời gian audit vào đầu file
    header = (
        f"> 🕒 **Lần Khám Gần Nhất (Watcher):** `{now_str}`  \n"
        f"> 🔄 **Tần Suất:** Định kỳ mỗi 2 giờ | **Vận Hành:** Zero-Token OS Task\n\n"
    )
    final_output = header + report_content

    report_file.write_text(final_output, encoding="utf-8")

    # Nếu có cảnh báo ATTENTION (exit code != 0), bắn notification
    if result.returncode != 0:
        send_windows_notification(
            title="⚠️ Antigravity Doctor: Cần Chú Ý!",
            message="Phát hiện chỉ số cần lưu ý trong Antigravity 2.0. Vui lòng mở wiki/agy-doctor-latest.md để xem chi tiết.",
        )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_doctor_audit())
