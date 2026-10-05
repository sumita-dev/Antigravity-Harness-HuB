from enum import Enum
import subprocess

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

    def evaluate_execution(self, context, test_command: str, timeout: int = 60, expected_exit_code: int = 0) -> Verdict:
        try:
            result = subprocess.run(test_command, shell=True, capture_output=True, text=True, timeout=timeout)
            exit_code = result.returncode
            stdout_str = result.stdout[:500] if result.stdout else ""
            stderr_str = result.stderr[:500] if result.stderr else ""
        except subprocess.TimeoutExpired as e:
            exit_code = -1
            stdout_bytes = e.stdout or b""
            stderr_bytes = e.stderr or b""
            stdout_str = stdout_bytes.decode('utf-8', errors='ignore')[:500] if isinstance(stdout_bytes, bytes) else str(stdout_bytes)[:500]
            stderr_str = stderr_bytes.decode('utf-8', errors='ignore')[:500] if isinstance(stderr_bytes, bytes) else str(stderr_bytes)[:500]
            stderr_str += f"\nTimeout after {timeout}s"
        except Exception as e:
            exit_code = -2
            stdout_str = ""
            stderr_str = str(e)[:500]

        context.record_step("EXECUTE", {"command": test_command, "exit_code": exit_code, "stdout": stdout_str, "stderr": stderr_str})

        if exit_code == expected_exit_code:
            context.safe_transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        else:
            if not context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE
            context.safe_transition(HarnessState.REJECTED)
            context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT

