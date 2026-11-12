#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# noqa: debug-artifact-file
"""Antigravity 2.0 Lifecycle 'Stop' Hook — Pre-Handoff Verification Gate.

Thực thi cơ chế kiểm thử bắt buộc trước khi bàn giao (Pre-Handoff Verification Gate):
1. Check A (Unresolved Command/Test Failure in Turn):
   Phát hiện lệnh kiểm thử (`pytest`, `unittest`, `npm test`, `ruff`, `mypy`, `py_compile`)
   thất bại trong lượt hiện tại nhưng chưa được chạy lại thành công (`exit code == 0`).
2. Check B (CleanStateVerifier Fast Audit on Code Mutation):
   Khi lượt hiện tại có chỉnh sửa file (`write_file`, `edit_file`, `replace_file_content`,
   `write_to_file`) hoặc được yêu cầu kiểm tra, kích hoạt `CleanStateVerifier` (chế độ fast)
   kiểm tra D1 (Syntax/Compilation) và D4 (Zero Debug Artifacts & Stray Files).
3. Check C (Targeted & Auto-Discovered Test Execution on Python Code/Test Mutation):
   Khi lượt hiện tại chỉnh sửa file test (`tests/test_*.py`, `*_test.py`), nhận `target_tests`,
   hoặc chỉnh sửa file mã nguồn `.py` mà chưa chạy `pytest` thành công sau bước sửa cuối cùng
   (`VULN-04`), tự động dò tìm bài kiểm thử tương ứng và chạy `pytest <target_tests> -q`
   (timeout 25s, `stdin=subprocess.DEVNULL`), chặn bàn giao nếu test fail (`returncode != 0`).
4. Circuit Breaker (`max_retries = 2`):
   Nếu `executionNum > 2` hoặc `[PRE-HANDOFF-GATE]` đã xuất hiện `>= 2` lần trong lượt hiện tại,
   trả về `{"decision": "allow"}` để chống lặp vô hạn.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import urllib.parse

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

from harness.validators.clean_state_verifier import (  # noqa: E402
    CleanStateVerifier,
    DimensionStatus,
)

GATE_MARKER = "[PRE-HANDOFF-GATE]"
ANTI_HALLUCINATION_MARKER = "[ANTI-HALLUCINATION-GUARD]"
TRIAD_PROCESS_MARKER = "[TRIAD-PROCESS-GATE]"
ALL_HOOK_MARKERS = (
    GATE_MARKER,
    ANTI_HALLUCINATION_MARKER,
    TRIAD_PROCESS_MARKER,
    "[AUTONOMOUS SKILL & TRIAD ROUTER]",
)
DEFAULT_MAX_RETRIES = 2
TARGET_PYTEST_TIMEOUT = 60
FALLBACK_MAX_TEST_FILES = 25

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

EXEMPT_BASENAMES = {
    "_session-handoff.md",
    "_open-questions.md",
    "memory.md",
}

EXEMPT_PATH_SEGMENTS = (
    "/.gemini/antigravity/brain/",
    "/antigravity/brain/",
    "/.brain/",
    "/obsidian/",
    "/wiki/",
    "/memory/",
    "/scratch/",
)


def is_exempt_path(path_str: str) -> bool:
    """Return True if path points to exempt documentation, memory, session notes, or scratch/brain artifacts."""
    if not path_str or not isinstance(path_str, str):
        return False
    cleaned = path_str.strip()
    if cleaned.lower().startswith("file:///"):
        cleaned = cleaned[8:]
    elif cleaned.lower().startswith("file://"):
        cleaned = cleaned[7:]
    cleaned = urllib.parse.unquote(cleaned).strip()
    if not cleaned:
        return False

    expanded = os.path.expanduser(cleaned)
    norm = expanded.replace("\\", "/")
    norm_low = norm.lower()

    basename_low = Path(norm).name.lower()
    if basename_low in EXEMPT_BASENAMES:
        return True

    padded = "/" + norm_low.lstrip("/")
    if any(seg in padded for seg in EXEMPT_PATH_SEGMENTS):
        return True

    return False

COMMAND_TOOL_NAMES = {
    "run_command",
    "bash",
    "execute_command",
    "shell",
    "run_terminal_cmd",
    "cmd",
}

NON_COMMAND_TOOL_NAMES = (
    MUTATION_TOOL_NAMES
    | {
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
)

VERIFICATION_CMD_RE = re.compile(
    r"(?:^|[;&|]\s*|\s|[\\/\"'])"
    r"(?:pytest|py\.test|unittest|npm\s+test|pnpm\s+test|yarn\s+test|"
    r"ruff|mypy|py_compile|flake8|cargo\s+test|go\s+test|harness_doctor\.py|"
    r"run_pytest_windows\.py)\b",
    re.IGNORECASE,
)

PYTEST_RUN_CMD_RE = re.compile(
    r"(?:^|[;&|]\s*|\s|[\\/\"'])(?:pytest|py\.test|unittest|run_pytest_windows\.py)\b",
    re.IGNORECASE,
)

EXIT_CODE_RE = re.compile(
    r"(?:Command exited with code|exit\s*code\s*[:=]|returncode\s*[:=])\s*(-?\d+)",
    re.IGNORECASE,
)

TEST_FAILURE_TEXT_RE = re.compile(
    r"(?:===\s*FAILURES\s*===|\bFAILED\b.*(?:\.py|::)|"
    r"\bAssertionError\b|\bSyntaxError\b|\b[1-9]\d*\s+failed\b|"
    r"ERROR\s+collecting\b)",
)

TEST_PASS_TEXT_RE = re.compile(
    r"(?:Command exited with code 0\b|\b[1-9]\d*\s+passed\b)",
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

    if any(marker in combined for marker in ALL_HOOK_MARKERS):
        return False
    if source == "SYSTEM" or step_type in ("SYSTEM_MESSAGE", "EPHEMERAL_MESSAGE"):
        return False
    return step_type == "USER_INPUT" or source == "USER_EXPLICIT"


def _is_verification_command(cmd: str) -> bool:
    """Return True if command string is a test, linter, or verification command."""
    if not cmd or not cmd.strip():
        return False
    return bool(VERIFICATION_CMD_RE.search(cmd))


def _is_pytest_command(cmd: str) -> bool:
    """Return True if command string invokes pytest or unittest."""
    if not cmd or not cmd.strip():
        return False
    return bool(PYTEST_RUN_CMD_RE.search(cmd))


def _is_test_py_filename(path_str: str) -> bool:
    p = Path(path_str)
    name_low = p.name.lower()
    return (
        name_low.startswith("test_")
        or name_low.endswith("_test.py")
        or name_low == "conftest.py"
    )


def _extract_path_from_args(args: dict[str, Any]) -> list[str]:
    """Extract file path strings from tool call arguments."""
    paths: list[str] = []
    for key in ("Path", "path", "TargetFile", "target_file", "FilePath", "file_path", "filename"):
        val = _clean_arg_val(args.get(key))
        if val and val not in paths:
            paths.append(val)
    return paths


def _classify_command_result(
    cmd_str: str,
    output_text: str,
    explicit_exit_code: int | None,
    from_verification_cmd: bool,
) -> dict[str, Any] | None:
    """Classify a command execution result as pass or fail if it is a verification event."""
    exit_code = explicit_exit_code
    if exit_code is None and output_text:
        m = EXIT_CODE_RE.search(output_text)
        if m:
            try:
                exit_code = int(m.group(1))
            except ValueError:
                exit_code = None

    has_test_failure_text = bool(TEST_FAILURE_TEXT_RE.search(output_text or ""))
    has_test_pass_text = bool(TEST_PASS_TEXT_RE.search(output_text or ""))

    is_verification = (
        from_verification_cmd
        or _is_verification_command(cmd_str)
        or (not cmd_str and (has_test_failure_text or has_test_pass_text or exit_code is not None))
    )
    if not is_verification:
        return None

    is_failure = False
    is_pass = False

    if exit_code is not None:
        if exit_code != 0:
            is_failure = True
        else:
            is_pass = True
    else:
        if has_test_failure_text:
            is_failure = True
        elif has_test_pass_text:
            is_pass = True

    if not is_failure and not is_pass:
        return None

    return {
        "command": cmd_str or "verification_command",
        "exit_code": exit_code if exit_code is not None else (1 if is_failure else 0),
        "status": "FAIL" if is_failure else "PASS",
        "output": (output_text or "")[:500],
    }


def extract_turn_context(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract current turn steps, retry count, verification events, and mutated source/test files."""
    last_user_idx = -1
    for idx, step in enumerate(steps):
        if _is_genuine_user_step(step):
            last_user_idx = idx

    turn_steps = steps[last_user_idx + 1 :] if last_user_idx >= 0 else list(steps)

    retry_count = 0
    mutated_files: list[str] = []
    modified_source_py_files: list[str] = []
    has_code_mutation = False
    last_any_mutation_idx = -1
    last_non_test_py_mutation_idx = -1
    last_passing_pytest_idx = -1
    verification_events: list[dict[str, Any]] = []

    pending_tool_calls: list[tuple[str, str]] = []

    def _record_mutated_path(raw_p: str, idx_step: int) -> bool:
        nonlocal last_any_mutation_idx, last_non_test_py_mutation_idx, has_code_mutation
        if is_exempt_path(raw_p):
            return False
        has_code_mutation = True
        last_any_mutation_idx = idx_step
        if raw_p not in mutated_files:
            mutated_files.append(raw_p)
        if Path(raw_p).suffix.lower() == ".py" and not _is_test_py_filename(raw_p):
            last_non_test_py_mutation_idx = idx_step
            if raw_p not in modified_source_py_files:
                modified_source_py_files.append(raw_p)
        return True

    def _record_verification_event(ev: dict[str, Any], idx_step: int) -> None:
        nonlocal last_passing_pytest_idx
        ev_with_idx = {**ev, "step_idx": idx_step}
        verification_events.append(ev_with_idx)
        if ev["status"] == "PASS":
            cmd_val = str(ev.get("command") or "")
            if _is_pytest_command(cmd_val) or cmd_val == "verification_command":
                last_passing_pytest_idx = idx_step

    for step_idx, step in enumerate(turn_steps):
        step_type = str(step.get("type") or "")
        source = str(step.get("source") or "")
        role = str(step.get("role") or "")
        content = str(step.get("content") or "")
        reason = str(step.get("reason") or "")
        message = str(step.get("message") or "")

        is_planner = step_type == "PLANNER_RESPONSE" or role in ("assistant", "model")

        if not is_planner:
            combined_meta = f"{content}\n{reason}\n{message}"
            if GATE_MARKER in combined_meta:
                retry_count += 1

        # 1. Inspect tool_calls on the step
        tool_calls = step.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            pending_tool_calls = []
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                fn_obj = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                raw_name = _clean_arg_val(
                    tc.get("name") or tc.get("tool") or fn_obj.get("name") or ""
                )
                tc_name = raw_name.rsplit(":", 1)[-1].strip()
                tc_args = _parse_args_dict(
                    tc.get("args")
                    if "args" in tc
                    else tc.get("arguments")
                    if "arguments" in tc
                    else tc.get("input")
                    if "input" in tc
                    else tc.get("parameters")
                )

                if tc_name in MUTATION_TOOL_NAMES:
                    extracted_paths = _extract_path_from_args(tc_args)
                    if extracted_paths:
                        for p in extracted_paths:
                            _record_mutated_path(p, step_idx)
                    else:
                        has_code_mutation = True

                cmd_str = _clean_arg_val(
                    tc_args.get("CommandLine")
                    or tc_args.get("command")
                    or tc_args.get("cmd")
                    or ""
                )
                if tc_name in COMMAND_TOOL_NAMES or cmd_str:
                    pending_tool_calls.append((tc_name or "run_command", cmd_str))
                elif tc_name:
                    pending_tool_calls.append((tc_name, ""))

        # Check direct mutation metadata on step
        raw_step_tool = _clean_arg_val(step.get("tool") or step.get("name") or "")
        step_tool = raw_step_tool.rsplit(":", 1)[-1].strip()
        if step_tool in MUTATION_TOOL_NAMES:
            extracted_paths = _extract_path_from_args(step)
            if extracted_paths:
                for p in extracted_paths:
                    _record_mutated_path(p, step_idx)
            else:
                has_code_mutation = True

        mod_list = step.get("modified_files")
        if isinstance(mod_list, list):
            for p in mod_list:
                cleaned_p = _clean_arg_val(p)
                if cleaned_p:
                    _record_mutated_path(cleaned_p, step_idx)

        # 2. Check embedded tool_results / tool_responses
        embedded_results = step.get("tool_results") or step.get("tool_responses")
        if isinstance(embedded_results, list):
            for idx_r, tr in enumerate(embedded_results):
                if not isinstance(tr, dict):
                    continue
                tc_name, cmd_str = ("", "")
                if idx_r < len(pending_tool_calls):
                    tc_name, cmd_str = pending_tool_calls[idx_r]
                cmd_str = _clean_arg_val(tr.get("command") or tr.get("CommandLine") or cmd_str)
                if tc_name in NON_COMMAND_TOOL_NAMES and not cmd_str:
                    continue
                out_chunks = [
                    str(tr.get(k) or "")
                    for k in ("content", "output", "stdout", "stderr", "result")
                    if tr.get(k)
                ]
                out_text = "\n".join(out_chunks).strip()
                raw_ec = tr.get("exit_code") if "exit_code" in tr else tr.get("returncode")
                explicit_ec = (
                    int(raw_ec) if isinstance(raw_ec, int) and not isinstance(raw_ec, bool) else None
                )
                ev = _classify_command_result(
                    cmd_str=cmd_str,
                    output_text=out_text,
                    explicit_exit_code=explicit_ec,
                    from_verification_cmd=_is_verification_command(cmd_str),
                )
                if ev is not None:
                    _record_verification_event(ev, step_idx)
            pending_tool_calls = []
            continue

        # 3. Non-planner step that may be a command/tool output step (including background task completion SYSTEM_MESSAGE)
        is_bg_task_completion = (
            (step_type == "SYSTEM_MESSAGE" or source == "SYSTEM")
            and "finished with result:" in content
            and "Command exited with code" in content
        )
        if (
            not is_planner
            and (
                (step_type not in ("USER_INPUT", "SYSTEM_MESSAGE") and source != "SYSTEM")
                or is_bg_task_completion
            )
        ):
            if any(m in content for m in ALL_HOOK_MARKERS):
                continue

            tc_name, cmd_str = ("", "")
            if pending_tool_calls:
                tc_name, cmd_str = pending_tool_calls.pop(0)

            step_cmd = _clean_arg_val(step.get("command") or step.get("CommandLine") or "")
            if step_cmd:
                cmd_str = step_cmd

            if tc_name in NON_COMMAND_TOOL_NAMES and not step_cmd:
                continue
            if cmd_str and not _is_verification_command(cmd_str):
                continue

            out_chunks = [
                str(step.get(k) or "")
                for k in ("content", "output", "stdout", "stderr", "result", "response")
                if isinstance(step.get(k), str) and str(step.get(k)).strip()
            ]
            out_text = "\n".join(out_chunks).strip()
            raw_ec = step.get("exit_code") if "exit_code" in step else step.get("returncode")
            explicit_ec = (
                int(raw_ec) if isinstance(raw_ec, int) and not isinstance(raw_ec, bool) else None
            )

            ev = _classify_command_result(
                cmd_str=cmd_str,
                output_text=out_text,
                explicit_exit_code=explicit_ec,
                from_verification_cmd=_is_verification_command(cmd_str),
            )
            if ev is not None:
                _record_verification_event(ev, step_idx)

    return {
        "turn_steps": turn_steps,
        "retry_count": retry_count,
        "verification_events": verification_events,
        "mutated_files": mutated_files,
        "modified_source_py_files": modified_source_py_files,
        "has_code_mutation": has_code_mutation,
        "last_any_mutation_idx": last_any_mutation_idx,
        "last_non_test_py_mutation_idx": last_non_test_py_mutation_idx,
        "last_passing_pytest_idx": last_passing_pytest_idx,
    }


