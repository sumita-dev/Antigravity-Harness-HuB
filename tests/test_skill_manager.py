"""Unit tests cho Skill Lifecycle Engine (harness/skills/manager.py)."""

import pytest
from pathlib import Path

from harness.skills.manager import SkillManager


@pytest.fixture
def temp_manager(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "plugins" / "code" / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugins" / "marketing" / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)

    brain_dir = tmp_path / "brain"
    return SkillManager(repo_root=repo_root, brain_dir=brain_dir)


def test_lint_skill_valid():
    content = """---
name: test-skill
description: A valid test skill description
---

# Test Skill

## When to Use
Use when testing.
"""
    res = SkillManager.lint_skill(content)
    assert res["valid"] is True
    assert res["errors"] == []
    assert res["metadata"]["name"] == "test-skill"
    assert res["metadata"]["description"] == "A valid test skill description"


def test_lint_skill_empty():
    res = SkillManager.lint_skill("")
    assert res["valid"] is False
    assert any("rỗng" in e for e in res["errors"])


def test_lint_skill_missing_frontmatter():
    content = "# Just a markdown header without frontmatter"
    res = SkillManager.lint_skill(content)
    assert res["valid"] is False
    assert any("YAML frontmatter" in e for e in res["errors"])


def test_lint_skill_invalid_name():
    content = """---
name: "invalid name with spaces!"
description: Test description
---

# Title
Body text.
"""
    res = SkillManager.lint_skill(content)
    assert res["valid"] is False
    assert any("không hợp lệ" in e for e in res["errors"])


def test_lint_skill_missing_description():
    content = """---
name: valid-name
---

# Title
Body text.
"""
    res = SkillManager.lint_skill(content)
    assert res["valid"] is False
    assert any("description" in e for e in res["errors"])


def test_lint_skill_empty_body():
    content = """---
name: valid-name
description: Valid description
---
"""
    res = SkillManager.lint_skill(content)
    assert res["valid"] is False
    assert any("body markdown" in e for e in res["errors"])


def test_create_skill_app_and_marketing(temp_manager):
    app_content = """---
name: app-skill
description: Skill for app branch
---

# App Skill Body
"""
    app_path = temp_manager.create_skill("app-skill", "app", app_content)
    assert app_path.exists()
    assert "plugins" in app_path.parts
    assert "code" in app_path.parts
    assert app_path.name == "SKILL.md"

    mkt_content = """---
name: mkt-skill
description: Skill for marketing branch
---

# Marketing Skill Body
"""
    mkt_path = temp_manager.create_skill("mkt-skill", "marketing", mkt_content)
    assert mkt_path.exists()
    assert "plugins" in mkt_path.parts
    assert "marketing" in mkt_path.parts


def test_create_skill_auto_frontmatter(temp_manager):
    raw_body = """# Auto Generated Title

## Overview
Some auto generated content here.
"""
    meta = {"name": "auto-skill", "description": "Auto generated description"}
    path = temp_manager.create_skill("auto-skill", "app", raw_body, metadata=meta)
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    lint_res = temp_manager.lint_skill(content)
    assert lint_res["valid"] is True
    assert lint_res["metadata"]["name"] == "auto-skill"


def test_create_skill_invalid_raises(temp_manager):
    bad_content = "Invalid content with no frontmatter"
    with pytest.raises(ValueError):
        temp_manager.create_skill("bad-skill", "app", bad_content)


def test_patch_skill(temp_manager):
    content = """---
name: patch-target
description: Target skill for patching
---

# Original Title

## Step 1
Do initial step.
"""
    temp_manager.create_skill("patch-target", "app", content)

    patched_path = temp_manager.patch_skill(
        name="patch-target",
        old_string="Do initial step.",
        new_string="Do enhanced step with verification.",
    )

    new_text = patched_path.read_text(encoding="utf-8")
    assert "Do enhanced step with verification." in new_text
    assert "Do initial step." not in new_text


def test_patch_skill_not_found_raises(temp_manager):
    content = """---
name: patch-target-2
description: Target skill for patching
---

# Title
Body.
"""
    temp_manager.create_skill("patch-target-2", "app", content)

    with pytest.raises(ValueError, match="không tồn tại"):
        temp_manager.patch_skill("patch-target-2", "Non existent string", "Replacement")


def test_stage_approve_and_reject_skill(temp_manager):
    content = """---
name: staged-skill
description: Staged skill description
---

# Staged Skill Body
Content here.
"""
    # 1. Stage
    record = temp_manager.stage_skill(
        name="staged-skill",
        diff_or_content=content,
        metadata={"author": "builder"},
        branch="app",
    )
    stage_id = record["id"]
    assert stage_id.startswith("stage-")
    assert record["status"] == "PENDING"

    pending_list = temp_manager.get_staged_skills("PENDING")
    assert len(pending_list) == 1
    assert pending_list[0]["id"] == stage_id

    # 2. Approve
    approved = temp_manager.approve_staged_skill(stage_id)
    assert approved["status"] == "APPROVED"
    assert "approved_at" in approved

    skill_path = temp_manager.find_skill_path("staged-skill")
    assert skill_path is not None
    assert skill_path.exists()

    # 3. Stage another and reject
    record2 = temp_manager.stage_skill(name="staged-2", diff_or_content=content, branch="marketing")
    rejected = temp_manager.reject_staged_skill(record2["id"], reason="Không đạt yêu cầu")
    assert rejected["status"] == "REJECTED"
    assert rejected["reason"] == "Không đạt yêu cầu"


def test_archive_skill(temp_manager):
    content = """---
name: obsolete-skill
description: Skill to be archived
---

# Obsolete Skill
Body.
"""
    skill_path = temp_manager.create_skill("obsolete-skill", "app", content)
    assert skill_path.exists()

    archived_path = temp_manager.archive_skill("obsolete-skill")
    assert archived_path is not None
    assert archived_path.exists()
    assert "skills_archive" in archived_path.parts
    assert not skill_path.exists()
