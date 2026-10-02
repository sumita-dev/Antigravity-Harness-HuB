from harness.state_machine import TaskContext, HarnessState
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.runners.app_runner import AppRunner
from harness.runners.marketing_runner import MarketingRunner

class ChiefOrchestrator:
    def __init__(self):
        from harness.memory.trajectory import TrajectoryStore
        from harness.memory.harvester import LearningHarvester
        self.quality_gate = AdversarialQualityGate(max_rounds=2)
        self.app_runner = AppRunner(self.quality_gate)
        self.marketing_runner = MarketingRunner(self.quality_gate)
        self.trajectory_store = TrajectoryStore()
        self.learning_harvester = LearningHarvester()

    def process_task(self, task_description: str, branch: str, mock_checker_output: str = "VERDICT: APPROVE"):
        context = TaskContext(task_id="task_1", branch=branch)
        
        relevant_patterns = self.learning_harvester.retrieve_relevant_patterns(task_description, branch)
        context.relevant_patterns = relevant_patterns

        context.transition(HarnessState.INTAKE)
        context.record_step("INTAKE", {"description": task_description})
        context.record_step("DESIGN", {})
        context.record_step("IMPLEMENTATION", {})
        context.record_step("AUDIT", {})
        
        if branch == "app":
            verdict = self.app_runner.run(task_description, context, mock_checker_output)
        elif branch == "marketing":
            verdict = self.marketing_runner.run(task_description, context, mock_checker_output)
        else:
            context.transition(HarnessState.ESCALATED)
            verdict = Verdict.ESCALATE

        trajectory = self.trajectory_store.save_trajectory(
            task_id=context.task_id,
            branch=branch,
            task_description=task_description,
            steps=context.trace_steps,
            final_verdict=verdict.name if hasattr(verdict, 'name') else str(verdict),
            critique_rounds=context.critique_rounds
        )
        self.learning_harvester.harvest(trajectory)
        
        return context, verdict

    def submit_for_review(self, context: TaskContext, checker_output: str):
        if context.state != HarnessState.AUDIT:
            context.transition(HarnessState.AUDIT)
            
        verdict = self.quality_gate.evaluate(context, checker_output)
        return verdict
