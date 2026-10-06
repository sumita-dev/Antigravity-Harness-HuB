"""Unit tests cho Skill Distiller (harness/memory/distiller.py)."""

import pytest

from harness.memory.distiller import SkillDistiller
from harness.memory.harvester import LearningHarvester
from harness.memory.trajectory import TrajectoryStore
from harness.skills.manager import SkillManager


@pytest.fixture
def temp_distiller(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "plugins" / "code" / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugins" / "marketing" / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)

    brain_dir = tmp_path / "brain"
    t_store = TrajectoryStore(path=brain_dir / "trajectories" / "trajectories.jsonl")
    harvester = LearningHarvester(path=brain_dir / "learnings" / "patterns.json")
    mgr = SkillManager(repo_root=repo_root, brain_dir=brain_dir)

    return SkillDistiller(
        trajectory_store=t_store,
        harvester=harvester,
        skill_manager=mgr,
    )


def test_distill_from_trajectory_app_sections(temp_distiller):
    trajectory = {
        "task_id": "test-task-1",
        "branch": "app",
        "task_description": "Xây dựng xác thực JWT bảo mật",
        "steps": [
            {"step": "INTAKE", "data": {"description": "Xây dựng xác thực JWT bảo mật"}},
            {"step": "DESIGN", "data": {"action": "Lập schema JWT token và claims"}},
            {"step": "IMPLEMENTATION", "data": {"action": "Viết mã auth handler và pytest"}},
            {"step": "AUDIT", "data": {"verdict": "VERDICT: APPROVE"}},
        ],
        "final_verdict": "APPROVE",
        "critique_rounds": 1,
        "metadata": {"active_skill": "security-review"},
    }

    result = temp_distiller.distill_from_trajectory(trajectory)
    assert result["name"] is not None
    assert result["branch"] == "app"
    content = result["content"]

    # Kiểm tra 4 phần cốt lõi
    assert "## When to Use" in content
    assert "## Procedure" in content
    assert "## Pitfalls & Mechanisms" in content
    assert "## Verification" in content

    # Kiểm tra lint
    lint_res = SkillManager.lint_skill(content)
    assert lint_res["valid"] is True
    assert lint_res["metadata"]["name"] == result["name"]


def test_distill_from_trajectory_marketing_sections(temp_distiller):
    trajectory = {
        "task_id": "test-task-2",
        "branch": "marketing",
        "task_description": "Soạn kịch bản YouTube tài chính 6 format",
        "steps": [
            {"step": "INTAKE", "data": {"description": "Kịch bản YouTube tài chính"}},
            {"step": "INTEL_RESEARCH", "data": {"action": "Thu thập số liệu thực địa"}},
            {"step": "DRAFT", "data": {"action": "Soạn bản thảo theo format Mổ sổ"}},
            {"step": "AUDIT", "data": {"verdict": "VERDICT: APPROVE"}},
        ],
        "final_verdict": "APPROVE",
        "critique_rounds": 0,
        "metadata": {"active_skill": "boc-phot-storytelling"},
    }

    result = temp_distiller.distill_from_trajectory(trajectory)
    assert result["branch"] == "marketing"
    content = result["content"]

    assert "## When to Use" in content
    assert "## Procedure" in content
    assert "## Pitfalls & Mechanisms" in content
    assert "## Verification" in content
    assert "AI Slop" in content


def test_distill_task_with_staging(temp_distiller):
    t_record = temp_distiller.trajectory_store.save_trajectory(
        task_id="task-stored-123",
        branch="app",
        task_description="Tối ưu database query indexing",
        steps=[
            {"step": "INTAKE", "data": {}},
            {"step": "DESIGN", "data": {}},
            {"step": "IMPLEMENTATION", "data": {}},
            {"step": "AUDIT", "data": {"verdict": "APPROVE"}},
        ],
        final_verdict="APPROVE",
        critique_rounds=0,
    )

    distilled = temp_distiller.distill_task("task-stored-123", stage_immediately=True)
    assert distilled is not None
    assert "stage_record" in distilled
    assert distilled["stage_record"]["status"] == "PENDING"

    # Kiểm tra stage record có trong staging
    staged = temp_distiller.skill_manager.get_staged_skills("PENDING")
    assert any(s["id"] == distilled["stage_record"]["id"] for s in staged)


def test_distill_task_not_found(temp_distiller):
    res = temp_distiller.distill_task("non-existent-task")
    assert res is None


def test_auto_distill_conditions(temp_distiller):
    approved_traj = {
        "task_id": "auto-1",
        "branch": "app",
        "task_description": "Approve task",
        "steps": [{"step": "INTAKE"}],
        "final_verdict": "APPROVE",
        "critique_rounds": 0,
    }
    rejected_traj = {
        "task_id": "auto-2",
        "branch": "app",
        "task_description": "Reject task",
        "steps": [{"step": "INTAKE"}],
        "final_verdict": "REJECT",
        "critique_rounds": 2,
    }

    assert temp_distiller.auto_distill(approved_traj) is not None
    assert temp_distiller.auto_distill(rejected_traj) is None
