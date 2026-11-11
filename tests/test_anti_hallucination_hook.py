"""Unit & integration tests for scripts/enforce_anti_hallucination_hook.py and AppWorkflowStore runtime enforcement."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError
from scripts.enforce_anti_hallucination_hook import (
    GUARD_MARKER,
    evaluate_hook_payload,
    evaluate_transcript,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPO_ROOT / "scripts" / "enforce_anti_hallucination_hook.py"


def _write_transcript(path: Path, steps: list[dict[str, Any]]) -> Path:
    lines = [json.dumps(s, ensure_ascii=False) for s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run_hook_cli(payload: dict[str, Any]) -> dict[str, Any]:
    res = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, f"Hook exited with {res.returncode}: {res.stderr}"
    return json.loads(res.stdout.strip())


def test_hooks_json_registers_anti_hallucination_hook() -> None:
    """Verify both .agent/hooks.json and .agents/hooks.json register enforce_anti_hallucination_hook.py."""
    for rel_path in (".agent/hooks.json", ".agents/hooks.json"):
        hooks_path = REPO_ROOT / rel_path
        assert hooks_path.is_file(), f"Missing {rel_path}"
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
        stop_hooks = data.get("auto-code-harvester", {}).get("Stop", [])
        commands = [h.get("command", "") for h in stop_hooks if isinstance(h, dict)]
        assert any("scripts/enforce_anti_hallucination_hook.py" in cmd for cmd in commands), (
            f"scripts/enforce_anti_hallucination_hook.py not registered in {rel_path}"
        )


def test_clean_response_allows_stop(tmp_path: Path) -> None:
    """Clean response without violations returns {'decision': 'allow'}."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Cập nhật cấu hình hệ thống"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã cập nhật cấu hình theo đúng yêu cầu kỹ thuật của Sếp.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-clean",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_speculative_language_triggers_continue(tmp_path: Path) -> None:
    """Speculative language ('chắc là sẽ chạy') returns {'decision': 'continue', 'reason': ...}."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra tính năng"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đoạn code mới này chắc là sẽ chạy ổn định.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-speculative",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res_fn = evaluate_hook_payload(payload)
    assert res_fn["decision"] == "continue"
    assert GUARD_MARKER in res_fn["reason"]
    assert "chắc là" in res_fn["reason"]

    res_cli = _run_hook_cli(payload)
    assert res_cli["decision"] == "continue"
    assert GUARD_MARKER in res_cli["reason"]


def test_sycophancy_triggers_continue(tmp_path: Path) -> None:
    """Sycophancy ('giả thuyết của anh hoàn toàn đúng') returns {'decision': 'continue', 'reason': ...}."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Có phải lỗi do race condition không?"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Giả thuyết của anh hoàn toàn đúng, nguyên nhân chính là do race condition.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-sycophancy",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
    }
    res_fn = evaluate_hook_payload(payload)
    assert res_fn["decision"] == "continue"
    assert GUARD_MARKER in res_fn["reason"]
    assert "Sycophancy" in res_fn["reason"]

    res_cli = _run_hook_cli(payload)
    assert res_cli["decision"] == "continue"
    assert "Sycophancy" in res_cli["reason"]


