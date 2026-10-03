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
import os
import sys
from pathlib import Path

BASE_URL = "https://graph.facebook.com/v20.0"
ENV_KEYS = ("FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN")

USAGE = """Facebook Fanpage Manager (fb-admin)

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


def _dump(resp) -> None:
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(resp.text)


def post_message(message: str) -> None:
    page_id, token = _config()
    _dump(_requests().post(f"{BASE_URL}/{page_id}/feed",
                        data={"message": message, "access_token": token}, timeout=30))


def list_posts(limit: int = 10) -> None:
    page_id, token = _config()
    _dump(_requests().get(f"{BASE_URL}/{page_id}/posts",
                       params={"limit": limit, "access_token": token}, timeout=30))


def list_comments(post_id: str) -> None:
    _, token = _config()
    _dump(_requests().get(f"{BASE_URL}/{post_id}/comments",
                       params={"access_token": token}, timeout=30))


def reply_comment(comment_id: str, message: str) -> None:
    _, token = _config()
    _dump(_requests().post(f"{BASE_URL}/{comment_id}/comments",
                        data={"message": message, "access_token": token}, timeout=30))


def schedule_feed_post(image_path: str, unix_time: int, caption: str) -> None:
    """Đăng ảnh kèm caption theo lịch (unix_time là thời điểm đăng)."""
    page_id, token = _config()
    with open(image_path, "rb") as fh:
        photo = _requests().post(f"{BASE_URL}/{page_id}/photos",
                              data={"published": "false", "access_token": token},
                              files={"source": fh}, timeout=120).json()
    photo_id = photo.get("id")
    if not photo_id:
        print(json.dumps({"error": "Upload ảnh thất bại", "details": photo},
                         ensure_ascii=False, indent=2))
        return
    _dump(_requests().post(f"{BASE_URL}/{page_id}/feed", data={
        "message": caption, "published": "false",
        "scheduled_publish_time": unix_time,
        "attached_media[0]": json.dumps({"media_fbid": photo_id}),
        "access_token": token,
    }, timeout=30))


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "post":
        if not rest:
            print("Thiếu nội dung bài viết"); return 2
        post_message(" ".join(rest))
    elif cmd == "list_posts":
        list_posts(int(rest[0]) if rest and rest[0].isdigit() else 10)
    elif cmd == "list_comments":
        if not rest:
            print("Thiếu POST_ID"); return 2
        list_comments(rest[0])
    elif cmd == "reply_comment":
        if len(rest) < 2:
            print("Cần COMMENT_ID và nội dung trả lời"); return 2
        reply_comment(rest[0], " ".join(rest[1:]))
    elif cmd == "schedule":
        if len(rest) < 3:
            print("Cần <đường_dẫn_ảnh> <unix_time> <caption>"); return 2
        schedule_feed_post(rest[0], int(rest[1]), " ".join(rest[2:]))
    else:
        print(f"Lệnh không hợp lệ: {cmd}\n\n{USAGE}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
