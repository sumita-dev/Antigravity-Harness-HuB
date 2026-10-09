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
                context.record_step("CRITIQUE", {"actor": "content_critic"})
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
