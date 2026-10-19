import json
import sys
import copy
import struct
import zlib
import zipfile
from pathlib import Path

import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError


URL = "http://localhost:3000"


def command(*ids):
    return {"id": "TEST", "argv": [sys.executable, "-c", "print('verified task behavior')"],
            "cwd": ".", "ac_ids": list(ids),
            "browser": {"url": URL, "assertions": [{"selector": "body", "text": "app"}]}}


@pytest.fixture(autouse=True)
def optional_browser_collector(monkeypatch):
    """Only replace unavailable Playwright boundary; receipt signing stays real."""
    def collect(contract, directory, timeout):
        def png_chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        image = (bytes.fromhex("89504e470d0a1a0a")
                 + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
                 + png_chunk(b"IDAT", zlib.compress(bytes([0, 255, 255, 255, 255])))
                 + png_chunk(b"IEND", b""))
        (directory / "browser.png").write_bytes(image)
        with zipfile.ZipFile(directory / "trace.zip", "w") as archive:
            archive.writestr("trace.json", json.dumps({"assertions": contract["assertions"]}))
        return {"status": "PASS", "url": contract["url"], "assertions": contract["assertions"]}
    monkeypatch.setattr("harness.execution_evidence._browser_run", collect)


def reviewed(store, task_id, actor, report):
    state = store.submit_implementation(task_id, actor, report)
    return store.review_code(task_id, "APPROVE", "critic", state["spec_sha256"], state["manifest_sha256"], "Reviewed current source and tests")


def receipt(store, state, actor="qa", command_id="TEST"):
    executed = store.execute(state["task_id"], actor, command_id)["execution_receipt"]
    directory = store.root.parent / "execution_evidence" / executed["receipt_id"]
    return executed, directory


def verification_payload(store, state, actor="qa", partial=False):
    run, directory = receipt(store, state, actor)
    return {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"],
            "commands": [{"id": "TEST", "receipt_id": run["receipt_id"]}],
            "preview": {"url": URL, "checks": [
                {"id": "AC1", "status": "NOT_VERIFIED", "reason": "Browser pending"} if partial else
                {"id": "AC1", "status": "PASS", "receipt_id": run["receipt_id"], "actor": actor, "evidence": str(directory / "browser.png")}]},
            "report": "independent verification"}


def browser_payload(store, state, actor="browser-qa"):
    run, directory = receipt(store, state, actor)
    return {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"], "url": URL,
            "checks": [{"id": "AC1", "status": "PASS", "receipt_id": run["receipt_id"], "actor": actor, "evidence": str(directory / "browser.png")}]}


def spec(**extra):
    return {"scope": "task board", "design": "local UI", "contracts": "local storage",
            "acceptance_criteria": [{"id": "AC1", "description": "create task", "ui": True}],
            "risks": "storage corruption", "verification_commands": [command("AC1")], **extra}


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
    store = AppWorkflowStore(tmp_path / "brain")
    return verification_payload(store, state)


def test_app_workflow_closed_loop_and_resume(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder-1", "implemented and tested")
    state = AppWorkflowStore(tmp_path / "brain").audit("task", "APPROVE", "qa", audit_payload(state, tmp_path))
    assert state["stage"] == "APPROVED"
    assert state["next_agent"] is None
    assert len(state["events"]) == 8


def test_gates_actor_independence_and_spec_binding(tmp_path):
    store, _ = setup_task(tmp_path)
    with pytest.raises(WorkflowError):
        reviewed(store, "task", "builder", "done")
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
            state = reviewed(store, "task", "builder", "done")
            state = store.audit("task", "REJECT", "qa", {"spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"], "report": "bug"})
    assert state["stage"] == "ESCALATED"
    assert state["reject_counts"][phase] == 2


