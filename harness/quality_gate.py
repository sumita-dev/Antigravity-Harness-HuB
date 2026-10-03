from enum import Enum

from harness.state_machine import HarnessState

class Verdict(str, Enum):
    """Là str-Enum nên vẫn so sánh được với chuỗi ('APPROVE'), đồng thời có .name/.value."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"

class AdversarialQualityGate:
    def __init__(self, max_rounds=2):
        self.max_rounds = max_rounds

    def evaluate(self, task_context, checker_output: str):
        task_context.record_step("CHECKER", {"raw": checker_output.strip()[:200]})
        if "VERDICT: APPROVE" in checker_output:
            task_context.transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in checker_output:
            if not task_context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE
            # Ghi nhận trạng thái REJECTED trước khi quay lại IMPLEMENTATION
            # (nếu vì lý do nào đó không hợp lệ, safe_transition không làm sập luồng).
            task_context.safe_transition(HarnessState.REJECTED)
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT
        elif "VERDICT: ESCALATE" in checker_output or "ESCALATE_HUMAN" in checker_output:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
        else:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
