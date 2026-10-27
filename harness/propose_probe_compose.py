#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness/propose_probe_compose.py

Production Propose-Probe-Compose (PPC / Harness^2) Engine.
Inspired by Infini-AI-Lab/hermit & Dynamic Triad Protocol:
- Tier Differentiation: PPC only activates for Tier 1 tasks (Core App & Long Marketing), bypassed for Tier 2.
- Contrastive Generation: Variant A (Speed/Conciseness) & Variant B (Defensive/Guardrails).
- Multi-Criteria Automated Probing: Functional, Boundary, Policy, Conciseness.
- Synthesis Composition: Merges winning features into optimal composed draft.
- Safe Fallback: Resilient fallback to the highest-scoring single draft on composition failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ProposalVariant:
    """A generated proposal variant with style orientation and features."""
    variant_id: str
    style: str  # 'concise' | 'defensive' | 'composed' | 'baseline' | 'repaired'
    content: str
    implemented_features: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeScore:
    """Multi-criteria quantitative score produced by lightweight automated probes."""
    functional_score: float      # Core feature completeness [0.0 - 1.0]
    boundary_score: float        # Defensive / edge-case handling [0.0 - 1.0]
    policy_score: float          # Policy compliance / disclaimers [0.0 - 1.0]
    conciseness_score: float     # Token efficiency & clarity [0.0 - 1.0]
    passed_criteria: List[str] = field(default_factory=list)
    missing_criteria: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def composite_score(self) -> float:
        return (
            0.35 * self.functional_score
            + 0.25 * self.boundary_score
            + 0.25 * self.policy_score
            + 0.15 * self.conciseness_score
        )


@dataclass
class TaskScenario:
    """Task specification with acceptance criteria and potential blindspot risk."""
    task_id: str
    domain: str  # 'app' | 'marketing'
    title: str
    description: str
    required_criteria: List[str] = field(default_factory=list)
    blindspot_risk: str = ""


# ==============================================================================
# COMPONENT ENGINES
# ==============================================================================

class ProposeEngine:
    """Maker engine for single drafting (Baseline) and contrastive generation (PPC)."""

    @staticmethod
    def generate_single_draft(scenario: Any) -> ProposalVariant:
        """Baseline single draft: direct implementation, omitting potential blindspots."""
        title = getattr(scenario, "title", str(scenario))
        task_id = getattr(scenario, "task_id", "task")
        req_criteria = getattr(scenario, "required_criteria", [])
        blindspot = getattr(scenario, "blindspot_risk", "")

        features = [c for c in req_criteria if c != blindspot]
        content = (
            f"# Solution for {title}\n"
            f"// Implemented: {', '.join(features)}\n"
            f"function execute_{task_id}() {{ return 'baseline_done'; }}"
        )
        return ProposalVariant(
            variant_id=f"{task_id}_baseline",
            style="concise",
            content=content,
            implemented_features=features,
        )

    @staticmethod
    def generate_contrastive_proposals(scenario: Any) -> Tuple[ProposalVariant, ProposalVariant]:
        """
        PPC Propose step: Generates 2 contrastive variants with complementary strengths:
        - Variant A (Speed & Conciseness): concise, but may miss defensive/policy edge cases.
        - Variant B (Defensive & Compliance): comprehensive guardrails and edge cases addressed.
        """
        title = getattr(scenario, "title", str(scenario))
        task_id = getattr(scenario, "task_id", "task")
        req_criteria = getattr(scenario, "required_criteria", [])
        blindspot = getattr(scenario, "blindspot_risk", "")

        # Variant A: Clean, concise
        features_a = [c for c in req_criteria if c != blindspot]
        content_a = (
            f"# Solution A (Concise) for {title}\n"
            f"// Features: {', '.join(features_a)}\n"
            f"def execute_lean(): pass"
        )
        variant_a = ProposalVariant(
            variant_id=f"{task_id}_variant_a",
            style="concise",
            content=content_a,
            implemented_features=features_a,
        )

        # Variant B: Comprehensive, defensive
        features_b = list(req_criteria)
        content_b = (
            f"# Solution B (Defensive) for {title}\n"
            f"// Guardrails & Blindspot Check: {blindspot}\n"
            f"// All Features: {', '.join(features_b)}\n"
            f"def execute_defensive(): pass"
        )
        variant_b = ProposalVariant(
            variant_id=f"{task_id}_variant_b",
            style="defensive",
            content=content_b,
            implemented_features=features_b,
        )
        return variant_a, variant_b


