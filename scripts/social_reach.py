#!/usr/bin/env python3
"""Social Reach Adapter CLI & Library.

Tầng thu thập nâng cao cho SubAgent Web Researcher:
- Tích hợp Agent Reach, xreach, yt-dlp, và Jina Reader.
- Tự động bóc tách và che giấu token/cookie nhạy cảm (Zero Token Leak).
- Cơ chế Graceful Fallback khi chưa cài CLI hoặc mạng offline.
- Chế độ kiểm tra sức khỏe hệ thống: --platform doctor.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Đảm bảo UTF-8 trơn tru trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Pattern nhận diện key nhạy cảm trong dict/json
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(token|secret|authorization|cookie|ct0|sessionid|auth_token|key|password|credential)"
)

# Pattern nhận diện token/cookie nhạy cảm trong chuỗi văn bản
SENSITIVE_TEXT_PATTERNS = [
    # auth_token=xyz hoặc auth_token: xyz
    (re.compile(r"(?i)(auth_token\s*[:=]\s*['\"]?)([^\s;&\"']+)(['\"]?)"), r"\1[REDACTED]\3"),
    # ct0=xyz
    (re.compile(r"(?i)(ct0\s*[:=]\s*['\"]?)([^\s;&\"']+)(['\"]?)"), r"\1[REDACTED]\3"),
    # sessionid=xyz
    (re.compile(r"(?i)(sessionid\s*[:=]\s*['\"]?)([^\s;&\"']+)(['\"]?)"), r"\1[REDACTED]\3"),
    # cookie: xyz hoặc cookie=xyz
    (re.compile(r"(?i)(cookie\s*[:=]\s*['\"]?)([^\r\n\"';]+)(['\"]?)"), r"\1[REDACTED]\3"),
    # api_key hoặc apikey hoặc key=xyz
    (re.compile(r"(?i)((?:api[_-]?)?key\s*[:=]\s*['\"]?)([^\s;&\"']+)(['\"]?)"), r"\1[REDACTED]\3"),
    # access_token hoặc token=xyz
    (re.compile(r"(?i)((?:access[_-]?)?token\s*[:=]\s*['\"]?)([^\s;&\"']+)(['\"]?)"), r"\1[REDACTED]\3"),
    # Bearer xyz
    (re.compile(r"(?i)(bearer\s+)([^\s;&\"']+)"), r"\1[REDACTED]"),
]

ENV_SECRETS_KEYS = (
    "TWITTER_AUTH_TOKEN",
    "AUTH_TOKEN",
    "CT0",
    "TWITTER_CT0",
    "FB_PAGE_ACCESS_TOKEN",
    "APIFY_API_TOKEN",
)


def redact_sensitive_data(value: Any) -> Any:
    """Bóc tách và che giấu các token, cookie, sessionid và credentials nhạy cảm."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            # Không redact hoàn toàn dict mô tả metadata/diagnostic, mà duyệt đệ quy bên trong
            is_diagnostic_container = key_str.lower() in ("cookie_storage", "cookie_dir", "cookie_path")
            if not is_diagnostic_container and SENSITIVE_KEY_PATTERN.search(key_str):
                result[key_str] = "[REDACTED]"
            else:
                result[key_str] = redact_sensitive_data(v)
        return result

    if isinstance(value, (list, tuple, set)):
        items = [redact_sensitive_data(item) for item in value]
        return type(value)(items) if not isinstance(value, set) else set(items)

    if isinstance(value, str):
        text = value
        for env_key in ENV_SECRETS_KEYS:
            env_val = os.environ.get(env_key, "").strip()
            if env_val and len(env_val) >= 4:
                text = text.replace(env_val, "[REDACTED]")

        for pattern, repl in SENSITIVE_TEXT_PATTERNS:
            text = pattern.sub(repl, text)
        return text

    return value


