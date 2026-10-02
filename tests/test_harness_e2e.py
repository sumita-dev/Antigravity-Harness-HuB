import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from harness.state_machine import TaskContext, HarnessState
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.orchestrator import ChiefOrchestrator

def test_app_branch_e2e():
    orc = ChiefOrchestrator()
    # Mocking that the first round fails, second round passes
    ctx, verdict = orc.process_task("Build login system", "app", mock_checker_output="VERDICT: REJECT")
    
    assert verdict == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 1
    
    # Try again
    verdict2 = orc.submit_for_review(ctx, "VERDICT: APPROVE")
    assert verdict2 == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED

def test_marketing_branch_e2e():
    orc = ChiefOrchestrator()
    # Mocking 2 round review where both fail, 3rd escalate
    ctx, verdict = orc.process_task("Write ads copy", "marketing", mock_checker_output="VERDICT: REJECT")
    assert verdict == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 1
    
    verdict2 = orc.submit_for_review(ctx, "VERDICT: REJECT")
    assert verdict2 == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 2
    
    verdict3 = orc.submit_for_review(ctx, "VERDICT: REJECT")
    assert verdict3 == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED
