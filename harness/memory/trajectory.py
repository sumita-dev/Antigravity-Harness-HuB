import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))


class TrajectoryStore:
    DEFAULT_PATH = BRAIN_DIR / "trajectories" / "trajectories.jsonl"

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

    def record_event(self, task_id: str, event_type: str, payload: dict, parent_id: str = None) -> dict:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "task_id": task_id,
            "event_type": event_type,
            "parent_id": parent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        events_path = self.path.parent / "events.jsonl"
        with open(events_path, "a") as f:
            f.write(json.dumps(event) + "\n")
        return event

    def get_events(self, task_id: str) -> list[dict]:
        events_path = self.path.parent / "events.jsonl"
        if not events_path.exists():
            return []
        
        events = []
        with open(events_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("task_id") == task_id:
                    events.append(record)
        
        events.sort(key=lambda x: x.get("timestamp", ""))
        return events

    def replay_events(self, task_id: str) -> list[dict]:
        events = self.get_events(task_id)
        if not events:
            return []
            
        # Optional: could link by parent_id, but sorted by timestamp is usually enough
        return events
