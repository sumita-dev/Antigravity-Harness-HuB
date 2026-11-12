# -*- coding: utf-8 -*-
"""Real-world E2E test suite for the 3-layer Pre-Handoff Verification Gate.

Tests all 3 enforcement layers across 7 realistic scenarios:
- Layer 1: Antigravity 2.0 Stop Hook (`scripts/verify_before_handoff_hook.py` & `.agent[s]/hooks.json`)
- Layer 2: State-Machine Quality Gate (`AdversarialQualityGate` in `harness/quality_gate.py`)
- Layer 3: Checkpoint & Clean-State Gate (`AppWorkflowStore` + `ExecutionEvidenceStore` + `CleanStateVerifier`)
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.state_machine import HarnessState, TaskContext
from scripts.verify_before_handoff_hook import (
    GATE_MARKER,
    evaluate_hook_payload,
    evaluate_transcript,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPO_ROOT / "scripts" / "verify_before_handoff_hook.py"


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
    assert res.returncode == 0, f"Hook CLI failed ({res.returncode}): {res.stderr}"
    return json.loads(res.stdout.strip())


def test_hooks_json_registers_pre_handoff_verification_hook() -> None:
    """Both .agent/hooks.json and .agents/hooks.json must register verify_before_handoff_hook.py under Stop."""
    for rel_path in (".agent/hooks.json", ".agents/hooks.json"):
        hooks_path = REPO_ROOT / rel_path
        assert hooks_path.is_file(), f"Missing {rel_path}"
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
        stop_hooks = data.get("auto-code-harvester", {}).get("Stop", [])
        commands = [h.get("command", "") for h in stop_hooks if isinstance(h, dict)]
        assert any("scripts/verify_before_handoff_hook.py" in cmd for cmd in commands), (
            f"scripts/verify_before_handoff_hook.py not registered in {rel_path}"
        )


def test_scenario_1_hook_blocks_unresolved_test_failure_in_transcript(tmp_path: Path) -> None:
    """Scenario 1: Agent runs pytest, gets exit code 1 (1 failed), and tries to hand off without re-running."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Sửa hàm tính thuế và kiểm thử giúp anh.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "pytest tests/test_tax.py -q"},
                    }
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": (
                    "Command exited with code 1.\n"
                    "=== FAILURES ===\n"
                    "E   AssertionError: assert 110 == 100\n"
                    "1 failed in 0.18s"
                ),
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Em đã cập nhật xong module tính thuế và bàn giao cho Sếp.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-scenario-1",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(tmp_path)],
        "terminationReason": "NO_TOOL_CALL",
    }

    res_fn = evaluate_hook_payload(payload)
    assert res_fn["decision"] == "continue"
    assert GATE_MARKER in res_fn["reason"]
    assert "exit code == 0" in res_fn["reason"]

    res_cli = _run_hook_cli(payload)
    assert res_cli["decision"] == "continue"
    assert GATE_MARKER in res_cli["reason"]


