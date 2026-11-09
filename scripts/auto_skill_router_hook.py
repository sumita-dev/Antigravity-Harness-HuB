#!/usr/bin/env python3
"""Antigravity 2.0 Lifecycle 'PreInvocation' Hook — Automatic Skill Routing & SubAgent Triad Injection.

Reads the Antigravity `PreInvocation` hook JSON payload from `stdin` (or CLI `--prompt`),
routes `lastUserInput` via `SkillRouter` and `SkillLoader`, and injects an ephemeral
routing directive on the first invocation of a user turn (`invocationNum in (None, 0, 1)`):
- Output contract: `{"injectSteps": [{"ephemeralMessage": "..."}], "terminationBehavior": ""}`
- Subsequent invocations in the same turn (`invocationNum > 1`): `{"injectSteps": [], "terminationBehavior": ""}`
- Failsafe: always exits with code 0 and valid JSON output.
"""

from __future__ import annotations

import argparse
import json
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

from harness.skills.router import SkillLoader, SkillRouter  # noqa: E402

ROUTER_MARKER = "[AUTO-SKILL-ROUTER]"

APP_TRIAD_SPEC = "Maker/Builder (pro) -> Code Critic (flash) -> QA Auditor (flash)"
APP_FULL_TRIAD_SPEC = (
    "Architect (pro) -> Design Reviewer (flash) -> Builder (pro) -> Code Critic (flash) -> QA Auditor (flash)"
)
MARKETING_TRIAD_SPEC = "Web Researcher (pro) -> Creator (pro) -> Compliance Critic (flash)"


def resolve_triad_spec(branch: str, skill: str | None = None) -> str:
    """Return the mandatory SubAgent Triad & Model Tiering specification for the routed branch."""
    if branch == "marketing":
        return MARKETING_TRIAD_SPEC
    if skill == "app":
        return APP_FULL_TRIAD_SPEC
    return APP_TRIAD_SPEC


def route_user_prompt(
    user_input: str,
    *,
    router: SkillRouter | None = None,
    loader: SkillLoader | None = None,
) -> dict[str, Any]:
    """Route a user prompt to (skill, branch, skill_path, triad_spec)."""
    r = router or SkillRouter()
    l = loader or SkillLoader()
    matched_skill, branch = r.route(user_input)
    skill_path = l.find_skill_path(matched_skill) if matched_skill else None
    normalized_path = Path(skill_path).as_posix() if skill_path else None
    triad_spec = resolve_triad_spec(branch, matched_skill)
    return {
        "branch": branch,
        "skill": matched_skill,
        "skill_path": normalized_path,
        "triad": triad_spec,
    }


def evaluate_pre_invocation_payload(
    payload: dict[str, Any],
    *,
    router: SkillRouter | None = None,
    loader: SkillLoader | None = None,
) -> dict[str, Any]:
    """Evaluate an Antigravity PreInvocation JSON payload and return the hook response."""
    empty_response: dict[str, Any] = {"injectSteps": [], "terminationBehavior": ""}
    if not isinstance(payload, dict):
        return empty_response

    raw_inv = payload.get("invocationNum")
    if raw_inv is not None:
        try:
            inv_num = int(raw_inv)
        except (TypeError, ValueError):
            inv_num = 1
        if inv_num > 1:
            return empty_response

    user_input = str(payload.get("lastUserInput") or "").strip()
    if not user_input:
        return empty_response

    route_info = route_user_prompt(user_input, router=router, loader=loader)
    branch = route_info["branch"]
    skill = route_info["skill"] or "none"
    skill_path = route_info["skill_path"] or "none"
    triad = route_info["triad"]

    if route_info["skill"] and route_info["skill_path"]:
        directive = (
            f"Activated skill '{skill}' ({skill_path}). "
            f"Read SKILL.md or delegate via Dynamic Triad [{triad}]."
        )
    else:
        directive = f"No specific skill keyword matched; follow branch '{branch}' Dynamic Triad [{triad}]."

    ephemeral_msg = (
        f"{ROUTER_MARKER} branch={branch} | skill={skill} | "
        f"skill_path={skill_path} | triad={triad} | directive={directive}"
    )
    return {
        "injectSteps": [{"ephemeralMessage": ephemeral_msg}],
        "terminationBehavior": "",
    }


def main() -> None:
    """CLI and Antigravity PreInvocation Hook entry point."""
    result: dict[str, Any] = {"injectSteps": [], "terminationBehavior": ""}
    try:
        parser = argparse.ArgumentParser(description="Antigravity PreInvocation Auto Skill Router Hook")
        parser.add_argument("--prompt", "-p", type=str, default="", help="Direct user prompt to route")
        parser.add_argument("--invocation-num", "-n", type=int, default=1, help="Invocation number in turn")
        args, _ = parser.parse_known_args()

        if args.prompt:
            result = evaluate_pre_invocation_payload(
                {
                    "lastUserInput": args.prompt,
                    "invocationNum": args.invocation_num,
                }
            )
        elif not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input and raw_input.strip():
                payload = json.loads(raw_input)
                if isinstance(payload, dict):
                    result = evaluate_pre_invocation_payload(payload)
    except Exception:
        result = {"injectSteps": [], "terminationBehavior": ""}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