def _resolve_workspace_root(
    base_dir: Path | str | None,
    transcript_path: Path | str,
    mutated_files: list[str],
) -> Path:
    """Resolve the target project/workspace root for CleanStateVerifier and pytest."""
    if base_dir:
        cand = Path(base_dir).resolve()
        if cand.is_dir():
            return cand

    for mf in mutated_files:
        p = Path(mf)
        if p.is_absolute() and p.exists():
            try:
                p.resolve().relative_to(REPO_ROOT)
            except ValueError:
                if p.parent.name in ("tests", "test", "src", "app"):
                    return p.parent.parent.resolve()
                return p.parent.resolve()

    t_parent = Path(transcript_path).resolve().parent
    if mutated_files and t_parent != REPO_ROOT:
        for mf in mutated_files:
            if not Path(mf).is_absolute() and (t_parent / mf).exists():
                return t_parent

    return REPO_ROOT


def _resolve_modified_test_files(
    workspace_root: Path,
    mutated_files: list[str],
    extra_target_tests: list[str] | None = None,
) -> list[Path]:
    """Return existing test file paths (`test_*.py` or `*_test.py`) touched in the turn."""
    candidates: list[str] = list(mutated_files)
    if extra_target_tests:
        for t in extra_target_tests:
            if isinstance(t, str) and t.strip() and t.strip() not in candidates:
                candidates.append(t.strip())

    resolved_tests: list[Path] = []
    for raw_path in candidates:
        if is_exempt_path(raw_path):
            continue
        p = Path(raw_path)
        if not p.is_absolute():
            p = (workspace_root / p).resolve()
        else:
            p = p.resolve()

        if not p.is_file() or p.suffix.lower() != ".py":
            continue

        is_test_name = p.name.startswith("test_") or p.name.endswith("_test.py")
        is_explicit = bool(extra_target_tests and raw_path in extra_target_tests)
        if (is_test_name or is_explicit) and p not in resolved_tests:
            resolved_tests.append(p)

    return resolved_tests


