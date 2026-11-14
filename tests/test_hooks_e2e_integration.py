"""E2E Stop Hook Chaining & Integration Tests (Spec Revision 1 - Mục 3.2).

Kiểm thử toàn diện chu trình 4 Stop Hooks tuần tự:
- Stop[0]: scripts/auto_harvest_global.py (Harvest & Memory Ingestion)
- Stop[1]: scripts/enforce_anti_hallucination_hook.py (8 trụ cột rào chắn thực chứng)
- Stop[2]: scripts/verify_before_handoff_hook.py (Pre-Handoff Verification, CleanState D1/D4 & VULN-04)
- Stop[3]: scripts/enforce_triad_process_hook.py (Dynamic Triad Invariant, Rule 1.6, Rule 1.11, Rule 1.17)

Bao gồm 13 test cases (TC-INT-01 đến TC-INT-12 gồm TC-INT-04a và TC-INT-04b):
- TC-INT-01: Full Clean Turn Execution (kèm Model: "flash" theo Rule 1.11)
- TC-INT-02: Stop 1 Rejection Cascading
- TC-INT-03: Stop 1 Pass -> Stop 2 Catches Test Fail
- TC-INT-04a: Stop 2 Catches CleanState D4 Residue (print debug)
- TC-INT-04b: Stop 2 Catches CleanState D1 Syntax Error
- TC-INT-05: Stop 1, 2 Pass -> Stop 3 Catches Triad Violation (Orchestrator direct edit)
- TC-INT-06: Stop 3 Catches Incomplete Triad (Missing Critic/QA)
- TC-INT-07: Stop 3 Catches Missing kill_all (SubAgent Orphan)
- TC-INT-08: Fast-Track / Tier 2 Exemption (Builder -> QA -> kill_all)
- TC-INT-09: Global Circuit Breaker Exhaustion
- TC-INT-10: Reactive Wakeup & Non-Idle Preservation (fullyIdle: false)
- TC-INT-11: Malformed JSON & Failsafe-to-Allow
- TC-INT-12: VULN-04 Targeted Pytest Auto-Discovery Gate
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from scripts.enforce_anti_hallucination_hook import (
    GUARD_MARKER as AH_GUARD_MARKER,
    evaluate_hook_payload as evaluate_stop1,
)
from scripts.verify_before_handoff_hook import (
    GATE_MARKER as HANDOFF_GATE_MARKER,
    evaluate_hook_payload as evaluate_stop2,
)
from scripts.enforce_triad_process_hook import (
    GUARD_MARKER as TRIAD_GUARD_MARKER,
    evaluate_hook_payload as evaluate_stop3,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_0_HARVEST = REPO_ROOT / "scripts" / "auto_harvest_global.py"
HOOK_1_AH = REPO_ROOT / "scripts" / "enforce_anti_hallucination_hook.py"
HOOK_2_HANDOFF = REPO_ROOT / "scripts" / "verify_before_handoff_hook.py"
HOOK_3_TRIAD = REPO_ROOT / "scripts" / "enforce_triad_process_hook.py"


def _write_transcript(path: Path, steps: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(s, ensure_ascii=False) for s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run_single_hook_cli(hook_script: Path, payload: dict[str, Any] | None = None, raw_stdin: str | None = None) -> dict[str, Any]:
    stdin_content = raw_stdin if raw_stdin is not None else (json.dumps(payload, ensure_ascii=False) if payload else "{}")
    proc = subprocess.run(
        [sys.executable, str(hook_script)],
        input=stdin_content,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=25,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"Hook {hook_script.name} exited with {proc.returncode}: {proc.stderr}"
    out_raw = proc.stdout.strip()
    return json.loads(out_raw) if out_raw else {}


def _run_pipeline(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Chạy tuần tự 4 Stop hooks: Stop[0] -> Stop[1] -> Stop[2] -> Stop[3]."""
    r0 = _run_single_hook_cli(HOOK_0_HARVEST, payload)
    r1 = _run_single_hook_cli(HOOK_1_AH, payload)
    if r1.get("decision") in ("continue", "block"):
        return r1, [r0, r1]

    r2 = _run_single_hook_cli(HOOK_2_HANDOFF, payload)
    if r2.get("decision") in ("continue", "block"):
        return r2, [r0, r1, r2]

    r3 = _run_single_hook_cli(HOOK_3_TRIAD, payload)
    if r3.get("decision") in ("continue", "block"):
        return r3, [r0, r1, r2, r3]

    return {"decision": "allow"}, [r0, r1, r2, r3]


