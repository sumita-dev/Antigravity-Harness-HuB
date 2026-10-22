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


def install(target, extra_args=None, extra_env=None):
    # Fail closed before invoking legacy installers that ignore destination flags.
    script = (REPO / "setup/setup.ps1").read_text(encoding="utf-8")
    assert "[string]$TargetDirectory" in script, "Portable target parameter is missing"
    assert "[switch]$SkipWatcher" in script, "SkipWatcher parameter is missing"
    cmd = [
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(REPO / "setup/setup.ps1"), "-TargetDirectory", str(target),
        "-SkipSessionRestore"
    ]
    if extra_args:
        cmd.extend(extra_args)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
        env=env,
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
    assert "GEMINI.md" in (target / "AGENTS.md").read_text(encoding="utf-8")
    assert not any((path / path.name).is_dir() for path in (target / "plugins").glob("*/skills/*"))
    env = dict(os.environ, HARNESS_BRAIN_DIR=str(tmp_path / "brain"), PYTHONDONTWRITEBYTECODE="1")
    cli = subprocess.run([sys.executable, str(target / "run_harness.py"), "--help"],
                         cwd=target, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert cli.returncode == 0, cli.stderr
    assert "--marketing-workflow" in cli.stdout


def test_install_preserves_unrelated_user_plugin(tmp_path):
    target = tmp_path / "portable-with-user-plugin"
    user_plugin = target / "plugins" / "user-plugin" / "plugin.json"
    user_plugin.parent.mkdir(parents=True)
    original = b'{"name":"user-plugin","keep":true}\n'
    user_plugin.write_bytes(original)

    result = install(target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert user_plugin.read_bytes() == original
    assert (target / "plugins" / "code" / "plugin.json").is_file()


def test_install_rejects_unowned_plugin_name_conflict_without_mutation(tmp_path):
    target = tmp_path / "portable-plugin-conflict"
    conflicting = target / "plugins" / "code" / "plugin.json"
    conflicting.parent.mkdir(parents=True)
    original = b'{"name":"private-code-plugin","private":true}\n'
    conflicting.write_bytes(original)
    config = target / "config.json"
    config.write_text('{"keep":true}', encoding="utf-8")

    result = install(target)

    assert result.returncode != 0
    assert "conflict" in (result.stdout + result.stderr).lower()
    assert conflicting.read_bytes() == original
    assert config.read_text(encoding="utf-8") == '{"keep":true}'


def test_second_install_updates_only_owned_files_and_preserves_user_files(tmp_path):
    target = tmp_path / "portable-update"
    assert install(target).returncode == 0
    managed = target / "plugins" / "code" / "plugin.json"
    managed.write_text('{"locally-edited":true}', encoding="utf-8")
    user_file = target / "plugins" / "code" / "user-data.txt"
    user_file.write_text("keep me", encoding="utf-8")
    unrelated = target / "plugins" / "user-plugin" / "plugin.json"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text('{"name":"user-plugin"}', encoding="utf-8")
    obsolete = target / "plugins" / "code" / "old-managed.txt"
    obsolete.write_text("harness old", encoding="utf-8")
    manifest = json.loads((target / ".harness-hub-managed.json").read_text(encoding="utf-8"))
    manifest["files"]["plugins/code/old-managed.txt"] = __import__("hashlib").sha256(b"harness old").hexdigest()
    (target / ".harness-hub-managed.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = install(target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(managed.read_text(encoding="utf-8")) == json.loads((REPO / "plugins/code/plugin.json").read_text(encoding="utf-8"))
    assert user_file.read_text(encoding="utf-8") == "keep me"
    assert unrelated.read_text(encoding="utf-8") == '{"name":"user-plugin"}'
    assert not obsolete.exists()


def test_install_failure_during_commit_rolls_back_existing_files(tmp_path):
    target = tmp_path / "portable-rollback"
    assert install(target).returncode == 0
    managed = target / "plugins" / "code" / "plugin.json"
    managed.write_text('{"updated":true}', encoding="utf-8")
    prior = managed.read_bytes()
    config = target / "config.json"
    config_before = config.read_bytes()
    manifest_before = (target / ".harness-hub-managed.json").read_bytes()

    result = install(target, extra_env={"HARNESS_SETUP_TEST_FAIL_AFTER_COPY": "1"})

    assert result.returncode != 0
    assert managed.read_bytes() == prior
    assert config.read_bytes() == config_before
    assert (target / ".harness-hub-managed.json").read_bytes() == manifest_before


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


def test_setup_accepts_skip_watcher_flag(tmp_path):
    target = tmp_path / "portable_skip_watcher"
    target.mkdir()
    result = install(target, extra_args=["-SkipWatcher"])
    assert result.returncode == 0, result.stderr


def test_install_preserves_vietnamese_unicode_in_custom_instructions(tmp_path):
    target = tmp_path / "portable_unicode"
    target.mkdir()

    # 1. Fresh install inherits default customInstructions with intact Vietnamese Unicode
    res = install(target, extra_args=["-SkipWatcher"])
    assert res.returncode == 0, res.stdout + res.stderr

    default_config = json.loads((REPO / "setup/config.json").read_text(encoding="utf-8"))
    expected_default_instructions = default_config["userSettings"]["customInstructions"]

    target_config_path = target / "config.json"
    assert not target_config_path.read_bytes().startswith(b"\xef\xbb\xbf"), "Config file should not have UTF-8 BOM"

    installed_config = json.loads(target_config_path.read_text(encoding="utf-8-sig"))
    actual_instructions = installed_config["userSettings"]["customInstructions"]
    assert actual_instructions == expected_default_instructions
    assert "Sếp" in actual_instructions
    assert "tiếng Việt" in actual_instructions
    assert "Xưng hô" in actual_instructions
    assert "XÆ°ng" not in actual_instructions
    assert "Sáº¿p" not in actual_instructions

    # 2. Existing custom Vietnamese instructions are preserved without Mojibake on subsequent install
    custom_vietnamese = "1/ Chỉ thị tuỳ biến: Luôn gọi Sếp là Anh, báo cáo trung thực và chính xác."
    installed_config["userSettings"]["customInstructions"] = custom_vietnamese
    target_config_path.write_text(json.dumps(installed_config, ensure_ascii=False, indent=2), encoding="utf-8")

    res2 = install(target, extra_args=["-SkipWatcher"])
    assert res2.returncode == 0, res2.stdout + res2.stderr

    assert not target_config_path.read_bytes().startswith(b"\xef\xbb\xbf"), "Config file should not have UTF-8 BOM after update"
    updated_config = json.loads(target_config_path.read_text(encoding="utf-8-sig"))
    assert updated_config["userSettings"]["customInstructions"] == custom_vietnamese


