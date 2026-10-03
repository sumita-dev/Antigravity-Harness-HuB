import json
import os
import uuid
from datetime import datetime
from pathlib import Path

BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))


class LearningHarvester:
    DEFAULT_PATH = BRAIN_DIR / "learnings" / "patterns.json"

    def __init__(self, path=None):
        self.path = Path(path) if path else self.DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.patterns = self._load_patterns()

    def _load_patterns(self):
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _save_patterns(self):
        # Keep maximum 50 patterns (prune oldest)
        if len(self.patterns) > 50:
            # Sort by timestamp to ensure we drop oldest. 
            # If timestamp is ISO format, string sort works, else we rely on insertion order.
            self.patterns = self.patterns[-50:]
            
        with open(self.path, "w") as f:
            json.dump(self.patterns, f, indent=2)

    def harvest(self, trajectory: dict) -> dict:
        pattern = None
        now = datetime.utcnow().isoformat()
        
        if trajectory.get("final_verdict") == "APPROVE":
            pattern = {
                "id": str(uuid.uuid4()),
                "branch": trajectory.get("branch"),
                "pattern_type": "SUCCESS",
                "description": trajectory.get("task_description"),
                "trigger": "Task matched description",
                "solution_summary": "Derived from successful trajectory steps",
                "timestamp": now
            }
        elif trajectory.get("final_verdict") in ["ESCALATE", "REJECT"]:
            pattern = {
                "id": str(uuid.uuid4()),
                "branch": trajectory.get("branch"),
                "pattern_type": "ANTI_PATTERN",
                "description": trajectory.get("task_description"),
                "failure_reason": "Failed quality gate or max critiques reached",
                "avoidance_advice": "Review failure trajectory steps",
                "timestamp": now
            }
            
        if pattern:
            self.patterns.append(pattern)
            self._save_patterns()
            
        return pattern

    def retrieve_relevant_patterns(self, task_description: str, branch: str = None) -> list[dict]:
        relevant = []
        task_desc_lower = task_description.lower()
        for p in self.patterns:
            if branch and p.get("branch") != branch:
                continue
            
            # Simple keyword matching
            # In a real scenario we'd use NLP/embeddings
            if p.get("description", "").lower() in task_desc_lower or \
               any(word in p.get("description", "").lower() for word in task_desc_lower.split()):
                relevant.append(p)
        return relevant
