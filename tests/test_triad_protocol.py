import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from harness.state_machine import TaskContext, HarnessState, HarnessTransitionError
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.runners.app_runner import AppRunner
from harness.runners.marketing_runner import MarketingRunner
from harness.orchestrator import ChiefOrchestrator
from harness.triad_protocol import (
    HandoffValidationError,
    TriadHandoffV2,
    parse_handoff_v2,
    sync_workspace_for_qa,
    validate_handoff_v2,
)
from harness.subagent_guard import SubagentGuard


def _walk_to_implementation(ctx: TaskContext) -> TaskContext:
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.DESIGN)
    ctx.transition(HarnessState.IMPLEMENTATION)
    return ctx


def test_triad_full_cycle_approve():
    """Luồng Triad đầy đủ: Maker -> Critic -> QA -> Approved."""
    ctx = _walk_to_implementation(TaskContext("triad-1", "app"))
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)

    # 1. Chuyển sang CRITIQUE (Code Critic)
    assert ctx.transition(HarnessState.CRITIQUE) is True
    assert ctx.state == HarnessState.CRITIQUE

    # 2. Critic APPROVE -> chuyển sang AUDIT
    verdict_crit = gate.evaluate_critique(ctx, "Spec GAP checked. No boundary flaws. VERDICT: APPROVE")
    assert verdict_crit == Verdict.APPROVE
    assert ctx.state == HarnessState.AUDIT

    # 3. QA Auditor APPROVE -> chuyển sang APPROVED
    verdict_qa = gate.evaluate_audit(ctx, "All unit tests pass. Zero secrets. VERDICT: APPROVE")
    assert verdict_qa == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_triad_critic_reject_and_smart_feedback():
    """Critic phát hiện Spec GAP / boundary logic -> Maker sửa -> nộp lại Critic."""
    ctx = _walk_to_implementation(TaskContext("triad-2", "app"))
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)

    ctx.transition(HarnessState.CRITIQUE)
    verdict_crit = gate.evaluate_critique(ctx, "Missing boundary check for empty array. VERDICT: REJECT")
    assert verdict_crit == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 1
    assert ctx.total_cycles == 1

    # Maker sửa xong nộp lại Critic
    ctx.transition(HarnessState.CRITIQUE)
    verdict_crit_2 = gate.evaluate_critique(ctx, "Boundary checked. VERDICT: APPROVE")
    assert verdict_crit_2 == Verdict.APPROVE
    assert ctx.state == HarnessState.AUDIT

    # Sau đó QA duyệt
    verdict_qa = gate.evaluate_audit(ctx, "VERDICT: APPROVE")
    assert verdict_qa == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_triad_qa_technical_failure_direct_to_qa():
    """QA bắt lỗi kỹ thuật / test fail -> Maker sửa và trả thẳng cho QA test lại."""
    ctx = _walk_to_implementation(TaskContext("triad-3", "app"))
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)

    # Đi qua Critic đạt
    ctx.transition(HarnessState.CRITIQUE)
    gate.evaluate_critique(ctx, "VERDICT: APPROVE")
    assert ctx.state == HarnessState.AUDIT

    # QA phát hiện test fail
    verdict_qa = gate.evaluate_audit(ctx, "Unit test failed on line 42. VERDICT: REJECT", direct_to_qa=True)
    assert verdict_qa == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.qa_rounds == 1
    assert ctx.critique_rounds == 0  # Không tăng critique_rounds
    assert ctx.total_cycles == 1

    # Smart Feedback Loop: Maker sửa test và trả thẳng sang AUDIT
    assert ctx.transition(HarnessState.AUDIT) is True
    assert ctx.state == HarnessState.AUDIT

    verdict_qa_2 = gate.evaluate_audit(ctx, "Test passed. VERDICT: APPROVE")
    assert verdict_qa_2 == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_triad_decoupled_circuit_breaker_critic():
    """Ngắt mạch độc lập ở vòng 2 của Critic (critic_rounds >= 2 -> ESCALATED)."""
    ctx = _walk_to_implementation(TaskContext("triad-4", "app"))
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)

    ctx.transition(HarnessState.CRITIQUE)
    assert gate.evaluate_critique(ctx, "VERDICT: REJECT") == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 1

    ctx.transition(HarnessState.CRITIQUE)
    assert gate.evaluate_critique(ctx, "VERDICT: REJECT") == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED
    assert ctx.critique_rounds == 2


