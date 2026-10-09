"""Offline regression checks for marketing CLI safety and truthful results."""
import importlib.util
import json
import hashlib
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_tool(skill, filename):
    path = ROOT / "plugins" / "marketing" / "skills" / skill / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("padding", ["  ", "\t", "\n "])
def test_redaction_covers_effective_and_raw_padded_config_token(monkeypatch, padding):
    tool = load_tool("fb-admin", "fb_api.py")
    secret = "qa-synthetic-effective-token"
    raw = padding + secret + padding
    monkeypatch.setenv("FB_PAGE_ID", "page")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", raw)
    _, effective = tool._config()
    assert effective == secret
    result = tool.redact({"message": "remote echo " + effective, "nested": ["raw echo " + raw, {"echo " + effective: effective}]})
    assert effective not in json.dumps(result)
    assert "[REDACTED]" in result["message"]


def test_policy_screen_never_certifies_safety_or_monetization():
    tool = load_tool("check-youtube-policy", "audit_policy.py")
    result = tool.analyze_script("A quiet story about a garden.")
    report = tool.format_markdown_report(result, "")
    assert result["screening_method"] == "regex_heuristic"
    assert result["limitations"]
    assert "AN TOÀN TUYỆT ĐỐI" not in report
    assert "đủ điều kiện bật kiếm tiền" not in report
    assert "bản quyền" in report and "YPP" in report


class Response:
    def __init__(self, data=None, status=200, invalid=False):
        self.data, self.status_code, self.invalid = data, status, invalid

    def json(self):
        if self.invalid:
            raise ValueError("invalid JSON token-secret")
        return self.data


class Gate:
    def __init__(self, expected, reject=False):
        self.expected, self.reject, self.records, self.status = expected, reject, [], "PREPARED"

    def validate_publish(self, task, publish, payload):
        if self.reject or payload != self.expected or self.status != "PREPARED":
            raise ValueError("stale or absent authorization")
        self.status = "UNKNOWN"
        return {"binding": {"media": [{"sha256": hashlib.sha256(Path(item).read_bytes()).hexdigest()} for item in payload["media"]]}}

    def record_publish(self, task, publish, status, **kwargs):
        self.status = status
        self.records.append((status, kwargs))


@pytest.fixture
def fb(monkeypatch):
    tool = load_tool("fb-admin", "fb_api.py")
    monkeypatch.setattr(tool, "_config", lambda: ("page-1", "token-secret"))
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "token-secret")
    return tool


@pytest.mark.parametrize("response", [Response({"error": {"message": "token-secret", "code": 190}}), Response({}, 400), Response({}, 500), Response(invalid=True)])
def test_facebook_read_errors_nonzero_and_redacted(fb, monkeypatch, capsys, response):
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(get=lambda *a, **k: response))
    assert fb.main(["list_posts"]) == 1
    captured = capsys.readouterr()
    assert "token-secret" not in captured.out + captured.err


def test_recursive_token_redaction(fb, monkeypatch, capsys):
    data = {"data": [{"access_token": "other-secret", "nested": {"url": "https://example.test/?access_token=unknown-secret", "message": "echo token-secret"}}]}
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(get=lambda *a, **k: Response(data)))
    assert fb.main(["list_posts"]) == 0
    captured = capsys.readouterr()
    assert not any(s in captured.out for s in ("other-secret", "unknown-secret", "token-secret"))


def test_write_requires_gate_without_network(fb, monkeypatch):
    monkeypatch.setattr(fb, "_requests", lambda: pytest.fail("unauthorized network"))
    assert fb.main(["post", "draft"]) == 1


def test_stale_payload_blocked_before_network(fb, monkeypatch):
    gate = Gate({"action": "post", "destination": "page-1", "content": "approved", "media": [], "schedule": None})
    monkeypatch.setattr(fb, "_requests", lambda: pytest.fail("stale network"))
    with pytest.raises(ValueError):
        fb.post_message("edited", gate=(gate, "task", "publish"))


def test_timeout_unknown_blocks_retry(fb, monkeypatch):
    payload = {"action": "post", "destination": "page-1", "content": "draft", "media": [], "schedule": None}
    gate = Gate(payload)
    calls = []
    def post(*args, **kwargs):
        calls.append(args)
        raise TimeoutError("timeout token-secret")
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(post=post))
    with pytest.raises(Exception):
        fb.post_message("draft", gate=(gate, "task", "publish"))
    assert gate.status == "UNKNOWN"
    with pytest.raises(ValueError):
        fb.post_message("draft", gate=(gate, "task", "publish"))
    assert len(calls) == 1


