import sys
import os
import json
import shutil
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from harness.state_machine import TaskContext, HarnessState
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.orchestrator import ChiefOrchestrator
import run_harness

REPO_ROOT = Path(__file__).resolve().parents[1]

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

def test_cli_curate(capsys):
    ret = run_harness.main(["--curate"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "BÁO CÁO VÒNG ĐỜI KỸ NĂNG" in captured.out

def test_cli_skills_pending_and_approve(capsys):
    created_skill_dir = REPO_ROOT / "plugins" / "code" / "skills" / "build-fast-api-authentication"
    try:
        # Process a task with auto-distill
        ret = run_harness.main(["--task", "Build fast API authentication", "--branch", "app", "--auto-distill"])
        assert ret == 0
        capsys.readouterr()  # Clear output buffer

        # List pending
        ret_list = run_harness.main(["--skills-pending", "--json"])
        assert ret_list == 0
        captured = capsys.readouterr()
        staged = json.loads(captured.out)
        assert len(staged) >= 1
        stage_id = staged[0]["id"]

        # Approve
        ret_app = run_harness.main(["--skills-approve", stage_id, "--json"])
        assert ret_app == 0
        captured_app = capsys.readouterr()
        app_data = json.loads(captured_app.out)
        assert app_data["status"] == "APPROVED"
    finally:
        if created_skill_dir.exists():
            shutil.rmtree(created_skill_dir, ignore_errors=True)
