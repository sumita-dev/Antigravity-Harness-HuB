import os
import json
import yaml
import pytest
from harness.skills.router import SkillLoader

MARKETING_SKILLS = [
    "boc-phot-storytelling",
    "check-youtube-policy",
    "yt-competitor-analyzer",
    "alex-hormozi-offer-builder",
    "alex-hormozi-money-models",
    "kahneman-creative-ads",
    "traffic-secrets-playbook",
    "cong-thuc-viet-content-by-noti-v4",
    "viet-content-seo-geo-v5",
    "meta-ads-analyzer-mod-by-noti",
    "fb-admin",
    "framework-marketing-da-kenh"
]

CODE_SKILLS = [
    "accessibility", "advisor", "app", "arena", "database-migrations",
    "domain-modeling", "forensics", "gitnexus-plan", "gitnexus-review",
    "gitnexus-work", "hillclimb", "impeccable", "loop-circuit-breaker",
    "ponytail-review", "reverse-lab", "security-review", "systematic-debugging",
    "test-driven-development", "verification-before-completion", "verify-ui", "why"
]

def test_marketing_skills_exist_and_frontmatter_valid():
    for skill_name in MARKETING_SKILLS:
        skill_file = os.path.join("plugins", "marketing", "skills", skill_name, "SKILL.md")
        assert os.path.exists(skill_file), f"Skill file missing: {skill_file}"
        
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Frontmatter MUST start at line 1
        assert content.startswith("---\n") or content.startswith("---\r\n"), (
            f"Skill {skill_name} does not start with YAML frontmatter at line 1"
        )

        # Parse YAML frontmatter
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Skill {skill_name} does not have closing delimiter '---'"
        
        frontmatter_raw = parts[1]
        fm = yaml.safe_load(frontmatter_raw)
        
        assert isinstance(fm, dict), f"Frontmatter in {skill_name} is not a valid YAML dict"
        assert "name" in fm, f"Frontmatter in {skill_name} missing 'name'"
        assert fm["name"] == skill_name, f"Skill name in frontmatter {fm['name']} != {skill_name}"
        assert "description" in fm and len(fm["description"].strip()) > 0, (
            f"Skill {skill_name} missing description in frontmatter"
        )

def test_code_skills_exist_and_frontmatter_valid():
    for skill_name in CODE_SKILLS:
        skill_file = os.path.join("plugins", "code", "skills", skill_name, "SKILL.md")
        assert os.path.exists(skill_file), f"Code skill file missing: {skill_file}"
        
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert content.startswith("---\n") or content.startswith("---\r\n"), (
            f"Skill {skill_name} does not start with YAML frontmatter at line 1"
        )

        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Skill {skill_name} does not have closing delimiter '---'"
        
        frontmatter_raw = parts[1]
        fm = yaml.safe_load(frontmatter_raw)
        
        assert isinstance(fm, dict), f"Frontmatter in {skill_name} is not a valid YAML dict"
        assert "name" in fm, f"Frontmatter in {skill_name} missing 'name'"
        assert fm["name"] == skill_name, f"Skill name in frontmatter {fm['name']} != {skill_name}"
        assert "description" in fm and len(fm["description"].strip()) > 0, (
            f"Skill {skill_name} missing description in frontmatter"
        )

def test_skill_loader_loads_all_marketing_skills():
    loader = SkillLoader()
    for skill_name in MARKETING_SKILLS:
        instructions = loader.load_instructions(skill_name)
        assert instructions is not None, f"Failed to load instructions for {skill_name}"
        assert len(instructions) > 50, f"Instructions too short for {skill_name}"

def test_skill_loader_loads_all_code_skills():
    loader = SkillLoader()
    for skill_name in CODE_SKILLS:
        instructions = loader.load_instructions(skill_name)
        assert instructions is not None, f"Failed to load instructions for {skill_name}"
        assert len(instructions) > 50, f"Instructions too short for {skill_name}"

def test_agents_skills_json_configured():
    for config_path in [".agents/skills.json", ".agent/skills.json"]:
        assert os.path.exists(config_path), f"Missing {config_path}"
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "entries" in data, f"Missing 'entries' in {config_path}"
        paths = [e.get("path") for e in data["entries"]]
        assert any("marketing" in p for p in paths), f"Marketing skills path not in entries of {config_path}"
        assert any("code" in p for p in paths), f"Code skills path not in entries of {config_path}"

def test_gemini_md_documents_all_marketing_skills():
    assert os.path.exists("GEMINI.md"), "Missing GEMINI.md"
    with open("GEMINI.md", "r", encoding="utf-8") as f:
        content = f.read()
    for skill_name in MARKETING_SKILLS:
        slash_cmd = f"/{skill_name}"
        assert slash_cmd in content, f"Slash command {slash_cmd} not documented in GEMINI.md"

@pytest.mark.skipif(
    not os.path.exists(os.path.expanduser("~/.gemini/config")),
    reason="Chỉ chạy trên máy dev đã cài global config (không chạy được trên CI)",
)
def test_global_config_skills_deployed():
    global_plugin_skills_dir = os.path.expanduser("~/.gemini/config/plugins/marketing/skills")
    assert os.path.exists(global_plugin_skills_dir), f"Global marketing plugin skills directory {global_plugin_skills_dir} missing"
    for skill_name in MARKETING_SKILLS:
        global_file = os.path.join(global_plugin_skills_dir, skill_name, "SKILL.md")
        assert os.path.exists(global_file), f"Global skill file missing: {global_file}"

    global_code_plugin_skills_dir = os.path.expanduser("~/.gemini/config/plugins/code/skills")
    assert os.path.exists(global_code_plugin_skills_dir), f"Global code plugin skills directory {global_code_plugin_skills_dir} missing"
    for skill_name in CODE_SKILLS:
        global_file = os.path.join(global_code_plugin_skills_dir, skill_name, "SKILL.md")
        assert os.path.exists(global_file), f"Global skill file missing: {global_file}"
