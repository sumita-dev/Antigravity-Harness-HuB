from harness.state_machine import TaskContext, HarnessState

class AppRunner:
    def __init__(self, quality_gate):
        self.quality_gate = quality_gate

    def run(self, task_description: str, context: TaskContext, mock_checker_output: str = "VERDICT: APPROVE"):
        if context.state == HarnessState.INTAKE:
            context.transition(HarnessState.DESIGN) # Architect
        if context.state == HarnessState.DESIGN:
            context.transition(HarnessState.IMPLEMENTATION) # Builder
        if context.state == HarnessState.IMPLEMENTATION:
            context.transition(HarnessState.AUDIT) # QA Auditor
            
        return self.quality_gate.evaluate(context, mock_checker_output)