def test_code_change_untracked_and_stale_evidence_block_approval(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
    (project / "untracked.js").write_text("new code")
    with pytest.raises(WorkflowError, match="changed"):
        store.audit("task", "APPROVE", "qa", audit_payload(state, tmp_path))
    with pytest.raises(WorkflowError, match="changed"):
        store.status("task")


def test_missing_preview_and_bad_command_block_approval(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
    payload = audit_payload(state, tmp_path)
    payload["preview"]["checks"] = []
    with pytest.raises(WorkflowError):
        store.audit("task", "APPROVE", "qa", payload)
    payload = audit_payload(state, tmp_path)
    payload["commands"][0]["receipt_id"] = "0" * 32
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
    state = reviewed(store, "task", "builder", "done")
    payload = audit_payload(state, tmp_path)
    store.audit("task", "APPROVE", "qa", payload)
    Path(payload["preview"]["checks"][0]["evidence"]).write_text("tampered")
    with pytest.raises(WorkflowError, match="evidence|Artifact"):
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
        reviewed(store, "task", "builder", "done")


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
    state = reviewed(store, "task", "builder", "done")
    (project / "index.html").write_text("changed")
    state = store.audit("task", "REJECT", "qa", {"spec_sha256": state["spec_sha256"],
                        "manifest_sha256": state["manifest_sha256"], "report": "code changed"})
    assert state["next_agent"] == "builder"
    assert reviewed(store, "task", "builder", "fixed")["stage"] == "AUDIT"


@pytest.mark.parametrize("change", ["command", "id", "port"])
def test_invalid_nested_qa_payload_returns_workflow_error(tmp_path, change):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
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
        reviewed(store, "task", "builder", "done")


def test_runtime_logs_excluded_but_untracked_config_included(tmp_path):
    store, project = setup_task(tmp_path)
    approved_design(store, snapshot_exclusions=["server.log"])
    state = reviewed(store, "task", "builder", "done")
    (project / "server.log").write_text("new logs")
    payload = audit_payload(state, tmp_path)
    assert store.audit("task", "APPROVE", "qa", payload)["stage"] == "APPROVED"
    (project / "config.json").write_text("{}")
    with pytest.raises(WorkflowError, match="changed"):
        store.status("task")


def test_partial_approve_with_not_verified_browser_checks(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
    data = verification_payload(store, state, partial=True)
    with pytest.raises(WorkflowError, match="Full APPROVE requires PASS evidence"):
        store.audit("task", "APPROVE", "qa", data)
    state = store.audit("task", "PARTIAL_APPROVE", "qa", data)
    assert state["stage"] == "AUDIT_PENDING_BROWSER"
    assert state["next_agent"] == "human_browser_verification"
    assert state["overall_verdict"] == "PARTIAL_APPROVE"
    assert state["browser_status"] == "NOT_VERIFIED"


def test_evidence_auto_deduplication_and_purpose_mapping(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
    data = verification_payload(store, state)
    shared = data["preview"]["checks"][0]["evidence"]
    data["browser"] = {"status": "PASS", "evidence": shared}
    state = store.audit("task", "APPROVE", "qa", data)
    assert state["stage"] == "APPROVED"
    shared_records = [record for record in state["evidence"] if record["path"] == shared]
    assert len(shared_records) == 1
    assert "ac_check: AC1" in shared_records[0]["purpose"]
    assert "browser" in shared_records[0]["purpose"]
    assert store.status("task")["stage"] == "APPROVED"


def test_verify_browser_happy_path_and_consistency_sweep(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
    state = store.audit("task", "PARTIAL_APPROVE", "qa", verification_payload(store, state, partial=True))
    store.request_browser_verification("task", "qa", "Run pending UI checks")
    data = browser_payload(store, state)
    state = store.verify_browser("task", "browser-qa", data)
    assert state["stage"] == "APPROVED"
    assert state["next_agent"] is None
    assert state["browser_status"] == "PASS"
    assert state["browser_verification_request"]["status"] == "COMPLETED"
    assert state["audit"]["verdict"] == "APPROVE"
    assert state["http_status"] == "NOT_VERIFIED"
    assert state["actors"]["qa_auditor"] == "qa"
    assert state["actors"]["browser_verifier"] == "browser-qa"
    assert state["audit"]["preview"]["checks"][0]["status"] == "PASS"
    assert state["events"][-1]["action"] == "verify_browser"
    assert store.status("task")["stage"] == "APPROVED"


def test_verify_browser_actor_constraints_and_validation(tmp_path):
    store, _ = setup_task(tmp_path)
    approved_design(store)
    state = reviewed(store, "task", "builder", "done")
    state = store.audit("task", "PARTIAL_APPROVE", "qa", verification_payload(store, state, partial=True))
    data = browser_payload(store, state)
    for maker in ("builder", "architect-1"):
        with pytest.raises(WorkflowError, match="Maker and Checker"):
            store.verify_browser("task", maker, data)
    with pytest.raises(WorkflowError, match="spec_sha256"):
        store.verify_browser("task", "browser-qa", dict(data, spec_sha256="wrong"))
    missing = copy.deepcopy(data)
    missing["checks"][0]["evidence"] = str(tmp_path / "missing.png")
    with pytest.raises(WorkflowError, match="Missing or empty evidence"):
        store.verify_browser("task", "browser-qa", missing)
    failed = copy.deepcopy(data)
    failed["checks"][0]["status"] = "FAIL"
    with pytest.raises(WorkflowError, match="must have status PASS"):
        store.verify_browser("task", "browser-qa", failed)
    forged = copy.deepcopy(data)
    forged["checks"][0].pop("receipt_id")
    with pytest.raises(WorkflowError, match="receipt"):
        store.verify_browser("task", "browser-qa", forged)


def test_verify_browser_cli_workflow(tmp_path, monkeypatch, capsys):
    import run_harness
    monkeypatch.setenv("HARNESS_BRAIN_DIR", str(tmp_path / "brain"))
    project = tmp_path / "app"
    project.mkdir()
    (project / "index.html").write_text("app")
    def cli(action, payload=None, actor=None, **options):
        args = ["--workflow", action, "--task-id", "task", "--json"]
        if payload is not None:
            path = tmp_path / "payload.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            args += ["--payload", str(path)]
        if actor: args += ["--actor", actor]
        for key, value in options.items(): args += ["--" + key.replace("_", "-"), str(value)]
        assert run_harness.main(args) == 0
        return json.loads(capsys.readouterr().out)
    cli("init", task="app", project_root=project)
    state = cli("spec", spec(evidence_root=str(tmp_path)), "architect")
    cli("design-review", {"verdict": "APPROVE", "spec_sha256": state["spec_sha256"], "report": "checked"}, "reviewer")
    cli("sign-off", {"spec_sha256": state["spec_sha256"], "human_message": "Duyệt"})
    state = cli("implementation", {"report": "built"}, "builder")
    state = cli("code-review", {"verdict": "APPROVE", "spec_sha256": state["spec_sha256"], "manifest_sha256": state["manifest_sha256"], "report": "checked source"}, "critic")
    store = AppWorkflowStore(tmp_path / "brain")
    data = verification_payload(store, state, partial=True)
    data["verdict"] = "PARTIAL_APPROVE"
    state = cli("audit", data, "qa")
    state = cli("verify-browser", browser_payload(store, state), "browser-qa")
    assert state["stage"] == "APPROVED" and state["next_agent"] is None
    assert state["browser_status"] == "PASS"
