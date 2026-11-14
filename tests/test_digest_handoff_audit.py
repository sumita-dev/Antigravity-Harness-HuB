# -*- coding: utf-8 -*-
"""Regression tests for the 7 audited gaps in digest <= 100 & Lean Handoff enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness.triad_protocol import (
    HandoffValidationError,
    parse_handoff_v2,
    validate_handoff_v2,
)
from scripts.enforce_triad_process_hook import GUARD_MARKER, evaluate_hook_payload


def _base_handoff(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": "T-DIGEST-AUDIT-01",
        "commit_sha": "abcdef1234567890",
        "verification_receipt": {
            "command": "pytest -q",
            "exit_code": 0,
            "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb924",
        },
        "digest": "Verdict: PASS | Exit Code: 0 | Key Findings: All unit tests passed.",
    }
    payload.update(overrides)
    return payload


def _write_transcript(path: Path, steps: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(s, ensure_ascii=False) for s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# GAP-01: strict_lean_handoff requires non-empty report_path or evidence_paths
# ---------------------------------------------------------------------------
def test_gap01_strict_lean_handoff_requires_report_or_evidence_paths() -> None:
    legacy_payload = _base_handoff()
    # Explicit legacy mode allows digest without report_path
    ok_legacy, err_legacy = validate_handoff_v2(
        legacy_payload, strict_lean_handoff=False, verify_report_exists=False
    )
    assert ok_legacy is True
    assert err_legacy == []

    # Default (strict_lean_handoff=True) rejects digest without report_path and without evidence_paths
    ok_strict, err_strict = validate_handoff_v2(legacy_payload, verify_report_exists=False)
    assert ok_strict is False
    assert any("Strict Lean Handoff" in e for e in err_strict)

    with pytest.raises(HandoffValidationError):
        parse_handoff_v2(legacy_payload, verify_report_exists=False)

    # Strict mode accepts non-empty report_path OR non-empty evidence_paths
    ok_with_rp, err_with_rp = validate_handoff_v2(
        _base_handoff(report_path="artifacts/qa_report.md"),
        strict_lean_handoff=True,
        verify_report_exists=False,
    )
    assert ok_with_rp is True
    assert err_with_rp == []

    ok_with_ep, err_with_ep = validate_handoff_v2(
        _base_handoff(evidence_paths=["artifacts/pytest.log"]),
        strict_lean_handoff=True,
        verify_report_exists=False,
    )
    assert ok_with_ep is True
    assert err_with_ep == []


# ---------------------------------------------------------------------------
# GAP-02: verify_report_exists checks is_file, size > 0, and non-placeholder
# ---------------------------------------------------------------------------
def test_gap02_verify_report_exists_rejects_dir_empty_and_placeholder(tmp_path: Path) -> None:
    # 1. Directory instead of file
    dir_path = tmp_path / "report_dir"
    dir_path.mkdir()
    ok_dir, err_dir = validate_handoff_v2(
        _base_handoff(report_path=str(dir_path)),
        require_report_path=True,
        verify_report_exists=True,
    )
    assert ok_dir is False
    assert any("không phải là tệp" in e for e in err_dir)

    # 2. 0-byte empty file
    empty_file = tmp_path / "empty_report.md"
    empty_file.write_text("", encoding="utf-8")
    ok_empty, err_empty = validate_handoff_v2(
        _base_handoff(report_path=str(empty_file)),
        require_report_path=True,
        verify_report_exists=True,
    )
    assert ok_empty is False
    assert any("rỗng" in e for e in err_empty)

    # 3. Bare placeholder content (TODO, TBD, ...)
    for placeholder in ("TODO", "tbd", "...", "   \n  "):
        ph_file = tmp_path / "placeholder_report.md"
        ph_file.write_text(placeholder, encoding="utf-8")
        ok_ph, err_ph = validate_handoff_v2(
            _base_handoff(report_path=str(ph_file)),
            require_report_path=True,
            verify_report_exists=True,
        )
        assert ok_ph is False, f"Placeholder {placeholder!r} should be rejected"
        assert any("placeholder" in e for e in err_ph)

    # 4. Valid non-empty report file passes
    valid_file = tmp_path / "valid_report.md"
    valid_file.write_text("# QA Report\n- Exit code: 0\n- Verdict: APPROVE\n", encoding="utf-8")
    ok_valid, err_valid = validate_handoff_v2(
        _base_handoff(report_path=str(valid_file)),
        require_report_path=True,
        verify_report_exists=True,
    )
    assert ok_valid is True
    assert err_valid == []


# ---------------------------------------------------------------------------
# GAP-03: digest validated against hallucination_detector (speculative/sycophancy)
# ---------------------------------------------------------------------------
def test_gap03_digest_rejects_speculative_and_sycophancy_phrases() -> None:
    spec_payload = _base_handoff(
        digest="Verdict: PASS | Probably works fine and should pass all tests.",
        report_path="artifacts/report.md",
    )
    ok_spec, err_spec = validate_handoff_v2(spec_payload, verify_report_exists=False)
    assert ok_spec is False
    assert any("võ đoán" in e for e in err_spec)

    syc_payload = _base_handoff(
        digest="Your intuition is absolutely spot-on, you hit the nail on the head.",
        report_path="artifacts/report.md",
    )
    ok_syc, err_syc = validate_handoff_v2(syc_payload, verify_report_exists=False)
    assert ok_syc is False
    assert any("Sycophancy" in e for e in err_syc)


# ---------------------------------------------------------------------------
# GAP-04: Consistent <= 100 words boundary & <= 1000 chars + path check
# ---------------------------------------------------------------------------
def test_gap04_digest_word_limit_100_words_boundary() -> None:
    exact_100 = " ".join(["ok"] * 100)
    ok_100, err_100 = validate_handoff_v2(
        _base_handoff(digest=exact_100, report_path="artifacts/r.md"),
        strict_lean_handoff=True,
        verify_report_exists=False,
    )
    assert ok_100 is True
    assert err_100 == []

    over_101 = " ".join(["ok"] * 101)
    ok_101, err_101 = validate_handoff_v2(
        _base_handoff(digest=over_101, report_path="artifacts/r.md"),
        strict_lean_handoff=True,
        verify_report_exists=False,
    )
    assert ok_101 is False
    assert any("100 từ" in e for e in err_101)


def test_digest_char_limit_1000_and_path_verification(tmp_path: Path) -> None:
    report_file = tmp_path / "real_report.md"
    report_file.write_text("# Real Report\nExit code 0.\n", encoding="utf-8")

    # 1. > 1000 chars (even though 1 word) -> rejected
    long_word_digest = "a" * 1001
    ok_chars, err_chars = validate_handoff_v2(
        _base_handoff(digest=long_word_digest, report_path=str(report_file)),
    )
    assert ok_chars is False
    assert any("1000 ký tự" in e for e in err_chars)

    # 2. Digest citing non-existent path with default verify_report_exists=True -> rejected
    ghost_digest = "Verdict: PASS | Checked `harness/non_existent_phantom_file.py`."
    ok_path, err_path = validate_handoff_v2(
        _base_handoff(digest=ghost_digest, report_path=str(report_file)),
    )
    assert ok_path is False
    assert any("đường dẫn không tồn tại" in e for e in err_path)


# ---------------------------------------------------------------------------
# GAP-05: SubAgent [Message] from Critic/QA without report_path is blocked
# ---------------------------------------------------------------------------
def test_gap05_subagent_message_without_report_path_blocked(tmp_path: Path) -> None:
    t_no_rp = _write_transcript(
        tmp_path / "t_no_report_path.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm thử tính năng"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Builder done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Code Critic"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Critic done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "QA Auditor", "Model": "flash"}}],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": "[Message] sender=conv-qa content=Verdict APPROVE. Exit code 0.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Hoàn tất.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    res = evaluate_hook_payload(
        {"transcriptPath": str(t_no_rp), "workspacePaths": [str(tmp_path)], "terminationReason": "NO_TOOL_CALL"}
    )
    assert res["decision"] == "continue"
    assert GUARD_MARKER in res["reason"]
    assert "Quy tắc 1.12" in res["reason"]


# ---------------------------------------------------------------------------
# GAP-06: Skimmed read_file (<20 lines on >30-line report) is blocked
# ---------------------------------------------------------------------------
def test_gap06_skimmed_report_read_blocked_and_full_read_allowed(tmp_path: Path) -> None:
    long_report = tmp_path / "long_qa_report.md"
    long_report.write_text("\n".join(f"Line {i}: verification detail" for i in range(1, 51)), encoding="utf-8")

    # 1. Only skimmed lines 1-5 on a 50-line file -> blocked
    t_skimmed = _write_transcript(
        tmp_path / "t_skimmed.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm thử"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Builder done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Code Critic"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Critic done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "QA Auditor", "Model": "flash"}}],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"[Message] sender=conv-qa content=Done. report_path={long_report.as_posix()}",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "read_file", "args": {"Path": str(long_report), "StartLine": 1, "EndLine": 5}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Line 1..5"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Xong.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    res_skim = evaluate_hook_payload(
        {"transcriptPath": str(t_skimmed), "workspacePaths": [str(tmp_path)], "terminationReason": "NO_TOOL_CALL"}
    )
    assert res_skim["decision"] == "continue"
    assert "Quy tắc 1.12" in res_skim["reason"]
    assert "đọc lướt" in res_skim["reason"]

    # 2. Full read (without StartLine/EndLine or >=20 lines) -> allowed
    t_full = _write_transcript(
        tmp_path / "t_full_read.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm thử"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Builder done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Code Critic"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Critic done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "QA Auditor", "Model": "flash"}}],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"[Message] sender=conv-qa content=Done. report_path={long_report.as_posix()}",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "read_file", "args": {"Path": str(long_report), "StartLine": 1, "EndLine": 50}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Full report"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Xong.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    res_full = evaluate_hook_payload(
        {"transcriptPath": str(t_full), "workspacePaths": [str(tmp_path)], "terminationReason": "NO_TOOL_CALL"}
    )
    assert res_full == {"decision": "allow"}


# ---------------------------------------------------------------------------
# GAP-07: Extended extensions (.txt, .log, .html, .csv) & downstream Prompt ref
# ---------------------------------------------------------------------------
def test_gap07_extended_extensions_and_downstream_prompt_context(tmp_path: Path) -> None:
    builder_log = tmp_path / "builder_output.log"
    builder_log.write_text("Build succeeded\n", encoding="utf-8")

    # 1. Builder provides .log report_path, Critic Prompt omits it -> blocked
    t_missing_ctx = _write_transcript(
        tmp_path / "t_missing_ctx.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Build & verify"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"[Message] sender=conv-b1 content=Done. report_path={builder_log.as_posix()}",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "read_file", "args": {"Path": str(builder_log)}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Build succeeded"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {"TypeName": "self", "Role": "Code Critic", "Prompt": "Review the code."},
                    }
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Critic done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "TypeName": "self",
                            "Role": "QA Auditor",
                            "Model": "flash",
                            "Prompt": f"Verify build from {builder_log.name}",
                        },
                    }
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "QA done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Xong.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    res_missing = evaluate_hook_payload(
        {"transcriptPath": str(t_missing_ctx), "workspacePaths": [str(tmp_path)], "terminationReason": "NO_TOOL_CALL"}
    )
    assert res_missing["decision"] == "continue"
    assert "builder_output.log" in res_missing["reason"]

    # 2. Both Critic and QA Prompts reference builder_output.log, and .log was read -> allowed
    t_with_ctx = _write_transcript(
        tmp_path / "t_with_ctx.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Build & verify"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"[Message] sender=conv-b1 content=Done. report_path={builder_log.as_posix()}",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "read_file", "args": {"Path": str(builder_log)}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Build succeeded"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "TypeName": "self",
                            "Role": "Code Critic",
                            "Prompt": f"Review changes and {builder_log.as_posix()}",
                        },
                    }
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Critic done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "TypeName": "self",
                            "Role": "QA Auditor",
                            "Model": "flash",
                            "Prompt": f"Verify {builder_log.name}",
                        },
                    }
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "QA done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Xong.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    res_ok = evaluate_hook_payload(
        {"transcriptPath": str(t_with_ctx), "workspacePaths": [str(tmp_path)], "terminationReason": "NO_TOOL_CALL"}
    )
    assert res_ok == {"decision": "allow"}