def discover_tests_for_source_mutations(
    modified_source_py_files: list[str],
    workspace_root: Path,
    *,
    fallback_max_files: int = FALLBACK_MAX_TEST_FILES,
) -> list[Path]:
    """Discover unit test files corresponding to modified non-test `.py` source files."""
    if not modified_source_py_files:
        return []

    discovered: list[Path] = []
    tests_dir = workspace_root / "tests"

    def _add(cand: Path) -> None:
        resolved = cand.resolve()
        if resolved.is_file() and resolved.suffix.lower() == ".py" and resolved not in discovered:
            discovered.append(resolved)

    for raw_src in modified_source_py_files:
        p = Path(raw_src)
        src_path = p.resolve() if p.is_absolute() else (workspace_root / p).resolve()
        stem = src_path.stem
        if stem == "__init__" and src_path.parent.name:
            stem = src_path.parent.name
        if not stem:
            continue

        # 1. Direct convention in tests/
        _add(tests_dir / f"test_{stem}.py")
        _add(tests_dir / f"{stem}_test.py")

        # 2. Sibling test files next to source file
        if src_path.parent.is_dir():
            _add(src_path.parent / f"test_{stem}.py")
            _add(src_path.parent / f"{stem}_test.py")

        # 3. Nested tests/**/test_<stem>*.py
        if tests_dir.is_dir():
            for match in sorted(tests_dir.rglob(f"test_{stem}*.py")):
                _add(match)
            for match in sorted(tests_dir.rglob(f"*{stem}*_test.py")):
                _add(match)

    # 4. Small workspace fallback (`<= 25` test files in `workspace_root / "tests"`)
    if not discovered and tests_dir.is_dir():
        all_ws_tests = sorted(
            tp.resolve()
            for tp in tests_dir.rglob("*.py")
            if tp.is_file() and (tp.name.startswith("test_") or tp.name.endswith("_test.py"))
        )
        if 0 < len(all_ws_tests) <= fallback_max_files:
            for tp in all_ws_tests:
                if tp not in discovered:
                    discovered.append(tp)

    return discovered


