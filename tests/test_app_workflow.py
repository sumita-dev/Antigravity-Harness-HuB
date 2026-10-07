import json
from pathlib import Path

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError


def spec():
    return {"scope": "task board", "design": "local UI", "contracts": "local storage",
            "acceptance_criteria": [{"id": "AC1", "description": "create task", "ui": True}],
            "risks": "storage corruption"}


def setup_task(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "index.html").write_text("app", encoding="utf-8")
    store = AppWorkflowStore(tmp_path / "brain")
    store.create("task", "build task board", project)
    return store, project


def approved_design(store):
    s = store.submit_spec("task", spec(), "architect-1")
    store.review_design("task", "APPROVE", "reviewer-1", s["spec_sha256"], "structure/function/logic checked")
    return store.sign_off("task", s["spec_sha256"], "Sếp: Duyệt bản đặc tả này")


def audit_payload(state, tmp_path):
    log = tmp_path / "qa.log"
    log.write_text("tests pass", encoding="utf-8")
    return {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"],
            "commands": [{"command": "npm test", "cwd": state["project_root"], "exit_code": 0, "log": str(log)}],
            "preview": {"url": "http://localhost:3000", "checks": [{"id": "AC1", "status": "PASS", "evidence": str(log)}]},
            "report": "QA independently checked code and UI"}


