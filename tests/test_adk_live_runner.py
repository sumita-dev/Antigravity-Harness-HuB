"""Unit tests for ADK Live Runner and Visual Dashboard (Giai đoạn 3).

Verifies ADKLiveRunner, SequentialAgent & LoopAgent workflow mapping,
TrajectoryStore integration, Process Hygiene, and run_harness.py CLI flags.
100% deterministic, zero network or API key required.
"""

from __future__ import annotations

import io
import json
import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.adk import (
    ADKLiveRunner,
    cleanup_dashboard_process,
    find_safe_port,
    is_adk_available,
    is_port_in_use,
    launch_visual_dashboard,
)
from harness.memory.trajectory import TrajectoryStore
from run_harness import main


# ==============================================================================
# 1. ADKLiveRunner Initialization & Branch Mapping
# ==============================================================================


def test_live_runner_initialization(tmp_path: Path):
    """Verify ADKLiveRunner initializes with custom or default TrajectoryStore."""
    store = TrajectoryStore(path=tmp_path / "trajectories.jsonl")
    runner = ADKLiveRunner(trajectory_store=store)

    assert runner.trajectory_store == store
    assert runner.adapter is not None
    assert isinstance(runner.is_adk_available, bool)


def test_live_runner_branch_classification():
    """Verify branch classification maps correctly to SequentialAgent vs LoopAgent."""
    runner = ADKLiveRunner()

    # Explicit marketing branch
    branch, wf = runner.classify_branch("Bất kỳ mô tả nào", branch="marketing")
    assert branch == "marketing"
    assert wf == "SequentialAgent"

    # Explicit app branch
    branch, wf = runner.classify_branch("Bất kỳ mô tả nào", branch="app")
    assert branch == "app"
    assert wf == "LoopAgent"

    # Auto routing: marketing task
    branch, wf = runner.classify_branch("Soạn kịch bản TikTok bóc phốt lừa đảo tài chính", branch="auto")
    assert branch == "marketing"
    assert wf == "SequentialAgent"

    # Auto routing: app task
    branch, wf = runner.classify_branch("Fix lỗi memory leak trong WebSocket backend", branch="auto")
    assert branch == "app"
    assert wf == "LoopAgent"


# ==============================================================================
# 2. Workflow Execution: Sequential (Marketing) & Loop (App)
# ==============================================================================


def test_marketing_sequential_execution(tmp_path: Path):
    """Verify Marketing workflow executes Web Researcher -> Creator -> Critic sequence."""
    store = TrajectoryStore(path=tmp_path / "trajectories.jsonl")
    runner = ADKLiveRunner(trajectory_store=store)

    result = runner.run_task(
        task_description="Soạn kịch bản video review cổ phiếu",
        branch="marketing",
        task_id="task-mkt-001",
    )

    assert result["task_id"] == "task-mkt-001"
    assert result["branch"] == "marketing"
    assert result["workflow_type"] == "SequentialAgent"
    assert result["verdict"] == "APPROVE"
    assert result["critique_rounds"] == 1
    assert result["events_count"] >= 9

    # Verify event order and agents involved
    events = runner.adapter.trajectory_store.get_trajectories(branch="marketing")
    assert len(events) == 1
    steps = events[0]["steps"]
    step_names = [s["step"] for s in steps]

    assert "workflow_start" in step_names
    assert "agent_start" in step_names
    assert "tool_execution" in step_names
    assert "content_generation" in step_names
    assert "compliance_audit" in step_names
    assert "workflow_finish" in step_names


def test_app_loop_execution_success(tmp_path: Path):
    """Verify App workflow executes Maker -> Critic -> QA Auditor loop."""
    store = TrajectoryStore(path=tmp_path / "trajectories.jsonl")
    runner = ADKLiveRunner(trajectory_store=store)

    result = runner.run_task(
        task_description="Xây dựng API đăng nhập JWT",
        branch="app",
        task_id="task-app-001",
    )

    assert result["task_id"] == "task-app-001"
    assert result["branch"] == "app"
    assert result["workflow_type"] == "LoopAgent"
    assert result["verdict"] == "APPROVE"
    assert result["critique_rounds"] == 1

    events = runner.adapter.trajectory_store.get_trajectories(branch="app")
    assert len(events) == 1
    step_names = [s["step"] for s in events[0]["steps"]]

    assert "loop_iteration_start" in step_names
    assert "code_review" in step_names
    assert "qa_audit" in step_names
    assert "workflow_finish" in step_names


def test_app_loop_rejection_and_circuit_breaker(tmp_path: Path):
    """Verify App workflow triggers circuit breaker when Critic rejects repeatedly."""
    store = TrajectoryStore(path=tmp_path / "trajectories.jsonl")
    runner = ADKLiveRunner(trajectory_store=store)

    result = runner.run_task(
        task_description="Tính năng thanh toán phức tạp",
        branch="app",
        task_id="task-app-reject",
        max_rounds=2,
        mock_verdict="REJECT",
    )

    assert result["task_id"] == "task-app-reject"
    assert result["verdict"] == "ESCALATE"
    assert result["critique_rounds"] == 2

    # Verify circuit breaker event was emitted
    events = runner.adapter.trajectory_store.get_trajectories(branch="app")
    assert len(events) == 1
    step_names = [s["step"] for s in events[0]["steps"]]
    assert "circuit_breaker_triggered" in step_names


