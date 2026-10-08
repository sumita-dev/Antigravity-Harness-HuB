import json
from pathlib import Path

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError


def spec(**extra):
    return {"scope": "task board", "design": "local UI", "contracts": "local storage",
            "acceptance_criteria": [{"id": "AC1", "description": "create task", "ui": True}],
            "risks": "storage corruption", **extra}


def setup_task(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "index.html").write_text("app", encoding="utf-8")
    store = AppWorkflowStore(tmp_path / "brain")
    store.create("task", "build task board", project)
    return store, project


def approved_design(store, **extra):
    s = store.submit_spec("task", spec(evidence_root=str(store.root.parent.parent), **extra), "architect-1")
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
    approved_design(store, snapshot_exclusions=["server.log"])
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
    assert res["stage"] == "AUDIT_PENDING_BROWSER"
    assert res["next_agent"] == "human_browser_verification"
    assert res["overall_verdict"] == "PARTIAL_APPROVE"
    assert res["browser_status"] == "NOT_VERIFIED"


def test_evidence_auto_deduplication_and_purpose_mapping(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder-1", "done")
    log = tmp_path / "shared.log"
    log.write_text("common log output", encoding="utf-8")
    payload = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "commands": [{"command": "npm test", "cwd": state["project_root"], "exit_code": 0, "log": str(log)}],
        "preview": {"url": "http://localhost:3000", "checks": [{"id": "AC1", "status": "PASS", "evidence": str(log)}]},
        "report": "QA checked"
    }
    state = store.audit("task", "APPROVE", "qa-1", payload)
    assert state["stage"] == "APPROVED"
    # Deduplication: single record despite multiple references
    assert len(state["evidence"]) == 1
    ev = state["evidence"][0]
    assert ev["sha256"] == state["evidence"][0]["sha256"]
    assert "qa_command: npm test" in ev["purpose"]
    assert "ac_check: AC1" in ev["purpose"]
    assert store.status("task")["stage"] == "APPROVED"


def test_verify_browser_happy_path_and_consistency_sweep(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder-1", "done")
    unit_log = tmp_path / "unit.log"
    unit_log.write_text("unit test passed", encoding="utf-8")
    audit_pl = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "commands": [{"command": "pytest", "cwd": state["project_root"], "exit_code": 0, "log": str(unit_log)}],
        "preview": {
            "url": "http://localhost:3000",
            "checks": [{"id": "AC1", "status": "NOT_VERIFIED", "reason": "Requires browser execution"}]
        },
        "report": "Core tests pass; pending browser"
    }
    state = store.audit("task", "PARTIAL_APPROVE", "qa-1", audit_pl)
    assert state["stage"] == "AUDIT_PENDING_BROWSER"
    store.request_browser_verification("task", "qa-1", "Please run browser tests")

    screenshot = tmp_path / "ac1_screenshot.png"
    screenshot.write_bytes(b"PNG_FAKE_IMAGE_DATA")

    verify_pl = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "url": "http://localhost:3000",
        "checks": [{"id": "AC1", "status": "PASS", "evidence": str(screenshot)}],
        "summary": "Browser verification confirmed UI behaves correctly"
    }

    approved_state = store.verify_browser("task", "qa-checker", verify_pl)
    assert approved_state["stage"] == "APPROVED"
    assert approved_state["next_agent"] is None
    assert approved_state["overall_verdict"] == "APPROVE"
    assert approved_state["browser_status"] == "PASS"

    # Consistency auto-sweep checks
    assert approved_state["browser_verification_request"]["status"] == "COMPLETED"
    assert approved_state["audit"]["verdict"] == "APPROVE"
    assert approved_state["http_status"] == "NOT_VERIFIED"
    assert "browser" not in approved_state["audit"]
    assert approved_state["actors"]["qa_auditor"] == "qa-1"
    assert approved_state["audit"]["preview"]["checks"][0]["status"] == "PASS"

    # Evidence has both unit test log and screenshot
    assert len(approved_state["evidence"]) == 2
    paths = {e["path"] for e in approved_state["evidence"]}
    assert str(unit_log.resolve()) in paths
    assert str(screenshot.resolve()) in paths

    # Event recorded
    last_event = approved_state["events"][-1]
    assert last_event["action"] == "verify_browser"
    assert last_event["actor"] == "qa-checker"
    assert last_event["stage"] == "APPROVED"

    assert store.status("task")["stage"] == "APPROVED"


