# -*- coding: utf-8 -*-
"""Test suite for unified in-process Stop hook pipeline."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import pytest

from scripts.unified_stop_pipeline import (
    SingleTranscriptContext,
    parse_transcript_once,
    run_unified_stop_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SCRIPT = REPO_ROOT / "scripts" / "unified_stop_pipeline.py"


def _write_transcript(path: Path, steps: list[dict[str, Any]]) -> Path:
    lines = [json.dumps(s, ensure_ascii=False) for s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run_cli(payload: dict[str, Any]) -> dict[str, Any]:
    res = subprocess.run(
        [sys.executable, str(PIPELINE_SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, f"Pipeline failed: {res.stderr}"
    return json.loads(res.stdout.strip())


def test_unified_pipeline_benign_transcript_allows(tmp_path: Path) -> None:
    t = _write_transcript(
        tmp_path / "t_benign.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra hệ thống"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {"Role": "Code Critic", "TypeName": "research", "Prompt": "review"},
                    }
                ],
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {"Role": "QA Auditor", "TypeName": "research", "Prompt": "audit"},
                    }
                ],
            },
            {"type": "PLANNER_RESPONSE", "content": "Hệ thống hoạt động bình thường."},
        ],
    )
    payload = {
        "conversationId": "conv-test-benign",
        "transcriptPath": str(t),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res = run_unified_stop_pipeline(payload)
    assert res == {"decision": "allow"}


def test_unified_pipeline_blocks_hallucination(tmp_path: Path) -> None:
    t = _write_transcript(
        tmp_path / "t_hallucination.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Tình trạng thế nào?"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Chắc là hệ thống hoạt động ổn định, giả thuyết của anh hoàn toàn đúng.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-test-hal",
        "transcriptPath": str(t),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res = run_unified_stop_pipeline(payload)
    assert res["decision"] == "continue"
    assert "ANTI-HALLUCINATION-GUARD" in res["reason"]


def test_unified_pipeline_blocks_unresolved_failure(tmp_path: Path) -> None:
    t = _write_transcript(
        tmp_path / "t_fail.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Chạy pytest"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest -q"}}],
            },
            {
                "type": "GENERIC",
                "status": "ERROR",
                "content": "=== FAILURES ===\nFAILED tests/test_foo.py::test_bar - AssertionError\n1 failed",
                "exit_code": 1,
            },
            {"type": "PLANNER_RESPONSE", "content": "Em đã chạy xong pytest."},
        ],
    )
    payload = {
        "conversationId": "conv-test-fail",
        "transcriptPath": str(t),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res = run_unified_stop_pipeline(payload)
    assert res["decision"] == "continue"
    assert "PRE-HANDOFF-GATE" in res["reason"]


def test_unified_pipeline_cli_stdin(tmp_path: Path) -> None:
    t = _write_transcript(
        tmp_path / "t_cli.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Hello"},
            {"type": "PLANNER_RESPONSE", "content": "Chào anh."},
        ],
    )
    payload = {
        "conversationId": "conv-test-cli",
        "transcriptPath": str(t),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    out = _run_cli(payload)
    assert out.get("decision") in ("allow", "continue")


def test_unified_pipeline_latency_under_200ms(tmp_path: Path) -> None:
    t = _write_transcript(
        tmp_path / "t_perf.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra hiệu năng"},
            {"type": "PLANNER_RESPONSE", "content": "Đang đo thời gian thực thi."},
        ],
    )
    payload = {
        "conversationId": "conv-test-perf",
        "transcriptPath": str(t),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }

    # Warm-up run
    run_unified_stop_pipeline(payload)

    # Measured run
    t0 = time.perf_counter()
    res = run_unified_stop_pipeline(payload)
    elapsed = time.perf_counter() - t0

    assert res["decision"] in ("allow", "continue")
    assert elapsed < 0.20, f"Unified stop pipeline took {elapsed:.4f}s >= 0.2s target"