def test_unverified_completion_claim_triggers_continue(tmp_path: Path) -> None:
    """Unverified completion claim ('tất cả test đã pass' without execution log) returns {'decision': 'continue'}."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Chạy kiểm thử module"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Báo cáo Sếp: tất cả test đã pass hoàn toàn.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-unverified",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
    }
    res_fn = evaluate_hook_payload(payload)
    assert res_fn["decision"] == "continue"
    assert GUARD_MARKER in res_fn["reason"]
    assert "exit code 0" in res_fn["reason"]

    res_cli = _run_hook_cli(payload)
    assert res_cli["decision"] == "continue"
    assert "exit code 0" in res_cli["reason"]


def test_verified_completion_claim_allows_stop(tmp_path: Path) -> None:
    """Verified completion claim ('tất cả test đã pass' with Command exited with code 0) returns {'decision': 'allow'}."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Chạy kiểm thử module"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest -q"}}],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "Command exited with code 0.\n15 passed in 0.42s",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Báo cáo Sếp: tất cả test đã pass với 15 test cases.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-verified",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
    }
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_circuit_breaker_allows_stop_after_two_retries(tmp_path: Path) -> None:
    """When 2 [ANTI-HALLUCINATION-GUARD] system messages already exist after the last USER_INPUT, returns allow."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra tính năng"},
            {"type": "PLANNER_RESPONSE", "content": "Đoạn này chắc là sẽ chạy."},
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"{GUARD_MARKER} Phát hiện vi phạm thực chứng lần 1.",
            },
            {"type": "PLANNER_RESPONSE", "content": "Đoạn này vẫn chắc là sẽ chạy."},
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"{GUARD_MARKER} Phát hiện vi phạm thực chứng lần 2.",
            },
            {"type": "PLANNER_RESPONSE", "content": "Đoạn này chắc là sẽ chạy lần 3."},
        ],
    )
    payload = {
        "conversationId": "conv-cb",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
    }
    res_t = evaluate_transcript(transcript)
    assert res_t["decision"] == "continue"
    assert "[ESCALATED_HARD_STOP]" in res_t["reason"]

    res_p = evaluate_hook_payload(payload)
    assert res_p["decision"] == "continue"
    assert "[ESCALATED_HARD_STOP]" in res_p["reason"]

    res_cli = _run_hook_cli(payload)
    assert res_cli["decision"] == "continue"
    assert "[ESCALATED_HARD_STOP]" in res_cli["reason"]


def test_app_workflow_handoff_anti_hallucination_enforcement(tmp_path: Path) -> None:
    """Verify AppWorkflowStore enforces hallucination_detector on implementation, code review, and QA audit."""
    project = tmp_path / "app"
    project.mkdir()
    (project / "main.py").write_text("print('ok')\n", encoding="utf-8")

    store = AppWorkflowStore(tmp_path / "brain")
    store.create("task-ahg", "Verify anti-hallucination gate in workflow", project)

    spec = {
        "scope": "backend service",
        "design": "modular python",
        "contracts": "cli output",
        "acceptance_criteria": [{"id": "AC1", "description": "run script", "ui": False}],
        "risks": "none",
        "verification_commands": [
            {
                "id": "CMD1",
                "argv": [sys.executable, "-c", "print('ok')"],
                "cwd": ".",
                "ac_ids": ["AC1"],
            }
        ],
        "evidence_root": str(tmp_path),
    }

    s = store.submit_spec("task-ahg", spec, "architect-1")
    store.review_design("task-ahg", "APPROVE", "reviewer-1", s["spec_sha256"], "Design verified")
    store.sign_off("task-ahg", s["spec_sha256"], "Duyệt")

    # 1. Speculative implementation report is rejected
    with pytest.raises(WorkflowError, match="Anti-Hallucination Guard rejected implementation report"):
        store.submit_implementation("task-ahg", "builder-1", "Code này chắc là sẽ chạy tốt")

    # 2. Clean implementation report succeeds and records hallucination_audit receipt
    state = store.submit_implementation("task-ahg", "builder-1", "Đã triển khai đầy đủ module main.py")
    assert state["hallucination_audit"]["verdict"] == "APPROVE"
    assert state["hallucination_audit"]["score"] == 1.0

    # 3. Sycophantic code review approval is rejected
    with pytest.raises(WorkflowError, match="Anti-Hallucination Guard rejected code review report"):
        store.review_code(
            "task-ahg",
            "APPROVE",
            "critic-1",
            state["spec_sha256"],
            state["manifest_sha256"],
            "Giả thuyết của anh hoàn toàn đúng, code chuẩn. AC1 mapped to test_assertion.",
        )

    # 4. Clean code review succeeds
    state = store.review_code(
        "task-ahg",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "Đã đối soát AST và contracts đầy đủ. AC1 mapped to test_assertion.",
    )
    assert state["code_review"]["hallucination_audit"]["verdict"] == "APPROVE"


def test_benign_git_status_does_not_spoof_test_completion_claim(tmp_path: Path) -> None:
    """VULN-02 regression: `git status` exit code 0 must not count as test execution evidence."""
    transcript = _write_transcript(
        tmp_path / "t_git_spoof.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Chạy toàn bộ pytest"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "Command exited with code 0.\nOn branch main\nnothing to commit",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Báo cáo Sếp: Tất cả test đã pass 100%!",
            },
        ],
    )
    payload = {
        "conversationId": "conv-vuln02-reg",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res = _run_hook_cli(payload)
    assert res["decision"] == "continue"
    assert GUARD_MARKER in res["reason"]


def test_qa_subagent_wakeup_message_satisfies_completion_claim(tmp_path: Path) -> None:
    """Root Orchestrator reporting green pytest after QA SubAgent wakeup evidence is allowed."""
    transcript = _write_transcript(
        tmp_path / "t_qa_wakeup.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm thử hệ thống"},
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": "[Message] sender=qa-sub-01 content=QA_VERDICT: PASS | pytest: 42 passed in 0.8s (exit_code=0)",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Báo cáo Sếp: Tất cả test đã pass sau vòng kiểm định của QA Auditor.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-qa-wakeup",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_default_check_paths_blocks_phantom_paths_and_no_check_paths_flag_disables(
    tmp_path: Path,
) -> None:
    """VULN-03 regression: check_paths=True is enabled by default; --no-check-paths disables it."""
    transcript = _write_transcript(
        tmp_path / "t_phantom_path.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Báo cáo file vừa tạo"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Em đã cập nhật file `harness/nonexistent_phantom_module_xyz.py`.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-vuln03-reg",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res_default = _run_hook_cli(payload)
    assert res_default["decision"] == "continue"
    assert "nonexistent_phantom_module_xyz.py" in res_default["reason"]

    res_disabled = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), "--no-check-paths"],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert res_disabled.returncode == 0
    assert json.loads(res_disabled.stdout.strip()) == {"decision": "allow"}


def test_routing_claim_without_http_probe_triggers_continue(tmp_path: Path) -> None:
    """Routing claim ('4 link bị fallback về trang chủ') without HTTP probe command returns continue."""
    transcript = _write_transcript(
        tmp_path / "t_routing_unverified.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra 4 link chuyển hướng"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Báo cáo: 4 link bị fallback về trang chủ.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-routing-unverified",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res_fn = evaluate_hook_payload(payload)
    assert res_fn["decision"] == "continue"
    assert GUARD_MARKER in res_fn["reason"]
    assert "chuyển hướng/routing" in res_fn["reason"]

    res_cli = _run_hook_cli(payload)
    assert res_cli["decision"] == "continue"
    assert "chuyển hướng/routing" in res_cli["reason"]


def test_routing_claim_with_http_probe_allows_stop(tmp_path: Path) -> None:
    """Routing claim ('4 link bị fallback về trang chủ') with prior curl probe returns allow."""
    transcript = _write_transcript(
        tmp_path / "t_routing_verified.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra 4 link chuyển hướng"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "curl -I https://example.com/link1"},
                    }
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "HTTP/1.1 301 Moved Permanently\nLocation: https://example.com/\nCommand exited with code 0",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Báo cáo: 4 link bị fallback về trang chủ.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-routing-verified",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_static_tasks_with_no_negative_claims_pass_cleanly(tmp_path: Path) -> None:
    """Static tasks discussing routing or navigation without negative failure claims return allow (Zero False Positives)."""
    transcript = _write_transcript(
        tmp_path / "t_static_routing.jsonl",
        [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Cập nhật tài liệu điều hướng và routing cho hệ thống",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": (
                    "Đã hoàn thành cập nhật tài liệu kiến trúc. "
                    "Hệ thống định tuyến cho phép chuyển hướng sang module dashboard khi người dùng đăng nhập thành công. "
                    "Chúng ta chuyển hướng sang bước kiểm tra các cấu hình static tiếp theo."
                ),
            },
        ],
    )
    payload = {
        "conversationId": "conv-static-routing",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_routing_claim_with_lean_evidence_tuple_allows_stop(tmp_path: Path) -> None:
    """Negative routing claim with embedded Lean Evidence Tuple returns allow."""
    transcript = _write_transcript(
        tmp_path / "t_evidence_tuple.jsonl",
        [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Kiểm tra endpoint API và chuyển hướng",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": (
                    "Báo cáo: Endpoint này bị redirect về trang chủ và không truy cập được.\n\n"
                    "### [EVIDENCE TUPLE]\n"
                    "- Target URL: https://example.com/api/v1/auth\n"
                    "- Probe Command: `curl -I https://example.com/api/v1/auth`\n"
                    "- Raw Status Code: HTTP 302 Found\n"
                ),
            },
        ],
    )
    payload = {
        "conversationId": "conv-evidence-tuple",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_routing_claim_with_table_evidence_tuple_allows_stop(tmp_path: Path) -> None:
    """Negative routing claim with table-formatted Lean Evidence Tuple returns allow."""
    transcript = _write_transcript(
        tmp_path / "t_evidence_table_tuple.jsonl",
        [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Kiểm tra endpoint bị lỗi 404",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": (
                    "Phát hiện lỗi 404 và không truy cập được trang quản trị.\n\n"
                    "### [EVIDENCE TUPLE]\n"
                    "| Target URL | Probe Command | Raw Status Code |\n"
                    "| :--- | :--- | :--- |\n"
                    "| https://example.com/admin | `Invoke-WebRequest -Uri https://example.com/admin` | HTTP 404 Not Found |\n"
                ),
            },
        ],
    )
    payload = {
        "conversationId": "conv-table-evidence-tuple",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(REPO_ROOT)],
        "terminationReason": "NO_TOOL_CALL",
    }
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}
