"""Tests for SkillRouter Scoring Engine, Tie-Breaking, Alias Redirection, and 15 Practical Cases.

Dune Invariant & Zero-Regression Verification:
1. 15/15 practical routing cases must pass 100%.
2. Scoring engine: Score = (max_len * 10) + count; tie-breaks resolved by total match count.
3. Alias redirection: verification-before-completion -> anti-hallucination-guard.
4. Keyword isolation: core web vitals -> webperf; ponytail-review vs karpathy-coder.
5. STAGE_GATES CLI integration in app_workflow.py.
"""
import pytest
from pathlib import Path

from harness.skills.router import SkillRouter, SkillLoader
from harness.app_workflow import STAGE_GATES, AppWorkflowStore


# 15 Ca Thực Tế Kiểm Thử Định Tuyến
PRACTICAL_ROUTING_CASES = [
    ("hãy phỏng vấn ý định của tôi trước khi làm", "interview-me"),
    ("viết code tra cứu official docs tài liệu chính thống", "source-driven-development"),
    ("hãy phản biện đối kháng hoài nghi kỹ thuật fresh-context review", "doubt-driven-development"),
    ("audit core web vitals lcp inp bundle size web performance", "webperf"),
    ("kiểm tra giao diện verify-ui devtools", "verify-ui"),
    ("đừng viết code phức tạp, ponytail review cắt bớt code", "ponytail-review"),
    ("sửa lỗi systematic debugging tìm root cause", "systematic-debugging"),
    ("chẩn đoán forensics khảo cổ trace git", "forensics"),
    ("giải thích lý do why khảo cổ kiến trúc", "why"),
    ("rào chắn chống ảo giác anti-hallucination", "anti-hallucination-guard"),
    ("chạy test trước khi hoàn tất verification before completion", "anti-hallucination-guard"),
    ("tối ưu hiệu năng hillclimb thực nghiệm", "hillclimb"),
    ("so sánh đa giải pháp arena", "arena"),
    ("kiểm tra bảo mật security review taint graph", "security-review"),
    ("thẩm định dịch ngược reverse-lab chống crack", "reverse-lab"),
]


@pytest.mark.parametrize("prompt,expected_skill", PRACTICAL_ROUTING_CASES)
def test_all_15_practical_routing_cases(prompt, expected_skill):
    router = SkillRouter()
    skill, branch = router.route(prompt)
    assert skill == expected_skill, f"Failed for prompt: {prompt}"
    assert branch == "app"


def test_scoring_engine_tie_break_by_match_count():
    router = SkillRouter()
    # Prompt with multiple keywords of systematic-debugging
    # "systematic debugging" (20 chars) + "root cause" (10 chars)
    skill, branch = router.route("systematic debugging và tìm root cause lỗi")
    assert skill == "systematic-debugging"
    assert branch == "app"


def test_alias_redirection_verification_before_completion():
    router = SkillRouter()
    assert router.resolve_alias("verification-before-completion") == "anti-hallucination-guard"
    
    loader = SkillLoader()
    assert loader.resolve_alias("verification-before-completion") == "anti-hallucination-guard"
    
    instructions = loader.load_instructions("verification-before-completion")
    assert instructions is not None
    assert "anti-hallucination-guard" in instructions or "The Iron Law" in instructions


def test_core_web_vitals_exclusive_to_webperf():
    router = SkillRouter()
    skill, branch = router.route("tối ưu core web vitals cho web")
    assert skill == "webperf"
    assert branch == "app"


def test_karpathy_coder_vs_ponytail_review_separation():
    router = SkillRouter()
    # karpathy-coder keywords
    skill_k, branch_k = router.route("áp dụng karpathy coder surgical changes và simplicity first")
    assert skill_k == "karpathy-coder"
    assert branch_k == "app"

    # ponytail-review keywords
    skill_p, branch_p = router.route("chạy ponytail review để rà soát phình mã và chống over-engineering")
    assert skill_p == "ponytail-review"
    assert branch_p == "app"


def test_systematic_debugging_root_cause_keyword():
    router = SkillRouter()
    skill, branch = router.route("điều tra root cause analysis cho test failure")
    assert skill == "systematic-debugging"
    assert branch == "app"


def test_stage_gates_app_workflow_integration():
    assert "INTAKE" in STAGE_GATES
    assert "interview-me" in STAGE_GATES["INTAKE"]["recommended_skills"]
    assert "IMPLEMENTATION" in STAGE_GATES
    assert "source-driven-development" in STAGE_GATES["IMPLEMENTATION"]["recommended_skills"]
    assert "doubt-driven-development" in STAGE_GATES["IMPLEMENTATION"]["recommended_skills"]
    assert "CRITIQUE" in STAGE_GATES
    assert "ponytail-review" in STAGE_GATES["CRITIQUE"]["recommended_skills"]
    assert "AUDIT" in STAGE_GATES
    assert "anti-hallucination-guard" in STAGE_GATES["AUDIT"]["recommended_skills"]
    assert "webperf" in STAGE_GATES["AUDIT"]["recommended_skills"]

    # Test AppWorkflowStore methods
    gate = AppWorkflowStore.get_stage_gate("AUDIT")
    assert "webperf" in gate.get("recommended_skills", [])

    intake_val = AppWorkflowStore.validate_stage_skills("INTAKE", {"description": "Chưa có spec cụ thể"})
    assert "interview-me" in intake_val["recommended_skills"]

    build_val = AppWorkflowStore.validate_stage_skills("IMPLEMENTATION", {"description": "Refactor core engine runtime"})
    assert "doubt-driven-development" in build_val["recommended_skills"]

    audit_val = AppWorkflowStore.validate_stage_skills("AUDIT", {"description": "Review web frontend template"})
    assert "webperf" in audit_val["recommended_skills"]