# TC-INT-01: Full Clean Turn Execution (kèm Rule 1.11)
def test_tc_int_01_full_clean_turn_execution(tmp_path: Path):
    """Turn sạch: Không file ảo, có pytest pass thật, Critic dùng Model='inherit', QA dùng Model='flash', đọc đủ report_path, kill_all."""
    critic_report = tmp_path / "critic_report.md"
    critic_report.write_text(
        "\n".join(f"- Critic finding line {i}: OK" for i in range(1, 27)) + "\n",
        encoding="utf-8",
    )
    qa_report = tmp_path / "qa_report.md"
    qa_report.write_text(
        "\n".join(f"- QA test result line {i}: PASS" for i in range(1, 27)) + "\n",
        encoding="utf-8",
    )

    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Triển khai tính năng mới"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Kích hoạt Maker triển khai mã nguồn.",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {"Role": "Builder", "TypeName": "app", "Prompt": "Triển khai mã nguồn"},
                    }
                ],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": "[Message] sender=sub-builder-1 content=Builder đã hoàn thành viết mã nguồn.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Kích hoạt Code Critic thẩm định.",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "Role": "Code Critic",
                            "TypeName": "app",
                            "Model": "inherit",  # Rule 1.11 Explicit Model Tiering
                            "Prompt": "Kiểm tra mã nguồn",
                        },
                    }
                ],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": (
                    "[Message] sender=sub-critic-1 content=Code Critic: APPROVE không có vi phạm GAP. "
                    f"report_path: {critic_report}"
                ),
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Kích hoạt QA Auditor nghiệm thu.",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "Role": "QA Auditor",
                            "TypeName": "app",
                            "Model": "flash",  # Rule 1.11 Explicit Model Tiering
                            "Prompt": f"Chạy test suite nghiệm thu (tham chiếu {critic_report})",
                        },
                    }
                ],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": (
                    "[Message] sender=sub-qa-1 content=QA Auditor: 100% tests pass, verdict PASS. "
                    f"report_path: {qa_report}"
                ),
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đọc đầy đủ báo cáo từ Critic và QA trước khi dọn dẹp.",
                "tool_calls": [
                    {"name": "read_file", "args": {"Path": str(critic_report)}},
                    {"name": "read_file", "args": {"Path": str(qa_report)}},
                ],
            },
            {
                "type": "TOOL_RESULT",
                "tool_name": "read_file",
                "content": "Read report contents.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Dọn dẹp subagents.",
                "tool_calls": [
                    {
                        "name": "manage_subagents",
                        "args": {"Action": "kill_all"},
                    }
                ],
            },
            {
                "type": "TOOL_RESULT",
                "tool_name": "manage_subagents",
                "content": "Successfully killed all subagents.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã hoàn thành toàn bộ chu trình Dynamic Triad, mã nguồn sạch và đạt chất lượng.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-01",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
    }
    decision, results = _run_pipeline(payload)
    assert decision == {"decision": "allow"}
    assert len(results) == 4
    assert results[1] == {"decision": "allow"}
    assert results[2] == {"decision": "allow"}
    assert results[3] == {"decision": "allow"}


# TC-INT-02: Stop 1 Rejection Cascading
def test_tc_int_02_stop_1_rejection_cascading(tmp_path: Path):
    """Turn chứa từ ngữ võ đoán 'chắc là sẽ chạy' -> Stop 1 chặn ngay lập tức."""
    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra hệ thống"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đoạn code mới này chắc là sẽ chạy mượt mà không cần test lại.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-02",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
    }
    decision, results = _run_pipeline(payload)
    assert decision["decision"] == "continue"
    assert AH_GUARD_MARKER in decision["reason"]
    # Bị chặn ngay tại Stop 1, Stop 2 & 3 không được phép bypass
    assert len(results) == 2


