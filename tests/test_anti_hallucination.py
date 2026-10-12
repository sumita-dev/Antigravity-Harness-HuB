"""Unit tests cho module hallucination_detector.py."""

from pathlib import Path
import pytest

from harness.validators.hallucination_detector import (
    AuditResult,
    audit_response,
    detect_speculative_language,
    verify_execution_claims,
    verify_file_paths,
)


REPO_DIR = Path(__file__).resolve().parent.parent


def test_verify_file_paths_existing():
    """Kiểm tra đường dẫn file có thật trong repo."""
    text = (
        "Chúng ta đã cấu hình file `configs/harness_config.json` và "
        "tham chiếu `requirements.txt` cùng file [README](file:///README.md)."
    )
    res = verify_file_paths(text, base_dir=REPO_DIR)
    assert res["valid"] is True
    assert len(res["missing_paths"]) == 0
    assert len(res["verified_paths"]) >= 3


def test_verify_file_paths_missing():
    """Kiểm tra phát hiện file bịa/không tồn tại."""
    text = "Vui lòng xem `harness/phantom_unknown_file.py` để biết chi tiết."
    res = verify_file_paths(text, base_dir=REPO_DIR)
    assert res["valid"] is False
    assert "harness/phantom_unknown_file.py" in res["missing_paths"]


def test_detect_speculative_language_clean():
    """Văn bản chuẩn, không chứa ngôn ngữ võ đoán."""
    text = "Đã thực hiện cập nhật mã nguồn theo đúng đặc tả kỹ thuật."
    violations = detect_speculative_language(text)
    assert len(violations) == 0


def test_detect_speculative_language_violations():
    """Văn bản chứa từ ngữ võ đoán tiếng Anh & tiếng Việt."""
    text_en = "This fix should work and probably solves the bug without verification."
    violations_en = detect_speculative_language(text_en)
    assert len(violations_en) >= 2
    assert any("should work" in v for v in violations_en)
    assert any("probably" in v for v in violations_en)

    text_vi = "Đoạn code này chắc là ổn, dường như sẽ hoạt động bình thường mà không cần test."
    violations_vi = detect_speculative_language(text_vi)
    assert len(violations_vi) >= 2
    assert any("chắc là" in v for v in violations_vi)
    assert any("dường như" in v for v in violations_vi)


def test_verify_execution_claims_without_log():
    """Tuyên bố thành công nhưng thiếu execution log -> REJECT / invalid."""
    text = "Tất cả test đã pass và fix thành công 100%."
    res = verify_execution_claims(text, execution_logs=None)
    assert res["valid"] is False
    assert len(res["unverified_claims"]) >= 1


def test_verify_execution_claims_with_valid_log():
    """Tuyên bố thành công có log exit code 0 đi kèm -> Valid."""
    text = "Tất cả test đã pass và fix thành công."
    log_str = (
        "Running command: pytest tests/\n"
        "16 passed in 1.2s\n"
        "Command exited with code 0"
    )
    res = verify_execution_claims(text, execution_logs=log_str)
    assert res["valid"] is True
    assert len(res["unverified_claims"]) == 0

    # Test với danh sách dict log
    log_list = [{"command": "pytest", "exit_code": 0, "output": "16 passed"}]
    res_list = verify_execution_claims(text, execution_logs=log_list)
    assert res_list["valid"] is True


def test_audit_response_approve():
    """Kiểm toán trường hợp đạt chuẩn: đường dẫn thật, không võ đoán, có log chứng thực."""
    text = (
        "Đã hoàn thành cấu hình trong `configs/harness_config.json`.\n"
        "Tất cả test đã pass sau khi chạy kiểm thử."
    )
    logs = "pytest tests/ -> 16 passed, exited with code 0"
    audit = audit_response(text, base_dir=REPO_DIR, execution_logs=logs)
    assert audit.verdict == "APPROVE"
    assert audit.is_approved is True
    assert audit.score == 1.0
    assert len(audit.violations) == 0


def test_audit_response_reject():
    """Kiểm toán trường hợp vi phạm đa trụ cột: file ảo, ngôn ngữ võ đoán, thiếu log."""
    text = (
        "Code mới trong `harness/fake_module.py` chắc là sẽ chạy tốt.\n"
        "Tất cả test đã pass mà không gặp vấn đề gì."
    )
    audit = audit_response(text, base_dir=REPO_DIR, execution_logs=None)
    assert audit.verdict == "REJECT"
    assert audit.is_approved is False
    assert audit.score < 1.0
    assert len(audit.violations) >= 3
    assert any("Ảo giác đường dẫn" in v for v in audit.violations)
    assert any("Ngôn ngữ võ đoán" in v for v in audit.violations)
    assert any("Tuyên bố thành công" in v for v in audit.violations)
