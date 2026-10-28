"""Unit tests for Agentic Evals Engine (Giai đoạn 2).

Tests TrajectoryEvaluator, PolicySafetyEvaluator, FactGroundingEvaluator,
AgentEvaluatorBridge, and full EvalSet execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.eval import (
    DEFAULT_RED_FLAG_PHRASES,
    AgentEvaluatorBridge,
    FactGroundingEvaluator,
    PolicySafetyEvaluator,
    TrajectoryEvaluator,
    is_eval_ready,
)

# Mark all tests in this module with 'eval' marker
pytestmark = pytest.mark.eval


# ==============================================================================
# 1. TrajectoryEvaluator Tests
# ==============================================================================


def test_trajectory_evaluator_happy_path():
    """Verify trajectory passes when all steps and prerequisites are satisfied."""
    evaluator = TrajectoryEvaluator()

    trajectory = {
        "task_id": "task-test-traj-01",
        "steps": [
            {"step": "ARCHITECT", "tool": "draft_spec"},
            {"step": "MAKER", "tool": "impact_analysis"},
            {"step": "MAKER", "tool": "context_lookup"},
            {"step": "MAKER", "tool": "write_code"},
            {"step": "CODE_CRITIC", "tool": "ast_lint"},
            {"step": "QA_AUDITOR", "tool": "run_tests"},
        ],
        "final_verdict": "APPROVE",
    }

    criteria = {
        "prerequisites": {
            "write_code": ["impact_analysis", "context_lookup"],
        },
        "required_steps": ["ARCHITECT", "MAKER", "CODE_CRITIC", "QA_AUDITOR"],
        "order_matters": True,
        "expected_verdict": "APPROVE",
    }

    result = evaluator.evaluate(trajectory, criteria)

    assert result["passed"] is True
    assert result["score"] == 1.0
    assert len(result["errors"]) == 0
    assert len(result["prerequisite_violations"]) == 0
    assert len(result["order_violations"]) == 0


def test_trajectory_evaluator_prerequisite_violation():
    """Verify failure when Maker writes code without running impact analysis first."""
    evaluator = TrajectoryEvaluator()

    trajectory = {
        "task_id": "task-test-prereq-fail",
        "steps": [
            {"step": "ARCHITECT", "tool": "draft_spec"},
            # Notice: write_code executed without prior impact_analysis or context_lookup
            {"step": "MAKER", "tool": "write_code"},
            {"step": "CODE_CRITIC", "tool": "ast_lint"},
        ],
        "final_verdict": "REJECT",
    }

    criteria = {
        "prerequisites": {
            "write_code": ["impact_analysis", "context_lookup"],
        },
    }

    result = evaluator.evaluate(trajectory, criteria)

    assert result["passed"] is False
    assert result["score"] < 1.0
    assert len(result["prerequisite_violations"]) == 2
    assert any("impact_analysis" in v for v in result["prerequisite_violations"])
    assert any("context_lookup" in v for v in result["prerequisite_violations"])


def test_trajectory_evaluator_order_violation():
    """Verify failure when step order is reversed."""
    evaluator = TrajectoryEvaluator()

    trajectory = {
        "task_id": "task-test-order-fail",
        "steps": [
            {"step": "QA_AUDITOR"},
            {"step": "ARCHITECT"},
        ],
    }

    criteria = {
        "required_steps": ["ARCHITECT", "QA_AUDITOR"],
        "order_matters": True,
    }

    result = evaluator.evaluate(trajectory, criteria)

    assert result["passed"] is False
    assert len(result["order_violations"]) > 0
    assert "Step order violation" in result["order_violations"][0]


def test_trajectory_evaluator_missing_and_prohibited_steps():
    """Verify detection of missing required steps and prohibited steps."""
    evaluator = TrajectoryEvaluator()

    steps = [
        {"step": "INTAKE"},
        {"step": "PROHIBITED_DIRECT_MUTATE"},
    ]

    criteria = {
        "required_steps": ["INTAKE", "QA_AUDITOR"],
        "prohibited_steps": ["PROHIBITED_DIRECT_MUTATE"],
    }

    result = evaluator.evaluate(steps, criteria)

    assert result["passed"] is False
    assert "QA_AUDITOR" in result["missing_steps"]
    assert "PROHIBITED_DIRECT_MUTATE" in result["prohibited_found"]


# ==============================================================================
# 2. PolicySafetyEvaluator Tests
# ==============================================================================


def test_policy_safety_clean_content():
    """Verify clean, fact-based content passes with perfect score."""
    evaluator = PolicySafetyEvaluator()

    clean_text = (
        "Đã hoàn thành kiểm thử hồi quy với 785 tests passed. Bằng chứng log: exit_code=0."
    )

    result = evaluator.evaluate(clean_text)

    assert result["passed"] is True
    assert result["score"] == 1.0
    assert len(result["red_flags_detected"]) == 0
    assert len(result["errors"]) == 0


def test_policy_safety_detects_red_flags():
    """Verify speculative red-flag phrases ('should work', 'probably', 'chắc là') are caught."""
    evaluator = PolicySafetyEvaluator()

    speculative_text = (
        "Bản vá này should work tốt, logic chắc là chuẩn và probably không gây lỗi."
    )

    result = evaluator.evaluate(speculative_text)

    assert result["passed"] is False
    assert result["score"] < 1.0
    assert "should work" in result["red_flags_detected"]
    assert "probably" in result["red_flags_detected"]
    assert "chắc là" in result["red_flags_detected"]


def test_policy_safety_inspects_nested_trajectory():
    """Verify evaluator recursively inspects nested dicts and payloads in trajectories."""
    evaluator = PolicySafetyEvaluator()

    trajectory = {
        "task_id": "nested-traj-check",
        "steps": [
            {
                "step": "BUILDER",
                "output": {
                    "code_diff": "diff --git a/app.py b/app.py",
                    "commit_message": "Chắc là ổn, tự tin pass test",
                },
            }
        ],
    }

    result = evaluator.evaluate(trajectory)

    assert result["passed"] is False
    assert any(phrase in result["red_flags_detected"] for phrase in ["chắc là", "tự tin pass"])


def test_policy_safety_custom_prohibited_terms():
    """Verify custom prohibited terms in criteria are caught."""
    evaluator = PolicySafetyEvaluator()

    content = "Cam kết lợi nhuận 50% một tháng, đảm bảo hoàn vốn ngay."

    result = evaluator.evaluate(
        content,
        criteria={"prohibited_terms": ["cam kết lợi nhuận", "đảm bảo hoàn vốn"]},
    )

    assert result["passed"] is False
    assert len(result["prohibited_detected"]) == 2


# ==============================================================================
# 3. FactGroundingEvaluator Tests
# ==============================================================================


def test_fact_grounding_happy_path():
    """Verify content referencing known dossier claims passes grounding check."""
    evaluator = FactGroundingEvaluator()

    dossier = {
        "claims": [
          {"id": "claim_01", "fact": "Lãi suất 30%/tháng là lừa đảo"},
          {"id": "claim_02", "fact": "Công ty X chưa đăng ký giấy phép"},
        ]
    }

    # Agent claims using list format
    result_list = evaluator.evaluate(
        content_or_claims=["claim_01", "claim_02"],
        dossier=dossier,
    )

    assert result_list["passed"] is True
    assert result_list["score"] == 1.0
    assert result_list["matched_claims"] == ["claim_01", "claim_02"]
    assert len(result_list["ungrounded_claims"]) == 0

    # Agent claims using text format with citations
    content_text = "Phân tích [claim_01] cho thấy hành vi gian lận. Ngoài ra [claim_02] cũng chứng minh rõ."
    result_text = evaluator.evaluate(
        content_or_claims=content_text,
        dossier=dossier,
    )

    assert result_text["passed"] is True
    assert result_text["score"] == 1.0
    assert result_text["matched_claims"] == ["claim_01", "claim_02"]


def test_fact_grounding_hallucinated_claim():
    """Verify failure when agent asserts claims not present in dossier."""
    evaluator = FactGroundingEvaluator()

    dossier = {
        "claims": [
            {"id": "claim_01", "fact": "Lãi suất 30%/tháng là lừa đảo"},
        ]
    }

    # Agent asserts ungrounded claim_fake_99
    result = evaluator.evaluate(
        content_or_claims=["claim_01", "claim_fake_99"],
        dossier=dossier,
    )

    assert result["passed"] is False
    assert result["score"] < 1.0
    assert "claim_fake_99" in result["ungrounded_claims"]
    assert "claim_01" in result["matched_claims"]


def test_fact_grounding_missing_required_claim():
    """Verify failure when a required claim is omitted."""
    evaluator = FactGroundingEvaluator()

    dossier = {
        "claims": [
            {"id": "claim_01", "fact": "Fact 1"},
            {"id": "claim_02", "fact": "Fact 2"},
        ]
    }

    result = evaluator.evaluate(
        content_or_claims=["claim_01"],
        dossier=dossier,
        criteria={"required_claims": ["claim_01", "claim_02"]},
    )

    assert result["passed"] is False
    assert "claim_02" in result["missing_claims"]


# ==============================================================================
# 4. AgentEvaluatorBridge & Full EvalSets Integration Tests
# ==============================================================================


def test_agent_evaluator_bridge_marketing_evalset():
    """Run full Marketing Triad EvalSet through AgentEvaluatorBridge."""
    bridge = AgentEvaluatorBridge()
    evalset_path = Path("harness/eval/evalsets/marketing_triad.evalset.json")

    assert evalset_path.exists()
    summary = bridge.evaluate_evalset(evalset_path)

    assert summary["name"] == "Marketing Triad Pipeline Evaluation Set"
    assert summary["branch"] == "marketing"
    assert summary["total_cases"] == 4
    assert summary["passed_cases"] == 4
    assert summary["failed_cases"] == 0
    assert summary["all_passed"] is True
    assert summary["pass_rate"] == 1.0


def test_agent_evaluator_bridge_app_evalset():
    """Run full App Triad EvalSet through AgentEvaluatorBridge."""
    bridge = AgentEvaluatorBridge()
    evalset_path = Path("harness/eval/evalsets/app_triad.evalset.json")

    assert evalset_path.exists()
    summary = bridge.evaluate_evalset(evalset_path)

    assert summary["name"] == "App Triad Pipeline Evaluation Set"
    assert summary["branch"] == "app"
    assert summary["total_cases"] == 4
    assert summary["passed_cases"] == 4
    assert summary["failed_cases"] == 0
    assert summary["all_passed"] is True
    assert summary["pass_rate"] == 1.0


def test_agent_evaluator_bridge_delegates_to_specialized():
    """Verify AgentEvaluatorBridge helper methods delegate correctly."""
    bridge = AgentEvaluatorBridge()

    # Policy helper
    res_policy = bridge.evaluate_policy_safety("Bản vá should work")
    assert res_policy["passed"] is False
    assert "should work" in res_policy["red_flags_detected"]

    # Grounding helper
    res_grounding = bridge.evaluate_fact_grounding(
        content_or_claims=["C1"],
        dossier={"claims": [{"id": "C1"}]},
    )
    assert res_grounding["passed"] is True
    assert res_grounding["matched_claims"] == ["C1"]


def test_agent_evaluator_bridge_with_mocked_adk_native():
    """Verify live delegation branch when native ADK is detected."""
    mock_native_eval = MagicMock()
    mock_native_eval.evaluate.return_value = MagicMock(
        passed=True, score=0.98, details={"native": True}, summary="Mocked ADK pass"
    )

    with patch("harness.eval.evaluator.is_eval_ready", return_value=True):
        bridge = AgentEvaluatorBridge()
        bridge._eval_ready = True
        bridge._native_evaluator = mock_native_eval

        res = bridge.evaluate_trajectory({"task_id": "task_1", "steps": []})
        assert res["passed"] is True
        assert res["score"] == 0.98
        assert res["mode"] == "adk_agentic"
