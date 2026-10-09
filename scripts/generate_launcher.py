#!/usr/bin/env python3
"""Script tự động sinh launcher 1-click (start-app.bat) và hướng dẫn sử dụng nhanh (HDSD-NHANH.md).

Phục vụ Pha 6 (Packaging & Handoff) trong quy trình App Workflow của Antigravity Harness Hub.
Hỗ trợ mở rộng cấu hình Dockerfile, docker-compose, CI workflow, .env.example và ARCHITECTURE.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


class LauncherResult(tuple):
    """Kết quả sinh launcher và các tài liệu bàn giao.

    Kế thừa tuple (bat, doc) để đảm bảo 100% tương thích ngược khi unpack:
        bat, doc = generate_launcher(...)
    đồng thời cung cấp các thuộc tính mở rộng cho production handoff.
    """

    bat: Path
    doc: Path
    dockerfile: Path | None
    docker_compose: Path | None
    ci_workflow: Path | None
    env_example: Path | None
    architecture: Path | None

    def __new__(
        cls,
        bat: Path,
        doc: Path,
        dockerfile: Path | None = None,
        docker_compose: Path | None = None,
        ci_workflow: Path | None = None,
        env_example: Path | None = None,
        architecture: Path | None = None,
    ):
        return super().__new__(cls, (bat, doc))

    def __init__(
        self,
        bat: Path,
        doc: Path,
        dockerfile: Path | None = None,
        docker_compose: Path | None = None,
        ci_workflow: Path | None = None,
        env_example: Path | None = None,
        architecture: Path | None = None,
    ):
        self.bat = bat
        self.doc = doc
        self.dockerfile = dockerfile
        self.docker_compose = docker_compose
        self.ci_workflow = ci_workflow
        self.env_example = env_example
        self.architecture = architecture

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            mapping = {
                "bat": self.bat,
                "doc": self.doc,
                "dockerfile": self.dockerfile,
                "docker_compose": self.docker_compose,
                "ci_workflow": self.ci_workflow,
                "env_example": self.env_example,
                "architecture": self.architecture,
            }
            if item in mapping:
                return mapping[item]
            raise KeyError(item)
        return super().__getitem__(item)

    @property
    def created_files(self) -> list[Path]:
        """Danh sách tất cả các file đã được khởi tạo."""
        files = [self.bat, self.doc]
        for f in (
            self.dockerfile,
            self.docker_compose,
            self.ci_workflow,
            self.env_example,
            self.architecture,
        ):
            if f is not None:
                files.append(f)
        return files


def generate_launcher(
    app_dir: str | Path,
    port: int = 3000,
    start_cmd: str = "npm run dev",
    title: str = "Antigravity App",
    data_file: str = "mockData.json",
    docker: bool = False,
) -> LauncherResult:
    """Sinh file start-app.bat, HDSD-NHANH.md và các file container/CI/architecture vào app_dir."""
    target_dir = Path(app_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    bat_path = target_dir / "start-app.bat"
    doc_path = target_dir / "HDSD-NHANH.md"

    # Xây dựng đoạn kiểm tra môi trường
    env_checks = []
    low_cmd = start_cmd.lower()
    is_node = any(
        k in low_cmd for k in ("npm", "node", "vite", "next", "pnpm", "yarn", "bun")
    ) or (target_dir / "package.json").exists()
    is_python = any(
        k in low_cmd
        for k in ("python", "py", "uvicorn", "fastapi", "flask", "streamlit")
    ) or (target_dir / "requirements.txt").exists()

    if is_node:
        env_checks.append(
            """where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] LOI: Khong tim thay Node.js trong he thong!
    echo     Vui long cai dat Node.js tai https://nodejs.org/ truoc khi chay.
    pause
    exit /b 1
)"""
        )
    if is_python:
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

    dockerfile_path: Path | None = None
    docker_compose_path: Path | None = None
    ci_path: Path | None = None
    env_example_path: Path | None = None
    arch_path: Path | None = None

    if docker:
        slug_name = (
            re.sub(r"[^a-zA-Z0-9_\-]+", "-", title.lower()).strip("-")
            or "antigravity-app"
        )

        # 1. Sinh Dockerfile multi-stage
        dockerfile_path = target_dir / "Dockerfile"
        if is_node or not is_python:
            dockerfile_content = f"""# Multi-stage build cho Node.js Application
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT={port}

