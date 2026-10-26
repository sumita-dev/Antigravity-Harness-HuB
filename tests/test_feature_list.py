"""Unit & Integration Tests for Feature List Primitive & WIP=1 Enforcement (Harness 2.0).

Kiểm thử 100% các tiêu chí AC-FL-01..05 và rào chắn chống Fake Passing.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from harness.feature_list import (
    CompletionEvidence,
    FakePassingError,
    FeatureItem,
    FeatureList,
    FeatureListValidationError,
    VCRMetrics,
    VerificationFailedError,
    WIPViolationError,
    _compute_manifest_hash,
)
from harness.validators.feature_list_validator import FeatureListValidator


def test_ac_fl_01_triple_structure_validation(tmp_path):
    """AC-FL-01: Kiểm tra cấu trúc Triple Structure, bắt buộc có behavior_description, verification_command, state."""
    # Thiếu behavior_description
    bad_item = FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="too short",  # < 10 chars
        verification_command="pytest",
        state="not_started",
    )
    fl = FeatureList("proj-1", [bad_item])
    with pytest.raises(FeatureListValidationError, match="behavior_description must be at least 10 characters"):
        fl.validate()

    # Thiếu verification_command
    bad_item2 = FeatureItem(
        id="FEAT-002",
        category="core",
        behavior_description="Valid long behavior description",
        verification_command=" ",
        state="not_started",
    )
    fl2 = FeatureList("proj-1", [bad_item2])
    with pytest.raises(FeatureListValidationError, match="verification_command must be at least 3 characters"):
        fl2.validate()

    # Sai category
    bad_item3 = FeatureItem(
        id="FEAT-003",
        category="invalid_category",
        behavior_description="Valid long behavior description",
        verification_command="pytest tests/",
        state="not_started",
    )
    fl3 = FeatureList("proj-1", [bad_item3])
    with pytest.raises(FeatureListValidationError, match="invalid category"):
        fl3.validate()

    # Hợp lệ
    valid_item = FeatureItem(
        id="FEAT-004",
        category="core",
        behavior_description="Valid long behavior description for login",
        verification_command="pytest tests/test_login.py",
        state="not_started",
    )
    fl4 = FeatureList("proj-1", [valid_item])
    errors = fl4.validate()
    assert len(errors) == 0


def test_ac_fl_02_wip_1_hard_constraint():
    """AC-FL-02: Bắt buộc WIP=1, từ chối kích hoạt tính năng thứ 2 nếu đã có 1 tính năng active."""
    f1 = FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="Implement user registration",
        verification_command="pytest tests/test_reg.py",
        state="not_started",
    )
    f2 = FeatureItem(
        id="FEAT-002",
        category="core",
        behavior_description="Implement password reset flow",
        verification_command="pytest tests/test_reset.py",
        state="not_started",
    )
    fl = FeatureList("proj-1", [f1, f2])

    # Kích hoạt f1 -> thành công
    fl.start_feature("FEAT-001")
    assert f1.state == "active"
    assert fl.vcr_metrics.active == 1

    # Cố tình kích hoạt f2 khi f1 đang active -> ném WIPViolationError
    with pytest.raises(WIPViolationError, match="WIP=1 Invariant violated|WIP=1 invariant"):
        fl.start_feature("FEAT-002")

    assert f2.state == "not_started"
    assert fl.vcr_metrics.active == 1

    # Chuyển f1 sang blocked -> kích hoạt f2 thành công
    fl.block_feature("FEAT-001", reason="Waiting for API spec from backend team")
    assert f1.state == "blocked"
    assert fl.vcr_metrics.blocked == 1
    assert fl.vcr_metrics.active == 0

    fl.start_feature("FEAT-002")
    assert f2.state == "active"
    assert fl.vcr_metrics.active == 1

    # Cố tình add một feature đã ở trạng thái active khi list đã có active
    f3 = FeatureItem(
        id="FEAT-003",
        category="core",
        behavior_description="Implement user logout endpoint",
        verification_command="pytest tests/test_logout.py",
        state="active",
    )
    with pytest.raises(WIPViolationError):
        fl.add_feature(f3)


def test_ac_fl_03_anti_fake_passing_and_verification(tmp_path):
    """AC-FL-03: Triệt tiêu Fake Passing. Chỉ cấp nhãn 'passing' khi verification_command chạy thật exit 0."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "test_script.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")

    f1 = FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="Verify calculation engine logic",
        verification_command=f'"{sys.executable}" test_script.py',
        state="active",
    )
    fl = FeatureList("calc-proj", [f1], file_path=project / "feature_list.json")
    fl.save()

    # 1. Fake passing bằng cách gán state='passing' mà không có evidence -> validate() quăng FakePassingError
    f1.state = "passing"
    with pytest.raises(FakePassingError):
        fl.validate()

    # 2. Reset về active và gọi verify_feature thật
    f1.state = "active"
    verified = fl.verify_feature("FEAT-001", actor="QA_Checker", project_root=project)
    assert verified.state == "passing"
    assert verified.completion_evidence is not None
    assert verified.completion_evidence.exit_code == 0
    assert verified.completion_evidence.verified_by == "QA_Checker"
    assert len(verified.completion_evidence.output_sha256) == 64
    assert len(verified.completion_evidence.manifest_sha256) == 64

    # Validate lại thành công
    fl.save()
    assert len(fl.validate(check_manifest_against_path=project)) == 0

    # 3. Lệnh thất bại (exit code != 0) -> không được chuyển passing, quăng VerificationFailedError
    (project / "failing_script.py").write_text("import sys; sys.exit(2)\n", encoding="utf-8")
    f2 = FeatureItem(
        id="FEAT-002",
        category="core",
        behavior_description="Failing test verification check",
        verification_command=f'"{sys.executable}" failing_script.py',
        state="active",
    )
    fl.add_feature(f2)
    # Vì f1 đã passing, f2 có thể chuyển active
    fl.start_feature("FEAT-002")

    with pytest.raises(VerificationFailedError, match="exit code 2"):
        fl.verify_feature("FEAT-002", project_root=project)

    assert f2.state == "active"
    assert f2.completion_evidence is None

    # 4. Lệnh tầm thường (Risk R5: echo ok, exit 0) bị từ chối
    f3 = FeatureItem(
        id="FEAT-003",
        category="core",
        behavior_description="Trivial mock command feature",
        verification_command="echo ok",
        state="not_started",
    )
    fl.add_feature(f3)
    fl.block_feature("FEAT-002", reason="Blocked pending bugfix for failing script")
    fl.start_feature("FEAT-003")
    with pytest.raises(VerificationFailedError, match="Rejected trivial verification_command"):
        fl.verify_feature("FEAT-003", project_root=project)