# ==============================================================================
# 3. Trajectory & Event Store Physical File Verification
# ==============================================================================


def test_trajectory_persisted_on_disk(tmp_path: Path):
    """Verify that ADKLiveRunner writes valid trajectories and events to physical disk files."""
    traj_file = tmp_path / "trajectories" / "trajectories.jsonl"
    events_file = tmp_path / "trajectories" / "events.jsonl"
    store = TrajectoryStore(path=traj_file)
    runner = ADKLiveRunner(trajectory_store=store)

    runner.run_task(
        task_description="Kiểm thử lưu vết vật lý",
        branch="marketing",
        task_id="disk-task-100",
    )

    # 1. Trajectory JSONL exists and contains valid record
    assert traj_file.exists()
    lines = traj_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["task_id"] == "disk-task-100"
    assert record["branch"] == "marketing"
    assert record["final_verdict"] == "APPROVE"
    assert len(record["steps"]) > 0

    # 2. Events JSONL exists and contains step events
    assert events_file.exists()
    event_lines = events_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(event_lines) >= 9
    first_ev = json.loads(event_lines[0])
    assert first_ev["task_id"] == "disk-task-100"
    assert first_ev["event_type"] == "workflow_start"


# ==============================================================================
# 4. Visual Dashboard & Process Hygiene Tests
# ==============================================================================


def test_is_port_in_use_and_safe_port():
    """Verify port availability detection and safe port allocation."""
    # Bind a temporary socket to guarantee port is in use
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        used_port = s.getsockname()[1]
        assert is_port_in_use(used_port, "127.0.0.1") is True

    # After closing socket, port should be free (or safe port resolves to another)
    safe = find_safe_port(start_port=19876, host="127.0.0.1")
    assert isinstance(safe, int)
    assert safe >= 19876


def test_launch_visual_dashboard_check_only():
    """Verify launch_visual_dashboard returns complete metadata in check_only mode."""
    dash = launch_visual_dashboard(port=8500, host="127.0.0.1", check_only=True)

    assert "ready" in dash
    assert "port" in dash
    assert "host" in dash
    assert dash["host"] == "127.0.0.1"
    assert "command" in dash
    assert "url" in dash
    assert dash["url"].startswith("http://127.0.0.1:")
    assert "message" in dash
    assert "hint" in dash


def test_cleanup_dashboard_process_safety():
    """Verify cleanup_dashboard_process terminates processes cleanly without exceptions."""
    # Test with None
    assert cleanup_dashboard_process(None) is True

    # Test with mock process
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 99999

    assert cleanup_dashboard_process(mock_proc, timeout=0.1) is True
    mock_proc.terminate.assert_called_once()


# ==============================================================================
# 5. CLI run_harness.py Flag Integration Tests
# ==============================================================================


def test_cli_visual_flag_standalone(capsys):
    """Verify 'python run_harness.py --visual' executes cleanly and prints dashboard info."""
    exit_code = main(["--visual"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ADK Visual Dashboard" in captured.out


def test_cli_visual_flag_json(capsys):
    """Verify 'python run_harness.py --visual --json' returns valid JSON."""
    exit_code = main(["--visual", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    assert "ready" in data
    assert "command" in data
    assert "url" in data


def test_cli_live_marketing_task(capsys):
    """Verify 'python run_harness.py --task ... --live' runs via ADKLiveRunner."""
    exit_code = main([
        "--task", "Soạn kịch bản quảng cáo bất động sản",
        "--branch", "marketing",
        "--live",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Live ADK Task Finished" in captured.out
    assert "SequentialAgent" in captured.out
    assert "VERDICT: APPROVE" in captured.out or "Verdict: APPROVE" in captured.out


def test_cli_live_app_task_json(capsys):
    """Verify 'python run_harness.py --task ... --live --json' outputs structured JSON."""
    exit_code = main([
        "--task", "Thiết kế component Button UI",
        "--branch", "app",
        "--live",
        "--json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["branch"] == "app"
    assert data["workflow_type"] == "LoopAgent"
    assert data["verdict"] == "APPROVE"
    assert "task_id" in data
    assert "events_count" in data


def test_cli_live_with_visual(capsys):
    """Verify 'python run_harness.py --task ... --live --visual' attaches dashboard command."""
    exit_code = main([
        "--task", "Build payment checkout page",
        "--branch", "app",
        "--live",
        "--visual",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Live ADK Task Finished" in captured.out
    assert "Visual Dashboard:" in captured.out


def test_cli_backward_compatibility_simulation(capsys):
    """Verify simulation mode without --live preserves 100% legacy behavior."""
    exit_code = main([
        "--task", "Viết test case đơn giản",
        "--branch", "app",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Simulation finished (no agents executed)" in captured.out
