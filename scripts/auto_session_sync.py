#!/usr/bin/env python3
"""
scripts/auto_session_sync.py

Central Session Sync Watcher:
Tự động đồng bộ các phiên làm việc Antigravity thời gian thực:
- Debounce (mặc định 60s): Gom trọn chu trình tác tử và thời gian nghỉ tự nhiên.
- Hard Timeout (mặc định 180s): Ép flush sau 3 phút nếu chat liên tục không nghỉ.
- Graceful Shutdown Flush: Bắt tín hiệu SIGINT/SIGTERM/atexit để flush tức thì các phiên đang chờ.
- Multi-workspace mapping: 1 watcher duy nhất tự động phân loại và ghi đúng vào .sessions/
  của từng dự án theo trường workspace_uris.
- Tối ưu tài nguyên: Chạy ngầm tiêu thụ CPU 0.0%, RAM nhẹ.
"""

import argparse
import atexit
import json
import os
import posixpath
import re
import signal
import sqlite3
import subprocess
import sys
import time

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.session_manager import (
        export_sessions,
        get_default_repo_dir,
        get_default_app_data_dir,
        normalize_uri_or_path,
        path_to_workspace_uri,
    )
except ImportError:
    from session_manager import (
        export_sessions,
        get_default_repo_dir,
        get_default_app_data_dir,
        normalize_uri_or_path,
        path_to_workspace_uri,
    )


def uri_to_workspace_path(uri: str) -> str | None:
    """Chuyển đổi workspace URI (ví dụ: file:///d%3A/Path/To/Repo) thành đường dẫn thư mục cục bộ."""
    if not uri:
        return None
    decoded = urllib.parse.unquote(str(uri))
    if decoded.startswith("file:///"):
        decoded = decoded[8:]
    elif decoded.startswith("file://"):
        decoded = decoded[7:]
    elif decoded.startswith("file:"):
        decoded = decoded[5:]

    decoded = decoded.replace("/", os.sep)
    m = re.match(r"^\\?([A-Za-z]:.*)$", decoded)
    if m:
        path = m.group(1)
        if len(path) >= 2 and path[1] == ":":
            path = path[0].upper() + path[1:]
    else:
        path = decoded
        if not path.startswith(os.sep) and not re.match(r"^[A-Za-z]:", path):
            path = os.sep + path

    if os.path.exists(path):
        try:
            return os.path.realpath(path)
        except Exception:
            return os.path.abspath(path)
    return os.path.abspath(path)


def extract_workspaces_from_uris(workspace_uris_raw: str) -> list[str]:
    """Trích xuất danh sách các đường dẫn workspace hợp lệ từ trường workspace_uris trong SQLite."""
    if not workspace_uris_raw:
        return []
    uris = []
    try:
        uris = json.loads(workspace_uris_raw)
        if not isinstance(uris, list):
            uris = [workspace_uris_raw]
    except Exception:
        uris = [workspace_uris_raw]

    results = []
    for u in uris:
        p = uri_to_workspace_path(u)
        if p and p not in results:
            results.append(p)
    return results


