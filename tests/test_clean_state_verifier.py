"""Unit & Integration Tests for Clean State Protocol & Verifier (Harness 2.0).

Kiểm chứng toàn diện các tiêu chí AC-CS-01..06 và tích hợp AC-INT-01.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError
from harness.feature_list import (
    CompletionEvidence,
    FeatureItem,
    FeatureList,
    _compute_manifest_hash,
)
from harness.validators.clean_state_verifier import (
    AuditDimension,
    CleanStateVerifier,
    DimensionStatus,
)


def test_ac_cs_01_syntax_error_detection(tmp_path):
    """AC-CS-01: Chiều D1 phát hiện chính xác lỗi cú pháp Python kèm tên file và dòng."""
    project = tmp_path / "proj"
    project.mkdir()

    # File hợp lệ
    (project / "valid.py").write_text("def hello():\n    return 42\n", encoding="utf-8")

    verifier = CleanStateVerifier(project_root=project)
    res = verifier.check_d1_build_type()
    assert res.status == DimensionStatus.PASS
    assert res.details["compiled_files"] == 1

    # Thêm file có lỗi cú pháp
    broken_file = project / "broken.py"
    broken_file.write_text("def broken_syntax(\n    return 123\n", encoding="utf-8")

    res2 = verifier.check_d1_build_type()
    assert res2.status == DimensionStatus.FAIL
    assert len(res2.violations) == 1
    assert "broken.py" in res2.violations[0]
    assert "Syntax error" in res2.violations[0]


def test_ac_cs_02_test_suite_execution(tmp_path):
    """AC-CS-02: Chiều D2 tự động nhận diện và thực thi test hermetic, kiểm tra exit code."""
    project = tmp_path / "proj"
    project.mkdir()

    # Khi không có test suite
    verifier = CleanStateVerifier(project_root=project)
    res = verifier.check_d2_test_suite()
    assert res.status == DimensionStatus.SKIPPED

    # Test suite vượt qua (exit code == 0)
    passing_verifier = CleanStateVerifier(
        project_root=project,
        config={"test_command": f'"{sys.executable}" -c "import sys; sys.exit(0)"'},
    )
    res_pass = passing_verifier.check_d2_test_suite()
    assert res_pass.status == DimensionStatus.PASS

    # Test suite thất bại (exit code != 0)
    failing_verifier = CleanStateVerifier(
        project_root=project,
        config={"test_command": f'"{sys.executable}" -c "print(\'TEST FAILED\'); import sys; sys.exit(1)"'},
    )
    res_fail = failing_verifier.check_d2_test_suite()
    assert res_fail.status == DimensionStatus.FAIL
    assert "failed with exit code 1" in res_fail.violations[0]


def test_ac_cs_03_feature_state_sync(tmp_path):
    """AC-CS-03: Chiều D3 kiểm tra đồng bộ giữa feature_list.json và mã nguồn thực tế."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("print('v1')\n", encoding="utf-8")

    fl_path = project / "feature_list.json"

    # Case 1: Feature passing nhưng thiếu completion_evidence -> FAIL (Ghost Passing)
    ghost_feat = FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="Core login authentication",
        verification_command="python -c 'print(1)'",
        state="passing",
        completion_evidence=None,
    )
    fl1 = FeatureList("test-proj", [ghost_feat], file_path=fl_path)
    fl1.save()

    verifier = CleanStateVerifier(project_root=project, config={"feature_list_path": str(fl_path)})
    res = verifier.check_d3_feature_sync()
    assert res.status == DimensionStatus.FAIL
    assert any("Fake Passing rejected" in v or "completion_evidence is missing" in v for v in res.violations)

    # Case 2: Evidence có exit_code != 0 -> FAIL
    manifest_hash = _compute_manifest_hash(project)
    bad_ev = CompletionEvidence(
        executed_command="pytest",
        exit_code=1,
        output_sha256="a" * 64,
        manifest_sha256=manifest_hash,
        verified_at="2026-10-26T00:00:00Z",
        verified_by="QA",
    )
    fl2 = FeatureList("test-proj", [FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="Core login authentication",
        verification_command="python -c 'print(1)'",
        state="passing",
        completion_evidence=bad_ev,
    )], file_path=fl_path)
    fl2.save()

    res2 = verifier.check_d3_feature_sync()
    assert res2.status == DimensionStatus.FAIL

    # Case 3: Mã nguồn bị sửa đổi làm lệch manifest_sha256 -> STALE FAIL
    valid_ev = CompletionEvidence(
        executed_command="pytest",
        exit_code=0,
        output_sha256="a" * 64,
        manifest_sha256=manifest_hash,
        verified_at="2026-10-26T00:00:00Z",
        verified_by="QA",
    )
    fl3 = FeatureList("test-proj", [FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="Core login authentication",
        verification_command="python -c 'print(1)'",
        state="passing",
        completion_evidence=valid_ev,
    )], file_path=fl_path)
    fl3.save()

    # Trước khi sửa code -> PASS
    # (Lưu lại manifest sau khi lưu fl_path)
    fresh_manifest = _compute_manifest_hash(project)
    valid_ev.manifest_sha256 = fresh_manifest
    fl3.features[0].completion_evidence = valid_ev
    fl3.save()
    fresh_manifest2 = _compute_manifest_hash(project)
    fl3.features[0].completion_evidence.manifest_sha256 = fresh_manifest2
    fl3.save()

    res3 = verifier.check_d3_feature_sync()
    assert res3.status == DimensionStatus.PASS

    # Sửa code
    (project / "app.py").write_text("print('v2 modified')\n", encoding="utf-8")
    res_stale = verifier.check_d3_feature_sync()
    assert res_stale.status == DimensionStatus.FAIL
    assert any("STALE" in v for v in res_stale.violations)