def run_targeted_pytest(
    test_files: list[Path],
    workspace_root: Path,
    *,
    timeout: int = TARGET_PYTEST_TIMEOUT,
) -> dict[str, str] | None:
    """Execute `pytest` on `test_files` with `stdin=subprocess.DEVNULL` and return block decision on failure."""
    if not test_files:
        return None

    cmd = [sys.executable, "-m", "pytest", "--import-mode=importlib", *[str(p) for p in test_files], "-q"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace_root),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if proc.returncode != 0:
            combined_out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            tail_lines = [ln.strip() for ln in combined_out.splitlines() if ln.strip()][-5:]
            summary = " | ".join(tail_lines) if tail_lines else f"exit code {proc.returncode}"
            rel_names = [p.name for p in test_files]
            return {
                "decision": "continue",
                "reason": (
                    f"{GATE_MARKER} Bài kiểm thử mục tiêu thất bại ({', '.join(rel_names)}, "
                    f"exit code {proc.returncode}): {summary}. "
                    "Yêu cầu sửa lỗi để pytest đạt exit code 0 trước khi bàn giao."
                ),
            }
    except subprocess.TimeoutExpired:
        return {
            "decision": "continue",
            "reason": (
                f"{GATE_MARKER} Bài kiểm thử mục tiêu bị quá thời gian chờ "
                f"(timeout > {timeout}s). Yêu cầu kiểm tra vòng lặp hoặc deadlock trước khi bàn giao."
            ),
        }
    except Exception:
        pass

    return None


