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

    # Test priority (longest match)
    # If a text has multiple keywords, it should pick the skill with longest matched keyword
    # Let's say text: "viết bài bóc phốt và làm offer"
    # "viết bài" -> fallback marketing, "bóc phốt" -> 8 chars, "làm offer" -> 9 chars
    skill, branch = router.route("bóc phốt offer builder")
    assert skill == "alex-hormozi-offer-builder" # "offer builder" is 13 chars, "bóc phốt" is 8 chars

def test_skill_loader():
    loader = SkillLoader()
    # Assuming tests run from project root, and "app" skill exists
    # we can mock or just check if it returns None for non-existent
    content = loader.load_instructions("non_existent_skill_123")
    assert content is None

    # If the real file exists, let's test that it actually loads something
    content_app = loader.load_instructions("app")
    if os.path.exists("skills/app/SKILL.md"):
        assert content_app is not None

def test_orchestrator_auto_routing():
    orchestrator = ChiefOrchestrator()
    # Test auto branch
    context, _ = orchestrator.process_task("viết bài bóc phốt", branch=None)
    assert context.branch == "marketing"
    assert context.active_skill == "boc-phot-storytelling"
    
    context2, _ = orchestrator.process_task("làm app cho điện thoại", branch="auto")
    assert context2.branch == "app"
    assert context2.active_skill == "app"
