#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# noqa: debug-artifact-file
"""Antigravity 2.0 Lifecycle 'Stop' Hook — Runtime Enforcement for Anti-Hallucination Guard.

Reads the session transcript (JSONL) from the Stop hook input payload (`stdin`),
audits the latest planner response in the current turn via `harness.validators.hallucination_detector`,
and enforces empirical grounding before allowing the agent turn to stop:
- Separates `verification_logs` (real test/linter commands, canonical test pass output, or QA SubAgent
  wakeup evidence) from `api_logs` (raw HTTP status evidence) so benign commands like `git status`
  cannot spoof test completion claims (`VULN-02`).
- Enables `check_paths=True` by default (`--no-check-paths` to disable) (`VULN-03`).
- If clean or circuit breaker reached (`max_retries = 2`): outputs `{"decision": "allow"}`.
- If violations detected (missing paths, speculative language, sycophancy, unverified completion/API claims):
  outputs `{"decision": "continue", "reason": "[ANTI-HALLUCINATION-GUARD] ..."}`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.validators.hallucination_detector import audit_response  # noqa: E402

GUARD_MARKER = "[ANTI-HALLUCINATION-GUARD]"
OTHER_HOOK_MARKERS = (
    GUARD_MARKER,
    "[PRE-HANDOFF-GATE]",
    "[TRIAD-PROCESS-GATE]",
    "[AUTONOMOUS SKILL & TRIAD ROUTER]",
    "[ESCALATED_HARD_STOP]",
)
DEFAULT_MAX_RETRIES = 2

MUTATION_TOOL_NAMES = {
    "write_file",
    "edit_file",
    "replace_file_content",
    "multi_replace_file_content",
    "write_to_file",
    "create_file",
    "patch_file",
    "apply_patch",
}

REPO_CODE_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".sql", ".sh", ".ps1",
}

EXEMPT_MUTATION_SEGMENTS = (
    "brain/",
    "/.brain/",
    "wiki/",
    "memory/",
    "_session-handoff",
    "_open-questions",
)

COMMAND_TOOL_NAMES = {
    "run_command",
    "bash",
    "execute_command",
    "shell",
    "run_terminal_cmd",
    "cmd",
}

NON_COMMAND_TOOL_NAMES = {
    "write_file",
    "edit_file",
    "replace_file_content",
    "multi_replace_file_content",
    "write_to_file",
    "create_file",
    "patch_file",
    "apply_patch",
    "read_file",
    "view_file",
    "list_dir",
    "find_by_name",
    "grep_search",
    "search_web",
    "ask_question",
    "send_message",
    "invoke_subagent",
    "manage_subagents",
    "manage_task",
    "schedule",
}

VERIFICATION_CMD_RE = re.compile(
    r"(?:^|[;&|]\s*|\s|[\\/\"'])"
    r"(?:pytest|py\.test|unittest|npm\s+(?:run\s+)?test|pnpm\s+(?:run\s+)?test|"
    r"yarn\s+test|vitest|jest|ruff|mypy|py_compile|compileall|tsc|biome|eslint|"
    r"flake8|cargo\s+test|go\s+test|harness_doctor\.py|run_pytest_windows\.py|"
    r"run_verification\.py|clean_state_check\.py)\b",
    re.IGNORECASE,
)

BENIGN_NON_TEST_CMD_RE = re.compile(
    r"^\s*(?:git\s+(?:status|diff|log|branch|show|rev-parse|ls-files)|"
    r"ls|dir|Get-ChildItem|rg|grep|findstr|cat|type|Get-Content|pwd|echo|Write-Output|whoami)\b",
    re.IGNORECASE,
)

CANONICAL_TEST_PASS_RE = re.compile(
    r"(?:\b[1-9]\d*\s+passed\b|\bRan\s+\d+\s+tests?\s+in\s+[\d\.]+s[\s\S]*?\bOK\b)",
    re.IGNORECASE,
)

SUBAGENT_EXIT_ZERO_RE = re.compile(
    r"(?:exited\s+with\s+code\s+0\b|\bexit[\s_-]*code\s*(?:[:=]|==)?\s*0\b|\breturncode\s*(?:[:=]|==)\s*0\b)",
    re.IGNORECASE,
)

NON_ZERO_EXIT_RE = re.compile(
    r"(?:Command exited with code|exit\s*code\s*[:=]|returncode\s*[:=])\s*([1-9]\d*|-\d+)",
    re.IGNORECASE,
)


def _clean_arg_val(val: Any) -> str:
    """Unwrap plain strings and double-encoded JSON string arguments safely."""
    if val is None:
        return ""
    if isinstance(val, (int, float, bool)):
        return str(val)
    if not isinstance(val, str):
        try:
            return json.dumps(val, ensure_ascii=False)
        except Exception:
            return str(val)
    s = val.strip()
    for _ in range(2):
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            try:
                decoded = json.loads(s)
                if isinstance(decoded, str):
                    s = decoded.strip()
                    continue
            except Exception:
                pass
        break
    return s


def _parse_args_dict(raw_args: Any) -> dict[str, Any]:
    cur = raw_args
    for _ in range(2):
        if isinstance(cur, dict):
            return cur
        if isinstance(cur, str) and cur.strip():
            try:
                cur = json.loads(cur)
                continue
            except Exception:
                break
        break
    return cur if isinstance(cur, dict) else {}


def parse_transcript(transcript_path: Path | str) -> list[dict[str, Any]]:
    """Parse transcript.jsonl into a list of step dictionaries."""
    path = Path(transcript_path)
    if not path.is_file():
        return []

    steps: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        steps.append(data)
                except Exception:
                    continue
    except Exception:
        return []
    return steps


def _is_genuine_user_step(step: dict[str, Any]) -> bool:
    """Return True if step represents a genuine user prompt rather than a hook retry injection."""
    if step.get("ephemeral"):
        return False
    step_type = str(step.get("type") or "")
    source = str(step.get("source") or "")
    content = str(step.get("content") or "")
    reason = str(step.get("reason") or "")
    message = str(step.get("message") or "")
    ephemeral_msg = str(step.get("ephemeralMessage") or "")
    combined = f"{content}\n{reason}\n{message}\n{ephemeral_msg}"

    if any(marker in combined for marker in OTHER_HOOK_MARKERS):
        return False
    if source == "SYSTEM" or step_type in ("SYSTEM_MESSAGE", "EPHEMERAL_MESSAGE"):
        return False
    return step_type == "USER_INPUT" or source == "USER_EXPLICIT"


def _qualifies_for_verification_log(
    tc_name: str,
    cmd_str: str,
    output_text: str,
    explicit_exit_code: int | None,
) -> bool:
    """Return True only when a tool execution genuinely represents test/linter verification."""
    if explicit_exit_code is not None and explicit_exit_code != 0:
        return False
    if explicit_exit_code is None and NON_ZERO_EXIT_RE.search(output_text or ""):
        return False

    norm_tool = tc_name.rsplit(":", 1)[-1].strip() if tc_name else ""

    if cmd_str:
        if BENIGN_NON_TEST_CMD_RE.search(cmd_str) and not VERIFICATION_CMD_RE.search(cmd_str):
            return False
        if VERIFICATION_CMD_RE.search(cmd_str):
            return True
        return bool(CANONICAL_TEST_PASS_RE.search(output_text or ""))

    if norm_tool in NON_COMMAND_TOOL_NAMES:
        return False

    return bool(CANONICAL_TEST_PASS_RE.search(output_text or ""))


def extract_turn_context_detailed(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract current turn steps, retry count, latest planner response, verification logs, and API logs."""
    last_user_idx = -1
    for idx, step in enumerate(steps):
        if _is_genuine_user_step(step):
            last_user_idx = idx

    turn_steps = steps[last_user_idx + 1 :] if last_user_idx >= 0 else list(steps)

    retry_count = 0
    latest_response = ""
    verification_chunks: list[str] = []
    api_chunks: list[str] = []
    pending_tool_calls: list[tuple[str, str]] = []
    has_code_mutation = False
    calls_ask_question = False
    has_escalated_hard_stop = False

    for step in turn_steps:
        step_type = str(step.get("type") or "")
        source = str(step.get("source") or "")
        role = str(step.get("role") or "")
        content = str(step.get("content") or "")
        reason = str(step.get("reason") or "")
        message = str(step.get("message") or "")
        sys_inst = str(step.get("system_instruction") or "")

        combined_meta = f"{content}\n{reason}\n{message}\n{sys_inst}"
        if "[ESCALATED_HARD_STOP]" in combined_meta:
            has_escalated_hard_stop = True

        is_planner = step_type == "PLANNER_RESPONSE" or role in ("assistant", "model")

        if is_planner:
            if content.strip():
                latest_response = content

            tool_calls = step.get("tool_calls")
            calls_ask_question = False
            if isinstance(tool_calls, list) and tool_calls:
                pending_tool_calls = []
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fn_obj = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                    tc_name = _clean_arg_val(
                        tc.get("name") or tc.get("tool") or fn_obj.get("name") or ""
                    )
                    if tc_name.rsplit(":", 1)[-1].strip() == "ask_question":
                        calls_ask_question = True
                    tc_args = _parse_args_dict(
                        tc.get("args")
                        if "args" in tc
                        else tc.get("arguments")
                        if "arguments" in tc
                        else tc.get("input")
                        if "input" in tc
                        else tc.get("parameters")
                    )
                    cmd_str = _clean_arg_val(
                        tc_args.get("CommandLine")
                        or tc_args.get("command")
                        or tc_args.get("cmd")
                        or ""
                    )
                    if tc_name.rsplit(":", 1)[-1] in COMMAND_TOOL_NAMES or cmd_str:
                        pending_tool_calls.append((tc_name or "run_command", cmd_str))
                    elif tc_name:
                        pending_tool_calls.append((tc_name, ""))

                    norm_tc = tc_name.rsplit(":", 1)[-1].strip()
                    if norm_tc in MUTATION_TOOL_NAMES:
                        target_path = _clean_arg_val(
                            tc_args.get("Path") or tc_args.get("path") or tc_args.get("file_path") or tc_args.get("file") or ""
                        ).replace("\\", "/")
                        ext = Path(target_path).suffix.lower()
                        is_exempt = any(seg in target_path.lower() for seg in EXEMPT_MUTATION_SEGMENTS)
                        if ext in REPO_CODE_EXTENSIONS and not is_exempt:
                            has_code_mutation = True

            tool_responses = step.get("tool_responses")
            if isinstance(tool_responses, list):
                for idx_r, tr in enumerate(tool_responses):
                    if not isinstance(tr, dict):
                        continue
                    tc_name, cmd_str = (
                        pending_tool_calls[idx_r] if idx_r < len(pending_tool_calls) else ("", "")
                    )
                    cmd_str = _clean_arg_val(
                        tr.get("command") or tr.get("CommandLine") or cmd_str
                    )
                    tr_out = str(tr.get("content") or tr.get("output") or "").strip()
                    tr_ec = tr.get("exit_code") if "exit_code" in tr else tr.get("returncode")
                    explicit_ec = (
                        int(tr_ec)
                        if isinstance(tr_ec, int) and not isinstance(tr_ec, bool)
                        else None
                    )
                    if cmd_str:
                        api_chunks.append(cmd_str)
                    if tr_out:
                        api_chunks.append(tr_out)
                    if explicit_ec == 0:
                        api_chunks.append("Command exited with code 0")
                    if _qualifies_for_verification_log(tc_name, cmd_str, tr_out, explicit_ec):
                        if tr_out:
                            verification_chunks.append(tr_out)
                        if explicit_ec == 0:
                            verification_chunks.append("Command exited with code 0")
                pending_tool_calls = []
            continue

        combined_meta = f"{content}\n{reason}\n{message}"
        if GUARD_MARKER in combined_meta:
            retry_count += 1
            continue

        if any(m in combined_meta for m in OTHER_HOOK_MARKERS):
            continue

        # SubAgent Reactive Wakeup or system messages
        if step_type == "SYSTEM_MESSAGE" or source == "SYSTEM":
            if content.strip():
                api_chunks.append(content.strip())
                if (
                    "[Message]" in content
                    and re.search(r"\b(?:pytest|unittest)\b", content, re.IGNORECASE)
                    and (
                        CANONICAL_TEST_PASS_RE.search(content)
                        or SUBAGENT_EXIT_ZERO_RE.search(content)
                    )
                ):
                    verification_chunks.append(content.strip())
                    verification_chunks.append("Command exited with code 0")
            continue

        if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
            continue

        # Tool / command result steps
        tool_results = step.get("tool_results")
        if isinstance(tool_results, list):
            for idx_r, tr in enumerate(tool_results):
                if not isinstance(tr, dict):
                    continue
                tc_name, cmd_str = (
                    pending_tool_calls[idx_r] if idx_r < len(pending_tool_calls) else ("", "")
                )
                cmd_str = _clean_arg_val(tr.get("command") or tr.get("CommandLine") or cmd_str)
                tr_out = str(tr.get("content") or tr.get("output") or "").strip()
                tr_ec = tr.get("exit_code") if "exit_code" in tr else tr.get("returncode")
                explicit_ec = (
                    int(tr_ec) if isinstance(tr_ec, int) and not isinstance(tr_ec, bool) else None
                )
                if cmd_str:
                    api_chunks.append(cmd_str)
                if tr_out:
                    api_chunks.append(tr_out)
                if explicit_ec == 0:
                    api_chunks.append("Command exited with code 0")
                if _qualifies_for_verification_log(tc_name, cmd_str, tr_out, explicit_ec):
                    if tr_out:
                        verification_chunks.append(tr_out)
                    if explicit_ec == 0:
                        verification_chunks.append("Command exited with code 0")
            pending_tool_calls = []
            continue

        tc_name, cmd_str = pending_tool_calls.pop(0) if pending_tool_calls else ("", "")
        step_cmd = _clean_arg_val(step.get("command") or step.get("CommandLine") or "")
        if step_cmd:
            cmd_str = step_cmd

        step_chunks: list[str] = []
        for field_name in ("content", "output", "stdout", "stderr", "response", "result"):
            val = step.get(field_name)
            if isinstance(val, str) and val.strip():
                step_chunks.append(val.strip())

        step_text = "\n".join(step_chunks)
        raw_ec = step.get("exit_code") if "exit_code" in step else step.get("returncode")
        explicit_ec = (
            int(raw_ec) if isinstance(raw_ec, int) and not isinstance(raw_ec, bool) else None
        )

        if cmd_str:
            api_chunks.append(cmd_str)
        if step_text:
            api_chunks.append(step_text)
        if explicit_ec == 0:
            api_chunks.append("Command exited with code 0")

        status_code = step.get("status_code") or step.get("http_status")
        if isinstance(status_code, int) and 100 <= status_code <= 599:
            api_chunks.append(f"HTTP {status_code}")

        if _qualifies_for_verification_log(tc_name, cmd_str, step_text, explicit_ec):
            if step_text:
                verification_chunks.append(step_text)
            if explicit_ec == 0:
                verification_chunks.append("Command exited with code 0")

        step_tool_name = _clean_arg_val(step.get("tool_name") or step.get("name") or step.get("tool") or "").rsplit(":", 1)[-1].strip()
        if step_tool_name in MUTATION_TOOL_NAMES:
            tc_args = _parse_args_dict(step.get("args") or step.get("arguments") or step.get("input") or step.get("parameters") or {})
            target_path = _clean_arg_val(
                tc_args.get("Path") or tc_args.get("path") or tc_args.get("file_path") or tc_args.get("file") or step.get("path") or ""
            ).replace("\\", "/")
            ext = Path(target_path).suffix.lower()
            is_exempt = any(seg in target_path.lower() for seg in EXEMPT_MUTATION_SEGMENTS)
            if ext in REPO_CODE_EXTENSIONS and not is_exempt:
                has_code_mutation = True

    verification_logs = "\n".join(verification_chunks) if verification_chunks else None
    api_logs = "\n".join(api_chunks) if api_chunks else None

    return {
        "turn_steps": turn_steps,
        "retry_count": retry_count,
        "latest_response": latest_response,
        "execution_logs": verification_logs,
        "verification_logs": verification_logs,
        "api_logs": api_logs,
        "has_code_mutation": has_code_mutation,
        "calls_ask_question": calls_ask_question,
        "has_escalated_hard_stop": has_escalated_hard_stop,
    }