def test_triad_decoupled_circuit_breaker_qa():
    """Ngắt mạch độc lập ở vòng 2 của QA (qa_rounds >= 2 -> ESCALATED)."""
    ctx = _walk_to_implementation(TaskContext("triad-5", "app"))
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)

    ctx.transition(HarnessState.CRITIQUE)
    gate.evaluate_critique(ctx, "VERDICT: APPROVE")
    assert ctx.state == HarnessState.AUDIT

    # Vòng 1 QA REJECT
    assert gate.evaluate_audit(ctx, "VERDICT: REJECT") == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.qa_rounds == 1

    # Trả thẳng AUDIT vòng 2
    ctx.transition(HarnessState.AUDIT)
    assert gate.evaluate_audit(ctx, "VERDICT: REJECT") == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED
    assert ctx.qa_rounds == 2


def test_triad_total_cycles_limit():
    """Ngắt mạch khi tổng số chu trình total_cycles >= 3."""
    ctx = _walk_to_implementation(TaskContext("triad-6", "app"))
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)

    # Chu trình 1: Critic reject (critic_rounds=1, total_cycles=1)
    ctx.transition(HarnessState.CRITIQUE)
    assert gate.evaluate_critique(ctx, "VERDICT: REJECT") == Verdict.REJECT
    assert ctx.total_cycles == 1

    # Chu trình 2: Critic approve, sau đó QA reject (qa_rounds=1, total_cycles=2)
    ctx.transition(HarnessState.CRITIQUE)
    assert gate.evaluate_critique(ctx, "VERDICT: APPROVE") == Verdict.APPROVE
    assert gate.evaluate_audit(ctx, "VERDICT: REJECT") == Verdict.REJECT
    assert ctx.total_cycles == 2

    # Chu trình 3: QA reject tiếp hoặc critic reject -> đạt max_total_cycles -> ESCALATE
    ctx.transition(HarnessState.AUDIT)
    assert gate.evaluate_audit(ctx, "VERDICT: REJECT") == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED
    assert ctx.total_cycles >= 3


def test_triad_fast_track_tier2():
    """Fast-Track cho Tier 2 (Minor/Hotfix): bỏ qua CRITIQUE, đi thẳng Maker -> QA."""
    runner = AppRunner(AdversarialQualityGate())
    ctx = TaskContext("fast-track-1", "app")
    ctx.transition(HarnessState.INTAKE)

    verdict = runner.run("Hotfix typo in auth token", ctx, fast_track=True)
    assert verdict == Verdict.APPROVE
    steps = [s["step"] for s in ctx.trace_steps]
    assert "DESIGN" in steps
    assert "IMPLEMENTATION" in steps
    assert "CRITIQUE" not in steps  # Fast track không qua critique
    assert "AUDIT" in steps
    assert ctx.state == HarnessState.APPROVED


def test_triad_app_runner_executes_critique_by_default():
    """AppRunner mặc định chạy qua bước CRITIQUE (Code Critic)."""
    runner = AppRunner(AdversarialQualityGate())
    ctx = TaskContext("triad-runner-1", "app")
    ctx.transition(HarnessState.INTAKE)

    verdict = runner.run("Implement core feature", ctx)
    assert verdict == Verdict.APPROVE
    steps = [s["step"] for s in ctx.trace_steps]
    assert "CRITIQUE" in steps
    assert "AUDIT" in steps
    critique_step = next(s for s in ctx.trace_steps if s["step"] == "CRITIQUE")
    assert critique_step["payload"]["actor"] == "code_critic"


