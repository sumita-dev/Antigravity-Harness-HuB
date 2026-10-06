"""Unit tests cho Curator Engine (harness/skills/curator.py)."""

from datetime import datetime, timezone, timedelta
import pytest
from pathlib import Path

from harness.skills.curator import SkillCurator
from harness.skills.manager import SkillManager
from harness.skills.router import SkillLoader


@pytest.fixture
def temp_curator_setup(tmp_path):
    repo_root = tmp_path / "repo"
    app_skills = repo_root / "plugins" / "code" / "skills"
    mkt_skills = repo_root / "plugins" / "marketing" / "skills"
    app_skills.mkdir(parents=True, exist_ok=True)
    mkt_skills.mkdir(parents=True, exist_ok=True)

    brain_dir = tmp_path / "brain"
    loader = SkillLoader(search_dirs=[app_skills, mkt_skills])
    manager = SkillManager(repo_root=repo_root, brain_dir=brain_dir)
    curator = SkillCurator(brain_dir=brain_dir, skill_loader=loader, skill_manager=manager)

    return {
        "repo_root": repo_root,
        "loader": loader,
        "manager": manager,
        "curator": curator,
    }


def test_track_usage(temp_curator_setup):
    curator = temp_curator_setup["curator"]

    stat1 = curator.track_usage("test-skill", task_id="task-1")
    assert stat1["usage_count"] == 1
    assert "task-1" in stat1["tasks"]

    stat2 = curator.track_usage("test-skill", task_id="task-2")
    assert stat2["usage_count"] == 2
    assert "task-2" in stat2["tasks"]

    fetched = curator.get_skill_stats("test-skill")
    assert fetched["usage_count"] == 2


def test_evaluate_lifecycle_stages(temp_curator_setup):
    curator = temp_curator_setup["curator"]
    manager = temp_curator_setup["manager"]
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Skill Active (used 2 days ago)
    manager.create_skill("active-skill", "app", "---\nname: active-skill\ndescription: active\n---\n# Body")
    t_active = (now - timedelta(days=2)).isoformat()
    curator.track_usage("active-skill", timestamp=t_active)

    # 2. Skill Stale (used 20 days ago)
    manager.create_skill("stale-skill", "app", "---\nname: stale-skill\ndescription: stale\n---\n# Body")
    t_stale = (now - timedelta(days=20)).isoformat()
    curator.track_usage("stale-skill", timestamp=t_stale)

    # 3. Skill Archive Candidate (used 45 days ago)
    manager.create_skill("archive-skill", "app", "---\nname: archive-skill\ndescription: archive\n---\n# Body")
    t_arch = (now - timedelta(days=45)).isoformat()
    curator.track_usage("archive-skill", timestamp=t_arch)

    report = curator.evaluate_lifecycle(
        active_days_threshold=14,
        archive_days_threshold=30,
        now_dt=now,
    )

    active_names = [s["name"] for s in report["active"]]
    stale_names = [s["name"] for s in report["stale"]]
    archive_names = [s["name"] for s in report["archive_candidates"]]

    assert "active-skill" in active_names
    assert "stale-skill" in stale_names
    assert "archive-skill" in archive_names


def test_find_consolidation_candidates(temp_curator_setup):
    manager = temp_curator_setup["manager"]
    curator = temp_curator_setup["curator"]

    skill_1 = """---
name: meta-ads-copywriter
description: Viết bài quảng cáo Facebook Meta Ads chuyển đổi cao cho thời trang mỹ phẩm
---

# Meta Ads Copywriter
Hướng dẫn viết content quảng cáo Facebook Ads, tối ưu ROI, chuyển đổi cao cho ngành hàng thời trang mỹ phẩm bán lẻ.
"""
    skill_2 = """---
name: facebook-ads-writer
description: Viết bài quảng cáo Facebook Meta Ads chuyển đổi cao cho thời trang mỹ phẩm bán buôn
---

# Facebook Ads Writer
Hướng dẫn viết content quảng cáo Facebook Ads, tối ưu ROI, chuyển đổi cao cho ngành hàng thời trang mỹ phẩm bán buôn.
"""
    manager.create_skill("meta-ads-copywriter", "marketing", skill_1)
    manager.create_skill("facebook-ads-writer", "marketing", skill_2)

    proposals = curator.find_consolidation_candidates(similarity_threshold=0.5)
    assert len(proposals) >= 1
    top_pair = proposals[0]
    assert {top_pair["skill_a"], top_pair["skill_b"]} == {"meta-ads-copywriter", "facebook-ads-writer"}
    assert top_pair["similarity"] >= 0.5


def test_auto_archive_stale_skills(temp_curator_setup):
    manager = temp_curator_setup["manager"]
    curator = temp_curator_setup["curator"]
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    manager.create_skill("old-skill", "app", "---\nname: old-skill\ndescription: old\n---\n# Body")
    t_arch = (now - timedelta(days=50)).isoformat()
    curator.track_usage("old-skill", timestamp=t_arch)

    # Dry run
    dry_list = curator.auto_archive_stale_skills(dry_run=True, now_dt=None)
    # Re-evaluate with specific now_dt
    report = curator.evaluate_lifecycle(archive_days_threshold=30, now_dt=now)
    assert any(c["name"] == "old-skill" for c in report["archive_candidates"])

    # Actual archive
    archived = curator.auto_archive_stale_skills(dry_run=False, manager=manager, archive_days_threshold=30)
    assert manager.find_skill_path("old-skill") is None or "old-skill" in archived