def check_doctor() -> dict[str, Any]:
    """Kiểm tra sự hiện diện của các công cụ và trả về báo cáo trạng thái."""
    agent_reach_bin = shutil.which("agent-reach")
    xreach_bin = shutil.which("xreach")
    yt_dlp_bin = shutil.which("yt-dlp")

    cookie_dir = Path.home() / ".agent-reach"
    cookie_store_present = cookie_dir.is_dir()

    platforms = {
        "twitter": {
            "ready": bool(agent_reach_bin or xreach_bin),
            "engine": "agent-reach" if agent_reach_bin else ("xreach" if xreach_bin else None),
            "fallback_suggested": "Google Dorking: site:x.com or site:twitter.com via search_web",
        },
        "reddit": {
            "ready": bool(agent_reach_bin),
            "engine": "agent-reach" if agent_reach_bin else None,
            "fallback_suggested": "Google Dorking: site:reddit.com via search_web",
        },
        "youtube": {
            "ready": bool(yt_dlp_bin or agent_reach_bin),
            "engine": "yt-dlp" if yt_dlp_bin else ("agent-reach" if agent_reach_bin else None),
            "fallback_suggested": "yt-competitor-analyzer skill or Google Search",
        },
        "web": {
            "ready": True,
            "engine": "jina-reader-http-fallback",
            "fallback_suggested": "Urllib HTTP GET to https://r.jina.ai/<url>",
        },
        "jina": {
            "ready": True,
            "engine": "jina-reader-http-fallback",
            "fallback_suggested": "Urllib HTTP GET to https://r.jina.ai/<url>",
        },
    }

    return {
        "status": "ok",
        "doctor": True,
        "binaries": {
            "agent-reach": agent_reach_bin,
            "xreach": xreach_bin,
            "yt-dlp": yt_dlp_bin,
        },
        "cookie_storage": {
            "path": str(cookie_dir),
            "exists": cookie_store_present,
            "recommendation": "Always use clone/secondary accounts for session cookies",
        },
        "platforms": platforms,
    }


