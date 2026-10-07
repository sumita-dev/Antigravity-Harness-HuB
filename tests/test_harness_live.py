import pytest
import subprocess
import json
import sys
from pathlib import Path

from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.state_machine import TaskContext, HarnessState

def test_evaluate_execution_success():
    gate = AdversarialQualityGate(max_rounds=2)
    context = TaskContext(task_id="t1", branch="app")
    context.state = HarnessState.AUDIT
    
    # Successful command
    command = f'{sys.executable} -c "exit(0)"'
    verdict = gate.evaluate_execution(context, command)
    
    assert verdict == Verdict.APPROVE
    assert context.state == HarnessState.APPROVED

def test_evaluate_execution_failure_then_reject():
    gate = AdversarialQualityGate(max_rounds=2)
    context = TaskContext(task_id="t2", branch="app")
    context.state = HarnessState.AUDIT
    
    command = f'{sys.executable} -c "exit(1)"'
    verdict = gate.evaluate_execution(context, command)
    
    assert verdict == Verdict.REJECT
    assert context.critique_rounds == 1
    assert context.state == HarnessState.IMPLEMENTATION

def test_evaluate_execution_circuit_breaker():
    gate = AdversarialQualityGate(max_rounds=2)
    context = TaskContext(task_id="t3", branch="app")
    context.state = HarnessState.AUDIT
    
    command = f'{sys.executable} -c "exit(1)"'
    
    # 1st fail
    v1 = gate.evaluate_execution(context, command)
    assert v1 == Verdict.REJECT
    
    # 2nd fail
    context.state = HarnessState.AUDIT  # reset to AUDIT for next evaluation
    v2 = gate.evaluate_execution(context, command)
    assert v2 == Verdict.ESCALATE
    assert context.state == HarnessState.ESCALATED
    

def test_dispatch_subagents_schema():
    script_path = Path(__file__).parent.parent / "scripts" / "dispatch_subagents.py"
    
    import os
    result = subprocess.run(
        [sys.executable, str(script_path), "--export-all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    
    assert result.returncode == 0
    agents = json.loads(result.stdout)
    agent_names = [a["name"] for a in agents]
    
    expected_agents = ["architect", "design_reviewer", "builder", "qa_auditor", "web_researcher", "creator", "compliance_critic"]
    for ea in expected_agents:
        assert ea in agent_names, f"{ea} not found in exported agents"
    
    # Test --export-schema for a specific agent
    result_architect = subprocess.run(
        [sys.executable, str(script_path), "--export-schema", "architect"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    assert result_architect.returncode == 0
    architect_data = json.loads(result_architect.stdout)
    assert architect_data["name"] == "architect"
    assert "description" in architect_data
    assert "system_prompt" in architect_data
    assert architect_data["role"] == "maker"
    assert architect_data["branch"] == "app"
    assert architect_data["model"] == "inherit"
    assert "Metadata only" in architect_data["runtime_enforcement"]
    reviewer = next(agent for agent in agents if agent["name"] == "design_reviewer")
    assert reviewer["role"] == "checker"
