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


def _is_junction(path):
    if hasattr(path, "is_junction"):
        try:
            return path.is_junction()
        except OSError:
            pass
    if os.name == "nt" and path.exists():
        try:
            st = os.lstat(path)
            return bool(getattr(st, "st_file_attributes", 0) & 1024)
        except OSError:
            pass
    return False


def _is_link(path):
    return path.is_symlink() or _is_junction(path)


class AppWorkflowStore:
    NEXT_AGENT = {"DESIGN": "architect", "DESIGN_REVIEW": "design_reviewer", "SIGN_OFF": "human",
                  "IMPLEMENTATION": "builder", "AUDIT": "qa_auditor",
                  "AUDIT_PENDING_BROWSER": "human_browser_verification",
                  "APPROVED": None, "ESCALATED": None}
    EXCLUDED_DIRS = {".git", ".gitnexus", ".brain", "node_modules", ".venv", "venv", ".pytest_cache", ".cache"}
    DOWNSTREAM = {"manifest", "manifest_sha256", "implementation_report", "audit", "evidence",
                  "overall_verdict", "browser_status", "functional_status", "http_status", "qa_actor_id",
                  "browser_verification", "browser_verification_request"}

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

    def _load(self, path, *, allow_legacy_revalidation=False):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise WorkflowError(f"Cannot read workflow: {exc}") from exc
        if not isinstance(state, dict):
            raise WorkflowError("Workflow must be an object")
        if (type(state.get("schema_version")) is not int or state["schema_version"] not in {1, 2}
                or not isinstance(state.get("stage"), str) or state["stage"] not in self.NEXT_AGENT):
            raise WorkflowError("Unsupported or corrupt workflow schema/stage")
        if state.get("task_id") != path.stem or not isinstance(state.get("events"), list):
            raise WorkflowError("Corrupt task identity/events")
        if type(state.get("revision")) is not int or state["revision"] < 1 or not isinstance(state.get("actors"), dict):
            raise WorkflowError("Corrupt revision/actors")
        if any(not isinstance(actor, str) or not actor.strip() for actor in state["actors"].values()):
            raise WorkflowError("Corrupt actor identity")
        makers = {state["actors"][role] for role in ("architect", "builder") if role in state["actors"]}
        checkers = {state["actors"][role] for role in ("design_reviewer", "qa_auditor", "browser_verifier") if role in state["actors"]}
        if makers & checkers:
            raise WorkflowError("Maker and Checker actor must differ")
        counters = state.get("reject_counts")
        if not isinstance(counters, dict) or any(type(counters.get(p)) is not int or counters[p] < 0 for p in ("design", "code")):
            raise WorkflowError("Corrupt reject counters")
        if any(counters[phase] >= 2 for phase in ("design", "code")) and state["stage"] != "ESCALATED":
            raise WorkflowError("Exhausted reject counters require ESCALATED stage")
        if "next_agent" not in state or state["next_agent"] != self.NEXT_AGENT[state["stage"]]:
            raise WorkflowError("Corrupt next_agent route for workflow stage")
        _text(state.get("project_root"), "project_root")
        if not isinstance(state.get("evidence"), list):
            raise WorkflowError("Corrupt evidence")
        if any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
               or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))) for item in state["evidence"]):
            raise WorkflowError("Corrupt evidence record")
        if state["stage"] in {"DESIGN_REVIEW", "SIGN_OFF", "IMPLEMENTATION", "AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"}:
            if not isinstance(state.get("spec"), dict) or _hash(_canonical(state["spec"])) != state.get("spec_sha256"):
                raise WorkflowError("Corrupt spec binding")
            self._validate_spec(state["spec"], Path(state["project_root"]))
        if state["stage"] in {"SIGN_OFF", "IMPLEMENTATION", "AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"}:
            self._validate_design(state, signed=state["stage"] != "SIGN_OFF")
        if state["schema_version"] == 1:
            if "spec" in state or "spec_sha256" in state:
                if not isinstance(state.get("spec"), dict) or _hash(_canonical(state["spec"])) != state.get("spec_sha256"):
                    raise WorkflowError("Corrupt legacy spec binding")
                self._validate_spec(state["spec"], Path(state["project_root"]))
                _text(state["actors"].get("architect"), "architect actor")
            forbidden = self.DOWNSTREAM - {"evidence"}
            dirty = (state["stage"] not in {"DESIGN", "DESIGN_REVIEW", "SIGN_OFF", "IMPLEMENTATION"}
                    or any(key in state for key in forbidden) or state["evidence"]
                    or any(not isinstance(event, dict) or event.get("action") in {
                        "implementation", "audit", "verify_browser", "audit_pending_browser"} for event in state["events"]))
            if allow_legacy_revalidation and state["stage"] in {"AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"}:
                pass
            elif dirty:
                raise WorkflowError("Legacy implementation checkpoint requires manual revalidation; preserve task history and counters")
            else:
                state["schema_version"] = 2
                self._save(path, state, "migrate-schema", "orchestrator")
        if state["stage"] in {"AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"}:
            if not isinstance(state.get("manifest"), dict) or _hash(_canonical(state["manifest"])) != state.get("manifest_sha256"):
                raise WorkflowError("Corrupt manifest binding")
        return state

    def _safe_path(self, value, name, *, absolute=True):
        path = Path(_text(value, name))
        if ".." in path.parts or (absolute and not path.is_absolute()):
            raise WorkflowError(f"{name} must be an absolute path without traversal")
        if any(_is_link(part) for part in (path, *path.parents)):
            raise WorkflowError(f"Symlink or Junction in {name}: {path}")
        return path.resolve()

    def _relative_path(self, value, name, *, allow_dot=False):
        value = _text(value, name)
        path = Path(value)
        if (path.is_absolute() or path.drive or ".." in path.parts or any(c in value for c in "*?[]")
                or (not path.parts and not allow_dot)):
            raise WorkflowError(f"{name} must be an exact root-relative path")
        return path

    def _validate_spec(self, spec, root):
        if not isinstance(spec, dict):
            raise WorkflowError("spec must be an object")
        for name in ("scope", "design", "contracts", "risks"):
            _text(spec.get(name), name)
        criteria = spec.get("acceptance_criteria")
        if not isinstance(criteria, list) or not criteria:
            raise WorkflowError("acceptance_criteria required")
        ids = set()
        for item in criteria:
            if (not isinstance(item, dict) or type(item.get("ui")) is not bool
                    or type(item.get("applicable", True)) is not bool):
                raise WorkflowError("AC must have id, description, ui/applicable booleans")
            ac_id = _text(item.get("id"), "AC id")
            if ac_id != item["id"] or ac_id in ids:
                raise WorkflowError("Duplicate or noncanonical AC id")
            _text(item.get("description"), "AC description")
            if not item.get("applicable", True):
                _text(item.get("na_reason"), "inapplicable AC na_reason")
            ids.add(ac_id)
        exclusions = spec.get("snapshot_exclusions", [])
        if not isinstance(exclusions, list):
            raise WorkflowError("snapshot_exclusions must be a list")
        paths = [self._relative_path(item, "snapshot exclusion").as_posix() for item in exclusions]
        if len(paths) != len(set(paths)):
            raise WorkflowError("Duplicate snapshot exclusion")
        if "evidence_root" in spec:
            evidence_root = self._safe_path(spec["evidence_root"], "evidence_root")
            if evidence_root.exists() and not evidence_root.is_dir():
                raise WorkflowError("evidence_root must be a directory")
        if "verification_commands" in spec:
            commands = spec["verification_commands"]
            if not isinstance(commands, list) or not commands:
                raise WorkflowError("verification_commands must be a nonempty list")
            command_ids = set()
            for command in commands:
                if not isinstance(command, dict):
                    raise WorkflowError("Spec command must be an object")
                command_id = _text(command.get("id"), "command id")
                _text(command.get("command"), "command")
                cwd = self._relative_path(command.get("cwd"), "command cwd", allow_dot=True)
                if not (root / cwd).resolve().is_relative_to(root.resolve()):
                    raise WorkflowError("Spec command cwd must be inside project")
                ac_ids = command.get("ac_ids")
                if (not isinstance(ac_ids, list) or not ac_ids or any(not isinstance(i, str) for i in ac_ids)
                        or len(ac_ids) != len(set(ac_ids)) or not set(ac_ids).issubset(ids)
                        or command_id in command_ids):
                    raise WorkflowError("Invalid Spec command IDs or AC coverage")
                command_ids.add(command_id)

    def _validate_design(self, state, *, signed=True):
        actors = state["actors"]
        architect = _text(actors.get("architect"), "architect actor")
        reviewer = _text(actors.get("design_reviewer"), "design reviewer actor")
        if reviewer in {architect, actors.get("builder")}:
            raise WorkflowError("Maker and Checker actor must differ")
        review = state.get("design_review")
        if not isinstance(review, dict) or review.get("verdict") != "APPROVE":
            raise WorkflowError("Current approved design review required")
        self._binding(state, review.get("spec_sha256"), "spec_sha256")
        _text(review.get("report"), "design review report")
        if signed:
            signoff = state.get("sign_off")
            if not isinstance(signoff, dict):
                raise WorkflowError("Current human signoff required")
            self._binding(state, signoff.get("spec_sha256"), "spec_sha256")
            grammar = r"(?:Sếp:\s*)?(?:Duyệt|Duyệt Spec này|Duyệt bản đặc tả này|SIGN_OFF:\s*approved|Bắt đầu code đi)"
            if not re.fullmatch(grammar, _text(signoff.get("human_message"), "human_message"), re.I):
                raise WorkflowError("Explicit whole approval phrase required")

    def _clear_downstream(self, state):
        for key in self.DOWNSTREAM:
            state.pop(key, None)
        state["evidence"] = []
        state["actors"].pop("browser_verifier", None)

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
            try:
                os.replace(temporary, path)
            except PermissionError:
                time.sleep(0.02)
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
        root = self._safe_path(state["project_root"], "project_root")
        if not root.is_dir():
            raise WorkflowError("Project directory missing")
        entries = {}
        excluded = set(self.EXCLUDED_DIRS) | {
            self._relative_path(item, "snapshot exclusion").as_posix()
            for item in state.get("spec", {}).get("snapshot_exclusions", [])}
        for current, dirs, files in os.walk(root, followlinks=False):
            included_dirs = []
            for directory in sorted(dirs):
                directory_path = Path(current) / directory
                if directory == "__pycache__" or directory_path.relative_to(root).as_posix() in excluded:
                    continue
                if _is_link(directory_path):
                    raise WorkflowError(f"Symlink or Junction directory in manifest: {directory}")
                included_dirs.append(directory)
            dirs[:] = included_dirs
            for name in sorted(files):
                file = Path(current) / name
                if file.suffix.lower() == ".pyc" or file.relative_to(root).as_posix() in excluded:
                    continue
                if _is_link(file) or any(_is_link(parent) for parent in file.parents if parent != root.parent):
                    raise WorkflowError(f"Symlink or Junction in manifest: {file}")
                try:
                    entries[file.relative_to(root).as_posix()] = _hash(file.read_bytes())
                except OSError as exc:
                    raise WorkflowError(f"Cannot hash manifest file {file}") from exc
        if not entries:
            raise WorkflowError("Empty implementation manifest")
        return entries, _hash(_canonical(entries))


    def _evidence(self, value, purpose=None, *, state):
        file = self._safe_path(value, "evidence path")
        roots = [self._safe_path(state["project_root"], "project_root"), self.root.parent.resolve() / "artifacts"]
        if "evidence_root" in state["spec"]:
            roots.append(self._safe_path(state["spec"]["evidence_root"], "evidence_root"))
        if not any(file.is_relative_to(root) for root in roots):
            raise WorkflowError("Evidence must stay inside project or approved artifact/evidence roots")
        if not file.is_file() or file.stat().st_size == 0:
            raise WorkflowError("Missing or empty evidence file")
        res = {"path": str(file), "sha256": _hash(file.read_bytes())}
        if purpose:
            res["purpose"] = purpose
        return res

    def _add_evidence(self, evidence_map, value, purpose=None, *, state):
        rec = self._evidence(value, purpose=purpose, state=state)
        norm = os.path.normcase(os.path.abspath(rec["path"]))
        if norm in evidence_map:
            existing = evidence_map[norm]
            if purpose:
                existing_purposes = [p.strip() for p in existing.get("purpose", "").split(",") if p.strip()]
                if purpose not in existing_purposes:
                    existing_purposes.append(purpose)
                    existing["purpose"] = ", ".join(existing_purposes)
        else:
            if "purpose" not in rec and purpose:
                rec["purpose"] = purpose
            evidence_map[norm] = rec
        return evidence_map[norm]

    def create(self, task_id, description, project_root):
        project = self._safe_path(str(Path(project_root).absolute()), "project_root")
        if not project.is_dir():
            raise WorkflowError("project_root must be an existing directory")
        with self._locked(task_id) as path:
            if path.exists():
                raise WorkflowError("Task already exists")
            state = {"schema_version": 2, "task_id": task_id, "description": _text(description, "description"),
                     "project_root": str(project), "stage": "DESIGN", "revision": 0, "events": [],
                     "reject_counts": {"design": 0, "code": 0}, "actors": {}, "evidence": []}
            return self._save(path, state, "init", "orchestrator")

    def submit_spec(self, task_id, spec, actor):
        actor = _text(actor, "actor")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "DESIGN")
            self._validate_spec(spec, Path(state["project_root"]))
            if actor in {state["actors"].get("design_reviewer"), state["actors"].get("qa_auditor")}:
                raise WorkflowError("Maker and Checker actor must differ")
            self._clear_downstream(state)
            state.pop("design_review", None)
            state.pop("sign_off", None)
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
        if verdict == "PARTIAL_APPROVE":
            raise WorkflowError("Design review requires full APPROVE, REJECT or ESCALATE")
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
            self._clear_downstream(state)
            state.update(manifest=manifest, manifest_sha256=digest, implementation_report=report, stage="AUDIT", evidence=[])
            state["actors"]["builder"] = actor
            return self._save(path, state, "implementation", actor)

    def _checks(self, checks, expected, name):
        if not isinstance(checks, list) or any(
                not isinstance(c, dict) or not isinstance(c.get("id"), str) for c in checks):
            raise WorkflowError(f"{name} require string AC IDs")
        by_id = {c["id"]: c for c in checks}
        if len(by_id) != len(checks) or set(by_id) != set(expected):
            raise WorkflowError(f"{name} must cover every required AC exactly once")
        return by_id

    def _preview_url(self, value):
        if not isinstance(value, str) or not re.fullmatch(
                r"http://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?(?:/[^\s]*)?", value):
            raise WorkflowError("Local preview URL required")
        try:
            port = urlsplit(value).port
        except ValueError as exc:
            raise WorkflowError("Invalid preview port") from exc
        if port == 0:
            raise WorkflowError("Invalid preview port")
        return value

    def _validate_approval(self, state, payload, verdict):
        """Validate the current design, source and submitted QA evidence together."""
        if verdict not in {"APPROVE", "PARTIAL_APPROVE"} or not isinstance(payload, dict):
            raise WorkflowError("Current approved or partial QA audit required")
        self._validate_design(state)
        self._binding(state, payload.get("spec_sha256"), "spec_sha256")
        self._binding(state, payload.get("manifest_sha256"), "manifest_sha256")
        if self._manifest(state)[1] != state["manifest_sha256"]:
            raise WorkflowError("Implementation changed since submission; return to Builder explicitly")
        _text(payload.get("report"), "report")
        evidence_map = {}
        commands = payload.get("commands")
        if not isinstance(commands, list) or not commands:
            raise WorkflowError("Independent QA command evidence required")
        declared = state["spec"].get("verification_commands")
        if declared is not None:
            declared_by_id = {command["id"]: command for command in declared}
            supplied = self._checks(commands, declared_by_id, "QA commands")
        else:
            supplied = None
        project = self._safe_path(state["project_root"], "project_root")
        for command in commands:
            if not isinstance(command, dict):
                raise WorkflowError("Command must be an object")
            cmd_str = _text(command.get("command"), "command")
            cwd = self._safe_path(command.get("cwd"), "QA cwd")
            if not cwd.is_dir() or not cwd.is_relative_to(project):
                raise WorkflowError("QA cwd must be inside project")
            if type(command.get("exit_code")) is not int or command["exit_code"] != 0:
                raise WorkflowError("QA commands must exit zero")
            if supplied is not None:
                contract = declared_by_id[command["id"]]
                ac_ids = command.get("ac_ids")
                if (command.get("command") != contract["command"]
                        or cwd != (project / contract["cwd"]).resolve()
                        or not isinstance(ac_ids, list) or any(not isinstance(i, str) for i in ac_ids)
                        or len(ac_ids) != len(set(ac_ids)) or set(ac_ids) != set(contract["ac_ids"])):
                    raise WorkflowError("QA command does not match signed verification command contract")
            self._add_evidence(evidence_map, command.get("log"),
                               purpose=f"qa_command: {cmd_str}", state=state)
        preview = payload.get("preview")
        if not isinstance(preview, dict):
            raise WorkflowError("Preview checks required")
        criteria = state["spec"]["acceptance_criteria"]
        checks = self._checks(preview.get("checks"), [ac["id"] for ac in criteria], "Preview checks")
        pending = set()
        applicable_ui = False
        for ac in criteria:
            check = checks[ac["id"]]
            status = check.get("status")
            if not ac.get("applicable", True):
                if status != "N/A" or _text(check.get("reason"), "N/A reason") != ac["na_reason"].strip():
                    raise WorkflowError("Only explicitly inapplicable ACs may use signed N/A reason")
                continue
            applicable_ui |= ac["ui"]
            if status == "PASS":
                self._add_evidence(evidence_map, check.get("evidence"),
                                   purpose=f"ac_check: {ac['id']}", state=state)
            elif status == "NOT_VERIFIED" and ac["ui"]:
                _text(check.get("reason"), "NOT_VERIFIED reason")
                pending.add(ac["id"])
            else:
                raise WorkflowError("Every applicable non-UI AC requires PASS evidence; UI requires PASS or NOT_VERIFIED")
        if verdict == "PARTIAL_APPROVE" and not pending:
            raise WorkflowError("PARTIAL_APPROVE requires at least one applicable UI AC NOT_VERIFIED")
        if verdict == "APPROVE" and pending:
            raise WorkflowError("Full APPROVE requires PASS evidence for all UI ACs")
        if applicable_ui:
            self._preview_url(preview.get("url"))
        component_status = {}
        functional_verified = bool(commands) and all(
            checks[ac["id"]].get("status") == "PASS"
            for ac in criteria if not ac["ui"] and ac.get("applicable", True))
        for key in ("functional", "http_smoke", "browser"):
            component = payload.get(key)
            if component is None:
                component_status[key] = "PASS" if key == "functional" and functional_verified else "NOT_VERIFIED"
                continue
            if (not isinstance(component, dict) or not isinstance(component.get("status"), str)
                    or component["status"] not in {"PASS", "NOT_VERIFIED"}):
                raise WorkflowError(f"Invalid {key} evidence status")
            if component["status"] == "PASS":
                self._add_evidence(evidence_map, component.get("evidence") or component.get("log"),
                                   purpose=key, state=state)
            else:
                _text(component.get("reason"), f"{key} NOT_VERIFIED reason")
                if key == "functional":
                    raise WorkflowError("Approval requires verified functional QA")
            component_status[key] = component["status"]
        return evidence_map, pending, component_status

    def _current_audit(self, state, verdict):
        audit = state.get("audit")
        if not isinstance(audit, dict) or audit.get("verdict") != verdict:
            raise WorkflowError("Current QA audit required")
        qa = _text(state["actors"].get("qa_auditor"), "QA actor")
        if qa in {state["actors"].get("architect"), state["actors"].get("builder")}:
            raise WorkflowError("Maker and Checker actor must differ")
        if state.get("qa_actor_id") != qa or audit.get("actor") != qa:
            raise WorkflowError("Corrupt QA actor binding")
        for record in state["evidence"]:
            if self._evidence(record["path"], state=state)["sha256"] != record["sha256"]:
                raise WorkflowError("Approved evidence changed")
        evidence_map, pending, statuses = self._validate_approval(state, audit, verdict)
        frozen = {os.path.normcase(os.path.abspath(item["path"])): item["sha256"] for item in state["evidence"]}
        if any(frozen.get(key) != record["sha256"] for key, record in evidence_map.items()):
            raise WorkflowError("Audit evidence has no current frozen binding")
        if state.get("overall_verdict") != verdict or state.get("functional_status") != statuses["functional"]:
            raise WorkflowError("Corrupt aggregate QA verdict/status")
        expected_browser = "NOT_VERIFIED" if pending else (
            "PASS" if any(ac["ui"] and ac.get("applicable", True)
                          for ac in state["spec"]["acceptance_criteria"]) else "NOT_VERIFIED")
        if state.get("browser_status") != expected_browser or state.get("http_status") != statuses["http_smoke"]:
            raise WorkflowError("Corrupt aggregate browser/HTTP status")
        return evidence_map, pending

    def audit(self, task_id, verdict, actor, payload):
        self._verdict(verdict)
        actor = _text(actor, "actor")
        if not isinstance(payload, dict):
            raise WorkflowError("audit payload must be object")
        _text(payload.get("report"), "report")
        with self._locked(task_id) as path:
            state = self._load(path)
            if state["stage"] not in {"AUDIT", "AUDIT_PENDING_BROWSER"}:
                raise WorkflowError(f"Expected AUDIT or AUDIT_PENDING_BROWSER, got {state['stage']}")
            self._binding(state, payload.get("spec_sha256"), "spec_sha256")
            self._binding(state, payload.get("manifest_sha256"), "manifest_sha256")
            if actor in {state["actors"].get("builder"), state["actors"].get("architect")}:
                raise WorkflowError("Maker and Checker actor must differ")
            evidence_map, pending, statuses = {}, set(), {}
            if verdict in {"APPROVE", "PARTIAL_APPROVE"}:
                evidence_map, pending, statuses = self._validate_approval(state, payload, verdict)
            state.pop("browser_verification", None)
            state.pop("browser_verification_request", None)
            state["actors"].pop("browser_verifier", None)
            state["actors"]["qa_auditor"] = actor
            state["qa_actor_id"] = actor
            state["audit"] = json.loads(json.dumps(payload))
            state["audit"].update(verdict=verdict, actor=actor)
            state["evidence"] = list(evidence_map.values())
            state["overall_verdict"] = verdict
            state["functional_status"] = statuses.get("functional", "NOT_VERIFIED")
            state["http_status"] = statuses.get("http_smoke", "NOT_VERIFIED")
            state["browser_status"] = "PASS" if verdict == "APPROVE" and any(
                ac["ui"] and ac.get("applicable", True) for ac in state["spec"]["acceptance_criteria"]) else "NOT_VERIFIED"
            approved_stage = "AUDIT_PENDING_BROWSER" if verdict == "PARTIAL_APPROVE" else "APPROVED"
            self._decision(state, "code", verdict, approved_stage, "IMPLEMENTATION")
            return self._save(path, state, "audit", actor)

    def verify_browser(self, task_id, actor, payload):
        """Promote a current partial audit using evidence for exactly its pending UI ACs."""
        actor = _text(actor, "actor")
        if not isinstance(payload, dict):
            raise WorkflowError("verify_browser payload must be object")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "AUDIT_PENDING_BROWSER")
            self._binding(state, payload.get("spec_sha256"), "spec_sha256")
            self._binding(state, payload.get("manifest_sha256"), "manifest_sha256")
            if actor in {state["actors"].get("builder"), state["actors"].get("architect")}:
                raise WorkflowError("Maker and Checker actor must differ")
            _, pending = self._current_audit(state, "PARTIAL_APPROVE")
            preview = payload.get("preview")
            url = payload.get("url") if "url" in payload else (
                preview.get("url") if isinstance(preview, dict) else None)
            if self._preview_url(url) != state["audit"]["preview"]["url"]:
                raise WorkflowError("Browser verification must use the same local preview URL")
            checks = payload.get("checks") if "checks" in payload else (
                preview.get("checks") if isinstance(preview, dict) else None)
            checks_by_id = self._checks(checks, pending, "Browser checks")
            for ac_id, check in checks_by_id.items():
                if check.get("status") != "PASS":
                    raise WorkflowError(f"Browser check for UI AC {ac_id} must have status PASS")
                ev_file = check.get("evidence") or check.get("screenshot") or check.get("log")
                self._evidence(ev_file, state=state)
                checks_by_id[ac_id] = dict(check, evidence=ev_file)
            updated = json.loads(json.dumps(state["audit"]))
            for check in updated["preview"]["checks"]:
                if check["id"] in checks_by_id:
                    check.update(checks_by_id[check["id"]])
                    check.pop("reason", None)
            # A browser result supplies only the UI evidence; independent functional QA is retained.
            updated.pop("browser", None)
            evidence_map, _, statuses = self._validate_approval(state, updated, "APPROVE")
            for item in state["evidence"]:
                norm = os.path.normcase(os.path.abspath(item["path"]))
                if norm not in evidence_map:
                    evidence_map[norm] = dict(item)
            for key in ("screenshots", "logs"):
                if key in payload:
                    if not isinstance(payload[key], list):
                        raise WorkflowError(f"Browser {key} must be a list")
                    for value in payload[key]:
                        self._add_evidence(evidence_map, value, purpose=f"browser_{key}", state=state)
            updated["verdict"] = "APPROVE"
            state["audit"] = updated
            state["actors"]["browser_verifier"] = actor
            state.update(overall_verdict="APPROVE", browser_status="PASS", stage="APPROVED",
                         functional_status=statuses["functional"], http_status=statuses["http_smoke"],
                         evidence=list(evidence_map.values()), browser_verification=json.loads(json.dumps(payload)))
            if "browser_verification_request" in state:
                state["browser_verification_request"]["status"] = "COMPLETED"
            return self._save(path, state, "verify_browser", actor)

    def request_browser_verification(self, task_id, actor, report):
        """Record a request only after current independent partial QA exists."""
        actor = _text(actor, "actor")
        report = _text(report, "report")
        with self._locked(task_id) as path:
            state = self._load(path)
            self._stage(state, "AUDIT_PENDING_BROWSER")
            if actor in {state["actors"].get("builder"), state["actors"].get("architect")}:
                raise WorkflowError("Maker and Checker actor must differ")
            self._current_audit(state, "PARTIAL_APPROVE")
            state["browser_verification_request"] = {
                "report": report, "actor": actor, "status": "PENDING",
                "spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"]}
            return self._save(path, state, "audit_pending_browser", actor)

    def revise(self, task_id, reason):
        """Invalidate design approval after an explicit architecture change request."""
        reason = _text(reason, "reason")
        with self._locked(task_id) as path:
            state = self._load(path)
            if state["stage"] == "ESCALATED":
                raise WorkflowError("Escalated task requires a new task and human direction")
            self._clear_downstream(state)
            for key in ["spec", "spec_sha256", "design_review", "sign_off"]:
                state.pop(key, None)
            state.update(stage="DESIGN", evidence=[], revision_reason=reason)
            return self._save(path, state, "revise", "orchestrator")

    def migrate_legacy(self, task_id, reason):
        """Invalidate v1 audit authority without discarding the task's provenance or counters."""
        reason = _text(reason, "reason")
        with self._locked(task_id) as path:
            state = self._load(path, allow_legacy_revalidation=True)
            if state["schema_version"] != 1 or state["stage"] not in {"AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"}:
                raise WorkflowError("Only legacy audited checkpoints may request explicit revalidation")
            authority_keys = self.DOWNSTREAM | {"spec", "spec_sha256", "design_review", "sign_off"}
            actors = dict(state["actors"])
            state["legacy_revalidation"] = {"previous_stage": state["stage"], "reason": reason,
                "actors": actors, "authority": {key: state[key] for key in authority_keys if key in state}}
            self._clear_downstream(state)
            state["actors"] = actors
            for key in ("spec", "spec_sha256", "design_review", "sign_off"):
                state.pop(key, None)
            state.update(schema_version=2, stage="DESIGN", revision_reason=reason)
            return self._save(path, state, "migrate-legacy", "orchestrator")

    def status(self, task_id):
        with self._locked(task_id) as path:
            state = self._load(path)
            if state["stage"] in {"APPROVED", "AUDIT_PENDING_BROWSER"}:
                self._current_audit(state, "APPROVE" if state["stage"] == "APPROVED" else "PARTIAL_APPROVE")
            return state