# TC-INT-03: Stop 1 Pass -> Stop 2 Catches Test Fail
def test_tc_int_03_stop_1_pass_stop_2_catches_test_fail(tmp_path: Path):
    """Turn văn phong sạch, nhưng lệnh pytest trước đó bị exit code 1 chưa fix."""
    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Chạy bài test"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Chạy pytest kiểm thử",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "pytest tests/test_core.py"},
                    }
                ],
            },
            {
                "type": "TOOL_RESULT",
                "tool_name": "run_command",
                "exit_code": 1,
                "output": "FAILED tests/test_core.py::test_init - AssertionError",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Kết quả chạy kiểm thử cho thấy có một số module cần xem xét lại.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-03",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
    }
    decision, results = _run_pipeline(payload)
    assert decision["decision"] == "continue"
    assert HANDOFF_GATE_MARKER in decision["reason"]
    assert len(results) == 3
    assert results[1] == {"decision": "allow"}
    assert results[2]["decision"] == "continue"


# TC-INT-04a: Stop 2 Catches CleanState D4 Residue
def test_tc_int_04a_stop_2_catches_cleanstate_d4_residue(tmp_path: Path):
    """Turn sạch, test pass, nhưng để lại print('DEBUG test') trong file code sửa."""
    proj = tmp_path / "app_d4"
    proj.mkdir()
    svc_file = proj / "service.py"
    svc_file.write_text("def run():\n    print('DEBUG test: starting')\n    return 42\n", encoding="utf-8")

    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Sửa service.py"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Cập nhật service.py",
                "tool_calls": [
                    {
                        "name": "write_file",
                        "args": {"Path": str(svc_file)},
                    }
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "write_file", "content": "File updated."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Chạy pytest kiểm tra",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"CommandLine": "pytest -q"},
                    }
                ],
            },
            {
                "type": "TOOL_RESULT",
                "tool_name": "run_command",
                "exit_code": 0,
                "output": "1 passed in 0.01s",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã cập nhật service.py theo đúng chuẩn kiến trúc.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-04a",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(proj)],
    }
    r1 = evaluate_stop1(payload)
    r2 = evaluate_stop2(payload)
    assert r1 == {"decision": "allow"}
    assert r2["decision"] == "continue"
    assert "CleanStateVerifier" in r2["reason"] or HANDOFF_GATE_MARKER in r2["reason"]


# TC-INT-04b: Stop 2 Catches CleanState D1 Syntax Error
def test_tc_int_04b_stop_2_catches_cleanstate_d1_syntax_error(tmp_path: Path):
    """Turn sửa file code Python bị lỗi cú pháp cố ý (def broken_syntax(:)."""
    proj = tmp_path / "app_d1"
    proj.mkdir()
    broken_file = proj / "broken.py"
    broken_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")

    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Tạo module broken.py"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Tạo module broken.py",
                "tool_calls": [
                    {
                        "name": "write_file",
                        "args": {"Path": str(broken_file)},
                    }
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "write_file", "content": "File created."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã hoàn thành tạo tệp mã nguồn theo yêu cầu.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-04b",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(proj)],
    }
    r1 = evaluate_stop1(payload)
    r2 = evaluate_stop2(payload)
    assert r1 == {"decision": "allow"}
    assert r2["decision"] == "continue"
    assert "cú pháp" in r2["reason"] or "SyntaxError" in r2["reason"] or "CleanStateVerifier" in r2["reason"]


# TC-INT-05: Stop 1, 2 Pass -> Stop 3 Catches Triad Violation
def test_tc_int_05_stop_3_catches_triad_violation(tmp_path: Path):
    """Turn sửa code thật nhưng Orchestrator tự sửa trực tiếp bằng edit_file mà không invoke SubAgent."""
    proj = tmp_path / "app_triad"
    proj.mkdir()
    svc_file = proj / "core.py"
    svc_file.write_text("def core(): pass\n", encoding="utf-8")

    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Sửa core.py"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Chỉnh sửa trực tiếp file core.py",
                "tool_calls": [
                    {
                        "name": "edit_file",
                        "args": {"Path": str(svc_file), "Target": "pass", "Replacement": "return 1"},
                    }
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "edit_file", "content": "1 replacement made."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã cập nhật core.py thành công.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-05",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(proj)],
    }
    decision, results = _run_pipeline(payload)
    assert decision["decision"] == "continue"
    assert TRIAD_GUARD_MARKER in decision["reason"]
    assert "Quy tắc 1.6" in decision["reason"]
    assert len(results) == 4
    assert results[1] == {"decision": "allow"}
    assert results[3]["decision"] == "continue"


