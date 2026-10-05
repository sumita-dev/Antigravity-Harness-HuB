from harness.state_machine import TaskContext, HarnessState

class AppRunner:
    def __init__(self, quality_gate):
        self.quality_gate = quality_gate

    def run(
        self,
        task_description: str,
        context: TaskContext,
        mock_checker_output: str = "VERDICT: APPROVE",
        spec: str = None,
        implementation_artifacts: dict = None,
        **kwargs,
    ):
        if context.state == HarnessState.INTAKE:
            context.transition(HarnessState.DESIGN)  # Architect
            context.record_step("DESIGN", {"actor": "architect", "spec": spec or "Default Architecture Spec"})
        if context.state == HarnessState.DESIGN:
            context.transition(HarnessState.IMPLEMENTATION)  # Builder
            context.record_step(
                "IMPLEMENTATION",
                {"actor": "builder", "artifacts": implementation_artifacts or {"status": "code_implemented"}},
            )
        if context.state == HarnessState.IMPLEMENTATION:
            context.transition(HarnessState.AUDIT)  # QA Auditor
            context.record_step("AUDIT", {"actor": "qa_auditor"})
            
        return self.quality_gate.evaluate(context, mock_checker_output)
