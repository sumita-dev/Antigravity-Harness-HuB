#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Native Antigravity 2.0 `run_workflow` script for the App Triad (Maker -> Code Critic -> QA Auditor).

Invoked via Antigravity `run_workflow` tool:
    run_workflow(
        ScriptPath="<repo>/workflows/app_triad.py",
        Description="Execute App Triad (Maker -> Code Critic -> QA Auditor)",
        Args={
            "task": "Implement feature X with unit tests",
            "spec_sha256": "<optional-64-hex-sha256>",
            "max_critique_rounds": 2,
            "max_qa_rounds": 2,
        },
    )

Conventions (per `run-workflow/SKILL.md`):
- Uses `phase()`, `agent(prompt, schema, role, type_name, workspace, model)`, `log()`, and `args`.
- Schemas `CRITIQUE_VERDICT_SCHEMA` and `AUDIT_VERDICT_SCHEMA` are aligned 1:1 with
  `CritiqueVerdictSchema.to_json_schema()` and `AuditVerdictSchema.to_json_schema()` in
  `harness/triad_protocol.py` (inlined here because `run_workflow` scripts cannot import local modules).
- Explicit Model Tiering: Maker (`inherit`, `workspace="share"`), Code Critic (`model="inherit"`),
  QA Auditor (`model="flash"`).
- Deterministic Circuit Breakers: `max_critique_rounds=2`, `max_qa_rounds=2`.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

# Aligned with harness.triad_protocol.CritiqueVerdictSchema.to_json_schema()
CRITIQUE_VERDICT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["APPROVE", "REJECT", "ESCALATE"],
            "description": "Critic verdict: APPROVE, REJECT, or ESCALATE.",
        },
        "summary": {
            "type": "string",
            "description": "Concise summary of the critique.",
        },
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of GAPs, logic flaws, or edge-case findings (required when REJECT).",
        },
        "ac_coverage": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ac_id": {"type": "string"},
                    "status": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["ac_id", "status"],
            },
            "description": "Acceptance criteria coverage mapping.",
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Actionable remediation steps.",
        },
        "spec_sha256": {"type": "string"},
        "manifest_sha256": {"type": "string"},
    },
    "required": ["verdict", "summary", "findings"],
}

# Aligned with harness.triad_protocol.AuditVerdictSchema.to_json_schema()
AUDIT_VERDICT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["APPROVE", "REJECT", "ESCALATE"],
            "description": "QA Auditor verdict: APPROVE, REJECT, or ESCALATE.",
        },
        "summary": {
            "type": "string",
            "description": "Concise summary of the QA audit.",
        },
        "executed_commands": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "exit_code": {"type": "integer"},
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                },
                "required": ["command", "exit_code"],
            },
            "description": "Executed verification commands with exit codes (required with exit_code == 0 when APPROVE).",
        },
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of defects or test failures found.",
        },
        "evidence_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Paths to test logs, screenshots, or reports.",
        },
        "spec_sha256": {"type": "string"},
        "manifest_sha256": {"type": "string"},
    },
    "required": ["verdict", "summary", "executed_commands"],
}

MAKER_HANDOFF_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["READY_FOR_CRITIC", "BLOCKED"]},
        "branch": {"type": "string"},
        "commit_sha": {"type": "string"},
        "modified_files": {"type": "array", "items": {"type": "string"}},
        "test_command": {"type": "string"},
        "test_exit_code": {"type": "integer"},
        "summary": {"type": "string"},
    },
    "required": ["status", "modified_files", "summary"],
}