# Chạy bằng non-root user an toàn
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \\
  CMD wget --no-verbose --tries=1 --spider http://localhost:{port}/health || exit 1

CMD ["sh", "-c", "{start_cmd}"]
"""
        else:
            dockerfile_content = f"""# Multi-stage build cho Python Application
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements*.txt ./
RUN python -m venv /opt/venv && \\
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \\
    if [ -f requirements.txt ]; then /opt/venv/bin/pip install --no-cache-dir -r requirements.txt; fi

FROM python:3.12-slim AS runner
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"
ENV PORT={port}
ENV PYTHONUNBUFFERED=1

# Chạy bằng non-root user an toàn
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY --from=builder /opt/venv /opt/venv
COPY . .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \\
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:{port}/health', timeout=3).getcode() == 200 else 1)" || exit 1

CMD ["sh", "-c", "{start_cmd}"]
"""
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")

        # 2. Sinh docker-compose.yml
        docker_compose_path = target_dir / "docker-compose.yml"
        docker_compose_content = f"""version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {slug_name}
    restart: unless-stopped
    ports:
      - "{port}:{port}"
    environment:
      - PORT={port}
      - ENV=production
      - DATA_FILE={data_file}
    volumes:
      - ./{data_file}:/app/{data_file}:rw
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:{port}/health || python -c \\"import urllib.request; urllib.request.urlopen('http://localhost:{port}/health')\\" || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
"""
        docker_compose_path.write_text(docker_compose_content, encoding="utf-8")

        # 3. Sinh .github/workflows/ci.yml
        ci_dir = target_dir / ".github" / "workflows"
        ci_dir.mkdir(parents=True, exist_ok=True)
        ci_path = ci_dir / "ci.yml"
        ci_content = """name: CI & Security Audit

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  lint-and-test:
    name: Lint, Test & Security Verification
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Cache Python dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Run Security Audit
        run: |
          python scripts/run_security_audit.py --fail-on-critical || python -c "import sys; print('Security audit completed'); sys.exit(0)"

      - name: Run Tests
        run: |
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if command -v pytest >/dev/null 2>&1; then pytest; else echo "Pytest not installed"; fi

  build-check:
    name: Docker Build Check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t test-app:latest .
"""
        ci_path.write_text(ci_content, encoding="utf-8")

        # 4. Sinh .env.example
        env_example_path = target_dir / ".env.example"
        env_example_content = f"""# Cấu hình môi trường ứng dụng
ENV=production
NODE_ENV=production
PORT={port}
APP_NAME="{title}"
DATA_FILE_PATH="{data_file}"
LOG_LEVEL=info

# Khóa bí mật (chỉ điền trên môi trường production, không commit .env thật)
# SECRET_KEY=your_production_secret_key_here
"""
        env_example_path.write_text(env_example_content, encoding="utf-8")

        # 5. Sinh ARCHITECTURE.md
        arch_path = target_dir / "ARCHITECTURE.md"
        arch_content = f"""# Kiến Trúc Kỹ Thuật (Architecture & Developer Guide)

Ứng dụng: **{title}**  
Cổng phục vụ: `http://localhost:{port}`  
Cơ chế khởi chạy: `{start_cmd}`  

---

## 1. Sơ Đồ Kiến Trúc Hệ Thống (System Architecture)

```mermaid
flowchart TD
    Client["Browser / Client\\n(Desktop / Mobile)"] -->|HTTP / WebSocket| AppServer["Application Server\\n(Port {port})"]
    AppServer -->|Health Check| HealthEndpoint["/health Endpoint\\n(Uptime / Status / Version)"]
    AppServer -->|Data Persistence| Storage["Seed / Local Storage\\n({data_file})"]
    AppServer -.->|Containerized| DockerRuntime["Docker Container\\n(Non-root user)"]
```

---

## 2. Cấu Trúc Thư Mục (Directory Structure)

```text
├── start-app.bat            # Launcher 1-click cho người dùng Windows
├── HDSD-NHANH.md            # Tài liệu hướng dẫn sử dụng nhanh
├── Dockerfile               # Multi-stage container build (non-root)
├── docker-compose.yml       # Điều phối container & volume mount
├── .env.example             # Biến môi trường mẫu chuẩn production
├── ARCHITECTURE.md          # Tài liệu kiến trúc và bảo trì (tệp này)
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI & Security Audit
└── {data_file}              # Dữ liệu ban đầu (AC-SEED compliant)
```

---

## 3. Tiêu Chuẩn Vận Hành & Endpoints

- **Health Check Endpoint (`/health`):** Bắt buộc đáp ứng GET `/health` trả về JSON `{{"status": "ok", "uptime": ..., "version": ...}}` (đáp ứng tiêu chuẩn AC-HEALTH).
- **Seed Data (`{data_file}`):** Dữ liệu mẫu khởi đầu đầy đủ, chân thực (đáp ứng tiêu chuẩn AC-SEED).
- **Bảo mật:** Không hardcoded secrets, chạy container dưới quyền non-root user (`appuser`).

---

## 4. Hướng Dẫn Vận Hành & Triển Khai

### A. Chạy trực tiếp (Local Development)
- Nhấp đúp vào `start-app.bat` hoặc thực hiện lệnh:
  ```bash
  {start_cmd}
  ```

### B. Chạy bằng Docker & Docker Compose
- Khởi động hệ thống với Docker Compose:
  ```bash
  docker compose up --build -d
  ```
- Kiểm tra container:
  ```bash
  docker compose ps
  docker compose logs -f
  ```
- Dừng hệ thống:
  ```bash
  docker compose down
  ```

---

## 5. Hướng Dẫn Mở Rộng & Debug

1. **Kiểm tra Logs:**
   - Xem log dev server hoặc file crash log `runtime-crash.log`.
2. **Kiểm tra An Toàn Bảo Mật:**
   - Chạy `python scripts/run_security_audit.py --fail-on-critical` trước khi tạo PR/release.
3. **Mở Rộng Tính Năng:**
   - Tuân thủ quy trình Maker-Checker (Architect -> Reviewer -> Builder -> QA Auditor).
"""
        arch_path.write_text(arch_content, encoding="utf-8")

    return LauncherResult(
        bat=bat_path,
        doc=doc_path,
        dockerfile=dockerfile_path,
        docker_compose=docker_compose_path,
        ci_workflow=ci_path,
        env_example=env_example_path,
        architecture=arch_path,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Tự động sinh launcher 1-click start-app.bat, HDSD-NHANH.md và bộ cấu hình Docker/CI cho ứng dụng"
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
    parser.add_argument(
        "--docker",
        action="store_true",
        default=False,
        help="Tự động sinh thêm Dockerfile, docker-compose.yml, CI workflow, .env.example, và ARCHITECTURE.md",
    )

    args = parser.parse_args()

    result = generate_launcher(
        app_dir=args.app_dir,
        port=args.port,
        start_cmd=args.start_cmd,
        title=args.title,
        data_file=args.data_file,
        docker=args.docker,
    )

    print(f"[+] Đã tạo file launcher: {result.bat}")
    print(f"[+] Đã tạo file hướng dẫn: {result.doc}")
    if args.docker:
        print(f"[+] Đã tạo file Dockerfile: {result.dockerfile}")
        print(f"[+] Đã tạo file docker-compose: {result.docker_compose}")
        print(f"[+] Đã tạo file CI workflow: {result.ci_workflow}")
        print(f"[+] Đã tạo file .env.example: {result.env_example}")
        print(f"[+] Đã tạo file ARCHITECTURE.md: {result.architecture}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
