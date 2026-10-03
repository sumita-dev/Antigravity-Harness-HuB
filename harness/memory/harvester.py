"""Learning Harvester: rút thông tin thật từ trajectory để tái sử dụng.

Lưu ý: đây là bộ trích xuất dựa trên luật (rule-based), KHÔNG phải học máy.
Nó ghi lại: task nào thành công/thất bại, dùng skill nào, qua bao nhiêu bước,
bao nhiêu vòng phản biện — để lần sau tra cứu nhanh.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))

SUCCESS_VERDICTS = {"APPROVE"}
FAILURE_VERDICTS = {"REJECT", "ESCALATE"}


class LearningHarvester:
    DEFAULT_PATH = BRAIN_DIR / "learnings" / "patterns.json"
    MAX_PATTERNS = 50

    def __init__(self, path=None, max_patterns: int = None):
        self.path = Path(path) if path else self.DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_patterns = max_patterns or self.MAX_PATTERNS
        self.patterns = self._load_patterns()

    # ----------------------- I/O -----------------------
    def _load_patterns(self) -> list:
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_patterns(self) -> None:
        if len(self.patterns) > self.max_patterns:
            # Giữ các pattern mới nhất theo timestamp (ISO-8601 so sánh chuỗi được)
            self.patterns = sorted(self.patterns,
                                   key=lambda p: p.get("timestamp", ""))[-self.max_patterns:]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.patterns, f, indent=2, ensure_ascii=False)

    # ----------------------- trích xuất -----------------------
    @staticmethod
    def _summarize_steps(steps: list) -> str:
        names = [s.get("step", "?") for s in steps]
        return "→".join(names) if names else "không có bước nào"

    def harvest(self, trajectory: dict):
        """Rút pattern từ 1 trajectory. Trả về pattern hoặc None."""
        verdict = str(trajectory.get("final_verdict", ""))
        steps = trajectory.get("steps") or []
        rounds = trajectory.get("critique_rounds", 0)
        metadata = trajectory.get("metadata") or {}
        skill = metadata.get("active_skill") or "không dùng skill"
        steps_summary = self._summarize_steps(steps)
        now = datetime.now(timezone.utc).isoformat()
        pattern = None

        if verdict in SUCCESS_VERDICTS:
            pattern = {
                "id": str(uuid.uuid4()),
                "branch": trajectory.get("branch"),
                "pattern_type": "SUCCESS",
                "description": trajectory.get("task_description"),
                "trigger": f"skill={skill}",
                "solution_summary": (
                    f"APPROVE sau {len(steps)} bước ({steps_summary}), "
                    f"{rounds} vòng phản biện"
                ),
                "timestamp": now,
            }
        elif verdict in FAILURE_VERDICTS:
            pattern = {
                "id": str(uuid.uuid4()),
                "branch": trajectory.get("branch"),
                "pattern_type": "ANTI_PATTERN",
                "description": trajectory.get("task_description"),
                "trigger": f"skill={skill}",
                "failure_reason": (
                    f"Kết thúc {verdict} sau {rounds} vòng phản biện ({steps_summary})"
                ),
                "avoidance_advice": (
                    "Xem lại trajectory: thiếu đặc tả/bằng chứng, hoặc lặp cùng lỗi "
                    "qua nhiều vòng review (đã chạm circuit breaker)"
                ),
                "timestamp": now,
            }

        if pattern:
            self.patterns.append(pattern)
            self._save_patterns()
        return pattern

    def retrieve_relevant_patterns(self, task_description: str, branch: str = None) -> list:
        """Tìm pattern liên quan bằng trùng khớp từ (rule-based, đủ cho tra cứu nhanh)."""
        words = {w for w in task_description.lower().split() if len(w) > 2}
        scored = []
        for p in self.patterns:
            if branch and p.get("branch") != branch:
                continue
            desc = str(p.get("description", "")).lower()
            score = len(words & set(desc.split()))
            if desc and desc in task_description.lower():
                score += 5
            if score:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored]
