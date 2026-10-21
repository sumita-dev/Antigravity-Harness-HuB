#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/safe_task_runner.py

Hard Execution Timeout & Safe Process Guard for Antigravity Harness Hub.
Chốt chặn cấp độ Script / Tooling:
- Bọc mọi lệnh thực thi (CLI hoặc Python callable) với Hard Timeout định lượng.
- Tự động diệt sạch toàn bộ cây tiến trình con (tree kill / taskkill /F /T) khi chạm trần thời gian.
- Dọn dẹp các tiến trình mồ côi có rủi ro treo modal dialog (như WINWORD.EXE, EXCEL.EXE).
- Trả về mã thoát chuẩn (exit code 124 khi timeout) kèm báo cáo JSON/text chi tiết.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


TIMEOUT_EXIT_CODE = 124
DEFAULT_TIMEOUT_SECONDS = 180


def kill_process_tree(pid: int, cleanup_names: Optional[List[str]] = None) -> None:
    """Diệt triệt để cây tiến trình trên Windows / POSIX để chống zombie/orphan."""
    if os.name == "nt":
        # Windows: taskkill /F /T /PID diệt toàn bộ process tree
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except Exception:
            pass

        # Quét dọn các tiến trình COM mồ côi nếu được chỉ định
        if cleanup_names:
            for proc_name in cleanup_names:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )
                except Exception:
                    pass
    else:
        # POSIX
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


def run_command_with_timeout(
    cmd: List[str] | str,
    timeout_sec: float = DEFAULT_TIMEOUT_SECONDS,
    shell: bool = False,
    cwd: Optional[str] = None,
    cleanup_names: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Chạy lệnh với hard timeout.
    Trả về dict:
    {
        "status": "SUCCESS" | "TIMEOUT" | "ERROR",
        "exit_code": int,
        "elapsed_sec": float,
        "stdout": str,
        "stderr": str,
        "timed_out": bool
    }
    """
    start_time = time.time()
    result = {
        "status": "SUCCESS",
        "exit_code": 0,
        "elapsed_sec": 0.0,
        "stdout": "",
        "stderr": "",
        "timed_out": False
    }

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=shell,
            cwd=cwd,
            env=env,
            encoding="utf-8",
            errors="replace"
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
            elapsed = time.time() - start_time
            result["elapsed_sec"] = round(elapsed, 3)
            result["exit_code"] = proc.returncode
            result["stdout"] = stdout
            result["stderr"] = stderr
            result["status"] = "SUCCESS" if proc.returncode == 0 else "ERROR"
            return result

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            kill_process_tree(proc.pid, cleanup_names=cleanup_names)
            try:
                stdout, stderr = proc.communicate(timeout=2.0)
            except Exception:
                stdout, stderr = "", "Process killed due to execution timeout."

            result["elapsed_sec"] = round(elapsed, 3)
            result["exit_code"] = TIMEOUT_EXIT_CODE
            result["stdout"] = stdout
            result["stderr"] = (stderr or "") + f"\n[SAFE_RUNNER_TIMEOUT] Exceeded hard timeout of {timeout_sec}s."
            result["status"] = "TIMEOUT"
            result["timed_out"] = True
            return result

    except Exception as exc:
        elapsed = time.time() - start_time
        result["elapsed_sec"] = round(elapsed, 3)
        result["exit_code"] = 1
        result["stderr"] = f"[SAFE_RUNNER_EXCEPTION] {exc}"
        result["status"] = "ERROR"
        return result


def main():
    parser = argparse.ArgumentParser(
        description="Safe Task Runner: Bọc thực thi với hard timeout và auto-kill cây tiến trình."
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Thời gian timeout tối đa tính bằng giây (mặc định: {DEFAULT_TIMEOUT_SECONDS}s)"
    )
    parser.add_argument(
        "--cleanup-proc",
        action="append",
        default=["WINWORD.EXE", "EXCEL.EXE"],
        help="Tên tiến trình mồ côi cần dọn sạch nếu timeout (có thể lặp lại)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới dạng JSON"
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Lệnh cần thực thi (ví dụ: python script.py arg1 arg2)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help(file=sys.stderr)
        sys.exit(1)

    cmd_to_run = args.command
    # Nếu truyền dạng ['--', 'cmd', ...] thì loại bỏ '--'
    if cmd_to_run and cmd_to_run[0] == "--":
        cmd_to_run = cmd_to_run[1:]

    if not cmd_to_run:
        print("[ERROR] Không tìm thấy lệnh thực thi hợp lệ.", file=sys.stderr)
        sys.exit(1)

    res = run_command_with_timeout(
        cmd=cmd_to_run,
        timeout_sec=args.timeout,
        cleanup_names=args.cleanup_proc
    )

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res["stdout"]:
            print(res["stdout"], end="")
        if res["stderr"]:
            print(res["stderr"], file=sys.stderr, end="")
        if res["timed_out"]:
            print(f"\n[ALERT] Lệnh bị ngắt do vượt ngưỡng an toàn {args.timeout}s!", file=sys.stderr)

    sys.exit(res["exit_code"])


if __name__ == "__main__":
    main()