class SessionSyncWatcher:
    """Watcher trung tâm theo dõi hoạt động phiên và flush tự động với debounce/hard timeout."""

    def __init__(
        self,
        repo_dir: str = None,
        app_data_dir: str = None,
        watch_all: bool = False,
        debounce_seconds: float = 60.0,
        max_timeout: float = 180.0,
        poll_interval: float = 1.0,
    ):
        self.repo_dir = os.path.abspath(repo_dir) if repo_dir else None
        self.app_data_dir = os.path.abspath(app_data_dir or get_default_app_data_dir())
        self.watch_all = watch_all
        self.debounce_seconds = float(debounce_seconds)
        self.max_timeout = float(max_timeout)
        self.poll_interval = float(poll_interval)

        # Trạng thái theo dõi
        self.pending_workspaces: dict[str, dict] = {}
        self.snapshot: dict[str, tuple[str, int]] = {}
        self._last_db_mtimes: tuple[float, float] = (0.0, 0.0)
        self._running = False
        self._shutdown_completed = False

    def get_db_path(self) -> str:
        return os.path.join(self.app_data_dir, "conversation_summaries.db")

    def _get_db_mtimes(self) -> tuple[float, float]:
        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            return (0.0, 0.0)
        try:
            mtime = os.path.getmtime(db_path)
            wal_path = db_path + "-wal"
            wal_mtime = os.path.getmtime(wal_path) if os.path.exists(wal_path) else 0.0
            return (mtime, wal_mtime)
        except OSError:
            return (0.0, 0.0)

    def scan_active_workspaces(self) -> list[str]:
        """Quét toàn bộ workspace có phiên trong SQLite database."""
        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            return []

        workspaces = set()
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT workspace_uris FROM conversation_summaries")
                for row in cur.fetchall():
                    for ws in extract_workspaces_from_uris(row["workspace_uris"]):
                        workspaces.add(ws)
            finally:
                conn.close()
        except Exception as e:
            print(f"[WARN] Khong the doc database: {e}", file=sys.stderr)

        return sorted(workspaces)

    def scan_changes(self, now: float = None) -> list[str]:
        """Quét database kiểm tra phiên mới hoặc có thay đổi (step_count, last_modified_time)."""
        if now is None:
            now = time.time()

        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            return []

        changed_workspaces = set()
        target_norm_repo = normalize_uri_or_path(self.repo_dir) if self.repo_dir else None
        repo_basename = os.path.basename(self.repo_dir).lower() if self.repo_dir else None

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT conversation_id, last_modified_time, step_count, workspace_uris FROM conversation_summaries"
                )
                rows = cur.fetchall()

                for row in rows:
                    c_id = row["conversation_id"]
                    mod_time = str(row["last_modified_time"] or "")
                    steps = int(row["step_count"] or 0)
                    state = (mod_time, steps)

                    # Kiểm tra thay đổi
                    is_new = c_id not in self.snapshot
                    has_changed = not is_new and self.snapshot[c_id] != state

                    self.snapshot[c_id] = state

                    if is_new or has_changed:
                        ws_paths = extract_workspaces_from_uris(row["workspace_uris"])

                        if self.watch_all:
                            for ws in ws_paths:
                                self._enqueue_workspace(ws, c_id, now)
                                changed_workspaces.add(ws)
                        else:
                            # Chế độ theo dõi repo cụ thể
                            if self.repo_dir:
                                matches = False
                                for ws in ws_paths:
                                    norm_ws = normalize_uri_or_path(ws)
                                    if norm_ws == target_norm_repo:
                                        matches = True
                                        break
                                    if repo_basename and norm_ws.rstrip("/").split("/")[-1].lower() == repo_basename:
                                        matches = True
                                        break

                                if matches:
                                    self._enqueue_workspace(self.repo_dir, c_id, now)
                                    changed_workspaces.add(self.repo_dir)
            finally:
                conn.close()
        except Exception as e:
            print(f"[WARN] Loi khi quet phien lam viec: {e}", file=sys.stderr)

        return sorted(changed_workspaces)

    def _enqueue_workspace(self, ws_path: str, conversation_id: str, now: float):
        """Đưa workspace vào hàng đợi debounce / hard timeout."""
        ws_norm = os.path.realpath(ws_path) if os.path.exists(ws_path) else os.path.abspath(ws_path)
        if ws_norm not in self.pending_workspaces:
            self.pending_workspaces[ws_norm] = {
                "ws_path": ws_norm,
                "first_seen": now,
                "last_seen": now,
                "conversations": {conversation_id},
            }
            print(f"[*] Phat hien hoat dong tai: {ws_norm} (Debounce: {self.debounce_seconds:.0f}s, Timeout: {self.max_timeout:.0f}s)")
        else:
            # Debounce: Cập nhật last_seen để gia hạn timer
            self.pending_workspaces[ws_norm]["last_seen"] = now
            self.pending_workspaces[ws_norm]["conversations"].add(conversation_id)

    def evaluate_timers(self, now: float = None) -> list[str]:
        """Đánh giá các timer debounce và hard timeout, kích hoạt flush khi đạt điều kiện."""
        if now is None:
            now = time.time()

        workspaces_to_flush = []
        for ws_path, info in list(self.pending_workspaces.items()):
            elapsed_debounce = now - info["last_seen"]
            elapsed_timeout = now - info["first_seen"]

            trigger_reason = None
            if elapsed_timeout >= self.max_timeout:
                trigger_reason = f"hard_timeout ({elapsed_timeout:.1f}s >= {self.max_timeout:.1f}s)"
            elif elapsed_debounce >= self.debounce_seconds:
                trigger_reason = f"debounce_quiet ({elapsed_debounce:.1f}s >= {self.debounce_seconds:.1f}s)"

            if trigger_reason:
                workspaces_to_flush.append((ws_path, trigger_reason))

        flushed = []
        for ws_path, reason in workspaces_to_flush:
            self.flush_workspace(ws_path, reason=reason)
            flushed.append(ws_path)

        return flushed

    def flush_workspace(self, ws_path: str, reason: str = "manual") -> dict:
        """Thực thi flush đồng bộ phiên vào .sessions/ của workspace chỉ định."""
        ws_path = os.path.abspath(ws_path)
        print(f"[*] Dang flush phien cho {ws_path} (ly do: {reason})...")

        res = export_sessions(
            repo_dir=ws_path,
            app_data_dir=self.app_data_dir,
            export_all=False,
        )

        if ws_path in self.pending_workspaces:
            del self.pending_workspaces[ws_path]

        if res.get("status") == "success":
            print(f"[OK] Da flush thanh cong {res.get('exported_count', 0)} phien vao {ws_path}/.sessions/")
        else:
            print(f"[ERROR] Loi khi flush phien cho {ws_path}: {res.get('message')}", file=sys.stderr)

        return res

    def flush_all(self, reason: str = "manual") -> list[dict]:
        """Flush toàn bộ workspace đang nằm trong hàng đợi chờ."""
        results = []
        for ws_path in list(self.pending_workspaces.keys()):
            res = self.flush_workspace(ws_path, reason=reason)
            results.append(res)
        return results

    def register_signal_handlers(self):
        """Đăng ký bắt tín hiệu thoát hệ thống để đảm bảo Graceful Shutdown Flush."""
        def _handle_exit(signum=None, frame=None):
            self.shutdown()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _handle_exit)
        except (ValueError, AttributeError):
            pass
        try:
            signal.signal(signal.SIGTERM, _handle_exit)
        except (ValueError, AttributeError):
            pass
        if hasattr(signal, "SIGBREAK"):
            try:
                signal.signal(signal.SIGBREAK, _handle_exit)
            except (ValueError, AttributeError):
                pass

        atexit.register(self.shutdown)

    def _save_pid(self):
        try:
            save_watcher_pid(
                pid=os.getpid(),
                app_data_dir=self.app_data_dir,
                repo_dir=self.repo_dir,
                watch_all=self.watch_all,
            )
        except Exception:
            pass

    def _remove_pid(self):
        pid_file = get_pid_file_path(self.app_data_dir)
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.startswith("{"):
                        data = json.loads(content)
                        saved_pid = int(data.get("pid", 0))
                    else:
                        saved_pid = int(content)
                    if saved_pid == os.getpid():
                        os.remove(pid_file)
            except Exception:
                pass

    def shutdown(self):
        """Xử lý tắt tiến trình an toàn, flush toàn bộ dữ liệu đang chờ."""
        if self._shutdown_completed:
            return
        self._shutdown_completed = True
        self._running = False

        if self.pending_workspaces:
            print(f"\n[*] Graceful Shutdown: Dang flush {len(self.pending_workspaces)} workspace dang cho truoc khi thoat...")
            self.flush_all(reason="graceful_shutdown")
        self._remove_pid()
        print("[OK] Session Sync Watcher da dong an toan.")

    def run_once(self) -> dict:
        """Chạy một lượt kiểm tra/flush rồi thoát ngay (phục vụ CI/test)."""
        if self.watch_all:
            workspaces = self.scan_active_workspaces()
            if self.repo_dir and self.repo_dir not in workspaces:
                workspaces.append(self.repo_dir)
            if not workspaces:
                workspaces = [get_default_repo_dir()]

            flushed_results = []
            total_exported = 0
            for ws in workspaces:
                res = export_sessions(repo_dir=ws, app_data_dir=self.app_data_dir)
                flushed_results.append(res)
                total_exported += res.get("exported_count", 0)

            return {
                "status": "success",
                "mode": "watch-all",
                "workspaces": workspaces,
                "exported_count": total_exported,
                "results": flushed_results,
            }
        else:
            target_repo = self.repo_dir or get_default_repo_dir()
            res = export_sessions(repo_dir=target_repo, app_data_dir=self.app_data_dir)
            return {
                "status": res.get("status", "success"),
                "mode": "single-repo",
                "repo_dir": target_repo,
                "exported_count": res.get("exported_count", 0),
                "result": res,
            }

    def run(self):
        """Khởi động vòng lặp theo dõi liên tục với cơ chế ngủ tiết kiệm tài nguyên (CPU 0.0%)."""
        self._running = True
        self.register_signal_handlers()

        # Nạp snapshot khởi đầu để tránh flush giả lập tức
        mtimes = self._get_db_mtimes()
        self._last_db_mtimes = mtimes

        db_path = self.get_db_path()
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
                try:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT conversation_id, last_modified_time, step_count FROM conversation_summaries")
                    for r in cur.fetchall():
                        self.snapshot[r["conversation_id"]] = (
                            str(r["last_modified_time"] or ""),
                            int(r["step_count"] or 0),
                        )
                finally:
                    conn.close()
            except Exception:
                pass

        print(f"[*] Session Sync Watcher da khoi dong!")
        print(f"    - Debounce: {self.debounce_seconds:.0f}s | Hard Timeout: {self.max_timeout:.0f}s")
        print(f"    - Che do: {'Watch-All (Toan bo workspace)' if self.watch_all else f'Single Repo: {self.repo_dir}'}")
        print(f"    - App Data: {self.app_data_dir}")
        print("    - Nhan Ctrl+C de dung va thuc hien Graceful Shutdown Flush.")

        self._save_pid()

        while self._running:
            try:
                now = time.time()
                cur_mtimes = self._get_db_mtimes()

                # Chi truy van database khi file thuc su bi ghi moi (mtime doi)
                if cur_mtimes != self._last_db_mtimes:
                    self._last_db_mtimes = cur_mtimes
                    self.scan_changes(now=now)

                # Kiem tra cac timer debounce / hard timeout
                self.evaluate_timers(now=now)

                time.sleep(self.poll_interval)
            except (KeyboardInterrupt, SystemExit):
                self.shutdown()
                break
            except Exception as e:
                print(f"[WARN] Loi ngoai le trong watcher loop: {e}", file=sys.stderr)
                time.sleep(self.poll_interval)