def test_ac_cs_04_zero_debug_artifacts_and_residue(tmp_path):
    """AC-CS-04: Chiều D4 phát hiện cặn bã debug và tệp rác (.tmp, .bak, breakpoint, console.log)."""
    project = tmp_path / "proj"
    project.mkdir()

    # Clean state ban đầu
    (project / "main.py").write_text("def run():\n    print('Hello World')\n", encoding="utf-8")
    verifier = CleanStateVerifier(project_root=project)
    assert verifier.check_d4_zero_debug().status == DimensionStatus.PASS

    # Thêm print("DEBUG...")
    (project / "debug.py").write_text('print("DEBUG: entering function")\n', encoding="utf-8")
    res = verifier.check_d4_zero_debug()
    assert res.status == DimensionStatus.FAIL
    assert any("print_debug" in v for v in res.violations)

    # Bypass với # noqa: debug-artifact
    (project / "debug.py").write_text('print("DEBUG: allowed")  # noqa: debug-artifact\n', encoding="utf-8")
    assert verifier.check_d4_zero_debug().status == DimensionStatus.PASS

    # Thêm breakpoint()
    (project / "debug.py").write_text("breakpoint()\n", encoding="utf-8")
    assert verifier.check_d4_zero_debug().status == DimensionStatus.FAIL

    # Thêm console.log trong file JS
    (project / "debug.py").unlink()
    (project / "index.js").write_text("console.log('test')\n", encoding="utf-8")
    assert verifier.check_d4_zero_debug().status == DimensionStatus.FAIL

    # Thêm file rác .tmp
    (project / "index.js").unlink()
    (project / "data.tmp").write_text("garbage", encoding="utf-8")
    res_tmp = verifier.check_d4_zero_debug()
    assert res_tmp.status == DimensionStatus.FAIL
    assert any("Stray file detected" in v and "data.tmp" in v for v in res_tmp.violations)