# TC-INT-06: Stop 3 Catches Incomplete Triad
def test_tc_int_06_stop_3_catches_incomplete_triad(tmp_path: Path):
    """Turn gọi SubAgent Builder nhưng kết thúc mà thiếu Code Critic hoặc QA Auditor."""
    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Xây dựng tính năng"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Gọi Builder",
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {"Role": "Builder", "TypeName": "app", "Prompt": "Xây dựng code"},
                    }
                ],
            },
            {
                "type": "SYSTEM_MESSAGE",
                "source": "SYSTEM",
                "content": "[Message] sender=sub-1 content=Builder hoàn tất.",
            },
            {
                "type": "PLANNER_RESPONSE",
                "content": "Dọn dẹp",
                "tool_calls": [
                    {"name": "manage_subagents", "args": {"Action": "kill_all"}}
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "manage_subagents", "content": "Killed all."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã hoàn thành tính năng.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-06",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
    }
    decision, results = _run_pipeline(payload)
    assert decision["decision"] in ("continue", "block")
    assert TRIAD_GUARD_MARKER in decision["reason"]
    assert "Code Critic" in decision["reason"] or "QA Auditor" in decision["reason"]


# TC-INT-07: Stop 3 Catches Missing kill_all
def test_tc_int_07_stop_3_catches_missing_kill_all(tmp_path: Path):
    """Turn gọi đủ Builder -> Critic -> QA nhưng quên gọi manage_subagents(Action='kill_all')."""
    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Triển khai đầy đủ"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Gọi Builder",
                "tool_calls": [
                    {"name": "invoke_subagent", "args": {"Role": "Builder", "TypeName": "app", "Prompt": "Build"}}
                ],
            },
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": "[Message] sender=s1 content=done"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Gọi Critic",
                "tool_calls": [
                    {"name": "invoke_subagent", "args": {"Role": "Code Critic", "TypeName": "app", "Model": "inherit", "Prompt": "Review"}}
                ],
            },
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": "[Message] sender=s2 content=pass"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Gọi QA",
                "tool_calls": [
                    {"name": "invoke_subagent", "args": {"Role": "QA Auditor", "TypeName": "app", "Model": "flash", "Prompt": "QA"}}
                ],
            },
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": "[Message] sender=s3 content=pass"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã hoàn tất toàn bộ quy trình mà quên kill_all.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-07",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
    }
    decision, results = _run_pipeline(payload)
    assert decision["decision"] in ("continue", "block")
    assert "kill_all" in decision["reason"] or "1.17" in decision["reason"]


# TC-INT-08: Fast-Track / Tier 2 Exemption
def test_tc_int_08_fast_track_tier2_exemption(tmp_path: Path):
    """Turn có từ khóa 'hotfix tier 2', gọi Builder -> QA Auditor -> đọc report_path -> kill_all (bỏ qua Critic)."""
    qa_report = tmp_path / "qa_tier2_report.md"
    qa_report.write_text(
        "\n".join(f"- Tier 2 QA check line {i}: PASS" for i in range(1, 27)) + "\n",
        encoding="utf-8",
    )

    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Xử lý hotfix nhỏ tier 2"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Kích hoạt fast-track tier 2 Maker",
                "tool_calls": [
                    {"name": "invoke_subagent", "args": {"Role": "Builder", "TypeName": "app", "Prompt": "Hotfix"}}
                ],
            },
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": "[Message] sender=s1 content=Builder done"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Kích hoạt QA fast-track",
                "tool_calls": [
                    {"name": "invoke_subagent", "args": {"Role": "QA Auditor", "TypeName": "app", "Model": "flash", "Prompt": "Verify"}}
                ],
            },
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": f"[Message] sender=s2 content=QA pass report_path: {qa_report}"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đọc báo cáo QA trước khi dọn dẹp",
                "tool_calls": [
                    {"name": "read_file", "args": {"Path": str(qa_report)}}
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "read_file", "content": "Read QA report."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Dọn dẹp subagents",
                "tool_calls": [
                    {"name": "manage_subagents", "args": {"Action": "kill_all"}}
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "manage_subagents", "content": "Killed all."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Hoàn thành xử lý hotfix tier 2 hợp lệ.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-08",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
    }
    decision, results = _run_pipeline(payload)
    assert decision == {"decision": "allow"}
    assert len(results) == 4
    assert results[3] == {"decision": "allow"}


# TC-INT-09: Global Circuit Breaker Exhaustion
def test_tc_int_09_global_circuit_breaker_exhaustion(tmp_path: Path):
    """Transcript ghi nhận retry_count >= 2 hoặc executionNum > 2 -> toàn bộ 4 hooks allow."""
    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Kiểm tra"},
            {"type": "PLANNER_RESPONSE", "content": "Lần 1 chắc là sẽ chạy."},
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": f"{AH_GUARD_MARKER} vi phạm 1"},
            {"type": "PLANNER_RESPONSE", "content": "Lần 2 chắc là sẽ chạy."},
            {"type": "SYSTEM_MESSAGE", "source": "SYSTEM", "content": f"{AH_GUARD_MARKER} vi phạm 2"},
            {"type": "PLANNER_RESPONSE", "content": "Lần 3 chắc là sẽ chạy."},
        ],
    )
    payload = {
        "conversationId": "conv-int-09",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
        "executionNum": 3,
    }
    decision, results = _run_pipeline(payload)
    assert decision == {"decision": "allow"}
    for r in results:
        assert r == {"decision": "allow"} or r == {}


