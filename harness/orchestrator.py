"""Bộ điều phối trung tâm (mô phỏng state machine).

Lưu ý kiến trúc: module này KHÔNG gọi LLM API. Nó kiểm soát thứ tự bước,
đếm vòng phản biện, nạp nội dung skill, ghi trajectory và trả phán quyết.
Pipeline thật (Antigravity) dùng nó để kiểm thử luồng và lấy skill instructions.
"""

import uuid

from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.runners.app_runner import AppRunner
from harness.runners.marketing_runner import MarketingRunner
from harness.skills.router import SkillLoader, SkillRouter
from harness.state_machine import HarnessState, HarnessTransitionError, TaskContext


class ChiefOrchestrator:
    def __init__(self):
        from harness.memory.harvester import LearningHarvester
        from harness.memory.trajectory import TrajectoryStore

        self.quality_gate = AdversarialQualityGate(max_rounds=2)
        self.runners = {
            "app": AppRunner(self.quality_gate),
            "marketing": MarketingRunner(self.quality_gate),
        }
        # Giữ tên cũ để không phá vỡ code bên ngoài đang tham chiếu
        self.app_runner = self.runners["app"]
        self.marketing_runner = self.runners["marketing"]
        self.trajectory_store = TrajectoryStore()
        self.learning_harvester = LearningHarvester()
        self.skill_router = SkillRouter()
        self.skill_loader = SkillLoader()

    # ----------------------- nội bộ -----------------------
    def _attach_skill(self, context: TaskContext, skill_name) -> None:
        """Nạp nội dung skill và ghi bằng chứng đã nạp vào trace (không bỏ phí)."""
        if not skill_name or context.skill_instructions is not None:
            return
        context.active_skill = skill_name
        context.skill_path = self.skill_loader.find_skill_path(skill_name)
        context.skill_instructions = self.skill_loader.load_instructions(skill_name)
        context.record_step("SKILL_LOAD", {
            "skill": skill_name,
            "path": context.skill_path,
            "chars": len(context.skill_instructions or ""),
        })

    def _finish(self, context: TaskContext, task_description: str, verdict):
        final = verdict.value if isinstance(verdict, Verdict) else str(verdict)
        trajectory = self.trajectory_store.save_trajectory(
            task_id=context.task_id,
            branch=context.branch,
            task_description=task_description,
            steps=context.trace_steps,
            final_verdict=final,
            critique_rounds=context.critique_rounds,
            metadata={
                "active_skill": context.active_skill,
                "skill_path": context.skill_path,
                "skill_chars": len(context.skill_instructions or ""),
            },
        )
        self.learning_harvester.harvest(trajectory)
        return trajectory

    # ----------------------- API công khai -----------------------
    def process_task(self, task_description: str, branch: str = None,
                     mock_checker_output: str = "VERDICT: APPROVE",
                     context: TaskContext = None, task_id: str = None,
                     review_rounds: int = 1):
        """Chạy một task.

        review_rounds > 1 mô phỏng hàng đợi review nhiều vòng — đây là cách
        duy nhất kích hoạt được Stagnation Circuit Breaker từ CLI.
        """
        skill = None
        if branch is None or branch == "auto":
            skill, branch = self.skill_router.route(task_description)

        if context is None:
            context = TaskContext(task_id=task_id or str(uuid.uuid4()), branch=branch)

        if context.state == HarnessState.INIT:
            context.transition(HarnessState.INTAKE)
            context.record_step("INTAKE", {"description": task_description})
            self._attach_skill(context, context.active_skill or skill)
            context.relevant_patterns = self.learning_harvester.retrieve_relevant_patterns(
                task_description, branch)

        runner = self.runners.get(branch)
        if runner is None:
            context.safe_transition(HarnessState.ESCALATED)
            verdict = Verdict.ESCALATE
        else:
            try:
                verdict = runner.run(task_description, context, mock_checker_output)
                for _ in range(max(0, review_rounds - 1)):
                    if context.state in (HarnessState.APPROVED, HarnessState.ESCALATED):
                        break
                    verdict = self.submit_for_review(context, mock_checker_output)
            except HarnessTransitionError:
                # Không làm sập CLI vì một bước chuyển trạng thái sai
                context.safe_transition(HarnessState.ESCALATED)
                verdict = Verdict.ESCALATE

        self._finish(context, task_description, verdict)
        return context, verdict

    def submit_for_review(self, context: TaskContext, checker_output: str):
        """Nộp sản phẩm cho Checker. An toàn khi task đã kết thúc."""
        if context.state == HarnessState.APPROVED:
            return Verdict.APPROVE
        if context.state == HarnessState.ESCALATED:
            return Verdict.ESCALATE
        if context.state != HarnessState.AUDIT:
            if not context.safe_transition(HarnessState.AUDIT):
                context.safe_transition(HarnessState.ESCALATED)
                return Verdict.ESCALATE
        return self.quality_gate.evaluate(context, checker_output)
