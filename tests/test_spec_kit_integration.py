import pytest
from pathlib import Path
from harness.state_machine import HarnessState, TaskContext
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.orchestrator import ChiefOrchestrator

def test_human_review_gate_pause_and_resume(tmp_path):
    """Kiểm tra Human Review Gate: tạm dừng an toàn và nối lại luồng sau khi duyệt."""
    gate = AdversarialQualityGate()
    ctx = TaskContext(task_id="test-gate-001", branch="app")
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.DESIGN)

    checkpoint_file = tmp_path / "checkpoint.json"

    # 1. Kích hoạt gate_check không có verdict định sẵn -> Chuyển sang PAUSED
    verdict, status = gate.gate_check(
        ctx,
        message="Review plan trước khi triển khai",
        checkpoint_path=str(checkpoint_file),
    )
    assert verdict == Verdict.PAUSE
    assert status == "PAUSED"
    assert ctx.state == HarnessState.PAUSED
    assert checkpoint_file.exists()

    # 2. Người dùng phê duyệt -> resume_gate chuyển tiếp sang IMPLEMENTATION
    resumed = gate.resume_gate(ctx, target_state=HarnessState.IMPLEMENTATION, choice="approve")
    assert resumed is True
    assert ctx.state == HarnessState.IMPLEMENTATION

    # 3. Thử nghiệm verdict_override trực tiếp
    verdict_direct, choice = gate.gate_check(ctx, verdict_override="approve")
    assert verdict_direct == Verdict.APPROVE
    assert choice == "approve"

def test_fan_out_tasks_parallel_execution():
    """Kiểm tra điều phối Fan-Out / Fan-In thực thi nhiều sub-tasks song song."""
    orc = ChiefOrchestrator()
    task_list = [
        "Sub-task 1: Setup database schema",
        "Sub-task 2: Implement auth endpoints",
        "Sub-task 3: Write integration tests",
    ]

    results = orc.fan_out_tasks(
        task_list=task_list,
        branch="app",
        max_concurrency=3,
        mock_checker_output="VERDICT: APPROVE",
    )

    assert len(results) == 3
    for sub_ctx, verdict in results:
        assert verdict == Verdict.APPROVE
        assert sub_ctx.state == HarnessState.APPROVED
        step_names = [s["step"] for s in sub_ctx.trace_steps]
        assert "INTAKE" in step_names
        assert "DESIGN" in step_names
        assert "IMPLEMENTATION" in step_names
