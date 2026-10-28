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
import shlex
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


TIMEOUT_EXIT_CODE = 124
DEFAULT_TIMEOUT_SECONDS = 180

# Các flag nhận đối số giá trị của rg và grep
STREAM_OPTIONS_WITH_ARGS = {
    "-e", "-f", "-g", "-t", "-T", "-m", "-C", "-A", "-B", "-E", "-M", "-r", "-d", "-D",
    "--regexp", "--file", "--glob", "--iglob", "--type", "--type-not", "--type-add",
    "--max-count", "--context", "--after-context", "--before-context", "--encoding",
    "--replace", "--max-columns", "--max-filesize", "--path-separator",
    "--exclude", "--include", "--exclude-dir", "--include-dir",
}


def _is_stream_missing_target_path(args: List[str]) -> bool:
    """Kiểm tra danh sách đối số của rg/grep có thiếu target path hay không."""
    if not args:
        return False

    for arg in args:
        if arg in ("--help", "-h", "--version", "-V"):
            return False

    i = 0
    has_explicit_pattern = False
    positional_args: List[str] = []

    while i < len(args):
        tok = args[i]
        if tok == "--":
            positional_args.extend(args[i + 1:])
            break
        if tok in ("-e", "--regexp", "-f", "--file"):
            has_explicit_pattern = True
            i += 2
            continue
        if tok.startswith(("-e=", "--regexp=", "-f=", "--file=")):
            has_explicit_pattern = True
            i += 1
            continue
        if tok in STREAM_OPTIONS_WITH_ARGS:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        positional_args.append(tok)
        i += 1

    if has_explicit_pattern:
        return len(positional_args) == 0
    else:
        return len(positional_args) == 1


def sanitize_stream_command(cmd: List[str] | str) -> List[str] | str:
    """Nếu lệnh bắt đầu bằng rg hoặc grep, phân tích các đối số.
    Nếu lệnh chỉ có flags và 1 pattern tìm kiếm nhưng hoàn toàn không có target path,
    tự động append '.' làm target path mặc định để ngăn chặn việc ripgrep/grep rơi vào chế độ đọc STDIN stream.
    """
    if isinstance(cmd, str):
        cmd_clean = cmd.strip()
        if not cmd_clean:
            return cmd
        try:
            tokens = shlex.split(cmd_clean, posix=(os.name != "nt"))
        except Exception:
            tokens = cmd_clean.split()
        if not tokens:
            return cmd
        exe = Path(tokens[0]).name.lower()
        if exe in ("rg", "grep", "rg.exe", "grep.exe"):
            if _is_stream_missing_target_path(tokens[1:]):
                return f"{cmd_clean} ."
        return cmd
    elif isinstance(cmd, (list, tuple)):
        if not cmd:
            return cmd
        exe = Path(cmd[0]).name.lower()
        if exe in ("rg", "grep", "rg.exe", "grep.exe"):
            tokens = list(cmd[1:])
            if _is_stream_missing_target_path(tokens):
                return list(cmd) + ["."]
        return list(cmd)
    return cmd


def kill_process_tree(pid: int, cleanup_names: Optional[List[str]] = None) -> None:
    """Diệt triệt để cây tiến trình trên Windows / POSIX để chống zombie/orphan."""
    if os.name == "nt":
        # Windows: taskkill /F /T /PID diệt toàn bộ process tree
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5
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
                        check=False,
                        timeout=5
                    )
                except Exception:
                    pass
    else:
        # POSIX: Chỉ kill process group nếu khác process group của tiến trình hiện tại (tránh tự kill test runner)
        import signal
        try:
            target_pgid = os.getpgid(pid)
            current_pgid = os.getpgrp() if hasattr(os, "getpgrp") else os.getpid()
            if target_pgid != current_pgid:
                os.killpg(target_pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
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
    env: Optional[Dict[str, str]] = None,
    stdin: Any = subprocess.DEVNULL
) -> Dict[str, Any]:
    """
    Chạy lệnh với hard timeout và bảo vệ STDIN stream.
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

    if stdin is None:
        stdin = subprocess.DEVNULL

    cmd = sanitize_stream_command(cmd)

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=shell,
            cwd=cwd,
            env=env,
            encoding="utf-8",
            errors="replace",
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
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
                proc.kill()
            except Exception:
                pass
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
