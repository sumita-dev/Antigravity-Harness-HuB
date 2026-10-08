#!/usr/bin/env python3
"""Facebook Fanpage Manager CLI - Meta Graph API.

Cấu hình (KHÔNG hardcode secret trong file này):
  1. Biến môi trường: FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN
  2. Hoặc file .env tại gốc repo (đã nằm trong .gitignore)

Quyền cần có cho token: pages_manage_posts, pages_read_engagement,
pages_manage_engagement, pages_read_user_content.

Token không bao giờ được in ra stdout/stderr.
"""

import json
import hashlib
import io
import os
import re
import sys
import argparse
from pathlib import Path

# Đảm bảo hỗ trợ UTF-8 trơn tru trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://graph.facebook.com/v20.0"
ENV_KEYS = ("FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN")

USAGE = """Facebook Fanpage Manager (fb-admin)

Write commands require: --task-id TASK --publish-id PUBLISH [--brain .brain]
Prepare and authorize the exact payload in MarketingWorkflowStore before sending.

  python fb_api.py post "<nội dung bài viết>"
  python fb_api.py list_posts [limit]
  python fb_api.py list_comments <POST_ID>
  python fb_api.py reply_comment <COMMENT_ID> "<nội dung trả lời>"
  python fb_api.py schedule <đường_dẫn_ảnh> <unix_time> "<caption>"

Cấu hình: đặt FB_PAGE_ID và FB_PAGE_ACCESS_TOKEN trong biến môi trường
hoặc file .env tại gốc repo.
"""


def load_env(start: Path | None = None) -> None:
    """Nạp FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN từ .env nếu môi trường chưa có."""
    if all(os.environ.get(k) for k in ENV_KEYS):
        return
    here = (start or Path(__file__).resolve()).parent
    for base in [here, *here.parents]:
        env_file = base / ".env"
        if not env_file.is_file():
            continue
        for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key in ENV_KEYS and not os.environ.get(key):
                os.environ[key] = val.strip().strip('"').strip("'")
        return


def _config():
    load_env()
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        sys.stderr.write(
            "[LỖI XÁC THỰC] Thiếu FB_PAGE_ID hoặc FB_PAGE_ACCESS_TOKEN.\n"
            "  Cách 1: export FB_PAGE_ID=... ; export FB_PAGE_ACCESS_TOKEN=...\n"
            "  Cách 2: tạo file .env tại gốc repo (xem .env.example).\n"
        )
        raise SystemExit(1)
    return page_id, token


def _requests():
    """Import muộn để CLI vẫn hiển thị --help khi chưa cài requests."""
    try:
        import requests
    except ImportError:  # pragma: no cover
        sys.stderr.write(
            "[LỖI PHỤ THUỘC] Thiếu package 'requests'.\n"
            "  Cài đặt: pip install -r requirements.txt\n"
        )
        raise SystemExit(1)
    return requests


