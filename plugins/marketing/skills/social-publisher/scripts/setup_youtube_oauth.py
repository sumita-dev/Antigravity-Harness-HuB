#!/usr/bin/env python3
"""Setup YouTube OAuth 2.0 credentials via local callback (stdlib only)."""

from __future__ import annotations

import argparse
import html
import json
import os
import secrets as py_secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 8765
REDIRECT_PATH = "/callback"
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}{REDIRECT_PATH}"
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


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


def http_post_form(url: str, data: dict[str, str], secret_vals: list[str]) -> dict:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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


def http_get_json_bearer(url: str, access_token: str, secret_vals: list[str]) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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


def wait_for_oauth_callback(expected_state: str, timeout_sec: int = 300) -> str:
    result: dict[str, str | None] = {"code": None, "error": None}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != REDIRECT_PATH:
                self.send_response(404)
                self.end_headers()
                return

            params = urllib.parse.parse_qs(parsed.query)
            state = params.get("state", [""])[0]
            error = params.get("error", [""])[0]
            code = params.get("code", [""])[0]

            if state != expected_state:
                result["error"] = "CSRF state mismatch in OAuth callback."
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Invalid OAuth state</h1>")
                return

            if error:
                result["error"] = f"OAuth authorization failed: {error}"
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                safe_err = html.escape(error).encode("utf-8")
                self.wfile.write(b"<h1>Authorization failed: " + safe_err + b"</h1>")
                return

            if not code:
                result["error"] = "Missing authorization code in callback."
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Missing authorization code</h1>")
                return

            result["code"] = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<h1>YouTube OAuth completed</h1><p>You may close this window.</p>"
            )

    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), CallbackHandler)
    server.timeout = timeout_sec
    try:
        while result["code"] is None and result["error"] is None:
            server.handle_request()
    finally:
        server.server_close()

    if result["error"]:
        raise RuntimeError(result["error"])
    if not result["code"]:
        raise RuntimeError("OAuth callback timed out without authorization code.")
    return result["code"]


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Run local OAuth 2.0 flow for YouTube Data API v3."
    )
    parser.add_argument(
        "--config-dir",
        default=os.getcwd(),
        help="Directory containing .env and output youtube_token.json (default: cwd).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open browser; print auth URL only.",
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir).resolve()
    env_map = load_env_file(config_dir / ".env")

    channel_id = get_setting("YOUTUBE_CHANNEL_ID", env_map)
    client_id = get_setting("YOUTUBE_CLIENT_ID", env_map)
    client_secret = get_setting("YOUTUBE_CLIENT_SECRET", env_map)

    missing = [
        name
        for name, val in (
            ("YOUTUBE_CHANNEL_ID", channel_id),
            ("YOUTUBE_CLIENT_ID", client_id),
            ("YOUTUBE_CLIENT_SECRET", client_secret),
        )
        if not val
    ]
    if missing:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": f"Missing required configuration: {', '.join(missing)}",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    secret_vals = [client_secret]
    state = py_secrets.token_urlsafe(24)

    auth_query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    auth_url = f"{OAUTH_AUTH_URL}?{auth_query}"
    print(f"Open this URL to authorize YouTube access:\n{auth_url}", flush=True)
    if not args.no_browser:
        webbrowser.open(auth_url)

    try:
        code = wait_for_oauth_callback(state)
        secret_vals.append(code)

        token_data = http_post_form(
            OAUTH_TOKEN_URL,
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            secret_vals,
        )
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        if not access_token or not refresh_token:
            raise RuntimeError(
                "OAuth token response missing access_token or refresh_token."
            )
        secret_vals.extend([access_token, refresh_token])

        channels_url = f"{YT_CHANNELS_URL}?part=id,snippet&mine=true"
        channels_resp = http_get_json_bearer(channels_url, access_token, secret_vals)
        items = channels_resp.get("items", [])
        matched = next((c for c in items if c.get("id") == channel_id), None)
        if not matched:
            found_ids = [c.get("id", "") for c in items]
            raise RuntimeError(
                f"Authenticated channel {found_ids} does not match YOUTUBE_CHANNEL_ID={channel_id}."
            )

        now = datetime.now(timezone.utc)
        expires_in = int(token_data.get("expires_in", 3600))
        expires_at = (now + timedelta(seconds=expires_in)).isoformat()
        channel_title = matched.get("snippet", {}).get("title", "")

        config_dir.mkdir(parents=True, exist_ok=True)
        token_path = config_dir / "youtube_token.json"
        saved_payload = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", " ".join(SCOPES)),
            "expires_in": expires_in,
            "expires_at": expires_at,
            "channel_id": channel_id,
            "channel_title": channel_title,
            "updated_at": now.isoformat(),
        }
        token_path.write_text(
            json.dumps(saved_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        print(
            json.dumps(
                {
                    "status": "ok",
                    "token_file": str(token_path),
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
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
