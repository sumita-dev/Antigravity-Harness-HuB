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

    skill, branch = router.route("hãy thiết lập second brain mới")
    assert skill == "setup-second-brain"
    assert branch == "app"

    # Test priority (longest match)
    # If a text has multiple keywords, it should pick the skill with longest matched keyword
    # Let's say text: "viết bài bóc phốt và làm offer"
    # "viết bài" -> fallback marketing, "bóc phốt" -> 8 chars, "làm offer" -> 9 chars
    skill, branch = router.route("bóc phốt offer builder")
    assert skill == "alex-hormozi-offer-builder" # "offer builder" is 13 chars, "bóc phốt" is 8 chars


@pytest.mark.parametrize(("user_text", "expected"), [
    ("dọn trình duyệt bị treo và tiến trình mồ côi", "browser-hygiene"),
    ("chăm sóc máy tính Windows, dọn cache", "cham-soc-may-tinh"),
    ("chuyển file docx thành markdown", "doc-to-markdown"),
    ("tạo video bằng Google Flow Veo", "flowkit"),
    ("audit paid media và hiệu quả chiến dịch", "paid-media-auditor"),
    ("viết integration test với Testcontainers PostgreSQL", "testcontainers"),
    ("gợi ý từ khóa YouTube autocomplete", "youtube-suggest"),
])
def test_routes_previously_unmapped_skills(user_text, expected):
    skill, _branch = SkillRouter().route(user_text)
    assert skill == expected


def test_specific_marketing_route_beats_generic_caption_route():
    skill, branch = SkillRouter().route("audit paid media và tối ưu quảng cáo facebook")
    assert (skill, branch) == ("paid-media-auditor", "marketing")

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


def test_multiline_dependencies_and_missing_dependency_are_explicit(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'SKILL.md').write_text('---\ndependencies:\n  - missing\n---\nRoot')
    loader = SkillLoader(search_dirs=[tmp_path])
    assert loader.get_skill_dependencies('root') == ['missing']
    with pytest.raises(ValueError, match='missing'):
        loader.load_instructions('root')


def test_composition_applies_dimensions_deduplicates_and_enforces_budget(tmp_path):
    import json
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'skill_composition': {'max_skills': 2, 'max_chars': 1000,
        'stage': {'IMPLEMENTATION': ['tdd']}, 'role': {'builder': ['tdd']},
        'stack': {'python': ['python']}, 'risk': {'high': ['security']}}}))
    for name in ('tdd', 'python', 'security'):
        (tmp_path / name).mkdir()
        (tmp_path / name / 'SKILL.md').write_text(name)
    router = SkillRouter(str(config))
    loader = SkillLoader(search_dirs=[tmp_path])
    with pytest.raises(ValueError, match='budget'):
        router.compose('IMPLEMENTATION', 'builder', 'python', 'high', loader=loader)
    result = router.compose('IMPLEMENTATION', 'builder', 'python', 'low', loader=loader)
    assert result['skills'] == ['tdd', 'python']
    assert 'tdd' in result['instructions']
    with pytest.raises(ValueError, match='budget'):
        router.compose('IMPLEMENTATION', 'builder', 'python', 'low', loader=loader, max_chars=2)


@pytest.mark.parametrize('field,expected', [('', []), ('dependencies: [base]\n', ['base']), ('dependencies:\n  - base\n', ['base'])])
def test_dependency_parser_ignores_unrelated_legacy_description_yaml(tmp_path, field, expected):
    skill = tmp_path / 'legacy'
    skill.mkdir()
    # Existing disk-cleanup descriptions contain unquoted colon-space prose.
    (skill / 'SKILL.md').write_text('---\nname: legacy\ndescription: cache cleanup: pip, npm\n' + field + '---\nBody', encoding='utf-8')
    assert SkillLoader(search_dirs=[tmp_path]).get_skill_dependencies('legacy') == expected


def test_invalid_dependency_yaml_has_useful_error(tmp_path):
    skill = tmp_path / 'broken'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\ndependencies: [unterminated\n---\nBody')
    with pytest.raises(ValueError, match='Invalid dependencies.*broken'):
        SkillLoader(search_dirs=[tmp_path]).get_skill_dependencies('broken')