def fetch_jina_fallback(url: str = "", query: str = "", timeout: int = 30) -> dict[str, Any]:
    """Fallback gọi Jina Reader bằng HTTP GET qua thư viện chuẩn urllib."""
    if not url and not query:
        return {
            "status": "unavailable",
            "platform": "jina",
            "limitations": "Agent-Reach CLI not installed or platform offline (missing --url or --query)",
            "fallback_suggested": "Provide a valid --url or --query",
        }

    if url:
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url
        target = f"https://r.jina.ai/{clean_url}"
    else:
        target = f"https://s.jina.ai/{urllib.parse.quote(query)}"

    req = urllib.request.Request(
        target,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Antigravity-SocialReach/1.0",
            "Accept": "text/plain, application/json, */*",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            return {
                "status": "success",
                "platform": "jina",
                "target_url": target,
                "content_preview": content[:1000],
                "content_length": len(content),
            }
    except Exception as exc:
        return {
            "status": "unavailable",
            "platform": "jina",
            "limitations": f"Network error during Jina fetch: {exc}",
            "fallback_suggested": "Use search_web or read_url_content native tools",
        }


def run_reach(
    platform: str,
    query: str = "",
    url: str = "",
    timeout: int = 30,
) -> dict[str, Any]:
    """Thực thi tác vụ thu thập theo platform chỉ định."""
    if platform == "doctor":
        return check_doctor()

    if platform in ("jina", "web"):
        # Ưu tiên agent-reach nếu có, ngược lại fallback HTTP Jina
        agent_reach_bin = shutil.which("agent-reach")
        if agent_reach_bin and url:
            try:
                proc = subprocess.run(
                    [agent_reach_bin, "web", url],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
                if proc.returncode == 0:
                    return {
                        "status": "success",
                        "platform": platform,
                        "url": url,
                        "output": proc.stdout[:2000],
                    }
            except Exception:
                pass
        return fetch_jina_fallback(url=url, query=query, timeout=timeout)

    if platform == "twitter":
        agent_reach_bin = shutil.which("agent-reach")
        xreach_bin = shutil.which("xreach")
        cmd = None
        if agent_reach_bin:
            cmd = [agent_reach_bin, "twitter"] + ([query] if query else ([url] if url else []))
        elif xreach_bin:
            cmd = [xreach_bin] + ([query] if query else ([url] if url else []))

        if cmd:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
                return {
                    "status": "success" if proc.returncode == 0 else "error",
                    "platform": "twitter",
                    "exit_code": proc.returncode,
                    "output": proc.stdout or proc.stderr,
                }
            except Exception as exc:
                return {
                    "status": "unavailable",
                    "platform": "twitter",
                    "limitations": f"Execution error: {exc}",
                    "fallback_suggested": "Use Google Dorking: site:x.com or site:twitter.com via search_web",
                }

        return {
            "status": "unavailable",
            "platform": "twitter",
            "limitations": "Agent-Reach CLI not installed or platform offline",
            "fallback_suggested": "Use Google Dorking: site:x.com or site:twitter.com via search_web",
        }

    if platform == "reddit":
        agent_reach_bin = shutil.which("agent-reach")
        if agent_reach_bin:
            try:
                cmd = [agent_reach_bin, "reddit"] + ([query] if query else ([url] if url else []))
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
                return {
                    "status": "success" if proc.returncode == 0 else "error",
                    "platform": "reddit",
                    "exit_code": proc.returncode,
                    "output": proc.stdout or proc.stderr,
                }
            except Exception as exc:
                return {
                    "status": "unavailable",
                    "platform": "reddit",
                    "limitations": f"Execution error: {exc}",
                    "fallback_suggested": "Use Google Dorking: site:reddit.com via search_web",
                }

        return {
            "status": "unavailable",
            "platform": "reddit",
            "limitations": "Agent-Reach CLI not installed or platform offline",
            "fallback_suggested": "Use Google Dorking: site:reddit.com via search_web",
        }

    if platform == "youtube":
        yt_dlp_bin = shutil.which("yt-dlp")
        agent_reach_bin = shutil.which("agent-reach")
        cmd = None
        if yt_dlp_bin and url:
            cmd = [yt_dlp_bin, "--dump-json", "--skip-download", url]
        elif agent_reach_bin:
            cmd = [agent_reach_bin, "youtube"] + ([query] if query else ([url] if url else []))

        if cmd:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
                return {
                    "status": "success" if proc.returncode == 0 else "error",
                    "platform": "youtube",
                    "exit_code": proc.returncode,
                    "output": proc.stdout or proc.stderr,
                }
            except Exception as exc:
                return {
                    "status": "unavailable",
                    "platform": "youtube",
                    "limitations": f"Execution error: {exc}",
                    "fallback_suggested": "Use yt-competitor-analyzer skill or Google Search",
                }

        return {
            "status": "unavailable",
            "platform": "youtube",
            "limitations": "Agent-Reach CLI not installed or platform offline",
            "fallback_suggested": "Install yt-dlp or use search_web / yt-competitor-analyzer skill",
        }

    return {
        "status": "unavailable",
        "platform": platform,
        "limitations": f"Unsupported platform: {platform}",
        "fallback_suggested": "Use search_web native tool",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Social Reach Adapter - Tầng thu thập dữ liệu mạng xã hội & web"
    )
    parser.add_argument(
        "--platform",
        choices=["twitter", "reddit", "youtube", "web", "jina", "doctor"],
        default="doctor",
        help="Nền tảng mục tiêu cần thu thập hoặc kiểm tra (mặc định: doctor)",
    )
    parser.add_argument("--query", type=str, default="", help="Từ khóa tìm kiếm")
    parser.add_argument("--url", type=str, default="", help="Đường dẫn URL bài viết/trang web")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới định dạng JSON",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Thời gian chờ tối đa bằng giây (mặc định: 30)",
    )

    args = parser.parse_args(argv)

    raw_result = run_reach(
        platform=args.platform,
        query=args.query,
        url=args.url,
        timeout=args.timeout,
    )

    clean_result = redact_sensitive_data(raw_result)

    # Nếu có cờ --json hoặc kết quả là doctor / unavailable, xuất JSON chuẩn
    if args.json or args.platform == "doctor" or clean_result.get("status") == "unavailable":
        sys.stdout.write(json.dumps(clean_result, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(json.dumps(clean_result, ensure_ascii=False, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
