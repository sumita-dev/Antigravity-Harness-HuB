from harness.state_machine import HarnessState

class Verdict:
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"

class AdversarialQualityGate:
    def __init__(self, max_rounds=2):
        self.max_rounds = max_rounds

    def evaluate(self, task_context, checker_output: str):
        if "VERDICT: APPROVE" in checker_output:
            task_context.transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in checker_output:
            if not task_context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE
            task_context.transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT
        elif "VERDICT: ESCALATE" in checker_output or "ESCALATE_HUMAN" in checker_output:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
        else:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
