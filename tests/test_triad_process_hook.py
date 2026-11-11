# -*- coding: utf-8 -*-
"""Comprehensive unit and CLI tests for scripts/enforce_triad_process_hook.py (VULN-01A, VULN-01B)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from scripts.enforce_triad_process_hook import (
    GUARD_MARKER,
    _clean_arg_val,
    classify_subagent_role,
    evaluate_hook_payload,
    evaluate_transcript,
    is_exempt_orchestrator_path,
    is_subagent_session,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPO_ROOT / "scripts" / "enforce_triad_process_hook.py"


def _write_transcript(path: Path, steps: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(s, ensure_ascii=False) for s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run_hook_cli(payload: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        cwd=str(REPO_ROOT),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert proc.returncode == 0, f"Hook exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout.strip())


def test_hooks_json_registers_triad_process_hook_at_stop_3() -> None:
    """Verify Stop[0] remains auto_harvest_global.py and Stop[3] registers enforce_triad_process_hook.py."""
    for rel in (".agent/hooks.json", ".agents/hooks.json"):
        cfg_path = REPO_ROOT / rel
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        stop_list = data["auto-code-harvester"]["Stop"]
        assert len(stop_list) >= 4
        assert "scripts/auto_harvest_global.py" in stop_list[0]["command"]
        assert "scripts/enforce_triad_process_hook.py" in stop_list[3]["command"]
        assert stop_list[3]["timeout"] == 30


def test_clean_arg_val_unwraps_double_encoded_json_strings() -> None:
    """Verify _clean_arg_val handles both double-encoded Antigravity JSONL args and plain strings."""
    assert _clean_arg_val('"kill_all"') == "kill_all"
    assert _clean_arg_val("kill_all") == "kill_all"
    assert _clean_arg_val('"d:\\\\repo\\\\service.py"') == "d:\\repo\\service.py"
    assert _clean_arg_val("d:\\repo\\service.py") == "d:\\repo\\service.py"
    assert _clean_arg_val(None) == ""


def test_subagent_session_exemptions_allow_direct_builder_mutations(tmp_path: Path) -> None:
    """SubAgent sessions (Builder/Creator/QA) must be allowed to edit repo files directly."""
    target_py = tmp_path / "service.py"

    # 1. Payload parentConversationId
    t_plain = _write_transcript(
        tmp_path / "t_sub_payload.jsonl",
        [
            {"type": "USER_INPUT", "content": "Implement service.py"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "write_file", "args": {"Path": str(target_py)}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Created file."},
            {"type": "PLANNER_RESPONSE", "content": "Done implementing service.py."},
        ],
    )
    assert evaluate_hook_payload(
        {
            "transcriptPath": str(t_plain),
            "parentConversationId": "root-conv-001",
            "terminationReason": "NO_TOOL_CALL",
        }
    ) == {"decision": "allow"}

    # 2. First step is SYSTEM_MESSAGE with [Message] and sender= (real Antigravity SubAgent startup)
    t_sys_msg = _write_transcript(
        tmp_path / "t_sub_sysmsg.jsonl",
        [
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": "[Message] timestamp=2026-11-09T04:00:00Z sender=0a22b30b content=Build module",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "edit_file", "args": {"Path": str(target_py)}}],
            },
            {"type": "PLANNER_RESPONSE", "content": "Completed build."},
        ],
    )
    assert is_subagent_session(
        [{"type": "SYSTEM_MESSAGE", "content": "[Message] sender=abc"}], {}
    )
    assert _run_hook_cli(
        {"transcriptPath": str(t_sys_msg), "terminationReason": "NO_TOOL_CALL"}
    ) == {"decision": "allow"}

    # 3. Initial USER_INPUT contains # FIXED PREFIX:
    t_prefix = _write_transcript(
        tmp_path / "t_sub_prefix.jsonl",
        [
            {
                "type": "USER_INPUT",
                "content": "# FIXED PREFIX: SYSTEM INVARIANTS & ROLE SPECIFICATION\nYou are the **Builder**.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "edit_file", "args": {"Path": str(target_py)}}],
            },
            {"type": "PLANNER_RESPONSE", "content": "Completed."},
        ],
    )
    assert _run_hook_cli(
        {"transcriptPath": str(t_prefix), "terminationReason": "NO_TOOL_CALL"}
    ) == {"decision": "allow"}


def test_exempt_orchestrator_paths_allowed_without_subagent(tmp_path: Path) -> None:
    """Root Orchestrator may write artifacts in brain/, Obsidian wiki/memory, and .brain/."""
    art_dir = tmp_path / "art_brain"
    payload = {"artifactDirectoryPath": str(art_dir)}
    assert is_exempt_orchestrator_path(str(art_dir / "implementation_plan.md"), payload)
    assert is_exempt_orchestrator_path(
        str(Path.home() / ".gemini" / "antigravity" / "brain" / "conv-1" / "plan.md"), payload
    )
    assert is_exempt_orchestrator_path(str(Path.home() / "Obsidian" / "wiki" / "index.md"), payload)
    assert is_exempt_orchestrator_path(".brain/app_workflows/task-1.json", payload)
    assert is_exempt_orchestrator_path("_session-handoff.md", payload)
    assert is_exempt_orchestrator_path("MEMORY.md", payload)
    assert not is_exempt_orchestrator_path(str(tmp_path / "src" / "pricing.py"), payload)

    t_exempt = _write_transcript(
        tmp_path / "t_exempt.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Lập kế hoạch triển khai"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "write_file",
                        "args": {"Path": str(art_dir / "implementation_plan.md")},
                    }
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Created plan."},
            {"type": "PLANNER_RESPONSE", "content": "Em gửi Sếp bản kế hoạch triển khai."},
        ],
    )
    assert _run_hook_cli(
        {
            "transcriptPath": str(t_exempt),
            "artifactDirectoryPath": str(art_dir),
            "terminationReason": "NO_TOOL_CALL",
        }
    ) == {"decision": "allow"}


def test_check_1_blocks_root_direct_code_mutation_without_subagent(tmp_path: Path) -> None:
    """VULN-01A: Root session mutating project file with 0 invoke_subagent calls is blocked."""
    t_path = _write_transcript(
        tmp_path / "t_direct_edit.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Sửa lỗi hàm tính giá"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "edit_file",
                        "args": {"Path": json.dumps(str(tmp_path / "pricing.py"))},
                    }
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Updated pricing.py"},
            {"type": "PLANNER_RESPONSE", "content": "Em đã sửa xong pricing.py."},
        ],
    )
    res = _run_hook_cli({"transcriptPath": str(t_path), "terminationReason": "NO_TOOL_CALL"})
    assert res["decision"] == "continue"
    assert GUARD_MARKER in res["reason"]
    assert "pricing.py" in res["reason"]


def test_reactive_wakeup_and_ask_question_exemptions(tmp_path: Path) -> None:
    """Orchestrator stopping turn to await Reactive Wakeup or ask_question must receive allow."""
    # 1. Spawn acknowledgement without wakeup message yet -> awaiting_wakeup == True -> allow
    t_wakeup = _write_transcript(
        tmp_path / "t_wakeup.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Xây dựng API mới"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {"TypeName": "self", "Role": "Builder", "Prompt": "Build API"},
                    }
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": (
                    "Created the following subagent: id=conv-sub-1. "
                    "It will send you a message when it has completed."
                ),
            },
            {"type": "PLANNER_RESPONSE", "content": ""},
        ],
    )
    assert _run_hook_cli(
        {"transcriptPath": str(t_wakeup), "terminationReason": "NO_TOOL_CALL"}
    ) == {"decision": "allow"}

    # 2. fullyIdle is False -> allow immediately
    assert evaluate_hook_payload(
        {"transcriptPath": str(t_wakeup), "fullyIdle": False, "terminationReason": "NO_TOOL_CALL"}
    ) == {"decision": "allow"}

    # 3. Last PLANNER_RESPONSE calls ask_question -> allow even after Architect/Builder or before kill_all
    t_ask = _write_transcript(
        tmp_path / "t_ask.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Thiết kế hệ thống"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "ask_question",
                        "args": {"questions": [{"question": "Sếp duyệt phương án nào?", "options": ["A", "B"]}]},
                    }
                ],
            },
        ],
    )
    assert _run_hook_cli(
        {"transcriptPath": str(t_ask), "terminationReason": "NO_TOOL_CALL"}
    ) == {"decision": "allow"}


def test_check_2_blocks_partial_app_triad_and_boilerplate_prompt_spoofing(tmp_path: Path) -> None:
    """Builder prompt mentioning Critic/QA in # FIXED PREFIX: must NOT spoof Critic/QA roles."""
    boiler_prompt = (
        "# FIXED PREFIX: Dynamic Triad Protocol (Maker -> Code Critic -> QA Auditor)\n"
        "You are the **Builder SubAgent**.\n"
        "# VARIABLE TASK BRIEF:\nImplement payment.py"
    )
    role_info = classify_subagent_role(
        {"TypeName": '"self"', "Role": '"Builder SubAgent"', "Prompt": json.dumps(boiler_prompt)}
    )
    assert role_info["is_app_maker"] is True
    assert role_info["is_exec_critic"] is False
    assert role_info["is_qa"] is False

    t_partial = _write_transcript(
        tmp_path / "t_partial.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Xây dựng thanh toán"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "TypeName": '"self"',
                            "Role": '"Builder SubAgent"',
                            "Prompt": json.dumps(boiler_prompt),
                        },
                    }
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "Created the following subagent: conv-b1. It will send you a message when it has completed.",
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": "[Message] sender=conv-b1 content=READY_FOR_CRITIC",
            },
            {"type": "PLANNER_RESPONSE", "content": "Em bàn giao luôn cho Sếp."},
        ],
    )
    res = _run_hook_cli({"transcriptPath": str(t_partial), "terminationReason": "NO_TOOL_CALL"})
    assert res["decision"] == "continue"
    assert "Code Critic" in res["reason"]
    assert "QA Auditor" in res["reason"]
    assert "kill_all" in res["reason"]


