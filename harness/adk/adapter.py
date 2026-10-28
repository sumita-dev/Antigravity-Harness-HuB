"""ADK Trajectory Adapter.

Converts Google ADK event stream and execution artifacts into Antigravity Harness
TrajectoryStore schema and event records, with strict Zero-Bloat lazy loading
and Zero-Secret sanitization.
"""

from __future__ import annotations

import importlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

# Sensitive key patterns for automatic sanitization
SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password|auth|credential|private[_-]?key)",
    re.IGNORECASE,
)


def is_adk_available() -> bool:
    """Check if google.adk package is installed and importable."""
    try:
        importlib.import_module("google.adk")
        return True
    except (ImportError, AttributeError):
        return False


def _sanitize_data(data: Any) -> Any:
    """Recursively redact sensitive tokens or credentials from payloads."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if SENSITIVE_KEY_PATTERN.search(str(k)):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_data(item) for item in data]
    elif isinstance(data, str):
        # Redact obvious token formats like "Bearer ..." or "AIzaSy..."
        if data.startswith("Bearer "):
            return "Bearer [REDACTED]"
        if re.search(r"AIza[0-9A-Za-z-_]{35}", data):
            return re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", data)
        return data
    return data


class ADKTrajectoryAdapter:
    """Adapter bridging Google ADK Runner events to Harness TrajectoryStore.

    Supports both live ADK event objects and mock/dict event streams. Operates in
    safe fallback mode when google.adk is not installed.
    """

    def __init__(self, trajectory_store: Optional[Any] = None) -> None:
        self.trajectory_store = trajectory_store
        self._adk_available = is_adk_available()

    @property
    def is_available(self) -> bool:
        """Return whether native google.adk is available in current environment."""
        return self._adk_available

    def adapt_event(
        self,
        raw_event: Union[dict, Any],
        task_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Convert an ADK Runner event (dict or object) into a Harness event dictionary.

        Output schema conforms to TrajectoryStore.record_event:
        {
            "event_type": str,
            "task_id": str,
            "parent_id": Optional[str],
            "timestamp": str (ISO-8601 UTC),
            "payload": dict (sanitized)
        }
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Handle dictionary input
        if isinstance(raw_event, dict):
            event_type = (
                raw_event.get("event_type")
                or raw_event.get("type")
                or raw_event.get("name")
                or "adk_event"
            )
            resolved_task_id = (
                task_id
                or raw_event.get("task_id")
                or raw_event.get("session_id")
                or "adk-task"
            )
            resolved_parent_id = (
                parent_id
                or raw_event.get("parent_id")
            )
            timestamp = raw_event.get("timestamp") or now_iso

            # Extract or build payload
            payload = raw_event.get("payload")
            if payload is None:
                # Wrap residual fields into payload
                payload = {
                    k: v
                    for k, v in raw_event.items()
                    if k not in {"event_type", "type", "task_id", "session_id", "parent_id", "timestamp"}
                }

            return {
                "event_type": str(event_type),
                "task_id": str(resolved_task_id),
                "parent_id": str(resolved_parent_id) if resolved_parent_id else None,
                "timestamp": str(timestamp),
                "payload": _sanitize_data(payload),
            }

        # Handle object input (ADK event instances)
        event_type = getattr(
            raw_event,
            "event_type",
            getattr(raw_event, "type", raw_event.__class__.__name__),
        )
        resolved_task_id = (
            task_id
            or getattr(raw_event, "task_id", None)
            or getattr(raw_event, "session_id", None)
            or "adk-task"
        )
        resolved_parent_id = (
            parent_id
            or getattr(raw_event, "parent_id", None)
        )
        timestamp = getattr(raw_event, "timestamp", now_iso)

        if hasattr(raw_event, "to_dict") and callable(raw_event.to_dict):
            payload = raw_event.to_dict()
        elif hasattr(raw_event, "__dict__"):
            payload = {
                k: v
                for k, v in raw_event.__dict__.items()
                if not k.startswith("_") and k not in {"event_type", "type", "task_id", "session_id", "parent_id", "timestamp"}
            }
        else:
            payload = {"raw_repr": repr(raw_event)}

        return {
            "event_type": str(event_type),
            "task_id": str(resolved_task_id),
            "parent_id": str(resolved_parent_id) if resolved_parent_id else None,
            "timestamp": str(timestamp),
            "payload": _sanitize_data(payload),
        }

    def adapt_step(self, event_or_step: Union[dict, Any]) -> dict[str, Any]:
        """Convert an ADK event or intermediate result into a Harness trajectory step.

        Output schema conforms to TrajectoryStore.save_trajectory 'steps':
        {
            "step": str,
            "data": dict
        }
        """
        if isinstance(event_or_step, dict):
            step_name = (
                event_or_step.get("step")
                or event_or_step.get("action")
                or event_or_step.get("stage")
                or event_or_step.get("event_type")
                or event_or_step.get("type")
                or "ADK_STEP"
            )
            step_data = event_or_step.get("data")
            if step_data is None:
                step_data = {
                    k: v
                    for k, v in event_or_step.items()
                    if k not in {"step"}
                }
            return {
                "step": str(step_name),
                "data": _sanitize_data(step_data),
            }

        # Handle object
        step_name = getattr(
            event_or_step,
            "step",
            getattr(
                event_or_step,
                "action",
                getattr(
                    event_or_step,
                    "event_type",
                    getattr(event_or_step, "type", event_or_step.__class__.__name__),
                ),
            ),
        )
        if hasattr(event_or_step, "data"):
            step_data = event_or_step.data
        elif hasattr(event_or_step, "to_dict") and callable(event_or_step.to_dict):
            step_data = event_or_step.to_dict()
        elif hasattr(event_or_step, "__dict__"):
            step_data = {
                k: v for k, v in event_or_step.__dict__.items() if not k.startswith("_")
            }
        else:
            step_data = {"repr": repr(event_or_step)}

        return {
            "step": str(step_name),
            "data": _sanitize_data(step_data),
        }

    def to_trajectory_record(
        self,
        task_id: str,
        branch: str,
        task_description: str,
        events: list[Any],
        final_verdict: str,
        critique_rounds: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Assemble full trajectory record ready for TrajectoryStore.save_trajectory."""
        adapted_steps = [self.adapt_step(e) for e in events]
        meta = metadata or {}
        meta["adapter"] = "ADKTrajectoryAdapter"
        meta["adk_available"] = self._adk_available

        return {
            "task_id": task_id,
            "branch": branch,
            "task_description": task_description,
            "steps": adapted_steps,
            "final_verdict": final_verdict,
            "critique_rounds": critique_rounds,
            "metadata": _sanitize_data(meta),
        }

    def record_adk_event(
        self,
        task_id: str,
        raw_event: Any,
        parent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record an ADK event directly into the configured TrajectoryStore."""
        adapted = self.adapt_event(raw_event, task_id=task_id, parent_id=parent_id)
        if self.trajectory_store and hasattr(self.trajectory_store, "record_event"):
            return self.trajectory_store.record_event(
                task_id=adapted["task_id"],
                event_type=adapted["event_type"],
                payload=adapted["payload"],
                parent_id=adapted["parent_id"],
            )
        return adapted

    def save_adk_trajectory(
        self,
        task_id: str,
        branch: str,
        task_description: str,
        events: list[Any],
        final_verdict: str,
        critique_rounds: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Save adapted ADK trajectory directly into the configured TrajectoryStore."""
        record = self.to_trajectory_record(
            task_id=task_id,
            branch=branch,
            task_description=task_description,
            events=events,
            final_verdict=final_verdict,
            critique_rounds=critique_rounds,
            metadata=metadata,
        )
        if self.trajectory_store and hasattr(self.trajectory_store, "save_trajectory"):
            return self.trajectory_store.save_trajectory(
                task_id=record["task_id"],
                branch=record["branch"],
                task_description=record["task_description"],
                steps=record["steps"],
                final_verdict=record["final_verdict"],
                critique_rounds=record["critique_rounds"],
                metadata=record["metadata"],
            )
        return record
