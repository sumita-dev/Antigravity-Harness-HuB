"""Regression coverage for the deterministic skill bundle linter."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
LINTER = REPO / "scripts" / "lint_harness_skills.py"


def make_fixture(root, skills, routes=None, direct_only=None):
    plugins = root / "plugins"
    for path, contents in skills.items():
        skill_dir = plugins / path
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(contents, encoding="utf-8")
    (root / "configs").mkdir(parents=True, exist_ok=True)
    (root / "configs" / "harness_config.json").write_text(json.dumps({
        "skill_routing": routes or {}, "skill_direct_only": direct_only or []
    }), encoding="utf-8")


def skill(name="good-skill", description="A useful skill"):
    return f"---\nname: {name}\ndescription: {description}\n---\n\nDo the work.\n"


def run_linter(root):
    return subprocess.run([sys.executable, str(LINTER), "--root", str(root)],
                          capture_output=True, text=True, encoding="utf-8")


def test_skill_integrity_linter_accepts_valid_bundle(tmp_path):
    make_fixture(tmp_path, {"code/skills/good-skill": skill() + "See [guide](references/guide.md).\n"},
                 direct_only=["good-skill"])
    (tmp_path / "plugins/code/skills/good-skill/references").mkdir()
    (tmp_path / "plugins/code/skills/good-skill/references/guide.md").write_text("guide", encoding="utf-8")
    result = run_linter(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(("skills", "routes", "direct", "needle"), [
    ({"code/skills/one": skill("duplicate"), "marketing/skills/two": skill("duplicate")}, {}, ["duplicate"], "duplicate skill name"),
    ({"code/skills/one": "---\ndescription: missing name\n---\n"}, {}, ["one"], "name"),
    ({"code/skills/one": skill() + "[broken](references/missing.md)"}, {}, ["good-skill"], "missing link"),
    ({"code/skills/one": skill() + "[local](file:///d:/checkout/guide.md)"}, {}, ["good-skill"], "file:///")
])
def test_skill_integrity_linter_rejects_metadata_and_reference_errors(tmp_path, skills, routes, direct, needle):
    make_fixture(tmp_path, skills, routes, direct)
    result = run_linter(tmp_path)
    assert result.returncode != 0
    assert needle in (result.stdout + result.stderr).lower()


def test_skill_integrity_linter_rejects_unclassified_and_dangling_routes(tmp_path):
    make_fixture(tmp_path, {"code/skills/good": skill("good")},
                 routes={"missing": {"branch": "app", "keywords": ["missing"]}})
    result = run_linter(tmp_path)
    output = (result.stdout + result.stderr).lower()
    assert result.returncode != 0
    assert "missing" in output
    assert "unclassified" in output
