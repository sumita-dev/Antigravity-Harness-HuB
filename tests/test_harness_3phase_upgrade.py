# -*- coding: utf-8 -*-
"""Comprehensive unit tests for the 3-Phase Harness Upgrade."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError as AppWorkflowError
from harness.eval.evaluator import (
    AgentEvaluatorBridge,
    FactGroundingEvaluator,
    PolicySafetyEvaluator,
    TrajectoryEvaluator,
)
from harness.marketing_workflow import MarketingWorkflowStore, WorkflowError as MktWorkflowError
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.state_machine import HarnessState, TaskContext
from harness.triad_protocol import (
    AuditVerdictSchema,
    CritiqueVerdictSchema,
    validate_audit_payload,
    validate_critique_payload,
)
from harness.validators.semantic_judge import (
    verify_diff_test_coverage,
    verify_marketing_claim_grounding,
)


def _make_ctx(state: HarnessState = HarnessState.AUDIT) -> TaskContext:
    ctx = TaskContext("upgrade-test", "app")
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.DESIGN)
    ctx.transition(HarnessState.IMPLEMENTATION)
    if state == HarnessState.CRITIQUE:
        ctx.transition(HarnessState.CRITIQUE)
    elif state == HarnessState.AUDIT:
        ctx.transition(HarnessState.AUDIT)
    return ctx


# ==============================================================================
# Phase 1: Mandatory Hallucination Gate in AdversarialQualityGate
# ==============================================================================


def test_phase1_backward_compat_short_mock_strings():
    gate = AdversarialQualityGate()
    ctx = _make_ctx(HarnessState.CRITIQUE)
    assert gate.evaluate_critique(ctx, "VERDICT: APPROVE") == Verdict.APPROVE
    assert ctx.state == HarnessState.AUDIT

    assert gate.evaluate_audit(ctx, "VERDICT: APPROVE") == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_phase1_speculative_language_rejected_in_critique_and_audit():
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)
    ctx_c = _make_ctx(HarnessState.CRITIQUE)
    v_c = gate.evaluate_critique(ctx_c, "This implementation should work and is probably fine. VERDICT: APPROVE")
    assert v_c == Verdict.REJECT
    assert ctx_c.state == HarnessState.IMPLEMENTATION
    assert ctx_c.critique_rounds == 1
    assert any(s["step"] == "HALLUCINATION_GATE" for s in ctx_c.trace_steps)

    ctx_a = _make_ctx(HarnessState.AUDIT)
    v_a = gate.evaluate_audit(ctx_a, "Everything looks good to me, should work. VERDICT: APPROVE")
    assert v_a == Verdict.REJECT
    assert ctx_a.state == HarnessState.IMPLEMENTATION
    assert ctx_a.qa_rounds == 1
    assert any(s["step"] == "HALLUCINATION_GATE" for s in ctx_a.trace_steps)


def test_phase1_sycophancy_rejected():
    gate = AdversarialQualityGate()
    ctx = _make_ctx(HarnessState.CRITIQUE)
    v = gate.evaluate_critique(ctx, "Your hypothesis is correct! VERDICT: APPROVE")
    assert v == Verdict.REJECT
    assert any(s["step"] == "HALLUCINATION_GATE" for s in ctx.trace_steps)


def test_phase1_unverified_completion_claim_rejected_then_approved_with_execute_step():
    gate = AdversarialQualityGate()
    ctx = _make_ctx(HarnessState.AUDIT)

    # Without EXECUTE exit_code == 0 -> REJECT
    v1 = gate.evaluate_audit(ctx, "All tests passed and build succeeded cleanly. VERDICT: APPROVE")
    assert v1 == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.qa_rounds == 1

    # Record real EXECUTE step with exit_code == 0 and re-submit to AUDIT
    ctx.record_step("EXECUTE", {"command": "python -m pytest -q", "exit_code": 0, "stdout": "10 passed"})
    ctx.transition(HarnessState.AUDIT)
    v2 = gate.evaluate_audit(ctx, "All tests passed and build succeeded cleanly. VERDICT: APPROVE")
    assert v2 == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_phase1_strict_paths_rejects_missing_path(tmp_path: Path):
    gate = AdversarialQualityGate()
    ctx = _make_ctx(HarnessState.AUDIT)
    v = gate.evaluate_audit(
        ctx,
        "Verified `nonexistent/missing_file.py` cleanly. VERDICT: APPROVE",
        strict_paths=True,
        base_dir=tmp_path,
    )
    assert v == Verdict.REJECT
    assert any(s["step"] == "HALLUCINATION_GATE" for s in ctx.trace_steps)


def test_phase1_circuit_breaker_escalates_on_repeated_hallucinations():
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)
    ctx = _make_ctx(HarnessState.CRITIQUE)

    assert gate.evaluate_critique(ctx, "This should work. VERDICT: APPROVE") == Verdict.REJECT
    assert ctx.critique_rounds == 1

    ctx.transition(HarnessState.CRITIQUE)
    assert gate.evaluate_critique(ctx, "This probably works. VERDICT: APPROVE") == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED


def test_phase1_enforce_flag_can_disable_guard():
    gate = AdversarialQualityGate()
    ctx = _make_ctx(HarnessState.CRITIQUE)
    v = gate.evaluate_critique(
        ctx,
        "This should work. VERDICT: APPROVE",
        enforce_hallucination_guard=False,
    )
    assert v == Verdict.APPROVE


# ==============================================================================
# Phase 2: Structured Output Schemas
# ==============================================================================


def test_phase2_schemas_and_validation():
    crit_schema = CritiqueVerdictSchema.to_json_schema()
    assert crit_schema["type"] == "object"
    assert "verdict" in crit_schema["properties"]
    assert "findings" in crit_schema["required"]

    audit_schema = AuditVerdictSchema.to_json_schema()
    assert audit_schema["type"] == "object"
    assert "executed_commands" in audit_schema["required"]

    # Critique: REJECT requires non-empty findings
    ok, errs = validate_critique_payload({"verdict": "REJECT", "summary": "Found issue", "findings": []})
    assert not ok
    assert any("findings" in e for e in errs)

    ok2, errs2 = validate_critique_payload(
        CritiqueVerdictSchema(verdict="REJECT", summary="Gap found", findings=["Missing edge case"]).to_dict()
    )
    assert ok2 and errs2 == []

    # Audit: APPROVE requires non-empty executed_commands with exit_code == 0
    ok_a1, errs_a1 = validate_audit_payload({"verdict": "APPROVE", "summary": "Looks ok", "executed_commands": []})
    assert not ok_a1

    ok_a2, errs_a2 = validate_audit_payload(
        {"verdict": "APPROVE", "summary": "Failed", "executed_commands": [{"command": "pytest", "exit_code": 1}]}
    )
    assert not ok_a2

    ok_a3, errs_a3 = validate_audit_payload(
        AuditVerdictSchema(
            verdict="APPROVE",
            summary="Verified suite",
            executed_commands=[{"command": "python -m pytest -q", "exit_code": 0}],
        ).to_dict()
    )
    assert ok_a3 and errs_a3 == []


def test_phase2_quality_gate_accepts_structured_dict_and_json_string():
    gate = AdversarialQualityGate()
    ctx = _make_ctx(HarnessState.CRITIQUE)

    # Invalid structured critique (REJECT without findings) -> REJECT
    v_bad = gate.evaluate_critique(ctx, {"verdict": "REJECT", "summary": "Bad", "findings": []})
    assert v_bad == Verdict.REJECT
    assert ctx.critique_rounds == 1

    # Valid structured critique (JSON string) -> APPROVE
    ctx.transition(HarnessState.CRITIQUE)
    crit_json = json.dumps(
        CritiqueVerdictSchema(verdict="APPROVE", summary="All ACs mapped cleanly.", findings=[]).to_dict()
    )
    assert gate.evaluate_critique(ctx, crit_json) == Verdict.APPROVE
    assert ctx.state == HarnessState.AUDIT

    # Valid structured audit dict with executed_commands -> APPROVE
    audit_payload = AuditVerdictSchema(
        verdict="APPROVE",
        summary="All tests passed cleanly.",
        executed_commands=[{"command": "python -m pytest -q", "exit_code": 0}],
    ).to_dict()
    assert gate.evaluate_audit(ctx, audit_payload) == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED


def test_phase2_workflow_schema_validation_helpers():
    with pytest.raises(AppWorkflowError):
        AppWorkflowStore.validate_structured_verdict(
            {"verdict": "APPROVE", "summary": "No commands", "executed_commands": []},
            kind="audit",
        )
    valid = AppWorkflowStore.validate_structured_verdict(
        {"verdict": "APPROVE", "summary": "OK", "executed_commands": [{"command": "pytest", "exit_code": 0}]},
        kind="audit",
    )
    assert valid["verdict"] == "APPROVE"

    with pytest.raises(MktWorkflowError):
        MarketingWorkflowStore.validate_structured_verdict(
            {"verdict": "REJECT", "summary": "No findings", "findings": []},
            kind="critique",
        )


# ==============================================================================
# Phase 3: Semantic Grounding & Transparent ADK Evaluator
# ==============================================================================


def test_phase3_verify_marketing_claim_grounding():
    dossier = {
        "claims": [
            {"id": "claim_01", "text": "Inflation rose 3.2% YoY."},
            {"id": "claim_02", "text": "Federal Reserve held rates steady."},
        ]
    }

    res_ok = verify_marketing_claim_grounding(
        "According to [claim_01], inflation rose 3.2% YoY, while [claim_02] notes steady rates.",
        dossier,
    )
    assert res_ok["is_grounded"] is True
    assert res_ok["verdict"] == "APPROVE"
    assert res_ok["matched_claims"] == ["claim_01", "claim_02"]
    assert res_ok["ungrounded_claims"] == []

    res_bad = verify_marketing_claim_grounding(
        "Based on [claim_01] and [claim_99], rates doubled.",
        dossier,
    )
    assert res_bad["is_grounded"] is False
    assert res_bad["verdict"] == "REJECT"
    assert "claim_99" in res_bad["ungrounded_claims"]


def test_phase3_verify_diff_test_coverage():
    # Dummy command only -> REJECT
    res_dummy = verify_diff_test_coverage(
        diff_files=["harness/quality_gate.py"],
        executed_commands=['python -c "print(\'ok\')"'],
    )
    assert res_dummy["is_covered"] is False
    assert res_dummy["verdict"] == "REJECT"
    assert len(res_dummy["dummy_commands_detected"]) == 1

    # Broad pytest run -> APPROVE
    res_broad = verify_diff_test_coverage(
        diff_files=["harness/quality_gate.py"],
        executed_commands=["python -m pytest -q"],
        test_output="1084 passed",
    )
    assert res_broad["is_covered"] is True
    assert res_broad["verdict"] == "APPROVE"

    # Targeted pytest run that misses modified file -> REJECT
    res_targeted_miss = verify_diff_test_coverage(
        diff_files=["harness/quality_gate.py"],
        executed_commands=["python -m pytest tests/test_other.py -q"],
        test_output="1 passed",
    )
    assert res_targeted_miss["is_covered"] is False
    assert "harness/quality_gate.py" in res_targeted_miss["uncovered_files"]


def test_phase3_evaluator_strict_adk_and_transparent_error_mode():
    fake_adk_eval = types.ModuleType("google.adk.evaluation")

    class BrokenAgentEvaluator:
        def __init__(self, config=None):
            pass

        def evaluate(self, *args, **kwargs):
            raise RuntimeError("ADK backend unavailable")

    fake_adk_eval.AgentEvaluator = BrokenAgentEvaluator

    with patch("harness.eval.evaluator.is_eval_ready", return_value=True), patch(
        "harness.eval.evaluator.importlib.import_module", return_value=fake_adk_eval
    ):
        # strict_adk=False -> transparent fallback mode + adk_error
        traj_eval = TrajectoryEvaluator(strict_adk=False)
        res = traj_eval.evaluate([{"step": "INTAKE"}], {"required_steps": ["INTAKE"]})
        assert res["mode"] == "deterministic_on_adk_error"
        assert "ADK backend unavailable" in res["adk_error"]
        assert res["passed"] is True

        pol_eval = PolicySafetyEvaluator(strict_adk=False)
        res_pol = pol_eval.evaluate("Clean verified report")
        assert res_pol["mode"] == "deterministic_on_adk_error"
        assert "ADK backend unavailable" in res_pol["adk_error"]

        fact_eval = FactGroundingEvaluator(strict_adk=False)
        res_fact = fact_eval.evaluate("See [claim_01]", {"claims": [{"id": "claim_01"}]})
        assert res_fact["mode"] == "deterministic_on_adk_error"
        assert "ADK backend unavailable" in res_fact["adk_error"]

        bridge = AgentEvaluatorBridge(strict_adk=False)
        res_bridge = bridge.evaluate_trajectory({"steps": [{"step": "INTAKE"}]}, {"required_steps": ["INTAKE"]})
        assert res_bridge["mode"] == "deterministic_on_adk_error"
        assert "ADK backend unavailable" in res_bridge["adk_error"]

        # strict_adk=True -> re-raises exception
        strict_traj = TrajectoryEvaluator(strict_adk=True)
        with pytest.raises(RuntimeError, match="ADK backend unavailable"):
            strict_traj.evaluate([{"step": "INTAKE"}])

        strict_pol = PolicySafetyEvaluator(strict_adk=True)
        with pytest.raises(RuntimeError, match="ADK backend unavailable"):
            strict_pol.evaluate("Clean report")

        strict_fact = FactGroundingEvaluator(strict_adk=True)
        with pytest.raises(RuntimeError, match="ADK backend unavailable"):
            strict_fact.evaluate("See [claim_01]", {"claims": [{"id": "claim_01"}]})
