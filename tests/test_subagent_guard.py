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
