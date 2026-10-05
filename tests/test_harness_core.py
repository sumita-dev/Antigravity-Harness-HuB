import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from harness.state_machine import TaskContext, HarnessState, HarnessTransitionError
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.orchestrator import ChiefOrchestrator


def _walk_to_audit(ctx: TaskContext) -> TaskContext:
    """Đi đúng luồng: INIT -> INTAKE -> DESIGN -> IMPLEMENTATION -> AUDIT."""
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.DESIGN)
    ctx.transition(HarnessState.IMPLEMENTATION)
    ctx.transition(HarnessState.AUDIT)
    return ctx


def test_state_machine_valid_transitions():
    ctx = TaskContext("1", "app")
    assert ctx.state == HarnessState.INIT
    _walk_to_audit(ctx)
    assert ctx.state == HarnessState.AUDIT


def test_state_machine_khong_nhay_coc_quy_trinh():
    """INTAKE không được nhảy cóc sang IMPLEMENTATION (đúng quy chuẩn README)."""
    ctx = TaskContext("1", "app")
    ctx.transition(HarnessState.INTAKE)
    with pytest.raises(HarnessTransitionError):
        ctx.transition(HarnessState.IMPLEMENTATION)
    assert ctx.state == HarnessState.INTAKE


def test_state_machine_invalid_transition():
    ctx = TaskContext("1", "app")
    with pytest.raises(ValueError):
        ctx.transition(HarnessState.AUDIT)


def test_safe_transition_khong_nem_loi():
    ctx = TaskContext("1", "app")
    assert ctx.safe_transition(HarnessState.AUDIT) is False
    assert ctx.state == HarnessState.INIT


def test_quality_gate_approve():
    ctx = _walk_to_audit(TaskContext("1", "app"))
    gate = AdversarialQualityGate()
    verdict = gate.evaluate(ctx, "Looks good. VERDICT: APPROVE")
    assert verdict == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_quality_gate_reject_retry():
    ctx = _walk_to_audit(TaskContext("1", "app"))
    gate = AdversarialQualityGate()
    verdict = gate.evaluate(ctx, "Failed tests. VERDICT: REJECT")
    assert verdict == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 1


def test_quality_gate_circuit_breaker():
    ctx = _walk_to_audit(TaskContext("1", "app"))
    gate = AdversarialQualityGate(max_rounds=2)

    assert gate.evaluate(ctx, "VERDICT: REJECT") == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    ctx.transition(HarnessState.AUDIT)

    assert gate.evaluate(ctx, "VERDICT: REJECT") == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    ctx.transition(HarnessState.AUDIT)

    assert gate.evaluate(ctx, "VERDICT: REJECT") == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED
    assert ctx.critique_rounds == 3


def test_quality_gate_output_vo_nghia_thi_escalate():
    """Checker trả về chuỗi vô nghĩa -> ESCALATE, tuyệt đối không tự APPROVE."""
    ctx = _walk_to_audit(TaskContext("1", "app"))
    gate = AdversarialQualityGate()
    assert gate.evaluate(ctx, "tôi không rõ") == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED


def test_orchestrator_routing():
    orc = ChiefOrchestrator()
    ctx, verdict = orc.process_task("Make a cool app", "app")
    assert ctx.state == HarnessState.APPROVED
    assert verdict == Verdict.APPROVE
    assert ctx.task_id and ctx.task_id != "task_1"   # task_id phải duy nhất, không hardcode

    ctx2, _ = orc.process_task("Make a cool post", "invalid")
    assert ctx2.state == HarnessState.ESCALATED


def test_review_rounds_kich_hoat_circuit_breaker():
    """Lỗi cũ: qua process_task không bao giờ escalate. Nay phải escalate được."""
    orc = ChiefOrchestrator()
    ctx, verdict = orc.process_task("Build login", "app",
                                    mock_checker_output="VERDICT: REJECT",
                                    review_rounds=3)
    assert ctx.state == HarnessState.ESCALATED
    assert verdict == Verdict.ESCALATE
    assert ctx.critique_rounds == 3


def test_skill_instructions_duoc_nap_va_ghi_trace():
    """Lỗi cũ: skill_instructions bị vứt đi. Nay phải nạp và ghi bằng chứng."""
    orc = ChiefOrchestrator()
    ctx, _ = orc.process_task("viết content cho facebook", "auto")
    assert ctx.active_skill == "cong-thuc-viet-content-by-noti-v4"
    assert ctx.skill_instructions and len(ctx.skill_instructions) > 500
    assert any(s["step"] == "SKILL_LOAD" and s["payload"]["chars"] > 500
               for s in ctx.trace_steps)


def test_app_runner_custom_payloads():
    """AppRunner ghi nhận đúng payload tùy chọn cho DESIGN và IMPLEMENTATION."""
    orc = ChiefOrchestrator()
    runner = orc.app_runner
    ctx = TaskContext("test_payload", "app")
    ctx.transition(HarnessState.INTAKE)
    verdict = runner.run(
        "Build a custom widget",
        ctx,
        spec="Custom App Spec 1.0",
        implementation_artifacts={"status": "done", "files": ["widget.py"]},
    )
    assert verdict == Verdict.APPROVE
    steps = {s["step"]: s["payload"] for s in ctx.trace_steps}
    assert steps["DESIGN"] == {"actor": "architect", "spec": "Custom App Spec 1.0"}
    assert steps["IMPLEMENTATION"] == {
        "actor": "builder",
        "artifacts": {"status": "done", "files": ["widget.py"]},
    }
    assert steps["AUDIT"] == {"actor": "qa_auditor"}


def test_app_runner_default_payloads():
    """AppRunner ghi nhận payload mặc định khi không truyền spec / implementation_artifacts."""
    orc = ChiefOrchestrator()
    runner = orc.app_runner
    ctx = TaskContext("test_default", "app")
    ctx.transition(HarnessState.INTAKE)
    verdict = runner.run("Build default widget", ctx)
    assert verdict == Verdict.APPROVE
    steps = {s["step"]: s["payload"] for s in ctx.trace_steps}
    assert steps["DESIGN"] == {"actor": "architect", "spec": "Default Architecture Spec"}
    assert steps["IMPLEMENTATION"] == {
        "actor": "builder",
        "artifacts": {"status": "code_implemented"},
    }
    assert steps["AUDIT"] == {"actor": "qa_auditor"}

