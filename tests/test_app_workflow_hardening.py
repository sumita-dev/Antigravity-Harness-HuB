"""Regression checks for current approval and exact snapshot boundaries."""
import copy
import json
import os
from pathlib import Path
import subprocess

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError


def prepared(tmp_path, *, criteria=None, **extra):
    project = tmp_path / "project"
    project.mkdir()
    (project / "index.html").write_text("app")
    store = AppWorkflowStore(tmp_path / "brain")
    store.create("task", "build", project)
    spec = {"scope": "app", "design": "local", "contracts": "api", "risks": "none",
            "evidence_root": str(tmp_path / "evidence"),
            "acceptance_criteria": criteria or [
                {"id": "UI", "description": "render", "ui": True},
                {"id": "API", "description": "serve", "ui": False}], **extra}
    (tmp_path / "evidence").mkdir()
    state = store.submit_spec("task", spec, "architect")
    store.review_design("task", "APPROVE", "reviewer", state["spec_sha256"], "checked")
    store.sign_off("task", state["spec_sha256"], "SIGN_OFF: approved")
    state = store.submit_implementation("task", "builder", "built")
    return store, project, state


def payload(tmp_path, state, *, partial=False):
    log = tmp_path / "evidence" / "qa.log"
    log.write_text("test pass")
    return {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"],
            "report": "independent checks", "commands": [{"command": "pytest", "cwd": state["project_root"],
            "exit_code": 0, "log": str(log)}], "preview": {"url": "http://localhost:3000",
            "checks": [{"id": "UI", "status": "NOT_VERIFIED", "reason": "browser absent"} if partial
                       else {"id": "UI", "status": "PASS", "evidence": str(log)},
                       {"id": "API", "status": "PASS", "evidence": str(log)}]}}


def browser(tmp_path, state):
    image = tmp_path / "evidence" / "screen.png"
    image.write_bytes(b"png")
    return {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"],
            "url": "http://localhost:3000", "checks": [{"id": "UI", "status": "PASS", "evidence": str(image)}]}


def overwrite(store, state):
    (store.root / "task.json").write_text(json.dumps(state), encoding="utf-8")


@pytest.mark.parametrize("action", ["verify", "request"])
def test_no_browser_bypass_before_partial_qa(tmp_path, action):
    store, _, state = prepared(tmp_path)
    with pytest.raises(WorkflowError):
        if action == "verify":
            store.verify_browser("task", "qa", browser(tmp_path, state))
        else:
            store.request_browser_verification("task", "qa", "please check")
    assert store.status("task")["stage"] == "AUDIT"


@pytest.mark.parametrize("change", ["all_pass", "non_ui_na", "non_ui_pending"])
def test_partial_requires_pending_ui_and_passing_applicable_non_ui(tmp_path, change):
    store, _, state = prepared(tmp_path)
    data = payload(tmp_path, state, partial=change != "all_pass")
    if change != "all_pass":
        data["preview"]["checks"][1] = {"id": "API", "status": "N/A" if change == "non_ui_na" else "NOT_VERIFIED", "reason": "skip"}
    with pytest.raises(WorkflowError):
        store.audit("task", "PARTIAL_APPROVE", "qa", data)


@pytest.mark.parametrize("change", ["duplicate", "unknown", "url", "missing_url", "old_log", "signoff", "review"])
def test_browser_requires_exact_pending_coverage_and_current_qa(tmp_path, change):
    store, _, state = prepared(tmp_path)
    state = store.audit("task", "PARTIAL_APPROVE", "qa", payload(tmp_path, state, partial=True))
    data = browser(tmp_path, state)
    if change == "duplicate":
        data["checks"].append(dict(data["checks"][0]))
    elif change == "unknown":
        data["checks"].append(dict(data["checks"][0], id="OTHER"))
    elif change == "url":
        data["url"] = "http://localhost:3001"
    elif change == "missing_url":
        data.pop("url")
    elif change == "old_log":
        (tmp_path / "evidence" / "qa.log").write_text("tampered")
    else:
        state["sign_off" if change == "signoff" else "design_review"]["spec_sha256"] = "0" * 64
        overwrite(store, state)
    with pytest.raises(WorkflowError):
        store.verify_browser("task", "browser-qa", data)