def evaluate_transcript(
    transcript_path: Path | str,
    *,
    base_dir: Path | str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    execution_num: int = 0,
    termination_reason: str = "",
    check_clean_state: bool = False,
    target_tests: list[str] | None = None,
) -> dict[str, str]:
    """Evaluate a transcript JSONL file and return the Pre-Handoff Stop hook decision."""
    if termination_reason and termination_reason != "NO_TOOL_CALL":
        return {"decision": "allow"}

    if execution_num > max_retries:
        return {"decision": "allow"}

    steps = parse_transcript(transcript_path)
    if not steps and not check_clean_state and not target_tests:
        return {"decision": "allow"}

    ctx = extract_turn_context(steps)
    if ctx["retry_count"] >= max_retries:
        return {"decision": "allow"}

    # -------------------------------------------------------------------------
    # Check A: Unresolved Command / Test Failure in Current Turn
    # -------------------------------------------------------------------------
    events: list[dict[str, Any]] = ctx["verification_events"]
    if events:
        has_any_failure = any(e["status"] == "FAIL" for e in events)
        latest_event = events[-1]
        if has_any_failure and latest_event["status"] != "PASS":
            failed_cmd = latest_event.get("command") or "test command"
            failed_code = latest_event.get("exit_code", 1)
            return {
                "decision": "continue",
                "reason": (
                    f"{GATE_MARKER} Phát hiện lệnh kiểm thử thất bại trong lượt hiện tại "
                    f"('{failed_cmd}', exit code {failed_code}) nhưng chưa được chạy lại "
                    "thành công (exit code == 0) trước khi bàn giao. Yêu cầu sửa lỗi và "
                    "chạy lại kiểm thử đạt exit code 0."
                ),
            }

    workspace_root = _resolve_workspace_root(
        base_dir=base_dir,
        transcript_path=transcript_path,
        mutated_files=ctx["mutated_files"],
    )

    # -------------------------------------------------------------------------
    # Check B: CleanStateVerifier Fast Audit (D1 Syntax & D4 Zero Debug)
    # -------------------------------------------------------------------------
    if ctx["has_code_mutation"] or check_clean_state:
        verifier = CleanStateVerifier(
            project_root=workspace_root,
            config={"fast_mode": True},
        )
        d1_res = verifier.check_d1_build_type()
        d4_res = verifier.check_d4_zero_debug()

        violations: list[str] = []
        if d1_res.status == DimensionStatus.FAIL:
            violations.extend(d1_res.violations[:3] or [d1_res.message])
        if d4_res.status == DimensionStatus.FAIL:
            violations.extend(d4_res.violations[:3] or [d4_res.message])

        if violations:
            v_str = "; ".join(violations)
            return {
                "decision": "continue",
                "reason": (
                    f"{GATE_MARKER} CleanStateVerifier phát hiện lỗi cú pháp hoặc debug artifact "
                    f"trước khi bàn giao: {v_str}. Yêu cầu làm sạch mã nguồn (D1/D4 PASS) trước khi kết thúc lượt."
                ),
            }

    # -------------------------------------------------------------------------
    # Check C: Targeted & Auto-Discovered Test Execution (VULN-04)
    # -------------------------------------------------------------------------
    unverified_mutations = (
        ctx["last_any_mutation_idx"] >= 0
        and ctx["last_passing_pytest_idx"] < ctx["last_any_mutation_idx"]
    )
    test_files = _resolve_modified_test_files(
        workspace_root=workspace_root,
        mutated_files=ctx["mutated_files"] if unverified_mutations else [],
        extra_target_tests=target_tests,
    )

    if (
        ctx["last_non_test_py_mutation_idx"] >= 0
        and ctx["last_passing_pytest_idx"] < ctx["last_non_test_py_mutation_idx"]
    ):
        discovered = discover_tests_for_source_mutations(
            ctx["modified_source_py_files"],
            workspace_root,
        )
        for dp in discovered:
            if dp not in test_files:
                test_files.append(dp)

    if test_files:
        pytest_block = run_targeted_pytest(test_files, workspace_root)
        if pytest_block is not None:
            return pytest_block

    return {"decision": "allow"}


