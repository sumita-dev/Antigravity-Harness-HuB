import pytest
from pathlib import Path

from harness.memory.trajectory import TrajectoryStore
from harness.skills.router import SkillLoader

def test_event_sourcing(tmp_path):
    store = TrajectoryStore(tmp_path / "trajectories.jsonl")
    
    task_id = "test-task-123"
    evt1 = store.record_event(task_id, "INIT", {"msg": "start"})
    assert evt1["task_id"] == task_id
    assert evt1["event_type"] == "INIT"
    assert "event_id" in evt1
    
    evt2 = store.record_event(task_id, "INTAKE", {"msg": "next"}, parent_id=evt1["event_id"])
    assert evt2["parent_id"] == evt1["event_id"]
    
    events = store.get_events(task_id)
    assert len(events) == 2
    assert events[0]["event_type"] == "INIT"
    assert events[1]["event_type"] == "INTAKE"
    
    replayed = store.replay_events(task_id)
    assert len(replayed) == 2
    assert replayed[0]["event_id"] == evt1["event_id"]
    assert replayed[1]["event_id"] == evt2["event_id"]

def test_skill_dependency_graph(tmp_path):
    skills_dir = tmp_path / "skills"
    
    skill_a_dir = skills_dir / "skill_a"
    skill_a_dir.mkdir(parents=True)
    (skill_a_dir / "SKILL.md").write_text('''---
name: skill_a
dependencies: ["skill_b", "skill_c"]
---
Content of Skill A''', encoding="utf-8")
    
    skill_b_dir = skills_dir / "skill_b"
    skill_b_dir.mkdir(parents=True)
    (skill_b_dir / "SKILL.md").write_text('''---
name: skill_b
dependencies: ["skill_d"]
---
Content of Skill B''', encoding="utf-8")

    skill_c_dir = skills_dir / "skill_c"
    skill_c_dir.mkdir(parents=True)
    (skill_c_dir / "SKILL.md").write_text('''---
name: skill_c
dependencies: ["skill_b"]
---
Content of Skill C''', encoding="utf-8")
    
    skill_d_dir = skills_dir / "skill_d"
    skill_d_dir.mkdir(parents=True)
    (skill_d_dir / "SKILL.md").write_text('''---
name: skill_d
dependencies: ["skill_a"]
---
Content of Skill D''', encoding="utf-8")
    
    loader = SkillLoader(search_dirs=[str(skills_dir)])
    
    deps_a = loader.get_skill_dependencies("skill_a")
    assert deps_a == ["skill_b", "skill_c"]
    
    content_a = loader.load_instructions("skill_a")
    
    assert "Content of Skill A" in content_a
    assert "Content of Skill B" in content_a
    assert "Content of Skill C" in content_a
    assert "Content of Skill D" in content_a
    
    assert "<!-- DEPENDENCY: skill_b -->" in content_a
    assert "<!-- ROOT SKILL: skill_a -->" in content_a
    
    content_a_no_deps = loader.load_instructions("skill_a", include_dependencies=False)
    assert "Content of Skill B" not in content_a_no_deps
    assert "Content of Skill A" in content_a_no_deps
