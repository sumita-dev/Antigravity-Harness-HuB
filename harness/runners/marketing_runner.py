from harness.state_machine import TaskContext, HarnessState
from harness.quality_gate import Verdict

class MarketingRunner:
    def __init__(self, quality_gate):
        self.quality_gate = quality_gate

    def run(
        self,
        task_description: str,
        context: TaskContext,
        mock_checker_output: str = "VERDICT: APPROVE",
        dossier: str = None,
        content_artifacts: dict = None,
        **kwargs,
    ):
        if context.state == HarnessState.INTAKE:
            context.transition(HarnessState.DESIGN)  # Web Researcher
            context.record_step("DESIGN", {"actor": "web_researcher", "dossier": dossier or "Default Research Dossier"})
        if context.state == HarnessState.DESIGN:
            context.transition(HarnessState.IMPLEMENTATION)  # Content Creator
            # Tích hợp PPC khi task_tier == 'tier_1' hoặc enable_ppc=True (bỏ qua cho Tier 2)
            task_tier = kwargs.get("task_tier") or getattr(context, "task_tier", None)
            enable_ppc = kwargs.get("enable_ppc", False) or task_tier == "tier_1"
            if enable_ppc:
                from harness.propose_probe_compose import ProposeProbeComposeEngine
                ppc_engine = ProposeProbeComposeEngine()
                ppc_res = ppc_engine.execute_ppc_pipeline(context, prompt=task_description, force_tier_1=True, **kwargs)
                context.record_step("PPC_SYNTHESIS", {
                    "tier": "tier_1",
                    "variant_id": getattr(ppc_res.get("composed"), "variant_id", "composed"),
                    "features": getattr(ppc_res.get("composed"), "implemented_features", []),
                })
                if content_artifacts is None:
                    content_artifacts = {}
                content_artifacts["ppc_composed"] = getattr(ppc_res.get("composed"), "content", "")
                content_artifacts["status"] = "content_composed_ppc"

            context.record_step(
                "IMPLEMENTATION",
                {"actor": "creator", "artifacts": content_artifacts or {"status": "draft_created"}},
            )
        if context.state == HarnessState.IMPLEMENTATION:
            if kwargs.get("fast_track", False):
                context.transition(HarnessState.AUDIT)  # Fast-Track
                context.record_step("AUDIT", {"actor": "compliance_critic"})
            else:
                context.transition(HarnessState.CRITIQUE)  # Dynamic Triad: Content Critic
                context.record_step("CRITIQUE", {"actor": "compliance_critic"})
                mock_critic_output = kwargs.get("mock_critic_output", "VERDICT: APPROVE")
                if "mock_critic_output" in kwargs or mock_checker_output == "VERDICT: APPROVE":
                    critique_verdict = self.quality_gate.evaluate_critique(context, mock_critic_output)
                    if critique_verdict != Verdict.APPROVE:
                        return critique_verdict
                else:
                    context.transition(HarnessState.AUDIT)
                if context.state == HarnessState.AUDIT:
                    context.record_step("AUDIT", {"actor": "compliance_critic"})
            
        return self.quality_gate.evaluate(context, mock_checker_output)
