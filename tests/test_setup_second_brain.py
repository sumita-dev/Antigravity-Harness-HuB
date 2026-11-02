"""tests/test_setup_second_brain.py

Unit tests cho script bootstrap_vault.py trong skill setup-second-brain.
Đảm bảo 100% Pass và tuân thủ các nguyên tắc:
1. Tạo đầy đủ 11 thư mục Evergreen tiêu chuẩn.
2. Tạo đầy đủ các tệp lõi và bộ 4 templates.
3. Không ghi đè các file có sẵn (đặc biệt wiki/_session-handoff.md) khi force=False.
4. Hỗ trợ --dry-run, --json, CLI options.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_SCRIPT = (
    REPO_ROOT
    / "plugins"
    / "second-brain"
    / "skills"
    / "setup-second-brain"
    / "scripts"
    / "bootstrap_vault.py"
)

_spec = importlib.util.spec_from_file_location("bootstrap_vault", BOOTSTRAP_SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load bootstrap_vault from {BOOTSTRAP_SCRIPT}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_vault"] = _mod
_spec.loader.exec_module(_mod)

VaultBootstrapper = _mod.VaultBootstrapper
bootstrap_main = _mod.main
STANDARD_DIRECTORIES = _mod.STANDARD_DIRECTORIES


def test_bootstrap_empty_vault(tmp_path: Path):
    """Kiểm tra khởi tạo vault trống hoàn toàn."""
    vault_dir = tmp_path / "MyVault"
    bootstrapper = VaultBootstrapper(vault_path=vault_dir)
    res = bootstrapper.bootstrap()

    assert res["status"] == "SUCCESS"
    assert len(res["created_dirs"]) == len(STANDARD_DIRECTORIES)
    assert len(res["created_files"]) == 8
    assert len(res["skipped_files"]) == 0

    # Kiểm tra các thư mục
    for d in STANDARD_DIRECTORIES:
        assert (vault_dir / d).is_dir(), f"Thư mục {d} chưa được tạo!"

    # Kiểm tra các tệp lõi
    assert (vault_dir / "AI_RULES.md").is_file()
    assert (vault_dir / "wiki" / "index.md").is_file()
    assert (vault_dir / "wiki" / "log.md").is_file()
    assert (vault_dir / "wiki" / "session.md").is_file()

    # Kiểm tra templates
    assert (vault_dir / "templates" / "source-note.md").is_file()
    assert (vault_dir / "templates" / "topic.md").is_file()
    assert (vault_dir / "templates" / "decision.md").is_file()
    assert (vault_dir / "templates" / "lesson.md").is_file()


def test_bootstrap_preserve_existing_files(tmp_path: Path):
    """Kiểm tra an toàn: Không ghi đè file có sẵn (đặc biệt _session-handoff.md và custom AI_RULES)."""
    vault_dir = tmp_path / "ExistingVault"
    wiki_dir = vault_dir / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    handoff_file = wiki_dir / "_session-handoff.md"
    handoff_content = "# Preserved Handoff Note\nDo not overwrite!"
    handoff_file.write_text(handoff_content, encoding="utf-8")

    custom_rules = vault_dir / "AI_RULES.md"
    custom_rules_content = "# User Custom AI Rules\nPreserve this!"
    custom_rules.write_text(custom_rules_content, encoding="utf-8")

    bootstrapper = VaultBootstrapper(vault_path=vault_dir, force=False)
    res = bootstrapper.bootstrap()

    # Kiểm tra file handoff không suy chuyển
    assert handoff_file.read_text(encoding="utf-8") == handoff_content
    # Kiểm tra AI_RULES.md bị bỏ qua không ghi đè
    assert custom_rules.read_text(encoding="utf-8") == custom_rules_content
    assert "AI_RULES.md" in res["skipped_files"]


def test_bootstrap_dry_run(tmp_path: Path):
    """Kiểm tra cờ dry-run không ghi bất kỳ thư mục hay file nào lên đĩa."""
    vault_dir = tmp_path / "DryRunVault"
    bootstrapper = VaultBootstrapper(vault_path=vault_dir, dry_run=True)
    res = bootstrapper.bootstrap()

    assert res["dry_run"] is True
    assert len(res["created_dirs"]) == len(STANDARD_DIRECTORIES)
    assert len(res["created_files"]) == 8
    assert not vault_dir.exists(), "Dry-run không được tạo thư mục trên đĩa!"


def test_bootstrap_cli_json(tmp_path: Path, capsys):
    """Kiểm tra CLI format JSON."""
    vault_dir = tmp_path / "CLIVault"
    ret = bootstrap_main(["--vault-path", str(vault_dir), "--json"])
    assert ret == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "SUCCESS"
    assert Path(data["vault_path"]) == vault_dir.resolve()