def test_verify_browser_actor_constraints_and_validation(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = store.submit_implementation("task", "builder-1", "done")
    unit_log = tmp_path / "unit.log"
    unit_log.write_text("unit test passed", encoding="utf-8")
    audit_pl = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "commands": [{"command": "pytest", "cwd": state["project_root"], "exit_code": 0, "log": str(unit_log)}],
        "preview": {
            "url": "http://localhost:3000",
            "checks": [{"id": "AC1", "status": "NOT_VERIFIED", "reason": "Requires browser execution"}]
        },
        "report": "Core tests pass"
    }
    state = store.audit("task", "PARTIAL_APPROVE", "qa-1", audit_pl)

    screenshot = tmp_path / "ac1.png"
    screenshot.write_bytes(b"PNG")

    valid_payload = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "url": "http://localhost:3000",
        "checks": [{"id": "AC1", "status": "PASS", "evidence": str(screenshot)}]
    }

    # Maker (builder or architect) cannot verify browser
    with pytest.raises(WorkflowError, match="Maker and Checker actor must differ"):
        store.verify_browser("task", "builder-1", valid_payload)
    with pytest.raises(WorkflowError, match="Maker and Checker actor must differ"):
        store.verify_browser("task", "architect-1", valid_payload)

    # Wrong spec binding
    bad_spec_payload = dict(valid_payload, spec_sha256="wrong" * 8)
    with pytest.raises(WorkflowError, match="spec_sha256"):
        store.verify_browser("task", "qa-2", bad_spec_payload)

    # Missing evidence file
    missing_ev_payload = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "url": "http://localhost:3000",
        "checks": [{"id": "AC1", "status": "PASS", "evidence": str(tmp_path / "nonexistent.png")}]
    }
    with pytest.raises(WorkflowError, match="Missing or empty evidence"):
        store.verify_browser("task", "qa-2", missing_ev_payload)

    # Incomplete checks (UI AC not PASS)
    fail_check_payload = {
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "url": "http://localhost:3000",
        "checks": [{"id": "AC1", "status": "FAIL", "evidence": str(screenshot)}]
    }
    with pytest.raises(WorkflowError, match="must have status PASS"):
        store.verify_browser("task", "qa-2", fail_check_payload)


def test_verify_browser_cli_workflow(tmp_path, monkeypatch, capsys):
    import run_harness
    monkeypatch.setenv("HARNESS_BRAIN_DIR", str(tmp_path / "brain"))
    project = tmp_path / "app"
    project.mkdir()
    (project / "index.html").write_text("hello", encoding="utf-8")

    run_harness.main(["--workflow", "init", "--task-id", "t1", "--task", "app", "--project-root", str(project), "--json"])
    capsys.readouterr()

    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec(evidence_root=str(tmp_path))), encoding="utf-8")
    run_harness.main(["--workflow", "spec", "--task-id", "t1", "--actor", "arch", "--payload", str(spec_file), "--json"])
    st = json.loads(capsys.readouterr().out)

    rev_file = tmp_path / "rev.json"
    rev_file.write_text(json.dumps({"verdict": "APPROVE", "spec_sha256": st["spec_sha256"], "report": "looks good"}), encoding="utf-8")
    run_harness.main(["--workflow", "design-review", "--task-id", "t1", "--actor", "reviewer", "--payload", str(rev_file), "--json"])
    capsys.readouterr()

    sign_file = tmp_path / "sign.json"
    sign_file.write_text(json.dumps({"spec_sha256": st["spec_sha256"], "human_message": "Duyệt"}), encoding="utf-8")
    run_harness.main(["--workflow", "sign-off", "--task-id", "t1", "--payload", str(sign_file), "--json"])
    capsys.readouterr()

    impl_file = tmp_path / "impl.json"
    impl_file.write_text(json.dumps({"report": "built"}), encoding="utf-8")
    run_harness.main(["--workflow", "implementation", "--task-id", "t1", "--actor", "builder", "--payload", str(impl_file), "--json"])
    st = json.loads(capsys.readouterr().out)

    log_file = tmp_path / "test.log"
    log_file.write_text("ok", encoding="utf-8")
    audit_file = tmp_path / "audit.json"
    audit_file.write_text(json.dumps({
        "verdict": "PARTIAL_APPROVE",
        "spec_sha256": st["spec_sha256"],
        "manifest_sha256": st["manifest_sha256"],
        "commands": [{"command": "test", "cwd": str(project), "exit_code": 0, "log": str(log_file)}],
        "preview": {"url": "http://localhost:3000", "checks": [{"id": "AC1", "status": "NOT_VERIFIED", "reason": "No browser"}]},
        "report": "partial"
    }), encoding="utf-8")
    run_harness.main(["--workflow", "audit", "--task-id", "t1", "--actor", "qa", "--payload", str(audit_file), "--json"])
    capsys.readouterr()

    screen_file = tmp_path / "screen.png"
    screen_file.write_bytes(b"IMG")
    vb_file = tmp_path / "vb.json"
    vb_file.write_text(json.dumps({
        "spec_sha256": st["spec_sha256"],
        "manifest_sha256": st["manifest_sha256"],
        "url": "http://localhost:3000",
        "checks": [{"id": "AC1", "status": "PASS", "evidence": str(screen_file)}],
        "summary": "verified in headless chrome"
    }), encoding="utf-8")
    ret = run_harness.main(["--workflow", "verify-browser", "--task-id", "t1", "--actor", "qa-browser", "--payload", str(vb_file), "--json"])
    assert ret == 0
    final_st = json.loads(capsys.readouterr().out)
    assert final_st["stage"] == "APPROVED"
    assert final_st["next_agent"] is None
    assert final_st["browser_status"] == "PASS"
