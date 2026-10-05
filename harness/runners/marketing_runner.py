from harness.state_machine import TaskContext, HarnessState

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
            context.transition(HarnessState.AUDIT)  # Compliance Critic
            context.record_step("AUDIT", {"actor": "compliance_critic"})
            
        return self.quality_gate.evaluate(context, mock_checker_output)
