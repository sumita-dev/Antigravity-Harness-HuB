"""Unit tests for Repro-First Policy Verifier (harness/validators/repro_first_verifier.py)."""

from __future__ import annotations

from pathlib import Path
import pytest

from harness.validators.repro_first_verifier import (
    ReproFirstVerifier,
    ReproVerificationResult,
    verify_repro_first,
)


def test_missing_repro_file(tmp_path: Path):
    """Kịch bản: File test không tồn tại -> status MISSING_REPRO, is_valid=False."""
    result = verify_repro_first(repro_dir=tmp_path, issue_id="999", run_test=True)

    assert isinstance(result, ReproVerificationResult)
    assert result.is_valid is False
    assert result.status == "MISSING_REPRO"
    assert result.exit_code is None
    assert result.test_path is None
    assert "not found" in result.message.lower()


def test_repro_file_exists_fails_as_expected_red_confirmed(tmp_path: Path):
    """Kịch bản: File test tồn tại và fail như mong muốn -> status RED_CONFIRMED, is_valid=True."""
    repro_dir = tmp_path / "tests" / "repro"
    repro_dir.mkdir(parents=True)
    test_file = repro_dir / "test_issue_101.py"
    test_file.write_text(
        "def test_bug_reproduction():\n"
        "    # Failing test demonstrating the bug\n"
        "    assert 1 == 2, 'Simulated reproduced bug failure'\n",
        encoding="utf-8",
    )

    result = verify_repro_first(
        repro_dir=tmp_path,
        issue_id="101",
        run_test=True,
        expected_status="RED",
    )

    assert result.is_valid is True
    assert result.status == "RED_CONFIRMED"
    assert result.exit_code is not None
    assert result.exit_code != 0
    assert result.test_path == str(test_file.resolve())
    assert "RED confirmed" in result.message


def test_repro_file_passes_when_expecting_red_invalid_failure(tmp_path: Path):
    """Kịch bản: File test pass khi chưa sửa (kỳ vọng RED nhưng lại pass) -> status INVALID_FAILURE, is_valid=False."""
    test_file = tmp_path / "test_issue_102.py"
    test_file.write_text(
        "def test_passing_instead_of_failing():\n"
        "    assert 1 == 1\n",
        encoding="utf-8",
    )

    result = verify_repro_first(
        repro_dir=tmp_path,
        issue_id="102",
        run_test=True,
        expected_status="RED",
    )

    assert result.is_valid is False
    assert result.status == "INVALID_FAILURE"
    assert result.exit_code == 0
    assert "passed unexpectedly" in result.message


def test_repro_file_passes_when_expecting_green_confirmed(tmp_path: Path):
    """Kịch bản: Sau khi sửa lỗi, test pass -> status GREEN_CONFIRMED, is_valid=True."""
    test_file = tmp_path / "test_issue_103.py"
    test_file.write_text(
        "def test_fixed_behavior():\n"
        "    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )

    result = verify_repro_first(
        repro_dir=tmp_path,
        issue_id="issue_103",
        run_test=True,
        expected_status="GREEN",
    )

    assert result.is_valid is True
    assert result.status == "GREEN_CONFIRMED"
    assert result.exit_code == 0
    assert "GREEN confirmed" in result.message


def test_repro_file_fails_when_expecting_green_invalid_failure(tmp_path: Path):
    """Kịch bản: Kỳ vọng GREEN nhưng test vẫn fail -> status INVALID_FAILURE, is_valid=False."""
    test_file = tmp_path / "test_issue_104.py"
    test_file.write_text(
        "def test_still_failing():\n"
        "    assert False, 'Still broken'\n",
        encoding="utf-8",
    )

    result = verify_repro_first(
        repro_dir=tmp_path,
        issue_id="104",
        run_test=True,
        expected_status="GREEN",
    )

    assert result.is_valid is False
    assert result.status == "INVALID_FAILURE"
    assert result.exit_code != 0
    assert "expecting GREEN" in result.message


def test_run_test_false_checks_presence_only(tmp_path: Path):
    """Kịch bản: run_test=False chỉ kiểm tra file có mặt."""
    test_file = tmp_path / "test_issue_105.py"
    test_file.write_text("# dummy test", encoding="utf-8")

    result = verify_repro_first(
        repro_dir=tmp_path,
        issue_id="105",
        run_test=False,
        expected_status="RED",
    )

    assert result.is_valid is True
    assert result.status == "RED_CONFIRMED"
    assert result.exit_code is None
    assert "run_test=False" in result.message


def test_repro_first_verifier_class_method_and_to_dict(tmp_path: Path):
    """Kịch bản: Gọi qua ReproFirstVerifier.verify và kiểm tra method to_dict()."""
    test_file = tmp_path / "test_issue_106.py"
    test_file.write_text("def test_fail(): assert False", encoding="utf-8")

    result = ReproFirstVerifier.verify(
        repro_dir=tmp_path,
        issue_id="issue_106",
        run_test=True,
        expected_status="RED",
    )

    assert result.is_valid is True
    assert result.status == "RED_CONFIRMED"
    dict_data = result.to_dict()
    assert dict_data["status"] == "RED_CONFIRMED"
    assert dict_data["is_valid"] is True
    assert "exit_code" in dict_data
    assert "test_path" in dict_data