def test_upload_missing_id_fails_and_does_not_submit_feed(fb, monkeypatch):
    fixture_dir = ROOT / ".brain" / "artifacts" / "harness-completion" / ("upload-fixture-" + uuid.uuid4().hex)
    fixture_dir.mkdir(parents=True)
    image = fixture_dir / "image.png"
    image.write_bytes(b"fixture")
    payload = {"action": "schedule", "destination": "page-1", "content": "caption", "media": [str(image.resolve())], "schedule": "1234567890"}
    gate = Gate(payload)
    calls = []
    def post(*args, **kwargs):
        calls.append(args)
        return Response({"success": True})
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(post=post))
    with pytest.raises(Exception):
        fb.schedule_feed_post(str(image), 1234567890, "caption", gate=(gate, "task", "publish"))
    assert len(calls) == 1 and gate.status == "UNKNOWN"


def test_success_requires_api_id_and_records_it(fb, monkeypatch):
    payload = {"action": "post", "destination": "page-1", "content": "draft", "media": [], "schedule": None}
    gate = Gate(payload)
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(post=lambda *a, **k: Response({"id": "post-42"})))
    fb.post_message("draft", gate=(gate, "task", "publish"))
    assert gate.status == "SUCCEEDED" and gate.records[-1][1]["external_id"] == "post-42"


@pytest.mark.parametrize("response,state", [(Response({"error": {"code": 190, "message": "token-secret"}}, 400), "FAILED"), (Response({}, 503), "UNKNOWN"), (Response(invalid=True), "UNKNOWN"), (Response({"success": True}), "UNKNOWN")])
def test_write_errors_preserve_ambiguous_outcome(fb, monkeypatch, response, state):
    payload = {"action": "post", "destination": "page-1", "content": "draft", "media": [], "schedule": None}
    gate = Gate(payload)
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(post=lambda *a, **k: response))
    with pytest.raises(Exception):
        fb.post_message("draft", gate=(gate, "task", "publish"))
    assert gate.status == state
    assert "token-secret" not in json.dumps(gate.records)


def test_network_read_failure_nonzero_redacted(fb, monkeypatch, capsys):
    def get(*args, **kwargs):
        raise ConnectionError("token-secret access_token=another-secret")
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(get=get))
    assert fb.main(["list_posts"]) == 1
    assert "secret" not in capsys.readouterr().err


@pytest.mark.parametrize("args", [["post"], ["schedule", "missing"], ["schedule", "image.png", "bad", "caption"], ["list_posts", "bad"], ["reply_comment", "comment"]])
def test_invalid_facebook_arguments_exit_two(fb, args):
    assert fb.main(args) == 2


def test_facebook_cli_consumes_real_approved_checkpoint(fb, monkeypatch):
    helpers_spec = importlib.util.spec_from_file_location("marketing_helpers", ROOT / "tests" / "test_marketing_workflow.py")
    helpers = importlib.util.module_from_spec(helpers_spec)
    helpers_spec.loader.exec_module(helpers)
    brain = ROOT / ".brain" / "artifacts" / "harness-completion" / ("fb-checkpoint-" + uuid.uuid4().hex)
    brain.mkdir(parents=True)
    workflow, _, state, _ = helpers.fixture(brain)
    workflow.audit("task", "independent-checker", helpers.approval(brain, state))
    request = {"action": "post", "destination": "page-1", "content": "12 customers", "media": [], "schedule": None}
    record = workflow.prepare_publish("task", "operator", request)
    calls = []
    def post(*args, **kwargs):
        calls.append(args)
        return Response({"id": "remote-42"})
    monkeypatch.setattr(fb, "_requests", lambda: SimpleNamespace(post=post))
    args = ["post", "12 customers", "--task-id", "task", "--publish-id", record["publish_id"], "--brain", str(brain)]
    assert fb.main(args) == 1 and not calls
    workflow.authorize_publish("task", record["publish_id"], "PUBLISH: approved")
    assert fb.main(args) == 0 and len(calls) == 1
    assert fb.main(args) == 1 and len(calls) == 1
    assert workflow.status("task")["publishing"][record["publish_id"]]["status"] == "SUCCEEDED"


