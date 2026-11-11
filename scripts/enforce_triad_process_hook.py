#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# noqa: debug-artifact-file
"""Antigravity 2.0 Lifecycle 'Stop' Hook — Dynamic Triad & SubAgent Process Gate.

Enforces Chief Orchestrator coordination invariants at Stop time using pure Python stdlib:
1. Check 1 (Mandatory SubAgent Delegation — Rule 1.6 / VULN-01A):
   Blocks Root Orchestrator direct mutations on non-exempt repository/project files
   when zero `invoke_subagent` calls were made in the current turn.
   Exempts SubAgent sessions (`Builder`, `Creator`, `QA`), artifact directories (`brain/`),
   Obsidian Second Brain (`Obsidian/`, `wiki/`, `memory/`), and `.brain/`.
2. Reactive Wakeup & Human Gate Preservation (Rules 1.5, 1.10, 1.16):
   Immediately returns `{"decision": "allow"}` when `fullyIdle is False`, when any
   `invoke_subagent` call is awaiting Reactive Wakeup, or when the latest planner step
   calls `ask_question`.
3. Check 2 (Dynamic Triad Completeness & SubAgent Lifecycle Closure — Rules 1.1, 1.17 / VULN-01B):
   - App Maker (`Builder`/`Maker`/`Coder`/`Implementer`) requires `Code Critic` + `QA Auditor`
     (or `QA Auditor` on explicit Tier-2 / Fast-Track / Hotfix turns).
   - Marketing Creator (`Creator`/`Scriptwriter`/`Copywriter`/`Writer`) requires
     `Web Researcher` + `Compliance Critic`.
   - Any turn with completed `invoke_subagent` calls must invoke
     `manage_subagents(Action="kill_all")` at or after the last `invoke_subagent` step.
4. Circuit Breaker (`max_retries = 2`):
   Allows stop when `executionNum > max_retries` or `[TRIAD-PROCESS-GATE]` count in turn
   reaches `max_retries` to prevent infinite loops.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
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

GUARD_MARKER = "[TRIAD-PROCESS-GATE]"
OTHER_HOOK_MARKERS = (
    GUARD_MARKER,
    "[ANTI-HALLUCINATION-GUARD]",
    "[PRE-HANDOFF-GATE]",
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
)

SUBAGENT_HEADER_MARKERS = (
    "# FIXED PREFIX:",
    "SYSTEM INVARIANTS & ROLE SPECIFICATION",
    "You are the **",
    "<subagent_reminder>",
)

EXEC_CRITIC_RE = re.compile(
    r"\b(?:code[\s_-]*critic|compliance[\s_-]*critic|critic|code[\s_-]*reviewer)\b",
    re.IGNORECASE,
)
QA_AUDITOR_RE = re.compile(
    r"\b(?:qa[\s_-]*auditor|qa|auditor|checker|verifier)\b",
    re.IGNORECASE,
)
APP_MAKER_RE = re.compile(
    r"\b(?:builder|maker|coder|implementer|developer)\b",
    re.IGNORECASE,
)
MKT_CREATOR_RE = re.compile(
    r"\b(?:creator|scriptwriter|copywriter|writer)\b",
    re.IGNORECASE,
)
RESEARCHER_RE = re.compile(
    r"\b(?:researcher|web[\s_-]*researcher|scout|architect)\b",
    re.IGNORECASE,
)
TIER2_FAST_TRACK_RE = re.compile(
    r"\b(?:tier[\s_-]*2|fast[\s_-]*track|hotfix)\b",
    re.IGNORECASE,
)
YOU_ARE_LINE_RE = re.compile(r"(?im)^\s*you\s+are\b[^\r\n]*")
FIXED_PREFIX_BLOCK_RE = re.compile(
    r"#\s*FIXED\s+PREFIX:.*?(?=#\s*VARIABLE\s+TASK\s+BRIEF:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
PATCH_FILE_HEADER_RE = re.compile(
    r"(?m)^(?:\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*|(?:\+\+\+|---)\s+[ab]/)([^\r\n]+)"
)


def _clean_arg_val(val: Any) -> str:
    """Unwrap plain strings and double-encoded JSON string arguments from Antigravity transcripts."""
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
    """Normalize tool call arguments whether stored as a dict or JSON-encoded string."""
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


def _normalize_tool_name(raw_name: Any) -> str:
    """Normalize tool name, stripping optional namespace prefixes like `default_api:`."""
    name = _clean_arg_val(raw_name)
    if ":" in name:
        name = name.rsplit(":", 1)[-1]
    return name.strip()


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
    """Return True if step represents a genuine user prompt rather than system/hook injection."""
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


def _is_planner_step(step: dict[str, Any]) -> bool:
    step_type = str(step.get("type") or "")
    role = str(step.get("role") or "")
    return step_type == "PLANNER_RESPONSE" or role in ("assistant", "model")


def is_subagent_session(
    steps: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
) -> bool:
    """Detect whether the current session belongs to an invoked SubAgent rather than Root Orchestrator."""
    if isinstance(payload, dict):
        if payload.get("isSubagent") or payload.get("is_subagent"):
            return True
        parent_id = _clean_arg_val(
            payload.get("parentConversationId") or payload.get("parent_conversation_id")
        )
        if parent_id:
            return True

    if not steps:
        return False

    first_step = steps[0]
    first_type = str(first_step.get("type") or "")
    first_source = str(first_step.get("source") or "")
    first_content = str(first_step.get("content") or "")
    if (first_type == "SYSTEM_MESSAGE" or first_source == "SYSTEM") and (
        "[Message]" in first_content and "sender=" in first_content
    ):
        return True

    checked_user = False
    for step in steps:
        if _is_planner_step(step):
            break
        s_type = str(step.get("type") or "")
        s_source = str(step.get("source") or "")
        s_content = str(step.get("content") or "")
        if s_type == "SYSTEM_MESSAGE" or s_source == "SYSTEM":
            if any(m in s_content for m in SUBAGENT_HEADER_MARKERS):
                return True
        elif s_type == "USER_INPUT" or s_source == "USER_EXPLICIT":
            if not checked_user:
                checked_user = True
                if any(m in s_content for m in SUBAGENT_HEADER_MARKERS):
                    return True

    return False


def is_exempt_orchestrator_path(
    raw_path: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Return True if a file path is legitimately writable by Root Orchestrator (artifacts, Obsidian, .brain)."""
    cleaned = _clean_arg_val(raw_path)
    if not cleaned:
        return True

    if cleaned.lower().startswith("file:///"):
        cleaned = cleaned[8:]
    elif cleaned.lower().startswith("file://"):
        cleaned = cleaned[7:]

    cleaned = urllib.parse.unquote(cleaned).strip()
    if not cleaned:
        return True

    expanded = os.path.expanduser(cleaned)
    norm = expanded.replace("\\", "/")
    norm_low = norm.lower()

    basename_low = Path(norm).name.lower()
    if basename_low in EXEMPT_BASENAMES:
        return True

    padded = "/" + norm_low.lstrip("/")
    if any(seg in padded for seg in EXEMPT_PATH_SEGMENTS):
        return True

    if isinstance(payload, dict):
        art_dir = _clean_arg_val(
            payload.get("artifactDirectoryPath") or payload.get("artifact_directory_path")
        )
        if art_dir:
            art_norm = os.path.expanduser(art_dir).replace("\\", "/").rstrip("/").lower()
            if art_norm and (norm_low == art_norm or norm_low.startswith(art_norm + "/")):
                return True

    obs_candidates: list[str] = []
    env_obs = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if env_obs:
        obs_candidates.append(env_obs)
    try:
        obs_candidates.append(str(Path.home() / "Obsidian"))
    except Exception:
        pass

    for cand in obs_candidates:
        cand_norm = os.path.expanduser(cand).replace("\\", "/").rstrip("/").lower()
        if cand_norm and (norm_low == cand_norm or norm_low.startswith(cand_norm + "/")):
            return True

    return False