class ApiFailure(RuntimeError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def redact(value):
    if isinstance(value, dict):
        return {redact(str(k)): ("[REDACTED]" if re.search(r"token|secret|authorization", str(k), re.I) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
        for candidate in (token, token.strip()):
            if candidate.strip():
                value = value.replace(candidate, "[REDACTED]")
        return re.sub(r"(?i)(access_token[=:\s]+)[^\s&\"']+", r"\1[REDACTED]", value)
    return value


def _response(resp, require_id=False):
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ApiFailure("Invalid JSON response", uncertain=True) from exc
    if not isinstance(payload, dict):
        raise ApiFailure("Unexpected API response", uncertain=True)
    if not 200 <= resp.status_code < 300 or payload.get("error"):
        raise ApiFailure(json.dumps(redact({"http_status": resp.status_code, "error": payload.get("error", "HTTP failure")}), ensure_ascii=False), uncertain=resp.status_code >= 500)
    if require_id and not payload.get("id"):
        raise ApiFailure("API response missing external id", uncertain=True)
    return payload


def _dump(resp) -> dict:
    payload = _response(resp)
    print(json.dumps(redact(payload), indent=2, ensure_ascii=False))
    return payload


def _publish(payload, operation, gate, media_snapshots=None):
    if gate is None:
        raise ValueError("Publishing requires --task-id, --publish-id and current exact authorization")
    store, task_id, publish_id = gate
    record = store.validate_publish(task_id, publish_id, payload)
    # The checkpoint is UNKNOWN before sending: a lost response may hide a completed write.
    try:
        if media_snapshots is not None:
            approved_media = record.get("binding", {}).get("media", [])
            if len(approved_media) != len(media_snapshots) or any(hashlib.sha256(data).hexdigest() != media.get("sha256") for data, media in zip(media_snapshots, approved_media)):
                raise ApiFailure("Media snapshot differs from approved bytes")
        result = operation()
    except Exception as exc:
        state = "FAILED" if isinstance(exc, ApiFailure) and not exc.uncertain else "UNKNOWN"
        store.record_publish(task_id, publish_id, state, error=str(redact(str(exc))))
        raise
    store.record_publish(task_id, publish_id, "SUCCEEDED", external_id=str(result["id"]))
    print(json.dumps(redact(result), indent=2, ensure_ascii=False))
    return result


def post_message(message: str, *, gate=None) -> dict:
    page_id, token = _config()
    payload = {"action": "post", "destination": page_id, "content": message, "media": [], "schedule": None}
    return _publish(payload, lambda: _response(_requests().post(f"{BASE_URL}/{page_id}/feed",
                        data={"message": message, "access_token": token}, timeout=30), require_id=True), gate)


def list_posts(limit: int = 10) -> None:
    page_id, token = _config()
    _dump(_requests().get(f"{BASE_URL}/{page_id}/posts",
                       params={"limit": limit, "access_token": token}, timeout=30))


def list_comments(post_id: str) -> None:
    _, token = _config()
    _dump(_requests().get(f"{BASE_URL}/{post_id}/comments",
                       params={"access_token": token}, timeout=30))


def reply_comment(comment_id: str, message: str, *, gate=None) -> dict:
    _, token = _config()
    payload = {"action": "reply_comment", "destination": comment_id, "content": message, "media": [], "schedule": None}
    return _publish(payload, lambda: _response(_requests().post(f"{BASE_URL}/{comment_id}/comments",
                        data={"message": message, "access_token": token}, timeout=30), require_id=True), gate)


def schedule_feed_post(image_path: str, unix_time: int, caption: str, *, gate=None) -> dict:
    """Đăng ảnh kèm caption theo lịch (unix_time là thời điểm đăng)."""
    page_id, token = _config()
    image = Path(image_path).resolve(strict=True)
    image_bytes = image.read_bytes()
    payload = {"action": "schedule", "destination": page_id, "content": caption, "media": [str(image)], "schedule": str(unix_time)}
    def operation():
        with io.BytesIO(image_bytes) as fh:
            photo = _response(_requests().post(f"{BASE_URL}/{page_id}/photos",
                              data={"published": "false", "access_token": token},
                              files={"source": fh}, timeout=120), require_id=True)
        return _response(_requests().post(f"{BASE_URL}/{page_id}/feed", data={
        "message": caption, "published": "false",
        "scheduled_publish_time": unix_time,
        "attached_media[0]": json.dumps({"media_fbid": photo["id"]}),
        "access_token": token,
        }, timeout=30), require_id=True)
    return _publish(payload, operation, gate, media_snapshots=[image_bytes])


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--task-id")
    parser.add_argument("--publish-id")
    parser.add_argument("--brain", default=str(Path(__file__).resolve().parents[5] / ".brain"))
    try:
        options, positional = parser.parse_known_args(args)
        return _dispatch(positional, options)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(json.dumps({"error": redact(str(exc))}, ensure_ascii=False), file=sys.stderr)
        return 1


def _dispatch(args, options):
    if not args:
        return 2
    cmd, rest = args[0], args[1:]
    gate = None
    if cmd == "post" and not rest:
        return 2
    if cmd == "reply_comment" and len(rest) < 2:
        return 2
    if cmd == "schedule" and (len(rest) < 3 or not rest[1].isdigit()):
        return 2
    if cmd in {"post", "reply_comment", "schedule"}:
        if not options.task_id or not options.publish_id:
            raise ValueError("Publishing requires --task-id and --publish-id")
        repo = Path(__file__).resolve().parents[5]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from harness.marketing_workflow import MarketingWorkflowStore
        gate = (MarketingWorkflowStore(Path(options.brain)), options.task_id, options.publish_id)
    if cmd == "post":
        if not rest:
            print("Thiếu nội dung bài viết"); return 2
        post_message(" ".join(rest), gate=gate)
    elif cmd == "list_posts":
        if len(rest) > 1 or (rest and (not rest[0].isdigit() or int(rest[0]) < 1)):
            return 2
        list_posts(int(rest[0]) if rest else 10)
    elif cmd == "list_comments":
        if not rest:
            print("Thiếu POST_ID"); return 2
        list_comments(rest[0])
    elif cmd == "reply_comment":
        if len(rest) < 2:
            print("Cần COMMENT_ID và nội dung trả lời"); return 2
        reply_comment(rest[0], " ".join(rest[1:]), gate=gate)
    elif cmd == "schedule":
        if len(rest) < 3:
            print("Cần <đường_dẫn_ảnh> <unix_time> <caption>"); return 2
        if not rest[1].isdigit():
            return 2
        schedule_feed_post(rest[0], int(rest[1]), " ".join(rest[2:]), gate=gate)
    else:
        print(f"Lệnh không hợp lệ: {cmd}\n\n{USAGE}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
