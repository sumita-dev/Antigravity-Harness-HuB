"""Contract checks for dispatch metadata and source/runtime separation."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def read(path):
    return (REPO / path).read_text(encoding="utf-8")


def test_registry_has_all_native_roles_and_two_reject_threshold():
    registry = read("agents/registry.md")
    for name in ("Architect", "Design_Reviewer", "Builder", "QA_Auditor",
                 "Web_Researcher", "Creator", "Compliance_Critic"):
        assert f"`{name}`" in registry
    assert "REJECT thứ hai" in registry
    assert "REJECT (> 2" not in registry
    assert "stage" in registry and "next_agent" in registry
    assert "sandbox" in registry


def test_config_preserves_models_and_has_complete_role_metadata():
    config = json.loads(read("configs/harness_config.json"))
    assert config["models"] == {"pro": "Gemini 3.1 Pro", "flash": "Gemini 3.8 Flash"}
    assert config["limits"]["max_critique_rounds"] == 2
    for role in ("architect", "design_reviewer", "builder", "qa_auditor", "web_researcher", "creator", "compliance_critic"):
        assert config["roles"][role] in config["models"]


def test_generic_design_rubric_does_not_impose_task_board_stack():
    generic = read("rubrics/design_review_rubric.md")
    assert "backend" in generic and "CLI" in generic
    for requirement in ("10,000 IDs", "layout 3 cột", "DOM-Free Core", "ERR_TITLE_REQUIRED"):
        assert requirement not in generic
    assert "task-board-design-profile.md" in generic
    assert (REPO / "rubrics/task-board-design-profile.md").is_file()


def test_marketing_contract_covers_analysis_and_hash_bound_artifacts():
    guide = read("docs/marketing-workflow-guide.md")
    for field in ("research-only", "source_accuracy", "policy", "integrity", "task_quality",
                  "claim_checks", "baseline_sha256", "artifacts_sha256", "UNKNOWN"):
        assert field in guide
    rubric = read("rubrics/content_compliance_rubric.md")
    assert "ROAS" in rubric and "tiền tệ" in rubric
    assert "Hook/CTA" in rubric and "research-only" in rubric


def test_native_readiness_does_not_claim_unobserved_execution():
    doc = read("docs/native-readiness.md")
    for state in ("OBSERVED", "DECLARED", "UNAVAILABLE", "NOT_VERIFIED"):
        assert state in doc
    assert "Antigravity E2E: NOT_VERIFIED" in doc


def test_entire_brain_runtime_is_ignored_and_policy_files_match():
    assert ".brain/" in read(".gitignore").splitlines()
    assert (REPO / "AGENTS.md").read_bytes() == (REPO / "GEMINI.md").read_bytes()


def test_doc_scanner_excludes_generated_brain_but_scans_nested_source(tmp_path, monkeypatch):
    import test_repo_integrity as integrity
    source = tmp_path / "harness" / "nested" / "unsafe.md"
    runtime = tmp_path / ".brain" / "fixtures" / "unsafe.md"
    for path in (source, runtime):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(integrity, "REPO", tmp_path)
    assert list(integrity._doc_files()) == [source]