# TC-INT-10: Reactive Wakeup & Non-Idle Preservation
def test_tc_int_10_reactive_wakeup_non_idle_preservation(tmp_path: Path):
    """Payload có fullyIdle: false -> toàn bộ 4 hooks trả về allow tức thì."""
    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Đang chạy task nền"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đoạn này chắc là sẽ chạy.",  # Có từ cấm nhưng fullyIdle=False
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-10",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(REPO_ROOT)],
        "fullyIdle": False,
    }
    decision, results = _run_pipeline(payload)
    assert decision == {"decision": "allow"}
    for r in results:
        assert r == {"decision": "allow"} or r == {}


# TC-INT-11: Malformed JSON & Failsafe-to-Allow
def test_tc_int_11_malformed_json_failsafe_to_allow():
    """Payload JSON đầu vào bị corrupt qua STDIN -> toàn bộ 4 hooks bắt exception, exit 0, trả về allow/{."""
    malformed_raw = "{'bad_json': unexpected end of file..."
    decision, results = _run_single_hook_cli(HOOK_0_HARVEST, raw_stdin=malformed_raw), []
    assert decision == {}

    r1 = _run_single_hook_cli(HOOK_1_AH, raw_stdin=malformed_raw)
    assert r1 == {"decision": "allow"}

    r2 = _run_single_hook_cli(HOOK_2_HANDOFF, raw_stdin=malformed_raw)
    assert r2 == {"decision": "allow"}

    r3 = _run_single_hook_cli(HOOK_3_TRIAD, raw_stdin=malformed_raw)
    assert r3 == {"decision": "allow"}


# TC-INT-12: VULN-04 Targeted Pytest Auto-Discovery Gate
def test_tc_int_12_vuln_04_targeted_pytest_auto_discovery_gate(tmp_path: Path):
    """Turn sửa code Python mà agent không chạy test; file test tương ứng bị fail -> Stop 2 tự động phát hiện và chặn."""
    proj = tmp_path / "proj_vuln04"
    proj.mkdir()
    (proj / "src").mkdir()
    (proj / "tests").mkdir()

    calc_file = proj / "src" / "calc.py"
    calc_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    test_file = proj / "tests" / "test_calc.py"
    test_file.write_text("def test_calc():\n    assert False, 'Cố ý gây lỗi kiểm thử'\n", encoding="utf-8")

    t_path = _write_transcript(
        tmp_path / "transcript.jsonl",
        [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Sửa calc.py"},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Sửa file calc.py",
                "tool_calls": [
                    {
                        "name": "write_file",
                        "args": {"Path": str(calc_file)},
                    }
                ],
            },
            {"type": "TOOL_RESULT", "tool_name": "write_file", "content": "File saved."},
            {
                "type": "PLANNER_RESPONSE",
                "content": "Đã cập nhật calc.py hoàn chỉnh.",
            },
        ],
    )
    payload = {
        "conversationId": "conv-int-12",
        "transcriptPath": str(t_path),
        "terminationReason": "NO_TOOL_CALL",
        "workspacePaths": [str(proj)],
    }

    r1 = evaluate_stop1(payload)
    r2 = evaluate_stop2(payload)

    assert r1 == {"decision": "allow"}
    assert r2["decision"] == "continue"
    assert HANDOFF_GATE_MARKER in r2["reason"]
    assert "test_calc.py" in r2["reason"] or "pytest" in r2["reason"].lower()
