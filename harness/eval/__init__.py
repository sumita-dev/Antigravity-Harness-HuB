"""Evaluation Bridge Module for Antigravity Harness Hub.

Provides lazy-loaded interface connecting Harness Quality Gates to Google ADK
AgentEvaluator and deterministic evaluation strategies:
- AgentEvaluatorBridge: Master bridge interface.
- TrajectoryEvaluator: Step order, prerequisites, and trajectory adherence.
- PolicySafetyEvaluator: Policy violations and red-flag phrase detector.
- FactGroundingEvaluator: Dossier claim mapping and anti-hallucination auditor.
"""

from .evaluator import (
    DEFAULT_RED_FLAG_PHRASES,
    AgentEvaluatorBridge,
    FactGroundingEvaluator,
    PolicySafetyEvaluator,
    TrajectoryEvaluator,
    is_eval_ready,
)

__all__ = [
    "AgentEvaluatorBridge",
    "TrajectoryEvaluator",
    "PolicySafetyEvaluator",
    "FactGroundingEvaluator",
    "DEFAULT_RED_FLAG_PHRASES",
    "is_eval_ready",
]
