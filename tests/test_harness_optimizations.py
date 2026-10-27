#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_harness_optimizations.py

Bộ kiểm thử nghiệm thu 4 Trụ Cột Tối Ưu Hóa Vận Hành Antigravity Harness Hub:
1. Trụ Cột 1: Cỗ Máy Giám Sát Phiên & Tự Động Handoff (session_guard.py & doctor integration)
2. Trụ Cột 2: Phân Tầng Test Suite (Test Tiering & Dead-man Switch Động)
3. Trụ Cột 3: Vệ Sinh Tiến Trình SubAgent (SubAgent Hygiene & Process Guard)
4. Trụ Cột 4: Scaffolding Scripts Tất Định Cho 3 Kỹ Năng Nhạy Cảm (Dune Invariant)
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

from harness.subagent_guard import (
    SubAgentState,
    SubagentGuard,
    SubagentInfo,
    get_deadman_timeout,
    list_idle_subagents,
)
from scripts.run_pytest_windows import FAST_TIER_TESTS, resolve_tier_args
from scripts.session_guard import (
    RED_THRESHOLD_BYTES,
    RED_THRESHOLD_TURNS,
    YELLOW_THRESHOLD_BYTES,
    YELLOW_THRESHOLD_TURNS,
    count_transcript_turns,
    evaluate_session_health,
    generate_handoff_content,
    write_handoff_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module_from_path(module_name: str, path: Path):
    import sys
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load scaffolding modules dynamically (directories contain hyphens)
mod_db = load_module_from_path(
    "lint_migration_safety",
    REPO_ROOT / "plugins/code/skills/database-migrations/scripts/lint_migration_safety.py",
)
lint_sql_content = mod_db.lint_sql_content
lint_python_migration_content = mod_db.lint_python_migration_content

mod_tamper = load_module_from_path(
    "audit_desktop_binary_tamper",
    REPO_ROOT / "plugins/code/skills/reverse-lab/scripts/audit_desktop_binary_tamper.py",
)
audit_tamper_content = mod_tamper.audit_tamper_content

mod_loop = load_module_from_path(
    "check_loop_thresholds",
    REPO_ROOT / "plugins/code/skills/loop-circuit-breaker/scripts/check_loop_thresholds.py",
)
check_loop_content = mod_loop.check_loop_content


# =============================================================================
# 1. TRỤ CỘT 1: SESSION GUARD & DOCTOR INTEGRATION
# =============================================================================
class TestSessionGuard:
    def test_evaluate_session_health_green(self):
        status, msg = evaluate_session_health(size_bytes=100 * 1024, turns=20)
        assert status == "GREEN"
        assert "an toàn" in msg

    def test_evaluate_session_health_yellow_by_size(self):
        status, msg = evaluate_session_health(size_bytes=YELLOW_THRESHOLD_BYTES + 1024, turns=20)
        assert status == "YELLOW"
        assert "Dung lượng transcript" in msg

    def test_evaluate_session_health_yellow_by_turns(self):
        status, msg = evaluate_session_health(size_bytes=50 * 1024, turns=YELLOW_THRESHOLD_TURNS + 1)
        assert status == "YELLOW"
        assert "Số turns" in msg

    def test_evaluate_session_health_red_by_size(self):
        status, msg = evaluate_session_health(size_bytes=RED_THRESHOLD_BYTES + 2048, turns=20)
        assert status == "RED"
        assert "vượt trần RED" in msg

    def test_evaluate_session_health_red_by_turns(self):
        status, msg = evaluate_session_health(size_bytes=50 * 1024, turns=RED_THRESHOLD_TURNS + 1)
        assert status == "RED"
        assert "Số turns" in msg

    def test_count_transcript_turns(self, tmp_path):
        transcript_file = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps({"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "Xin chào"}),
            json.dumps({"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Chào Sếp"}),
            json.dumps({"step_index": 2, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "Làm tiếp đi"}),
            json.dumps({"step_index": 3, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Đang làm"}),
        ]
        transcript_file.write_text("\n".join(lines), encoding="utf-8")

        total_steps, user_turns = count_transcript_turns(transcript_file)
        assert total_steps == 4
        assert user_turns == 2

    def test_auto_handoff_generation_and_write(self, tmp_path):
        target_file = tmp_path / "wiki" / "_session-handoff.md"
        info = {
            "size_bytes": 260 * 1024,
            "turns": 45,
            "transcript_path": str(tmp_path / "test.jsonl"),
            "status": "RED",
        }
        content = generate_handoff_content(info)
        assert "# Session Handoff" in content
        assert "Session Rollover Gate" in content
        assert "active" in content

        written = write_handoff_file(content, target_path=target_file)
        assert written == target_file
        assert target_file.exists()
        saved_text = target_file.read_text(encoding="utf-8")
        assert "Session Rollover Gate" in saved_text

    def test_doctor_session_health_warning_does_not_fail_doctor(self):
        from scripts.harness_doctor import HarnessDoctor
        doctor = HarnessDoctor()
        issues = doctor.check_pillar_5_hygiene()
        session_issues = [i for i in issues if i.code == "WARN_SESSION_ROLLOVER"]
        for issue in session_issues:
            assert issue.severity == "WARN"


# =============================================================================
# 2. TRỤ CỘT 2: TEST TIERING & DEAD-MAN SWITCH
# =============================================================================
class TestTestTieringAndDeadmanSwitch:
    def test_resolve_tier_args_fast(self):
        tier, args = resolve_tier_args(["--tier", "fast", "-q"])
        assert tier == "fast"
        assert "-q" in args
        for t in FAST_TIER_TESTS:
            assert t in args

    def test_resolve_tier_args_smoke(self):
        tier, args = resolve_tier_args(["--smoke", "-v"])
        assert tier == "fast"
        assert "-v" in args
        for t in FAST_TIER_TESTS:
            assert t in args

    def test_resolve_tier_args_full(self):
        tier, args = resolve_tier_args(["--tier", "full", "-q"])
        assert tier == "full"
        assert args == ["-q"]

    def test_resolve_tier_preserves_custom_tests(self):
        tier, args = resolve_tier_args(["--tier", "fast", "tests/custom_test.py"])
        assert tier == "fast"
        assert "tests/custom_test.py" in args
        assert len(args) == 1

    def test_get_deadman_timeout(self):
        assert get_deadman_timeout("fast") == 45
        assert get_deadman_timeout("smoke") == 45
        assert get_deadman_timeout("full") == 240
        assert get_deadman_timeout("default") == 240

    def test_fast_tier_tests_duration_under_25_seconds(self):
        start = time.time()
        for t in FAST_TIER_TESTS:
            assert (REPO_ROOT / t).exists(), f"File test cốt lõi không tồn tại: {t}"
        elapsed = time.time() - start
        assert elapsed < 25.0


# =============================================================================
# 3. TRỤ CỘT 3: SUBAGENT HYGIENE & PROCESS GUARD
# =============================================================================
class TestSubagentGuard:
    def test_subagent_guard_initialization(self):
        guard = SubagentGuard()
        assert guard.repo_root.exists()

    def test_list_active_subagents_returns_list(self):
        guard = SubagentGuard()
        active = guard.list_active_subagents()
        assert isinstance(active, list)

    def test_detect_orphaned_subagents_returns_list(self):
        guard = SubagentGuard()
        orphaned = guard.detect_orphaned_subagents()
        assert isinstance(orphaned, list)

    def test_cleanup_subagents_dry_run(self):
        guard = SubagentGuard()
        res = guard.cleanup_subagents(dry_run=True)
        assert res["dry_run"] is True
        assert isinstance(res["terminated"], list)
        assert isinstance(res["cleaned_locks"], list)

    def test_cleanup_triad_cycle(self):
        guard = SubagentGuard()
        cycle_res = guard.cleanup_triad_cycle("test-cycle-1", dry_run=True)
        assert cycle_res["cycle_id"] == "test-cycle-1"
        assert cycle_res["status"] == "CLEAN"

    def test_scan_orphan_locks_detects_created_lock(self, tmp_path):
        guard = SubagentGuard(repo_root=tmp_path)
        brain_dir = tmp_path / ".brain"
        brain_dir.mkdir(parents=True, exist_ok=True)
        lock_file = brain_dir / "test_task.lock"
        lock_file.write_text("locked", encoding="utf-8")

        locks = guard.scan_orphan_locks()
        assert lock_file in locks

    def test_subagent_aliases_and_list_idle(self):
        # Kiểm tra alias SubAgentState và SubagentInfo tương đương
        assert SubAgentState is SubagentInfo
        idle = list_idle_subagents()
        assert isinstance(idle, list)


# =============================================================================
# 4. TRỤ CỘT 4: SCAFFOLDING SCRIPTS (DUNE INVARIANT)
# =============================================================================
class TestScaffoldingScripts:
    # 4.1 Database Migration Safety Linter
    def test_lint_sql_drop_table(self):
        sql = "DROP TABLE users;"
        violations = lint_sql_content(sql)
        assert len(violations) == 1
        assert violations[0].rule_code == "ERR_DROP_TABLE"

    def test_lint_sql_drop_column(self):
        sql = "ALTER TABLE users DROP COLUMN email;"
        violations = lint_sql_content(sql)
        assert any(v.rule_code == "ERR_DROP_COLUMN" for v in violations)

    def test_lint_sql_truncate_table(self):
        sql = "TRUNCATE TABLE logs;"
        violations = lint_sql_content(sql)
        assert any(v.rule_code == "ERR_TRUNCATE_TABLE" for v in violations)

    def test_lint_sql_not_null_without_default(self):
        sql_bad = "ALTER TABLE accounts ADD COLUMN status VARCHAR(20) NOT NULL;"
        violations_bad = lint_sql_content(sql_bad)
        assert any(v.rule_code == "ERR_NOT_NULL_WITHOUT_DEFAULT" for v in violations_bad)

        sql_good = "ALTER TABLE accounts ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';"
        violations_good = lint_sql_content(sql_good)
        assert len(violations_good) == 0

    def test_lint_python_migration_downgrade_missing(self):
        py_code = """
def upgrade():
    op.create_table('test')
"""
        violations = lint_python_migration_content(py_code)
        assert any(v.rule_code == "ERR_MISSING_DOWNGRADE" for v in violations)

    def test_lint_python_migration_downgrade_empty(self):
        py_code = """
def upgrade():
    op.create_table('test')

def downgrade():
    pass
"""
        violations = lint_python_migration_content(py_code)
        assert any(v.rule_code == "ERR_EMPTY_DOWNGRADE" for v in violations)

    # 4.2 Reverse Lab Desktop Tamper Auditor
    def test_audit_tamper_private_key(self):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        findings = audit_tamper_content(content)
        assert any(f.code == "ERR_HARDCODED_PRIVATE_KEY" for f in findings)

    def test_audit_tamper_aws_key(self):
        content = "AWS_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE'"
        findings = audit_tamper_content(content)
        assert any(f.code == "ERR_HARDCODED_AWS_KEY" for f in findings)

    def test_audit_tamper_debug_flags(self):
        content = "const options = { args: ['--remote-debugging-port=9222'] };"
        findings = audit_tamper_content(content)
        assert any(f.code == "ERR_DEBUG_PORT_EXPOSED" for f in findings)

    def test_audit_tamper_insecure_memory_calls(self):
        content = "BOOL ret = VirtualProtect(addr, size, PAGE_EXECUTE_READWRITE, &oldProtect);"
        findings = audit_tamper_content(content)
        assert any(f.code == "ERR_INSECURE_MEMORY_CALL" for f in findings)

    # 4.3 Loop Circuit Breaker Checker
    def test_check_loop_unbounded_while_true(self):
        bad_loop = """
def process_stream():
    while True:
        print("polling")
"""
        findings = check_loop_content(bad_loop)
        assert any(f.rule_code == "ERR_UNBOUNDED_WHILE_LOOP" for f in findings)

    def test_check_loop_while_true_with_timeout_is_safe(self):
        safe_loop = """
def process_stream():
    start = time.time()
    while True:
        if time.time() - start > timeout:
            break
        print("polling")
"""
        findings = check_loop_content(safe_loop)
        assert not any(f.rule_code == "ERR_UNBOUNDED_WHILE_LOOP" for f in findings)

    def test_check_loop_unguarded_recursion(self):
        bad_recursion = """
def factorial(n):
    return n * factorial(n - 1)
"""
        findings = check_loop_content(bad_recursion)
        assert any(f.rule_code == "ERR_UNGUARDED_RECURSION" for f in findings)

    def test_check_loop_guarded_recursion_is_safe(self):
        safe_recursion = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        findings = check_loop_content(safe_recursion)
        assert not any(f.rule_code == "ERR_UNGUARDED_RECURSION" for f in findings)
