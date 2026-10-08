"""Exercise the portable installer without touching the user's global profile."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell is unavailable")


def install(target):
    # Fail closed before invoking legacy installers that ignore destination flags.
    script = (REPO / "setup/setup.ps1").read_text(encoding="utf-8")
    assert "[string]$TargetDirectory" in script, "Portable target parameter is missing"
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(REPO / "setup/setup.ps1"), "-TargetDirectory", str(target),
         "-SkipSessionRestore"], capture_output=True, text=True, timeout=120,
    )


def test_portable_install_twice_preserves_config_and_runs_cli(tmp_path):
    target = tmp_path / "portable"
    target.mkdir()
    config = {"userSettings": {"themeMode": "CUSTOM", "enableTerminalSandbox": True},
              "plugins": {"private-plugin": {"enabled": True}}, "privateSetting": 42}
    (target / "config.json").write_text(json.dumps(config), encoding="utf-8")
    for _ in range(2):
        result = install(target)
        assert result.returncode == 0, result.stdout + result.stderr
    actual = json.loads((target / "config.json").read_text(encoding="utf-8-sig"))
    assert actual["userSettings"]["themeMode"] == "CUSTOM"
    assert actual["userSettings"]["enableTerminalSandbox"] is True
    assert actual["privateSetting"] == 42
    assert actual["plugins"]["private-plugin"]["enabled"] is True
    for path in ("run_harness.py", "docs/app-workflow-guide.md", "docs/marketing-workflow-guide.md",
                 "harness/app_workflow.py", "harness/marketing_workflow.py", "tests/test_harness_core.py"):
        assert (target / path).is_file(), path
    assert (target / "AGENTS.md").read_bytes() == (target / "GEMINI.md").read_bytes()
    assert not any((path / path.name).is_dir() for path in (target / "plugins").glob("*/skills/*"))
    env = dict(os.environ, HARNESS_BRAIN_DIR=str(tmp_path / "brain"), PYTHONDONTWRITEBYTECODE="1")
    cli = subprocess.run([sys.executable, str(target / "run_harness.py"), "--help"],
                         cwd=target, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert cli.returncode == 0, cli.stderr
    assert "--marketing-workflow" in cli.stdout


@pytest.mark.parametrize("target", [REPO, REPO.parent])
def test_install_rejects_repository_and_ancestor(target):
    result = install(target)
    assert result.returncode != 0
    assert "repository" in result.stderr.lower()


@pytest.mark.parametrize("directory", ["harness", "docs", "plugins", "tests"])
@pytest.mark.parametrize("nested", [False, True])
def test_install_rejects_target_inside_packaged_source(tmp_path, directory, nested):
    fixture = tmp_path / "repo"
    (fixture / "setup").mkdir(parents=True)
    for name in ("setup.ps1", "config.json"):
        shutil.copy2(REPO / "setup" / name, fixture / "setup" / name)
    source = fixture / directory
    source.mkdir()
    (source / "keep.txt").write_text("source", encoding="utf-8")
    target = source / "installer-probe" if nested else source
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(fixture / "setup/setup.ps1"), "-TargetDirectory", str(target), "-SkipSessionRestore"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode != 0
    assert "packaged source directory" in result.stderr.lower()
    assert not (target / "config.json").exists()
    assert (source / "keep.txt").read_text(encoding="utf-8") == "source"


def test_install_rejects_symlink_cleanup_target(tmp_path):
    target = tmp_path / "portable"
    outside = tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    try:
        (target / "harness").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires an available OS privilege")
    result = install(target)
    assert result.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "keep"
