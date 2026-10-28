"""Agent Evaluator Bridge and Agentic Evaluation Engines.

Provides a lazy-loaded, decoupled interface to Google ADK AgentEvaluator.
When google.adk.evaluation is available, bridges directly to native agentic evals.
When absent, seamlessly falls back to high-speed deterministic evaluation engines:
- TrajectoryEvaluator: enforces step order, tool prerequisites, and step-skipping guards.
- PolicySafetyEvaluator: detects policy violations and speculative red-flag phrases.
- FactGroundingEvaluator: audits claim grounding and cross-checks evidence dossiers.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

DEFAULT_RED_FLAG_PHRASES: list[str] = [
    "should work",
    "probably",
    "chắc là",
    "có lẽ",
    "might work",
    "it seems",
    "hình như",
    "không sao đâu",
    "tự tin pass",
    "chắc chắn sẽ chạy",
    "may be fine",
    "looks good to me without testing",
]


def is_eval_ready() -> bool:
    """Check if Google ADK evaluation module is installed and functional."""
    try:
        importlib.import_module("google.adk.evaluation")
        return True
    except (ImportError, AttributeError):
        return False


def _extract_all_strings(data: Any) -> list[str]:
    """Recursively extract all string values from nested dicts, lists, or primitives."""
    strings: list[str] = []
    if isinstance(data, str):
        strings.append(data)
    elif isinstance(data, dict):
        for val in data.values():
            strings.extend(_extract_all_strings(val))
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            strings.extend(_extract_all_strings(item))
    return strings


# ==============================================================================
# 1. TrajectoryEvaluator
# ==============================================================================


class TrajectoryEvaluator:
    """Evaluates agent execution trajectories against required order, prerequisites, and rules.

    Guards against step-skipping, missing prerequisite tool calls (e.g. calling mutate
    before context/impact), and order violations.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._eval_ready = is_eval_ready()

    def evaluate(
        self,
        trajectory: Union[dict[str, Any], list[Any]],
        criteria: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate a trajectory or step list against sequence and prerequisite criteria.

        Args:
            trajectory: Dictionary matching TrajectoryStore schema or a list of steps.
            criteria: Dict containing:
                - 'prerequisites': dict[str, list[str]] e.g. {'write_code': ['impact_analysis', 'context_lookup']}
                - 'required_steps': list[str]
                - 'prohibited_steps': list[str]
                - 'order_matters': bool
                - 'strict_sequence': list[str] (exact ordered transitions)
                - 'max_critique_rounds': int
                - 'expected_verdict': str

        Returns:
            Dictionary containing evaluation verdict, score, mode, and diagnostics.
        """
        crit = criteria or {}

        # If native ADK evaluator is loaded and configured for trajectory evals
        if self._eval_ready:
            try:
                adk_eval = importlib.import_module("google.adk.evaluation")
                evaluator_cls = getattr(adk_eval, "AgentEvaluator")
                native_eval = evaluator_cls(self.config)
                native_result = native_eval.evaluate(trajectory, crit)
                return {
                    "passed": bool(getattr(native_result, "passed", True)),
                    "score": float(getattr(native_result, "score", 1.0)),
                    "evaluator": "TrajectoryEvaluator",
                    "mode": "adk_agentic",
                    "details": getattr(native_result, "details", {}),
                    "summary": getattr(native_result, "summary", "Native ADK Trajectory Evaluation complete."),
                }
            except Exception as exc:
                logger.warning("ADK TrajectoryEvaluator execution failed: %s. Using deterministic fallback.", exc)

        # Deterministic Evaluation
        return self._evaluate_deterministic(trajectory, crit)

    def _evaluate_deterministic(
        self,
        trajectory: Union[dict[str, Any], list[Any]],
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        errors: list[str] = []
        prerequisite_violations: list[str] = []
        order_violations: list[str] = []
        missing_steps: list[str] = []
        prohibited_found: list[str] = []

        # Normalize steps
        raw_steps: list[Any] = []
        final_verdict = None
        critique_rounds = 0

        if isinstance(trajectory, dict):
            raw_steps = trajectory.get("steps") or trajectory.get("events") or []
            final_verdict = trajectory.get("final_verdict")
            critique_rounds = trajectory.get("critique_rounds", 0)
        elif isinstance(trajectory, list):
            raw_steps = trajectory

        # Extract normalized step actions and tools
        actions: list[dict[str, str]] = []
        for s in raw_steps:
            if isinstance(s, dict):
                step_name = str(s.get("step") or s.get("name") or s.get("event_type") or "")
                tool_name = str(s.get("tool") or s.get("tool_name") or s.get("action") or "")
                actions.append({"step": step_name, "tool": tool_name})
            else:
                actions.append({"step": str(s), "tool": ""})

        # All observed identifiers (both step names and tool names)
        step_identifiers: list[str] = [a["step"] for a in actions if a["step"]]
        all_identifiers: list[str] = []
        for a in actions:
            if a["step"]:
                all_identifiers.append(a["step"])
            if a["tool"]:
                all_identifiers.append(a["tool"])

        # 1. Prerequisite Tool / Step Checks
        # Example prerequisites: {"write_code": ["impact_analysis", "context_lookup"]}
        prereqs: dict[str, list[str]] = criteria.get("prerequisites", {})
        for target, required_priors in prereqs.items():
            # Find occurrences of target
            target_indices = [
                i for i, a in enumerate(actions)
                if a["step"] == target or a["tool"] == target
            ]
            for t_idx in target_indices:
                prior_identifiers = set()
                for prev in actions[:t_idx]:
                    if prev["step"]:
                        prior_identifiers.add(prev["step"])
                    if prev["tool"]:
                        prior_identifiers.add(prev["tool"])

                for req in required_priors:
                    if req not in prior_identifiers:
                        violation = f"Action '{target}' at position {t_idx} requires prior '{req}', which was not executed."
                        prerequisite_violations.append(violation)
                        errors.append(violation)

        # 2. Required steps check
        required_steps: list[str] = criteria.get("required_steps", [])
        for req in required_steps:
            if req not in all_identifiers:
                missing_steps.append(req)
                errors.append(f"Missing required step/tool '{req}' in trajectory")

        # 3. Prohibited steps check
        prohibited_steps: list[str] = criteria.get("prohibited_steps", [])
        for pro in prohibited_steps:
            if pro in all_identifiers:
                prohibited_found.append(pro)
                errors.append(f"Found prohibited step/tool '{pro}' in trajectory")

        # 4. Order and sequence checking
        order_matters = criteria.get("order_matters", False)
        if order_matters and len(required_steps) > 1:
            indices = []
            for r in required_steps:
                if r in all_identifiers:
                    indices.append(all_identifiers.index(r))
                else:
                    indices.append(-1)
            for i in range(len(indices) - 1):
                if indices[i] != -1 and indices[i + 1] != -1 and indices[i] > indices[i + 1]:
                    v_msg = f"Step order violation: '{required_steps[i]}' appeared after '{required_steps[i + 1]}'"
                    order_violations.append(v_msg)
                    errors.append(v_msg)

        # 5. Strict sequence / No-step-skipping check
        strict_sequence: list[str] = criteria.get("strict_sequence", [])
        if strict_sequence and len(strict_sequence) > 1:
            # Verify each subsequent element follows directly without skipping steps in the strict sequence
            matched_pos = []
            for item in strict_sequence:
                if item in step_identifiers:
                    matched_pos.append(step_identifiers.index(item))
                else:
                    matched_pos.append(-1)
            for i in range(len(matched_pos) - 1):
                if matched_pos[i] != -1 and matched_pos[i + 1] != -1:
                    if matched_pos[i] > matched_pos[i + 1]:
                        msg = f"Strict sequence violated: '{strict_sequence[i]}' came after '{strict_sequence[i + 1]}'"
                        order_violations.append(msg)
                        errors.append(msg)

        # 6. Expected verdict check
        if criteria.get("expected_verdict") is not None and final_verdict is not None:
            expected = criteria["expected_verdict"]
            if final_verdict != expected:
                errors.append(f"Expected final_verdict '{expected}', got '{final_verdict}'")

        # 7. Max critique rounds
        if "max_critique_rounds" in criteria:
            max_rounds = criteria["max_critique_rounds"]
            if critique_rounds > max_rounds:
                errors.append(f"Critique rounds ({critique_rounds}) exceeded maximum ({max_rounds})")

        passed = len(errors) == 0
        total_checks = (
            len(prereqs)
            + len(required_steps)
            + len(prohibited_steps)
            + (1 if order_matters else 0)
            + (1 if criteria.get("expected_verdict") is not None else 0)
        )
        if total_checks == 0:
            score = 1.0 if passed else 0.0
        else:
            failed_count = (
                len(prerequisite_violations)
                + len(missing_steps)
                + len(prohibited_found)
                + len(order_violations)
                + (1 if criteria.get("expected_verdict") is not None and final_verdict != criteria.get("expected_verdict") else 0)
            )
            score = max(0.0, min(1.0, 1.0 - (failed_count / max(1, total_checks))))

        summary = (
            "Trajectory verification passed successfully."
            if passed
            else f"Trajectory verification failed ({len(errors)} issues): {'; '.join(errors[:3])}"
        )

        return {
            "passed": passed,
            "score": round(score, 3),
            "evaluator": "TrajectoryEvaluator",
            "mode": "fallback_deterministic",
            "errors": errors,
            "prerequisite_violations": prerequisite_violations,
            "order_violations": order_violations,
            "missing_steps": missing_steps,
            "prohibited_found": prohibited_found,
            "total_steps": len(actions),
            "summary": summary,
        }


# ==============================================================================
# 2. PolicySafetyEvaluator
# ==============================================================================


class PolicySafetyEvaluator:
    """Evaluates text, transcripts, or agent outputs for policy compliance and red-flag phrases.

    Flags speculative statements ('should work', 'probably', 'chắc là') and forbidden terms.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._eval_ready = is_eval_ready()
        custom_flags = self.config.get("red_flag_phrases", [])
        self.red_flag_phrases = list(set(DEFAULT_RED_FLAG_PHRASES + custom_flags))

    def evaluate(
        self,
        content_or_trajectory: Union[str, dict[str, Any], list[Any]],
        criteria: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate content or trajectory for red flags and safety policy violations.

        Args:
            content_or_trajectory: Text string, output dict, or full trajectory.
            criteria: Dict containing optional 'red_flag_phrases', 'prohibited_terms',
                      'policy_rules'.

        Returns:
            Dict containing pass/fail verdict, score, detected phrases, and summary.
        """
        crit = criteria or {}

        # ADK native integration if available
        if self._eval_ready:
            try:
                adk_eval = importlib.import_module("google.adk.evaluation")
                evaluator_cls = getattr(adk_eval, "AgentEvaluator")
                native_eval = evaluator_cls(self.config)
                native_result = native_eval.evaluate(content_or_trajectory, crit)
                return {
                    "passed": bool(getattr(native_result, "passed", True)),
                    "score": float(getattr(native_result, "score", 1.0)),
                    "evaluator": "PolicySafetyEvaluator",
                    "mode": "adk_agentic",
                    "details": getattr(native_result, "details", {}),
                    "summary": getattr(native_result, "summary", "Native ADK Policy Evaluation complete."),
                }
            except Exception as exc:
                logger.warning("ADK PolicySafetyEvaluator failed: %s. Using deterministic fallback.", exc)

        return self._evaluate_deterministic(content_or_trajectory, crit)

    def _evaluate_deterministic(
        self,
        content_or_trajectory: Union[str, dict[str, Any], list[Any]],
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        # Merge configured red flag phrases with criteria
        active_red_flags = list(set(self.red_flag_phrases + criteria.get("red_flag_phrases", [])))
        prohibited_terms = criteria.get("prohibited_terms", [])

        # Extract all text segments
        text_blobs = _extract_all_strings(content_or_trajectory)
        combined_text = " ".join(text_blobs).lower()

        detected_red_flags: list[str] = []
        for phrase in active_red_flags:
            # Case-insensitive substring matching
            pattern = re.escape(phrase.lower())
            if re.search(r"\b" + pattern + r"\b", combined_text) or phrase.lower() in combined_text:
                detected_red_flags.append(phrase)

        detected_prohibited: list[str] = []
        for term in prohibited_terms:
            pattern = re.escape(term.lower())
            if re.search(r"\b" + pattern + r"\b", combined_text) or term.lower() in combined_text:
                detected_prohibited.append(term)

        errors: list[str] = []
        if detected_red_flags:
            errors.append(f"Red-flag phrases detected: {detected_red_flags}")
        if detected_prohibited:
            errors.append(f"Prohibited policy terms detected: {detected_prohibited}")

        passed = len(detected_red_flags) == 0 and len(detected_prohibited) == 0

        # Calculate score
        penalty = (0.25 * len(detected_red_flags)) + (0.4 * len(detected_prohibited))
        score = max(0.0, min(1.0, 1.0 - penalty))

        summary = (
            "Policy safety verification passed cleanly."
            if passed
            else f"Policy safety check failed: {'; '.join(errors)}"
        )

        return {
            "passed": passed,
            "score": round(score, 3),
            "evaluator": "PolicySafetyEvaluator",
            "mode": "fallback_deterministic",
            "red_flags_detected": detected_red_flags,
            "prohibited_detected": detected_prohibited,
            "errors": errors,
            "summary": summary,
        }


# ==============================================================================
# 3. FactGroundingEvaluator
# ==============================================================================


class FactGroundingEvaluator:
    """Evaluates agent claims and outputs against an evidence dossier.

    Verifies claim citation, ungrounded (hallucinated) claims, and grounding coverage.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._eval_ready = is_eval_ready()

    def evaluate(
        self,
        content_or_claims: Union[str, list[Any], dict[str, Any]],
        dossier: Union[dict[str, Any], list[Any]],
        criteria: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate factual grounding of agent output against dossier.

        Args:
            content_or_claims: Text content with claim citations (e.g. '[claim_01]'),
                               or list of claim ID strings, or dict containing 'claims_used'.
            dossier: Evidence dossier dict (e.g. {'claims': [{'id': 'claim_01', ...}]}) or list of claims.
            criteria: Dict containing optional 'required_claims', 'min_grounding_score'.

        Returns:
            Dict containing pass/fail verdict, score, matched/ungrounded claims, and summary.
        """
        crit = criteria or {}

        if self._eval_ready:
            try:
                adk_eval = importlib.import_module("google.adk.evaluation")
                evaluator_cls = getattr(adk_eval, "AgentEvaluator")
                native_eval = evaluator_cls(self.config)
                native_result = native_eval.evaluate(
                    {"content": content_or_claims, "dossier": dossier}, crit
                )
                return {
                    "passed": bool(getattr(native_result, "passed", True)),
                    "score": float(getattr(native_result, "score", 1.0)),
                    "evaluator": "FactGroundingEvaluator",
                    "mode": "adk_agentic",
                    "details": getattr(native_result, "details", {}),
                    "summary": getattr(native_result, "summary", "Native ADK Fact Grounding Evaluation complete."),
                }
            except Exception as exc:
                logger.warning("ADK FactGroundingEvaluator failed: %s. Using deterministic fallback.", exc)

        return self._evaluate_deterministic(content_or_claims, dossier, crit)

    def _evaluate_deterministic(
        self,
        content_or_claims: Union[str, list[Any], dict[str, Any]],
        dossier: Union[dict[str, Any], list[Any]],
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        # 1. Extract valid claim IDs from dossier
        dossier_claim_ids: set[str] = set()
        if isinstance(dossier, dict):
            claims_list = dossier.get("claims") or dossier.get("facts") or []
            if isinstance(claims_list, list):
                for item in claims_list:
                    if isinstance(item, dict):
                        cid = str(item.get("id") or item.get("claim_id") or "")
                        if cid:
                            dossier_claim_ids.add(cid)
                    elif isinstance(item, str):
                        dossier_claim_ids.add(item)
            elif isinstance(claims_list, dict):
                dossier_claim_ids.update(claims_list.keys())
        elif isinstance(dossier, list):
            for item in dossier:
                if isinstance(item, dict):
                    cid = str(item.get("id") or item.get("claim_id") or "")
                    if cid:
                        dossier_claim_ids.add(cid)
                elif isinstance(item, str):
                    dossier_claim_ids.add(item)

        # 2. Extract claims referenced by agent
        referenced_claims: set[str] = set()
        if isinstance(content_or_claims, list):
            for c in content_or_claims:
                if isinstance(c, dict):
                    cid = str(c.get("id") or c.get("claim_id") or "")
                    if cid:
                        referenced_claims.add(cid)
                elif isinstance(c, str):
                    referenced_claims.add(c)
        elif isinstance(content_or_claims, dict):
            used = (
                content_or_claims.get("claims_used")
                or content_or_claims.get("claim_ids")
                or content_or_claims.get("claims")
            )
            if isinstance(used, list):
                for c in used:
                    referenced_claims.add(str(c))
            else:
                # Search within text strings of dictionary
                for txt in _extract_all_strings(content_or_claims):
                    self._extract_claims_from_text(txt, referenced_claims, dossier_claim_ids)
        elif isinstance(content_or_claims, str):
            self._extract_claims_from_text(content_or_claims, referenced_claims, dossier_claim_ids)

        # 3. Match claims against dossier
        matched_claims = sorted(list(referenced_claims & dossier_claim_ids))
        ungrounded_claims = sorted(list(referenced_claims - dossier_claim_ids))

        # Check required claims
        required_claims = criteria.get("required_claims", [])
        missing_claims = [rc for rc in required_claims if rc not in matched_claims]

        # Grounding ratio
        total_referenced = len(referenced_claims)
        if total_referenced > 0:
            grounding_ratio = len(matched_claims) / total_referenced
        else:
            grounding_ratio = 1.0 if not required_claims else 0.0

        min_grounding_score = criteria.get("min_grounding_score", 1.0)
        errors: list[str] = []

        if ungrounded_claims:
            errors.append(f"Ungrounded/hallucinated claims found: {ungrounded_claims}")
        if missing_claims:
            errors.append(f"Required claims missing from output: {missing_claims}")
        if grounding_ratio < min_grounding_score:
            errors.append(
                f"Grounding ratio {round(grounding_ratio, 2)} lower than threshold {min_grounding_score}"
            )

        passed = len(errors) == 0

        # Score calculation
        penalty = 0.5 * len(ungrounded_claims) + 0.3 * len(missing_claims)
        score = max(0.0, min(1.0, grounding_ratio - penalty))

        summary = (
            f"Fact grounding verified: {len(matched_claims)}/{total_referenced} claims grounded."
            if passed
            else f"Fact grounding failed: {'; '.join(errors)}"
        )

        return {
            "passed": passed,
            "score": round(score, 3),
            "evaluator": "FactGroundingEvaluator",
            "mode": "fallback_deterministic",
            "matched_claims": matched_claims,
            "ungrounded_claims": ungrounded_claims,
            "missing_claims": missing_claims,
            "grounding_ratio": round(grounding_ratio, 3),
            "errors": errors,
            "summary": summary,
        }

    def _extract_claims_from_text(
        self,
        text: str,
        referenced_set: set[str],
        known_dossier_claims: set[str],
    ) -> None:
        """Extract bracketed and named claim tokens from text."""
        # Find [claim_01], [claim-01], [CLAIM_1], [C1]
        matches = re.findall(r"\[([a-zA-Z0-9_\-]+)\]", text)
        for m in matches:
            if m.lower().startswith("claim") or m in known_dossier_claims:
                referenced_set.add(m)

        # Also search for direct token mentions of known dossier claim IDs
        for k_cid in known_dossier_claims:
            if re.search(r"\b" + re.escape(k_cid) + r"\b", text):
                referenced_set.add(k_cid)


# ==============================================================================
# 4. AgentEvaluatorBridge
# ==============================================================================


class AgentEvaluatorBridge:
    """Bridge interface wrapping Google ADK AgentEvaluator and specialized evaluators.

    Allows QA Auditor and Quality Gates to inspect SubAgent tool trajectories,
    instruction following, policy compliance, and fact grounding.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._eval_ready = is_eval_ready()
        self._native_evaluator = None

        if self._eval_ready:
            try:
                adk_eval = importlib.import_module("google.adk.evaluation")
                evaluator_cls = getattr(adk_eval, "AgentEvaluator")
                self._native_evaluator = evaluator_cls(self.config)
            except Exception as e:
                logger.warning(
                    "ADK evaluation module detected but instantiation failed: %s. Using fallback mode.",
                    e,
                )
                self._eval_ready = False

        # Specialized modular evaluators
        self.trajectory_evaluator = TrajectoryEvaluator(self.config)
        self.policy_evaluator = PolicySafetyEvaluator(self.config)
        self.grounding_evaluator = FactGroundingEvaluator(self.config)

    @property
    def is_ready(self) -> bool:
        """Return True if native Google ADK evaluation is fully operational."""
        return self._eval_ready

    def evaluate_trajectory(
        self,
        trajectory: dict[str, Any],
        eval_criteria: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate a full execution trajectory against schema and behavioral criteria."""
        criteria = eval_criteria or {}

        # If native ADK evaluator is loaded, route to it
        if self._eval_ready and self._native_evaluator is not None:
            try:
                native_result = self._native_evaluator.evaluate(trajectory, criteria)
                return {
                    "passed": bool(getattr(native_result, "passed", True)),
                    "score": float(getattr(native_result, "score", 1.0)),
                    "mode": "adk_agentic",
                    "eval_ready": True,
                    "details": getattr(native_result, "details", {}),
                    "summary": getattr(native_result, "summary", "Native ADK Evaluation complete."),
                }
            except Exception as exc:
                logger.warning("Native ADK evaluation threw exception: %s. Running fallback.", exc)

        # Deterministic Fallback Evaluator
        return self._evaluate_deterministic(trajectory, criteria)

    def evaluate_policy_safety(
        self,
        content_or_trajectory: Union[str, dict[str, Any], list[Any]],
        eval_criteria: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate content or trajectory for red-flag phrases and policy safety."""
        return self.policy_evaluator.evaluate(content_or_trajectory, eval_criteria)

    def evaluate_fact_grounding(
        self,
        content_or_claims: Union[str, list[Any], dict[str, Any]],
        dossier: Union[dict[str, Any], list[Any]],
        eval_criteria: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate fact grounding of content or claims against an evidence dossier."""
        return self.grounding_evaluator.evaluate(content_or_claims, dossier, eval_criteria)

    def evaluate_evalset(
        self,
        evalset_source: Union[str, Path, dict[str, Any]],
    ) -> dict[str, Any]:
        """Load and evaluate an entire EvalSet file or dictionary.

        Args:
            evalset_source: Path to .evalset.json file or pre-loaded dictionary.

        Returns:
            Dictionary containing overall eval summary, pass rate, and individual results.
        """
        data: dict[str, Any]
        if isinstance(evalset_source, (str, Path)):
            path = Path(evalset_source)
            if not path.exists():
                raise FileNotFoundError(f"EvalSet file not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = evalset_source

        eval_cases = data.get("eval_cases", [])
        results: list[dict[str, Any]] = []
        passed_cases = 0

        for case in eval_cases:
            case_id = case.get("id", "unnamed-case")
            expected = case.get("expected", {})
            case_passed = True
            case_details: dict[str, Any] = {"id": case_id, "checks": {}}

            # Check 1: Trajectory evaluation
            if "trajectory" in case:
                traj_crit = {
                    "prerequisites": case.get("prerequisites", {}),
                    "required_steps": case.get("required_steps", []),
                    "order_matters": case.get("order_matters", False),
                }
                if case.get("expected_verdict") is not None:
                    traj_crit["expected_verdict"] = case["expected_verdict"]
                res_traj = self.trajectory_evaluator.evaluate(case["trajectory"], traj_crit)
                case_details["checks"]["trajectory"] = res_traj
                expected_traj_pass = expected.get("trajectory_pass")
                if expected_traj_pass is not None and res_traj["passed"] != expected_traj_pass:
                    case_passed = False

            # Check 2: Policy Safety evaluation
            content_to_check = case.get("content") or case.get("trajectory")
            if content_to_check:
                res_policy = self.policy_evaluator.evaluate(content_to_check)
                case_details["checks"]["policy_safety"] = res_policy
                expected_policy_pass = expected.get("policy_safety_pass")
                if expected_policy_pass is not None and res_policy["passed"] != expected_policy_pass:
                    case_passed = False

            # Check 3: Fact Grounding evaluation
            if "dossier" in case:
                claims_input = case.get("content") or case.get("trajectory") or case.get("claims")
                res_grounding = self.grounding_evaluator.evaluate(claims_input, case["dossier"])
                case_details["checks"]["fact_grounding"] = res_grounding
                expected_grounding_pass = expected.get("fact_grounding_pass")
                if expected_grounding_pass is not None and res_grounding["passed"] != expected_grounding_pass:
                    case_passed = False

            case_details["passed"] = case_passed
            if case_passed:
                passed_cases += 1
            results.append(case_details)

        total_cases = len(eval_cases)
        pass_rate = round(passed_cases / total_cases, 3) if total_cases > 0 else 1.0

        return {
            "name": data.get("name", "Unnamed EvalSet"),
            "branch": data.get("branch", "unknown"),
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": total_cases - passed_cases,
            "pass_rate": pass_rate,
            "all_passed": passed_cases == total_cases,
            "results": results,
        }

    def evaluate_steps(
        self,
        steps: list[dict[str, Any]],
        expectations: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Evaluate tool/step execution order and trajectory adherence."""
        exp = expectations or {}
        required = exp.get("required_steps", [])
        prohibited = exp.get("prohibited_steps", [])
        order_matters = exp.get("order_matters", False)

        step_names = [
            s.get("step") if isinstance(s, dict) else str(s)
            for s in steps
        ]

        # Check required steps
        missing_steps = [req for req in required if req not in step_names]

        # Check prohibited steps
        found_prohibited = [p for p in prohibited if p in step_names]

        # Check order if required
        order_violations = []
        if order_matters and len(required) > 1:
            indices = []
            for r in required:
                if r in step_names:
                    indices.append(step_names.index(r))
                else:
                    indices.append(-1)
            for i in range(len(indices) - 1):
                if indices[i] != -1 and indices[i + 1] != -1 and indices[i] > indices[i + 1]:
                    order_violations.append(f"{required[i]} appeared after {required[i + 1]}")

        passed = not missing_steps and not found_prohibited and not order_violations

        # Calculate score
        if not required:
            score = 1.0 if not found_prohibited else 0.0
        else:
            match_ratio = (len(required) - len(missing_steps)) / len(required)
            penalty = 0.5 * len(found_prohibited) + 0.3 * len(order_violations)
            score = max(0.0, min(1.0, match_ratio - penalty))

        return {
            "passed": passed,
            "score": round(score, 3),
            "mode": "adk_agentic" if self._eval_ready else "fallback_deterministic",
            "eval_ready": self._eval_ready,
            "total_steps": len(steps),
            "missing_steps": missing_steps,
            "prohibited_found": found_prohibited,
            "order_violations": order_violations,
            "summary": (
                "Step sequence verified successfully."
                if passed
                else f"Step sequence issues: missing={missing_steps}, prohibited={found_prohibited}, order_violations={order_violations}"
            ),
        }

    def _evaluate_deterministic(
        self,
        trajectory: dict[str, Any],
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform zero-dependency deterministic evaluation on trajectory schema and goals."""
        errors: list[str] = []
        checks_run = 0
        checks_passed = 0

        # Check 1: Trajectory structure validity
        checks_run += 1
        required_keys = {"task_id", "steps", "final_verdict"}
        missing_keys = [k for k in required_keys if k not in trajectory]
        if missing_keys:
            errors.append(f"Missing required trajectory keys: {missing_keys}")
        else:
            checks_passed += 1

        # Check 2: Expected verdict
        if "expected_verdict" in criteria:
            checks_run += 1
            expected = criteria["expected_verdict"]
            actual = trajectory.get("final_verdict")
            if actual != expected:
                errors.append(f"Expected final_verdict '{expected}', got '{actual}'")
            else:
                checks_passed += 1

        # Check 3: Max critique rounds
        if "max_critique_rounds" in criteria:
            checks_run += 1
            max_rounds = criteria["max_critique_rounds"]
            actual_rounds = trajectory.get("critique_rounds", 0)
            if actual_rounds > max_rounds:
                errors.append(f"Critique rounds ({actual_rounds}) exceeded maximum ({max_rounds})")
            else:
                checks_passed += 1

        # Check 4: Step expectations
        steps = trajectory.get("steps", [])
        if "required_steps" in criteria or "prohibited_steps" in criteria:
            checks_run += 1
            step_eval = self.evaluate_steps(
                steps,
                expectations={
                    "required_steps": criteria.get("required_steps", []),
                    "prohibited_steps": criteria.get("prohibited_steps", []),
                    "order_matters": criteria.get("order_matters", False),
                },
            )
            if not step_eval["passed"]:
                errors.append(step_eval["summary"])
            else:
                checks_passed += 1

        # Check 5: Minimum step count
        if "min_steps" in criteria:
            checks_run += 1
            min_s = criteria["min_steps"]
            if len(steps) < min_s:
                errors.append(f"Step count ({len(steps)}) is lower than min_steps ({min_s})")
            else:
                checks_passed += 1

        # Check 6: Prerequisites if provided
        if "prerequisites" in criteria:
            checks_run += 1
            res_prereq = self.trajectory_evaluator.evaluate(
                trajectory, {"prerequisites": criteria["prerequisites"]}
            )
            if not res_prereq["passed"]:
                errors.extend(res_prereq["errors"])
            else:
                checks_passed += 1

        passed = len(errors) == 0
        score = (checks_passed / checks_run) if checks_run > 0 else 1.0

        return {
            "passed": passed,
            "score": round(score, 3),
            "mode": "fallback_deterministic",
            "eval_ready": self._eval_ready,
            "errors": errors,
            "summary": (
                "Deterministic trajectory verification passed."
                if passed
                else f"Verification failed: {'; '.join(errors)}"
            ),
        }
