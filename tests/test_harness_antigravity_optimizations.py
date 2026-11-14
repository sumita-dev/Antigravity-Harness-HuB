# -*- coding: utf-8 -*-
"""Tests for the 3 Antigravity 2.0 Harness Optimizations:
1. Native `run_workflow` triad scripts (`workflows/app_triad.py`, `workflows/marketing_triad.py`).
2. Progressive Disclosure for `GEMINI.md` (>= 30% byte reduction, core invariants & pointers intact).
3. Stop hook / `audit_response` false-positive reduction for illustrative code/backticks.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from harness.validators.hallucination_detector import audit_response
from scripts.enforce_anti_hallucination_hook import evaluate_hook_payload

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_transcript(path: Path, steps: list[dict[str, Any]]) -> Path:
    lines = [json.dumps(s, ensure_ascii=False) for s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_run_workflow_triad_scripts_exist_and_parse_cleanly() -> None:
    """Both workflows/app_triad.py and workflows/marketing_triad.py exist, compile, and define primitives & schemas."""
    app_script = REPO_ROOT / "workflows" / "app_triad.py"
    mkt_script = REPO_ROOT / "workflows" / "marketing_triad.py"

    assert app_script.is_file(), "Missing workflows/app_triad.py"
    assert mkt_script.is_file(), "Missing workflows/marketing_triad.py"

    app_src = app_script.read_text(encoding="utf-8")
    mkt_src = mkt_script.read_text(encoding="utf-8")

    # Both must parse and compile cleanly with top-level await support
    ast.parse(app_src, filename=str(app_script))
    compile(app_src, str(app_script), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    ast.parse(mkt_src, filename=str(mkt_script))
    compile(mkt_src, str(mkt_script), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    # App Triad primitives, schemas, model tiering, and circuit breakers
    for token in (
        "phase(",
        "agent(",
        "log(",
        "CRITIQUE_VERDICT_SCHEMA",
        "AUDIT_VERDICT_SCHEMA",
        "max_critique_rounds",
        "max_qa_rounds",
        "max_total_cycles",
        "total_cycles",
        "await maker(",
        "await run_app_triad(",
        'workspace="share"',
        'model="inherit"',
        'model="flash"',
        "run_workflow(",
    ):
        assert token in app_src, f"workflows/app_triad.py missing '{token}'"

    # Marketing Triad primitives, schemas, and circuit breaker
    for token in (
        "phase(",
        "agent(",
        "log(",
        "DOSSIER_SCHEMA",
        "CREATOR_DRAFT_SCHEMA",
        "MARKETING_CRITIQUE_SCHEMA",
        "max_critique_rounds",
        "await creator(",
        "await run_marketing_triad(",
        "source_accuracy",
        "policy",
        "integrity",
        "task_quality",
        "run_workflow(",
    ):
        assert token in mkt_src, f"workflows/marketing_triad.py missing '{token}'"


def test_gemini_md_progressive_disclosure_size_and_invariants() -> None:
    """GEMINI.md is reduced by >= 30% from 18,912 bytes while preserving core invariants and on-demand pointers."""
    gem_path = REPO_ROOT / "GEMINI.md"
    size = gem_path.stat().st_size
    # Baseline was 18,912 bytes; >= 30% reduction -> <= 13,238 bytes
    assert size <= 13238, f"GEMINI.md is {size} bytes (> 13,238 bytes; < 30% reduction)"

    gem_text = gem_path.read_text(encoding="utf-8")
    for required in (
        "Dynamic Triad Protocol",
        "workflows/app_triad.py",
        "workflows/marketing_triad.py",
        "docs/anti-hallucination-details.md",
        "docs/second-brain-protocol.md",
        "SubAgent Lifecycle Closure Invariant",
        "Workspace Isolation Invariant",
        "Session Rollover Enforcer",
        "TUYỆT ĐỐI CẤM gọi `schedule` timer khi kích hoạt SubAgent",
    ):
        assert required in gem_text, f"GEMINI.md missing required invariant/pointer: {required}"

    assert (REPO_ROOT / "docs" / "anti-hallucination-details.md").is_file()
    assert (REPO_ROOT / "docs" / "second-brain-protocol.md").is_file()


def test_audit_response_ignores_explicit_code_fences_only() -> None:
    """Legitimate code inside ```python or ```json blocks does not trigger false positives."""
    doc_response = (
        "Tài liệu cấu hình các bộ lọc kiểm tra mã nguồn và dữ liệu mẫu:\n\n"
        "```python\n"
        "COMPLETION_EXAMPLES = ['all tests pass', 'tests passed', 'chạy xanh mượt']\n"
        "ROUTING_EXAMPLES = ['redirect to homepage', '404 not found']\n"
        "SPECULATIVE_EXAMPLES = ['should work', 'probably']\n"
        "```\n\n"
        "```json\n"
        '{"sample_status": "all checks passed", "note": "free tier api call"}\n'
        "```\n"
        "Quy trình này áp dụng cho mọi module."
    )
    res = audit_response(doc_response, base_dir=REPO_ROOT, check_paths=True)
    assert res.verdict == "APPROVE", f"False positive triggered: {res.violations}"
    assert res.unverified_claims == []
    assert res.unverified_routing_claims == []
    assert res.unverified_api_claims == []
    assert res.speculative_phrases == []
    assert res.sycophancy_phrases == []


def test_audit_response_rejects_bypass_in_text_fence_or_inline_backticks() -> None:
    """Wrapping fake completion claims in ```text or inline backticks with >=20% filler prose MUST still be REJECTED."""
    filler = (
        "Đây là phần giải thích chi tiết về tiến độ công việc trong phiên làm việc hôm nay. "
        "Các thay đổi đã được rà soát kỹ lưỡng theo yêu cầu của dự án và kiến trúc tổng thể.\n"
    )
    text_fence_bypass = filler + "```text\ntất cả test đã pass\n```\n"
    res_text_fence = audit_response(text_fence_bypass, base_dir=REPO_ROOT, check_paths=True)
    assert res_text_fence.verdict == "REJECT"
    assert res_text_fence.unverified_claims

    inline_backtick_bypass = filler + "Kết quả cuối cùng: `tất cả test đã pass`."
    res_inline = audit_response(inline_backtick_bypass, base_dir=REPO_ROOT, check_paths=True)
    assert res_inline.verdict == "REJECT"
    assert res_inline.unverified_claims


def test_audit_response_still_rejects_unquoted_violations() -> None:
    """Real unquoted violations in prose must still be rejected."""
    bad_completion = audit_response(
        "Báo cáo: tất cả test đã pass hoàn toàn.",
        base_dir=REPO_ROOT,
        check_paths=True,
    )
    assert bad_completion.verdict == "REJECT"
    assert bad_completion.unverified_claims

    bad_routing = audit_response(
        "Báo cáo: 4 link bị fallback về trang chủ.",
        base_dir=REPO_ROOT,
        check_paths=True,
    )
    assert bad_routing.verdict == "REJECT"
    assert bad_routing.unverified_routing_claims


def test_stop_hook_allows_explicit_code_blocks_and_blocks_text_fence_bypass(tmp_path: Path) -> None:
    """Stop hook allows explicit ```python code blocks while still blocking ```text bypasses."""
    t_code = _write_transcript(
        tmp_path / "t_code.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Cho ví dụ cấu hình python"},
            {
                "type": "PLANNER_RESPONSE",
                "content": (
                    "Dưới đây là cấu hình mẫu trong Python:\n"
                    "```python\n"
                    "PATTERNS = ['all tests pass', 'chắc là', '404 not found']\n"
                    "```\n"
                    "Đây là cấu hình kiểm thử."
                ),
            },
        ],
    )
    payload_code = {
        "conversationId": "conv-opt-code",
        "transcriptPath": str(t_code),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload_code) == {"decision": "allow"}

    t_bypass = _write_transcript(
        tmp_path / "t_bypass.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Báo cáo kết quả test"},
            {
                "type": "PLANNER_RESPONSE",
                "content": (
                    "Đã hoàn thành cập nhật toàn bộ tài liệu và kiểm tra cấu hình hệ thống.\n"
                    "```text\n"
                    "tất cả test đã pass\n"
                    "```\n"
                ),
            },
        ],
    )
    payload_bypass = {
        "conversationId": "conv-opt-bypass",
        "transcriptPath": str(t_bypass),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res_bypass = evaluate_hook_payload(payload_bypass)
    assert res_bypass["decision"] == "continue"
