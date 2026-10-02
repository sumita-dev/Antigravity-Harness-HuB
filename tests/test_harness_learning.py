import os
import json
import pytest
from pathlib import Path

from harness.memory.trajectory import TrajectoryStore
from harness.memory.harvester import LearningHarvester
from harness.state_machine import TaskContext, HarnessState
from harness.orchestrator import ChiefOrchestrator
from harness.quality_gate import Verdict

def test_trajectory_store(tmp_path):
    store = TrajectoryStore(path=tmp_path / "trajectories.jsonl")
    
    # Save trajectory
    store.save_trajectory(
        task_id="t1",
        branch="app",
        task_description="Build a button",
        steps=[{"step": "INTAKE"}],
        final_verdict="APPROVE",
        critique_rounds=1
    )
    
    # Retrieve trajectory
    trajectories = store.get_trajectories(branch="app")
    assert len(trajectories) == 1
    assert trajectories[0]["task_id"] == "t1"
    assert trajectories[0]["final_verdict"] == "APPROVE"

def test_learning_harvester_approve(tmp_path):
    harvester = LearningHarvester(path=tmp_path / "patterns.json")
    trajectory = {
        "task_id": "t1",
        "branch": "app",
        "task_description": "Build a green button",
        "steps": [{"step": "INTAKE"}],
        "final_verdict": "APPROVE",
        "critique_rounds": 1
    }
    
    pattern = harvester.harvest(trajectory)
    assert pattern["pattern_type"] == "SUCCESS"
    assert pattern["branch"] == "app"
    
    relevant = harvester.retrieve_relevant_patterns("green button", branch="app")
    assert len(relevant) == 1
    assert relevant[0]["id"] == pattern["id"]

def test_learning_harvester_escalate(tmp_path):
    harvester = LearningHarvester(path=tmp_path / "patterns.json")
    trajectory = {
        "task_id": "t2",
        "branch": "marketing",
        "task_description": "Write a blog post",
        "steps": [{"step": "INTAKE"}],
        "final_verdict": "ESCALATE",
        "critique_rounds": 2
    }
    
    pattern = harvester.harvest(trajectory)
    assert pattern["pattern_type"] == "ANTI_PATTERN"
    assert pattern["branch"] == "marketing"

def test_task_context_record_step():
    ctx = TaskContext("t1", "app")
    assert hasattr(ctx, "trace_steps")
    ctx.record_step("INTAKE", {"info": "test"})
    assert len(ctx.trace_steps) == 1
    assert ctx.trace_steps[0]["step"] == "INTAKE"
    assert ctx.trace_steps[0]["payload"]["info"] == "test"
    assert "timestamp" in ctx.trace_steps[0]

def test_chief_orchestrator_integration(tmp_path, monkeypatch):
    # Patch default paths to use tmp_path for isolated testing
    monkeypatch.setattr(TrajectoryStore, "DEFAULT_PATH", tmp_path / "trajectories.jsonl")
    monkeypatch.setattr(LearningHarvester, "DEFAULT_PATH", tmp_path / "patterns.json")
    
    orchestrator = ChiefOrchestrator()
    
    # Process a task that approves
    context, verdict = orchestrator.process_task("Build a search bar", "app", mock_checker_output="VERDICT: APPROVE")
    assert verdict == Verdict.APPROVE
    
    # Check that steps were recorded
    assert len(context.trace_steps) >= 4
    step_names = [s["step"] for s in context.trace_steps]
    assert "INTAKE" in step_names
    assert "DESIGN" in step_names
    assert "IMPLEMENTATION" in step_names
    assert "AUDIT" in step_names
    
    # Check that trajectory was saved
    trajectories = orchestrator.trajectory_store.get_trajectories(branch="app")
    assert len(trajectories) == 1
    assert trajectories[0]["final_verdict"] == "APPROVE"
    
    # Check that pattern was harvested
    patterns = orchestrator.learning_harvester.retrieve_relevant_patterns("search bar", branch="app")
    assert len(patterns) == 1
    assert patterns[0]["pattern_type"] == "SUCCESS"
