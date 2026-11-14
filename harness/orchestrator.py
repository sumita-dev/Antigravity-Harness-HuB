"""Bộ điều phối trung tâm (mô phỏng state machine).

Lưu ý kiến trúc: module này KHÔNG gọi LLM API. Nó kiểm soát thứ tự bước,
đếm vòng phản biện, nạp nội dung skill, ghi trajectory và trả phán quyết.
Pipeline thật (Antigravity) dùng nó để kiểm thử luồng và lấy skill instructions.
"""

import uuid
from typing import Optional

from harness.evidence_cache import EvaluationCache, EvidenceTreeBuilder
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.runners.app_runner import AppRunner
from harness.runners.marketing_runner import MarketingRunner
from harness.skills.router import SkillLoader, SkillRouter
from harness.state_machine import HarnessState, HarnessTransitionError, TaskContext


class ChiefOrchestrator:
    def __init__(self):
        from harness.memory.distiller import SkillDistiller
        from harness.memory.harvester import LearningHarvester
        from harness.memory.trajectory import TrajectoryStore
        from harness.skills.curator import SkillCurator
        from harness.skills.manager import SkillManager

        self.evaluation_cache = EvaluationCache()
        self.evidence_builder = EvidenceTreeBuilder()
        self.quality_gate = AdversarialQualityGate(
            max_rounds=2,
            cache=self.evaluation_cache,
            evidence_builder=self.evidence_builder,
        )
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
        self.skill_manager = SkillManager()
        self.skill_curator = SkillCurator(skill_loader=self.skill_loader, skill_manager=self.skill_manager)
        self.skill_distiller = SkillDistiller(
            trajectory_store=self.trajectory_store,
            harvester=self.learning_harvester,
            skill_manager=self.skill_manager,
        )

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
        self.skill_curator.track_usage(skill_name, task_id=context.task_id)

    def _finish(self, context: TaskContext, task_description: str, verdict, auto_distill: bool = False):
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
                "cache_stats": self.evaluation_cache.stats(),
            },
        )
        self.learning_harvester.harvest(trajectory)
        if auto_distill and final == "APPROVE":
            self.skill_distiller.auto_distill(trajectory)
        return trajectory

    # ----------------------- API công khai -----------------------
    def process_task(self, task_description: str, branch: str = None,
                     mock_checker_output: str = "VERDICT: APPROVE",
                     context: TaskContext = None, task_id: str = None,
                     review_rounds: int = 1, auto_distill: bool = False):
        """Chạy một task.

        review_rounds > 1 mô phỏng hàng đợi review nhiều vòng — đây là cách
        duy nhất kích hoạt được Stagnation Circuit Breaker từ CLI.
        """
        routed_skill, routed_branch = self.skill_router.route(task_description)
        if branch is None or branch == "auto":
            skill = routed_skill
            branch = routed_branch
        else:
            routed_skill_branch = self.skill_router.routing_table.get(routed_skill, {}).get("branch", routed_branch)
            skill = routed_skill if (routed_skill and routed_skill_branch == branch) else None

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

        self._finish(context, task_description, verdict, auto_distill=auto_distill)
        return context, verdict

    def fan_out_tasks(
        self,
        task_list: list[str],
        branch: str = "app",
        max_concurrency: int = 4,
        mock_checker_output: str = "VERDICT: APPROVE",
        auto_distill: bool = False,
    ) -> list[tuple[TaskContext, Verdict]]:
        """Thực thi song song danh sách sub-tasks theo mô hình Fan-Out/Fan-In (Spec-Kit).

        Chia nhỏ danh sách task độc lập từ tasks.md, dispatch qua ThreadPoolExecutor
        với giới hạn max_concurrency và gom toàn bộ kết quả trả về.
        """
        import concurrent.futures

        if not task_list:
            return []

        concurrency = max(1, min(max_concurrency, len(task_list)))
        results: list[tuple[TaskContext, Verdict]] = []

        def _execute_single(sub_task_desc: str):
            sub_ctx = TaskContext(task_id=str(uuid.uuid4()), branch=branch)
            return self.process_task(
                task_description=sub_task_desc,
                branch=branch,
                mock_checker_output=mock_checker_output,
                context=sub_ctx,
                auto_distill=auto_distill,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_task = {
                executor.submit(_execute_single, desc): desc
                for desc in task_list
            }
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    err_ctx = TaskContext(task_id=str(uuid.uuid4()), branch=branch)
                    err_ctx.record_step("FAN_OUT_ERROR", {"task": future_to_task[future], "error": str(exc)})
                    err_ctx.safe_transition(HarnessState.ESCALATED)
                    results.append((err_ctx, Verdict.ESCALATE))

        return results

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
        if checker_output.strip() == "VERDICT: REJECT":
            return self.quality_gate.evaluate(context, checker_output)
        return self.quality_gate.evaluate_audit(context, checker_output)
