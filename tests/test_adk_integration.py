"""Unit tests for Google ADK Integration (Giai đoạn 1).

Tests Lazy-Loading, Fallback Safety, Trajectory Adaptation, Sanitization,
and AgentEvaluatorBridge behavior.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from harness.adk import ADKTrajectoryAdapter, is_adk_available
from harness.adk.adapter import _sanitize_data
from harness.eval import AgentEvaluatorBridge, is_eval_ready
from harness.memory.trajectory import TrajectoryStore


# ==============================================================================
# 1. Availability & Lazy Import Safety Tests
# ==============================================================================


def test_availability_flags_do_not_crash():
    """Verify is_adk_available() and is_eval_ready() return bool without throwing."""
    adk_avail = is_adk_available()
    eval_ready = is_eval_ready()

    assert isinstance(adk_avail, bool)
    assert isinstance(eval_ready, bool)


def test_is_adk_available_fallback_on_import_error():
    """Simulate missing google.adk library and verify safe False return."""
    with patch.dict("sys.modules", {"google.adk": None}):
        # Force reload / re-check
        with patch("builtins.__import__", side_effect=ImportError("No module named 'google.adk'")):
            assert is_adk_available() is False


def test_is_eval_ready_fallback_on_import_error():
    """Simulate missing google.adk.evaluation and verify safe False return."""
    with patch.dict("sys.modules", {"google.adk.evaluation": None}):
        with patch("builtins.__import__", side_effect=ImportError("No module named 'google.adk'")):
            assert is_eval_ready() is False


# ==============================================================================
# 2. ADKTrajectoryAdapter Event & Step Mapping Tests
# ==============================================================================


def test_adapter_event_dict_mapping():
    """Test mapping of raw ADK event dictionary to TrajectoryStore event schema."""
    adapter = ADKTrajectoryAdapter()
    raw_event = {
        "event_type": "model_call",
        "task_id": "task-test-01",
        "parent_id": "parent-123",
        "timestamp": "2026-10-28T00:00:00Z",
        "payload": {
            "model": "gemini-2.5-pro",
            "prompt": "Evaluate market size",
            "api_key": "mock_secret_api_key_12345",
        },
    }

    adapted = adapter.adapt_event(raw_event)

    assert adapted["event_type"] == "model_call"
    assert adapted["task_id"] == "task-test-01"
    assert adapted["parent_id"] == "parent-123"
    assert adapted["timestamp"] == "2026-10-28T00:00:00Z"
    # Verify sensitive key redaction
    assert adapted["payload"]["api_key"] == "[REDACTED]"
    assert adapted["payload"]["model"] == "gemini-2.5-pro"


def test_adapter_event_object_mapping():
    """Test mapping of an object-based ADK Event instance."""
    adapter = ADKTrajectoryAdapter()

    class MockADKEvent:
        def __init__(self):
            self.type = "tool_execution"
            self.task_id = "task-obj-02"
            self.parent_id = "parent-step-1"
            self.timestamp = "2026-10-28T01:00:00Z"
            self.tool_name = "web_search"
            self.query = "market research"
            self.auth_token = "Bearer secret_jwt_token"

    mock_event = MockADKEvent()
    adapted = adapter.adapt_event(mock_event)

    assert adapted["event_type"] == "tool_execution"
    assert adapted["task_id"] == "task-obj-02"
    assert adapted["parent_id"] == "parent-step-1"
    assert adapted["payload"]["tool_name"] == "web_search"
    assert adapted["payload"]["auth_token"] == "[REDACTED]"


def test_adapter_step_mapping():
    """Test adapting intermediate steps to TrajectoryStore step schema."""
    adapter = ADKTrajectoryAdapter()

    step_dict = {
        "step": "WEB_RESEARCH",
        "data": {"status": "success", "results_count": 5},
    }
    adapted_step = adapter.adapt_step(step_dict)
    assert adapted_step["step"] == "WEB_RESEARCH"
    assert adapted_step["data"]["results_count"] == 5

    # Object step
    class MockStep:
        def __init__(self):
            self.action = "COMPLIANCE_CRITIQUE"
            self.data = {"verdict": "APPROVE", "issues_found": 0}

    adapted_obj_step = adapter.adapt_step(MockStep())
    assert adapted_obj_step["step"] == "COMPLIANCE_CRITIQUE"
    assert adapted_obj_step["data"]["verdict"] == "APPROVE"


def test_data_sanitization():
    """Test that passwords, tokens, API keys and bearer strings are redacted."""
    raw = {
        "user": "alice",
        "password": "supersecretpassword",
        "custom_header": "Bearer abc.xyz.123",
        "nested": {
            "gemini_api_key": "mock_gemini_api_key_xyz",
            "normal_field": "safe_value",
        },
        "list_items": [
            {"access_token": "token123"},
            {"public_info": "public"},
        ],
    }

    sanitized = _sanitize_data(raw)

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["custom_header"] == "Bearer [REDACTED]"
    assert sanitized["nested"]["gemini_api_key"] == "[REDACTED]"
    assert sanitized["nested"]["normal_field"] == "safe_value"
    assert sanitized["list_items"][0]["access_token"] == "[REDACTED]"
    assert sanitized["list_items"][1]["public_info"] == "public"


# ==============================================================================
# 3. TrajectoryStore Disk Integration Tests
# ==============================================================================


def test_adapter_store_integration(tmp_path):
    """Test recording events and saving full trajectory to physical TrajectoryStore."""
    store_path = tmp_path / "trajectories.jsonl"
    store = TrajectoryStore(path=store_path)
    adapter = ADKTrajectoryAdapter(trajectory_store=store)

    task_id = "adk-integrated-task-99"

    # 1. Record an event
    event = adapter.record_adk_event(
        task_id=task_id,
        raw_event={
            "event_type": "agent_start",
            "payload": {"agent": "Creator", "goal": "Generate script"},
        },
    )
    assert event["event_type"] == "agent_start"

    # Verify event on disk
    events_from_store = store.get_events(task_id)
    assert len(events_from_store) == 1
    assert events_from_store[0]["event_type"] == "agent_start"
    assert events_from_store[0]["payload"]["agent"] == "Creator"

    # 2. Save full trajectory
    adk_steps = [
        {"step": "INTAKE", "data": {"input": "write script"}},
        {"step": "CREATOR", "data": {"draft": "Script text content"}},
        {"step": "CRITIC", "data": {"verdict": "APPROVE"}},
    ]

    record = adapter.save_adk_trajectory(
        task_id=task_id,
        branch="marketing",
        task_description="Tạo kịch bản tài chính chuẩn bóc phốt",
        events=adk_steps,
        final_verdict="APPROVE",
        critique_rounds=1,
        metadata={"client": "test_suite"},
    )

    assert record["task_id"] == task_id
    assert record["final_verdict"] == "APPROVE"
    assert len(record["steps"]) == 3
    assert record["metadata"]["adapter"] == "ADKTrajectoryAdapter"

    # Verify trajectory record on disk
    saved_trajectories = store.get_trajectories(branch="marketing", verdict="APPROVE")
    assert len(saved_trajectories) == 1
    assert saved_trajectories[0]["task_id"] == task_id
    assert saved_trajectories[0]["steps"][1]["step"] == "CREATOR"


# ==============================================================================
# 4. AgentEvaluatorBridge Tests
# ==============================================================================


def test_agent_evaluator_bridge_fallback_evaluation():
    """Test deterministic evaluation mode of AgentEvaluatorBridge."""
    bridge = AgentEvaluatorBridge()
    assert isinstance(bridge.is_ready, bool)

    valid_trajectory = {
        "task_id": "eval-task-01",
        "branch": "app",
        "task_description": "Implement feature X",
        "steps": [
            {"step": "INTAKE", "data": {}},
            {"step": "BUILDER", "data": {}},
            {"step": "QA_AUDITOR", "data": {}},
        ],
        "final_verdict": "APPROVE",
        "critique_rounds": 1,
    }

    # Evaluation with matching criteria
    result = bridge.evaluate_trajectory(
        valid_trajectory,
        eval_criteria={
            "expected_verdict": "APPROVE",
            "max_critique_rounds": 2,
            "required_steps": ["INTAKE", "BUILDER", "QA_AUDITOR"],
            "min_steps": 2,
        },
    )

    assert result["passed"] is True
    assert result["score"] == 1.0
    assert result["mode"] == "fallback_deterministic"

    # Evaluation with failing criteria
    failing_result = bridge.evaluate_trajectory(
        valid_trajectory,
        eval_criteria={
            "expected_verdict": "REJECT",  # Mismatch
            "max_critique_rounds": 0,       # 1 > 0 -> Exceeded
            "required_steps": ["NON_EXISTENT_STEP"],
        },
    )

    assert failing_result["passed"] is False
    assert failing_result["score"] < 1.0
    assert len(failing_result["errors"]) >= 2


def test_agent_evaluator_bridge_step_sequence_evaluation():
    """Test evaluate_steps with order and prohibition rules."""
    bridge = AgentEvaluatorBridge()

    steps = [
        {"step": "INTAKE"},
        {"step": "BUILDER"},
        {"step": "QA_AUDITOR"},
    ]

    # Valid ordered sequence
    res_ordered = bridge.evaluate_steps(
        steps,
        expectations={
            "required_steps": ["INTAKE", "QA_AUDITOR"],
            "order_matters": True,
        },
    )
    assert res_ordered["passed"] is True
    assert res_ordered["score"] == 1.0

    # Sequence with prohibited step
    res_prohibited = bridge.evaluate_steps(
        steps,
        expectations={
            "prohibited_steps": ["BUILDER"],
        },
    )
    assert res_prohibited["passed"] is False
    assert "BUILDER" in res_prohibited["prohibited_found"]

    # Sequence with order violation
    reversed_steps = [
        {"step": "QA_AUDITOR"},
        {"step": "INTAKE"},
    ]
    res_violation = bridge.evaluate_steps(
        reversed_steps,
        expectations={
            "required_steps": ["INTAKE", "QA_AUDITOR"],
            "order_matters": True,
        },
    )
    assert res_violation["passed"] is False
    assert len(res_violation["order_violations"]) > 0


def test_agent_evaluator_bridge_with_mocked_adk_runner():
    """Test live delegation branch when native ADK is simulated as present."""
    mock_native_eval = MagicMock()
    mock_eval_result = MagicMock()
    mock_eval_result.passed = True
    mock_eval_result.score = 0.95
    mock_eval_result.details = {"adk_metric": "passed"}
    mock_eval_result.summary = "All checks passed in native ADK"
    mock_native_eval.evaluate.return_value = mock_eval_result

    with patch("harness.eval.evaluator.is_eval_ready", return_value=True):
        with patch("harness.eval.evaluator.AgentEvaluatorBridge.__init__", lambda self, config=None: None):
            bridge = AgentEvaluatorBridge()
            bridge._eval_ready = True
            bridge._native_evaluator = mock_native_eval

            res = bridge.evaluate_trajectory(
                {"task_id": "test", "steps": [], "final_verdict": "APPROVE"},
                eval_criteria={"metric": "strict"},
            )

            assert res["passed"] is True
            assert res["score"] == 0.95
            assert res["mode"] == "adk_agentic"
            assert res["summary"] == "All checks passed in native ADK"
            mock_native_eval.evaluate.assert_called_once()