def extract_turn_context(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Backward-compatible wrapper returning turn context with isolated verification & API logs."""
    return extract_turn_context_detailed(steps)


def evaluate_transcript(
    transcript_path: Path | str,
    *,
    base_dir: Path | str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    execution_num: int = 0,
    termination_reason: str = "",
    check_paths: bool = True,
) -> dict[str, str]:
    """Evaluate a transcript JSONL file and return the Stop hook decision payload."""
    if termination_reason and termination_reason != "NO_TOOL_CALL":
        return {"decision": "allow"}

    if execution_num >= max_retries + 1:
        return {"decision": "allow"}

    steps = parse_transcript(transcript_path)
    if not steps:
        return {"decision": "allow"}

    ctx = extract_turn_context_detailed(steps)

    if ctx.get("calls_ask_question"):
        return {"decision": "allow"}

    if ctx.get("has_escalated_hard_stop"):
        return {"decision": "allow"}

    if execution_num > max_retries or ctx["retry_count"] >= max_retries:
        return {
            "decision": "continue",
            "reason": (
                f"[ESCALATED_HARD_STOP] Cầu dao ngắt mạch đã kích hoạt sau {max_retries} lần cảnh báo "
                "không sửa được vi phạm thực chứng. Khóa toàn bộ quyền tự trị. "
                "Yêu cầu Quản đốc xuất trình báo cáo vi phạm trực tiếp cho Sếp."
            ),
            "system_instruction": (
                f"[ESCALATED_HARD_STOP] Cầu dao ngắt mạch đã kích hoạt sau {max_retries} lần cảnh báo "
                "không sửa được vi phạm thực chứng. Khóa toàn bộ quyền tự trị. "
                "Yêu cầu Quản đốc xuất trình báo cáo vi phạm trực tiếp cho Sếp."
            ),
        }

    latest_response = ctx["latest_response"]
    if not latest_response or not latest_response.strip():
        return {"decision": "allow"}

    resolved_base_dir = Path(base_dir).resolve() if base_dir else REPO_ROOT
    audit_res = audit_response(
        latest_response,
        base_dir=resolved_base_dir,
        execution_logs=ctx["verification_logs"],
        check_paths=check_paths,
        api_execution_logs=ctx["api_logs"],
        turn_steps=ctx["turn_steps"],
        has_code_mutation=ctx.get("has_code_mutation", False),
    )

    if audit_res.verdict == "REJECT":
        if getattr(audit_res, "has_mutation_without_test", False):
            return {
                "decision": "continue",
                "reason": (
                    f"{GUARD_MARKER} Phát hiện thao tác sửa/ghi mã nguồn repository nhưng không có lệnh kiểm thử "
                    "(pytest / linter với exit code == 0) đi kèm (Tool-Mutation Balance Violation). "
                    "Yêu cầu chạy test kiểm chứng thực tế trước khi hoàn tất turn!"
                ),
            }
        if getattr(audit_res, "unverified_routing_claims", None):
            claims_repr = ", ".join(f"'{c}'" for c in audit_res.unverified_routing_claims[:3])
            return {
                "decision": "continue",
                "reason": (
                    f"{GUARD_MARKER} Tuyên bố chuyển hướng/routing hoặc lỗi hệ thống ({claims_repr}) "
                    "nhưng không có raw HTTP probe evidence từ CLI (Cosmetic Triad Ban). "
                    "Yêu cầu chạy curl hoặc Invoke-WebRequest để lấy HTTP status thực tế hoặc đính kèm khối `### [EVIDENCE TUPLE]` "
                    "(Target URL, Probe Command, Raw Status Code) trước khi kết luận!"
                ),
            }
        violations_str = "; ".join(audit_res.violations)
        return {
            "decision": "continue",
            "reason": (
                f"{GUARD_MARKER} Phát hiện vi phạm thực chứng: {violations_str}. "
                "Yêu cầu sửa lại câu trả lời kèm bằng chứng thực tế."
            ),
        }

    return {"decision": "allow"}


def evaluate_hook_payload(
    payload: dict[str, Any],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    check_paths: bool = True,
) -> dict[str, str]:
    """Evaluate an Antigravity Stop hook JSON payload dictionary."""
    if not isinstance(payload, dict):
        return {"decision": "allow"}

    if payload.get("fullyIdle") is False:
        return {"decision": "allow"}

    termination_reason = str(payload.get("terminationReason") or "").strip()
    if termination_reason and termination_reason != "NO_TOOL_CALL":
        return {"decision": "allow"}

    try:
        execution_num = int(payload.get("executionNum") or 0)
    except (TypeError, ValueError):
        execution_num = 0

    if execution_num >= max_retries + 1:
        return {"decision": "allow"}

    transcript_path = payload.get("transcriptPath")
    if not transcript_path or not isinstance(transcript_path, str):
        return {"decision": "allow"}

    base_dir: Path | None = None
    workspace_paths = payload.get("workspacePaths")
    if isinstance(workspace_paths, list) and workspace_paths:
        first_ws = Path(str(workspace_paths[0]))
        if first_ws.is_dir():
            base_dir = first_ws

    return evaluate_transcript(
        transcript_path,
        base_dir=base_dir,
        max_retries=max_retries,
        execution_num=execution_num,
        termination_reason=termination_reason,
        check_paths=check_paths,
    )


def main() -> None:
    """CLI and Antigravity Stop Hook entry point."""
    result: dict[str, str] = {"decision": "allow"}
    try:
        parser = argparse.ArgumentParser(
            description="Enforce Anti-Hallucination Guard on Stop Hook"
        )
        parser.add_argument("--transcript", "-t", type=str, help="Direct path to transcript.jsonl")
        parser.add_argument("--base-dir", type=str, default="", help="Base workspace directory")
        parser.add_argument(
            "--max-retries",
            type=int,
            default=DEFAULT_MAX_RETRIES,
            help="Circuit breaker max retries",
        )
        parser.add_argument(
            "--check-paths",
            dest="check_paths",
            action="store_true",
            default=True,
            help="Enable strict file path existence checks (default: enabled)",
        )
        parser.add_argument(
            "--no-check-paths",
            dest="check_paths",
            action="store_false",
            help="Disable strict file path existence checks",
        )
        args, _ = parser.parse_known_args()

        if args.transcript:
            result = evaluate_transcript(
                args.transcript,
                base_dir=args.base_dir or None,
                max_retries=args.max_retries,
                check_paths=args.check_paths,
            )
        elif not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input and raw_input.strip():
                payload = json.loads(raw_input)
                if isinstance(payload, dict):
                    result = evaluate_hook_payload(
                        payload,
                        max_retries=args.max_retries,
                        check_paths=args.check_paths,
                    )
    except Exception:
        # Failsafe: never break the Antigravity agent lifecycle
        result = {"decision": "allow"}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
