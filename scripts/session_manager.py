#!/usr/bin/env python3
"""
scripts/session_manager.py

Zero-Friction Portable Session Sync:
Đồng bộ và khôi phục toàn bộ phiên làm việc, lịch sử hội thoại,
não bộ tác tử (brain/scratch/artifacts) và metadata SQLite giữa các máy tính.

Sử dụng:
  python scripts/session_manager.py --action export [--repo-dir <path>] [--app-data-dir <path>]
  python scripts/session_manager.py --action import [--repo-dir <path>] [--app-data-dir <path>]
"""

import argparse
import base64
import json
import os
import posixpath
import re
import shutil
import sqlite3
import stat
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path


def get_default_app_data_dir() -> str:
    """Xác định đường dẫn thư mục dữ liệu Antigravity mặc định."""
    custom = os.environ.get("ANTIGRAVITY_APP_DATA_DIR")
    if custom:
        return os.path.abspath(custom)
    return os.path.abspath(os.path.expanduser("~/.gemini/antigravity"))


def get_default_repo_dir() -> str:
    """Xác định thư mục gốc của repository."""
    current_file = os.path.abspath(__file__)
    return os.path.abspath(os.path.join(os.path.dirname(current_file), ".."))


def path_to_workspace_uri(path: str) -> str:
    """Chuyển đường dẫn thư mục sang URI workspace của Antigravity.

    Hàm thuần chuỗi nên cho KẾT QUẢ GIỐNG NHAU trên mọi hệ điều hành:
      D:\\AntiGravity\\MyProject -> file:///d%3A/AntiGravity/MyProject
      c:/work/test              -> file:///c%3A/work/test
      /home/runner/work/x       -> file:///home/runner/work/x

    Chỉ đường dẫn TƯƠNG ĐỐI mới phải quy về tuyệt đối (phụ thuộc OS hiện tại).
    """
    raw = str(path).replace("\\", "/")

    drive_match = re.match(r"^([A-Za-z]):(.*)$", raw)
    if drive_match:
        drive = drive_match.group(1).lower()
        rest = drive_match.group(2) or "/"
        if not rest.startswith("/"):
            rest = "/" + rest
        rest = posixpath.normpath(rest)
        return f"file:///{drive}%3A{rest}"

    if not raw.startswith("/"):
        raw = os.path.abspath(raw).replace("\\", "/")
    return "file://" + posixpath.normpath(raw)


def normalize_uri_or_path(uri_or_path: str) -> str:
    """Chuẩn hoá URI/path về khoá so sánh, ĐỘC LẬP NỀN TẢNG.

    Dùng làm khoá đối chiếu workspace giữa các máy (Windows <-> Linux/WSL):
      file:///d%3A/AntiGravity/MyProject -> d:/antigravity/myproject
      D:\\AntiGravity\\MyProject          -> d:/antigravity/myproject
      file:///home/runner/work/x         -> /home/runner/work/x
      /home/runner/work/x                -> /home/runner/work/x

    Quy ước: đường dẫn Windows hạ hết về chữ thường (Windows không phân biệt
    hoa/thường); đường dẫn POSIX giữ nguyên hoa/thường (POSIX phân biệt hoa/thường).
    """
    if not uri_or_path:
        return ""

    decoded = urllib.parse.unquote(str(uri_or_path))

    if decoded.startswith("file:///"):
        # URI tuyệt đối: giữ lại dấu "/" gốc (lỗi cũ: cắt 8 ký tự làm mất root,
        # biến "/tmp/x" thành "tmp/x" -> không bao giờ khớp trên POSIX).
        decoded = decoded[8:]
    elif decoded.startswith("file://"):
        decoded = decoded[7:]          # dạng file://host/path (hiếm)
    elif decoded.startswith("file:"):
        decoded = decoded[5:]

    decoded = decoded.replace("\\", "/")

    drive_match = re.match(r"^/?([A-Za-z]):(.*)$", decoded)
    if drive_match:
        # Windows không phân biệt hoa/thường -> hạ hết về chữ thường để so khớp
        # ổn định giữa các máy (giữ nguyên hành vi os.path.normcase trước đây).
        drive = drive_match.group(1).lower()
        rest = posixpath.normpath("/" + (drive_match.group(2) or "/").lstrip("/"))
        return f"{drive}:{rest}".lower()

    if not decoded.startswith("/"):
        decoded = "/" + decoded
    return posixpath.normpath(decoded)


