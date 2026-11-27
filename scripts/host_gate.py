#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host Gate CLI & Anti-Recursion Shim Generator for Antigravity Harness Hub."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Optional, Sequence, Union

UnionPath = Union[str, Path]

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.host_watch import (  # noqa: E402
    DEFAULT_CACHE_MAX_AGE_DAYS,
    DEFAULT_CACHE_MAX_BYTES,
    DEFAULT_WAIT_TIMEOUT_SEC,
    audit_dev_caches,
    check_storage_advisories,
    get_state_dir,
    prune_dev_cache_lru,
    prune_stale_pytest_temps,
    sample_host_io,
)
from scripts.safe_task_runner import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    GATE_BUSY_EXIT_CODE,
    run_command_with_timeout,
)

DEFAULT_SHIM_TOOLS: tuple[str, ...] = (
    "pnpm",
    "npm",
    "yarn",
    "pip",
    "pytest",
    "cargo",
    "go",
    "tsc",
)

_SAFE_TOOL_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def strip_dir_from_path(path_value: str, shim_dir: Optional[UnionPath]) -> str:
    """Remove shim_dir from a PATH string safely across Windows and POSIX."""
    if not path_value:
        return ""
    if not shim_dir:
        return path_value
    target = os.path.normcase(os.path.normpath(os.path.abspath(str(shim_dir))))
    kept: list[str] = []
    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        norm_entry = os.path.normcase(os.path.normpath(os.path.abspath(entry)))
        if norm_entry == target:
            continue
        kept.append(entry)
    return os.pathsep.join(kept)


def resolve_real_tool(tool: str, shim_dir: Optional[UnionPath], env_path: Optional[str] = None) -> tuple[Optional[str], str]:
    """Strip shim_dir from PATH and resolve the real binary without cwd hijacking."""
    raw_path = env_path if env_path is not None else os.environ.get("PATH", "")
    clean_path = strip_dir_from_path(raw_path, shim_dir)
    shim_resolved = Path(shim_dir).resolve() if shim_dir else None

    if os.name == "nt":
        pathext = [
            ext.strip()
            for ext in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC").split(os.pathsep)
            if ext.strip()
        ]
        suffix = Path(tool).suffix.lower()
        candidates = [tool] if (suffix and any(suffix == ext.lower() for ext in pathext)) else [f"{tool}{ext}" for ext in pathext]
    else:
        candidates = [tool]

    for entry in clean_path.split(os.pathsep):
        if not entry:
            continue
        try:
            dir_path = Path(entry).resolve()
        except OSError:
            continue
        if not dir_path.is_dir():
            continue
        if shim_resolved is not None and dir_path == shim_resolved:
            continue
        for cand_name in candidates:
            cand = dir_path / cand_name
            try:
                if not cand.is_file():
                    continue
                if os.name != "nt" and not os.access(cand, os.X_OK):
                    continue
                if shim_resolved is not None and cand.resolve().parent == shim_resolved:
                    continue
                return str(cand), clean_path
            except OSError:
                continue

    return None, clean_path


