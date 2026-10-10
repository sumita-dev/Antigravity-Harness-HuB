import pytest
import os
from harness.skills.router import SkillRouter, SkillLoader
from harness.orchestrator import ChiefOrchestrator

def test_skill_routing_app_fallback():
    router = SkillRouter()
    skill, branch = router.route("làm cái tính năng login")
    assert branch == "app"
    assert skill is None

def test_skill_routing_marketing_fallback():
    router = SkillRouter()
    skill, branch = router.route("viết bài content cho facebook")
    assert branch == "marketing"
    assert skill is None

def test_skill_routing_specific_skills():
    router = SkillRouter()
    
    skill, branch = router.route("cần bóc phốt ông A")
    assert skill == "boc-phot-storytelling"
    assert branch == "marketing"

    skill, branch = router.route("xây dựng alex hormozi offer")
    assert skill == "alex-hormozi-offer-builder"
    assert branch == "marketing"

    skill, branch = router.route("giải quyết lỗi ngầm bằng khảo cổ")
    assert skill == "forensics"
    assert branch == "app"

    skill, branch = router.route("hướng dẫn làm app và mvp")
    assert skill == "app"
    assert branch == "app"

    skill, branch = router.route("tạo app cho anh")
    assert skill == "app"
    assert branch == "app"

    skill, branch = router.route("viết app quản lý")
    assert skill == "app"
    assert branch == "app"

    skill, branch = router.route("code app bán hàng")
    assert skill == "app"
    assert branch == "app"
    
    skill, branch = router.route("viết code theo test-driven-development")
    assert skill == "test-driven-development"
    assert branch == "app"

    skill, branch = router.route("phân tích quảng cáo meta bị cpm tăng")
    assert skill == "meta-ads-analyzer-mod-by-noti"
    assert branch == "marketing"

    skill, branch = router.route("kiểm tra vi phạm kịch bản cho video")
    assert skill == "check-youtube-policy"
    assert branch == "marketing"

    skill, branch = router.route("sử dụng mitmproxy để dịch ngược")
    assert skill == "reverse-lab"
    assert branch == "app"

    skill, branch = router.route("so sánh phương án lai ghép giải thuật")
    assert skill == "arena"
    assert branch == "app"

    skill, branch = router.route("tra cứu wiki về obsidian")
    assert skill == "query-wiki"
    assert branch == "app"

    skill, branch = router.route("tiêu hoá source này vào vault")
    assert skill == "ingest-source"
    assert branch == "app"

    skill, branch = router.route("kiểm tra wiki sức khỏe vault")
    assert skill == "lint-wiki"
    assert branch == "app"

    skill, branch = router.route("lưu bộ nhớ vào vault obsidian")
    assert skill == "second-brain-memory"
    assert branch == "app"

    # Test priority (longest match)
    # If a text has multiple keywords, it should pick the skill with longest matched keyword
    # Let's say text: "viết bài bóc phốt và làm offer"
    # "viết bài" -> fallback marketing, "bóc phốt" -> 8 chars, "làm offer" -> 9 chars
    skill, branch = router.route("bóc phốt offer builder")
    assert skill == "alex-hormozi-offer-builder" # "offer builder" is 13 chars, "bóc phốt" is 8 chars

def test_skill_loader():
    loader = SkillLoader()
    # Check if it returns None for non-existent
    content = loader.load_instructions("non_existent_skill_123")
    assert content is None

    # Test loading code skill from plugins/code/skills
    content_app = loader.load_instructions("app")
    assert content_app is not None
    assert "name: app" in content_app

    # Test loading marketing skill from plugins/marketing/skills
    content_boc_phot = loader.load_instructions("boc-phot-storytelling")
    assert content_boc_phot is not None
    assert "name: boc-phot-storytelling" in content_boc_phot

    # Test loading second-brain skill from plugins/second-brain/skills
    content_query_wiki = loader.load_instructions("query-wiki")
    assert content_query_wiki is not None
    assert "name: query-wiki" in content_query_wiki

    # Test path resolution
    app_path = loader.find_skill_path("app")
    assert app_path is not None and os.path.isabs(app_path)
    assert app_path.replace("\\", "/").endswith("plugins/code/skills/app/SKILL.md")
    mkt_path = loader.find_skill_path("boc-phot-storytelling")
    assert mkt_path is not None and os.path.isabs(mkt_path)
    assert mkt_path.replace("\\", "/").endswith(
        "plugins/marketing/skills/boc-phot-storytelling/SKILL.md")
    sb_path = loader.find_skill_path("query-wiki")
    assert sb_path is not None and os.path.isabs(sb_path)
    assert sb_path.replace("\\", "/").endswith(
        "plugins/second-brain/skills/query-wiki/SKILL.md")

def test_orchestrator_auto_routing():
    orchestrator = ChiefOrchestrator()
    # Test auto branch
    context, _ = orchestrator.process_task("viết bài bóc phốt", branch=None)
    assert context.branch == "marketing"
    assert context.active_skill == "boc-phot-storytelling"
    
    context2, _ = orchestrator.process_task("làm app cho điện thoại", branch="auto")
    assert context2.branch == "app"
    assert context2.active_skill == "app"
