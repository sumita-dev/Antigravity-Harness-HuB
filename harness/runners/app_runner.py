from harness.state_machine import TaskContext, HarnessState
from harness.quality_gate import Verdict

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
        test_command: str = None,
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
            if kwargs.get("fast_track", False):
                context.transition(HarnessState.AUDIT)  # Fast-Track: Maker -> QA
                context.record_step("AUDIT", {"actor": "qa_auditor"})
            else:
                context.transition(HarnessState.CRITIQUE)  # Dynamic Triad: Maker -> Code Critic
                context.record_step("CRITIQUE", {"actor": "code_critic"})
                # If mock_critic_output is provided and rejects, evaluate it
                mock_critic_output = kwargs.get("mock_critic_output", "VERDICT: APPROVE")
                if "mock_critic_output" in kwargs or mock_checker_output == "VERDICT: APPROVE":
                    # Evaluate critique
                    critique_verdict = self.quality_gate.evaluate_critique(context, mock_critic_output)
                    if critique_verdict != Verdict.APPROVE:
                        return critique_verdict
                else:
                    # Move to AUDIT
                    context.transition(HarnessState.AUDIT)
                if context.state == HarnessState.AUDIT:
                    context.record_step("AUDIT", {"actor": "qa_auditor"})
            
        if test_command:
            return self.quality_gate.evaluate_execution(context, test_command)
        return self.quality_gate.evaluate(context, mock_checker_output)