def safe_copy_sqlite(src_path: str, dst_path: str) -> bool:
    """
    Sao chép SQLite an toàn kể cả khi database đang mở trong chế độ WAL.
    Sử dụng SQLite backup API để đảm bảo snapshot nhất quán, không bị lock.
    """
    if not os.path.exists(src_path):
        return False
    
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    try:
        abs_src = os.path.abspath(src_path)
        src_uri = f"file:{abs_src}?mode=ro"
        src_conn = sqlite3.connect(src_uri, uri=True, timeout=10.0)
        try:
            dst_conn = sqlite3.connect(dst_path, timeout=10.0)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()
        return True
    except Exception:
        # Fallback sao chép file truyền thống nếu backup API gặp sự cố
        try:
            shutil.copy2(src_path, dst_path)
            # Nếu có file wal/shm đi kèm, sao chép luôn
            for ext in [".db-wal", ".db-shm"]:
                wal_src = src_path + ext
                if os.path.exists(wal_src):
                    shutil.copy2(wal_src, dst_path + ext)
            return True
        except Exception as e:
            print(f"[WARN] Khong the sao chep {src_path} sang {dst_path}: {e}", file=sys.stderr)
            return False


def ensure_conversation_summaries_table(conn: sqlite3.Connection):
    """Đảm bảo bảng conversation_summaries tồn tại với đầy đủ cột."""
    schema = """
    CREATE TABLE IF NOT EXISTS `conversation_summaries` (
        `conversation_id` text,
        `title` text NOT NULL DEFAULT "",
        `preview` text NOT NULL DEFAULT "",
        `step_count` integer NOT NULL DEFAULT 0,
        `last_modified_time` datetime NOT NULL,
        `workspace_uris` text NOT NULL,
        `status` text NOT NULL DEFAULT "",
        `source` text NOT NULL DEFAULT "",
        `project_id` text NOT NULL DEFAULT "",
        `agent_name` text NOT NULL DEFAULT "",
        `parent_conversation_id` text NOT NULL DEFAULT "",
        `nesting_depth` integer NOT NULL DEFAULT 0,
        `battle_id` text NOT NULL DEFAULT "",
        `winning_conversation_id` text NOT NULL DEFAULT "",
        `not_fully_idle` numeric NOT NULL DEFAULT false,
        `killed` numeric NOT NULL DEFAULT false,
        `last_user_input_time` datetime NOT NULL,
        `last_user_input_step_index` integer NOT NULL DEFAULT -1,
        `app_data_dir` text NOT NULL DEFAULT "",
        `raw_summary` blob,
        `group_id` text NOT NULL DEFAULT "",
        PRIMARY KEY (`conversation_id`)
    );
    """
    conn.execute(schema)
    conn.commit()


