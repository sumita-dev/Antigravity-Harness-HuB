#!/usr/bin/env python3
"""Run pytest with Windows temp-directory modes normalized for restricted runners."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path


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


def main() -> int:
    if os.name != "nt":
        print("This runner is intended for Windows; use python -m pytest on other platforms.", file=sys.stderr)
        return 2
    install_mode_normalizer()
    enable_subprocess_normalizer()
    args = sys.argv[1:]
    if not any(arg == "--basetemp" or arg.startswith("--basetemp=") for arg in args):
        temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or Path.cwd())
        args.extend(["--basetemp", str(temp_root / f"antigravity-pytest-{uuid.uuid4().hex}")])
    import pytest
    return int(pytest.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