def _extract_mutation_paths(tc_name: str, tc_args: dict[str, Any]) -> list[str]:
    """Extract target file paths from a file-mutation tool call."""
    paths: list[str] = []
    for key in ("Path", "path", "TargetFile", "target_file", "FilePath", "file_path", "filename"):
        if key in tc_args:
            val = _clean_arg_val(tc_args.get(key))
            if val and val not in paths:
                paths.append(val)

    if not paths and tc_name in ("apply_patch", "patch_file"):
        patch_body = _clean_arg_val(
            tc_args.get("Patch")
            or tc_args.get("patch")
            or tc_args.get("Diff")
            or tc_args.get("diff")
            or tc_args.get("Content")
            or tc_args.get("content")
        )
        if patch_body:
            for m in PATCH_FILE_HEADER_RE.finditer(patch_body):
                cand = m.group(1).strip()
                if cand and cand not in paths:
                    paths.append(cand)
        if not paths:
            paths.append("<unscoped_patch>")

    return paths


def _extract_step_tool_calls(step: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return normalized `(tool_name, args_dict)` pairs from a step."""
    calls: list[tuple[str, dict[str, Any]]] = []
    raw_calls = step.get("tool_calls")
    if isinstance(raw_calls, list):
        for tc in raw_calls:
            if not isinstance(tc, dict):
                continue
            fn_obj = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            raw_name = tc.get("name") or tc.get("tool") or fn_obj.get("name") or ""
            tc_name = _normalize_tool_name(raw_name)
            raw_args = (
                tc.get("args")
                if "args" in tc
                else tc.get("arguments")
                if "arguments" in tc
                else tc.get("input")
                if "input" in tc
                else tc.get("parameters")
                if "parameters" in tc
                else fn_obj.get("arguments")
            )
            tc_args = _parse_args_dict(raw_args)
            if tc_name:
                calls.append((tc_name, tc_args))
    return calls


def _step_text(step: dict[str, Any]) -> str:
    """Combine output/content fields of a tool or system step."""
    chunks: list[str] = []
    for key in ("content", "output", "stdout", "stderr", "result", "response", "message"):
        val = step.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val.strip())
    embedded = step.get("tool_results") or step.get("tool_responses")
    if isinstance(embedded, list):
        for item in embedded:
            if isinstance(item, dict):
                for key in ("content", "output", "result"):
                    v = item.get(key)
                    if isinstance(v, str) and v.strip():
                        chunks.append(v.strip())
    return "\n".join(chunks)


def _is_spawn_ack_text(text: str) -> bool:
    low = text.lower()
    return (
        "created the following subagent" in low
        or "will send you a message when it has completed" in low
    )


def _has_wakeup_message_after(turn_steps: list[dict[str, Any]], inv_idx: int) -> bool:
    """Return True if a SubAgent Reactive Wakeup SYSTEM_MESSAGE arrives after `inv_idx`."""
    for step in turn_steps[inv_idx + 1 :]:
        s_type = str(step.get("type") or "")
        s_source = str(step.get("source") or "")
        s_content = str(step.get("content") or "")
        if (s_type == "SYSTEM_MESSAGE" or s_source == "SYSTEM") and "[Message]" in s_content:
            if not any(m in s_content for m in OTHER_HOOK_MARKERS):
                return True
    return False


def _is_invocation_awaiting_wakeup(turn_steps: list[dict[str, Any]], inv_idx: int) -> bool:
    """Determine if an `invoke_subagent` call at `inv_idx` is still awaiting Reactive Wakeup."""
    inv_step = turn_steps[inv_idx]
    embedded = inv_step.get("tool_results") or inv_step.get("tool_responses")
    has_embedded_result = isinstance(embedded, list) and len(embedded) > 0

    following_steps = turn_steps[inv_idx + 1 :]
    if not following_steps and not has_embedded_result:
        return True

    immediate_texts: list[str] = []
    if has_embedded_result:
        immediate_texts.append(_step_text(inv_step))

    for step in following_steps:
        if _is_planner_step(step):
            break
        s_type = str(step.get("type") or "")
        s_source = str(step.get("source") or "")
        if s_type == "SYSTEM_MESSAGE" or s_source == "SYSTEM":
            break
        txt = _step_text(step)
        if txt:
            immediate_texts.append(txt)

    if not immediate_texts and not _has_wakeup_message_after(turn_steps, inv_idx):
        return True

    combined_immediate = "\n".join(immediate_texts)
    if _is_spawn_ack_text(combined_immediate) and not _has_wakeup_message_after(turn_steps, inv_idx):
        return True

    return False


def classify_subagent_role(tc_args: dict[str, Any]) -> dict[str, Any]:
    """Classify an `invoke_subagent` call primarily via cleaned `(Role, TypeName, AgentName)`."""
    role_str = _clean_arg_val(tc_args.get("Role") or tc_args.get("role"))
    type_name = _clean_arg_val(
        tc_args.get("TypeName") or tc_args.get("type_name") or tc_args.get("SubagentType")
    )
    agent_name = _clean_arg_val(
        tc_args.get("AgentName")
        or tc_args.get("agent_name")
        or tc_args.get("Name")
        or tc_args.get("name")
    )
    prompt_str = _clean_arg_val(tc_args.get("Prompt") or tc_args.get("prompt"))

    parts = [p for p in (role_str, type_name, agent_name) if p]
    if not role_str and not agent_name and prompt_str:
        m = YOU_ARE_LINE_RE.search(prompt_str)
        if m:
            parts.append(m.group(0).strip())

    header_text = " ".join(parts).strip()

    is_exec_critic = bool(EXEC_CRITIC_RE.search(header_text))
    is_qa = bool(QA_AUDITOR_RE.search(header_text))
    is_app_maker = bool(APP_MAKER_RE.search(header_text)) and not (is_exec_critic or is_qa)
    is_mkt_creator = bool(MKT_CREATOR_RE.search(header_text)) and not (is_exec_critic or is_qa)
    is_researcher = (type_name.lower() == "research") or bool(RESEARCHER_RE.search(header_text))

    return {
        "role": role_str,
        "type_name": type_name,
        "agent_name": agent_name,
        "header_text": header_text,
        "is_exec_critic": is_exec_critic,
        "is_qa": is_qa,
        "is_app_maker": is_app_maker,
        "is_mkt_creator": is_mkt_creator,
        "is_researcher": is_researcher,
    }


def evaluate_transcript(
    transcript_path: Path | str,
    *,
    payload: dict[str, Any] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    execution_num: int = 0,
    termination_reason: str = "",
) -> dict[str, str]:
    """Evaluate a transcript JSONL file and return the Triad Process Gate decision."""
    eff_payload = payload if isinstance(payload, dict) else {}

    if eff_payload.get("fullyIdle") is False:
        return {"decision": "allow"}

    if termination_reason not in ("", "NO_TOOL_CALL"):
        return {"decision": "allow"}

    if execution_num >= max_retries + 1:
        return {"decision": "allow"}

    steps = parse_transcript(transcript_path)
    if not steps:
        return {"decision": "allow"}

    if is_subagent_session(steps, eff_payload):
        return {"decision": "allow"}

    last_user_idx = -1
    for idx, step in enumerate(steps):
        if _is_genuine_user_step(step):
            last_user_idx = idx

    turn_steps = steps[last_user_idx + 1 :] if last_user_idx >= 0 else list(steps)
    if not turn_steps:
        return {"decision": "allow"}

    retry_count = 0
    last_planner_step: dict[str, Any] | None = None
    non_exempt_mutations: list[str] = []
    subagent_invocations: list[tuple[int, dict[str, Any]]] = []
    schedule_without_bg_cmd_steps: list[int] = []
    last_kill_all_idx = -1
    tier2_text_fragments: list[str] = []

    if last_user_idx >= 0:
        user_prompt = str(steps[last_user_idx].get("content") or "")
        if user_prompt.strip():
            tier2_text_fragments.append(user_prompt)

    for step_idx, step in enumerate(turn_steps):
        is_planner = _is_planner_step(step)
        content = str(step.get("content") or "")
        reason = str(step.get("reason") or "")
        message = str(step.get("message") or "")

        if not is_planner:
            combined_meta = f"{content}\n{reason}\n{message}"
            if GUARD_MARKER in combined_meta:
                retry_count += 1
        else:
            last_planner_step = step
            if content.strip():
                tier2_text_fragments.append(content)

        step_tcs = _extract_step_tool_calls(step)
        step_tc_names = {name for name, _ in step_tcs}
        if "schedule" in step_tc_names and "run_command" not in step_tc_names:
            schedule_without_bg_cmd_steps.append(step_idx)

        for tc_name, tc_args in step_tcs:
            if tc_name in MUTATION_TOOL_NAMES:
                for p in _extract_mutation_paths(tc_name, tc_args):
                    if not is_exempt_orchestrator_path(p, eff_payload):
                        if p not in non_exempt_mutations:
                            non_exempt_mutations.append(p)
            elif tc_name == "invoke_subagent":
                subagent_invocations.append((step_idx, tc_args))
                role_val = _clean_arg_val(tc_args.get("Role") or tc_args.get("role"))
                if role_val:
                    tier2_text_fragments.append(role_val)
                prompt_val = _clean_arg_val(tc_args.get("Prompt") or tc_args.get("prompt"))
                if prompt_val:
                    stripped_prompt = FIXED_PREFIX_BLOCK_RE.sub("", prompt_val)
                    tier2_text_fragments.append(stripped_prompt)
            elif tc_name == "manage_subagents":
                action_val = _clean_arg_val(tc_args.get("Action") or tc_args.get("action"))
                if action_val.lower() == "kill_all":
                    last_kill_all_idx = step_idx

        step_tool = _normalize_tool_name(step.get("tool") or step.get("name") or "")
        if step_tool in MUTATION_TOOL_NAMES:
            for p in _extract_mutation_paths(step_tool, step):
                if not is_exempt_orchestrator_path(p, eff_payload) and p not in non_exempt_mutations:
                    non_exempt_mutations.append(p)

    # Exemption (d): Last PLANNER_RESPONSE invokes ask_question (Human Gate / Intent Alignment)
    if last_planner_step is not None:
        last_calls = _extract_step_tool_calls(last_planner_step)
        if any(name == "ask_question" for name, _ in last_calls):
            return {"decision": "allow"}

    # Escalation marker check: if [ESCALATED_HARD_STOP] already appeared, allow turn closure
    has_escalated_hard_stop = any(
        "[ESCALATED_HARD_STOP]" in f"{s.get('content') or ''}\n{s.get('reason') or ''}\n{s.get('message') or ''}\n{s.get('system_instruction') or ''}"
        for s in turn_steps
    )
    if has_escalated_hard_stop:
        return {"decision": "allow"}

    if execution_num > max_retries or retry_count >= max_retries:
        return {
            "decision": "continue",
            "reason": (
                f"[ESCALATED_HARD_STOP] Cầu dao ngắt mạch Dynamic Triad đã kích hoạt sau {max_retries} lần cảnh báo. "
                "Khóa toàn bộ quyền tự trị. Yêu cầu Quản đốc xuất trình báo cáo vi phạm trực tiếp cho Sếp."
            ),
            "system_instruction": (
                f"[ESCALATED_HARD_STOP] Cầu dao ngắt mạch Dynamic Triad đã kích hoạt sau {max_retries} lần cảnh báo. "
                "Khóa toàn bộ quyền tự trị. Yêu cầu Quản đốc xuất trình báo cáo vi phạm trực tiếp cho Sếp."
            ),
        }

    # Check 1 (VULN-01A): Direct code/project file mutation by Root Orchestrator with 0 subagents
    if non_exempt_mutations and len(subagent_invocations) == 0:
        sample = ", ".join(Path(p).name if p != "<unscoped_patch>" else p for p in non_exempt_mutations[:3])
        return {
            "decision": "continue",
            "reason": (
                f"{GUARD_MARKER} Vi phạm Quy tắc 1.6 (Mandatory SubAgent Delegation): "
                f"Quản đốc đã trực tiếp chỉnh sửa tệp dự án ({sample}) mà không phân quyền "
                "qua `invoke_subagent`. Yêu cầu thực thi đúng chu trình Dynamic Triad "
                "(Maker -> Critic -> QA Auditor) và dọn dẹp bằng `manage_subagents(Action='kill_all')`."
            ),
        }

    # Reactive Wakeup Gate (Rule 1.10)
    if len(subagent_invocations) == 0:
        return {"decision": "allow"}

    if any(_is_invocation_awaiting_wakeup(turn_steps, inv_idx) for inv_idx, _ in subagent_invocations):
        return {"decision": "allow"}

    # Check 2 (VULN-01B): Completed SubAgent Triad completeness & Rule 17 kill_all closure
    classified = [classify_subagent_role(tc_args) for _, tc_args in subagent_invocations]
    has_app_maker = any(c["is_app_maker"] for c in classified)
    has_mkt_creator = any(c["is_mkt_creator"] for c in classified)
    has_exec_critic = any(c["is_exec_critic"] for c in classified)
    has_qa = any(c["is_qa"] for c in classified)
    has_researcher = any(c["is_researcher"] for c in classified)

    is_tier2 = bool(TIER2_FAST_TRACK_RE.search("\n".join(tier2_text_fragments)))

    missing_roles: list[str] = []
    if has_app_maker:
        if not is_tier2 and not has_exec_critic:
            missing_roles.append("Code Critic")
        if not has_qa:
            missing_roles.append("QA Auditor")

    if has_mkt_creator:
        if not has_researcher:
            missing_roles.append("Web Researcher")
        if not has_exec_critic:
            missing_roles.append("Compliance Critic")

    last_subagent_invoke_idx = subagent_invocations[-1][0]
    kill_all_missing = last_kill_all_idx < last_subagent_invoke_idx

    # Check 2b (BUG-08): Chronological ordering (post-QA/Critic Maker mutations),
    # Rule 1.11 (Explicit Model Tiering), and Rule 1.10 (schedule timer alongside SubAgent)
    unreviewed_maker_violations: list[str] = []
    last_app_maker_pos = max((i for i, c in enumerate(classified) if c["is_app_maker"]), default=-1)
    last_exec_critic_pos = max((i for i, c in enumerate(classified) if c["is_exec_critic"]), default=-1)
    last_qa_pos = max((i for i, c in enumerate(classified) if c["is_qa"]), default=-1)
    last_mkt_creator_pos = max((i for i, c in enumerate(classified) if c["is_mkt_creator"]), default=-1)

    if has_app_maker and not missing_roles:
        if (not is_tier2 and last_exec_critic_pos < last_app_maker_pos) or (last_qa_pos < last_app_maker_pos):
            unreviewed_maker_violations.append(
                "Vi phạm thứ tự Dynamic Triad (Rule 1.1): Lần gọi Builder/Maker cuối cùng diễn ra SAU Critic/QA Auditor và chưa được thẩm định lại"
            )
    if has_mkt_creator and not missing_roles:
        if last_exec_critic_pos < last_mkt_creator_pos:
            unreviewed_maker_violations.append(
                "Vi phạm thứ tự Dynamic Marketing Triad (Rule 3): Lần gọi Creator cuối cùng diễn ra SAU Compliance Critic và chưa được thẩm định lại"
            )

    model_tier_violations: list[str] = []
    for (_, tc_args), c in zip(subagent_invocations, classified):
        model_val = _clean_arg_val(tc_args.get("Model") or tc_args.get("model")).lower()
        if (c["is_exec_critic"] or c["is_qa"]) and model_val == "inherit":
            role_label = c["role"] or "Critic/QA"
            model_tier_violations.append(
                f"Vi phạm Quy tắc 1.11 (Explicit Model Tiering): Cấm dùng Model='inherit' cho {role_label}"
            )

    schedule_violations: list[str] = []
    if schedule_without_bg_cmd_steps and len(subagent_invocations) > 0:
        schedule_violations.append(
            "Vi phạm Quy tắc 1.10 (Zero-Polling): Cấm gọi `schedule` timer khi kích hoạt `invoke_subagent`"
        )

    if unreviewed_maker_violations or model_tier_violations or schedule_violations:
        block_issues = unreviewed_maker_violations + model_tier_violations + schedule_violations
        if missing_roles:
            block_issues.append(
                f"Thiếu bước kiểm định độc lập bắt buộc trong Dynamic Triad: {', '.join(missing_roles)}"
            )
        if kill_all_missing:
            block_issues.append(
                "Chưa gọi `manage_subagents(Action='kill_all')` sau khi SubAgent hoàn tất (Quy tắc 1.17)"
            )
        return {
            "decision": "block",
            "reason": (
                f"{GUARD_MARKER} Phát hiện vi phạm nghiêm trọng quy trình Dynamic Triad: "
                f"{'; '.join(block_issues)}."
            ),
        }

    if missing_roles or kill_all_missing:
        issues: list[str] = []
        if missing_roles:
            issues.append(
                f"Thiếu bước kiểm định độc lập bắt buộc trong Dynamic Triad: {', '.join(missing_roles)}"
            )
        if kill_all_missing:
            issues.append(
                "Chưa gọi `manage_subagents(Action='kill_all')` sau khi SubAgent hoàn tất (Quy tắc 1.17)"
            )
        return {
            "decision": "continue",
            "reason": (
                f"{GUARD_MARKER} Phát hiện vi phạm quy trình điều phối tác tử: "
                f"{'; '.join(issues)}. Yêu cầu hoàn tất đầy đủ các bước còn thiếu trước khi bàn giao."
            ),
        }

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
    if termination_reason not in ("", "NO_TOOL_CALL"):
        return {"decision": "allow"}

    try:
        execution_num = int(payload.get("executionNum") or 0)
    except (TypeError, ValueError):
        execution_num = 0

    if execution_num >= max_retries + 1:
        return {"decision": "allow"}

    if is_subagent_session([], payload):
        return {"decision": "allow"}

    transcript_path = payload.get("transcriptPath")
    if not transcript_path or not isinstance(transcript_path, str):
        return {"decision": "allow"}

    return evaluate_transcript(
        transcript_path,
        payload=payload,
        max_retries=max_retries,
        execution_num=execution_num,
        termination_reason=termination_reason,
    )


def main() -> None:
    """CLI and Antigravity Stop Hook entry point."""
    result: dict[str, str] = {"decision": "allow"}
    try:
        parser = argparse.ArgumentParser(
            description="Enforce Dynamic Triad & SubAgent Process Gate on Stop Hook"
        )
        parser.add_argument("--transcript", "-t", type=str, help="Direct path to transcript.jsonl")
        parser.add_argument(
            "--max-retries",
            type=int,
            default=DEFAULT_MAX_RETRIES,
            help="Circuit breaker max retries",
        )
        args, _ = parser.parse_known_args()

        if args.transcript:
            result = evaluate_transcript(
                args.transcript,
                max_retries=args.max_retries,
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
        # Failsafe: never break the Antigravity agent lifecycle
        result = {"decision": "allow"}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