def evaluate_hook_payload(
    payload: dict[str, Any],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
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

    if execution_num > max_retries:
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

    check_clean_state = bool(payload.get("check_clean_state", False))
    raw_targets = payload.get("target_tests")
    target_tests = (
        [str(t) for t in raw_targets if isinstance(t, str)]
        if isinstance(raw_targets, list)
        else None
    )

    return evaluate_transcript(
        transcript_path,
        base_dir=base_dir,
        max_retries=max_retries,
        execution_num=execution_num,
        termination_reason=termination_reason,
        check_clean_state=check_clean_state,
        target_tests=target_tests,
    )


def main() -> None:
    """CLI and Antigravity Stop Hook entry point."""
    result: dict[str, str] = {"decision": "allow"}
    try:
        parser = argparse.ArgumentParser(
            description="Enforce Pre-Handoff Verification Gate on Antigravity Stop Hook"
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
            "--check-clean-state",
            action="store_true",
            help="Force CleanStateVerifier D1/D4 check",
        )
        parser.add_argument(
            "--target-tests",
            nargs="*",
            default=None,
            help="Explicit test files to execute with pytest",
        )
        args, _ = parser.parse_known_args()

        if args.transcript:
            result = evaluate_transcript(
                args.transcript,
                base_dir=args.base_dir or None,
                max_retries=args.max_retries,
                check_clean_state=args.check_clean_state,
                target_tests=args.target_tests,
            )
        elif not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input and raw_input.strip():
                payload = json.loads(raw_input)
                if isinstance(payload, dict):
                    result = evaluate_hook_payload(
                        payload,
                        max_retries=args.max_retries,
                    )
    except Exception:
        # Failsafe: never crash the Antigravity agent lifecycle
        result = {"decision": "allow"}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