def export_sessions(
    repo_dir: str = None,
    app_data_dir: str = None,
    conversation_id: str = None,
    export_all: bool = False,
) -> dict:
    """
    Quét conversation_summaries.db, sao chép toàn bộ database và thư mục não bộ
    thuộc workspace hiện tại vào $repo_dir/.sessions/.
    """
    repo_dir = os.path.abspath(repo_dir or get_default_repo_dir())
    app_data_dir = os.path.abspath(app_data_dir or get_default_app_data_dir())
    sessions_dir = os.path.join(repo_dir, ".sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    db_path = os.path.join(app_data_dir, "conversation_summaries.db")
    if not os.path.exists(db_path):
        return {
            "status": "error",
            "message": f"Khong tim thay database tong tai: {db_path}",
            "exported_count": 0,
        }

    target_norm_repo = normalize_uri_or_path(repo_dir)
    repo_basename = os.path.basename(repo_dir).lower()

    matched_rows = []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM conversation_summaries")
        all_rows = cur.fetchall()

        for row in all_rows:
            c_id = row["conversation_id"]
            if conversation_id and c_id != conversation_id:
                continue

            if export_all or conversation_id:
                matched_rows.append(row)
                continue

            # Kiểm tra workspace_uris khớp repo hiện tại
            uris_raw = row["workspace_uris"] or ""
            uris = []
            try:
                uris = json.loads(uris_raw)
            except Exception:
                if uris_raw:
                    uris = [uris_raw]

            matches = False
            for u in uris:
                norm_u = normalize_uri_or_path(u)
                if norm_u == target_norm_repo:
                    matches = True
                    break
                # Fallback: so tên thư mục cuối (đã chuẩn hoá, không phân biệt hoa/thường)
                if repo_basename and norm_u.rstrip("/").split("/")[-1].lower() == repo_basename:
                    matches = True
                    break

            if matches:
                matched_rows.append(row)
    finally:
        conn.close()

    exported_conversations = []
    conversations_source_dir = os.path.join(app_data_dir, "conversations")
    brain_source_dir = os.path.join(app_data_dir, "brain")

    for row in matched_rows:
        c_id = row["conversation_id"]
        c_dir = os.path.join(sessions_dir, c_id)
        os.makedirs(c_dir, exist_ok=True)

        # 1. Sao chép database phiên <id>.db
        src_db = os.path.join(conversations_source_dir, f"{c_id}.db")
        dst_db = os.path.join(c_dir, f"{c_id}.db")
        has_db = safe_copy_sqlite(src_db, dst_db)

        # 2. Sao chép thư mục não bộ brain/<id>
        src_brain = os.path.join(brain_source_dir, c_id)
        dst_brain = os.path.join(c_dir, "brain")
        has_brain = False
        if os.path.exists(src_brain):
            try:
                shutil.copytree(src_brain, dst_brain, dirs_exist_ok=True)
                has_brain = True
            except Exception as e:
                print(f"[WARN] Loi khi sao chep brain cho {c_id}: {e}", file=sys.stderr)

        # 3. Chuẩn hóa metadata để lưu vào sessions_index.json
        row_dict = dict(row)
        if row_dict.get("raw_summary") is not None and isinstance(row_dict["raw_summary"], (bytes, bytearray)):
            row_dict["raw_summary_b64"] = base64.b64encode(row_dict["raw_summary"]).decode("ascii")
        else:
            row_dict["raw_summary_b64"] = None
        row_dict.pop("raw_summary", None)

        row_dict["has_db"] = has_db
        row_dict["has_brain"] = has_brain
        exported_conversations.append(row_dict)

    # 4. Ghi file index .sessions/sessions_index.json
    index_data = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_repo_path": repo_dir,
        "source_workspace_uri": path_to_workspace_uri(repo_dir),
        "count": len(exported_conversations),
        "conversations": exported_conversations,
    }

    index_path = os.path.join(sessions_dir, "sessions_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    return {
        "status": "success",
        "exported_count": len(exported_conversations),
        "sessions_dir": sessions_dir,
        "index_file": index_path,
        "conversations": [c["conversation_id"] for c in exported_conversations],
    }