def test_triad_handoff_v2_schema_contract():
    """Hợp đồng Triad Handoff Contract v2: Xác thực đầy đủ các trường và bắt buộc commit_sha & verification_receipt."""
    valid_data = {
        "$schema": "https://antigravity.dev/schemas/triad-handoff.v2.json",
        "task_id": "TASK-2026-11-11-SYNC-01",
        "source_branch": "worktree/maker-01",
        "commit_sha": "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
        "spec_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        "modified_files": [
            {"path": "harness/triad_protocol.py", "change_type": "CREATE", "diff_stat": "+100 -0"}
        ],
        "verification_receipt": {
            "command": "pytest tests/test_triad_protocol.py -q",
            "exit_code": 0,
            "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        },
        "acceptance_criteria_matrix": [
            {"ac_id": "AC-04", "status": "SATISFIED", "evidence_ref": "test_triad_handoff_v2_schema_contract"}
        ],
        "digest": "Maker completed Handoff v2 protocol implementation with full verification.",
    }

    ok, errors = validate_handoff_v2(valid_data)
    assert ok is True
    assert errors == []

    handoff = parse_handoff_v2(valid_data)
    assert handoff.task_id == "TASK-2026-11-11-SYNC-01"
    assert handoff.commit_sha == "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5"
    assert handoff.verification_receipt["exit_code"] == 0

    json_str = handoff.to_json()
    assert "https://antigravity.dev/schemas/triad-handoff.v2.json" in json_str

    # Test SubagentGuard.record_handoff
    guard = SubagentGuard()
    recorded = guard.record_handoff(valid_data)
    assert recorded.task_id == handoff.task_id


def test_triad_handoff_v2_rejection_rules():
    """Từ chối nếu commit_sha không hợp lệ hoặc verification_receipt thất bại."""
    # 1. commit_sha chứa ký tự không hợp lệ
    bad_sha = {
        "task_id": "T1",
        "commit_sha": "not-a-hex-sha!",
        "verification_receipt": {"command": "pytest", "exit_code": 0, "stdout_hash": "abc"},
    }
    ok, errors = validate_handoff_v2(bad_sha)
    assert ok is False
    assert any("commit_sha" in e for e in errors)
    with pytest.raises(HandoffValidationError):
        parse_handoff_v2(bad_sha)

    # 2. exit_code != 0 trong verification_receipt
    bad_ec = {
        "task_id": "T2",
        "commit_sha": "1234567890abcdef",
        "verification_receipt": {"command": "pytest", "exit_code": 2, "stdout_hash": "abc"},
    }
    ok, errors = validate_handoff_v2(bad_ec)
    assert ok is False
    assert any("exit_code bắt buộc phải bằng 0" in e for e in errors)


def test_sync_workspace_for_qa_mechanism(tmp_path: Path):
    """Kiểm tra cơ chế đồng bộ workspace chống Branch Blindness (VULN-05)."""
    # Test fallback khi không có git repo
    res = sync_workspace_for_qa("feature-branch", tmp_path, repo_root=tmp_path)
    assert res["synced"] is True
    assert "filesystem fallback" in res["message"]


def test_triad_handoff_v2_report_and_evidence_paths():
    """Pha 1: Kiểm tra report_path, evidence_paths và require_report_path=True."""
    base = {
        "task_id": "T-REPORT-01",
        "commit_sha": "1234567890abcdef",
        "verification_receipt": {"command": "pytest -q", "exit_code": 0, "stdout_hash": "abc123"},
        "report_path": "artifacts/qa_report.md",
        "evidence_paths": ["artifacts/pytest.log", "artifacts/screenshot.png"],
    }
    ok, errors = validate_handoff_v2(base, require_report_path=True)
    assert ok is True
    assert errors == []

    handoff = parse_handoff_v2(base, require_report_path=True)
    assert handoff.report_path == "artifacts/qa_report.md"
    assert handoff.evidence_paths == ["artifacts/pytest.log", "artifacts/screenshot.png"]
    d = handoff.to_dict()
    assert d["report_path"] == "artifacts/qa_report.md"
    assert d["evidence_paths"] == ["artifacts/pytest.log", "artifacts/screenshot.png"]

    # Thiếu report_path khi require_report_path=True -> lỗi
    no_rp = {k: v for k, v in base.items() if k != "report_path"}
    ok_missing, err_missing = validate_handoff_v2(no_rp, require_report_path=True)
    assert ok_missing is False
    assert any("report_path" in e for e in err_missing)
    with pytest.raises(HandoffValidationError):
        parse_handoff_v2(no_rp, require_report_path=True)

    # report_path rỗng -> lỗi ngay cả khi require_report_path=False
    empty_rp = {**base, "report_path": "   "}
    ok_empty, err_empty = validate_handoff_v2(empty_rp)
    assert ok_empty is False
    assert any("report_path" in e for e in err_empty)

    # evidence_paths sai kiểu hoặc có phần tử rỗng -> lỗi
    bad_ep = {**base, "evidence_paths": ["valid.log", ""]}
    ok_ep, err_ep = validate_handoff_v2(bad_ep)
    assert ok_ep is False
    assert any("evidence_paths[1]" in e for e in err_ep)