def test_ac_cs_05_clean_boot_smoke_test(tmp_path):
    """AC-CS-05: Chiều D5 thực thi lệnh smoke boot trong timeout 5000ms."""
    project = tmp_path / "proj"
    project.mkdir()

    # Boot thành công
    verifier_pass = CleanStateVerifier(
        project_root=project,
        config={"boot_command": [sys.executable, "-c", "import sys; print('Ready'); sys.exit(0)"]},
    )
    res_pass = verifier_pass.check_d5_clean_startup()
    assert res_pass.status == DimensionStatus.PASS
    assert res_pass.duration_ms < 5000.0

    # Boot thất bại (crash / exit != 0)
    verifier_fail = CleanStateVerifier(
        project_root=project,
        config={"boot_command": [sys.executable, "-c", "raise RuntimeError('Boot crash')"]},
    )
    res_fail = verifier_fail.check_d5_clean_startup()
    assert res_fail.status == DimensionStatus.FAIL

    # Boot timeout (> 5000ms)
    verifier_timeout = CleanStateVerifier(
        project_root=project,
        config={
            "boot_command": [sys.executable, "-c", "import time; time.sleep(10)"],
            "boot_timeout_ms": 200.0,  # Dùng timeout nhỏ cho test nhanh
        },
    )
    res_timeout = verifier_timeout.check_d5_clean_startup()
    assert res_timeout.status == DimensionStatus.FAIL
    assert any("timed out" in v for v in res_timeout.violations)


def test_ac_cs_06_idempotent_verifier_execution(tmp_path):
    """AC-CS-06: Verifier chạy liên tiếp >= 3 lần không làm biến đổi mã nguồn hay sinh rác."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "main.py").write_text("def app(): return True\n", encoding="utf-8")

    initial_manifest = _compute_manifest_hash(project)
    verifier = CleanStateVerifier(
        project_root=project,
        config={"boot_command": f'"{sys.executable}" -c "print(1)"'},
    )

    for i in range(3):
        report = verifier.audit()
        assert report.overall_status == DimensionStatus.PASS
        # Đảm bảo mã nguồn trên đĩa bất biến
        current_manifest = _compute_manifest_hash(project)
        assert current_manifest == initial_manifest


def test_ac_int_01_app_workflow_integration(tmp_path):
    """AC-INT-01: Tích hợp chốt chặn Clean State vào audit và sign_off trong AppWorkflowStore."""
    project = tmp_path / "app"
    project.mkdir()
    (project / "index.html").write_text("app", encoding="utf-8")

    store = AppWorkflowStore(tmp_path / "brain")
    store.create("task-clean", "Test clean state gate", project)

    def dummy_cmd(*ids):
        return {
            "id": "TEST",
            "argv": [sys.executable, "-c", "print('ok')"],
            "cwd": ".",
            "ac_ids": list(ids),
            "browser": {"url": "http://localhost:3000", "assertions": [{"selector": "body", "text": "app"}]},
        }

    spec = {
        "scope": "test app",
        "design": "clean ui",
        "contracts": "clean storage",
        "acceptance_criteria": [{"id": "AC1", "description": "task ac", "ui": False}],
        "risks": "none",
        "verification_commands": [dummy_cmd("AC1")],
        "evidence_root": str(tmp_path),
    }

    # Submit spec & review design
    s = store.submit_spec("task-clean", spec, "arch-1")
    store.review_design("task-clean", "APPROVE", "rev-1", s["spec_sha256"], "Design ok")

    # Thử cài file rác vào project trước sign-off
    (project / "stray.tmp").write_text("dirty artifact", encoding="utf-8")
    with pytest.raises(WorkflowError, match="Clean state verification failed before sign-off"):
        store.sign_off("task-clean", s["spec_sha256"], "Sếp: Duyệt bản đặc tả này")

    # Dọn sạch file rác -> sign_off thành công
    (project / "stray.tmp").unlink()
    state = store.sign_off("task-clean", s["spec_sha256"], "Sếp: Duyệt bản đặc tả này")
    assert state["stage"] == "IMPLEMENTATION"