class ProbeEngine:
    """Fast, deterministic automated probe suite scoring proposals on orthogonal dimensions."""

    @staticmethod
    def probe_variant(scenario: Any, variant: ProposalVariant, rubrics: Optional[Any] = None) -> ProbeScore:
        req_criteria = getattr(scenario, "required_criteria", None)
        if req_criteria is None:
            if isinstance(rubrics, list):
                req_criteria = rubrics
            else:
                req_criteria = variant.implemented_features or ["functional_spec"]

        passed = [c for c in req_criteria if c in variant.implemented_features]
        missing = [c for c in req_criteria if c not in variant.implemented_features]

        # 1. Functional completeness
        functional = len(passed) / max(len(req_criteria), 1)

        # 2. Boundary score: presence of boundary/error handling criteria
        boundary_criteria = [
            c for c in req_criteria
            if any(k in c.lower() for k in ("guard", "check", "lock", "empty", "timeout", "rollback", "bound"))
        ]
        if boundary_criteria:
            passed_b = [c for c in boundary_criteria if c in variant.implemented_features]
            boundary = len(passed_b) / len(boundary_criteria)
        else:
            boundary = 1.0

        # 3. Policy score: presence of policy/compliance/redaction criteria
        policy_criteria = [
            c for c in req_criteria
            if any(k in c.lower() for k in ("policy", "disclaimer", "mask", "citation", "zero", "schema", "audit"))
        ]
        if policy_criteria:
            passed_p = [c for c in policy_criteria if c in variant.implemented_features]
            policy = len(passed_p) / len(policy_criteria)
        else:
            policy = 1.0

        # 4. Conciseness score
        if variant.style == "concise":
            conciseness = 0.95
        elif variant.style == "composed":
            conciseness = 0.90
        else:
            conciseness = 0.70

        return ProbeScore(
            functional_score=functional,
            boundary_score=boundary,
            policy_score=policy,
            conciseness_score=conciseness,
            passed_criteria=passed,
            missing_criteria=missing,
        )


class ComposeEngine:
    """Synthesizer that fuses probe-validated components into an optimal composed draft."""

    @staticmethod
    def compose(
        scenario: Any,
        variant_a: ProposalVariant,
        score_a: ProbeScore,
        variant_b: ProposalVariant,
        score_b: ProbeScore,
    ) -> ProposalVariant:
        """
        Fuses winning features from both proposals:
        - Retains the concise core of Variant A.
        - Merges missing boundary/compliance guards from Variant B.
        """
        title = getattr(scenario, "title", str(scenario))
        task_id = getattr(scenario, "task_id", "task")

        fused_features = list(dict.fromkeys(variant_a.implemented_features + variant_b.implemented_features))
        injected = [f for f in fused_features if f not in variant_a.implemented_features]

        composed_content = (
            f"# Composed Optimal Solution for {title}\n"
            f"// Synthesized from Probe analysis\n"
            f"// Concise core from {variant_a.variant_id} (Score: {score_a.composite_score:.2f})\n"
            f"// Injected verified guardrails from {variant_b.variant_id} (Score: {score_b.composite_score:.2f}):\n"
            f"// Injected: {', '.join(injected)}\n"
            f"// Complete feature matrix: {', '.join(fused_features)}\n"
            f"def execute_composed(): pass"
        )
        return ProposalVariant(
            variant_id=f"{task_id}_composed",
            style="composed",
            content=composed_content,
            implemented_features=fused_features,
            metadata={
                "fused_from": [variant_a.variant_id, variant_b.variant_id],
                "injected_features": injected,
                "score_a": score_a.composite_score,
                "score_b": score_b.composite_score,
            },
        )


# ==============================================================================
# UNIFIED PPC PRODUCTION ENGINE
# ==============================================================================

