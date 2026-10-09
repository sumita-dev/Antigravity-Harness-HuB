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
