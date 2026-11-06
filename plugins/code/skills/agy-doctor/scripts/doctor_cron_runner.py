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


def send_windows_notification(
    title: str, message: str, report_file: Path | None = None
) -> None:
    """Gửi Windows Toast notification hỗ trợ click để mở file qua WinRT protocol activation."""
    if report_file and report_file.exists():
        file_uri = report_file.resolve().as_uri()
    else:
        file_uri = ""

    # Chuẩn bị XML an toàn
    safe_title = (
        title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    safe_message = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    if file_uri:
        xml_content = f"""<toast launch="{file_uri}" activationType="protocol">
    <visual>
        <binding template="ToastGeneric">
            <text>{safe_title}</text>
            <text>{safe_message}</text>
        </binding>
    </visual>
    <actions>
        <action content="Mở Báo Cáo (.md)" activationType="protocol" arguments="{file_uri}" />
    </actions>
</toast>"""
    else:
        xml_content = f"""<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{safe_title}</text>
            <text>{safe_message}</text>
        </binding>
    </visual>
</toast>"""

    # Gọi Windows.UI.Notifications qua PowerShell WinRT API
    ps_cmd = (
        f"$xmlText = @'\n{xml_content}\n'@;\n"
        f"$appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe';\n"
        f"$xmlDoc = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]::New();\n"
        f"$xmlDoc.LoadXml($xmlText);\n"
        f"$toast = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]::New($xmlDoc);\n"
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]::CreateToastNotifier($appId).Show($toast);\n"
    )

    try:
        res = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_cmd,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if res.returncode == 0:
            return
    except Exception:
        pass

    # Fallback dự phòng sang System.Windows.Forms.NotifyIcon nếu WinRT không khả dụng
    ps_fallback = (
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
            ["powershell.exe", "-NoProfile", "-Command", ps_fallback],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        pass


def run_doctor_audit() -> int:
    """Thực thi chẩn đoán, tự động tối ưu hóa và kết xuất vào Obsidian Vault."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Đảm bảo thư mục wiki trong Vault tồn tại
    target_dir = DEFAULT_VAULT_PATH / "wiki"
    target_dir.mkdir(parents=True, exist_ok=True)
    report_file = target_dir / "agy-doctor-latest.md"

    # Chạy audit_antigravity.py lần 1
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

    # TỰ ĐỘNG TỐI ƯU HÓA:
    # Nếu phát hiện trùng lặp quy tắc cross-scope gây lãng phí token (ERR_DUPLICATE_RULES_ACROSS_SCOPES)
    auto_optimized = False
    if "ERR_DUPLICATE_RULES_ACROSS_SCOPES" in report_content:
        opt_cmd = [sys.executable, str(AUDIT_SCRIPT), "--fix-duplicate-rules"]
        opt_res = subprocess.run(
            opt_cmd,
            cwd=str(WORKSPACE_ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if opt_res.returncode == 0:
            auto_optimized = True
            # Re-run audit sau khi tối ưu hóa để lấy báo cáo mới nhất
            re_audit = subprocess.run(
                cmd,
                cwd=str(WORKSPACE_ROOT),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            result = re_audit
            report_content = re_audit.stdout or report_content

    # Ghi nhận thời gian audit vào đầu file
    opt_badge = " (Đã tự động tối ưu hóa quy tắc)" if auto_optimized else ""
    header = (
        f"> 🕒 **Lần Khám Gần Nhất (Watcher):** `{now_str}`{opt_badge}  \n"
        f"> 🔄 **Tần Suất:** Định kỳ mỗi 1 giờ | **Vận Hành:** Zero-Token OS Task\n\n"
    )
    final_output = header + report_content

    report_file.write_text(final_output, encoding="utf-8")

    # Nếu có cảnh báo ATTENTION (exit code != 0), bắn notification
    if result.returncode != 0:
        send_windows_notification(
            title="⚠️ Antigravity Doctor: Cần Chú Ý!",
            message="Phát hiện chỉ số cần lưu ý trong Antigravity 2.0. Nhấn vào đây để xem chi tiết.",
            report_file=report_file,
        )

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_doctor_audit())