def test_ac_fl_04_vcr_metric_real_time_computation():
    """AC-FL-04: Thước đo Verified Completion Rate (VCR) được cập nhật liên tục."""
    fl = FeatureList("vcr-test")
    # Ban đầu rỗng -> VCR = 1.0
    assert fl.vcr_metrics.vcr_score == 1.0

    # Thêm 4 features (đều not_started) -> mẫu số = 0 -> VCR = 1.0
    for i in range(1, 5):
        fl.add_feature(FeatureItem(
            id=f"FEAT-00{i}",
            category="core",
            behavior_description=f"Feature number {i} behavior test",
            verification_command="pytest",
        ))
    assert fl.vcr_metrics.total_features == 4
    assert fl.vcr_metrics.not_started == 4
    assert fl.vcr_metrics.vcr_score == 1.0

    # Kích hoạt FEAT-001 -> active=1, not_started=3 -> VCR = 0 / (0 + 1 + 0) = 0.0
    fl.start_feature("FEAT-001")
    assert fl.vcr_metrics.active == 1
    assert fl.vcr_metrics.vcr_score == 0.0

    # Mock hoàn thành FEAT-001 sang passing kèm evidence giả lập hợp lệ
    fl.get_feature("FEAT-001").state = "passing"
    fl.get_feature("FEAT-001").completion_evidence = CompletionEvidence(
        executed_command="pytest",
        exit_code=0,
        output_sha256="b" * 64,
        manifest_sha256="c" * 64,
        verified_at="2026-10-26T00:00:00Z",
        verified_by="QA",
    )
    fl.recalculate_vcr()
    # 1 passing, 0 active, 0 blocked -> VCR = 1 / 1 = 1.0
    assert fl.vcr_metrics.passing == 1
    assert fl.vcr_metrics.vcr_score == 1.0

    # Kích hoạt FEAT-002 -> active=1 -> VCR = 1 / (1 + 1) = 0.5
    fl.start_feature("FEAT-002")
    assert fl.vcr_metrics.vcr_score == 0.5

    # Block FEAT-002 -> blocked=1 -> VCR = 1 / (1 + 0 + 1) = 0.5
    fl.block_feature("FEAT-002", reason="Waiting for database schema migration")
    assert fl.vcr_metrics.vcr_score == 0.5


def test_ac_fl_05_blocked_state_handling():
    """AC-FL-05: Khi chuyển sang 'blocked', bắt buộc có blocked_reason tối thiểu 10 ký tự."""
    f = FeatureItem(
        id="FEAT-001",
        category="sec",
        behavior_description="Audit authentication tokens security",
        verification_command="python -m pytest",
        state="not_started",
    )
    fl = FeatureList("proj-sec", [f])
    fl.start_feature("FEAT-001")

    # Lý do quá ngắn (< 10 ký tự) -> ném ValueError
    with pytest.raises(ValueError, match="at least 10 characters"):
        fl.block_feature("FEAT-001", reason="too short")

    # Lý do hợp lệ
    fl.block_feature("FEAT-001", reason="Blocked waiting for HSM hardware key credentials")
    assert f.state == "blocked"
    assert f.blocked_reason == "Blocked waiting for HSM hardware key credentials"

    # Khi unblock / start lại -> blocked_reason được dọn sạch
    fl.unblock_feature("FEAT-001")
    assert f.state == "active"
    assert f.blocked_reason is None


def test_feature_list_json_schema_roundtrip(tmp_path):
    """Kiểm tra xuất và nạp JSON Schema v2.0.0 bảo toàn toàn bộ dữ liệu và định dạng."""
    project = tmp_path / "proj"
    project.mkdir()
    fl_file = project / "feature_list.json"

    f1 = FeatureItem(
        id="FEAT-001",
        category="perf",
        behavior_description="Optimize query response time under 100ms",
        verification_command="pytest tests/perf",
        state="passing",
        completion_evidence=CompletionEvidence(
            executed_command="pytest tests/perf",
            exit_code=0,
            output_sha256="1" * 64,
            manifest_sha256="2" * 64,
            verified_at="2026-10-26T12:00:00Z",
            verified_by="QA_Auditor",
        ),
    )
    fl = FeatureList(
        project_id="test-roundtrip",
        features=[f1],
        file_path=fl_file,
    )
    fl.save()

    # Nạp lại qua FeatureListValidator
    loaded = FeatureListValidator.validate_file(fl_file, check_manifest=False)
    assert loaded.schema_version == "2.0.0"
    assert loaded.project_id == "test-roundtrip"
    assert len(loaded.features) == 1
    assert loaded.features[0].id == "FEAT-001"
    assert loaded.features[0].category == "perf"
    assert loaded.features[0].completion_evidence.exit_code == 0
    assert loaded.vcr_metrics.vcr_score == 1.0
