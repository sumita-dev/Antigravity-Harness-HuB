from enum import Enum
import json
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union

from harness.state_machine import HarnessState

_SHORT_MOCK_EXEMPTIONS = frozenset({
    "VERDICT: APPROVE",
    "VERDICT: REJECT",
    "VERDICT: ESCALATE",
    "ESCALATE_HUMAN",
    "Test passed. VERDICT: APPROVE",
})

class Verdict(str, Enum):
    """Là str-Enum nên vẫn so sánh được với chuỗi ('APPROVE'), đồng thời có .name/.value."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    PAUSE = "PAUSE"

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

    def gate_check(
        self,
        task_context,
        message: str = "Human Review Gate: Approval required.",
        options: Optional[List[str]] = None,
        verdict_override: Optional[str] = None,
        checkpoint_path: Optional[str] = None,
    ) -> Tuple[Verdict, str]:
        """Human-in-the-Loop Review Gate (lấy cảm hứng từ GateStep của Spec-Kit).

        Nếu verdict_override được truyền trực tiếp (hoặc non-interactive với giá trị định sẵn),
        xử lý quyết định ngay. Nếu không, chuyển trạng thái sang PAUSED và lưu checkpoint để resume sau.
        """
        import json
        from pathlib import Path

        if options is None:
            options = ["approve", "reject"]

        # Nếu có verdict định sẵn (ví dụ resume hoặc non-interactive input)
        if verdict_override:
            choice = verdict_override.strip().lower()
            if choice in ("approve", "approved", "yes", "1"):
                task_context.record_step("GATE_RESUME", {"message": message, "choice": choice, "verdict": "APPROVE"})
                return Verdict.APPROVE, choice
            elif choice in ("reject", "rejected", "no", "0"):
                task_context.record_step("GATE_RESUME", {"message": message, "choice": choice, "verdict": "REJECT"})
                return Verdict.REJECT, choice
            else:
                task_context.record_step("GATE_RESUME", {"message": message, "choice": choice, "verdict": "ESCALATE"})
                return Verdict.ESCALATE, choice

        # Chuyển trạng thái sang PAUSED
        previous_state = task_context.state
        task_context.safe_transition(HarnessState.PAUSED)
        
        # Ghi checkpoint lưu state nếu có đường dẫn
        checkpoint_info = {
            "task_id": task_context.task_id,
            "branch": task_context.branch,
            "previous_state": previous_state.name,
            "state": task_context.state.name,
            "message": message,
            "options": options,
            "critique_rounds": task_context.critique_rounds,
            "qa_rounds": task_context.qa_rounds,
            "total_cycles": task_context.total_cycles,
        }
        task_context.record_step("GATE_PAUSE", checkpoint_info)

        if checkpoint_path:
            p = Path(checkpoint_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(checkpoint_info, indent=2, ensure_ascii=False), encoding="utf-8")

        return Verdict.PAUSE, "PAUSED"

    def resume_gate(
        self,
        task_context,
        target_state: HarnessState,
        choice: str,
    ) -> bool:
        """Nối lại luồng sau khi được người dùng phê duyệt từ trạng thái PAUSED."""
        if task_context.state != HarnessState.PAUSED:
            return False
        
        task_context.record_step("GATE_RESOLVED", {"choice": choice, "target_state": target_state.name})
        return task_context.safe_transition(target_state)

    def _run_hallucination_gate(
        self,
        task_context,
        output_text: str,
        *,
        check_paths: bool = False,
        base_dir: Optional[Any] = None,
        extra_execution_logs: Optional[List[Dict[str, Any]]] = None,
    ):
        """Extract EXECUTE steps from task_context.trace_steps and run audit_response()."""
        from harness.validators.hallucination_detector import audit_response

        execution_logs: List[Dict[str, Any]] = []
        trace_steps = getattr(task_context, "trace_steps", None)
        if isinstance(trace_steps, list):
            for step in trace_steps:
                if isinstance(step, dict) and step.get("step") == "EXECUTE":
                    payload = step.get("payload")
                    if isinstance(payload, dict):
                        execution_logs.append(payload)
        if extra_execution_logs:
            execution_logs.extend(extra_execution_logs)

        return audit_response(
            output_text,
            base_dir=base_dir,
            execution_logs=execution_logs or None,
            check_paths=check_paths,
        )

    @staticmethod
    def _try_extract_structured_payload(raw_output: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Return dict if raw_output is a dict or a JSON object string with 'verdict'."""
        if isinstance(raw_output, dict):
            return raw_output
        if isinstance(raw_output, str):
            stripped = raw_output.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict) and "verdict" in parsed:
                        return parsed
                except Exception:
                    return None
        return None

    def evaluate_critique(
        self,
        task_context,
        critic_output: Union[str, Dict[str, Any]],
        *,
        enforce_hallucination_guard: bool = True,
        strict_paths: bool = False,
        base_dir: Optional[Any] = None,
    ) -> Verdict:
        """Đánh giá phản biện từ Critic (soi GAP, logic, edge cases)."""
        structured = self._try_extract_structured_payload(critic_output)
        if structured is not None:
            from harness.triad_protocol import validate_critique_payload

            is_valid, schema_errors = validate_critique_payload(structured)
            if not is_valid:
                task_context.record_step(
                    "CRITIC",
                    {"raw": json.dumps(structured, ensure_ascii=False)[:200], "schema_errors": schema_errors},
                )
                if not task_context.increment_critique(self.max_rounds):
                    return Verdict.ESCALATE
                if not task_context.check_total_cycles(self.max_total_cycles):
                    return Verdict.ESCALATE
                task_context.safe_transition(HarnessState.REJECTED)
                task_context.safe_transition(HarnessState.IMPLEMENTATION)
                return Verdict.REJECT

            verdict_str = str(structured["verdict"]).strip()
            verdict_token = f"VERDICT: {verdict_str}"
            text_parts = [str(structured.get("summary") or "")]
            text_parts.extend(str(f) for f in (structured.get("findings") or []))
            text_parts.extend(str(r) for r in (structured.get("recommendations") or []))
            text_for_gate = "\n".join(p for p in text_parts if p)
            raw_preview = json.dumps(structured, ensure_ascii=False)[:200]
        else:
            verdict_token = str(critic_output)
            text_for_gate = verdict_token
            raw_preview = verdict_token.strip()[:200]

        if enforce_hallucination_guard and text_for_gate.strip() not in _SHORT_MOCK_EXEMPTIONS:
            audit_res = self._run_hallucination_gate(
                task_context,
                text_for_gate,
                check_paths=strict_paths,
                base_dir=base_dir,
            )
            if audit_res.verdict == "REJECT":
                task_context.record_step(
                    "HALLUCINATION_GATE",
                    {
                        "stage": "CRITIC",
                        "verdict": audit_res.verdict,
                        "score": audit_res.score,
                        "violations": list(audit_res.violations),
                    },
                )
                if not task_context.increment_critique(self.max_rounds):
                    return Verdict.ESCALATE
                if not task_context.check_total_cycles(self.max_total_cycles):
                    return Verdict.ESCALATE
                task_context.safe_transition(HarnessState.REJECTED)
                task_context.safe_transition(HarnessState.IMPLEMENTATION)
                return Verdict.REJECT

        task_context.record_step("CRITIC", {"raw": raw_preview})
        if "VERDICT: APPROVE" in verdict_token:
            task_context.safe_transition(HarnessState.AUDIT)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in verdict_token:
            if not task_context.increment_critique(self.max_rounds):
                return Verdict.ESCALATE
            if not task_context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE
            task_context.safe_transition(HarnessState.REJECTED)
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT
        elif "VERDICT: ESCALATE" in verdict_token or "ESCALATE_HUMAN" in verdict_token:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
        else:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE

    def _check_latest_execution_step(self, task_context) -> Tuple[bool, Optional[int], Optional[Dict[str, Any]]]:
        """Kiểm tra bước EXECUTE mới nhất trong trace_steps xem có exit_code != 0 chưa được khắc phục hay không."""
        trace_steps = getattr(task_context, "trace_steps", None)
        if not isinstance(trace_steps, list):
            return False, None, None
        execute_steps = [
            s for s in trace_steps
            if isinstance(s, dict) and s.get("step") == "EXECUTE"
        ]
        if not execute_steps:
            return False, None, None
        latest_exec = execute_steps[-1]
        payload = latest_exec.get("payload")
        if isinstance(payload, dict) and "exit_code" in payload:
            exit_code = payload.get("exit_code")
            expected = payload.get("expected_exit_code", 0)
            if exit_code != expected:
                return True, exit_code, payload
        return False, None, payload if isinstance(payload, dict) else None

    def evaluate_audit(
        self,
        task_context,
        checker_output: Union[str, Dict[str, Any]],
        direct_to_qa: bool = True,
        *,
        enforce_hallucination_guard: bool = True,
        strict_paths: bool = False,
        base_dir: Optional[Any] = None,
    ) -> Verdict:
        """Đánh giá kiểm định từ QA Auditor (test thật, security scan, health check)."""
        structured = self._try_extract_structured_payload(checker_output)
        extra_exec_logs: Optional[List[Dict[str, Any]]] = None
        if structured is not None:
            from harness.triad_protocol import validate_audit_payload

            is_valid, schema_errors = validate_audit_payload(structured)
            if not is_valid:
                task_context.record_step(
                    "CHECKER",
                    {"raw": json.dumps(structured, ensure_ascii=False)[:200], "schema_errors": schema_errors},
                )
                if not task_context.increment_qa(self.max_qa_rounds):
                    return Verdict.ESCALATE
                if not task_context.check_total_cycles(self.max_total_cycles):
                    return Verdict.ESCALATE
                task_context.safe_transition(HarnessState.REJECTED)
                task_context.safe_transition(HarnessState.IMPLEMENTATION)
                return Verdict.REJECT

            verdict_str = str(structured["verdict"]).strip()
            verdict_token = f"VERDICT: {verdict_str}"
            text_parts = [str(structured.get("summary") or "")]
            text_parts.extend(str(f) for f in (structured.get("findings") or []))
            text_for_gate = "\n".join(p for p in text_parts if p)
            raw_preview = json.dumps(structured, ensure_ascii=False)[:200]
            extra_exec_logs = [
                c for c in (structured.get("executed_commands") or []) if isinstance(c, dict)
            ]
        else:
            verdict_token = str(checker_output)
            text_for_gate = verdict_token
            raw_preview = verdict_token.strip()[:200]

        has_exec_fail, exec_exit_code, exec_payload = self._check_latest_execution_step(task_context)
        if "VERDICT: APPROVE" in verdict_token and has_exec_fail:
            reason = f"Rejected: latest EXECUTE step has non-zero exit_code ({exec_exit_code})"
            task_context.record_step("CHECKER", {"raw": raw_preview, "reason": reason})
            already_counted = bool(exec_payload and exec_payload.get("_qa_counted") and not exec_payload.get("_audit_checked"))
            if exec_payload is not None:
                exec_payload["_audit_checked"] = True
            if not already_counted:
                if not task_context.increment_qa(self.max_qa_rounds):
                    return Verdict.ESCALATE
                if not task_context.check_total_cycles(self.max_total_cycles):
                    return Verdict.ESCALATE
            elif getattr(task_context, "state", None) == HarnessState.ESCALATED:
                return Verdict.ESCALATE
            task_context.safe_transition(HarnessState.REJECTED)
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT

        if enforce_hallucination_guard and text_for_gate.strip() not in _SHORT_MOCK_EXEMPTIONS:
            audit_res = self._run_hallucination_gate(
                task_context,
                text_for_gate,
                check_paths=strict_paths,
                base_dir=base_dir,
                extra_execution_logs=extra_exec_logs,
            )
            if audit_res.verdict == "REJECT":
                task_context.record_step(
                    "HALLUCINATION_GATE",
                    {
                        "stage": "AUDIT",
                        "verdict": audit_res.verdict,
                        "score": audit_res.score,
                        "violations": list(audit_res.violations),
                    },
                )
                if not task_context.increment_qa(self.max_qa_rounds):
                    return Verdict.ESCALATE
                if not task_context.check_total_cycles(self.max_total_cycles):
                    return Verdict.ESCALATE
                task_context.safe_transition(HarnessState.REJECTED)
                task_context.safe_transition(HarnessState.IMPLEMENTATION)
                return Verdict.REJECT

        task_context.record_step("CHECKER", {"raw": raw_preview})
        if "VERDICT: APPROVE" in verdict_token:
            if getattr(task_context, "state", None) != HarnessState.APPROVED:
                task_context.transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        elif "VERDICT: REJECT" in verdict_token:
            # Lỗi kỹ thuật / test fail -> tăng qa_rounds
            if not task_context.increment_qa(self.max_qa_rounds):
                return Verdict.ESCALATE
            if not task_context.check_total_cycles(self.max_total_cycles):
                return Verdict.ESCALATE
            task_context.safe_transition(HarnessState.REJECTED)
            # Smart Feedback Loop: nếu direct_to_qa (lỗi kỹ thuật/test fail/secret leak), trả về IMPLEMENTATION để sửa và sau đó quay thẳng AUDIT
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT
        elif "VERDICT: ESCALATE" in verdict_token or "ESCALATE_HUMAN" in verdict_token:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE
        else:
            task_context.transition(HarnessState.ESCALATED)
            return Verdict.ESCALATE

    def evaluate(self, task_context, checker_output: str):
        """Giữ tương thích ngược với luồng evaluate cũ."""
        has_exec_fail, exec_exit_code, exec_payload = self._check_latest_execution_step(task_context)
        if "VERDICT: APPROVE" in checker_output and has_exec_fail:
            reason = f"Rejected: latest EXECUTE step has non-zero exit_code ({exec_exit_code})"
            task_context.record_step("CHECKER", {"raw": checker_output.strip()[:200], "reason": reason})
            already_counted = bool(exec_payload and exec_payload.get("_qa_counted") and not exec_payload.get("_audit_checked"))
            if exec_payload is not None:
                exec_payload["_audit_checked"] = True
            if not already_counted:
                if not task_context.increment_critique(self.max_rounds):
                    return Verdict.ESCALATE
                if not task_context.check_total_cycles(self.max_total_cycles):
                    return Verdict.ESCALATE
            elif getattr(task_context, "state", None) == HarnessState.ESCALATED:
                return Verdict.ESCALATE
            task_context.safe_transition(HarnessState.REJECTED)
            task_context.safe_transition(HarnessState.IMPLEMENTATION)
            return Verdict.REJECT

        task_context.record_step("CHECKER", {"raw": checker_output.strip()[:200]})
        if "VERDICT: APPROVE" in checker_output:
            if getattr(task_context, "state", None) != HarnessState.APPROVED:
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
            result = subprocess.run(
                test_command,
                shell=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
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

        exec_payload = {
            "command": test_command,
            "exit_code": exit_code,
            "expected_exit_code": expected_exit_code,
            "stdout": stdout_str,
            "stderr": stderr_str,
        }
        if exit_code != expected_exit_code:
            exec_payload["_qa_counted"] = True
        context.record_step("EXECUTE", exec_payload)

        if exit_code == expected_exit_code:
            if getattr(context, "state", None) == HarnessState.IMPLEMENTATION:
                context.safe_transition(HarnessState.AUDIT)
            context.safe_transition(HarnessState.APPROVED)
            return Verdict.APPROVE
        else:
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
        raw_steps = getattr(task_context, "steps", None) or getattr(task_context, "trace_steps", [])
        executed_steps = [
            s.get("step", str(s)) if isinstance(s, dict) else s
            for s in (raw_steps or [])
        ]

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

    def evaluate_with_ppc(
        self,
        task_context,
        variants: Optional[List[Any]] = None,
        rubrics: Optional[Any] = None,
        mock_critic_output: Optional[str] = None,
        mock_checker_output: str = "VERDICT: APPROVE",
        **kwargs,
    ) -> Tuple[Verdict, Any]:
        """Tích hợp Propose-Probe-Compose (Harness^2) vào vòng đời Dynamic Triad.

        Quy tắc phân tầng (Hermit PPC Protocol):
        - Tier 1: kích hoạt PPC (Probe -> Compose -> Critic -> QA).
        - Tier 2: bỏ qua PPC, chuyển thẳng bản nháp đơn lẻ sang QA/Checker.
        """
        from harness.propose_probe_compose import ProposeProbeComposeEngine
        engine = ProposeProbeComposeEngine()

        # Kiểm tra Tier
        is_tier_1 = kwargs.get("enable_ppc", False) or engine.is_tier_1(task_context)

        if not is_tier_1:
            # Tier 2: Bỏ qua PPC
            primary_variant = variants[0] if (variants and len(variants) > 0) else "tier_2_draft"
            if hasattr(task_context, "record_step"):
                task_context.record_step("PPC_BYPASS", {"tier": "tier_2", "reason": "Fast-Track / Minor Task"})
            verdict = self.evaluate(task_context, mock_checker_output)
            return verdict, primary_variant

        # Tier 1: Kích hoạt PPC
        scenario_arg = kwargs.pop("scenario", None) or task_context
        if variants and len(variants) >= 2:
            scores = engine.probe(variants, rubrics=rubrics, scenario=scenario_arg, **kwargs)
            composed_variant = engine.compose(
                probe_results=scores,
                variants=variants,
                scenario=scenario_arg,
                **kwargs
            )
        else:
            res = engine.execute_ppc_pipeline(task_context, rubrics=rubrics, force_tier_1=True, scenario=scenario_arg, **kwargs)
            composed_variant = res["composed"]

        if hasattr(task_context, "record_step"):
            task_context.record_step("PPC_COMPOSE", {
                "tier": "tier_1",
                "composed_id": getattr(composed_variant, "variant_id", "composed"),
                "features": getattr(composed_variant, "implemented_features", []),
            })

        # Đánh giá qua Critic nếu cần
        if mock_critic_output is not None:
            critic_v = self.evaluate_critique(task_context, mock_critic_output)
            if critic_v != Verdict.APPROVE:
                return critic_v, composed_variant

        # Đánh giá qua Checker / QA
        checker_v = self.evaluate(task_context, mock_checker_output)
        return checker_v, composed_variant