def test_app_workflow_closed_loop_and_resume(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder-1", "implemented and tested")
    state = AppWorkflowStore(tmp_path / "brain").audit("task", "APPROVE", "qa-1", audit_payload(state, tmp_path))
    assert state["stage"] == "APPROVED"
    assert state["next_agent"] is None
    assert len(state["events"]) == 6


def test_gates_actor_independence_and_spec_binding(tmp_path):
    store, _ = setup_task(tmp_path)
    with pytest.raises(WorkflowError):
        store.submit_implementation("task", "builder", "done")
    state = store.submit_spec("task", spec(), "same")
    with pytest.raises(WorkflowError):
        store.review_design("task", "APPROVE", "same", state["spec_sha256"], "ok")
    with pytest.raises(WorkflowError):
        store.review_design("task", "APPROVE", "checker", "wrong", "ok")
    assert store.status("task")["stage"] == "DESIGN_REVIEW"


@pytest.mark.parametrize("phase", ["design", "code"])
def test_two_rejects_escalate_and_counter_survives_restart(tmp_path, phase):
    store, _ = setup_task(tmp_path)
    if phase == "code":
        approved_design(store)
    for i in range(2):
        store = AppWorkflowStore(tmp_path / "brain")
        if phase == "design":
            state = store.submit_spec("task", spec(), "architect")
            state = store.review_design("task", "REJECT", "reviewer", state["spec_sha256"], "missing logic")
        else:
            state = store.submit_implementation("task", "builder", "done")
            state = store.audit("task", "REJECT", "qa", {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"], "report": "bug"})
    assert state["stage"] == "ESCALATED"
    assert state["reject_counts"][phase] == 2


def test_code_change_untracked_and_stale_evidence_block_approval(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    (project / "untracked.js").write_text("new code")
    with pytest.raises(WorkflowError, match="changed"):
        store.audit("task", "APPROVE", "qa", audit_payload(state, tmp_path))
    assert store.status("task")["stage"] == "AUDIT"


def test_missing_preview_and_bad_command_block_approval(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    payload = audit_payload(state, tmp_path)
    payload["preview"]["checks"] = []
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", payload)
    payload = audit_payload(state, tmp_path)
    payload["commands"][0]["exit_code"] = 1
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", payload)


def test_task_id_and_duplicate_task_guard(tmp_path):
    store, project = setup_task(tmp_path)
    for task in ["../escape", "", "CON", "a/b"]:
        with pytest.raises(WorkflowError):
            store.create(task, "task", project)
    with pytest.raises(WorkflowError):
        store.create("task", "duplicate", project)


def test_preview_evidence_hash_is_frozen_and_current_on_status(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    payload = audit_payload(state, tmp_path)
    store.audit("task", "APPROVE", "qa", payload)
    Path(payload["commands"][0]["log"]).write_text("tampered")
    with pytest.raises(WorkflowError, match="evidence"):
        store.status("task")


def test_negative_human_message_is_not_approval(tmp_path):
    store, _ = setup_task(tmp_path)
    state = store.submit_spec("task", spec(), "architect")
    store.review_design("task", "APPROVE", "reviewer", state["spec_sha256"], "checked")
    for message in ["không duyệt", "not approved", "chưa duyệt", "Từ chối duyệt Spec này",
                    "Sẽ duyệt sau khi sửa xong", "Cần Sếp approve trước", "Duyệt nếu sửa xong",
                    "Anh cần xem trước khi duyệt", "approve?", "Sếp có duyệt không?"]:
        with pytest.raises(WorkflowError):
            store.sign_off("task", state["spec_sha256"], message)
    assert store.status("task")["stage"] == "SIGN_OFF"


@pytest.mark.parametrize("message", ["Duyệt", "Duyệt bản đặc tả này", "SIGN_OFF: approved", "Bắt đầu code đi", "Sếp: Duyệt Spec này"])
def test_signoff_accepts_only_whole_affirmative_phrase_and_preserves_raw(tmp_path, message):
    store, _ = setup_task(tmp_path)
    state = store.submit_spec("task", spec(), "architect")
    store.review_design("task", "APPROVE", "reviewer", state["spec_sha256"], "checked")
    raw = f"  {message}  "
    state = store.sign_off("task", state["spec_sha256"], raw)
    assert state["stage"] == "IMPLEMENTATION"
    assert state["sign_off"]["human_message"] == raw


def test_revise_invalidates_signoff_without_resetting_counters(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = store.revise("task", "new architecture")
    assert state["stage"] == "DESIGN"
    assert "sign_off" not in state
    with pytest.raises(WorkflowError):
        store.submit_implementation("task", "builder", "done")


def test_corrupt_state_and_lock_fail_without_overwrite(tmp_path):
    store, _ = setup_task(tmp_path)
    path = store.root / "task.json"
    path.write_text("[]")
    with pytest.raises(WorkflowError):
        store.status("task")
    assert path.read_text() == "[]"
    lock = store.root / "task.lock"
    lock.write_text("busy")
    with pytest.raises(WorkflowError, match="locked"):
        store.status("task")
    assert lock.read_text() == "busy"


def test_cli_checkpoints_and_errors(tmp_path, monkeypatch, capsys):
    import run_harness
    monkeypatch.setenv("HARNESS_BRAIN_DIR", str(tmp_path / "brain"))
    project = tmp_path / "app"
    project.mkdir()
    ret = run_harness.main(["--workflow", "init", "--task-id", "cli", "--task", "app", "--project-root", str(project), "--json"])
    assert ret == 0
    assert json.loads(capsys.readouterr().out)["next_agent"] == "architect"
    assert run_harness.main(["--workflow", "status", "--task-id", "../bad", "--json"]) == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_reject_changed_code_returns_to_builder(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    (project / "index.html").write_text("changed")
    state = store.audit("task", "REJECT", "qa", {"spec_sha256": state["spec_sha256"],
                        "manifest_sha256": state["manifest_sha256"], "report": "code changed"})
    assert state["next_agent"] == "builder"
    assert store.submit_implementation("task", "builder", "fixed")["stage"] == "AUDIT"


@pytest.mark.parametrize("change", ["command", "id", "port"])
def test_invalid_nested_qa_payload_returns_workflow_error(tmp_path, change):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    payload = audit_payload(state, tmp_path)
    if change == "command":
        payload["commands"] = [None]
    elif change == "id":
        payload["preview"]["checks"][0]["id"] = []
    else:
        payload["preview"]["url"] = "http://localhost:99999"
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", payload)


def test_symlink_directory_cannot_escape_manifest(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    target = tmp_path / "outside"
    target.mkdir()
    try:
        (project / "linked").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(WorkflowError, match="Symlink"):
        store.submit_implementation("task", "builder", "done")


def test_runtime_logs_excluded_but_untracked_config_included(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    (project / "server.log").write_text("new logs")
    payload = audit_payload(state, tmp_path)
    assert store.audit("task", "APPROVE", "qa", payload)["stage"] == "APPROVED"
    (project / "config.json").write_text("{}")
    with pytest.raises(WorkflowError, match="changed"):
        store.status("task")


def test_partial_approve_with_not_verified_browser_checks(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder", "done")
    log = tmp_path / "qa.log"
    log.write_text("unit tests pass", encoding="utf-8")
    payload = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "commands": [{"command": "npm test", "cwd": state["project_root"], "exit_code": 0, "log": str(log)}],
        "preview": {
            "url": "http://localhost:3000",
            "checks": [{"id": "AC1", "status": "NOT_VERIFIED", "reason": "Runtime has no browser automation tool"}]
        },
        "report": "Core functional tests pass; browser checks NOT_VERIFIED"
    }
    # Full APPROVE should fail when UI AC is NOT_VERIFIED
    with pytest.raises(WorkflowError, match="Full APPROVE requires PASS evidence"):
        store.audit("task", "APPROVE", "qa-1", payload)
    
    # PARTIAL_APPROVE should succeed and record status
    res = store.audit("task", "PARTIAL_APPROVE", "qa-1", payload)
    assert res["stage"] == "APPROVED"
    assert res["overall_verdict"] == "PARTIAL_APPROVE"
    assert res["browser_status"] == "NOT_VERIFIED"

