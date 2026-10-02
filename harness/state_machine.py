from enum import Enum, auto

class HarnessState(Enum):
    INIT = auto()
    INTAKE = auto()
    DESIGN = auto()
    IMPLEMENTATION = auto()
    AUDIT = auto()
    APPROVED = auto()
    REJECTED = auto()
    ESCALATED = auto()

class TaskContext:
    def __init__(self, task_id, branch):
        self.task_id = task_id
        self.branch = branch
        self.state = HarnessState.INIT
        self.critique_rounds = 0
        self.trace_steps: list[dict] = []
        self.relevant_patterns: list[dict] = []
        self.active_skill = None
        self.skill_instructions = None

    def record_step(self, step_name: str, payload: dict):
        from datetime import datetime
        self.trace_steps.append({
            "step": step_name,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        })

    def transition(self, new_state: HarnessState):
        valid_transitions = {
            HarnessState.INIT: [HarnessState.INTAKE],
            HarnessState.INTAKE: [HarnessState.DESIGN, HarnessState.IMPLEMENTATION, HarnessState.ESCALATED],
            HarnessState.DESIGN: [HarnessState.IMPLEMENTATION, HarnessState.ESCALATED],
            HarnessState.IMPLEMENTATION: [HarnessState.AUDIT, HarnessState.ESCALATED],
            HarnessState.AUDIT: [HarnessState.APPROVED, HarnessState.REJECTED, HarnessState.IMPLEMENTATION, HarnessState.ESCALATED],
            HarnessState.REJECTED: [HarnessState.ESCALATED],
            HarnessState.APPROVED: [],
            HarnessState.ESCALATED: []
        }
        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
            return True
        raise ValueError(f"Invalid transition from {self.state} to {new_state}")

    def increment_critique(self, max_rounds=2):
        self.critique_rounds += 1
        if self.critique_rounds > max_rounds:
            self.transition(HarnessState.ESCALATED)
            return False
        return True