def import_sessions(
    repo_dir: str = None,
    app_data_dir: str = None,
) -> dict:
    """
    Đọc .sessions/sessions_index.json trong repo, sao chép file .db và brain
    vào máy mới, đồng thời nạp/cập nhật SQLite conversation_summaries.db với đường dẫn workspace mới.
    """
    repo_dir = os.path.abspath(repo_dir or get_default_repo_dir())
    app_data_dir = os.path.abspath(app_data_dir or get_default_app_data_dir())
    sessions_dir = os.path.join(repo_dir, ".sessions")
    index_path = os.path.join(sessions_dir, "sessions_index.json")

    if not os.path.exists(index_path):
        return {
            "status": "error",
            "message": f"Khong tim thay sessions_index.json tai: {index_path}",
            "imported_count": 0,
        }

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    conversations = index_data.get("conversations", [])
    if not conversations:
        return {
            "status": "success",
            "message": "Khong co phien lam viec nao can nap.",
            "imported_count": 0,
        }

    conversations_target_dir = os.path.join(app_data_dir, "conversations")
    brain_target_dir = os.path.join(app_data_dir, "brain")
    os.makedirs(conversations_target_dir, exist_ok=True)
    os.makedirs(brain_target_dir, exist_ok=True)

    db_path = os.path.join(app_data_dir, "conversation_summaries.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    new_workspace_uri = path_to_workspace_uri(repo_dir)

    imported_ids = []
    conn = sqlite3.connect(db_path, timeout=15.0)
    try:
        ensure_conversation_summaries_table(conn)
        cur = conn.cursor()

        for conv in conversations:
            c_id = conv["conversation_id"]
            c_dir = os.path.join(sessions_dir, c_id)

            # 1. Khôi phục file .db
            src_db = os.path.join(c_dir, f"{c_id}.db")
            dst_db = os.path.join(conversations_target_dir, f"{c_id}.db")
            if os.path.exists(src_db):
                safe_copy_sqlite(src_db, dst_db)

            # 2. Khôi phục thư mục brain
            src_brain = os.path.join(c_dir, "brain")
            dst_brain = os.path.join(brain_target_dir, c_id)
            if os.path.exists(src_brain):
                try:
                    shutil.copytree(src_brain, dst_brain, dirs_exist_ok=True)
                except Exception as e:
                    print(f"[WARN] Khong the khoi phuc brain cho {c_id}: {e}", file=sys.stderr)

            # 3. Điều chỉnh URI workspace và app_data_dir
            new_workspace_uris_json = json.dumps([new_workspace_uri])
            app_dir_name = conv.get("app_data_dir") or "antigravity"

            raw_summary_bytes = None
            if conv.get("raw_summary_b64"):
                try:
                    raw_summary_bytes = base64.b64decode(conv["raw_summary_b64"])
                except Exception:
                    raw_summary_bytes = None

            cols = [
                "conversation_id", "title", "preview", "step_count", "last_modified_time",
                "workspace_uris", "status", "source", "project_id", "agent_name",
                "parent_conversation_id", "nesting_depth", "battle_id", "winning_conversation_id",
                "not_fully_idle", "killed", "last_user_input_time", "last_user_input_step_index",
                "app_data_dir", "raw_summary", "group_id"
            ]

            values = [
                c_id,
                conv.get("title", ""),
                conv.get("preview", ""),
                conv.get("step_count", 0),
                conv.get("last_modified_time", datetime.now(timezone.utc).isoformat()),
                new_workspace_uris_json,
                conv.get("status", ""),
                conv.get("source", ""),
                conv.get("project_id", ""),
                conv.get("agent_name", ""),
                conv.get("parent_conversation_id", ""),
                conv.get("nesting_depth", 0),
                conv.get("battle_id", ""),
                conv.get("winning_conversation_id", ""),
                conv.get("not_fully_idle", 0),
                conv.get("killed", 0),
                conv.get("last_user_input_time", datetime.now(timezone.utc).isoformat()),
                conv.get("last_user_input_step_index", -1),
                app_dir_name,
                raw_summary_bytes,
                conv.get("group_id", "")
            ]

            placeholders = ", ".join(["?"] * len(cols))
            col_clause = ", ".join([f"`{c}`" for c in cols])
            cur.execute(f"INSERT OR REPLACE INTO conversation_summaries ({col_clause}) VALUES ({placeholders})", values)
            imported_ids.append(c_id)

        conn.commit()
    finally:
        conn.close()

    return {
        "status": "success",
        "imported_count": len(imported_ids),
        "target_app_data_dir": app_data_dir,
        "new_workspace_uri": new_workspace_uri,
        "conversations": imported_ids,
    }


def _handle_remove_readonly(func, path, exc_info):
    """Bỏ cờ read-only trên Windows (ví dụ file .git/objects/pack) trước khi xóa."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _safe_rmtree(path: str) -> None:
    """Xóa thư mục an toàn kể cả khi chứa file read-only trên Windows."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_handle_remove_readonly)
    else:
        shutil.rmtree(path, onerror=_handle_remove_readonly)


def _get_dir_size(path: str) -> int:
    """Tính tổng dung lượng (bytes) của toàn bộ tệp trong một thư mục."""
    total = 0
    for root, _, files in os.walk(path):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                total += os.path.getsize(fpath)
            except OSError:
                pass
    return total


def _prune_sessions_index(index_path: str, deleted_ids: set) -> None:
    """Xóa entry của các session đã bị xóa khỏi sessions_index.json (hỗ trợ dict hoặc list)."""
    if not deleted_ids or not os.path.exists(index_path):
        return
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    except Exception as e:
        print(f"[WARN] Khong the doc sessions_index.json de cap nhat: {e}", file=sys.stderr)
        return

    def _keep_entry(entry) -> bool:
        if isinstance(entry, dict):
            return entry.get("conversation_id") not in deleted_ids
        if isinstance(entry, str):
            return entry not in deleted_ids
        return True

    changed = False
    if isinstance(index_data, dict):
        convs = index_data.get("conversations")
        if isinstance(convs, list):
            filtered = [c for c in convs if _keep_entry(c)]
            if len(filtered) != len(convs):
                index_data["conversations"] = filtered
                if "count" in index_data:
                    index_data["count"] = len(filtered)
                changed = True
    elif isinstance(index_data, list):
        filtered = [c for c in index_data if _keep_entry(c)]
        if len(filtered) != len(index_data):
            index_data = filtered
            changed = True

    if changed:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)


