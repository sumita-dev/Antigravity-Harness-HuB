import json
import os
from pathlib import Path

class TrajectoryStore:
    DEFAULT_PATH = Path(".brain/trajectories/trajectories.jsonl")

    def __init__(self, path=None):
        self.path = Path(path) if path else self.DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save_trajectory(self, task_id: str, branch: str, task_description: str, steps: list, final_verdict: str, critique_rounds: int, metadata: dict = None) -> dict:
        record = {
            "task_id": task_id,
            "branch": branch,
            "task_description": task_description,
            "steps": steps,
            "final_verdict": final_verdict,
            "critique_rounds": critique_rounds,
            "metadata": metadata or {}
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def get_trajectories(self, branch: str = None, verdict: str = None) -> list[dict]:
        if not self.path.exists():
            return []
        
        trajectories = []
        with open(self.path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                if branch and record.get("branch") != branch:
                    continue
                if verdict and record.get("final_verdict") != verdict:
                    continue
                trajectories.append(record)
        return trajectories
