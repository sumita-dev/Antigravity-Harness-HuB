#!/usr/bin/env python3
"""Setup Facebook long-lived user token and Page tokens (stdlib only)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


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


def get_setting(key: str, env_map: dict[str, str], override: str | None = None) -> str:
    if override:
        return override.strip()
    env_val = os.environ.get(key, "").strip()
    if env_val:
        return env_val
    return env_map.get(key, "").strip()


def redact_secrets(text: str, secrets: list[str]) -> str:
    masked = text
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "[REDACTED]")
    return masked


def http_get_json(url: str, secrets: list[str]) -> dict:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code}: {redact_secrets(body, secrets)}"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error: {redact_secrets(str(exc.reason), secrets)}"
        ) from None


def update_env_if_missing(env_path: Path, page_id: str, page_token: str) -> bool:
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    existing_vals = load_env_file(env_path)
    need_page_id = not existing_vals.get("FB_PAGE_ID", "").strip()
    need_page_token = not existing_vals.get("FB_PAGE_ACCESS_TOKEN", "").strip()

    if not need_page_id and not need_page_token:
        return False

    updated_id = False
    updated_token = False
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("FB_PAGE_ID=") and need_page_id and not updated_id:
            new_lines.append(f"FB_PAGE_ID={page_id}")
            updated_id = True
        elif (
            stripped.startswith("FB_PAGE_ACCESS_TOKEN=")
            and need_page_token
            and not updated_token
        ):
            new_lines.append(f"FB_PAGE_ACCESS_TOKEN={page_token}")
            updated_token = True
        else:
            new_lines.append(line)

    if need_page_id and not updated_id:
        new_lines.append(f"FB_PAGE_ID={page_id}")
    if need_page_token and not updated_token:
        new_lines.append(f"FB_PAGE_ACCESS_TOKEN={page_token}")

    content = "\n".join(new_lines) + ("\n" if new_lines else "")
    env_path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Exchange Facebook short-lived token for long-lived user & page tokens."
    )
    parser.add_argument(
        "--config-dir",
        default=os.getcwd(),
        help="Directory containing .env and output fb_tokens.json (default: cwd).",
    )
    parser.add_argument(
        "--short-token",
        default=None,
        help="Optional short-lived user token (overrides FB_SHORT_TOKEN env/.env).",
    )
    args = parser.parse_args()

    config_dir = Path(args.config_dir).resolve()
    env_path = config_dir / ".env"
    env_map = load_env_file(env_path)

    app_id = get_setting("FB_APP_ID", env_map)
    app_secret = get_setting("FB_APP_SECRET", env_map)
    short_token = get_setting("FB_SHORT_TOKEN", env_map, args.short_token)

    missing = [
        name
        for name, val in (
            ("FB_APP_ID", app_id),
            ("FB_APP_SECRET", app_secret),
            ("FB_SHORT_TOKEN", short_token),
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

    secrets = [app_secret, short_token]

    try:
        exchange_query = urllib.parse.urlencode(
            {
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            }
        )
        exchange_url = f"{GRAPH_BASE}/oauth/access_token?{exchange_query}"
        user_token_data = http_get_json(exchange_url, secrets)
        long_user_token = user_token_data.get("access_token", "")
        if not long_user_token:
            raise RuntimeError("Graph API did not return access_token.")
        secrets.append(long_user_token)

        pages: list[dict] = []
        accounts_query = urllib.parse.urlencode(
            {
                "fields": "id,name,access_token,category",
                "limit": "100",
                "access_token": long_user_token,
            }
        )
        next_url: str | None = f"{GRAPH_BASE}/me/accounts?{accounts_query}"
        while next_url:
            page_resp = http_get_json(next_url, secrets)
            for item in page_resp.get("data", []):
                page_tok = item.get("access_token", "")
                if page_tok:
                    secrets.append(page_tok)
                pages.append(
                    {
                        "id": item.get("id", ""),
                        "name": item.get("name", ""),
                        "category": item.get("category", ""),
                        "access_token": page_tok,
                    }
                )
            next_url = page_resp.get("paging", {}).get("next")

        config_dir.mkdir(parents=True, exist_ok=True)
        tokens_path = config_dir / "fb_tokens.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "graph_version": GRAPH_VERSION,
            "user_token": {
                "access_token": long_user_token,
                "token_type": user_token_data.get("token_type", "bearer"),
                "expires_in": user_token_data.get("expires_in"),
            },
            "pages": pages,
        }
        tokens_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        env_updated = False
        if pages:
            first_page = pages[0]
            if first_page.get("id") and first_page.get("access_token"):
                env_updated = update_env_if_missing(
                    env_path, first_page["id"], first_page["access_token"]
                )

        summary = {
            "status": "ok",
            "tokens_file": str(tokens_path),
            "pages_count": len(pages),
            "pages": [{"id": p["id"], "name": p["name"]} for p in pages],
            "env_updated": env_updated,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": redact_secrets(str(exc), secrets),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
