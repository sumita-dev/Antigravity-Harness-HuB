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
GATE_BUSY_EXIT_CODE = 75
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_GATE_WAIT_TIMEOUT = 45.0

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
                stdin=subprocess.DEVNULL,
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
                        stdin=subprocess.DEVNULL,
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


def _execute_popen(
    cmd: List[str] | str,
    timeout_sec: float,
    shell: bool,
    cwd: Optional[str],
    cleanup_names: Optional[List[str]],
    env: Optional[Dict[str, str]],
    stdin: Any,
    low_io_priority: bool,
    start_time: float,
) -> Dict[str, Any]:
    result = {
        "status": "SUCCESS",
        "exit_code": 0,
        "elapsed_sec": 0.0,
        "stdout": "",
        "stderr": "",
        "timed_out": False,
    }
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

        if low_io_priority:
            try:
                from harness.host_watch import apply_low_io_priority
                apply_low_io_priority(proc.pid)
            except Exception:
                pass

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


def run_command_with_timeout(
    cmd: List[str] | str,
    timeout_sec: float = DEFAULT_TIMEOUT_SECONDS,
    shell: bool = False,
    cwd: Optional[str] = None,
    cleanup_names: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    stdin: Any = subprocess.DEVNULL,
    low_io_priority: bool = True,
    gate_category: Optional[str] = None,
    wait_timeout_sec: float = DEFAULT_GATE_WAIT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Chạy lệnh với hard timeout, bảo vệ STDIN stream, hạ ưu tiên I/O và tùy chọn Host Gate slot.
    Trả về dict:
    {
        "status": "SUCCESS" | "TIMEOUT" | "ERROR" | "BUSY",
        "exit_code": int,
        "elapsed_sec": float,
        "stdout": str,
        "stderr": str,
        "timed_out": bool
    }
    """
    start_time = time.time()
    if stdin is None:
        stdin = subprocess.DEVNULL

    cmd = sanitize_stream_command(cmd)

    if gate_category is not None:
        try:
            from harness.host_watch import HostGateBusyError, acquire_host_slot, resolve_pool
        except ImportError:
            acquire_host_slot = None
            HostGateBusyError = None  # type: ignore[assignment,misc]
            resolve_pool = None

        if acquire_host_slot is not None and HostGateBusyError is not None and resolve_pool is not None:
            effective_env = dict(env) if env is not None else os.environ.copy()
            held_raw = str(effective_env.get("ANTIGRAVITY_HELD_POOLS", ""))
            held_pools = {p.strip() for p in held_raw.split(",") if p.strip()}
            target_pool = resolve_pool(gate_category, cmd=cmd)

            if target_pool is not None and target_pool in held_pools:
                effective_env["ANTIGRAVITY_SHIM_ACTIVE"] = "1"
                return _execute_popen(
                    cmd, timeout_sec, shell, cwd, cleanup_names,
                    effective_env, stdin, low_io_priority, start_time,
                )

            try:
                with acquire_host_slot(
                    gate_category,
                    wait_timeout=wait_timeout_sec,
                    cmd=cmd,
                ) as slot:
                    child_env = env
                    if slot is not None:
                        child_env = dict(effective_env)
                        child_env["ANTIGRAVITY_SHIM_ACTIVE"] = "1"
                        child_env["ANTIGRAVITY_HELD_POOLS"] = ",".join(sorted(held_pools | {slot.pool}))
                    return _execute_popen(
                        cmd, timeout_sec, shell, cwd, cleanup_names,
                        child_env, stdin, low_io_priority, start_time,
                    )
            except HostGateBusyError as exc:
                return {
                    "status": "BUSY",
                    "exit_code": GATE_BUSY_EXIT_CODE,
                    "elapsed_sec": round(time.time() - start_time, 3),
                    "stdout": "",
                    "stderr": f"[HOST-GATE-BUSY] {exc}",
                    "timed_out": False,
                    "gate_busy": True,
                }

    return _execute_popen(
        cmd, timeout_sec, shell, cwd, cleanup_names,
        env, stdin, low_io_priority, start_time,
    )


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
        "--host-gate",
        action="store_true",
        help="Bọc lệnh qua Host Gate concurrency slot (auto-classify nếu không chỉ định --gate-category)"
    )
    parser.add_argument(
        "--gate-category",
        choices=["auto", "io_heavy", "compute_io", "install", "worktree", "build", "test"],
        default=None,
        help="Phân loại pool cho Host Gate"
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=DEFAULT_GATE_WAIT_TIMEOUT,
        help=f"Thời gian chờ slot Host Gate tối đa (mặc định: {DEFAULT_GATE_WAIT_TIMEOUT}s)"
    )
    parser.add_argument(
        "--no-low-prio",
        action="store_true",
        help="Không hạ mức ưu tiên CPU/Disk I/O của tiến trình con"
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

    gate_category = args.gate_category or ("auto" if args.host_gate else None)

    res = run_command_with_timeout(
        cmd=cmd_to_run,
        timeout_sec=args.timeout,
        cleanup_names=args.cleanup_proc,
        low_io_priority=not args.no_low_prio,
        gate_category=gate_category,
        wait_timeout_sec=args.wait_timeout,
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
