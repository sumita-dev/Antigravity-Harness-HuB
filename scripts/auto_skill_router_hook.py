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

from harness.skills.router import SkillLoader, SkillRouter  # noqa: E402

ROUTER_MARKER = "[AUTO-SKILL-ROUTER]"

DEFAULT_MAKER_MODEL = "inherit"
DEFAULT_CRITIC_MODEL = "inherit"
DEFAULT_QA_MODEL = "flash"


def resolve_triad_spec(
    branch: str,
    skill: str | None = None,
    *,
    maker_model: str | None = None,
    critic_model: str = DEFAULT_CRITIC_MODEL,
    qa_model: str = DEFAULT_QA_MODEL,
) -> str:
    """Return the mandatory SubAgent Triad & Model Tiering specification for the routed branch.

    Accommodates flexible model selection (e.g. inherit, pro, custom) instead of hardcoding (pro) blindly.
    """
    maker = (maker_model or os.environ.get("ANTIGRAVITY_MAKER_MODEL") or DEFAULT_MAKER_MODEL).strip()
    if branch == "marketing":
        return f"Web Researcher ({maker}) -> Creator ({maker}) -> Compliance Critic ({critic_model})"
    if skill == "app":
        return (
            f"Architect ({maker}) -> Design Reviewer ({critic_model}) -> "
            f"Builder ({maker}) -> Code Critic ({critic_model}) -> QA Auditor ({qa_model})"
        )
    return f"Maker/Builder ({maker}) -> Code Critic ({critic_model}) -> QA Auditor ({qa_model})"


APP_TRIAD_SPEC = resolve_triad_spec("app")
APP_FULL_TRIAD_SPEC = resolve_triad_spec("app", "app")
MARKETING_TRIAD_SPEC = resolve_triad_spec("marketing")


def route_user_prompt(
    user_input: str,
    *,
    router: SkillRouter | None = None,
    loader: SkillLoader | None = None,
    maker_model: str | None = None,
) -> dict[str, Any]:
    """Route a user prompt to (skill, branch, skill_path, triad_spec)."""
    r = router or SkillRouter()
    l = loader or SkillLoader()
    matched_skill, branch = r.route(user_input)
    skill_path = l.find_skill_path(matched_skill) if matched_skill else None
    normalized_path = Path(skill_path).as_posix() if skill_path else None
    triad_spec = resolve_triad_spec(branch, matched_skill, maker_model=maker_model)
    return {
        "branch": branch,
        "skill": matched_skill,
        "skill_path": normalized_path,
        "triad": triad_spec,
    }


def _workspace_has_triad_rules(payload: dict[str, Any]) -> bool | None:
    """Return True if workspace GEMINI.md defines Triad rules, False if missing, None if no workspace provided."""
    raw_ws = payload.get("workspaceRoot") or payload.get("workspace") or payload.get("cwd")
    if not raw_ws:
        return None
    ws_path = Path(str(raw_ws))
    if not ws_path.is_dir():
        return False
    gemini_md = ws_path / "GEMINI.md"
    if not gemini_md.is_file():
        return False
    try:
        content = gemini_md.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "triad" in content or "dynamic triad" in content


def evaluate_pre_invocation_payload(
    payload: dict[str, Any],
    *,
    router: SkillRouter | None = None,
    loader: SkillLoader | None = None,
    maker_model: str | None = None,
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

    resolved_maker_model = (
        maker_model
        or payload.get("makerModel")
        or payload.get("maker_model")
        or payload.get("model")
    )
    route_info = route_user_prompt(
        user_input,
        router=router,
        loader=loader,
        maker_model=resolved_maker_model,
    )
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

    ws_has_triad = _workspace_has_triad_rules(payload)
    extra_guard = ""
    if ws_has_triad is False:
        extra_guard = (
            " | workspace_triad=MISSING_LOCAL_GEMINI"
            " | sandbox_guard=Reviewer/Critic MUST use TypeName='research' (read-only),"
            " Builder use Workspace='share', keep 'browser' idle, Zero-Paraphrase Handoff"
        )

    conversation_id = str(payload.get("conversationId") or payload.get("conversation_id") or "")
    try:
        from harness.host_watch import get_pre_invocation_host_notice

        host_notice = get_pre_invocation_host_notice(conversation_id=conversation_id)
    except Exception:
        host_notice = None
    if host_notice:
        extra_guard += f" | host_io={host_notice}"

    directive_msg = (
        f"{ROUTER_MARKER} branch={branch} | skill={skill} | "
        f"skill_path={skill_path} | triad={triad} | directive={directive}{extra_guard}"
    )
    return {
        "injectSteps": [
            {
                "systemMessage": {"systemMessage": directive_msg},
                "ephemeralMessage": directive_msg,
            }
        ],
        "terminationBehavior": "",
    }


def main() -> None:
    """CLI and Antigravity PreInvocation Hook entry point."""
    result: dict[str, Any] = {"injectSteps": [], "terminationBehavior": ""}
    try:
        parser = argparse.ArgumentParser(description="Antigravity PreInvocation Auto Skill Router Hook")
        parser.add_argument("--prompt", "-p", type=str, default="", help="Direct user prompt to route")
        parser.add_argument("--invocation-num", "-n", type=int, default=1, help="Invocation number in turn")
        parser.add_argument("--model", "-m", type=str, default="", help="Flexible maker model override")
        args, _ = parser.parse_known_args()

        if args.prompt:
            result = evaluate_pre_invocation_payload(
                {
                    "lastUserInput": args.prompt,
                    "invocationNum": args.invocation_num,
                },
                maker_model=args.model or None,
            )
        elif not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input and raw_input.strip():
                payload = json.loads(raw_input)
                if isinstance(payload, dict):
                    result = evaluate_pre_invocation_payload(
                        payload,
                        maker_model=args.model or None,
                    )
    except Exception:
        result = {"injectSteps": [], "terminationBehavior": ""}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