def prune_sessions(
    repo_dir: str = None,
    max_size_mb: float = 400.0,
    keep_latest: int = 20,
    dry_run: bool = False,
    recent_protect_seconds: float = 300.0,
) -> dict:
    """
    Dọn bớt các thư mục session cũ trong <repo_dir>/.sessions khi tổng dung lượng
    vượt ngưỡng max_size_mb, bảo vệ keep_latest thư mục mới nhất và các thư mục
    vừa được sửa đổi trong vòng recent_protect_seconds giây.
    """
    repo_dir = os.path.abspath(repo_dir or get_default_repo_dir())
    sessions_dir = os.path.join(repo_dir, ".sessions")

    if not os.path.exists(sessions_dir):
        return {
            "status": "success",
            "dry_run": dry_run,
            "deleted_count": 0,
            "deleted_ids": [],
            "bytes_before": 0,
            "bytes_after": 0,
            "freed_bytes": 0,
            "max_size_mb": max_size_mb,
            "keep_latest": keep_latest,
        }

    total_bytes = _get_dir_size(sessions_dir)
    max_bytes = int(max_size_mb * 1024 * 1024)

    if total_bytes <= max_bytes:
        return {
            "status": "success",
            "dry_run": dry_run,
            "deleted_count": 0,
            "deleted_ids": [],
            "bytes_before": total_bytes,
            "bytes_after": total_bytes,
            "freed_bytes": 0,
            "max_size_mb": max_size_mb,
            "keep_latest": keep_latest,
        }

    dir_entries = []
    with os.scandir(sessions_dir) as it:
        for entry in it:
            if entry.is_dir(follow_symlinks=False):
                try:
                    mtime = entry.stat(follow_symlinks=False).st_mtime
                except OSError:
                    mtime = 0.0
                dir_entries.append({
                    "name": entry.name,
                    "path": entry.path,
                    "mtime": mtime,
                    "size": _get_dir_size(entry.path),
                })

    # Sắp xếp mới nhất trước để bảo vệ keep_latest thư mục mới nhất
    newest_first = sorted(dir_entries, key=lambda x: x["mtime"], reverse=True)
    protected_names = {e["name"] for e in newest_first[: max(0, keep_latest)]}

    now = time.time()
    candidates = [
        e for e in dir_entries
        if e["name"] not in protected_names and (now - e["mtime"]) >= recent_protect_seconds
    ]
    # Xóa cũ nhất trước
    candidates.sort(key=lambda x: x["mtime"])

    current_bytes = total_bytes
    freed_bytes = 0
    deleted_ids = []

    for entry in candidates:
        if current_bytes <= max_bytes:
            break
        if not dry_run:
            _safe_rmtree(entry["path"])
        current_bytes -= entry["size"]
        freed_bytes += entry["size"]
        deleted_ids.append(entry["name"])

    if deleted_ids and not dry_run:
        index_path = os.path.join(sessions_dir, "sessions_index.json")
        _prune_sessions_index(index_path, set(deleted_ids))

    return {
        "status": "success",
        "dry_run": dry_run,
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "bytes_before": total_bytes,
        "bytes_after": max(0, current_bytes),
        "freed_bytes": freed_bytes,
        "max_size_mb": max_size_mb,
        "keep_latest": keep_latest,
    }


def main():
    parser = argparse.ArgumentParser(description="Zero-Friction Portable Session Sync for Antigravity")
    parser.add_argument("--action", choices=["export", "import", "prune"], required=True, help="Thao tac: export, import hoac prune")
    parser.add_argument("--repo-dir", default=None, help="Thu muc repository (mac dinh: thu muc chua script/..)")
    parser.add_argument("--app-data-dir", default=None, help="Thu muc Antigravity app data")
    parser.add_argument("--conversation-id", default=None, help="ID phien cu the can export")
    parser.add_argument("--all", action="store_true", help="Export toan bo phien trong he thong")
    parser.add_argument("--max-size-mb", type=float, default=400.0, help="Nguong dung luong toi da (MB) cho prune (mac dinh: 400)")
    parser.add_argument("--keep-latest", type=int, default=20, help="So luong phien moi nhat duoc bao ve khi prune (mac dinh: 20)")
    parser.add_argument("--dry-run", action="store_true", help="Chay thu prune khong xoa file that")

    args = parser.parse_args()

    if args.action == "export":
        print(f"[*] Dang xuat phien lam viec vao .sessions/...")
        res = export_sessions(
            repo_dir=args.repo_dir,
            app_data_dir=args.app_data_dir,
            conversation_id=args.conversation_id,
            export_all=args.all,
        )
        if res.get("status") == "success":
            print(f"[OK] Da xuat thanh cong {res['exported_count']} phien lam viec!")
            print(f"     Thu muc luu: {res['sessions_dir']}")
            print(f"     File chi muc: {res['index_file']}")
        else:
            print(f"[ERROR] {res.get('message')}", file=sys.stderr)
            sys.exit(1)

    elif args.action == "import":
        print(f"[*] Dang nap phien lam viec tu .sessions/ vao may moi...")
        res = import_sessions(
            repo_dir=args.repo_dir,
            app_data_dir=args.app_data_dir,
        )
        if res.get("status") == "success":
            print(f"[OK] Da nap thanh cong {res['imported_count']} phien lam viec vao Antigravity!")
            print(f"     Workspace URI moi: {res['new_workspace_uri']}")
            print(f"     App Data Dir: {res['target_app_data_dir']}")
        else:
            print(f"[ERROR] {res.get('message')}", file=sys.stderr)
            sys.exit(1)

    elif args.action == "prune":
        prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"[*] {prefix}Dang don dep .sessions/ (nguong: {args.max_size_mb} MB, giu lai: {args.keep_latest} phien moi nhat)...")
        res = prune_sessions(
            repo_dir=args.repo_dir,
            max_size_mb=args.max_size_mb,
            keep_latest=args.keep_latest,
            dry_run=args.dry_run,
        )
        before_mb = res["bytes_before"] / (1024 * 1024)
        after_mb = res["bytes_after"] / (1024 * 1024)
        freed_mb = res["freed_bytes"] / (1024 * 1024)
        print(f"[OK] {prefix}Da don {res['deleted_count']} phien cu (giai phong {freed_mb:.2f} MB).")
        print(f"     Dung luong truoc: {before_mb:.2f} MB -> Sau: {after_mb:.2f} MB")


if __name__ == "__main__":
    main()
