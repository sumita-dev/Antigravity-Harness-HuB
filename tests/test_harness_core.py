import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from harness.state_machine import TaskContext, HarnessState
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.orchestrator import ChiefOrchestrator

def test_state_machine_valid_transitions():
    ctx = TaskContext("1", "app")
    assert ctx.state == HarnessState.INIT
    ctx.transition(HarnessState.INTAKE)
    assert ctx.state == HarnessState.INTAKE
    ctx.transition(HarnessState.IMPLEMENTATION)
    assert ctx.state == HarnessState.IMPLEMENTATION
    ctx.transition(HarnessState.AUDIT)
    assert ctx.state == HarnessState.AUDIT

def test_state_machine_invalid_transition():
    ctx = TaskContext("1", "app")
    with pytest.raises(ValueError):
        ctx.transition(HarnessState.AUDIT)

def test_quality_gate_approve():
    ctx = TaskContext("1", "app")
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.IMPLEMENTATION)
    ctx.transition(HarnessState.AUDIT)
    
    gate = AdversarialQualityGate()
    verdict = gate.evaluate(ctx, "Looks good. VERDICT: APPROVE")
    
    assert verdict == Verdict.APPROVE
    assert ctx.state == HarnessState.APPROVED

def test_quality_gate_reject_retry():
    ctx = TaskContext("1", "app")
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.IMPLEMENTATION)
    ctx.transition(HarnessState.AUDIT)
    
    gate = AdversarialQualityGate()
    verdict = gate.evaluate(ctx, "Failed tests. VERDICT: REJECT")
    
    assert verdict == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    assert ctx.critique_rounds == 1

def test_quality_gate_circuit_breaker():
    ctx = TaskContext("1", "app")
    ctx.transition(HarnessState.INTAKE)
    ctx.transition(HarnessState.IMPLEMENTATION)
    ctx.transition(HarnessState.AUDIT)
    
    gate = AdversarialQualityGate(max_rounds=2)
    
    verdict = gate.evaluate(ctx, "VERDICT: REJECT")
    assert verdict == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    
    ctx.transition(HarnessState.AUDIT)
    
    verdict = gate.evaluate(ctx, "VERDICT: REJECT")
    assert verdict == Verdict.REJECT
    assert ctx.state == HarnessState.IMPLEMENTATION
    
    ctx.transition(HarnessState.AUDIT)
    
    verdict = gate.evaluate(ctx, "VERDICT: REJECT")
    assert verdict == Verdict.ESCALATE
    assert ctx.state == HarnessState.ESCALATED

def test_orchestrator_routing():
    orc = ChiefOrchestrator()
    ctx, _ = orc.process_task("Make a cool app", "app")
    assert ctx.state == HarnessState.APPROVED
    
    ctx2, _ = orc.process_task("Make a cool post", "invalid")
    assert ctx2.state == HarnessState.ESCALATED
