#!/usr/bin/env python3
"""Script helper giám sát dev server và bắt lỗi runtime thời gian thực.

Spawn tiến trình dev server theo lệnh được truyền vào, đọc đồng thời stdout và stderr,
phát hiện các dòng chứa ERROR, CRITICAL, Exception hoặc Traceback, và ghi nhận vào
file 'runtime-crash.log' kèm timestamp.

Tích hợp Pre-flight Port Check và HTTP Health Check tự động.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ERROR_PATTERN = re.compile(
    r"(?:error|critical|exception|traceback|syntaxerror|typeerror|referenceerror|fatal|unhandled)",
    re.IGNORECASE,
)


def log_crash(log_file: Path, line: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {line}\n")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Kiểm tra socket kết nối xem port có đang bị chiếm dụng không."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def wait_for_http_ok(url: str, timeout: float = 15.0) -> bool:
    """Thăm dò GET request tới URL cho tới khi nhận HTTP 200 trước khi in thông báo server đã sẵn sàng."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Antigravity-DevLogger-HealthCheck/1.0"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    print(f"[*] Server đã sẵn sàng tại {url} (HTTP 200 OK)")
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"[!] Hết thời gian chờ ({timeout}s), chưa nhận được HTTP 200 từ: {url}")
    return False


def stream_reader(pipe, is_stderr: bool, log_file: Path) -> None:
    try:
        for raw_line in iter(pipe.readline, ""):
            line = raw_line.rstrip("\r\n")
            # In ra console để người dùng vẫn theo dõi được dev server
            if is_stderr:
                sys.stderr.write(raw_line)
                sys.stderr.flush()
            else:
                sys.stdout.write(raw_line)
                sys.stdout.flush()

            # Bắt lỗi và ghi vào file crash log
            if is_stderr or ERROR_PATTERN.search(line):
                log_crash(log_file, f"[{'STDERR' if is_stderr else 'STDOUT'}] {line}")
    except (ValueError, OSError):
        pass
    finally:
        pipe.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chạy command dev server và tự động bắt lỗi runtime vào runtime-crash.log"
    )
    parser.add_argument(
        "--command",
        "-c",
        required=True,
        help="Command dòng lệnh để khởi chạy dev server (ví dụ: 'npm run dev', 'python app.py')",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Thư mục làm việc (mặc định: current directory)",
    )
    parser.add_argument(
        "--log-file",
        default="runtime-crash.log",
        help="Tên file log ghi nhận lỗi (mặc định: runtime-crash.log)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Cổng dev server để kiểm tra pre-flight port check (ví dụ: 3000, 5173)",
    )
    parser.add_argument(
        "--url",
        "-u",
        default=None,
        help="URL health check (mặc định: http://localhost:<port> nếu có --port)",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=15.0,
        help="Thời gian timeout tối đa cho HTTP health check tính bằng giây (mặc định: 15)",
    )

    args = parser.parse_args()

    work_dir = Path(args.cwd).resolve()
    log_path = work_dir / args.log_file

    # 1. Pre-flight Port Check
    check_port = args.port
    if check_port is None and args.url:
        m = re.search(r":(\d+)", args.url)
        if m:
            check_port = int(m.group(1))

    if check_port is not None:
        if is_port_in_use(check_port):
            warning_msg = f"[!] CẢNH BÁO PRE-FLIGHT: Port {check_port} đang bị chiếm dụng bởi tiến trình khác!"
            print(warning_msg, file=sys.stderr)
            log_crash(log_path, warning_msg)
        else:
            print(f"[*] Pre-flight check: Port {check_port} khả dụng.")

    print(f"[*] Khởi động dev server: {args.command}")
    print(f"[*] Thư mục làm việc: {work_dir}")
    print(f"[*] Crash log đích: {log_path}")

    # Ghi nhận thời điểm bắt đầu phiên
    log_crash(log_path, f"=== BẮT ĐẦU PHIÊN GIÁM SÁT DEV SERVER: {args.command} ===")

    process = subprocess.Popen(
        args.command,
        cwd=work_dir,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    stdout_thread = threading.Thread(
        target=stream_reader, args=(process.stdout, False, log_path), daemon=True
    )
    stderr_thread = threading.Thread(
        target=stream_reader, args=(process.stderr, True, log_path), daemon=True
    )

    stdout_thread.start()
    stderr_thread.start()

    # 2. HTTP Health Check (nếu có URL hoặc port)
    target_url = args.url
    if not target_url and check_port:
        target_url = f"http://localhost:{check_port}"

    if target_url:
        health_thread = threading.Thread(
            target=wait_for_http_ok,
            args=(target_url, args.health_timeout),
            daemon=True,
        )
        health_thread.start()

    try:
        exit_code = process.wait()
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        log_crash(log_path, f"=== KẾT THÚC PHIÊN: Tiến trình dừng với mã thoát {exit_code} ===")
        return exit_code
    except KeyboardInterrupt:
        print("\n[*] Nhận tín hiệu dừng từ người dùng. Đang tắt tiến trình...")
        process.terminate()
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
        log_crash(log_path, "=== PHIÊN BỊ DỪNG BỞI NGƯỜI DÙNG (SIGINT) ===")
        return 0


if __name__ == "__main__":
    sys.exit(main())
