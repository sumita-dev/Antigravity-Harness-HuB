#!/usr/bin/env python3
"""Auto Harvest Global Code Patterns.

Antigravity Lifecycle Hook script executed on 'Stop' event.
Analyzes session transcript (jsonl), detects resolved code errors,
extracts learned patterns, and persists them to:
1. <global_config>/global_code_patterns.json
2. <global_config>/rules/learned_code_rules.md

Adheres strictly to the Antigravity Hook contract.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import uuid
from typing import Any

DEFAULT_MAX_PATTERNS = 50


def get_config_dir(override_dir: str | None = None) -> Path:
    """Determine the Antigravity global configuration directory."""
    if override_dir:
        return Path(override_dir).resolve()
    env_dir = os.environ.get("ANTIGRAVITY_CONFIG_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return (Path.home() / ".gemini" / "config").resolve()


def sanitize_text(text: str) -> str:
    """Sanitize machine-specific and user-specific paths for privacy and portability."""
    if not text:
        return ""
    # Normalize Windows user paths: C:\Users\<name>\... -> ~/...
    text = re.sub(r"[A-Za-z]:\\Users\\[^\s\\\"\'\(\)\[\]]+", "~", text)
    # Normalize Unix user paths: /home/<name>/... or /Users/<name>/... -> ~/...
    text = re.sub(r"/(?:home|Users)/[^\s/\"\'\(\)\[\]]+", "~", text)
    return text.strip()


def parse_transcript(transcript_path: Path) -> list[dict[str, Any]]:
    """Parse transcript.jsonl into a list of step dictionaries."""
    if not transcript_path.is_file():
        return []

    steps: list[dict[str, Any]] = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
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


def is_command_failure(status: str, content: str, error: str) -> bool:
    """Determine whether a tool execution resulted in a code or command error."""
    if status == "ERROR":
        return True
    if error and error.strip():
        return True
    if not content:
        return False

    # Non-zero exit code check
    exit_match = re.search(r"(?:The\s+)?command exited with code\s+([1-9]\d*)", content, re.IGNORECASE)
    if exit_match:
        return True

    # Python traceback detection
    if "Traceback (most recent call last):" in content:
        return True

    # Test failure detection (pytest, unittest, jest, etc.)
    if re.search(r"\b(?:FAILED|FAILURES|ERRORS)\b.*(?:tests?|test_|\.py|\.js|\.ts)", content, re.IGNORECASE):
        return True

    # Python exception detection
    if re.search(r"\b[A-Za-z0-9_.]*(?:Error|Exception)\b:\s*.+", content):
        return True

    return False


def extract_error_details(content: str, error: str) -> tuple[str, str]:
    """Extract error type and root cause message from step content/error."""
    combined = sanitize_text((error or "") + "\n" + (content or ""))

    # 1. Standard Python / Runtime exceptions: e.g. ModuleNotFoundError: No module named 'x'
    exc_match = re.search(r"\b([A-Za-z0-9_.]*(?:Error|Exception))\b:\s*(.+)", combined)
    if exc_match:
        err_type = exc_match.group(1).split(".")[-1]
        cause_line = exc_match.group(2).strip().splitlines()[0]
        return err_type, cause_line[:250]

    # 2. Pytest FAILED line
    pytest_match = re.search(r"FAILED\s+([^\s]+)(?:\s+-\s+(.+))?", combined)
    if pytest_match:
        err_type = "AssertionError" if "assert" in combined.lower() else "TestFailure"
        detail = pytest_match.group(2) or pytest_match.group(1)
        return err_type, detail.strip().splitlines()[0][:250]

    # 3. Non-zero exit code
    exit_match = re.search(r"(?:The\s+)?command exited with code\s+([1-9]\d*)", combined, re.IGNORECASE)
    if exit_match:
        code = exit_match.group(1)
        # Check first non-empty error line in content
        first_line = ""
        for line in combined.splitlines():
            line_str = line.strip()
            if (
                line_str
                and not line_str.startswith("Created At")
                and not line_str.startswith("Completed At")
                and not re.match(r"^(?:The\s+)?command exited", line_str, re.IGNORECASE)
            ):
                first_line = line_str
                break
        detail = first_line if first_line else f"Command exited with code {code}"
        return f"CommandExitCode{code}", detail[:250]

    if error:
        return "RuntimeError", sanitize_text(error).splitlines()[0][:250]

    return "ExecutionError", "Command execution failed"


_WORKSPACE_SPECIFIC_PATTERNS = (
    re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)\b(?::\d+)?|\[::1\](?::\d+)?", re.IGNORECASE),
    re.compile(r"(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{30,}|Bearer\s+[A-Za-z0-9._-]{20,})"),
    re.compile(r"\b(?:JIRA-\d+|PR\s*#\d+)\b", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z]:\\(?:Users|Projects|Work|dev)\\|/tmp/)", re.IGNORECASE),
)


def is_workspace_specific(text: str) -> bool:
    """Detect workspace-specific facts (loopback, real secrets, local tickets, unsanitized local paths)."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in _WORKSPACE_SPECIFIC_PATTERNS)