def test_scenario_2_hook_allows_after_red_green_fix_and_rerun(tmp_path: Path) -> None:
    """Scenario 2: Agent runs pytest (code 1), edits code to fix bug, re-runs pytest (code 0), and hands off."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    app_file = ws / "tax.py"
    app_file.write_text("def calc_tax(amount: float) -> float:\n    return round(amount * 0.1, 2)\n", encoding="utf-8")

    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {
                "type": "USER_INPUT",
                "source": "USER_EXPLICIT",
                "content": "Sửa hàm calc_tax và chạy pytest.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {"name": "run_command", "args": {"CommandLine": "pytest -q"}},
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "Command exited with code 1.\n1 failed in 0.12s",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {"name": "edit_file", "args": {"Path": str(app_file)}},
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "Made 1 replacement in tax.py.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {"name": "run_command", "args": {"CommandLine": "pytest -q"}},
                ],
            },
            {
                "type": "GENERIC",
                "status": "DONE",
                "content": "Command exited with code 0.\n4 passed in 0.10s",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã sửa lỗi và chạy lại pytest đạt 4 passed (exit code 0).",
            },
        ],
    )
    payload = {
        "conversationId": "conv-scenario-2",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(ws)],
        "terminationReason": "NO_TOOL_CALL",
    }

    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_scenario_3_hook_blocks_dirty_workspace_d1_and_d4(tmp_path: Path) -> None:
    """Scenario 3: Hook catches D1 syntax errors and D4 debug artifacts/stray .tmp files on code mutation."""
    ws = tmp_path / "dirty_ws"
    ws.mkdir()
    service_py = ws / "service.py"

    # 3a: Syntax Error (D1 fail)
    service_py.write_text("def broken_func(:\n    return 1\n", encoding="utf-8")
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Viết hàm service"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "write_file", "args": {"Path": str(service_py)}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Created file."},
            {"type": "PLANNER_RESPONSE", "content": "Đã viết xong service.py."},
        ],
    )
    payload = {
        "conversationId": "conv-scenario-3",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(ws)],
        "terminationReason": "NO_TOOL_CALL",
    }

    res_d1 = _run_hook_cli(payload)
    assert res_d1["decision"] == "continue"
    assert GATE_MARKER in res_d1["reason"]
    assert "Syntax error" in res_d1["reason"] or "CleanStateVerifier" in res_d1["reason"]

    # 3b: Fix syntax error, but leave breakpoint(), print("DEBUG..."), and a stray .tmp file (D4 fail)
    service_py.write_text(
        'def clean_syntax():\n    breakpoint()\n    print("DEBUG: internal state")\n    return 1\n',
        encoding="utf-8",
    )
    stray_tmp = ws / "leftover.tmp"
    stray_tmp.write_text("temp data", encoding="utf-8")

    res_d4 = _run_hook_cli(payload)
    assert res_d4["decision"] == "continue"
    assert GATE_MARKER in res_d4["reason"]
    assert any(k in res_d4["reason"] for k in ("breakpoint", "print_debug", "leftover.tmp"))

    # 3c: Clean up debug artifacts and stray .tmp file -> hook allows handoff
    service_py.write_text("def clean_syntax() -> int:\n    return 1\n", encoding="utf-8")
    stray_tmp.unlink()

    res_clean = _run_hook_cli(payload)
    assert res_clean == {"decision": "allow"}


def test_scenario_4_hook_executes_real_targeted_pytest_on_modified_test_file(tmp_path: Path) -> None:
    """Scenario 4: Hook spawns real pytest on modified test_*.py file, blocking when failing and allowing when passing."""
    ws = tmp_path / "pytest_ws"
    tests_dir = ws / "tests"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "test_math_logic.py"

    # Failing test file touched by write_file in the turn
    test_file.write_text(
        "def test_addition():\n    assert 2 + 2 == 5\n",
        encoding="utf-8",
    )

    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Thêm unit test cho phép cộng"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "write_file", "args": {"Path": "tests/test_math_logic.py"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Created file."},
            {"type": "PLANNER_RESPONSE", "content": "Đã tạo xong file test_math_logic.py."},
        ],
    )
    payload = {
        "conversationId": "conv-scenario-4",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(ws)],
        "terminationReason": "NO_TOOL_CALL",
    }

    res_fail = _run_hook_cli(payload)
    assert res_fail["decision"] == "continue"
    assert GATE_MARKER in res_fail["reason"]
    assert "test_math_logic.py" in res_fail["reason"]

    # Fix the test so it passes -> hook runs pytest and allows handoff
    test_file.write_text(
        "def test_addition():\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    res_pass = _run_hook_cli(payload)
    assert res_pass == {"decision": "allow"}


def test_scenario_5_hook_circuit_breaker_max_retries_two(tmp_path: Path) -> None:
    """Scenario 5: Circuit breaker allows stop after 2 [PRE-HANDOFF-GATE] retries in the same turn."""
    transcript = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Chạy kiểm thử"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest -q"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Command exited with code 1.\n1 failed"},
            {"type": "PLANNER_RESPONSE", "content": "Bàn giao lần 1."},
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"{GATE_MARKER} Phát hiện lệnh kiểm thử thất bại lần 1.",
            },
            {"type": "PLANNER_RESPONSE", "content": "Bàn giao lần 2."},
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": f"{GATE_MARKER} Phát hiện lệnh kiểm thử thất bại lần 2.",
            },
            {"type": "PLANNER_RESPONSE", "content": "Bàn giao lần 3."},
        ],
    )
    payload = {
        "conversationId": "conv-scenario-5",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(tmp_path)],
        "terminationReason": "NO_TOOL_CALL",
    }

    assert evaluate_transcript(transcript) == {"decision": "allow"}
    assert evaluate_hook_payload(payload) == {"decision": "allow"}
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_scenario_6_quality_gate_blocks_approval_when_latest_execute_failed() -> None:
    """Scenario 6: AdversarialQualityGate blocks VERDICT: APPROVE when latest EXECUTE step has exit_code != 0."""
    gate = AdversarialQualityGate(max_rounds=2, max_qa_rounds=2, max_total_cycles=3)
    context = TaskContext(task_id="task-scenario-6", branch="app")
    context.transition(HarnessState.INTAKE)
    context.transition(HarnessState.DESIGN)
    context.transition(HarnessState.IMPLEMENTATION)
    context.transition(HarnessState.AUDIT)

    # 1. Run failing command via evaluate_execution
    fail_cmd = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
    v_exec_fail = gate.evaluate_execution(context, fail_cmd)
    assert v_exec_fail == Verdict.REJECT
    assert context.state == HarnessState.IMPLEMENTATION

    exec_steps = [s for s in context.trace_steps if s["step"] == "EXECUTE"]
    assert len(exec_steps) == 1
    assert exec_steps[-1]["payload"]["exit_code"] == 1

    # 2. Attempt to approve via evaluate_audit without re-running execution -> deterministically rejected!
    context.transition(HarnessState.AUDIT)
    v_audit_blocked = gate.evaluate_audit(context, "All checks look fine. VERDICT: APPROVE")
    assert v_audit_blocked == Verdict.REJECT
    assert context.state == HarnessState.IMPLEMENTATION

    checker_steps = [s for s in context.trace_steps if s["step"] == "CHECKER"]
    assert "Rejected: latest EXECUTE step has non-zero exit_code" in checker_steps[-1]["payload"].get("reason", "")

    # 3. Re-run command and succeed (exit_code == 0)
    pass_cmd = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
    v_exec_pass = gate.evaluate_execution(context, pass_cmd)
    assert v_exec_pass == Verdict.APPROVE

    # 4. Subsequent evaluate_audit with VERDICT: APPROVE now succeeds
    v_audit_approved = gate.evaluate_audit(context, "Verified green test run. VERDICT: APPROVE")
    assert v_audit_approved == Verdict.APPROVE
    assert context.state == HarnessState.APPROVED


def test_scenario_7_app_workflow_store_full_pre_handoff_gate(tmp_path: Path) -> None:
    """Scenario 7: AppWorkflowStore blocks approval on missing receipt, tampered source, or dirty workspace, and approves when clean."""
    project = tmp_path / "sample_app"
    tests_dir = project / "tests"
    tests_dir.mkdir(parents=True)

    main_py = project / "main.py"
    test_py = tests_dir / "test_main.py"

    main_py.write_text("def greet(name: str) -> str:\n    return f'Hello, {name}!'\n", encoding="utf-8")
    test_py.write_text(
        "from main import greet\n\ndef test_greet():\n    assert greet('World') == 'Hello, World!'\n",
        encoding="utf-8",
    )

    evidence_file = tmp_path / "qa_evidence.log"
    evidence_file.write_text("pytest passed: 1 passed in 0.05s\n", encoding="utf-8")

    store = AppWorkflowStore(tmp_path / "brain" / "app_workflows")
    store.create("task-s7", "Build greeting module with full pre-handoff verification", project)

    spec = {
        "scope": "Greeting module",
        "design": "Pure function greet(name) with pytest suite",
        "contracts": "greet(str) -> str",
        "acceptance_criteria": [{"id": "AC1", "description": "Unit test passes", "ui": False}],
        "risks": "None",
        "verification_commands": [
            {
                "id": "CMD_PYTEST",
                "argv": [sys.executable, "-m", "pytest", "-q"],
                "cwd": ".",
                "ac_ids": ["AC1"],
            }
        ],
        "evidence_root": str(tmp_path),
    }

    s = store.submit_spec("task-s7", spec, "architect-1")
    store.review_design("task-s7", "APPROVE", "reviewer-1", s["spec_sha256"], "Architecture sound.")
    store.sign_off("task-s7", s["spec_sha256"], "Duyệt")

    # Builder leaves a stray .tmp debug file during implementation before submitting
    stray_file = project / "debug_dump.tmp"
    stray_file.write_text("temporary debug dump", encoding="utf-8")

    # Submit implementation while debug_dump.tmp exists
    state = store.submit_implementation("task-s7", "builder-1", "Đã hoàn thiện main.py và test_main.py.")
    state = store.review_code(
        "task-s7",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "Logic và cú pháp đạt yêu cầu. AC1 mapped to test_assertion.",
    )
    assert state["stage"] == "AUDIT"

    # (c) With stray_file present in project, CleanStateVerifier D4 automatically downgrades APPROVE -> REJECT!
    exec_res = store.execute("task-s7", "qa-1", "CMD_PYTEST")
    receipt_id_1 = exec_res["execution_receipt"]["receipt_id"]

    state_dirty = store.audit(
        "task-s7",
        "APPROVE",
        "qa-1",
        {
            "spec_sha256": state["spec_sha256"],
            "manifest_sha256": state["manifest_sha256"],
            "report": "QA chạy lệnh CMD_PYTEST.",
            "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id_1, "actor": "qa-1"}],
            "preview": {
                "checks": [{"id": "AC1", "status": "PASS", "evidence": str(evidence_file)}],
            },
        },
    )
    assert state_dirty["overall_verdict"] == "REJECT"
    assert state_dirty["stage"] == "IMPLEMENTATION"
    assert "CleanStateVerifier Rejected" in state_dirty["audit"]["report"]

    # Builder removes stray .tmp file and re-submits clean implementation
    stray_file.unlink()
    state = store.submit_implementation("task-s7", "builder-1", "Đã xóa file tạm debug_dump.tmp và làm sạch workspace.")
    state = store.review_code(
        "task-s7",
        "APPROVE",
        "critic-1",
        state["spec_sha256"],
        state["manifest_sha256"],
        "Workspace sạch và code đạt chuẩn. AC1 mapped to test_assertion.",
    )
    assert state["stage"] == "AUDIT"

    # (a) Verify missing/unexecuted receipt is blocked on clean workspace
    with pytest.raises(WorkflowError, match="Receipt must be recorded by workflow execute"):
        store.audit(
            "task-s7",
            "APPROVE",
            "qa-1",
            {
                "spec_sha256": state["spec_sha256"],
                "manifest_sha256": state["manifest_sha256"],
                "report": "Thử duyệt với receipt cũ không khớp manifest mới.",
                "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id_1, "actor": "qa-1"}],
                "preview": {
                    "checks": [{"id": "AC1", "status": "PASS", "evidence": str(evidence_file)}],
                },
            },
        )

    # (b) Verify tampering with source file after submit_implementation is blocked (manifest SHA256 mismatch)
    original_code = main_py.read_text(encoding="utf-8")
    main_py.write_text(original_code + "\n# unauthorized post-submission edit\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="Implementation changed since submission"):
        store.execute("task-s7", "qa-1", "CMD_PYTEST")

    # Restore exact source file
    main_py.write_text(original_code, encoding="utf-8")

    # (d) Full valid pre-handoff flow: QA runs signed command -> CleanState 5D passes -> APPROVED
    exec_res_2 = store.execute("task-s7", "qa-1", "CMD_PYTEST")
    receipt_id_2 = exec_res_2["execution_receipt"]["receipt_id"]
    assert exec_res_2["execution_receipt"]["exit_code"] == 0

    final_state = store.audit(
        "task-s7",
        "APPROVE",
        "qa-1",
        {
            "spec_sha256": state["spec_sha256"],
            "manifest_sha256": state["manifest_sha256"],
            "report": "Đã chạy kiểm thử thực tế CMD_PYTEST (exit code 0) và vượt qua 5 chiều CleanStateVerifier.",
            "commands": [{"id": "CMD_PYTEST", "receipt_id": receipt_id_2, "actor": "qa-1"}],
            "preview": {
                "checks": [{"id": "AC1", "status": "PASS", "evidence": str(evidence_file)}],
            },
        },
    )
    assert final_state["stage"] == "APPROVED"
    assert final_state["overall_verdict"] == "APPROVE"
    assert final_state["functional_status"] == "PASS"


def test_scenario_8_auto_discovers_and_runs_pytest_on_unverified_source_py_mutation(
    tmp_path: Path,
) -> None:
    """VULN-04 regression: Mutating pricing.py without running pytest auto-runs tests/test_pricing.py."""
    ws = tmp_path / "ws_source_mutation"
    tests_dir = ws / "tests"
    tests_dir.mkdir(parents=True)

    src_file = ws / "pricing.py"
    test_file = tests_dir / "test_pricing.py"
    src_file.write_text("def discount(x: float) -> float:\n    return x * 0.2\n", encoding="utf-8")
    test_file.write_text(
        "from pricing import discount\n\ndef test_discount():\n    assert discount(100) == 90\n",
        encoding="utf-8",
    )

    # Even if an earlier pytest passed BEFORE the breaking edit, mutating pricing.py afterward must re-verify!
    transcript = _write_transcript(
        tmp_path / "t_post_pytest_edit.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Sửa hàm discount"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest -q"}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Command exited with code 0.\n1 passed"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [{"name": "edit_file", "args": {"Path": str(src_file)}}],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Updated pricing.py"},
            {"type": "PLANNER_RESPONSE", "content": "Đã cập nhật pricing.py."},
        ],
    )
    payload = {
        "conversationId": "conv-scenario-8",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(ws)],
        "terminationReason": "NO_TOOL_CALL",
    }

    res_broken = _run_hook_cli(payload)
    assert res_broken["decision"] == "continue"
    assert GATE_MARKER in res_broken["reason"]
    assert "test_pricing.py" in res_broken["reason"]

    # Fix source code so test_pricing.py passes -> hook allows handoff
    src_file.write_text("def discount(x: float) -> float:\n    return x * 0.9\n", encoding="utf-8")
    assert _run_hook_cli(payload) == {"decision": "allow"}


def test_scenario_9_exempt_paths_do_not_trigger_verification_or_queue_tests(
    tmp_path: Path,
) -> None:
    """Mutating brain, obsidian, wiki, memory, or scratch paths does NOT count as code mutation."""
    from scripts.verify_before_handoff_hook import extract_turn_context, parse_transcript

    ws = tmp_path / "ws_exempt"
    ws.mkdir(parents=True)
    brain_file = "C:/Users/User/.gemini/antigravity/brain/conv123/scratch/helper.py"
    wiki_file = "D:/vault/wiki/_session-handoff.md"
    mem_file = "D:/vault/memory/memory.md"

    transcript = _write_transcript(
        tmp_path / "t_exempt.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Cập nhật tài liệu và bộ nhớ"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "",
                "tool_calls": [
                    {"name": "write_file", "args": {"Path": brain_file, "Content": "x = 1"}},
                    {"name": "edit_file", "args": {"Path": wiki_file, "Content": "notes"}},
                    {"name": "write_file", "args": {"Path": mem_file, "Content": "facts"}},
                ],
            },
            {"type": "GENERIC", "status": "DONE", "content": "Updated files"},
            {"type": "PLANNER_RESPONSE", "content": "Đã cập nhật memory và wiki."},
        ],
    )
    steps = parse_transcript(transcript)
    ctx = extract_turn_context(steps)
    assert ctx["has_code_mutation"] is False
    assert ctx["mutated_files"] == []
    assert ctx["modified_source_py_files"] == []

    payload = {
        "conversationId": "conv-scenario-9",
        "transcriptPath": str(transcript),
        "workspacePaths": [str(ws)],
        "terminationReason": "NO_TOOL_CALL",
    }
    res = _run_hook_cli(payload)
    assert res == {"decision": "allow"}
