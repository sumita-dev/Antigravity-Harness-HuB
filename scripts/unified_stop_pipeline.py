#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Antigravity 2.0 Lifecycle 'Stop' Hook — Unified In-Process Stop Pipeline.

Optimizes Stop Hook execution latency on Antigravity 2.0 by combining:
1. auto_harvest_global.harvest_from_transcript (pattern learning)
2. enforce_anti_hallucination_hook.evaluate_hook_payload (anti-hallucination / DoD)
3. verify_before_handoff_hook.evaluate_hook_payload (pre-handoff verification)
4. enforce_triad_process_hook.evaluate_hook_payload (triad protocol guard)

All four gates execute in-process with a SINGLE in-memory transcript parse,
eliminating redundant subprocess spawns, repeated JSON disk reads, and process startup latency.
Returns the first blocking decision ("continue") or {"decision": "allow"}.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
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

from scripts import auto_harvest_global  # noqa: E402
from scripts import enforce_anti_hallucination_hook  # noqa: E402
from scripts import enforce_triad_process_hook  # noqa: E402
from scripts import verify_before_handoff_hook  # noqa: E402

DEFAULT_MAX_RETRIES = 2


def parse_transcript_once(transcript_path: Path | str) -> list[dict[str, Any]]:
    """Parse transcript.jsonl into a list of step dictionaries once in memory."""
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


class SingleTranscriptContext:
    """Context manager binding in-memory parsed steps to all four hooks."""

    def __init__(self, target_path_str: str, parsed_steps: list[dict[str, Any]]):
        self.target_path_str = target_path_str
        try:
            self.resolved_target = str(Path(target_path_str).resolve()) if target_path_str else ""
        except Exception:
            self.resolved_target = target_path_str
        self.parsed_steps = parsed_steps
        self.orig_harv = auto_harvest_global.parse_transcript
        self.orig_anti = enforce_anti_hallucination_hook.parse_transcript
        self.orig_veri = verify_before_handoff_hook.parse_transcript
        self.orig_triad = enforce_triad_process_hook.parse_transcript

    def __enter__(self) -> SingleTranscriptContext:
        def _cached_parse(p: Any) -> list[dict[str, Any]]:
            try:
                p_str = str(Path(p).resolve())
                if p_str == self.resolved_target:
                    return self.parsed_steps
            except Exception:
                if str(p) == self.target_path_str:
                    return self.parsed_steps
            return parse_transcript_once(p)

        auto_harvest_global.parse_transcript = _cached_parse
        enforce_anti_hallucination_hook.parse_transcript = _cached_parse
        verify_before_handoff_hook.parse_transcript = _cached_parse
        enforce_triad_process_hook.parse_transcript = _cached_parse
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        auto_harvest_global.parse_transcript = self.orig_harv
        enforce_anti_hallucination_hook.parse_transcript = self.orig_anti
        verify_before_handoff_hook.parse_transcript = self.orig_veri
        enforce_triad_process_hook.parse_transcript = self.orig_triad


def run_unified_stop_pipeline(
    payload: dict[str, Any],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, str]:
    """Execute the unified stop hook pipeline in-process with a single transcript parse."""
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

    # Parse transcript once in memory
    t_path = Path(transcript_path)
    steps = parse_transcript_once(t_path)
    if not steps:
        return {"decision": "allow"}

    with SingleTranscriptContext(transcript_path, steps):
        # 1. Harvest global code patterns (failsafe, non-blocking)
        try:
            conv_id = str(payload.get("conversationId") or "")
            auto_harvest_global.harvest_from_transcript(t_path, conversation_id=conv_id)
        except Exception:
            pass

        # 2. Enforce Anti-Hallucination & Definition of Done Guard
        try:
            anti_res = enforce_anti_hallucination_hook.evaluate_hook_payload(
                payload,
                max_retries=max_retries,
            )
            if isinstance(anti_res, dict) and anti_res.get("decision") not in (None, "allow"):
                return anti_res
        except Exception:
            pass

        # 3. Enforce Pre-Handoff Verification Gate (CleanState & Targeted Tests)
        try:
            veri_res = verify_before_handoff_hook.evaluate_hook_payload(
                payload,
                max_retries=max_retries,
            )
            if isinstance(veri_res, dict) and veri_res.get("decision") not in (None, "allow"):
                return veri_res
        except Exception:
            pass

        # 4. Enforce SubAgent Triad Process Gate
        try:
            triad_res = enforce_triad_process_hook.evaluate_hook_payload(
                payload,
                max_retries=max_retries,
            )
            if isinstance(triad_res, dict) and triad_res.get("decision") not in (None, "allow"):
                return triad_res
        except Exception:
            pass

    return {"decision": "allow"}


def main() -> None:
    """CLI and Antigravity Stop Hook entry point."""
    result: dict[str, str] = {"decision": "allow"}
    try:
        parser = argparse.ArgumentParser(
            description="Antigravity Unified In-Process Stop Hook Pipeline"
        )
        parser.add_argument("--transcript", "-t", type=str, help="Direct path to transcript.jsonl")
        parser.add_argument("--base-dir", "-b", type=str, default="", help="Base workspace directory")
        parser.add_argument(
            "--max-retries",
            "-r",
            type=int,
            default=DEFAULT_MAX_RETRIES,
            help="Circuit breaker max retries",
        )
        args, _ = parser.parse_known_args()

        payload: dict[str, Any] = {}
        if args.transcript:
            payload = {
                "transcriptPath": args.transcript,
                "workspacePaths": [args.base_dir] if args.base_dir else [],
                "terminationReason": "NO_TOOL_CALL",
            }
        elif not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input and raw_input.strip():
                try:
                    payload = json.loads(raw_input)
                except Exception:
                    payload = {}

        if payload:
            result = run_unified_stop_pipeline(payload, max_retries=args.max_retries)
    except Exception:
        result = {"decision": "allow"}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