def has_valid_triad_schema(pattern: dict[str, Any]) -> bool:
    """Verify that a pattern contains non-empty string cue, lesson, and evidence fields."""
    for field in ("cue", "lesson", "evidence"):
        val = pattern.get(field)
        if not isinstance(val, str) or not val.strip():
            return False
    return True


def build_triad_fields(
    err_type: str,
    cause: str,
    fix_text: str,
    verify_cmd: str,
    unique_files: list[str],
    conversation_id: str,
) -> dict[str, str]:
    """Build Triad Lesson Schema fields (cue, lesson, evidence) for a resolved pattern."""
    cue = f"[{err_type}] {cause} (cmd: {verify_cmd})" if verify_cmd else f"[{err_type}] {cause}"
    files_str = ",".join(unique_files) if unique_files else "none"
    evidence = (
        f"Resolved via {verify_cmd or 'code_modification'} (exit=0); "
        f"files={files_str}; conv={conversation_id}"
    )
    return {
        "cue": cue,
        "lesson": fix_text,
        "evidence": evidence,
    }


def make_dedup_key(error_type: str, cause: str) -> str:
    """Generate a stable deduplication key for error patterns."""
    # Normalize cause: remove hex addresses, numbers, extra whitespace
    norm = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", cause)
    norm = re.sub(r"\bline \d+\b", "line X", norm, flags=re.IGNORECASE)
    norm = re.sub(r"\s+", " ", norm).strip().lower()
    return f"{error_type.strip().lower()}::{norm[:120]}"


def _is_pattern_workspace_specific(pat: dict[str, Any]) -> bool:
    """Check whether any core field of a pattern contains workspace-specific facts."""
    fields_to_check = [
        str(pat.get("cause", "")),
        str(pat.get("fix", "")),
        str(pat.get("command", "")),
        " ".join(str(f) for f in (pat.get("files_modified") or [])),
    ]
    return any(is_workspace_specific(text) for text in fields_to_check if text)


def _build_resolved_pattern(
    ae: dict[str, Any],
    conversation_id: str,
    verify_cmd: str = "",
) -> dict[str, Any] | None:
    """Construct a resolved pattern dict with Triad schema, returning None if workspace-specific."""
    files = [f["file"] for f in ae["fixes"] if f.get("file")]
    unique_files = list(dict.fromkeys(files))
    descs = [f["description"] for f in ae["fixes"] if f.get("description")]
    fix_text = "; ".join(descs[:3]) if descs else "Fixed via code modification"
    cmd = verify_cmd or ae.get("command", "")
    triad = build_triad_fields(
        err_type=ae["error_type"],
        cause=ae["cause"],
        fix_text=fix_text,
        verify_cmd=cmd,
        unique_files=unique_files,
        conversation_id=conversation_id,
    )
    pat: dict[str, Any] = {
        "id": f"pat_{uuid.uuid4().hex[:8]}",
        "error_type": ae["error_type"],
        "cause": ae["cause"],
        "fix": fix_text,
        "command": cmd,
        "files_modified": unique_files,
        "timestamp": ae.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "occurrences": 1,
        **triad,
    }
    if _is_pattern_workspace_specific(pat):
        return None
    return pat


