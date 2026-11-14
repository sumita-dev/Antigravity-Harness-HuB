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

    # Both must parse and compile cleanly
    ast.parse(app_src, filename=str(app_script))
    compile(app_src, str(app_script), "exec")
    ast.parse(mkt_src, filename=str(mkt_script))
    compile(mkt_src, str(mkt_script), "exec")

    # App Triad primitives, schemas, model tiering, and circuit breakers
    for token in (
        "phase(",
        "agent(",
        "log(",
        "CRITIQUE_VERDICT_SCHEMA",
        "AUDIT_VERDICT_SCHEMA",
        "max_critique_rounds",
        "max_qa_rounds",
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


def test_audit_response_ignores_illustrative_keywords_in_code_and_backticks() -> None:
    """Illustrative keywords inside fenced code blocks or inline backticks must not trigger false positives."""
    doc_response = (
        "Tài liệu hướng dẫn quy chuẩn rào chắn:\n"
        "- Tránh viết các cụm như `tất cả test đã pass`, `chắc là`, `giả thuyết của anh đúng`, "
        "`bị fallback về`, hoặc `free tier gọi được api` khi chưa có bằng chứng.\n\n"
        "Ví dụ mẫu cấu hình regex kiểm tra:\n"
        "```python\n"
        "COMPLETION_EXAMPLES = ['all tests pass', 'tests passed', 'chạy xanh mượt']\n"
        "ROUTING_EXAMPLES = ['redirect to homepage', '404 not found']\n"
        "```\n"
        "Quy trình này áp dụng cho mọi báo cáo."
    )
    res = audit_response(doc_response, base_dir=REPO_ROOT, check_paths=True)
    assert res.verdict == "APPROVE", f"False positive triggered: {res.violations}"
    assert res.unverified_claims == []
    assert res.unverified_routing_claims == []
    assert res.unverified_api_claims == []
    assert res.speculative_phrases == []
    assert res.sycophancy_phrases == []


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


def test_stop_hook_allows_pure_discussion_with_illustrative_examples(tmp_path: Path) -> None:
    """Stop hook allows documentation/discussion turns with illustrative examples in backticks/code blocks."""
    t_doc = _write_transcript(
        tmp_path / "t_doc.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Giải thích các mẫu bị hook chặn"},
            {
                "type": "PLANNER_RESPONSE",
                "content": (
                    "Hook sẽ chặn các câu khẳng định thiếu bằng chứng như `tất cả test đã pass` "
                    "hoặc `4 link bị fallback về` nếu viết trực tiếp ngoài khối code.\n"
                    "```text\n"
                    "all tests pass\n"
                    "chắc là sẽ chạy\n"
                    "```\n"
                    "Đây là cơ chế bảo vệ thực chứng."
                ),
            },
        ],
    )
    payload_doc = {
        "conversationId": "conv-opt-doc",
        "transcriptPath": str(t_doc),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload_doc) == {"decision": "allow"}
