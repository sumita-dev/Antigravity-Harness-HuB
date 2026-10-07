"""Persistent checkpoints for Gemini's native agents; no agent/API execution.

Actor IDs and execution reports are supplied by the runtime, not authenticated.
Each task is one atomic JSON transaction containing state, events and evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from contextlib import contextmanager
from datetime import datetime, timezone


class WorkflowError(ValueError):
    """Invalid, stale or incomplete workflow submission."""


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{name} must be a nonempty string")
    return value.strip()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class AppWorkflowStore:
    NEXT_AGENT = {"DESIGN": "architect", "DESIGN_REVIEW": "design_reviewer", "SIGN_OFF": "human",
                  "IMPLEMENTATION": "builder", "AUDIT": "qa_auditor", "APPROVED": None, "ESCALATED": None}
    EXCLUDED_DIRS = {".git", ".brain", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
                     ".next", "dist", "build", "coverage", ".cache", "test-results", "playwright-report"}

    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("HARNESS_BRAIN_DIR", Path(__file__).resolve().parents[1] / ".brain")) / "app_workflows"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", task_id):
            raise WorkflowError("Invalid task ID")
        if task_id.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise WorkflowError("Reserved task ID")
        return self.root / f"{task_id}.json"

    @contextmanager
    def _locked(self, task_id):
        path = self._path(task_id)
        lock = path.with_suffix(".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise WorkflowError("Task is locked; retry later. For abandoned locks verify no writer before removing lock.") from exc
        try:
            os.close(fd)
            yield path
        finally:
            lock.unlink()

    def _load(self, path):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise WorkflowError(f"Cannot read workflow: {exc}") from exc
        if not isinstance(state, dict):
            raise WorkflowError("Workflow must be an object")
        if state.get("schema_version") != 1 or state.get("stage") not in self.NEXT_AGENT:
            raise WorkflowError("Unsupported or corrupt workflow schema/stage")
        if state.get("task_id") != path.stem or not isinstance(state.get("events"), list):
            raise WorkflowError("Corrupt task identity/events")
        if type(state.get("revision")) is not int or state["revision"] < 1 or not isinstance(state.get("actors"), dict):
            raise WorkflowError("Corrupt revision/actors")
        counters = state.get("reject_counts")
        if not isinstance(counters, dict) or any(type(counters.get(p)) is not int or counters[p] < 0 for p in ("design", "code")):
            raise WorkflowError("Corrupt reject counters")
        _text(state.get("project_root"), "project_root")
        if not isinstance(state.get("evidence"), list):
            raise WorkflowError("Corrupt evidence")
        if any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
               or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) for item in state["evidence"]):
            raise WorkflowError("Corrupt evidence record")
        if state["stage"] in {"DESIGN_REVIEW", "SIGN_OFF", "IMPLEMENTATION", "AUDIT", "APPROVED"}:
            if not isinstance(state.get("spec"), dict) or _hash(_canonical(state["spec"])) != state.get("spec_sha256"):
                raise WorkflowError("Corrupt spec binding")
        if state["stage"] in {"AUDIT", "APPROVED"}:
            if not isinstance(state.get("manifest"), dict) or _hash(_canonical(state["manifest"])) != state.get("manifest_sha256"):
                raise WorkflowError("Corrupt manifest binding")
        return state

    def _save(self, path, state, action, actor):
        state["revision"] += 1
        state["next_agent"] = self.NEXT_AGENT[state["stage"]]
        state["events"].append({"revision": state["revision"], "action": action, "actor": actor,
                                "stage": state["stage"], "timestamp": datetime.now(timezone.utc).isoformat()})
        temporary = path.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return state

    def _stage(self, state, expected):
        if state["stage"] != expected:
            raise WorkflowError(f"Expected {expected}, got {state['stage']}")

    def _binding(self, state, supplied, key):
        if supplied != state.get(key):
            raise WorkflowError(f"Stale or invalid {key}")

    def _manifest(self, state):
        root = Path(state["project_root"])
        if not root.is_dir():
            raise WorkflowError("Project directory missing")
        entries = {}
        for current, dirs, files in os.walk(root, followlinks=False):
            for directory in dirs:
                if directory not in self.EXCLUDED_DIRS and (Path(current) / directory).is_symlink():
                    raise WorkflowError(f"Symlink directory in manifest: {directory}")
            dirs[:] = sorted(d for d in dirs if d not in self.EXCLUDED_DIRS)
            for name in sorted(files):
                file = Path(current) / name
                if file.suffix.lower() in {".log", ".pyc"}:
                    continue
                if file.is_symlink() or any(parent.is_symlink() for parent in file.parents if parent != root.parent):
                    raise WorkflowError(f"Symlink in manifest: {file}")
                try:
                    entries[file.relative_to(root).as_posix()] = _hash(file.read_bytes())
                except OSError as exc:
                    raise WorkflowError(f"Cannot hash manifest file {file}") from exc
        if not entries:
            raise WorkflowError("Empty implementation manifest")
        return entries, _hash(_canonical(entries))

    def _evidence(self, value):
        file = Path(_text(value, "evidence path")).resolve()
        if not file.is_file() or file.stat().st_size == 0:
            raise WorkflowError("Missing or empty evidence file")
        return {"path": str(file), "sha256": _hash(file.read_bytes())}

    def create(self, task_id, description, project_root):
        project = Path(project_root).resolve()
        if not project.is_dir():
            raise WorkflowError("project_root must be an existing directory")
        with self._locked(task_id) as path:
            if path.exists():
                raise WorkflowError("Task already exists")
            state = {"schema_version": 1, "task_id": task_id, "description": _text(description, "description"),
                     "project_root": str(project), "stage": "DESIGN", "revision": 0, "events": [],
                     "reject_counts": {"design": 0, "code": 0}, "actors": {}, "evidence": []}
            return self._save(path, state, "init", "orchestrator")

    def submit_spec(self, task_id, spec, actor):
        actor = _text(actor, "actor")
        if not isinstance(spec, dict):
            raise WorkflowError("spec must be an object")
        for name in ["scope", "design", "contracts", "risks"]:
            _text(spec.get(name), name)
        criteria = spec.get("acceptance_criteria")
        if not isinstance(criteria, list) or not criteria:
            raise WorkflowError("acceptance_criteria required")
        ids = set()
        for item in criteria:
            if not isinstance(item, dict) or type(item.get("ui")) is not bool:
                raise WorkflowError("AC must have id, description, ui boolean")
            ac_id = _text(item.get("id"), "AC id")
            _text(item.get("description"), "AC description")
            if ac_id in ids:
                raise WorkflowError("Duplicate AC id")
            ids.add(ac_id)
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "DESIGN")
            if actor in {state["actors"].get("design_reviewer"), state["actors"].get("qa_auditor")}:
                raise WorkflowError("Maker and Checker actor must differ")
            state.update(spec=spec, spec_sha256=_hash(_canonical(spec)), stage="DESIGN_REVIEW")
            state["actors"]["architect"] = actor
            return self._save(path, state, "spec", actor)

    def _verdict(self, value):
        if value not in {"APPROVE", "PARTIAL_APPROVE", "REJECT", "ESCALATE"}:
            raise WorkflowError("verdict must be APPROVE, PARTIAL_APPROVE, REJECT or ESCALATE")

    def _decision(self, state, phase, verdict, approved, rejected):
        if verdict == "REJECT":
            state["reject_counts"][phase] += 1
            state["stage"] = "ESCALATED" if state["reject_counts"][phase] >= 2 else rejected
        elif verdict in {"APPROVE", "PARTIAL_APPROVE"}:
            state["stage"] = approved
        else:
            state["stage"] = "ESCALATED"

    def review_design(self, task_id, verdict, actor, spec_sha256, report):
        self._verdict(verdict)
        actor = _text(actor, "actor")
        report = _text(report, "report")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "DESIGN_REVIEW")
            self._binding(state, spec_sha256, "spec_sha256")
            if actor in {state["actors"].get("architect"), state["actors"].get("builder")}:
                raise WorkflowError("Maker and Checker actor must differ")
            state["actors"]["design_reviewer"] = actor
            state["design_review"] = {"verdict": verdict, "report": report, "spec_sha256": spec_sha256}
            self._decision(state, "design", verdict, "SIGN_OFF", "DESIGN")
            return self._save(path, state, "design-review", actor)

    def sign_off(self, task_id, spec_sha256, human_message):
        message = _text(human_message, "human_message")
        # Fail closed: never infer approval from a request, refusal or condition.
        grammar = r"(?:Sếp:\s*)?(?:Duyệt|Duyệt Spec này|Duyệt bản đặc tả này|SIGN_OFF:\s*approved|Bắt đầu code đi)"
        if not re.fullmatch(grammar, message, re.I):
            raise WorkflowError("Explicit whole approval phrase required: Duyệt / Duyệt Spec này / Duyệt bản đặc tả này / SIGN_OFF: approved / Bắt đầu code đi")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "SIGN_OFF")
            self._binding(state, spec_sha256, "spec_sha256")
            state["sign_off"] = {"spec_sha256": spec_sha256, "human_message": human_message,
                                 "identity_verification": "runtime supplied; not authenticated"}
            state["stage"] = "IMPLEMENTATION"
            return self._save(path, state, "sign-off", "human")

    def submit_implementation(self, task_id, actor, report):
        actor = _text(actor, "actor")
        report = _text(report, "report")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "IMPLEMENTATION")
            if actor in {state["actors"].get("design_reviewer"), state["actors"].get("qa_auditor")}:
                raise WorkflowError("Maker and Checker actor must differ")
            self._binding(state, state.get("sign_off", {}).get("spec_sha256"), "spec_sha256")
            manifest, digest = self._manifest(state)
            state.update(manifest=manifest, manifest_sha256=digest, implementation_report=report, stage="AUDIT", evidence=[])
            state["actors"]["builder"] = actor
            return self._save(path, state, "implementation", actor)

    def audit(self, task_id, verdict, actor, payload):
        self._verdict(verdict)
        actor = _text(actor, "actor")
        if not isinstance(payload, dict):
            raise WorkflowError("audit payload must be object")
        _text(payload.get("report"), "report")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "AUDIT")
            self._binding(state, payload.get("spec_sha256"), "spec_sha256")
            self._binding(state, payload.get("manifest_sha256"), "manifest_sha256")
            if actor in {state["actors"].get("builder"), state["actors"].get("architect")}:
                raise WorkflowError("Maker and Checker actor must differ")
            if verdict in {"APPROVE", "PARTIAL_APPROVE"} and self._manifest(state)[1] != state["manifest_sha256"]:
                raise WorkflowError("Implementation changed since submission; return to Builder explicitly")
            evidence = []
            if verdict in {"APPROVE", "PARTIAL_APPROVE"}:
                commands = payload.get("commands")
                if not isinstance(commands, list) or not commands:
                    raise WorkflowError("Independent QA command evidence required")
                for command in commands:
                    if not isinstance(command, dict):
                        raise WorkflowError("Command must be an object")
                    _text(command.get("command"), "command")
                    cwd = Path(_text(command.get("cwd"), "cwd")).resolve()
                    if not cwd.is_dir() or not cwd.is_relative_to(Path(state["project_root"])):
                        raise WorkflowError("QA cwd must be inside project")
                    if type(command.get("exit_code")) is not int or command["exit_code"] != 0:
                        raise WorkflowError("QA commands must exit zero")
                    evidence.append(self._evidence(command.get("log")))
                preview = payload.get("preview", {})
                if not isinstance(preview, dict) or not isinstance(preview.get("checks"), list):
                    raise WorkflowError("Preview checks required")
                if any(not isinstance(c, dict) or not isinstance(c.get("id"), str) for c in preview["checks"]):
                    raise WorkflowError("Preview checks require string AC IDs")
                checks = {c.get("id"): c for c in preview["checks"]}
                if len(checks) != len(preview["checks"]) or set(checks) != {ac["id"] for ac in state["spec"]["acceptance_criteria"]}:
                    raise WorkflowError("Preview must cover every AC exactly once")
                has_not_verified_ui = False
                for ac in state["spec"]["acceptance_criteria"]:
                    check = checks[ac["id"]]
                    status = check.get("status")
                    if status == "N/A" and not ac["ui"]:
                        _text(check.get("reason"), "N/A reason")
                    elif status == "PASS":
                        evidence.append(self._evidence(check.get("evidence")))
                    elif status == "NOT_VERIFIED" and ac["ui"]:
                        _text(check.get("reason"), "NOT_VERIFIED reason")
                        has_not_verified_ui = True
                    else:
                        raise WorkflowError("Every UI AC requires PASS evidence or NOT_VERIFIED with reason for PARTIAL_APPROVE; non UI N/A requires reason")
                
                if verdict == "APPROVE" and has_not_verified_ui:
                    raise WorkflowError("Full APPROVE requires PASS evidence for all UI ACs; use PARTIAL_APPROVE when browser checks are NOT_VERIFIED")

                if any(ac["ui"] for ac in state["spec"]["acceptance_criteria"]):
                    if not re.fullmatch(r"http://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?(?:/[^\s]*)?", str(preview.get("url", ""))):
                        raise WorkflowError("Local preview URL required")
                    try:
                        port = urlsplit(preview["url"]).port
                    except ValueError as exc:
                        raise WorkflowError("Invalid preview port") from exc
                    if port == 0:
                        raise WorkflowError("Invalid preview port")
            state["actors"]["qa_auditor"] = actor
            state["audit"] = payload
            state["evidence"] = evidence
            state["overall_verdict"] = verdict
            state["browser_status"] = "NOT_VERIFIED" if verdict == "PARTIAL_APPROVE" else ("PASS" if verdict == "APPROVE" else "FAIL")
            self._decision(state, "code", verdict, "APPROVED", "IMPLEMENTATION")
            return self._save(path, state, "audit", actor)

    def revise(self, task_id, reason):
        """Invalidate design approval after an explicit architecture change request."""
        reason = _text(reason, "reason")
        with self._locked(task_id) as path:
            state = self._load(path)
            if state["stage"] == "ESCALATED":
                raise WorkflowError("Escalated task requires a new task and human direction")
            for key in ["spec", "spec_sha256", "design_review", "sign_off", "manifest", "manifest_sha256", "audit", "implementation_report"]:
                state.pop(key, None)
            state.update(stage="DESIGN", evidence=[], revision_reason=reason)
            return self._save(path, state, "revise", "orchestrator")

    def status(self, task_id):
        with self._locked(task_id) as path:
            state = self._load(path)
            if state["stage"] == "APPROVED":
                if self._manifest(state)[1] != state["manifest_sha256"]:
                    raise WorkflowError("Approved implementation changed")
                for evidence in state["evidence"]:
                    if self._evidence(evidence["path"])["sha256"] != evidence["sha256"]:
                        raise WorkflowError("Approved evidence changed")
            return state