def harvest_patterns_from_steps(steps: list[dict[str, Any]], conversation_id: str = "") -> list[dict[str, Any]]:
    """Analyze step history and identify resolved code error patterns."""
    resolved_patterns: list[dict[str, Any]] = []
    active_errors: list[dict[str, Any]] = []

    # Map step index to step data for quick lookup
    # Antigravity step sequence typically:
    # Step N: PLANNER_RESPONSE with tool_calls
    # Step N+1: GENERIC (tool execution output)

    for i, step in enumerate(steps):
        step_type = step.get("type", "")
        status = step.get("status", "")
        content = step.get("content", "")
        err_msg = step.get("error", "")
        created_at = step.get("created_at", "")

        # Look for code editing actions in PLANNER_RESPONSE
        if step_type == "PLANNER_RESPONSE":
            tool_calls = step.get("tool_calls", [])
            for tc in tool_calls:
                tc_name = tc.get("name", "")
                args = tc.get("args", {})
                if tc_name in (
                    "replace_file_content",
                    "write_to_file",
                    "edit_file",
                    "write_file",
                    "multi_replace_file_content",
                    "apply_patch",
                ):
                    target_file = sanitize_text(
                        str(args.get("Path") or args.get("TargetFile") or args.get("file_path") or "")
                    )
                    instruction = sanitize_text(
                        str(args.get("Instruction") or args.get("Description") or args.get("toolSummary") or "")
                    )
                    fix_desc = instruction if instruction else f"Modified file `{target_file}`"
                    for ae in active_errors:
                        ae["fixes"].append({
                            "file": target_file,
                            "description": fix_desc,
                            "timestamp": created_at
                        })

        # Check tool execution results in GENERIC or response steps
        elif step_type in ("GENERIC", "TOOL_RESPONSE") or content or err_msg:
            # Check what tool this corresponds to by inspecting the preceding PLANNER_RESPONSE
            prev_tool_call = None
            for p in range(i - 1, -1, -1):
                if steps[p].get("type") == "PLANNER_RESPONSE":
                    tcs = steps[p].get("tool_calls", [])
                    if tcs:
                        prev_tool_call = tcs[-1]
                    break

            tool_name = prev_tool_call.get("name", "") if prev_tool_call else ""
            tool_args = prev_tool_call.get("args", {}) if prev_tool_call else {}
            cmd_line = sanitize_text(str(tool_args.get("CommandLine", "")))

            failed = is_command_failure(status, content, err_msg)

            if failed:
                err_type, cause = extract_error_details(content, err_msg)
                active_errors.append({
                    "error_type": err_type,
                    "cause": cause,
                    "command": cmd_line,
                    "step_index": step.get("step_index", i),
                    "timestamp": created_at,
                    "fixes": []
                })
            else:
                # Execution succeeded! If it was run_command or validation step,
                # resolve pending errors that had code modifications applied.
                if active_errors:
                    is_success_cmd = (
                        tool_name == "run_command"
                        or bool(re.search(r"(?:The\s+)?command exited with code\s+0\b", content, re.IGNORECASE))
                        or status == "DONE"
                    )
                    if is_success_cmd:
                        verify_cmd = cmd_line if tool_name == "run_command" else ""
                        for ae in active_errors:
                            if ae["fixes"]:
                                pat = _build_resolved_pattern(ae, conversation_id, verify_cmd=verify_cmd)
                                if pat is not None:
                                    resolved_patterns.append(pat)
                        active_errors.clear()

    # If transcript ended cleanly and there remain active errors with recorded fixes,
    # capture them as resolved by final session state.
    if active_errors:
        last_step = steps[-1] if steps else {}
        if last_step.get("status") == "DONE":
            for ae in active_errors:
                if ae["fixes"]:
                    pat = _build_resolved_pattern(ae, conversation_id)
                    if pat is not None:
                        resolved_patterns.append(pat)

    return resolved_patterns


