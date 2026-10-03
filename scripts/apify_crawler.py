#!/usr/bin/env python3
"""
Apify Social Media Crawler for Antigravity Harness Hub.

Supports scraping public data from Twitter/X, Facebook, and Instagram via Apify API actors:
- Twitter: apidojo/tweet-scraper or vdrmmr/twitter-scraper
- Facebook: apify/facebook-posts-scraper
- Instagram: apify/instagram-scraper
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Đảm bảo hỗ trợ UTF-8 trơn tru trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def load_env():
    """Load APIFY_API_TOKEN from os.environ or .env file."""
    # Check environment variable first
    token = os.environ.get("APIFY_API_TOKEN")
    if token:
        return token.strip()

    # Try importing dotenv if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        token = os.environ.get("APIFY_API_TOKEN")
        if token:
            return token.strip()
    except ImportError:
        pass

    # Fallback: Search for .env in current and parent directories
    search_dirs = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
    ]

    for directory in search_dirs:
        env_path = directory / ".env"
        if env_path.is_file():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            if key.strip() == "APIFY_API_TOKEN":
                                val = val.strip().strip("'\"")
                                os.environ["APIFY_API_TOKEN"] = val
                                return val
            except Exception:
                pass

    return None


def normalize_actor_id(actor_id: str) -> str:
    """Normalize actor ID to Apify URL format (replace '/' with '~')."""
    return actor_id.strip().replace("/", "~")


def build_actor_payload(platform: str, query: str, limit: int, custom_actor: str = None) -> tuple[str, dict]:
    """
    Build the appropriate actor ID and input payload based on platform and query.
    """
    platform = platform.lower()

    if platform in ("twitter", "x"):
        actor = custom_actor or "apidojo~tweet-scraper"
        actor = normalize_actor_id(actor)

        # Build payload for apidojo/tweet-scraper
        is_url = query.startswith("http://") or query.startswith("https://") or "twitter.com" in query or "x.com" in query
        if is_url:
            payload = {
                "startUrls": [query],
                "maxItems": limit,
                "sort": "Latest"
            }
        else:
            payload = {
                "searchTerms": [query],
                "maxItems": limit,
                "sort": "Latest"
            }
        return actor, payload

    elif platform in ("facebook", "fb"):
        actor = custom_actor or "apify~facebook-posts-scraper"
        actor = normalize_actor_id(actor)

        is_url = query.startswith("http://") or query.startswith("https://") or "facebook.com" in query
        if is_url:
            target_url = query
        else:
            # Query is keyword / phrase -> generate search URL
            target_url = f"https://www.facebook.com/search/posts/?q={urllib.parse.quote(query)}"

        payload = {
            "startUrls": [{"url": target_url}],
            "resultsLimit": limit,
            "captionText": True
        }
        return actor, payload

    elif platform in ("instagram", "ig"):
        actor = custom_actor or "apify~instagram-scraper"
        actor = normalize_actor_id(actor)

        is_url = query.startswith("http://") or query.startswith("https://") or "instagram.com" in query
        if is_url:
            payload = {
                "directUrls": [query],
                "resultsType": "posts",
                "resultsLimit": limit
            }
        elif query.startswith("#"):
            payload = {
                "search": query,
                "searchType": "hashtag",
                "resultsType": "posts",
                "resultsLimit": limit,
                "searchLimit": limit
            }
        elif query.startswith("@"):
            clean_user = query.lstrip("@")
            payload = {
                "directUrls": [f"https://www.instagram.com/{clean_user}/"],
                "resultsType": "posts",
                "resultsLimit": limit
            }
        else:
            payload = {
                "search": query,
                "searchType": "hashtag",
                "resultsType": "posts",
                "resultsLimit": limit,
                "searchLimit": limit
            }
        return actor, payload

    elif platform == "custom":
        if not custom_actor:
            raise ValueError("Cần chỉ định --actor cho chế độ custom.")
        actor = normalize_actor_id(custom_actor)
        payload = {
            "query": query,
            "limit": limit
        }
        return actor, payload

    else:
        raise ValueError(f"Nền tảng không hỗ trợ: {platform}. Chọn: twitter, facebook, instagram.")


def run_apify_actor(actor_id: str, payload: dict, token: str, timeout: int = 180) -> list | dict:
    """
    Run Apify actor synchronously and return dataset items.
    Endpoint: https://api.apify.com/v2/acts/{actorId}/run-sync-get-dataset-items?token={token}&timeout={timeout}
    """
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={token}&timeout={timeout}"
    data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Antigravity-Harness-Hub/1.0",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw_body = resp.read().decode("utf-8")
            if "application/json" in content_type or raw_body.strip().startswith(("{", "[")):
                return json.loads(raw_body)
            return {"raw_output": raw_body}
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        msg = f"[LỖI APIFY] HTTP {e.code}: {e.reason}"
        if error_body:
            try:
                err_json = json.loads(error_body)
                if "error" in err_json and "message" in err_json["error"]:
                    msg += f" - {err_json['error']['message']}"
                else:
                    msg += f" - {error_body[:200]}"
            except Exception:
                msg += f" - {error_body[:200]}"
        raise RuntimeError(msg) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"[LỖI KẾT NỐI] Không thể kết nối tới Apify: {e.reason}") from e
    except TimeoutError:
        raise RuntimeError(f"[LỖI TIMEOUT] Quá thời gian chờ ({timeout}s) khi chạy actor {actor_id}.")


def main():
    parser = argparse.ArgumentParser(
        description="Apify Social Media Crawler - Trinh sát dữ liệu mạng xã hội cho Antigravity Harness Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ví dụ sử dụng:
  python scripts/apify_crawler.py twitter --query "bất động sản" --limit 10
  python scripts/apify_crawler.py facebook --query "chứng khoán phái sinh" --limit 5
  python scripts/apify_crawler.py instagram --query "#taichinh" --limit 10 --output out.json
"""
    )

    parser.add_argument(
        "platform",
        choices=["twitter", "x", "facebook", "fb", "instagram", "ig", "custom"],
        help="Nền tảng mạng xã hội cần cào dữ liệu (twitter, facebook, instagram, custom)"
    )
    parser.add_argument(
        "-q", "--query",
        required=True,
        help="Từ khóa tìm kiếm, hashtag, username hoặc URL bài viết/trang"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=10,
        help="Số lượng kết quả tối đa cần lấy (mặc định: 10)"
    )
    parser.add_argument(
        "-a", "--actor",
        help="Ghi đè Apify Actor ID (ví dụ: apidojo/tweet-scraper, vdrmmr/twitter-scraper)"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=180,
        help="Thời gian timeout tối đa tính bằng giây (mặc định: 180s)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Đường dẫn file để ghi kết quả JSON (nếu không cung cấp, in ra stdout)"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="In JSON dạng compact (không thụt dòng)"
    )

    args = parser.parse_args()

    # 1. Load token
    token = load_env()
    if not token:
        sys.stderr.write(
            "[LỖI XÁC THỰC] Không tìm thấy APIFY_API_TOKEN trong biến môi trường hoặc file .env.\n"
            "Vui lòng thiết lập biến môi trường APIFY_API_TOKEN hoặc cấu hình trong file .env tại thư mục gốc.\n"
        )
        sys.exit(1)

    # 2. Build payload & actor
    try:
        actor_id, payload = build_actor_payload(
            platform=args.platform,
            query=args.query,
            limit=args.limit,
            custom_actor=args.actor
        )
    except ValueError as ve:
        sys.stderr.write(f"[LỖI THAM SỐ] {ve}\n")
        sys.exit(2)

    sys.stderr.write(f"[*] Đang thực thi Apify Actor: {actor_id}\n")
    sys.stderr.write(f"[*] Tham số: platform={args.platform}, query='{args.query}', limit={args.limit}\n")

    # 3. Call Apify API
    try:
        results = run_apify_actor(
            actor_id=actor_id,
            payload=payload,
            token=token,
            timeout=args.timeout
        )
    except Exception as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(3)

    # 4. Output results
    indent = None if args.compact else 2
    json_str = json.dumps(results, ensure_ascii=False, indent=indent)

    if args.output:
        try:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            item_count = len(results) if isinstance(results, list) else 1
            sys.stderr.write(f"[OK] Đã lưu {item_count} bản ghi vào: {out_path.resolve()}\n")
        except Exception as e:
            sys.stderr.write(f"[LỖI GHI FILE] Không thể lưu file '{args.output}': {e}\n")
            sys.exit(4)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
