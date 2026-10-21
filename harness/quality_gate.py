from enum import Enum
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union

from harness.state_machine import HarnessState

class Verdict(str, Enum):
    """Là str-Enum nên vẫn so sánh được với chuỗi ('APPROVE'), đồng thời có .name/.value."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"

class AdversarialQualityGate:
    def __init__(
        self,
        max_rounds: int = 2,
        max_qa_rounds: int = 2,
        max_total_cycles: int = 3,
        evaluator: Optional[Any] = None,
    ):
        self.max_rounds = max_rounds
        self.max_qa_rounds = max_qa_rounds
        self.max_total_cycles = max_total_cycles
        self._evaluator = evaluator

    @property
    def evaluator(self) -> Any:
        if self._evaluator is None:
            from harness.validators.opik_evaluator import OpikEvaluator
            self._evaluator = OpikEvaluator()
        return self._evaluator

    def evaluate_critique(self, task_context, critic_output: str) -> Verdict:
        """Đánh giá phản biện từ Critic (soi GAP, logic, edge cases)."""
        task_context.record_step("CRITIC", {"raw": critic_output.strip()[:200]})
        if "VERDICT: APPROVE" in critic_output:
            task_context.safe_transition(HarnessState.AUDIT)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in critic_output:
            if not task_context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE
            if not task_context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE
            task_context.safe_transition(HarnessState.REJECTED)
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT
        elif "VERDICT: ESCALATE" in critic_output or "ESCALATE_HUMAN" in critic_output:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
        else:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE

    def evaluate_audit(self, task_context, checker_output: str, direct_to_qa: bool = True) -> Verdict:
        """Đánh giá kiểm định từ QA Auditor (test thật, security scan, health check)."""
        task_context.record_step("CHECKER", {"raw": checker_output.strip()[:200]})
        if "VERDICT: APPROVE" in checker_output:
            task_context.transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in checker_output:
            # Lỗi kỹ thuật / test fail -> tăng qa_rounds
            if not task_context.increment_qa(self.max_qa_rounds):
                return Verdict.ESCALATE
            if not task_context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE
            task_context.safe_transition(HarnessState.REJECTED)
            # Smart Feedback Loop: nếu direct_to_qa (lỗi kỹ thuật/test fail/secret leak), trả về IMPLEMENTATION để sửa và sau đó quay thẳng AUDIT
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT
        elif "VERDICT: ESCALATE" in checker_output or "ESCALATE_HUMAN" in checker_output:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
        else:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE

    def evaluate(self, task_context, checker_output: str):
        """Giữ tương thích ngược với luồng evaluate cũ."""
        task_context.record_step("CHECKER", {"raw": checker_output.strip()[:200]})
        if "VERDICT: APPROVE" in checker_output:
            task_context.transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in checker_output:
            if not task_context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE
            if not task_context.check_total_cycles(self.max_total_cycles):
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
            context.critique_rounds += 1
            if not context.increment_qa(self.max_qa_rounds):
                return Verdict.ESCALATE
            if not context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE
            context.safe_transition(HarnessState.REJECTED)
            context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT

    def evaluate_quantitative(
        self,
        response_text: str,
        reference_text: Optional[str] = None,
        planned_steps: Optional[List[Any]] = None,
        executed_steps: Optional[List[Any]] = None,
        execution_logs: Optional[Any] = None,
        rubric_criteria: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Tính toán bảng điểm định lượng toàn diện kết hợp các metrics Opik."""
        evaluator = self.evaluator
        scores = {}

        # 1. Hallucination check
        scores["hallucination"] = evaluator.evaluate_hallucination(
            text=response_text,
            execution_logs=execution_logs,
        )

        # 2. Degeneration check
        scores["degeneration"] = evaluator.evaluate_degeneration(response_text)

        # 3. Levenshtein ratio nếu có chuỗi tham chiếu
        if reference_text is not None:
            scores["levenshtein"] = evaluator.evaluate_levenshtein(
                output=response_text,
                reference=reference_text,
            )

        # 4. Trajectory adherence nếu có kế hoạch và lịch sử thực thi
        if planned_steps is not None and executed_steps is not None:
            scores["trajectory"] = evaluator.evaluate_trajectory(
                planned_steps=planned_steps,
                executed_steps=executed_steps,
            )

        # 5. Rubric G-Eval nếu có danh sách tiêu chí
        if rubric_criteria:
            scores["rubric"] = evaluator.evaluate_rubric(
                text=response_text,
                criteria=rubric_criteria,
            )

        composite = evaluator.compute_composite_score(scores)
        return {
            "composite_score": composite,
            "is_passing": composite >= 0.8,
            "metrics": {
                k: {
                    "score": v.value,
                    "reason": v.reason,
                    "metadata": v.metadata,
                }
                for k, v in scores.items()
            },
        }

    def evaluate_app_quality_gate(
        self,
        task_context,
        response_text: str,
        execution_logs: Optional[Any] = None,
        planned_steps: Optional[List[Any]] = None,
        threshold: float = 0.8,
    ) -> Tuple[Verdict, Dict[str, Any]]:
        """Cổng chất lượng định lượng cho nhánh App dựa trên OpikEvaluator.

        Đánh giá:
        - Hallucination score (đường dẫn file, ký hiệu AST, bằng chứng exit code 0)
        - Trajectory accuracy (mức độ tuân thủ quy trình các bước)
        - Degeneration check (chống lặp token vô nghĩa)
        """
        evaluator = self.evaluator
        executed_steps = getattr(task_context, "steps", [])

        scores = {
            "hallucination": evaluator.evaluate_hallucination(
                text=response_text,
                execution_logs=execution_logs,
            ),
            "degeneration": evaluator.evaluate_degeneration(response_text),
        }

        if planned_steps:
            scores["trajectory"] = evaluator.evaluate_trajectory(
                planned_steps=planned_steps,
                executed_steps=executed_steps,
            )

        weights = {"hallucination": 0.5, "trajectory": 0.3, "degeneration": 0.2}
        composite = evaluator.compute_composite_score(scores, weights=weights)

        details = {
            "composite_score": composite,
            "threshold": threshold,
            "is_passing": (
                composite >= threshold
                and scores["hallucination"].value >= threshold
            ),
            "metrics": {
                k: {
                    "score": v.value,
                    "reason": v.reason,
                    "metadata": v.metadata,
                }
                for k, v in scores.items()
            },
        }

        if hasattr(task_context, "record_step"):
            task_context.record_step(
                "APP_QUALITY_GATE",
                {"score": composite, "metrics": details["metrics"]},
            )

        if details["is_passing"]:
            if hasattr(task_context, "safe_transition"):
                task_context.safe_transition(HarnessState.APPROVED)
            return Verdict.APPROVE, details
        else:
            if hasattr(task_context, "increment_qa") and not task_context.increment_qa(self.max_qa_rounds):
                return Verdict.ESCALATE, details
            if hasattr(task_context, "check_total_cycles") and not task_context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE, details
            if hasattr(task_context, "safe_transition"):
                task_context.safe_transition(HarnessState.REJECTED)
                task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT, details

    def evaluate_marketing_quality_gate(
        self,
        task_context,
        content_text: str,
        rubric_criteria: Optional[List[Dict[str, Any]]] = None,
        threshold: float = 0.8,
    ) -> Tuple[Verdict, Dict[str, Any]]:
        """Cổng chất lượng định lượng cho nhánh Marketing dựa trên OpikEvaluator.

        Đánh giá:
        - Rubric G-Eval (cấu trúc bài viết, hooks, bằng chứng, VoC)
        - Degeneration check (chất lượng ngôn từ, chống lặp cụm từ)
        - Hallucination score (đối soát sự thật, trích dẫn nguồn)
        """
        evaluator = self.evaluator
        scores = {
            "degeneration": evaluator.evaluate_degeneration(content_text),
            "hallucination": evaluator.evaluate_hallucination(content_text),
        }

        if rubric_criteria:
            scores["rubric"] = evaluator.evaluate_rubric(content_text, rubric_criteria)

        weights = {"rubric": 0.5, "degeneration": 0.3, "hallucination": 0.2}
        composite = evaluator.compute_composite_score(scores, weights=weights)

        details = {
            "composite_score": composite,
            "threshold": threshold,
            "is_passing": composite >= threshold,
            "metrics": {
                k: {
                    "score": v.value,
                    "reason": v.reason,
                    "metadata": v.metadata,
                }
                for k, v in scores.items()
            },
        }

        if hasattr(task_context, "record_step"):
            task_context.record_step(
                "MARKETING_QUALITY_GATE",
                {"score": composite, "metrics": details["metrics"]},
            )

        if details["is_passing"]:
            if hasattr(task_context, "safe_transition"):
                task_context.safe_transition(HarnessState.APPROVED)
            return Verdict.APPROVE, details
        else:
            if hasattr(task_context, "increment_critique") and not task_context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE, details
            if hasattr(task_context, "check_total_cycles") and not task_context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE, details
            if hasattr(task_context, "safe_transition"):
                task_context.safe_transition(HarnessState.REJECTED)
                task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT, details


