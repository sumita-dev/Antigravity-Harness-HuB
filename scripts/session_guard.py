#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/session_guard.py

Cỗ Máy Giám Sát Phiên Làm Việc & Tự Động Handoff (Session Rollover Guard).
Giám sát dung lượng transcript và số turns để phát hiện nguy cơ quá tải context window,
tự động kết xuất biên bản bàn giao _session-handoff.md khi chạm ngưỡng ngắt mạch.

Quy Chuẩn Ngưỡng:
- 🟢 GREEN:  <= 200 KB và <= 35 turns. Trạng thái an toàn.
- 🟡 YELLOW: > 200 KB hoặc > 35 turns. Cảnh báo sớm, chuẩn bị hoàn tất task.
- 🔴 RED:    > 250 KB hoặc > 40 turns. Ngắt mạch bắt buộc, kích hoạt Session Rollover.

CLI:
  python scripts/session_guard.py [--check] [--auto-handoff] [--transcript PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ngưỡng dung lượng và số turns theo quy chuẩn
YELLOW_THRESHOLD_BYTES = 200 * 1024  # 204,800 bytes (200 KB)
YELLOW_THRESHOLD_TURNS = 35
RED_THRESHOLD_BYTES = 250 * 1024     # 256,000 bytes (250 KB)
RED_THRESHOLD_TURNS = 40

DEFAULT_OBSIDIAN_VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH") or os.environ.get("SECOND_BRAIN_PATH") or (Path.home() / "Obsidian"))
DEFAULT_HANDOFF_PATH = DEFAULT_OBSIDIAN_VAULT / "wiki" / "_session-handoff.md"


def find_active_transcript(repo_root: Optional[Path] = None) -> Optional[Path]:
    """Tự động dò tìm file transcript hoạt động gần nhất."""
    root = repo_root or REPO_ROOT

    # 1. Kiểm tra biến môi trường
    env_transcript = os.environ.get("ANTIGRAVITY_TRANSCRIPT")
    if env_transcript and Path(env_transcript).is_file():
        return Path(env_transcript).resolve()

    # 2. Kiểm tra thư mục AppData Antigravity
    app_data_candidates = []
    custom_app_data = os.environ.get("ANTIGRAVITY_APP_DATA_DIR")
    if custom_app_data:
        app_data_candidates.append(Path(custom_app_data))
    app_data_candidates.append(Path.home() / ".gemini" / "antigravity")

    for app_data in app_data_candidates:
        brain_dir = app_data / "brain"
        if brain_dir.is_dir():
            # Tìm transcript.jsonl mới nhất
            transcripts = list(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
            if not transcripts:
                transcripts = list(brain_dir.glob("**/transcript*.jsonl"))
            if transcripts:
                transcripts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return transcripts[0].resolve()

    # 3. Kiểm tra trong .sessions/ hoặc .brain/ của repo
    repo_sessions = root / ".sessions"
    if repo_sessions.is_dir():
        files = list(repo_sessions.glob("**/*.jsonl"))
        if files:
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return files[0].resolve()

    repo_brain = root / ".brain"
    if repo_brain.is_dir():
        files = list(repo_brain.glob("**/*.jsonl"))
        if files:
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return files[0].resolve()

    return None


def count_transcript_turns(transcript_path: Path) -> Tuple[int, int]:
    """Đếm số bước (steps) và số lượt hội thoại (turns) từ file JSONL.
    
    Returns:
        (total_steps, user_turns)
    """
    total_steps = 0
    user_turns = 0
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                total_steps += 1
                try:
                    data = json.loads(stripped)
                    source = data.get("source", "")
                    step_type = data.get("type", "")
                    if source == "USER_EXPLICIT" or step_type == "USER_INPUT":
                        user_turns += 1
                except Exception:
                    pass
    except Exception:
        pass
    return total_steps, user_turns


def evaluate_session_health(
    size_bytes: int,
    turns: int,
) -> Tuple[str, str]:
    """Đánh giá trạng thái sức khỏe phiên làm việc theo ngưỡng chuẩn.
    
    Returns:
        (status, reason_message)
    """
    if size_bytes > RED_THRESHOLD_BYTES or turns > RED_THRESHOLD_TURNS:
        reasons = []
        if size_bytes > RED_THRESHOLD_BYTES:
            reasons.append(f"Dung lượng transcript ({size_bytes / 1024:.1f} KB) vượt trần RED {RED_THRESHOLD_BYTES / 1024:.0f} KB")
        if turns > RED_THRESHOLD_TURNS:
            reasons.append(f"Số turns ({turns}) vượt trần RED {RED_THRESHOLD_TURNS} turns")
        return "RED", "; ".join(reasons)

    if size_bytes > YELLOW_THRESHOLD_BYTES or turns > YELLOW_THRESHOLD_TURNS:
        reasons = []
        if size_bytes > YELLOW_THRESHOLD_BYTES:
            reasons.append(f"Dung lượng transcript ({size_bytes / 1024:.1f} KB) vượt ngưỡng YELLOW {YELLOW_THRESHOLD_BYTES / 1024:.0f} KB")
        if turns > YELLOW_THRESHOLD_TURNS:
            reasons.append(f"Số turns ({turns}) vượt ngưỡng YELLOW {YELLOW_THRESHOLD_TURNS} turns")
        return "YELLOW", "; ".join(reasons)

    return "GREEN", f"Phiên làm việc an toàn ({size_bytes / 1024:.1f} KB, {turns} turns)"


def generate_handoff_content(
    transcript_info: Dict[str, Any],
    goal: str = "Tự động kích hoạt do chạm ngưỡng ngắt mạch Session Rollover",
    summary: str = "Transcript chạm ngưỡng cảnh báo, cần lưu trữ ngữ cảnh và mở phiên mới.",
) -> str:
    """Tạo nội dung bàn giao chuẩn cho _session-handoff.md."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    size_kb = transcript_info.get("size_bytes", 0) / 1024.0
    turns = transcript_info.get("turns", 0)
    transcript_path = transcript_info.get("transcript_path", "N/A")

    content = f"""# Session Handoff [{today}]
- **Mục tiêu**: {goal}
- **Đã hoàn thành**: Ghi nhận toàn bộ tiến trình trước khi rollover ({size_kb:.1f} KB, {turns} turns).
- **Đang xử lý**: {summary}
- **Quyết định đã chốt**: Kích hoạt Session Rollover Gate theo GEMINI.md Điều 1.13; ngắt mạch phiên và bàn giao sang phiên mới.
- **Các bước tiếp theo**: Khởi tạo phiên mới, nạp lại bối cảnh từ Obsidian Vault wiki/_session-handoff.md và tiếp tục nhiệm vụ.
- **File liên quan**: `{transcript_path}`
- **Status**: active
"""
    return content


def write_handoff_file(
    content: str,
    target_path: Optional[Path] = None,
) -> Optional[Path]:
    """Ghi nội dung bàn giao vào file _session-handoff.md."""
    dest = target_path or DEFAULT_HANDOFF_PATH

    # Kiểm tra xem thư mục đích hoặc thư mục cha có thể tạo được không
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        return dest
    except Exception as exc:
        # Fallback về repo local nếu không ghi được vào Obsidian Vault
        fallback = REPO_ROOT / ".brain" / "_session-handoff.md"
        try:
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text(content, encoding="utf-8")
            return fallback
        except Exception:
            return None


def check_session(
    transcript_path: Optional[Path] = None,
    auto_handoff: bool = False,
    handoff_dest: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Kiểm tra sức khỏe phiên làm việc và thực hiện auto-handoff nếu cần."""
    resolved_path = transcript_path or find_active_transcript(repo_root)

    if not resolved_path or not resolved_path.is_file():
        return {
            "status": "GREEN",
            "message": "Không tìm thấy file transcript hoạt động (coi như phiên mới/sạch).",
            "size_bytes": 0,
            "turns": 0,
            "total_steps": 0,
            "transcript_path": None,
            "handoff_written": None,
        }

    size_bytes = resolved_path.stat().st_size
    total_steps, user_turns = count_transcript_turns(resolved_path)
    # Turns tính theo số lượt turns thực tế hoặc steps nếu ít user_turns
    turns = max(user_turns, total_steps)

    status, message = evaluate_session_health(size_bytes, turns)

    handoff_written = None
    if auto_handoff and status == "RED":
        info = {
            "size_bytes": size_bytes,
            "turns": turns,
            "total_steps": total_steps,
            "transcript_path": str(resolved_path),
            "status": status,
        }
        content = generate_handoff_content(info)
        written_path = write_handoff_file(content, handoff_dest)
        if written_path:
            handoff_written = str(written_path)

    return {
        "status": status,
        "message": message,
        "size_bytes": size_bytes,
        "turns": turns,
        "total_steps": total_steps,
        "transcript_path": str(resolved_path),
        "handoff_written": handoff_written,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Session Rollover Guard")
    parser.add_argument("--check", action="store_true", default=True, help="Kiểm tra trạng thái phiên làm việc")
    parser.add_argument("--auto-handoff", action="store_true", help="Tự động xuất _session-handoff.md nếu status là RED")
    parser.add_argument("--transcript", type=str, default=None, help="Đường dẫn file transcript chỉ định")
    parser.add_argument("--handoff-dest", type=str, default=None, help="Đường dẫn lưu file handoff tuỳ chọn")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON")
    parser.add_argument("--strict", action="store_true", help="Thoát với exit code 1 nếu trạng thái RED")

    args = parser.parse_args()

    transcript_path = Path(args.transcript).resolve() if args.transcript else None
    handoff_dest = Path(args.handoff_dest).resolve() if args.handoff_dest else None

    result = check_session(
        transcript_path=transcript_path,
        auto_handoff=args.auto_handoff,
        handoff_dest=handoff_dest,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = result["status"]
        icons = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}
        icon = icons.get(status, "⚪")
        print("=" * 65)
        print(f"{icon} SESSION GUARD STATUS: {status}")
        print("=" * 65)
        print(f"- Chi tiết: {result['message']}")
        print(f"- Kích thước: {result['size_bytes'] / 1024:.1f} KB ({result['size_bytes']} bytes)")
        print(f"- Số turns/steps: {result['turns']} (total steps: {result['total_steps']})")
        if result['transcript_path']:
            print(f"- File transcript: {result['transcript_path']}")
        if result['handoff_written']:
            print(f"- Auto-handoff file: {result['handoff_written']}")
        print("=" * 65)

    if args.strict and result["status"] == "RED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
