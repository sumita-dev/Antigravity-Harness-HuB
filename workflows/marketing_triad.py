#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Native Antigravity 2.0 `run_workflow` script for the Marketing Triad (Web Researcher -> Creator -> Compliance Critic).

Invoked via Antigravity `run_workflow` tool:
    run_workflow(
        ScriptPath="<repo>/workflows/marketing_triad.py",
        Description="Execute Marketing Triad (Researcher -> Creator -> Compliance Critic)",
        Args={
            "task": "Write or revise marketing script / content",
            "mode": "pipeline",  # "pipeline" | "research-only" | "revision"
            "max_critique_rounds": 2,
        },
    )

Conventions (per `run-workflow/SKILL.md` and `docs/marketing-workflow-guide.md`):
- Uses `phase()`, `agent(prompt, schema, role, type_name, workspace, model)`, `log()`, and `args`.
- Enforces 4-pillar Compliance Critique (`source_accuracy`, `policy`, `integrity`, `task_quality`).
- Deterministic Circuit Breaker: `max_critique_rounds=2`.
"""

from __future__ import annotations

import json
from typing import Any, Dict

DOSSIER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "dossier_sha256": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "statement": {"type": "string"},
                    "source_url": {"type": "string"},
                    "verified": {"type": "boolean"},
                },
                "required": ["claim_id", "statement", "source_url", "verified"],
            },
        },
        "policy_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "YPP, EDSA, Meta, or platform compliance risks detected.",
        },
        "summary": {"type": "string"},
    },
    "required": ["claims", "policy_risks", "summary"],
}

CREATOR_DRAFT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "mapped_claim_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["content", "mapped_claim_ids", "summary"],
}

MARKETING_CRITIQUE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["APPROVE", "REJECT", "ESCALATE"],
            "description": "Compliance Critic verdict: APPROVE, REJECT, or ESCALATE.",
        },
        "pillars": {
            "type": "object",
            "properties": {
                "source_accuracy": {"type": "string", "enum": ["PASS", "FAIL"]},
                "policy": {"type": "string", "enum": ["PASS", "FAIL"]},
                "integrity": {"type": "string", "enum": ["PASS", "FAIL"]},
                "task_quality": {"type": "string", "enum": ["PASS", "FAIL"]},
            },
            "required": ["source_accuracy", "policy", "integrity", "task_quality"],
        },
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Actionable policy/accuracy/quality findings (required when REJECT).",
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["verdict", "pillars", "findings", "summary"],
}


async def run_marketing_triad(workflow_args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the Marketing Triad pipeline/loop with deterministic circuit breaker."""
    task = str(workflow_args.get("task") or "").strip()
    if not task:
        raise ValueError("Args['task'] is required for workflows/marketing_triad.py")

    mode = str(workflow_args.get("mode") or "pipeline").strip()
    max_critique_rounds = int(workflow_args.get("max_critique_rounds", 2))

    # 1. Web Researcher -> Dossier
    phase("Web Research (Dossier)")
    research_prompt = (
        "Role: Web Researcher.\n"
        "Invariants: Gather verified facts with source URLs, assign claim_ids, "
        "and flag YPP/EDSA/Meta policy risks. Never invent sources.\n"
        f"Mode: {mode}\n\n"
        f"Task:\n{task}"
    )
    dossier = await agent(
        prompt=research_prompt,
        schema=DOSSIER_SCHEMA,
        role="Web Researcher",
        type_name="self",
        workspace="inherit",
        model="inherit",
    )
    log(f"Research Dossier claims={len(dossier.get('claims', []))}")

    if mode == "research-only":
        phase("Compliance Critique (Research-Only)")
        res_critique = await agent(
            prompt=(
                "Role: Compliance Critic (Research-Only Mode).\n"
                "Audit the research dossier across source_accuracy, policy, integrity, and task_quality.\n\n"
                f"Task:\n{task}\n\n"
                f"Dossier:\n{json.dumps(dossier, ensure_ascii=False)}"
            ),
            schema=MARKETING_CRITIQUE_SCHEMA,
            role="Compliance Critic (Research)",
            type_name="self",
            workspace="inherit",
            model="inherit",
        )
        return {
            "final_status": "APPROVED" if res_critique.get("verdict") == "APPROVE" else "ESCALATED",
            "mode": mode,
            "dossier": dossier,
            "critique": res_critique,
        }

    # 2. Stateful Creator handle -> Draft mapped to Dossier claim IDs
    phase("Content Creation (Creator)")
    creator = agent(
        role="Content Creator",
        type_name="self",
        workspace="inherit",
        model="inherit",
    )
    creator_prompt = (
        "Role: Content Creator (Maker).\n"
        "Invariants: Draft or revise content strictly grounded in the Research Dossier. "
        "Map every factual claim to a valid claim_id from the dossier.\n"
        f"Mode: {mode}\n\n"
        f"Task:\n{task}\n\n"
        f"Dossier:\n{json.dumps(dossier, ensure_ascii=False)}"
    )
    draft = await creator(creator_prompt, schema=CREATOR_DRAFT_SCHEMA)
    log(f"Creator draft ready, mapped_claim_ids={draft.get('mapped_claim_ids', [])}")

    # 3. Compliance Critic loop (max_critique_rounds = 2)
    critique: Dict[str, Any] = {}
    for round_idx in range(1, max_critique_rounds + 1):
        phase(f"Compliance Critique (Round {round_idx}/{max_critique_rounds})")
        critic_prompt = (
            "Role: Compliance Critic (Independent Reviewer).\n"
            "Audit the Creator draft against the Dossier across all 4 pillars: "
            "source_accuracy, policy, integrity, task_quality.\n"
            "If REJECT, provide non-empty actionable findings.\n\n"
            f"Task:\n{task}\n\n"
            f"Dossier:\n{json.dumps(dossier, ensure_ascii=False)}\n\n"
            f"Draft:\n{json.dumps(draft, ensure_ascii=False)}"
        )
        critique = await agent(
            prompt=critic_prompt,
            schema=MARKETING_CRITIQUE_SCHEMA,
            role=f"Compliance Critic (R{round_idx})",
            type_name="self",
            workspace="inherit",
            model="inherit",
        )
        log(f"Compliance Critic R{round_idx} verdict: {critique.get('verdict')}")

        if critique.get("verdict") == "APPROVE":
            result = {
                "final_status": "APPROVED",
                "mode": mode,
                "dossier": dossier,
                "draft": draft,
                "critique": critique,
            }
            log(f"Marketing Triad APPROVED: {json.dumps(result, ensure_ascii=False)}")
            return result

        if round_idx >= max_critique_rounds or critique.get("verdict") == "ESCALATE":
            result = {
                "final_status": "ESCALATED",
                "mode": mode,
                "rounds_used": round_idx,
                "dossier": dossier,
                "draft": draft,
                "critique": critique,
            }
            log(f"Circuit breaker triggered at Compliance Critique: {json.dumps(result, ensure_ascii=False)}")
            return result

        phase(f"Creator Revision (Round {round_idx})")
        rev_prompt = (
            "Role: Content Creator (Maker) — Revision.\n"
            "Fix every finding raised by Compliance Critic while keeping all claims grounded in the Dossier.\n\n"
            f"Dossier:\n{json.dumps(dossier, ensure_ascii=False)}\n\n"
            f"Previous Draft:\n{json.dumps(draft, ensure_ascii=False)}\n\n"
            f"Critic Findings:\n{json.dumps(critique, ensure_ascii=False)}"
        )
        draft = await creator(rev_prompt, schema=CREATOR_DRAFT_SCHEMA)

    return {"final_status": "ESCALATED", "stage": "UNKNOWN"}


result = await run_marketing_triad(args if "args" in globals() else {})
print(json.dumps(result, ensure_ascii=False))
