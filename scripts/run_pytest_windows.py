#!/usr/bin/env python3
"""Run pytest with Windows temp-directory modes normalized for restricted runners and test tiering."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import List, Tuple

FAST_TIER_TESTS = [
    "tests/test_harness_doctor.py",
    "tests/test_skill_router_ranking.py",
    "tests/test_clean_state_cli.py",
    "tests/test_anti_hallucination.py",
    "tests/test_deterministic_rules.py",
]


def normalize_directory_mode(mode: int) -> int:
    """Keep pytest's private 0700 temp dirs traversable in sandboxed Windows CI."""
    return 0o777 if mode == 0o700 else mode


def install_mode_normalizer() -> None:
    original_mkdir = os.mkdir

    def normalized_mkdir(path, mode=0o777, *, dir_fd=None):
        mode = normalize_directory_mode(mode)
        if dir_fd is None:
            return original_mkdir(path, mode)
        return original_mkdir(path, mode, dir_fd=dir_fd)

    os.mkdir = normalized_mkdir


def enable_subprocess_normalizer() -> None:
    """Make child Python interpreters launched by tests inherit the same fix."""
    repo_root = Path(__file__).resolve().parents[1]
    shim_dir = Path(__file__).resolve().parent / "pytest_windows_shim"
    inherited = os.environ.get("PYTHONPATH", "")
    os.environ["PYTEST_WINDOWS_NORMALIZE_TEMP_MODE"] = "1"
    os.environ["PYTHONPATH"] = os.pathsep.join(
        item for item in (str(shim_dir), str(repo_root), inherited) if item
    )


def resolve_tier_args(raw_args: List[str]) -> Tuple[str, List[str]]:
    """Phân tách cấu hình tier (--tier fast/full hoặc --smoke) và cờ lệnh pytest."""
    tier = "full"
    filtered: List[str] = []
    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg == "--smoke":
            tier = "fast"
            i += 1
        elif arg == "--tier":
            if i + 1 < len(raw_args):
                tier = raw_args[i + 1].lower()
                i += 2
            else:
                i += 1
        elif arg.startswith("--tier="):
            tier = arg.split("=", 1)[1].lower()
            i += 1
        else:
            filtered.append(arg)
            i += 1

    if tier in ("fast", "smoke"):
        has_custom_test = any(
            arg.endswith(".py") or ("tests/" in arg or "tests\\" in arg)
            for arg in filtered
            if not arg.startswith("-")
        )
        if not has_custom_test:
            filtered.extend(FAST_TIER_TESTS)

    return tier, filtered


def main() -> int:
    if os.name != "nt":
        print("This runner is intended for Windows; use python -m pytest on other platforms.", file=sys.stderr)
        return 2
    install_mode_normalizer()
    enable_subprocess_normalizer()
    tier, args = resolve_tier_args(sys.argv[1:])
    if not any(arg == "--basetemp" or arg.startswith("--basetemp=") for arg in args):
        temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or Path.cwd())
        args.extend(["--basetemp", str(temp_root / f"antigravity-pytest-{uuid.uuid4().hex}")])
    import pytest
    return int(pytest.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