def generate_shim_script(
    tool: str,
    *,
    python_exe: Optional[str] = None,
    gate_script: Optional[Path] = None,
    platform_name: Optional[str] = None,
) -> tuple[str, str]:
    """Return (filename, content) for a recursion-safe host_gate shim."""
    if not _SAFE_TOOL_RE.match(tool):
        raise ValueError(f"Unsafe shim tool name: {tool!r}")

    py_bin = python_exe or sys.executable
    gate_path = str((gate_script or Path(__file__)).resolve())
    plat = platform_name or ("windows" if os.name == "nt" else "posix")

    if plat == "windows":
        content = (
            "@echo off\r\n"
            "setlocal\r\n"
            'set "SHIM_DIR=%~dp0"\r\n'
            'if "%SHIM_DIR:~-1%"=="\\" set "SHIM_DIR=%SHIM_DIR:~0,-1%"\r\n'
            'if "%ANTIGRAVITY_SHIM_ACTIVE%"=="1" goto :bypass\r\n'
            'set "ANTIGRAVITY_SHIM_ACTIVE=1"\r\n'
            f'"{py_bin}" "{gate_path}" --shim-exec "{tool}" --shim-dir "%SHIM_DIR%" -- %*\r\n'
            "exit /b %ERRORLEVEL%\r\n"
            ":bypass\r\n"
            f'"{py_bin}" "{gate_path}" --shim-bypass "{tool}" --shim-dir "%SHIM_DIR%" -- %*\r\n'
            "exit /b %ERRORLEVEL%\r\n"
        )
        return f"{tool}.cmd", content

    q_tool = shlex.quote(tool)
    q_py = shlex.quote(py_bin)
    q_gate = shlex.quote(gate_path)
    content = (
        "#!/usr/bin/env sh\n"
        'SHIM_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'CLEAN_PATH=""\n'
        'OLD_IFS="$IFS"\n'
        'IFS=":"\n'
        "for p in $PATH; do\n"
        '  [ "$p" = "$SHIM_DIR" ] || [ "$p" = "$SHIM_DIR/" ] && continue\n'
        '  CLEAN_PATH="${CLEAN_PATH:+$CLEAN_PATH:}$p"\n'
        "done\n"
        'IFS="$OLD_IFS"\n'
        'export PATH="$CLEAN_PATH"\n'
        'if [ "${ANTIGRAVITY_SHIM_ACTIVE:-}" = "1" ]; then\n'
        f'  exec {q_tool} "$@"\n'
        "fi\n"
        "export ANTIGRAVITY_SHIM_ACTIVE=1\n"
        f'exec {q_py} {q_gate} --shim-exec {q_tool} --shim-dir "$SHIM_DIR" -- "$@"\n'
    )
    return tool, content