def test_browser_retains_functional_qa_identity_and_absent_http_is_unverified(tmp_path):
    store, _, state = prepared(tmp_path)
    state = store.audit("task", "PARTIAL_APPROVE", "qa", payload(tmp_path, state, partial=True))
    assert state["http_status"] == "NOT_VERIFIED"
    state = store.verify_browser("task", "browser-qa", browser(tmp_path, state))
    assert state["actors"]["qa_auditor"] == "qa"
    assert state["qa_actor_id"] == "qa"
    assert state["actors"]["browser_verifier"] == "browser-qa"
    assert store.status("task")["stage"] == "APPROVED"


def test_design_partial_is_rejected(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    store = AppWorkflowStore(tmp_path / "brain")
    store.create("task", "build", project)
    spec = {"scope": "app", "design": "api", "contracts": "api", "risks": "none",
            "acceptance_criteria": [{"id": "API", "description": "api", "ui": False}]}
    state = store.submit_spec("task", spec, "architect")
    with pytest.raises(WorkflowError):
        store.review_design("task", "PARTIAL_APPROVE", "reviewer", state["spec_sha256"], "partial")


@pytest.mark.parametrize("name", ["legacy.htm", "saved_files/app.js", "ORCHESTRATION_source.py", "ANTIGRAVITY_source.py",
                                  "lib/build/app.py", "lib/dist/app.js", "server.log", "untracked.json"])
def test_snapshot_includes_source_name_collisions(tmp_path, name):
    store, project, state = prepared(tmp_path)
    target = project / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("source")
    with pytest.raises(WorkflowError, match="changed"):
        store.audit("task", "APPROVE", "qa", payload(tmp_path, state))


def test_only_signed_root_build_exclusion_applies(tmp_path):
    store, project, state = prepared(tmp_path, snapshot_exclusions=["dist"])
    (project / "dist").mkdir()
    (project / "dist" / "bundle.js").write_text("generated")
    state = store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
    (project / "lib" / "dist").mkdir(parents=True)
    (project / "lib" / "dist" / "source.js").write_text("source")
    with pytest.raises(WorkflowError, match="changed"):
        store.status("task")


@pytest.mark.parametrize("extra", [{"snapshot_exclusions": "dist"}, {"snapshot_exclusions": ["../outside"]},
                                  {"snapshot_exclusions": ["**/*.js"]}, {"evidence_root": "relative"},
                                  {"verification_commands": "pytest"}])
def test_signed_optional_spec_fields_have_strict_types_and_paths(tmp_path, extra):
    with pytest.raises(WorkflowError):
        prepared(tmp_path, **extra)


def test_evidence_outside_authorized_roots_rejected(tmp_path):
    store, _, state = prepared(tmp_path)
    data = payload(tmp_path, state)
    outside = tmp_path / "outside.log"
    outside.write_text("untrusted")
    data["commands"][0]["log"] = str(outside)
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", data)


@pytest.mark.parametrize("stage", ["AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"])
def test_legacy_implementation_checkpoints_fail_closed(tmp_path, stage):
    store, _, state = prepared(tmp_path)
    state.update(schema_version=1, stage=stage, next_agent=store.NEXT_AGENT[stage])
    overwrite(store, state)
    with pytest.raises(WorkflowError, match="legacy|Legacy"):
        store.status("task")


def test_pristine_v1_implementation_migrates_without_repeating_signoff(tmp_path):
    store, _, state = prepared(tmp_path)
    state["stage"] = "IMPLEMENTATION"
    state["next_agent"] = "builder"
    for key in ("manifest", "manifest_sha256", "implementation_report"):
        state.pop(key)
    state["schema_version"] = 1
    state["events"] = state["events"][:-1]
    state["reject_counts"] = {"design": 1, "code": 1}
    original = copy.deepcopy(state)
    overwrite(store, state)
    migrated = store.status("task")
    assert migrated["schema_version"] == 2
    assert migrated["sign_off"] == original["sign_off"]
    assert migrated["actors"] == original["actors"]
    assert migrated["reject_counts"] == original["reject_counts"]
    assert migrated["events"][:-1] == original["events"]
    assert migrated["events"][-1]["action"] == "migrate-schema"
    assert store.submit_implementation("task", "builder", "built")["stage"] == "AUDIT"


@pytest.mark.parametrize("action", ["revise", "resubmit"])
def test_replacement_clears_every_downstream_aggregate(tmp_path, action):
    store, _, state = prepared(tmp_path)
    state = store.audit("task", "PARTIAL_APPROVE", "qa", payload(tmp_path, state, partial=True))
    state = store.request_browser_verification("task", "qa", "browser needed")
    if action == "resubmit":
        state = store.audit("task", "REJECT", "qa", {"spec_sha256": state["spec_sha256"],
                           "manifest_sha256": state["manifest_sha256"], "report": "bug"})
        state = store.submit_implementation("task", "builder", "fixed")
    else:
        state = store.revise("task", "new design")
    for key in ("audit", "overall_verdict", "browser_status", "functional_status", "http_status",
                "browser_verification", "browser_verification_request", "qa_actor_id"):
        assert key not in state
    assert state["reject_counts"]["code"] == (1 if action == "resubmit" else 0)


def test_signed_command_contract_is_exact(tmp_path):
    store, _, state = prepared(tmp_path, verification_commands=[
        {"id": "TEST", "command": "pytest", "cwd": ".", "ac_ids": ["API"]}])
    data = payload(tmp_path, state)
    data["commands"][0].update(id="TEST", ac_ids=["API"])
    data["commands"][0]["command"] = "echo pass"
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", data)
    data["commands"][0]["command"] = "pytest"
    assert store.audit("task", "APPROVE", "qa", data)["stage"] == "APPROVED"


def test_functional_status_derives_from_verified_commands_and_non_ui_ac(tmp_path):
    store, _, state = prepared(tmp_path)
    state = store.audit("task", "PARTIAL_APPROVE", "qa", payload(tmp_path, state, partial=True))
    assert state["functional_status"] == "PASS"
    assert state["http_status"] == "NOT_VERIFIED"


@pytest.mark.parametrize("status", ["FAIL", "NOT_VERIFIED"])
def test_explicit_unverified_functional_component_cannot_be_overridden(tmp_path, status):
    store, _, state = prepared(tmp_path)
    data = payload(tmp_path, state, partial=True)
    data["functional"] = {"status": status, "reason": "not independently verified"}
    with pytest.raises(WorkflowError):
        store.audit("task", "PARTIAL_APPROVE", "qa", data)


@pytest.mark.parametrize("target", ["root", "source", "evidence", "evidence_parent"])
def test_symlink_paths_cannot_supply_source_or_evidence(tmp_path, target):
    store, project, state = prepared(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file").write_text("external")
    try:
        if target == "root":
            alias = tmp_path / "alias"
            alias.symlink_to(project, target_is_directory=True)
        elif target == "source":
            (project / "source.py").symlink_to(outside / "file")
        elif target == "evidence":
            (tmp_path / "evidence" / "external.log").symlink_to(outside / "file")
        else:
            (tmp_path / "evidence" / "alias").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(WorkflowError, match="Symlink"):
        if target == "root":
            store.create("other", "build", alias)
        elif target == "source":
            store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
        else:
            data = payload(tmp_path, state)
            data["commands"][0]["log"] = str(tmp_path / "evidence" / ("external.log" if target == "evidence" else "alias/file"))
            store.audit("task", "APPROVE", "qa", data)


def test_evidence_traversal_is_rejected_even_inside_signed_root(tmp_path):
    store, _, state = prepared(tmp_path)
    data = payload(tmp_path, state)
    data["commands"][0]["log"] = str(tmp_path / "evidence" / ".." / "evidence" / "qa.log")
    with pytest.raises(WorkflowError, match="traversal"):
        store.audit("task", "APPROVE", "qa", data)


@pytest.mark.parametrize("field", ["command", "actor", "verdict", "sign_off"])
def test_approved_status_revalidates_qa_and_signoff_records(tmp_path, field):
    store, _, state = prepared(tmp_path)
    state = store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
    if field == "command":
        state["audit"]["commands"][0]["exit_code"] = 1
    elif field == "actor":
        state["actors"]["qa_auditor"] = "builder"
    elif field == "verdict":
        state["audit"]["verdict"] = "REJECT"
    else:
        state["sign_off"]["human_message"] = "not approved"
    overwrite(store, state)
    with pytest.raises(WorkflowError):
        store.status("task")


def test_signed_inapplicability_is_required_and_browser_covers_only_pending_ids(tmp_path):
    criteria = [{"id": "UI", "description": "render", "ui": True},
                {"id": "API", "description": "api", "ui": False},
                {"id": "OPTION", "description": "optional", "ui": True, "applicable": False, "na_reason": "outside scope"},
                {"id": "DONE", "description": "done", "ui": True}]
    store, _, state = prepared(tmp_path, criteria=criteria)
    data = payload(tmp_path, state, partial=True)
    data["preview"]["checks"].extend([
        {"id": "OPTION", "status": "N/A", "reason": "outside scope"},
        {"id": "DONE", "status": "PASS", "evidence": data["commands"][0]["log"]}])
    state = store.audit("task", "PARTIAL_APPROVE", "qa", data)
    state = store.verify_browser("task", "browser-qa", browser(tmp_path, state))
    assert state["audit"]["preview"]["checks"][2]["status"] == "N/A"
    assert store.status("task")["stage"] == "APPROVED"


@pytest.mark.parametrize("legacy_stage", ["DESIGN", "DESIGN_REVIEW", "SIGN_OFF", "IMPLEMENTATION"])
def test_pristine_legacy_migration_validates_current_actor_provenance(tmp_path, legacy_stage):
    store, _, state = prepared(tmp_path)
    state.update(stage=legacy_stage, schema_version=1, next_agent=store.NEXT_AGENT[legacy_stage])
    for key in ("manifest", "manifest_sha256", "implementation_report"):
        state.pop(key)
    state["events"] = state["events"][:1 if legacy_stage == "DESIGN" else 2 if legacy_stage == "DESIGN_REVIEW" else 3 if legacy_stage == "SIGN_OFF" else 4]
    state["actors"]["design_reviewer"] = "architect"
    if legacy_stage in {"DESIGN", "DESIGN_REVIEW"}:
        state.pop("sign_off")
        state.pop("design_review")
    overwrite(store, state)
    with pytest.raises(WorkflowError):
        store.status("task")


def test_signed_evidence_root_cannot_be_a_file(tmp_path):
    root = tmp_path / "file"
    root.write_text("not directory")
    with pytest.raises(WorkflowError):
        prepared(tmp_path, evidence_root=str(root))


def test_default_runtime_exclusions_are_root_relative(tmp_path):
    store, project, state = prepared(tmp_path)
    for name in (".brain", "node_modules", ".gitnexus", ".cache"):
        (project / name).mkdir()
        (project / name / "runtime").write_text("data")
    state = store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
    nested = project / "lib" / "node_modules"
    nested.mkdir(parents=True)
    (nested / "source.js").write_text("source")
    with pytest.raises(WorkflowError, match="changed"):
        store.status("task")


@pytest.mark.parametrize("stage", ["AUDIT", "AUDIT_PENDING_BROWSER", "APPROVED"])
def test_legacy_audited_revalidation_preserves_task_history_and_reject_counts(tmp_path, stage):
    store, _, state = prepared(tmp_path)
    state.update(schema_version=1, stage=stage, next_agent=store.NEXT_AGENT[stage])
    state["reject_counts"] = {"design": 1, "code": 1}
    original = copy.deepcopy(state)
    overwrite(store, state)
    assert callable(getattr(store, "migrate_legacy", None))
    migrated = store.migrate_legacy("task", "revalidate legacy audit")
    assert migrated["schema_version"] == 2
    assert migrated["task_id"] == original["task_id"]
    assert migrated["stage"] == "DESIGN"
    assert migrated["actors"] == original["actors"]
    assert migrated["events"][:-1] == original["events"]
    assert migrated["reject_counts"] == original["reject_counts"]
    assert "sign_off" not in migrated and "manifest_sha256" not in migrated
    assert migrated["legacy_revalidation"]["previous_stage"] == stage
    assert migrated["legacy_revalidation"]["authority"]["sign_off"] == original["sign_off"]
    assert store.status("task")["stage"] == "DESIGN"


def test_legacy_revalidation_cannot_reopen_escalated(tmp_path):
    store, _, state = prepared(tmp_path)
    state.update(schema_version=1, stage="ESCALATED", next_agent=None, reject_counts={"design": 0, "code": 2})
    overwrite(store, state)
    assert callable(getattr(store, "migrate_legacy", None))
    with pytest.raises(WorkflowError):
        store.migrate_legacy("task", "restart")


@pytest.mark.parametrize("change", [{"schema_version": []}, {"schema_version": True}, {"stage": []},
                                   {"actors": {"architect": []}}])
def test_corrupt_checkpoint_field_types_raise_workflow_error(tmp_path, change):
    store, _, state = prepared(tmp_path)
    overwrite(store, dict(state, **change))
    with pytest.raises(WorkflowError):
        store.status("task")


def test_invalid_component_status_raises_workflow_error(tmp_path):
    store, _, state = prepared(tmp_path)
    data = payload(tmp_path, state)
    data["http_smoke"] = {"status": []}
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", data)


def test_legacy_revalidation_retains_browser_actor_provenance(tmp_path):
    store, _, state = prepared(tmp_path)
    state.update(schema_version=1, stage="APPROVED", next_agent=None)
    state["actors"]["browser_verifier"] = "browser-qa"
    actors = dict(state["actors"])
    overwrite(store, state)
    migrated = store.migrate_legacy("task", "revalidate")
    assert migrated["actors"] == actors


@pytest.mark.skipif(os.name != "nt", reason="NTFS junction regression")
@pytest.mark.parametrize("kind", ["root", "source", "evidence_parent", "evidence_root"])
def test_ntfs_junctions_cannot_escape_source_or_evidence(tmp_path, kind):
    target = tmp_path / "external"
    target.mkdir()
    (target / "source.py").write_text("external source")
    if kind == "evidence_root":
        link = tmp_path / "junction"
    else:
        store, project, state = prepared(tmp_path)
        link = (project / "junction" if kind == "source" else
                tmp_path / "evidence" / "junction" if kind == "evidence_parent" else tmp_path / "junction")
    created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    if created.returncode:
        pytest.skip("NTFS junction creation unavailable")
    with pytest.raises(WorkflowError, match="Symlink|Junction"):
        if kind == "evidence_root":
            prepared(tmp_path, evidence_root=str(link))
        elif kind == "root":
            store.create("linked", "build", link)
        elif kind == "source":
            store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
        else:
            data = payload(tmp_path, state)
            data["commands"][0]["log"] = str(link / "source.py")
            store.audit("task", "APPROVE", "qa", data)


@pytest.mark.parametrize("phase", ["design", "code"])
@pytest.mark.parametrize("action", ["status", "approve", "pristine_migration", "legacy_revalidation"])
def test_exhausted_reject_counts_cannot_continue_or_migrate(tmp_path, phase, action):
    store, _, state = prepared(tmp_path)
    state["reject_counts"][phase] = 2
    if action == "pristine_migration":
        state.update(schema_version=1, stage="IMPLEMENTATION", next_agent="builder")
        for key in ("manifest", "manifest_sha256", "implementation_report"):
            state.pop(key)
        state["events"] = state["events"][:-1]
    elif action == "legacy_revalidation":
        state.update(schema_version=1)
    overwrite(store, state)
    with pytest.raises(WorkflowError, match="ESCALATED|exhausted"):
        if action in {"status", "pristine_migration"}:
            store.status("task")
        elif action == "approve":
            store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
        else:
            store.migrate_legacy("task", "revalidate")
    persisted = json.loads((store.root / "task.json").read_text(encoding="utf-8"))
    assert persisted == state


@pytest.mark.parametrize("phase", ["design", "code"])
def test_exhausted_counters_with_escalated_stage_remain_readable(tmp_path, phase):
    store, _, state = prepared(tmp_path)
    state.update(stage="ESCALATED", next_agent=None)
    state["reject_counts"][phase] = 2
    overwrite(store, state)
    assert store.status("task")["reject_counts"][phase] == 2
    with pytest.raises(WorkflowError):
        store.revise("task", "restart")


@pytest.mark.parametrize("route", ["builder", None, [], "missing"])
def test_route_must_match_persisted_stage(tmp_path, route):
    store, _, state = prepared(tmp_path)
    if route == "missing":
        state.pop("next_agent")
    else:
        state["next_agent"] = route
    overwrite(store, state)
    with pytest.raises(WorkflowError, match="route|next_agent"):
        store.status("task")


def test_approved_route_requires_explicit_none(tmp_path):
    store, _, state = prepared(tmp_path)
    state = store.audit("task", "APPROVE", "qa", payload(tmp_path, state))
    assert state["next_agent"] is None
    state.pop("next_agent")
    overwrite(store, state)
    with pytest.raises(WorkflowError, match="route|next_agent"):
        store.status("task")
