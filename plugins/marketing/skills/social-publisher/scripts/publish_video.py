#!/usr/bin/env python3
"""Publish or schedule videos to Facebook Page and YouTube (stdlib only)."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

GRAPH_VERSION = "v21.0"
FB_GRAPH_VIDEO_BASE = f"https://graph-video.facebook.com/{GRAPH_VERSION}"
YT_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_RESUMABLE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
    "?uploadType=resumable&part=snippet,status"
)
YT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
FB_MIN_SCHEDULE_SECONDS = 10 * 60
FB_MAX_SCHEDULE_SECONDS = 30 * 24 * 60 * 60


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def load_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def get_setting(key: str, env_map: dict[str, str]) -> str:
    env_val = os.environ.get(key, "").strip()
    if env_val:
        return env_val
    return env_map.get(key, "").strip()


def redact_secrets(text: str, secret_vals: list[str]) -> str:
    masked = text
    for val in secret_vals:
        if val:
            masked = masked.replace(val, "[REDACTED]")
    return masked


def parse_schedule(schedule_str: str) -> datetime:
    raw = schedule_str.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    dt: datetime | None = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue

    if dt is None:
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid --schedule format '{schedule_str}'. Use 'YYYY-MM-DD HH:MM' or ISO-8601."
            ) from exc

    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc)


def validate_schedule_for_platforms(
    scheduled_utc: datetime, platforms: list[str]
) -> None:
    now_utc = datetime.now(timezone.utc)
    delta_seconds = (scheduled_utc - now_utc).total_seconds()
    if "yt" in platforms and delta_seconds <= 0:
        raise ValueError("YouTube --schedule must be in the future.")
    if "fb" in platforms:
        if delta_seconds < FB_MIN_SCHEDULE_SECONDS:
            raise ValueError(
                "Facebook --schedule must be at least 10 minutes in the future."
            )
        if delta_seconds > FB_MAX_SCHEDULE_SECONDS:
            raise ValueError(
                "Facebook --schedule must be within 30 days from now."
            )


def resolve_fb_credentials(
    config_dir: Path, env_map: dict[str, str], page_id_arg: str | None
) -> tuple[str, str]:
    page_id = (page_id_arg or "").strip() or get_setting("FB_PAGE_ID", env_map)
    if not page_id:
        raise ValueError("Missing FB_PAGE_ID (pass --page-id or set in .env).")

    tokens_file = config_dir / "fb_tokens.json"
    if tokens_file.is_file():
        data = json.loads(tokens_file.read_text(encoding="utf-8"))
        for page in data.get("pages", []):
            if str(page.get("id", "")) == page_id and page.get("access_token"):
                return page_id, str(page["access_token"])

    env_token = get_setting("FB_PAGE_ACCESS_TOKEN", env_map)
    if env_token:
        return page_id, env_token

    raise ValueError(
        f"Missing Page Access Token for page_id={page_id} in fb_tokens.json and .env."
    )


def resolve_yt_credentials(
    config_dir: Path, env_map: dict[str, str]
) -> tuple[Path, dict, str, str]:
    token_path = config_dir / "youtube_token.json"
    if not token_path.is_file():
        raise ValueError(
            f"Missing {token_path}. Run setup_youtube_oauth.py first."
        )
    token_data = json.loads(token_path.read_text(encoding="utf-8"))
    if not token_data.get("refresh_token"):
        raise ValueError("youtube_token.json is missing refresh_token.")

    client_id = get_setting("YOUTUBE_CLIENT_ID", env_map)
    client_secret = get_setting("YOUTUBE_CLIENT_SECRET", env_map)
    if not client_id or not client_secret:
        raise ValueError("Missing YOUTUBE_CLIENT_ID or YOUTUBE_CLIENT_SECRET.")

    return token_path, token_data, client_id, client_secret


def encode_multipart(
    fields: dict[str, str],
    file_field: tuple[str, str, bytes, str] | None = None,
) -> tuple[bytes, str]:
    boundary = f"----SocialPublisher{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
        )
        chunks.append(f"{value}\r\n".encode("utf-8"))

    if file_field is not None:
        field_name, filename, content, content_type = file_field
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(content)
        chunks.append(b"\r\n")

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def http_request_json(
    url: str,
    method: str,
    data: bytes | None,
    headers: dict[str, str],
    secret_vals: list[str],
    timeout: int = 120,
) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code}: {redact_secrets(body, secret_vals)}"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error: {redact_secrets(str(exc.reason), secret_vals)}"
        ) from None


def refresh_yt_access_token(
    token_path: Path,
    token_data: dict,
    client_id: str,
    client_secret: str,
    secret_vals: list[str],
) -> str:
    refresh_token = str(token_data["refresh_token"])
    secret_vals.extend([client_secret, refresh_token])

    form = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    resp = http_request_json(
        YT_OAUTH_TOKEN_URL,
        "POST",
        form,
        {"Content-Type": "application/x-www-form-urlencoded"},
        secret_vals,
        timeout=30,
    )
    new_access_token = resp.get("access_token", "")
    if not new_access_token:
        raise RuntimeError("Failed to refresh YouTube access_token.")
    secret_vals.append(new_access_token)

    now = datetime.now(timezone.utc)
    expires_in = int(resp.get("expires_in", 3600))
    token_data["access_token"] = new_access_token
    if resp.get("refresh_token"):
        token_data["refresh_token"] = resp["refresh_token"]
    token_data["expires_in"] = expires_in
    token_data["expires_at"] = (now + timedelta(seconds=expires_in)).isoformat()
    token_data["updated_at"] = now.isoformat()
    token_path.write_text(
        json.dumps(token_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return new_access_token


def build_yt_metadata(
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
    scheduled_utc: datetime | None,
) -> dict:
    snippet: dict = {
        "title": title,
        "description": description,
    }
    if tags:
        snippet["tags"] = tags

    status: dict = {
        "privacyStatus": "private" if scheduled_utc is not None else privacy,
    }
    if scheduled_utc is not None:
        status["publishAt"] = scheduled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {"snippet": snippet, "status": status}


def upload_youtube(
    video_path: Path,
    metadata: dict,
    access_token: str,
    scheduled_utc: datetime | None,
    secret_vals: list[str],
) -> dict:
    file_size = video_path.stat().st_size
    mime_type = mimetypes.guess_type(str(video_path))[0] or "video/*"

    init_req = urllib.request.Request(
        YT_RESUMABLE_UPLOAD_URL,
        data=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": mime_type,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(init_req, timeout=60) as resp:
            upload_uri = resp.headers.get("Location")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"YouTube init HTTP {exc.code}: {redact_secrets(body, secret_vals)}"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"YouTube init network error: {redact_secrets(str(exc.reason), secret_vals)}"
        ) from None

    if not upload_uri:
        raise RuntimeError("YouTube resumable init did not return Location header.")

    uploaded = 0
    video_resp: dict | None = None
    with video_path.open("rb") as fh:
        while uploaded < file_size:
            fh.seek(uploaded)
            chunk = fh.read(YT_CHUNK_SIZE)
            if not chunk:
                break
            end_byte = uploaded + len(chunk) - 1
            put_req = urllib.request.Request(
                upload_uri,
                data=chunk,
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {uploaded}-{end_byte}/{file_size}",
                    "Content-Type": "application/octet-stream",
                },
                method="PUT",
            )
            try:
                with urllib.request.urlopen(put_req, timeout=300) as resp:
                    if resp.status in (200, 201):
                        video_resp = json.loads(resp.read().decode("utf-8"))
                        uploaded = file_size
                        break
                    uploaded = end_byte + 1
            except urllib.error.HTTPError as exc:
                if exc.code == 308:
                    range_header = exc.headers.get("Range")
                    if range_header and "-" in range_header:
                        last_byte = int(range_header.split("-")[-1])
                        uploaded = last_byte + 1
                    else:
                        uploaded = end_byte + 1
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"YouTube chunk HTTP {exc.code}: {redact_secrets(body, secret_vals)}"
                ) from None
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    f"YouTube chunk network error: {redact_secrets(str(exc.reason), secret_vals)}"
                ) from None

    if not video_resp or not video_resp.get("id"):
        raise RuntimeError("YouTube upload finished without returning video id.")

    video_id = str(video_resp["id"])
    return {
        "status": "scheduled" if scheduled_utc is not None else "published",
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "scheduled_at": (
            scheduled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            if scheduled_utc is not None
            else None
        ),
    }


def upload_facebook(
    video_path: Path,
    page_id: str,
    page_token: str,
    title: str,
    description: str,
    scheduled_utc: datetime | None,
    secret_vals: list[str],
) -> dict:
    endpoint = f"{FB_GRAPH_VIDEO_BASE}/{page_id}/videos"
    file_size = video_path.stat().st_size

    # Step 1: start
    start_body, start_ct = encode_multipart(
        {
            "access_token": page_token,
            "upload_phase": "start",
            "file_size": str(file_size),
        }
    )
    start_resp = http_request_json(
        endpoint,
        "POST",
        start_body,
        {"Content-Type": start_ct},
        secret_vals,
        timeout=60,
    )
    session_id = str(start_resp.get("upload_session_id", ""))
    video_id = str(start_resp.get("video_id", ""))
    if not session_id or not video_id:
        raise RuntimeError("Facebook upload start missing upload_session_id or video_id.")

    start_offset = int(start_resp.get("start_offset", 0))
    end_offset = int(start_resp.get("end_offset", 0))

    # Step 2: transfer chunks
    with video_path.open("rb") as fh:
        while start_offset < end_offset:
            fh.seek(start_offset)
            chunk = fh.read(end_offset - start_offset)
            if not chunk:
                break
            transfer_body, transfer_ct = encode_multipart(
                {
                    "access_token": page_token,
                    "upload_phase": "transfer",
                    "upload_session_id": session_id,
                    "start_offset": str(start_offset),
                },
                file_field=(
                    "video_file_chunk",
                    video_path.name,
                    chunk,
                    "application/octet-stream",
                ),
            )
            transfer_resp = http_request_json(
                endpoint,
                "POST",
                transfer_body,
                {"Content-Type": transfer_ct},
                secret_vals,
                timeout=300,
            )
            start_offset = int(transfer_resp.get("start_offset", file_size))
            end_offset = int(transfer_resp.get("end_offset", file_size))

    # Step 3: finish
    finish_fields: dict[str, str] = {
        "access_token": page_token,
        "upload_phase": "finish",
        "upload_session_id": session_id,
    }
    if title:
        finish_fields["title"] = title
    if description:
        finish_fields["description"] = description
    if scheduled_utc is not None:
        finish_fields["published"] = "false"
        finish_fields["scheduled_publish_time"] = str(int(scheduled_utc.timestamp()))

    finish_body, finish_ct = encode_multipart(finish_fields)
    finish_resp = http_request_json(
        endpoint,
        "POST",
        finish_body,
        {"Content-Type": finish_ct},
        secret_vals,
        timeout=60,
    )
    if not finish_resp.get("success"):
        raise RuntimeError(
            f"Facebook upload finish did not succeed: {redact_secrets(json.dumps(finish_resp), secret_vals)}"
        )

    return {
        "status": "scheduled" if scheduled_utc is not None else "published",
        "video_id": video_id,
        "url": f"https://www.facebook.com/{page_id}/videos/{video_id}",
        "scheduled_at": (
            scheduled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            if scheduled_utc is not None
            else None
        ),
    }


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Publish or schedule video to Facebook Page and/or YouTube."
    )
    parser.add_argument(
        "--platform",
        required=True,
        choices=("fb", "yt", "all"),
        help="Target platform(s).",
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Path to the video file.",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Video title (required when platform includes yt).",
    )
    parser.add_argument(
        "--description",
        default="",
        help="Video description / caption.",
    )
    parser.add_argument(
        "--tags",
        default="",
        help="Comma-separated tags for YouTube.",
    )
    parser.add_argument(
        "--privacy",
        default="private",
        choices=("public", "unlisted", "private"),
        help="YouTube privacy status (default: private).",
    )
    parser.add_argument(
        "--schedule",
        default=None,
        help="Schedule time ('YYYY-MM-DD HH:MM' local time or ISO-8601).",
    )
    parser.add_argument(
        "--page-id",
        default=None,
        help="Optional Facebook Page ID (overrides FB_PAGE_ID).",
    )
    parser.add_argument(
        "--config-dir",
        default=os.getcwd(),
        help="Directory containing .env and token files (default: cwd).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs, config, schedule constraints and print planned payload without calling APIs.",
    )
    args = parser.parse_args()

    platforms = ["fb", "yt"] if args.platform == "all" else [args.platform]
    config_dir = Path(args.config_dir).resolve()
    env_map = load_env_file(config_dir / ".env")
    video_path = Path(args.video).resolve()
    secret_vals: list[str] = []

    try:
        if not video_path.is_file():
            raise ValueError(f"Video file not found: {video_path}")
        file_size = video_path.stat().st_size
        if file_size <= 0:
            raise ValueError(f"Video file is empty: {video_path}")

        if "yt" in platforms and not args.title.strip():
            raise ValueError("--title is required when publishing to YouTube.")

        scheduled_utc: datetime | None = None
        if args.schedule:
            scheduled_utc = parse_schedule(args.schedule)
            validate_schedule_for_platforms(scheduled_utc, platforms)

        tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

        fb_creds: tuple[str, str] | None = None
        if "fb" in platforms:
            fb_creds = resolve_fb_credentials(config_dir, env_map, args.page_id)
            secret_vals.append(fb_creds[1])

        yt_creds: tuple[Path, dict, str, str] | None = None
        if "yt" in platforms:
            yt_creds = resolve_yt_credentials(config_dir, env_map)
            secret_vals.extend(
                [
                    str(yt_creds[1].get("access_token", "")),
                    str(yt_creds[1].get("refresh_token", "")),
                    yt_creds[3],
                ]
            )

        if args.dry_run:
            planned: dict[str, dict] = {}
            if "fb" in platforms and fb_creds is not None:
                fb_payload: dict[str, object] = {
                    "page_id": fb_creds[0],
                    "endpoint": f"{FB_GRAPH_VIDEO_BASE}/{fb_creds[0]}/videos",
                    "file_size": file_size,
                    "title": args.title.strip(),
                    "description": args.description,
                }
                if scheduled_utc is not None:
                    fb_payload["published"] = False
                    fb_payload["scheduled_publish_time"] = int(scheduled_utc.timestamp())
                planned["fb"] = {
                    "status": "dry_run",
                    "video_id": None,
                    "url": None,
                    "scheduled_at": (
                        scheduled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                        if scheduled_utc is not None
                        else None
                    ),
                    "planned_payload": fb_payload,
                }
            if "yt" in platforms:
                yt_meta = build_yt_metadata(
                    args.title.strip(),
                    args.description,
                    tags_list,
                    args.privacy,
                    scheduled_utc,
                )
                planned["yt"] = {
                    "status": "dry_run",
                    "video_id": None,
                    "url": None,
                    "scheduled_at": (
                        scheduled_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                        if scheduled_utc is not None
                        else None
                    ),
                    "planned_payload": yt_meta,
                }
            print(
                json.dumps(
                    {"status": "dry_run", "results": planned},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        results: dict[str, dict] = {}
        errors: dict[str, str] = {}

        if "fb" in platforms and fb_creds is not None:
            try:
                results["fb"] = upload_facebook(
                    video_path=video_path,
                    page_id=fb_creds[0],
                    page_token=fb_creds[1],
                    title=args.title.strip(),
                    description=args.description,
                    scheduled_utc=scheduled_utc,
                    secret_vals=secret_vals,
                )
            except Exception as exc:
                errors["fb"] = redact_secrets(str(exc), secret_vals)

        if "yt" in platforms and yt_creds is not None:
            try:
                token_path, token_data, client_id, client_secret = yt_creds
                access_token = refresh_yt_access_token(
                    token_path, token_data, client_id, client_secret, secret_vals
                )
                yt_meta = build_yt_metadata(
                    args.title.strip(),
                    args.description,
                    tags_list,
                    args.privacy,
                    scheduled_utc,
                )
                results["yt"] = upload_youtube(
                    video_path=video_path,
                    metadata=yt_meta,
                    access_token=access_token,
                    scheduled_utc=scheduled_utc,
                    secret_vals=secret_vals,
                )
            except Exception as exc:
                errors["yt"] = redact_secrets(str(exc), secret_vals)

        output = {
            "status": "ok" if not errors else "error",
            "results": results,
        }
        if errors:
            output["errors"] = errors
            print(json.dumps(output, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1

        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": redact_secrets(str(exc), secret_vals),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
