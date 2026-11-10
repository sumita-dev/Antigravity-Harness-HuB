"""Comprehensive tests for Harness Upgrade Pha 1, Pha 2, and Pha 3.

Covers:
1. Pha 1: Hallucination detector evasions (speculation, sycophancy, 3rd-party API claims).
2. Pha 2: AppWorkflowStore test manifest, test tampering guard, AC-to-Assertion check, mutation testing gate.
3. Pha 3: Semantic judge evaluation and deterministic fallback handling.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError
from harness.validators.hallucination_detector import (
    detect_speculative_language,
    detect_sycophancy,
    verify_api_and_investigation_claims,
)
from harness.validators.semantic_judge import evaluate_semantic_grounding


# =============================================================================
# Pha 1: Hallucination Detector Evasion Patterns
# =============================================================================


def test_pha1_speculative_vietnamese_evasions():
    samples = [
        "Nhiều khả năng nguyên nhân xuất phát từ caching.",
        "Khả năng rất cao là service worker đã hoạt động.",
        "Em tin tưởng tuyệt đối vào bản vá này.",
        "Theo kinh nghiệm của em thì hàm này chuẩn rồi.",
        "Giao diện trông có vẻ ổn định.",
        "Đoạn code này không thể có lỗi được.",
        "Em nghĩ là được rồi, không cần test thêm.",
    ]
    for sample in samples:
        hits = detect_speculative_language(sample)
        assert len(hits) > 0, f"Expected speculation pattern match in: {sample}"


def test_pha1_speculative_english_evasions():
    samples = [
        "There is a high probability that the migration fixed the issue.",
        "I am confident that this patch resolves all edge cases.",
        "The current implementation looks solid for production.",
    ]
    for sample in samples:
        hits = detect_speculative_language(sample)
        assert len(hits) > 0, f"Expected speculation pattern match in: {sample}"


def test_pha1_sycophancy_vietnamese_evasions():
    samples = [
        "Phân tích của Sếp quá thấu đáo, chuẩn không cần chỉnh.",
        "Góc nhìn của anh thật sâu sắc, nhìn thấu toàn bộ kiến trúc.",
        "Giải pháp này quá đỉnh, đúng tầm chuyên gia.",
        "Nhận định của Sếp chuẩn xác 100%.",
    ]
    for sample in samples:
        hits = detect_sycophancy(sample)
        assert len(hits) > 0, f"Expected sycophancy pattern match in: {sample}"


def test_pha1_third_party_api_claim_patterns():
    samples = [
        "Stripe webhook bị failed và trả về status 400 do secret key.",
        "Firebase authentication gặp lỗi status 403 forbidden.",
        "Supabase payment endpoint error khi tạo customer.",
        "AWS oauth request bị chặn với error code 401.",
        "ZaloPay payment call failed do timeout.",
        "PayOS status 500 internal server error khi xác thực.",
    ]
    for sample in samples:
        api_res = verify_api_and_investigation_claims(sample, execution_logs=None)
        assert api_res["valid"] is False, f"Expected API claim to require raw HTTP logs: {sample}"
        assert len(api_res["unverified_api_claims"]) > 0

    # With valid raw HTTP log, it should pass
    valid_logs = [{"status_code": 400, "raw_response": "HTTP 400 Bad Request"}]
    api_res = verify_api_and_investigation_claims("Stripe webhook bị failed với status 400", execution_logs=valid_logs)
    assert api_res["valid"] is True


# =============================================================================
# Pha 3: Semantic Judge Evaluator
# =============================================================================


def test_pha3_semantic_judge_clean_text():
    clean_text = "Đã triển khai hàm calculate_discount theo đặc tả và hoàn tất kiểm thử."
    res = evaluate_semantic_grounding(clean_text, execution_logs=[{"exit_code": 0}])
    assert res["is_grounded"] is True
    assert res["verdict"] == "APPROVE"
    assert res["score"] >= 0.8
    assert len(res["violations"]) == 0


def test_pha3_semantic_judge_detects_speculation():
    text = "Nhiều khả năng chức năng mới trông có vẻ ổn định."
    res = evaluate_semantic_grounding(text)
    assert res["is_grounded"] is False
    assert res["verdict"] == "REJECT"
    assert len(res["speculative_phrases"]) >= 1


def test_pha3_semantic_judge_detects_sycophancy():
    text = "Ý kiến của Sếp quá thấu đáo, nhìn thấu toàn bộ vấn đề."
    res = evaluate_semantic_grounding(text)
    assert res["is_grounded"] is False
    assert res["verdict"] == "REJECT"
    assert len(res["sycophancy_phrases"]) >= 1


def test_pha3_semantic_judge_fallback_handling():
    # Empty string fallback
    res_empty = evaluate_semantic_grounding("")
    assert res_empty["is_grounded"] is True
    assert res_empty["verdict"] == "APPROVE"
    assert res_empty["score"] == 1.0

    # None / non-string input fallback
    res_none = evaluate_semantic_grounding(None)  # type: ignore
    assert res_none["is_grounded"] is True
    assert res_none["verdict"] == "APPROVE"


# =============================================================================
# Pha 2: AppWorkflowStore Upgrades
# =============================================================================


def _setup_workflow_project(tmp_path: Path, weak_test: bool = False):
    project = tmp_path / "project"
    tests_dir = project / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    src_file = project / "fee_service.py"
    src_file.write_text(
        "def calculate_fee(amount: int) -> int:\n    if amount > 100:\n        return amount + 10\n    return amount + 5\n",
        encoding="utf-8",
    )

    test_file = tests_dir / "test_fee.py"
    if weak_test:
        test_file.write_text(
            "from fee_service import calculate_fee\n\ndef test_fee():\n    calculate_fee(200)\n    assert True\n",
            encoding="utf-8",
        )
    else:
        test_file.write_text(
            "from fee_service import calculate_fee\n\ndef test_fee():\n    assert calculate_fee(200) == 210\n    assert calculate_fee(101) == 111\n    assert calculate_fee(100) == 105\n    assert calculate_fee(50) == 55\n",
            encoding="utf-8",
        )

    brain_dir = tmp_path / "brain"
    store = AppWorkflowStore(brain_dir)
    store.create("task-pha2", "Pha 2 upgrade test task", project)

    spec = {
        "scope": "Fee service calculation",
        "design": "Pure calculate_fee function",
        "contracts": "calculate_fee(int) -> int",
        "acceptance_criteria": [{"id": "AC1", "description": "Unit test calculate_fee", "ui": False}],
        "risks": "None",
        "verification_commands": [
            {
                "id": "CMD_PYTEST",
                "argv": [sys.executable, "-m", "pytest", "-q"],
                "cwd": ".",
                "ac_ids": ["AC1"],
            }
        ],
        "evidence_root": str(tmp_path),
    }

    return store, project, spec, src_file, test_file


def test_pha2_test_manifest_sha256_persistence(tmp_path: Path):
    store, project, spec, src_file, test_file = _setup_workflow_project(tmp_path)
    s = store.submit_spec("task-pha2", spec, "architect-1")

    # Verify test_manifest_sha256 is calculated and persisted
    assert "test_manifest_sha256" in s
    assert isinstance(s["test_manifest_sha256"], str)
    assert len(s["test_manifest_sha256"]) == 64
    assert "tests/test_fee.py" in s.get("test_manifest", {})


def test_pha2_tampered_test_detection(tmp_path: Path):
    store, project, spec, src_file, test_file = _setup_workflow_project(tmp_path)
    s = store.submit_spec("task-pha2", spec, "architect-1")
    store.review_design("task-pha2", "APPROVE", "reviewer-1", s["spec_sha256"], "Design approved.")
    store.sign_off("task-pha2", s["spec_sha256"], "Duyệt")

    # Maker tampers with the approved acceptance test
    test_file.write_text("def test_fee():\n    assert True\n", encoding="utf-8")

    with pytest.raises(WorkflowError, match="Unauthorized test tampering detected"):
        store.submit_implementation("task-pha2", "builder-1", "Đã sửa file test và code.")


def test_pha2_critique_report_ac_to_assertion_mapping_enforcement(tmp_path: Path):
    store, project, spec, src_file, test_file = _setup_workflow_project(tmp_path)
    s = store.submit_spec("task-pha2", spec, "architect-1")
    store.review_design("task-pha2", "APPROVE", "reviewer-1", s["spec_sha256"], "Design approved.")
    store.sign_off("task-pha2", s["spec_sha256"], "Duyệt")

    # Builder modifies src_file
    src_file.write_text(
        "def calculate_fee(amount: int) -> int:\n    # updated\n    if amount > 100:\n        return amount + 10\n    return amount + 5\n",
        encoding="utf-8",
    )
    state = store.submit_implementation("task-pha2", "builder-1", "Hoàn thành fee_service.py.")

    # 1. Critique without AC-to-Assertion mapping should fail
    with pytest.raises(WorkflowError, match="Critique report must contain AC-to-Assertion mapping"):
        store.review_code(
            "task-pha2",
            "APPROVE",
            "critic-1",
            state["spec_sha256"],
            state["manifest_sha256"],
            "Đã kiểm tra code không có lỗi.",
        )

    # 2. Critique with explicit AC-to-Assertion mapping should succeed
    valid_review = store.review_code(
        "task-pha2",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "Đã rà soát kỹ lưỡng. AC1 được map đầy đủ tới assertion trong test_fee.",
    )
    assert valid_review["stage"] == "AUDIT"


def test_pha2_mutation_testing_gate_in_audit(tmp_path: Path):
    store, project, spec, src_file, test_file = _setup_workflow_project(tmp_path)
    s = store.submit_spec("task-pha2", spec, "architect-1")
    store.review_design("task-pha2", "APPROVE", "reviewer-1", s["spec_sha256"], "Design approved.")
    store.sign_off("task-pha2", s["spec_sha256"], "Duyệt")

    # Builder modifies source file during implementation
    src_file.write_text(
        "def calculate_fee(amount: int) -> int:\n    # builder implementation\n    if amount > 100:\n        return amount + 10\n    return amount + 5\n",
        encoding="utf-8",
    )
    state = store.submit_implementation("task-pha2", "builder-1", "Đã viết code fee_service.py.")
    state = store.review_code(
        "task-pha2",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "AC1 mapped to test_fee assertion.",
    )

    # QA executes test command
    exec_res = store.execute("task-pha2", "qa-1", "CMD_PYTEST")
    receipt_id = exec_res["execution_receipt"]["receipt_id"]

    ev_file = tmp_path / "ac1.log"
    ev_file.write_text("AC1 verified", encoding="utf-8")

    # Audit APPROVE triggers mutation testing: strict test_fee kills all mutants
    approved_state = store.audit(
        "task-pha2",
        "APPROVE",
        "qa-1",
        {
            "spec_sha256": state["spec_sha256"],
            "manifest_sha256": state["manifest_sha256"],
            "report": "QA audit passed.",
            "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id, "actor": "qa-1"}],
            "preview": {"checks": [{"id": "AC1", "status": "PASS", "evidence": str(ev_file)}]},
        },
    )
    assert approved_state["stage"] == "APPROVED"
    assert approved_state["overall_verdict"] == "APPROVE"


def test_pha2_mutation_testing_failure_on_weak_test(tmp_path: Path):
    store, project, spec, src_file, test_file = _setup_workflow_project(tmp_path, weak_test=True)

    s = store.submit_spec("task-pha2", spec, "architect-1")
    store.review_design("task-pha2", "APPROVE", "reviewer-1", s["spec_sha256"], "Design approved.")
    store.sign_off("task-pha2", s["spec_sha256"], "Duyệt")

    # Builder modifies source file
    src_file.write_text(
        "def calculate_fee(amount: int) -> int:\n    # builder modification\n    if amount > 100:\n        return amount + 10\n    return amount + 5\n",
        encoding="utf-8",
    )
    state = store.submit_implementation("task-pha2", "builder-1", "Đã viết fee_service.py.")
    state = store.review_code(
        "task-pha2",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "AC1 mapped to test_fee assertion.",
    )

    exec_res = store.execute("task-pha2", "qa-1", "CMD_PYTEST")
    receipt_id = exec_res["execution_receipt"]["receipt_id"]

    ev_file = tmp_path / "ac1.log"
    ev_file.write_text("AC1 verified", encoding="utf-8")

    # Mutation test will detect surviving mutants because test_fee asserts True!
    with pytest.raises(WorkflowError, match="Mutation testing failed"):
        store.audit(
            "task-pha2",
            "APPROVE",
            "qa-1",
            {
                "spec_sha256": state["spec_sha256"],
                "manifest_sha256": state["manifest_sha256"],
                "report": "QA audit passed.",
                "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id, "actor": "qa-1"}],
                "preview": {"checks": [{"id": "AC1", "status": "PASS", "evidence": str(ev_file)}]},
            },
        )


def test_pha2_mutation_bypass_hotfix_fast_track(tmp_path: Path):
    store, project, spec, src_file, test_file = _setup_workflow_project(tmp_path, weak_test=True)

    s = store.submit_spec("task-pha2", spec, "architect-1")
    store.review_design("task-pha2", "APPROVE", "reviewer-1", s["spec_sha256"], "Design approved.")
    store.sign_off("task-pha2", s["spec_sha256"], "Duyệt")

    src_file.write_text(
        "def calculate_fee(amount: int) -> int:\n    # builder hotfix\n    if amount > 100:\n        return amount + 10\n    return amount + 5\n",
        encoding="utf-8",
    )
    state = store.submit_implementation("task-pha2", "builder-1", "Đã viết fee_service.py.")
    state = store.review_code(
        "task-pha2",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "AC1 mapped to test_fee assertion.",
    )

    exec_res = store.execute("task-pha2", "qa-1", "CMD_PYTEST")
    receipt_id = exec_res["execution_receipt"]["receipt_id"]

    ev_file = tmp_path / "ac1.log"
    ev_file.write_text("AC1 verified", encoding="utf-8")

    # 1. skip_mutation_check without fast-track or hotfix should fail
    with pytest.raises(WorkflowError, match="skip_mutation_check is only allowed for hotfix or fast-track"):
        store.audit(
            "task-pha2",
            "APPROVE",
            "qa-1",
            {
                "spec_sha256": state["spec_sha256"],
                "manifest_sha256": state["manifest_sha256"],
                "report": "QA audit passed.",
                "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id, "actor": "qa-1"}],
                "preview": {"checks": [{"id": "AC1", "status": "PASS", "evidence": str(ev_file)}]},
                "skip_mutation_check": True,
            },
        )

    # 2. skip_mutation_check with hotfix flag should succeed
    bypassed_state = store.audit(
        "task-pha2",
        "APPROVE",
        "qa-1",
        {
            "spec_sha256": state["spec_sha256"],
            "manifest_sha256": state["manifest_sha256"],
            "report": "QA audit passed.",
            "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id, "actor": "qa-1"}],
            "preview": {"checks": [{"id": "AC1", "status": "PASS", "evidence": str(ev_file)}]},
            "skip_mutation_check": True,
            "hotfix": True,
        },
    )
    assert bypassed_state["stage"] == "APPROVED"