def install_shims(
    shim_dir: UnionPath,
    tools: Optional[Sequence[str]] = None,
    *,
    platform_name: Optional[str] = None,
) -> list[Path]:
    """Write host_gate shims into shim_dir and return created file paths."""
    target_dir = Path(shim_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    selected = list(tools) if tools else list(DEFAULT_SHIM_TOOLS)
    created: list[Path] = []
    for tool in selected:
        fname, content = generate_shim_script(tool, platform_name=platform_name)
        out_path = target_dir / fname
        out_path.write_text(content, encoding="utf-8")
        if os.name != "nt":
            try:
                out_path.chmod(0o755)
            except OSError:
                pass
        created.append(out_path)
    return created


def _print_result(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"{k}: {v}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Host Gate: Typed concurrency slot + low I/O priority wrapper & cache hygiene CLI."
    )
    parser.add_argument(
        "--category",
        choices=["auto", "io_heavy", "compute_io", "install", "worktree", "build", "test"],
        default="auto",
        help="Pool category for concurrency gating (default: auto)",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=DEFAULT_WAIT_TIMEOUT_SEC,
        help=f"Max seconds to wait for a busy slot before failing fast (default: {DEFAULT_WAIT_TIMEOUT_SEC})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Hard child execution timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--no-low-prio",
        action="store_true",
        help="Skip lowering child process I/O and CPU priority",
    )
    parser.add_argument("--status", action="store_true", help="Sample & display host I/O status")
    parser.add_argument("--prune-caches", action="store_true", help="Prune stale pytest temps and LRU Go cache")
    parser.add_argument("--dry-run", action="store_true", help="Preview pruning without deleting files")
    parser.add_argument("--install-shims", metavar="DIR", default=None, help="Install PATH shims into DIR")
    parser.add_argument("--shim", action="append", default=None, help="Tool name(s) to generate shims for")
    parser.add_argument("--state-dir", default=None, help="Override Host Watch state directory")
    parser.add_argument("--cache-dir", default=None, help="Override cache directory for --prune-caches")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--shim-exec", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--shim-bypass", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--shim-dir", default=None, help=argparse.SUPPRESS)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute (after --)")

    args = parser.parse_args(argv)

    if args.state_dir:
        os.environ["ANTIGRAVITY_HOST_WATCH_DIR"] = str(Path(args.state_dir))
    resolved_state = get_state_dir(args.state_dir)

    if args.status:
        telemetry = sample_host_io(state_dir=resolved_state)
        caches = audit_dev_caches()
        advisories = check_storage_advisories(Path.cwd())
        payload = {
            "telemetry": telemetry,
            "caches": caches,
            "advisories": advisories,
        }
        if args.json:
            _print_result(payload, True)
        else:
            print(
                f"Host I/O Level: {telemetry['level']} | "
                f"EMA={telemetry['ema_bytes_per_sec'] / (1024 * 1024):.2f} MB/s | "
                f"IOPS={telemetry['ema_iops']:.1f} | Lat={telemetry['ema_avg_latency_ms']:.2f} ms | "
                f"Slots={telemetry['active_slots']}"
            )
            print(
                f"Caches: pytest_temps={caches['pytest_temp_count']} (stale={caches['pytest_stale_count']}), "
                f"go_cache={caches['go_cache_bytes'] / (1024**3):.2f} GB"
            )
            for adv in advisories:
                print(f"[ADVISORY] {adv['message']}")
        return 0

    if args.prune_caches:
        pytest_res = prune_stale_pytest_temps(dry_run=args.dry_run)
        audit = audit_dev_caches(go_cache_dir=args.cache_dir)
        go_target = args.cache_dir or audit.get("go_cache_dir")
        go_res = None
        if go_target and Path(go_target).is_dir():
            go_res = prune_dev_cache_lru(
                go_target,
                max_bytes=DEFAULT_CACHE_MAX_BYTES,
                max_age_days=DEFAULT_CACHE_MAX_AGE_DAYS,
                dry_run=args.dry_run,
            )
        payload = {
            "dry_run": args.dry_run,
            "pytest_temps": pytest_res,
            "go_cache": go_res,
        }
        if args.json:
            _print_result(payload, True)
        else:
            print(
                f"Pytest temps ({'dry-run' if args.dry_run else 'pruned'}): "
                f"removed={pytest_res['removed_count']} freed={pytest_res['freed_bytes']} bytes"
            )
            if go_res is not None:
                print(
                    f"Go cache ({'dry-run' if args.dry_run else 'pruned'}): "
                    f"deleted={go_res['deleted_count']} freed={go_res['freed_bytes']} bytes"
                )
        return 0

    if args.install_shims or args.shim:
        target_dir = Path(args.install_shims) if args.install_shims else (resolved_state / "shims")
        created = install_shims(target_dir, tools=args.shim)
        payload = {
            "shim_dir": str(target_dir.resolve()),
            "shims": [str(p) for p in created],
        }
        if args.json:
            _print_result(payload, True)
        else:
            print(f"Installed {len(created)} shims in {payload['shim_dir']}:")
            for p in created:
                print(f"  - {p.name}")
        return 0

    cmd_to_run = list(args.command or [])
    if cmd_to_run and cmd_to_run[0] == "--":
        cmd_to_run = cmd_to_run[1:]

    if args.shim_bypass or args.shim_exec:
        tool = args.shim_bypass or args.shim_exec
        real_bin, clean_path = resolve_real_tool(tool, args.shim_dir)
        if not real_bin:
            msg = f"[HOST-GATE-SHIM] Real binary for '{tool}' not found outside shim dir '{args.shim_dir}'."
            if args.json:
                _print_result({"status": "ERROR", "exit_code": 127, "stderr": msg}, True)
            else:
                print(msg, file=sys.stderr)
            return 127
        child_env = os.environ.copy()
        child_env["PATH"] = clean_path
        child_env["ANTIGRAVITY_SHIM_ACTIVE"] = "1"
        gate_cat = None if args.shim_bypass else args.category
        res = run_command_with_timeout(
            cmd=[real_bin, *cmd_to_run],
            timeout_sec=args.timeout,
            env=child_env,
            low_io_priority=not args.no_low_prio,
            gate_category=gate_cat,
            wait_timeout_sec=args.wait_timeout,
        )
    else:
        if not cmd_to_run:
            parser.print_help(file=sys.stderr)
            return 1
        res = run_command_with_timeout(
            cmd=cmd_to_run,
            timeout_sec=args.timeout,
            low_io_priority=not args.no_low_prio,
            gate_category=args.category,
            wait_timeout_sec=args.wait_timeout,
        )

    if args.json:
        _print_result(res, True)
    else:
        if res.get("stdout"):
            print(res["stdout"], end="")
        if res.get("stderr"):
            print(res["stderr"], file=sys.stderr, end="")
        if res.get("exit_code") == GATE_BUSY_EXIT_CODE and "[HOST-GATE-BUSY]" not in (res.get("stderr") or ""):
            print("[HOST-GATE-BUSY] Concurrency slot exhausted.", file=sys.stderr)

    return int(res.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
