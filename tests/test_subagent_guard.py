#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_subagent_guard.py

Kiểm thử hệ thống SubagentGuard & Quy chuẩn Dead-man's Switch Watchdog:
1. Phân tầng timeout: Fast-tier (45s) vs Full-tier (240s).
2. Kiểm tra quy định: Dead-man's Switch chỉ áp dụng cho CLI run_command, cấm schedule trên invoke_subagent.
3. Vệ sinh tiến trình mồ côi và dọn dẹp orphan locks.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from harness.subagent_guard import (
    FAST_TIER_TIMEOUT,
    FULL_TIER_TIMEOUT,
    SubAgentState,
    SubagentGuard,
    SubagentInfo,
    cleanup_triad_cycle,
    get_deadman_timeout,
    list_idle_subagents,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestSubagentGuardIsolated:
    def test_timeout_thresholds(self):
        assert FAST_TIER_TIMEOUT == 45
        assert FULL_TIER_TIMEOUT == 240
        assert get_deadman_timeout("fast") == 45
        assert get_deadman_timeout("smoke") == 45
        assert get_deadman_timeout("full") == 240
        assert get_deadman_timeout("batch") == 240

    def test_subagent_guard_initialization(self):
        guard = SubagentGuard(repo_root=REPO_ROOT)
        assert guard.repo_root == REPO_ROOT

    def test_subagent_info_structure(self):
        info = SubagentInfo(pid=1234, name="worker_proc", status="running")
        d = info.to_dict()
        assert d["pid"] == 1234
        assert d["name"] == "worker_proc"
        assert d["status"] == "running"
        assert SubAgentState is SubagentInfo

    def test_list_idle_and_active_subagents(self):
        guard = SubagentGuard(repo_root=REPO_ROOT)
        active = guard.list_active_subagents()
        assert isinstance(active, list)
        idle = list_idle_subagents()
        assert isinstance(idle, list)

    def test_cleanup_subagents_dry_run(self):
        guard = SubagentGuard(repo_root=REPO_ROOT)
        result = guard.cleanup_subagents(dry_run=True)
        assert result["dry_run"] is True
        assert isinstance(result["terminated"], list)
        assert isinstance(result["cleaned_locks"], list)

    def test_orphan_lock_detection_and_cleanup(self, tmp_path):
        guard = SubagentGuard(repo_root=tmp_path)
        brain_dir = tmp_path / ".brain"
        brain_dir.mkdir(parents=True, exist_ok=True)
        lock_file = brain_dir / "orphan_job.lock"
        lock_file.write_text("lock_data", encoding="utf-8")

        locks = guard.scan_orphan_locks()
        assert lock_file in locks

        cleaned = guard.cleanup_subagents(dry_run=False)["cleaned_locks"]
        assert str(lock_file) in cleaned
        assert not lock_file.exists()

    def test_deadman_switch_rule_docs_consistency(self):
        """Kiểm chứng quy định Dead-man's switch trong GEMINI.md và README.md:
        - Chỉ áp dụng cho run_command.
        - Cấm trên invoke_subagent.
        """
        gemini_md = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")
        assert "run_command" in gemini_md
        assert "invoke_subagent" in gemini_md
        assert "TUYỆT ĐỐI CẤM gọi `schedule` timer khi kích hoạt SubAgent" in gemini_md

        readme_md = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "TUYỆT ĐỐI CẤM" in readme_md or "Tuyệt đối cấm trên SubAgent" in readme_md
        assert "invoke_subagent" in readme_md

    def test_cleanup_triad_cycle_logic(self, tmp_path):
        guard = SubagentGuard(repo_root=tmp_path)
        brain_dir = tmp_path / ".brain"
        brain_dir.mkdir(parents=True, exist_ok=True)
        lock_file = brain_dir / "cycle_test.lock"
        lock_file.write_text("locked", encoding="utf-8")

        res = guard.cleanup_triad_cycle(cycle_id="test_c1", dry_run=False)
        assert res["cycle_id"] == "test_c1"
        assert res["status"] == "CLEAN"
        assert str(lock_file) in res["cleaned_locks"]
        assert not lock_file.exists()

        # Module-level function
        res_mod = cleanup_triad_cycle(cycle_id="test_c2", dry_run=True, repo_root=tmp_path)
        assert res_mod["cycle_id"] == "test_c2"
        assert res_mod["dry_run"] is True

    def test_lifecycle_closure_rule_docs_consistency(self):
        gemini_md = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")
        assert "SubAgent Lifecycle Closure Invariant" in gemini_md
        assert 'manage_subagents(Action="kill_all")' in gemini_md
        assert "cleanup_triad_cycle()" in gemini_md

        global_gemini_md = (REPO_ROOT / "configs" / "global_gemini.md").read_text(encoding="utf-8")
        assert "SubAgent Lifecycle Closure Invariant" in global_gemini_md
        assert 'manage_subagents(Action="kill_all")' in global_gemini_md

        readme_md = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "SubAgent Lifecycle Closure Invariant" in readme_md
        assert 'manage_subagents(Action="kill_all")' in readme_md

    def test_session_rollover_enforcer_docs_consistency(self):
        gemini_md = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")
        assert "Session Rollover Enforcer" in gemini_md
        assert "_session-handoff.md" in gemini_md

        global_gemini_md = (REPO_ROOT / "configs" / "global_gemini.md").read_text(encoding="utf-8")
        assert "Session Rollover Enforcer" in global_gemini_md
        assert "_session-handoff.md" in global_gemini_md

        readme_md = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "Session Rollover Enforcer" in readme_md
        assert "_session-handoff.md" in readme_md

    def test_workspace_isolation_rule_docs_consistency(self):
        gemini_md = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")
        assert "Workspace Isolation Invariant" in gemini_md
        assert "Workspace: 'branch'" in gemini_md

        global_gemini_md = (REPO_ROOT / "configs" / "global_gemini.md").read_text(encoding="utf-8")
        assert "Workspace Isolation Invariant" in global_gemini_md
        assert "Workspace: 'branch'" in global_gemini_md

        readme_md = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "Workspace Isolation Invariant" in readme_md
        assert "Workspace: 'branch'" in readme_md

    def test_cli_cleanup_argument(self, monkeypatch, capsys):
        import sys
        from harness.subagent_guard import main

        monkeypatch.setattr(sys, "argv", ["subagent_guard.py", "--cleanup", "--dry-run", "--json"])
        ret = main()
        assert ret == 0
        captured = capsys.readouterr()
        assert "terminated" in captured.out
        assert "cleaned_locks" in captured.out

        monkeypatch.setattr(sys, "argv", ["subagent_guard.py", "--cleanup-triad", "--cycle-id", "triad_001", "--dry-run", "--json"])
        ret2 = main()
        assert ret2 == 0
        captured2 = capsys.readouterr()
        assert "triad_001" in captured2.out
        assert "CLEAN" in captured2.out

    def test_cli_tier_and_scan_arguments(self, monkeypatch, capsys):
        import sys
        from harness.subagent_guard import main

        monkeypatch.setattr(sys, "argv", ["subagent_guard.py", "--tier", "fast", "--json"])
        ret = main()
        assert ret == 0
        captured = capsys.readouterr()
        assert "deadman_timeout_seconds" in captured.out
        assert "45" in captured.out