def test_check_2_allows_complete_tier1_tier2_and_marketing_triads_with_kill_all(
    tmp_path: Path,
) -> None:
    """Complete Tier-1 App Triad, Tier-2 Fast-Track, and Marketing Triad pass once kill_all runs."""
    # 1. Complete Tier-1 App Triad + double-encoded kill_all
    t_tier1 = _write_transcript(
        tmp_path / "t_tier1_ok.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Xây dựng module order"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Builder completed."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Code Critic"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Critic approved."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "QA Auditor"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "QA passed."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã hoàn tất chu trình Triad và giải phóng SubAgent.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": '"kill_all"'}}],
            },
        ],
    )
    assert _run_hook_cli({"transcriptPath": str(t_tier1), "terminationReason": "NO_TOOL_CALL"}) == {
        "decision": "allow"
    }

    # 2. Explicit Tier-2 Hotfix Fast-Track (Builder + QA Auditor + kill_all)
    t_tier2 = _write_transcript(
        tmp_path / "t_tier2_ok.jsonl",
        [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Thực hiện Tier 2 fast-track hotfix cho lỗi typo nhỏ",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Builder"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Builder done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "QA Auditor"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "QA done."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Hoàn tất hotfix.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    assert _run_hook_cli({"transcriptPath": str(t_tier2), "terminationReason": "NO_TOOL_CALL"}) == {
        "decision": "allow"
    }

    # 3. Marketing Triad: Creator without Researcher/Critic is blocked; full Triad + kill_all passes
    t_mkt_bad = _write_transcript(
        tmp_path / "t_mkt_bad.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Viết kịch bản YouTube mới"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Scriptwriter Creator"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Draft completed."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Em gửi kịch bản.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    res_mkt_bad = _run_hook_cli({"transcriptPath": str(t_mkt_bad), "terminationReason": "NO_TOOL_CALL"})
    assert res_mkt_bad["decision"] == "continue"
    assert "Web Researcher" in res_mkt_bad["reason"]
    assert "Compliance Critic" in res_mkt_bad["reason"]

    t_mkt_ok = _write_transcript(
        tmp_path / "t_mkt_ok.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Viết kịch bản YouTube mới"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "research", "Role": "Web Researcher"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Dossier ready."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Scriptwriter Creator"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Draft ready."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "invoke_subagent", "args": {"TypeName": "self", "Role": "Compliance Critic"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Approved."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Bàn giao kịch bản.",
                "tool_calls": [{"name": "manage_subagents", "args": {"Action": "kill_all"}}],
            },
        ],
    )
    assert _run_hook_cli({"transcriptPath": str(t_mkt_ok), "terminationReason": "NO_TOOL_CALL"}) == {
        "decision": "allow"
    }


def test_circuit_breaker_allows_after_two_retries(tmp_path: Path) -> None:
    """Circuit breaker allows stop once [TRIAD-PROCESS-GATE] has fired twice in the same turn."""
    t_cb = _write_transcript(
        tmp_path / "t_cb.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Sửa nhanh file"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "edit_file", "args": {"Path": str(tmp_path / "mod.py")}}],
            },
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": f"{GUARD_MARKER} Retry 1"},
            {"type": "PLANNER_RESPONSE", "content": "Thử lại 1"},
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": f"{GUARD_MARKER} Retry 2"},
            {"type": "PLANNER_RESPONSE", "content": "Thử lại 2"},
        ],
    )
    res_t = evaluate_transcript(t_cb)
    assert res_t["decision"] == "continue"
    assert "[ESCALATED_HARD_STOP]" in res_t["reason"]

    res_cli = _run_hook_cli({"transcriptPath": str(t_cb), "terminationReason": "NO_TOOL_CALL"})
    assert res_cli["decision"] == "continue"
    assert "[ESCALATED_HARD_STOP]" in res_cli["reason"]