def test_sync_workspace_for_qa_dirty_working_tree(tmp_path: Path):
    """Pha 4: Chặn sync nếu working tree có thay đổi chưa commit trừ khi allow_dirty=True."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()

    def _git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            check=True,
        )

    _git("init")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test User")
    (repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
    _git("add", "app.py")
    _git("commit", "-m", "init")
    _git("branch", "maker-branch")

    # Tạo file untracked (dirty working tree)
    (repo / "uncommitted.py").write_text("print('wip')\n", encoding="utf-8")

    res_blocked = sync_workspace_for_qa("maker-branch", repo, repo_root=repo)
    assert res_blocked["synced"] is False
    assert "uncommitted/untracked" in res_blocked["message"]

    # Khi allow_dirty=True thì cho phép checkout
    res_allowed = sync_workspace_for_qa("maker-branch", repo, repo_root=repo, allow_dirty=True)
    assert res_allowed["synced"] is True


def test_triad_handoff_v2_physical_report_verification_and_workspace_mode(tmp_path: Path):
    """GAP-1 (DR-01): verify_report_exists=True kiểm tra sự tồn tại vật lý trên đĩa và workspace_mode."""
    report_file = tmp_path / "actual_report.md"
    report_file.write_text("# QA Audit Report\nAll passed.\n", encoding="utf-8")

    payload = {
        "task_id": "T-VERIFY-REPORT-01",
        "commit_sha": "1234567890abcdef",
        "verification_receipt": {"command": "pytest -q", "exit_code": 0, "stdout_hash": "abc123"},
        "report_path": str(report_file),
        "workspace_mode": "branch",
        "workspace_path": str(tmp_path),
    }

    # 1. verify_report_exists=True khi file tồn tại -> OK
    ok, errors = validate_handoff_v2(payload, require_report_path=True, verify_report_exists=True)
    assert ok is True
    assert errors == []

    parsed = parse_handoff_v2(payload, require_report_path=True, verify_report_exists=True)
    assert parsed.workspace_mode == "branch"
    assert parsed.workspace_path == str(tmp_path)
    assert parsed.to_dict()["workspace_mode"] == "branch"
    assert parsed.to_dict()["workspace_path"] == str(tmp_path)

    # 2. verify_report_exists=True khi file KHÔNG tồn tại -> Lỗi
    non_existent = tmp_path / "non_existent_report.md"
    bad_payload = dict(payload, report_path=str(non_existent))
    ok_bad, errors_bad = validate_handoff_v2(bad_payload, require_report_path=True, verify_report_exists=True)
    assert ok_bad is False
    assert any("không tồn tại" in e for e in errors_bad)

    with pytest.raises(HandoffValidationError):
        parse_handoff_v2(bad_payload, require_report_path=True, verify_report_exists=True)

    # 3. verify_report_exists=False (mặc định) vẫn tương thích ngược với synthetic path
    ok_compat, errors_compat = validate_handoff_v2(bad_payload, require_report_path=True, verify_report_exists=False)
    assert ok_compat is True
    assert errors_compat == []

    # 4. workspace_mode không hợp lệ -> Lỗi
    bad_mode = dict(payload, workspace_mode="invalid_mode")
    ok_mode, errors_mode = validate_handoff_v2(bad_mode)
    assert ok_mode is False
    assert any("workspace_mode" in e for e in errors_mode)

    # 5. workspace_mode=None mặc định an toàn về "inherit"
    none_mode = dict(payload, workspace_mode=None)
    ok_none, errors_none = validate_handoff_v2(none_mode)
    assert ok_none is True
    parsed_none = parse_handoff_v2(none_mode)
    assert parsed_none.workspace_mode == "inherit"

    # 6. SubagentGuard record_handoff với verify_report_exists=True
    guard = SubagentGuard()
    rec = guard.record_handoff(payload, require_report_path=True, verify_report_exists=True)
    assert rec.task_id == "T-VERIFY-REPORT-01"
    assert rec.workspace_mode == "branch"

