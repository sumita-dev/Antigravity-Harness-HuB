"""Test suite for deterministic IFEval-inspired compliance rules."""

import pytest
from harness.validators.deterministic_rules import (
    RuleAuditResult,
    audit_deterministic_constraints,
    verify_bullet_points,
    verify_forbidden_words,
    verify_json_format,
    verify_markdown_headers,
    verify_paragraph_count,
    verify_required_keywords,
    verify_start_end_phrase,
    verify_word_count,
)


def test_verify_word_count():
    text = "One two three four five"
    # Pass exact range
    ok, cnt, msg = verify_word_count(text, min_words=3, max_words=10)
    assert ok is True
    assert cnt == 5

    # Fail min
    ok, cnt, msg = verify_word_count(text, min_words=6)
    assert ok is False
    assert cnt == 5
    assert "nhỏ hơn giới hạn tối thiểu" in msg

    # Fail max
    ok, cnt, msg = verify_word_count(text, max_words=4)
    assert ok is False
    assert cnt == 5
    assert "vượt quá giới hạn tối đa" in msg


def test_verify_json_format():
    # Raw JSON
    raw_json = '{"status": "ok", "code": 200}'
    ok, parsed, msg = verify_json_format(raw_json, required_keys=["status", "code"])
    assert ok is True
    assert parsed == {"status": "ok", "code": 200}

    # Markdown codeblock JSON
    md_json = """Here is the config:
```json
{
  "name": "harness",
  "version": "2.0"
}
```
Thanks!"""
    ok, parsed, msg = verify_json_format(md_json, required_keys=["name"])
    assert ok is True
    assert parsed["name"] == "harness"
    assert parsed["version"] == "2.0"

    # Missing required keys
    ok, parsed, msg = verify_json_format(raw_json, required_keys=["status", "non_existent"])
    assert ok is False
    assert "thiếu các key bắt buộc: non_existent" in msg

    # Invalid JSON
    invalid_json = "This is definitely { not valid json }..."
    ok, parsed, msg = verify_json_format(invalid_json)
    assert ok is False
    assert parsed is None


def test_verify_forbidden_words():
    text = "This solution should work and probably fixes the issue."
    # Detected
    ok, detected, msg = verify_forbidden_words(text, ["should work", "probably", "guarantee"])
    assert ok is False
    assert "should work" in detected
    assert "probably" in detected
    assert "guarantee" not in detected

    # Clean
    clean_text = "Task completed with exit code 0 and all tests passed."
    ok, detected, msg = verify_forbidden_words(clean_text, ["probably", "maybe", "chắc là"])
    assert ok is True
    assert len(detected) == 0


def test_verify_required_keywords():
    text = "Docker container deployment with Docker compose and Docker swarm."
    # Pass min occurrences
    ok, counts, msg = verify_required_keywords(text, ["Docker", "compose"], min_occurrences=1)
    assert ok is True
    assert counts["Docker"] == 3
    assert counts["compose"] == 1

    # Fail higher min occurrences
    ok, counts, msg = verify_required_keywords(text, ["compose"], min_occurrences=2)
    assert ok is False
    assert counts["compose"] == 1
    assert "xuất hiện 1/2 lần" in msg


def test_verify_start_end_phrase():
    text = "[START] Pipeline execution finished successfully. [END]"
    ok, msg = verify_start_end_phrase(text, starts_with="[START]", ends_with="[END]")
    assert ok is True

    # Fail starts_with
    ok, msg = verify_start_end_phrase(text, starts_with="[BEGIN]")
    assert ok is False
    assert "không bắt đầu bằng '[BEGIN]'" in msg

    # Fail ends_with
    ok, msg = verify_start_end_phrase(text, ends_with="[DONE]")
    assert ok is False
    assert "không kết thúc bằng '[DONE]'" in msg


def test_verify_markdown_headers():
    doc = """# Main Title

## Section 1
Content 1

## Section 2
Content 2

### Subsection 2.1
Details
"""
    # Any level headers
    ok, cnt, msg = verify_markdown_headers(doc, min_headers=3, max_headers=5)
    assert ok is True
    assert cnt == 4

    # Level 2 headers
    ok, cnt, msg = verify_markdown_headers(doc, level=2, min_headers=2, max_headers=2)
    assert ok is True
    assert cnt == 2

    # Level 1 headers fail min
    ok, cnt, msg = verify_markdown_headers(doc, level=1, min_headers=2)
    assert ok is False
    assert cnt == 1


def test_verify_paragraph_count():
    text = """First paragraph with some text.

Second paragraph with more interesting details.

Third paragraph closing the thoughts."""
    ok, cnt, msg = verify_paragraph_count(text, min_paragraphs=3, max_paragraphs=3)
    assert ok is True
    assert cnt == 3

    ok, cnt, msg = verify_paragraph_count(text, min_paragraphs=5)
    assert ok is False
    assert cnt == 3


def test_verify_bullet_points():
    text = """Task Checklist:
- Item 1
* Item 2
+ Item 3
1. Item 4
2. Item 5
"""
    ok, cnt, msg = verify_bullet_points(text, min_bullets=4, max_bullets=6)
    assert ok is True
    assert cnt == 5

    ok, cnt, msg = verify_bullet_points(text, min_bullets=10)
    assert ok is False
    assert cnt == 5


def test_audit_deterministic_constraints():
    sample_text = """# Executive Report

The audit result demonstrates full system compliance.
Docker containers are functioning properly.

- Verified container health
- Zero security vulnerabilities detected

```json
{
  "status": "APPROVED",
  "score": 100
}
```
"""
    constraints = {
        "min_words": 10,
        "max_words": 100,
        "required_json_keys": ["status", "score"],
        "forbidden_words": ["probably", "maybe", "should work"],
        "required_keywords": ["Docker", "compliance"],
        "min_headers": 1,
        "header_level": 1,
        "min_bullets": 2,
    }

    result = audit_deterministic_constraints(sample_text, constraints)
    assert isinstance(result, RuleAuditResult)
    assert result.valid is True
    assert len(result.violations) == 0
    assert result.metrics["word_count"] > 10
    assert result.metrics["json_valid"] is True
    assert result.metrics["bullet_count"] == 2
    assert result.metrics["header_count"] == 1

    # Introduce failure
    failing_constraints = {
        **constraints,
        "forbidden_words": ["compliance"],  # this exists in text
        "max_bullets": 1,  # text has 2
    }
    fail_result = audit_deterministic_constraints(sample_text, failing_constraints)
    assert fail_result.valid is False
    assert len(fail_result.violations) == 2