def render_rules_markdown(md_path: Path, patterns: list[dict[str, Any]]) -> None:
    """Render learned patterns into a clean Antigravity markdown rule."""
    lines = [
        "---",
        "description: Learned code rules and error preventions captured automatically",
        "---",
        "",
        "# Learned Code Rules & Best Practices",
        "",
        "> Tự động tổng hợp và cập nhật bởi Auto Code Harvester từ các phiên sửa lỗi code thực tế.",
        "",
    ]

    if not patterns:
        lines.append("*Chưa có mẫu lỗi nào được ghi nhận.*")
    else:
        for idx, pat in enumerate(patterns, 1):
            err_type = pat.get("error_type", "UnknownError")
            cause = pat.get("cause", "N/A")
            fix = pat.get("fix", "N/A")
            cmd = pat.get("command", "")
            files = pat.get("files_modified", [])
            occ = pat.get("occurrences", 1)
            ts = pat.get("timestamp", "")
            cid = pat.get("conversation_id", "")

            lines.append(f"### {idx}. [{err_type}]")
            lines.append(f"- **Nguyên nhân:** `{cause}`")
            lines.append(f"- **Cách khắc phục:** {fix}")
            cue = pat.get("cue")
            if isinstance(cue, str) and cue.strip():
                lines.append(f"- **Cue:** `{cue}`")
            lesson = pat.get("lesson")
            if isinstance(lesson, str) and lesson.strip():
                lines.append(f"- **Lesson:** {lesson}")
            evidence = pat.get("evidence")
            if isinstance(evidence, str) and evidence.strip():
                lines.append(f"- **Evidence:** `{evidence}`")
            if cmd:
                lines.append(f"- **Lệnh liên quan:** `{cmd}`")
            if files:
                file_str = ", ".join(f"`{f}`" for f in files)
                lines.append(f"- **Tệp can thiệp:** {file_str}")
            cid_str = f" | Conv: `{cid}`" if cid else ""
            lines.append(f"- **Tần suất & Thời gian:** {occ} lần | Lần cuối: {ts}{cid_str}")
            lines.append("")

    tmp_md = md_path.with_suffix(".tmp")
    with open(tmp_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    tmp_md.replace(md_path)


def save_patterns(
    config_dir: Path,
    new_patterns: list[dict[str, Any]],
    max_patterns: int = DEFAULT_MAX_PATTERNS
) -> None:
    """Persist learned patterns to global JSON and markdown rules with deduplication."""
    filtered_new = [p for p in new_patterns if not _is_pattern_workspace_specific(p)]
    if not filtered_new:
        return

    config_dir.mkdir(parents=True, exist_ok=True)
    json_path = config_dir / "global_code_patterns.json"

    existing_patterns: list[dict[str, Any]] = []
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    existing_patterns = data
                elif isinstance(data, dict) and "patterns" in data and isinstance(data["patterns"], list):
                    existing_patterns = data["patterns"]
        except Exception:
            existing_patterns = []

    # Map by deduplication key (filter out legacy workspace-specific entries on reload)
    pattern_map: dict[str, dict[str, Any]] = {}
    for pat in existing_patterns:
        if _is_pattern_workspace_specific(pat):
            continue
        k = make_dedup_key(pat.get("error_type", ""), pat.get("cause", ""))
        pattern_map[k] = pat

    for pat in filtered_new:
        k = make_dedup_key(pat.get("error_type", ""), pat.get("cause", ""))
        if k in pattern_map:
            cur = pattern_map[k]
            cur["occurrences"] = cur.get("occurrences", 1) + 1
            cur["timestamp"] = pat.get("timestamp", cur.get("timestamp"))
            if pat.get("fix") and len(pat["fix"]) > len(cur.get("fix", "")):
                cur["fix"] = pat["fix"]
            merged_files = list(dict.fromkeys(cur.get("files_modified", []) + pat.get("files_modified", [])))
            cur["files_modified"] = merged_files
            if pat.get("conversation_id"):
                cur["conversation_id"] = pat["conversation_id"]
            for triad_key in ("cue", "lesson", "evidence"):
                new_val = pat.get(triad_key)
                cur_val = cur.get(triad_key, "")
                if isinstance(new_val, str) and new_val.strip():
                    if not isinstance(cur_val, str) or len(new_val) >= len(cur_val):
                        cur[triad_key] = new_val
        else:
            pattern_map[k] = pat

    # Sort: highest occurrences first, then latest timestamp
    all_patterns = list(pattern_map.values())
    all_patterns.sort(key=lambda p: (p.get("occurrences", 1), p.get("timestamp", "")), reverse=True)

    # Enforce maximum pattern capacity
    capped_patterns = all_patterns[:max_patterns]

    # Atomic write to JSON
    tmp_json = json_path.with_suffix(".tmp")
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": 1,
                "total": len(capped_patterns),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "patterns": capped_patterns,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    tmp_json.replace(json_path)

    # Write to Markdown rules
    rules_dir = config_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    md_path = rules_dir / "learned_code_rules.md"
    render_rules_markdown(md_path, capped_patterns)


def harvest_from_transcript(
    transcript_path: Path,
    conversation_id: str = "",
    config_dir: Path | None = None,
    max_patterns: int = DEFAULT_MAX_PATTERNS,
) -> list[dict[str, Any]]:
    """Process a single transcript file and persist any new patterns discovered."""
    if not transcript_path.is_file():
        return []

    target_config_dir = config_dir or get_config_dir()
    steps = parse_transcript(transcript_path)
    if not steps:
        return []

    patterns = harvest_patterns_from_steps(steps, conversation_id=conversation_id)
    if patterns:
        save_patterns(target_config_dir, patterns, max_patterns=max_patterns)
    return patterns


def main() -> None:
    """CLI and Hook entry point. Guarantees safe zero-exit with JSON output."""
    try:
        parser = argparse.ArgumentParser(description="Auto Harvest Global Code Patterns Hook")
        parser.add_argument("--transcript", "-t", type=str, help="Direct path to transcript.jsonl")
        parser.add_argument("--conversation-id", "-c", type=str, default="", help="Conversation ID")
        parser.add_argument("--config-dir", type=str, default="", help="Override config dir")
        args, _ = parser.parse_known_args()

        transcript_arg = args.transcript
        conv_id = args.conversation_id
        override_config = args.config_dir or None

        # Check if input is coming from stdin (Antigravity Hook Contract)
        if not transcript_arg:
            if not sys.stdin.isatty():
                try:
                    raw_input = sys.stdin.read()
                    if raw_input and raw_input.strip():
                        payload = json.loads(raw_input)
                        if isinstance(payload, dict):
                            transcript_arg = payload.get("transcriptPath")
                            if not conv_id:
                                conv_id = payload.get("conversationId", "")
                except Exception:
                    pass

        if transcript_arg:
            t_path = Path(transcript_arg)
            cfg_dir = get_config_dir(override_config)
            harvest_from_transcript(t_path, conversation_id=conv_id, config_dir=cfg_dir)

    except Exception:
        # Failsafe: Never break the Antigravity agent lifecycle
        pass

    # Strictly output valid JSON to stdout as required by the Antigravity hook contract
    print(json.dumps({}))


if __name__ == "__main__":
    main()