VBS_LAUNCHER_NAME = "AntigravitySessionWatcher.vbs"
WATCHER_PID_FILE = "watcher.pid"


def is_pid_running(pid: int) -> bool:
    """Kiểm tra xem một PID có đang tồn tại và hoạt động hay không."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def stop_process(pid: int) -> bool:
    """Dừng một tiến trình theo PID."""
    if not is_pid_running(pid):
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_TERMINATE = 0x0001
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                try:
                    ctypes.windll.kernel32.TerminateProcess(handle, 0)
                    return True
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
        try:
            res = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False


def get_startup_dir(custom_dir: str = None) -> str:
    """Lấy thư mục Startup (Windows hoặc thư mục tuỳ chỉnh để kiểm thử)."""
    if custom_dir:
        return os.path.abspath(custom_dir)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return os.path.join(str(Path.home()), "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def get_pid_file_path(app_data_dir: str) -> str:
    """Đường dẫn lưu file PID của watcher."""
    return os.path.join(app_data_dir, WATCHER_PID_FILE)


def get_running_watcher_pid(app_data_dir: str) -> int | None:
    """Đọc PID từ file và kiểm tra xem watcher có thực sự đang chạy không."""
    pid_file = get_pid_file_path(app_data_dir)
    if not os.path.exists(pid_file):
        return None
    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            try:
                data = json.loads(content)
                pid = int(data.get("pid", 0))
            except Exception:
                pid = int(content)
        if pid > 0 and is_pid_running(pid):
            return pid
        try:
            os.remove(pid_file)
        except OSError:
            pass
    except Exception:
        pass
    return None


def save_watcher_pid(pid: int, app_data_dir: str, repo_dir: str = None, watch_all: bool = True) -> str:
    """Lưu PID và metadata của watcher vào file."""
    os.makedirs(app_data_dir, exist_ok=True)
    pid_file = get_pid_file_path(app_data_dir)
    info = {
        "pid": pid,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "repo_dir": repo_dir,
        "app_data_dir": app_data_dir,
        "watch_all": watch_all,
    }
    with open(pid_file, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return pid_file


def generate_vbs_launcher(python_exe: str, script_path: str, repo_dir: str = None) -> str:
    """Tạo nội dung script VBS launcher hoàn toàn ẩn cửa sổ console (WindowStyle=0)."""
    cmd = f'"{python_exe}" "{script_path}" --watch-all'
    if repo_dir:
        cmd += f' --repo-dir "{repo_dir}"'
    escaped_cmd = cmd.replace('"', '""')
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run "{escaped_cmd}", 0, False\r\n'
        'Set WshShell = Nothing\r\n'
    )
    return vbs_content


def install_startup(
    repo_dir: str = None,
    app_data_dir: str = None,
    startup_dir: str = None,
    python_exe: str = None,
) -> dict:
    """Cài đặt VBS launcher vào Windows Startup và tự động khởi chạy watcher nếu chưa chạy."""
    app_data_dir = os.path.abspath(app_data_dir or get_default_app_data_dir())
    st_dir = get_startup_dir(startup_dir)
    os.makedirs(st_dir, exist_ok=True)

    py_exe = os.path.abspath(python_exe or sys.executable)
    script_path = os.path.abspath(__file__)
    resolved_repo = os.path.abspath(repo_dir) if repo_dir else None

    # 1. Tạo file VBS launcher tàng hình
    vbs_path = os.path.join(st_dir, VBS_LAUNCHER_NAME)
    vbs_content = generate_vbs_launcher(py_exe, script_path, repo_dir=resolved_repo)
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print(f"[OK] Da tao VBS launcher tai: {vbs_path}")

    # 2. Kiểm tra watcher đã chạy chưa
    current_pid = get_running_watcher_pid(app_data_dir)
    if current_pid:
        print(f"[*] Watcher da dang chay ngam (PID: {current_pid}).")
        return {
            "status": "success",
            "vbs_path": vbs_path,
            "pid": current_pid,
            "already_running": True,
        }

    # 3. Tự động khởi chạy watcher ngầm
    cmd = [py_exe, script_path, "--watch-all", "--app-data-dir", app_data_dir]
    if resolved_repo:
        cmd.extend(["--repo-dir", resolved_repo])

    popen_kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        # DETACHED_PROCESS (0x00000008) | CREATE_NO_WINDOW (0x08000000)
        popen_kwargs["creationflags"] = 0x08000008
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)
    save_watcher_pid(proc.pid, app_data_dir, repo_dir=resolved_repo, watch_all=True)
    print(f"[OK] Da khoi chay watcher ngam (PID: {proc.pid}).")

    return {
        "status": "success",
        "vbs_path": vbs_path,
        "pid": proc.pid,
        "already_running": False,
    }


def uninstall_startup(app_data_dir: str = None, startup_dir: str = None) -> dict:
    """Gỡ bỏ VBS launcher khỏi Startup và dừng watcher nếu đang chạy."""
    app_data_dir = os.path.abspath(app_data_dir or get_default_app_data_dir())
    st_dir = get_startup_dir(startup_dir)
    vbs_path = os.path.join(st_dir, VBS_LAUNCHER_NAME)

    vbs_removed = False
    if os.path.exists(vbs_path):
        try:
            os.remove(vbs_path)
            vbs_removed = True
            print(f"[OK] Da xoa VBS launcher: {vbs_path}")
        except Exception as e:
            print(f"[WARN] Khong the xoa VBS launcher: {e}", file=sys.stderr)

    pid = get_running_watcher_pid(app_data_dir)
    stopped = False
    if pid:
        stopped = stop_process(pid)
        print(f"[OK] Da dung tien trinh watcher (PID: {pid}).")
        pid_file = get_pid_file_path(app_data_dir)
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except OSError:
                pass

    return {
        "status": "success",
        "uninstalled_vbs": vbs_removed,
        "stopped_pid": pid if stopped else None,
    }


def check_watcher_status(app_data_dir: str = None, startup_dir: str = None) -> dict:
    """Kiểm tra trạng thái hoạt động của watcher và VBS launcher."""
    app_data_dir = os.path.abspath(app_data_dir or get_default_app_data_dir())
    st_dir = get_startup_dir(startup_dir)
    vbs_path = os.path.join(st_dir, VBS_LAUNCHER_NAME)

    pid = get_running_watcher_pid(app_data_dir)
    is_running = pid is not None
    vbs_exists = os.path.exists(vbs_path)

    print("=== Antigravity Session Watcher Status ===")
    print(f"  Trang thai:        {'RUNNING (Dang chay)' if is_running else 'STOPPED (Da dung)'}")
    if is_running:
        print(f"  PID:               {pid}")
    print(f"  Startup Launcher:  {'INSTALLED (Da cai dat)' if vbs_exists else 'NOT INSTALLED (Chua cai)'}")
    print(f"  VBS Path:          {vbs_path}")
    print(f"  App Data Dir:      {app_data_dir}")

    return {
        "status": "running" if is_running else "stopped",
        "pid": pid,
        "startup_installed": vbs_exists,
        "vbs_path": vbs_path,
        "startup_dir": st_dir,
        "app_data_dir": app_data_dir,
    }


def main():
    parser = argparse.ArgumentParser(description="Central Session Sync Watcher for Antigravity")
    parser.add_argument("--debounce-seconds", type=float, default=60.0, help="Thoi gian debounce quiet timer (mac dinh: 60s)")
    parser.add_argument("--max-timeout", type=float, default=180.0, help="Thoi gian hard timeout ep flush (mac dinh: 180s)")
    parser.add_argument("--watch-all", action="store_true", help="Tu dong theo doi va dong bo tat ca workspace trong database")
    parser.add_argument("--repo-dir", default=None, help="Theo doi 1 workspace cu the (mac dinh: repo hien tai)")
    parser.add_argument("--app-data-dir", default=None, help="Thu muc Antigravity app data")
    parser.add_argument("--once", action="store_true", help="Chay 1 luot kiem tra/flush roi thoat ngay (phuc vu CI/test)")
    parser.add_argument("--interval", type=float, default=1.0, help="Chu ky kiem tra moi giay (mac dinh: 1.0s, CPU 0.0%%)")
    parser.add_argument("--install-startup", action="store_true", help="Cai dat VBS launcher vao Windows Startup va khoi chay watcher ngam")
    parser.add_argument("--uninstall-startup", action="store_true", help="Go bo VBS launcher khoi Windows Startup va dung watcher ngam")
    parser.add_argument("--status", action="store_true", help="Kiem tra trang thai watcher va VBS launcher")
    parser.add_argument("--startup-dir", default=None, help="Thu muc Windows Startup tuy chinh (phuc vu test hoac cau hinh rieng)")

    args = parser.parse_args()

    watch_all = args.watch_all
    repo_dir = args.repo_dir
    app_data_dir = args.app_data_dir

    if args.status:
        check_watcher_status(app_data_dir=app_data_dir, startup_dir=args.startup_dir)
        sys.exit(0)

    if args.install_startup:
        install_startup(repo_dir=repo_dir, app_data_dir=app_data_dir, startup_dir=args.startup_dir)
        sys.exit(0)

    if args.uninstall_startup:
        uninstall_startup(app_data_dir=app_data_dir, startup_dir=args.startup_dir)
        sys.exit(0)

    if not watch_all and not repo_dir:
        repo_dir = get_default_repo_dir()

    watcher = SessionSyncWatcher(
        repo_dir=repo_dir,
        app_data_dir=app_data_dir,
        watch_all=watch_all,
        debounce_seconds=args.debounce_seconds,
        max_timeout=args.max_timeout,
        poll_interval=args.interval,
    )

    if args.once:
        print("[*] Thuc hien chay 1 luot (--once)...")
        res = watcher.run_once()
        print(f"[OK] Hoan tat: Da xuat tong cong {res.get('exported_count', 0)} phien.")
        sys.exit(0)

    watcher.run()


if __name__ == "__main__":
    main()