def test_media_snapshot_mismatch_never_uploads(fb, monkeypatch):
    directory = ROOT / ".brain" / "artifacts" / "harness-completion" / ("freeze-fixture-" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    image = directory / "image.png"
    image.write_bytes(b"approved image")
    payload = {"action": "schedule", "destination": "page-1", "content": "caption", "media": [str(image.resolve())], "schedule": "1234567890"}
    class RestoringGate(Gate):
        def validate_publish(self, task, publish, request):
            record = super().validate_publish(task, publish, request)
            record["binding"]["media"][0]["sha256"] = hashlib.sha256(b"different approved image").hexdigest()
            return record
    gate = RestoringGate(payload)
    monkeypatch.setattr(fb, "_requests", lambda: pytest.fail("mismatched media uploaded"))
    with pytest.raises(Exception):
        fb.schedule_feed_post(str(image), 1234567890, "caption", gate=(gate, "task", "publish"))
    assert gate.status == "FAILED"


def test_marketing_junction_guard_checks_ancestors(monkeypatch):
    from harness.marketing_workflow import _safe_path, WorkflowError
    junction = ROOT / ".brain" / "fake-junction"
    monkeypatch.setattr(Path, "is_junction", lambda path: path == junction, raising=False)
    with pytest.raises(WorkflowError, match="junction"):
        _safe_path(junction / "evidence.txt")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration")
def test_marketing_rejects_real_windows_junction():
    from harness.marketing_workflow import _safe_path, WorkflowError
    directory = ROOT / ".brain" / "artifacts" / "harness-completion" / ("junction-fixture-" + uuid.uuid4().hex)
    target, link = directory / "target", directory / "link"
    target.mkdir(parents=True)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(WorkflowError, match="junction"):
            _safe_path(link / "evidence.txt")
    finally:
        link.rmdir()


def test_analyzer_offline_node_regressions():
    result = subprocess.run(["node", "tests/marketing_analyzer.test.js"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_social_reach_redaction_comprehensive(monkeypatch):
    from scripts.social_reach import redact_sensitive_data

    secret_auth = "qa-dummy-auth-token-999"
    secret_ct0 = "qa-dummy-ct0-xyz"
    secret_session = "qa-dummy-session-123"
    secret_cookie = "qa-dummy-cookie-abc"
    secret_key = "qa-dummy-key-456"
    secret_bearer = "qa-dummy-bearer-789"
    env_secret = "qa-dummy-env-secret-999"

    monkeypatch.setenv("TWITTER_AUTH_TOKEN", env_secret)

    raw_text = (
        f"auth_token={secret_auth}; ct0={secret_ct0}; sessionid={secret_session}; "
        f"cookie: {secret_cookie}\napi_key={secret_key}; Bearer {secret_bearer} and env={env_secret}"
    )
    redacted_text = redact_sensitive_data(raw_text)

    for secret in (secret_auth, secret_ct0, secret_session, secret_cookie, secret_key, secret_bearer, env_secret):
        assert secret not in redacted_text
    assert "[REDACTED]" in redacted_text

    raw_dict = {
        "auth_token": secret_auth,
        "nested": {
            "ct0": secret_ct0,
            "sessionid": secret_session,
            "cookie": secret_cookie,
            "api_key": secret_key,
            "safe_value": "hello world",
        },
        "list_items": [
            f"auth_token={secret_auth}",
            {"bearer_token": secret_bearer},
        ],
    }
    redacted_dict = redact_sensitive_data(raw_dict)
    serialized = json.dumps(redacted_dict)
    for secret in (secret_auth, secret_ct0, secret_session, secret_cookie, secret_key, secret_bearer):
        assert secret not in serialized
    assert redacted_dict["nested"]["safe_value"] == "hello world"


def test_social_reach_cli_doctor_json():
    script_path = ROOT / "scripts" / "social_reach.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--platform", "doctor", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["doctor"] is True
    assert "binaries" in payload
    assert "platforms" in payload
    for platform in ("twitter", "reddit", "youtube", "web", "jina"):
        assert platform in payload["platforms"]


def test_social_reach_fallback_uninstalled_platform_no_crash(monkeypatch):
    import shutil
    from scripts.social_reach import run_reach, main

    # Giả lập không tìm thấy binary nào
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    # 1. Gọi run_reach trực tiếp
    res_tw = run_reach("twitter", query="test")
    assert res_tw["status"] == "unavailable"
    assert "limitations" in res_tw
    assert "fallback_suggested" in res_tw

    res_rd = run_reach("reddit", query="test")
    assert res_rd["status"] == "unavailable"
    assert "limitations" in res_rd

    res_yt = run_reach("youtube", url="https://youtube.com/watch?v=123")
    assert res_yt["status"] == "unavailable"
    assert "limitations" in res_yt

    # 2. Gọi main CLI với platform chưa cài đặt phải trả về exit code 0 thay vì crash
    exit_code = main(["--platform", "twitter", "--json"])
    assert exit_code == 0


def test_social_reach_jina_fallback_mock_and_offline(monkeypatch):
    import urllib.request
    from scripts.social_reach import fetch_jina_fallback, run_reach

    # Test trường hợp thiếu tham số
    missing_res = fetch_jina_fallback()
    assert missing_res["status"] == "unavailable"

    # Test thành công với mocked urllib
    class DummyResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=30: DummyResponse(b"# Mocked Jina Article\n\nContent extracted cleanly."),
    )

    success_res = run_reach("jina", url="https://example.com/test")
    assert success_res["status"] == "success"
    assert "Mocked Jina Article" in success_res["content_preview"]

    # Test lỗi mạng không gây crash
    def raise_network_err(*args, **kwargs):
        raise ConnectionResetError("Connection reset by peer")

    monkeypatch.setattr(urllib.request, "urlopen", raise_network_err)
    err_res = run_reach("jina", url="https://offline-target.test")
    assert err_res["status"] == "unavailable"
    assert "limitations" in err_res
    assert "fallback_suggested" in err_res

