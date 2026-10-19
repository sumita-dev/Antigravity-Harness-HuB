"""Unit tests for Self-Correction Loop."""

import pytest
from harness.validators.self_correction import (
    CorrectionAttempt,
    SelfCorrectionResult,
    default_deterministic_fixer,
    run_self_correction_loop,
)


def test_self_correction_success_immediately():
    """Văn bản hợp lệ ngay lần đầu không cần retry (total_retries = 0)."""
    text = "Hello world! This is a valid response with sufficient length."
    constraints = {
        "min_words": 5,
        "max_words": 20,
    }

    result = run_self_correction_loop(text, constraints)

    assert result.success is True
    assert result.total_retries == 0
    assert len(result.attempts) == 1
    assert result.attempts[0].success is True
    assert result.attempts[0].violations == []
    assert result.final_text == text


def test_self_correction_success_after_one_retry_default_fixer():
    """Văn bản vi phạm được default_deterministic_fixer tự động sửa sau 1 lần retry."""
    # Vi phạm: chứa từ cấm và thiếu starts_with
    text = "This should probably work and it is great."
    constraints = {
        "forbidden_words": ["probably"],
        "starts_with": "[VERIFIED]",
    }

    result = run_self_correction_loop(text, constraints, max_retries=2)

    assert result.success is True
    assert result.total_retries == 1
    assert len(result.attempts) == 2
    assert result.attempts[0].success is False
    assert result.attempts[1].success is True
    assert "probably" not in result.final_text
    assert result.final_text.startswith("[VERIFIED]")


def test_self_correction_json_fixing():
    """Tự động tạo JSON hợp lệ khi chuỗi ban đầu không có JSON hợp lệ."""
    text = 'Here is the summary with no json object at all'
    constraints = {
        "json_format": True,
        "required_json_keys": ["status", "code"],
    }

    result = run_self_correction_loop(text, constraints, max_retries=2)

    assert result.success is True
    assert result.total_retries >= 1
    assert "```json" in result.final_text
    assert '"status": "default_value"' in result.final_text
    assert '"code": "default_value"' in result.final_text


def test_self_correction_with_custom_corrector_fn():
    """Vòng lặp sử dụng custom corrector function."""
    text = "draft text"
    constraints = {
        "required_keywords": ["ANTIGRAVITY", "CERTIFIED"],
    }

    def my_corrector(t: str, violations: list[str]) -> str:
        return f"{t} with ANTIGRAVITY and CERTIFIED badges"

    result = run_self_correction_loop(text, constraints, corrector_fn=my_corrector, max_retries=2)

    assert result.success is True
    assert result.total_retries == 1
    assert "ANTIGRAVITY" in result.final_text
    assert "CERTIFIED" in result.final_text


def test_self_correction_max_retries_exhausted():
    """Trường hợp sửa không thành công sau khi hết số lần retry tối đa."""
    text = "bad text"
    constraints = {
        "min_words": 100,  # Đòi hỏi 100 từ nhưng corrector không thêm đủ
    }

    def stubborn_corrector(t: str, violations: list[str]) -> str:
        return f"{t} still short"

    result = run_self_correction_loop(text, constraints, corrector_fn=stubborn_corrector, max_retries=2)

    assert result.success is False
    assert result.total_retries == 2
    assert len(result.attempts) == 3  # Attempt 0, Attempt 1, Attempt 2
    assert result.attempts[-1].success is False
    assert len(result.attempts[-1].violations) > 0
