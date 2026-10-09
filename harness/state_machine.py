from datetime import datetime, timezone
from enum import Enum, auto


class HarnessTransitionError(ValueError):
    """Chuyển trạng thái không hợp lệ (ví dụ nhảy cóc INTAKE -> IMPLEMENTATION)."""

class HarnessState(Enum):
    INIT = auto()
    INTAKE = auto()
    DESIGN = auto()
    IMPLEMENTATION = auto()
    CRITIQUE = auto()
    AUDIT = auto()
    APPROVED = auto()
    REJECTED = auto()
    ESCALATED = auto()

class TaskContext:
    def __init__(self, task_id, branch, trajectory_store=None):
        self.task_id = task_id
        self.branch = branch
        self.state = HarnessState.INIT
        self.critique_rounds = 0
        self.qa_rounds = 0
        self.total_cycles = 0
        self.trace_steps: list[dict] = []
        self.relevant_patterns: list[dict] = []
        self.active_skill = None
        self.skill_path = None
        self.skill_instructions = None
        self.trajectory_store = trajectory_store
        self.last_event_id = None

    def record_step(self, step_name: str, payload: dict):
        step_record = {
            "step": step_name,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self.trajectory_store:
            event = self.trajectory_store.record_event(
                task_id=self.task_id,
                event_type=step_name,
                payload=payload,
                parent_id=self.last_event_id
            )
            self.last_event_id = event["event_id"]
            step_record["event_id"] = event["event_id"]
            
        self.trace_steps.append(step_record)

    def transition(self, new_state: HarnessState):
        valid_transitions = {
            HarnessState.INIT: [HarnessState.INTAKE],
            # Không cho nhảy cóc: INTAKE phải qua DESIGN (đúng quy chuẩn README)
            HarnessState.INTAKE: [HarnessState.DESIGN, HarnessState.ESCALATED],
            HarnessState.DESIGN: [HarnessState.IMPLEMENTATION, HarnessState.ESCALATED],
            # IMPLEMENTATION có thể sang CRITIQUE (Dynamic Triad) hoặc AUDIT (Fast-Track)
            HarnessState.IMPLEMENTATION: [HarnessState.CRITIQUE, HarnessState.AUDIT, HarnessState.ESCALATED],
            # CRITIQUE có thể sang AUDIT (đạt), quay về IMPLEMENTATION (sửa GAP), hoặc ESCALATED
            HarnessState.CRITIQUE: [HarnessState.AUDIT, HarnessState.IMPLEMENTATION, HarnessState.ESCALATED],
            # AUDIT có thể sang APPROVED, REJECTED, IMPLEMENTATION (test fail sửa nhanh), CRITIQUE (GAP kiến trúc), ESCALATED
            HarnessState.AUDIT: [HarnessState.APPROVED, HarnessState.REJECTED, HarnessState.IMPLEMENTATION, HarnessState.CRITIQUE, HarnessState.ESCALATED],
            HarnessState.REJECTED: [HarnessState.IMPLEMENTATION, HarnessState.CRITIQUE, HarnessState.ESCALATED],
            HarnessState.APPROVED: [],
            HarnessState.ESCALATED: []
        }
        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
            return True
        raise HarnessTransitionError(f"Invalid transition from {self.state} to {new_state}")

    def safe_transition(self, new_state: HarnessState) -> bool:
        """Chuyển trạng thái an toàn: trả về False thay vì ném lỗi."""
        try:
            return self.transition(new_state)
        except HarnessTransitionError:
            return False

    def increment_critique(self, max_rounds=2):
        self.critique_rounds += 1
        self.total_cycles += 1
        if self.critique_rounds >= max_rounds:
            self.safe_transition(HarnessState.ESCALATED)
            return False
        return True

    def increment_qa(self, max_rounds=2):
        self.qa_rounds += 1
        self.total_cycles += 1
        if self.qa_rounds >= max_rounds:
            self.safe_transition(HarnessState.ESCALATED)
            return False
        return True

    def check_total_cycles(self, max_cycles=3):
        if self.total_cycles >= max_cycles:
            self.safe_transition(HarnessState.ESCALATED)
            return False
        return True