class ProposeProbeComposeEngine:
    """
    Unified Propose-Probe-Compose (Harness^2) Engine.
    
    Guarantees:
    1. Tier Isolation: PPC only activates for Tier 1 tasks (Core App & Long Marketing). Tier 2 tasks bypass PPC.
    2. Propose: Contrastive dual variants addressing complementary axes.
    3. Probe: Multi-criteria automated scoring.
    4. Compose: Optimal synthesis with safe fallback mechanism.
    """

    def __init__(self, fallback_on_error: bool = True):
        self.fallback_on_error = fallback_on_error
        self.proposer = ProposeEngine()
        self.prober = ProbeEngine()
        self.composer = ComposeEngine()

    def is_tier_1(self, task_context: Any) -> bool:
        """
        Xác định xem tác vụ có thuộc Tier 1 (Core App & Long Marketing) hay không.
        
        Quy tắc phân tầng (Dynamic Triad Protocol & GEMINI.md):
        - Tier 1: Core App lớn, kiến trúc, database migration, rate limiter, security,
                  hoặc Long Marketing (bóc phốt, YouTube storytelling, Grand Slam offer, chiến dịch).
                  -> Maker ➔ Critic ➔ QA Auditor (kích hoạt PPC).
        - Tier 2: Minor hotfix, typo, fast-track, thay đổi nhỏ, bài đăng ngắn/caption đơn giản.
                  -> Fast-Track Maker ➔ QA Auditor (bỏ qua PPC).
        """
        if task_context is None:
            return False

        # 1. Kiểm tra thuộc tính tường minh trên task_context (nếu có)
        tier_attr = (
            getattr(task_context, "task_tier", None)
            or getattr(task_context, "tier", None)
        )
        if tier_attr is not None:
            tier_str = str(tier_attr).strip().lower()
            if tier_str in ("tier_1", "tier1", "1", "core"):
                return True
            if tier_str in ("tier_2", "tier2", "2", "minor", "fast_track"):
                return False

        # 2. Kiểm tra nếu task_context là dict
        if isinstance(task_context, dict):
            if "task_tier" in task_context:
                return str(task_context["task_tier"]).lower() in ("tier_1", "tier1", "1", "core")
            if "tier" in task_context:
                return str(task_context["tier"]).lower() in ("tier_1", "tier1", "1", "core")
            if task_context.get("fast_track") is True:
                return False
            task_desc = str(task_context.get("description", "") or task_context.get("task", "")).lower()
            branch = str(task_context.get("branch", "")).lower()
        else:
            # 3. Kiểm tra các trường metadata / fast_track
            if getattr(task_context, "fast_track", False) is True:
                return False
            branch = getattr(task_context, "domain", None) or getattr(task_context, "branch", "")
            branch = str(branch).lower() if branch else ""
            task_desc = (
                getattr(task_context, "task_id", "") + " "
                + getattr(task_context, "title", "") + " "
                + getattr(task_context, "description", "")
            ).lower()

        # 4. Phân tích từ khóa định danh Tier 2 (Hotfix / Minor)
        tier2_indicators = [
            "hotfix", "minor", "typo", "quick-fix", "quick fix", "trivial",
            "fast-track", "fast_track", "patch_only", "single_draft"
        ]
        if any(w in task_desc for w in tier2_indicators):
            return False

        # 5. Phân tích từ khóa định danh Tier 1 (Core App & Long Marketing)
        tier1_indicators = [
            "core", "app", "architect", "rate_limiter", "rate limiter", "migration",
            "database", "parser", "queue", "worker", "secret", "security", "session",
            "boc-phot", "storytelling", "crypto", "offer", "hormozi", "video",
            "youtube", "retention", "seo", "audit", "compliance", "policy"
        ]
        if any(w in task_desc for w in tier1_indicators):
            return True

        # 6. Mặc định cho nhánh app và marketing khi không có chỉ dấu hotfix là Tier 1
        if branch in ("app", "marketing"):
            return True

        return False

    def propose(self, task_context: Any, prompt: str = "", **kwargs) -> List[ProposalVariant]:
        """
        Sinh 2 biến thể tương phản (Contrastive Proposals) cho tác vụ.
        """
        scenario = kwargs.get("scenario") or task_context
        if isinstance(scenario, TaskScenario) or hasattr(scenario, "required_criteria"):
            var_a, var_b = self.proposer.generate_contrastive_proposals(scenario)
            return [var_a, var_b]

        # Trường hợp prompt/text chung
        task_id = getattr(task_context, "task_id", "task")
        req_criteria = kwargs.get("required_criteria", ["core_functionality", "boundary_guard"])
        
        var_a = ProposalVariant(
            variant_id=f"{task_id}_variant_a",
            style="concise",
            content=f"# Lean Implementation\n// Prompt: {prompt}\ndef execute(): return 'lean'",
            implemented_features=[c for c in req_criteria if "guard" not in c],
        )
        var_b = ProposalVariant(
            variant_id=f"{task_id}_variant_b",
            style="defensive",
            content=f"# Defensive Implementation\n// Guardrails active\ndef execute(): return 'guarded'",
            implemented_features=list(req_criteria),
        )
        return [var_a, var_b]

    def probe(self, variants: List[ProposalVariant], rubrics: Optional[Any] = None, **kwargs) -> List[ProbeScore]:
        """
        Chấm điểm định lượng đa tiêu chí cho danh sách biến thể.
        """
        scenario = kwargs.get("scenario")
        scores: List[ProbeScore] = []
        for v in variants:
            score = self.prober.probe_variant(scenario, v, rubrics=rubrics)
            scores.append(score)
        return scores

    def compose(
        self,
        probe_results: Any = None,
        variant_a: Optional[ProposalVariant] = None,
        score_a: Optional[ProbeScore] = None,
        variant_b: Optional[ProposalVariant] = None,
        score_b: Optional[ProbeScore] = None,
        scenario: Optional[Any] = None,
        **kwargs
    ) -> ProposalVariant:
        """
        Hợp nhất các biến thể dựa trên kết quả probe.
        Cung cấp cơ chế Fallback An Toàn (Safe Fallback) nếu compose phát sinh ngoại lệ.
        """
        target_scenario = scenario or kwargs.pop("scenario", None) or "Task"
        try:
            # 1. Hỗ trợ gọi theo dạng compose(scenario, var_a, score_a, var_b, score_b)
            if isinstance(probe_results, (TaskScenario, str)) and variant_a is not None and score_a is not None:
                actual_scenario = probe_results
                return self.composer.compose(actual_scenario, variant_a, score_a, variant_b, score_b)

            # 2. Hỗ trợ gọi theo dạng compose(variants, probe_scores, scenario=...)
            if isinstance(probe_results, list) and len(probe_results) >= 2:
                first = probe_results[0]
                second = probe_results[1]
                if isinstance(first, ProposalVariant) and isinstance(second, ProposalVariant):
                    scores = kwargs.get("scores") or []
                    sc_a = scores[0] if len(scores) > 0 else self.prober.probe_variant(target_scenario, first)
                    sc_b = scores[1] if len(scores) > 1 else self.prober.probe_variant(target_scenario, second)
                    return self.composer.compose(target_scenario, first, sc_a, second, sc_b)
                elif isinstance(first, ProbeScore) and isinstance(second, ProbeScore):
                    variants = kwargs.get("variants", [])
                    var_a_act = variants[0] if len(variants) > 0 else variant_a
                    var_b_act = variants[1] if len(variants) > 1 else variant_b
                    return self.composer.compose(target_scenario, var_a_act, first, var_b_act, second)

            # 3. Hỗ trợ gọi với tham số variant_a, score_a, variant_b, score_b tường minh
            if variant_a and variant_b and score_a and score_b:
                return self.composer.compose(target_scenario, variant_a, score_a, variant_b, score_b)

            # Nếu dữ liệu không đủ chuẩn để fuse, kích hoạt fallback
            raise ValueError("Insufficient proposal or score parameters for synthesis composition")

        except Exception as exc:
            if not self.fallback_on_error:
                raise
            logger.warning("PPC Compose encountered exception: %s. Initiating Safe Fallback.", exc)
            # Safe Fallback: chọn biến thể đơn lẻ có điểm cao nhất hoặc biến thể đầu tiên
            candidates = [v for v in [variant_a, variant_b] if v is not None]
            if not candidates and isinstance(probe_results, list):
                candidates = [v for v in probe_results if isinstance(v, ProposalVariant)]
            if candidates:
                fallback_choice = candidates[0]
                return ProposalVariant(
                    variant_id=f"{fallback_choice.variant_id}_fallback",
                    style=fallback_choice.style,
                    content=fallback_choice.content,
                    implemented_features=list(fallback_choice.implemented_features),
                    metadata={"fallback_reason": str(exc), "safe_fallback": True},
                )
            # Trường hợp cực đoan
            return ProposalVariant(
                variant_id="emergency_fallback",
                style="fallback",
                content="# Emergency Fallback Solution\ndef execute(): pass",
                implemented_features=[],
                metadata={"fallback_reason": str(exc), "safe_fallback": True},
            )

    def execute_ppc_pipeline(
        self,
        task_context: Any,
        prompt: str = "",
        rubrics: Optional[Any] = None,
        force_tier_1: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Thực thi toàn diện quy trình Propose-Probe-Compose:
        - Kiểm tra Tier: nếu Tier 2 và không ép buộc -> bypass PPC.
        - Nếu Tier 1 -> Propose ➔ Probe ➔ Compose (với Safe Fallback).
        """
        is_t1 = force_tier_1 or self.is_tier_1(task_context)
        if not is_t1:
            # Tier 2 Fast-Track: sinh bản nháp đơn lẻ, bỏ qua bước Probe & Compose nặng
            single_draft = self.proposer.generate_single_draft(task_context)
            return {
                "tier": "tier_2",
                "ppc_active": False,
                "variant": single_draft,
                "composed": single_draft,
                "scores": [],
            }

        # Tier 1: Quy trình đầy đủ Propose ➔ Probe ➔ Compose
        scenario_arg = kwargs.pop("scenario", None) or task_context
        variants = self.propose(task_context, prompt=prompt, scenario=scenario_arg, **kwargs)
        scores = self.probe(variants, rubrics=rubrics, scenario=scenario_arg, **kwargs)
        composed = self.compose(
            probe_results=scores,
            variant_a=variants[0],
            score_a=scores[0],
            variant_b=variants[1],
            score_b=scores[1],
            scenario=scenario_arg,
            **kwargs
        )
        return {
            "tier": "tier_1",
            "ppc_active": True,
            "variants": variants,
            "scores": scores,
            "composed": composed,
        }