async def run_app_triad(workflow_args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the App Triad loop with deterministic circuit breakers."""
    task = str(workflow_args.get("task") or "").strip()
    if not task:
        raise ValueError("Args['task'] is required for workflows/app_triad.py")

    spec_sha256 = str(workflow_args.get("spec_sha256") or "")
    max_critique_rounds = int(workflow_args.get("max_critique_rounds", 2))
    max_qa_rounds = int(workflow_args.get("max_qa_rounds", 2))

    # 1. Maker (Builder) in isolated share workspace
    phase("Implementation (Maker)")
    maker_prompt = (
        "Role: App Builder (Maker).\n"
        "Invariants: Follow Karpathy principles, run deterministic tests/linters before handoff, "
        "commit changes on your branch, and never hardcode secrets.\n"
        f"Spec SHA256: {spec_sha256 or 'N/A'}\n\n"
        f"Task:\n{task}"
    )
    maker_handoff = await agent(
        prompt=maker_prompt,
        schema=MAKER_HANDOFF_SCHEMA,
        role="App Builder (Maker)",
        type_name="self",
        workspace="share",
        model="inherit",
    )
    log(f"Maker handoff: {json.dumps(maker_handoff, ensure_ascii=False)}")

    # 2. Code Critic loop (max_critique_rounds = 2)
    critique_verdict: Dict[str, Any] = {}
    for round_idx in range(1, max_critique_rounds + 1):
        phase(f"Code Critique (Round {round_idx}/{max_critique_rounds})")
        critic_prompt = (
            "Role: Code Critic (Independent Reviewer).\n"
            "Invariants: Read full context, verify GAPs, logic, edge cases, and AC coverage. "
            "Do NOT edit code. If REJECT, provide non-empty actionable findings.\n\n"
            f"Task:\n{task}\n\n"
            f"Maker Handoff:\n{json.dumps(maker_handoff, ensure_ascii=False)}"
        )
        critique_verdict = await agent(
            prompt=critic_prompt,
            schema=CRITIQUE_VERDICT_SCHEMA,
            role=f"Code Critic (R{round_idx})",
            type_name="self",
            workspace="inherit",
            model="inherit",
        )
        log(f"Code Critic R{round_idx} verdict: {critique_verdict.get('verdict')}")

        if critique_verdict.get("verdict") == "APPROVE":
            break

        if round_idx >= max_critique_rounds or critique_verdict.get("verdict") == "ESCALATE":
            result = {
                "final_status": "ESCALATED",
                "stage": "CRITIQUE",
                "rounds_used": round_idx,
                "critique": critique_verdict,
            }
            log(f"Circuit breaker triggered at Code Critique: {json.dumps(result, ensure_ascii=False)}")
            return result

        phase(f"Maker Remediation for Critique (Round {round_idx})")
        fix_prompt = (
            "Role: App Builder (Maker) — Remediation.\n"
            "Fix every finding raised by Code Critic, re-run tests, and commit.\n\n"
            f"Critic Findings:\n{json.dumps(critique_verdict, ensure_ascii=False)}"
        )
        maker_handoff = await agent(
            prompt=fix_prompt,
            schema=MAKER_HANDOFF_SCHEMA,
            role=f"App Builder Fix (R{round_idx})",
            type_name="self",
            workspace="share",
            model="inherit",
        )

    # 3. QA Auditor loop (max_qa_rounds = 2, model="flash")
    qa_verdict: Dict[str, Any] = {}
    for qa_idx in range(1, max_qa_rounds + 1):
        phase(f"QA Audit (Round {qa_idx}/{max_qa_rounds})")
        qa_prompt = (
            "Role: QA Auditor (Independent Verifier).\n"
            "Invariants: Rerun test suite deterministically, verify physical paths, zero secrets, "
            "and attach executed_commands with exit_code == 0 for APPROVE.\n\n"
            f"Task:\n{task}\n\n"
            f"Maker Handoff:\n{json.dumps(maker_handoff, ensure_ascii=False)}\n\n"
            f"Code Critic Verdict:\n{json.dumps(critique_verdict, ensure_ascii=False)}"
        )
        qa_verdict = await agent(
            prompt=qa_prompt,
            schema=AUDIT_VERDICT_SCHEMA,
            role=f"QA Auditor (R{qa_idx})",
            type_name="self",
            workspace="inherit",
            model="flash",
        )
        log(f"QA Auditor R{qa_idx} verdict: {qa_verdict.get('verdict')}")

        if qa_verdict.get("verdict") == "APPROVE":
            result = {
                "final_status": "APPROVED",
                "maker_handoff": maker_handoff,
                "critique": critique_verdict,
                "qa_audit": qa_verdict,
            }
            log(f"App Triad APPROVED: {json.dumps(result, ensure_ascii=False)}")
            return result

        if qa_idx >= max_qa_rounds or qa_verdict.get("verdict") == "ESCALATE":
            result = {
                "final_status": "ESCALATED",
                "stage": "QA_AUDIT",
                "rounds_used": qa_idx,
                "qa_audit": qa_verdict,
            }
            log(f"Circuit breaker triggered at QA Audit: {json.dumps(result, ensure_ascii=False)}")
            return result

        phase(f"Maker Remediation for QA (Round {qa_idx})")
        qa_fix_prompt = (
            "Role: App Builder (Maker) — QA Remediation.\n"
            "Fix every test failure or defect reported by QA Auditor and re-run tests.\n\n"
            f"QA Findings:\n{json.dumps(qa_verdict, ensure_ascii=False)}"
        )
        maker_handoff = await agent(
            prompt=qa_fix_prompt,
            schema=MAKER_HANDOFF_SCHEMA,
            role=f"App Builder QA Fix (R{qa_idx})",
            type_name="self",
            workspace="share",
            model="inherit",
        )

    return {"final_status": "ESCALATED", "stage": "UNKNOWN"}


if "agent" in globals() and "phase" in globals():
    _args = globals().get("args", {})
    _coro = run_app_triad(_args)
    try:
        _loop = asyncio.get_running_loop()
        asyncio.ensure_future(_coro)
    except RuntimeError:
        _final = asyncio.run(_coro)
        print(json.dumps(_final, ensure_ascii=False))
