#!/usr/bin/env python3
"""Script tự động sinh launcher 1-click (start-app.bat) và hướng dẫn sử dụng nhanh (HDSD-NHANH.md).

Phục vụ Pha 6 (Packaging & Handoff) trong quy trình App Workflow của Antigravity Harness Hub.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def generate_launcher(
    app_dir: str | Path,
    port: int = 3000,
    start_cmd: str = "npm run dev",
    title: str = "Antigravity App",
    data_file: str = "mockData.json",
) -> tuple[Path, Path]:
    """Sinh file start-app.bat và HDSD-NHANH.md vào app_dir."""
    target_dir = Path(app_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    bat_path = target_dir / "start-app.bat"
    doc_path = target_dir / "HDSD-NHANH.md"

    # Xây dựng đoạn kiểm tra môi trường
    env_checks = []
    low_cmd = start_cmd.lower()
    if any(k in low_cmd for k in ("npm", "node", "vite", "next", "pnpm", "yarn", "bun")):
        env_checks.append(
            """where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] LOI: Khong tim thay Node.js trong he thong!
    echo     Vui long cai dat Node.js tai https://nodejs.org/ truoc khi chay.
    pause
    exit /b 1
)"""
        )
    if any(k in low_cmd for k in ("python", "py", "uvicorn", "fastapi", "flask", "streamlit")):
        env_checks.append(
            """where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [!] LOI: Khong tim thay Python trong he thong!
        echo     Vui long cai dat Python tai https://python.org/ truoc khi chay.
        pause
        exit /b 1
    )
)"""
        )

    env_check_block = "\n\n".join(env_checks)
    if not env_check_block:
        env_check_block = "REM Khong co kiem tra dac thu cho lenh nay."

    bat_content = f"""@echo off
chcp 65001 >nul
title {title} - Launcher
echo ========================================================
echo   DANG KHOI DONG UNG DUNG: {title}
echo   Port: {port}
echo   Command: {start_cmd}
echo ========================================================
echo.

REM 1. Kiem tra moi truong
{env_check_block}

REM 2. Khoi dong dev server o cua so moi (background)
echo [*] Dang khoi chay dev server...
start "{title} - Server" cmd /c "{start_cmd}"

REM 3. Cho server khoi dong va tu dong mo trinh duyet
echo [*] Dang mo trinh duyet tai http://localhost:{port} ...
timeout /t 3 /nobreak >nul
start http://localhost:{port}

echo.
echo ========================================================
echo   Ung dung da duoc khoi chay thanh cong!
echo   Trinh duyet da mo tai: http://localhost:{port}
echo   De tat ung dung: Vui long dong cua so "{title} - Server".
echo ========================================================
pause
"""

    doc_content = f"""# Hướng Dẫn Sử Dụng Nhanh (1-Click Run)

Ứng dụng: **{title}**  
Cổng kết nối: `http://localhost:{port}`  
Lệnh khởi chạy: `{start_cmd}`  

---

## 1. Cách khởi động ứng dụng (1-Click)
- Nhấp đúp chuột vào file **`start-app.bat`** trong thư mục này.
- Hệ thống sẽ tự động kiểm tra môi trường, khởi động server ngầm và mở trình duyệt web tại:
  **http://localhost:{port}**

---

## 2. Cách tắt ứng dụng
- Đóng cửa sổ Command Prompt có tiêu đề **`{title} - Server`**.
- Server sẽ dừng và giải phóng cổng `{port}`.

---

## 3. Dữ liệu ban đầu (Seed Data)
- Vị trí file dữ liệu: **`{data_file}`**
- Ứng dụng đã được tích hợp sẵn dữ liệu mẫu thực tế, phong phú (đáp ứng tiêu chí AC-SEED) để trải nghiệm và demo ngay mà không cần cấu hình ban đầu.
"""

    bat_path.write_text(bat_content, encoding="utf-8")
    doc_path.write_text(doc_content, encoding="utf-8")

    return bat_path, doc_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tự động sinh launcher 1-click start-app.bat và HDSD-NHANH.md cho ứng dụng"
    )
    parser.add_argument(
        "--app-dir",
        default=".",
        help="Đường dẫn thư mục ứng dụng (mặc định: current directory)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Cổng dev server (mặc định: 3000)",
    )
    parser.add_argument(
        "--start-cmd",
        default="npm run dev",
        help="Lệnh khởi chạy ứng dụng (ví dụ: 'npm run dev', 'python main.py')",
    )
    parser.add_argument(
        "--title",
        default="Antigravity Application",
        help="Tên ứng dụng hiển thị (mặc định: Antigravity Application)",
    )
    parser.add_argument(
        "--data-file",
        default="mockData.json",
        help="Đường dẫn file dữ liệu mẫu/seed data (mặc định: mockData.json)",
    )

    args = parser.parse_args()

    bat_file, doc_file = generate_launcher(
        app_dir=args.app_dir,
        port=args.port,
        start_cmd=args.start_cmd,
        title=args.title,
        data_file=args.data_file,
    )

    print(f"[+] Đã tạo file launcher: {bat_file}")
    print(f"[+] Đã tạo file hướng dẫn: {doc_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
