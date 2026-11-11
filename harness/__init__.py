"""Antigravity Harness Framework & Coordination Core."""
from typing import Any


def get_deadman_timeout(tier: str = "full") -> int:
    from harness.subagent_guard import get_deadman_timeout as _timeout
    return _timeout(tier)


def list_idle_subagents(repo_root=None):
    from harness.subagent_guard import list_idle_subagents as _list_idle
    return _list_idle(repo_root)


def __getattr__(name: str) -> Any:
    if name in ("SubagentGuard", "SubagentInfo", "SubAgentState"):
        import harness.subagent_guard as mod
        return getattr(mod, name)
    if name in ("TriadHandoffV2", "validate_handoff_v2", "parse_handoff_v2", "sync_workspace_for_qa"):
        import harness.triad_protocol as mod
        return getattr(mod, name)
    raise AttributeError(f"module 'harness' has no attribute '{name}'")


__all__ = [
    "get_deadman_timeout",
    "SubagentGuard",
    "SubagentInfo",
    "SubAgentState",
    "list_idle_subagents",
    "TriadHandoffV2",
    "validate_handoff_v2",
    "parse_handoff_v2",
    "sync_workspace_for_qa",
]
