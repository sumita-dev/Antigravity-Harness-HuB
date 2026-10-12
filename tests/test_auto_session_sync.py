"""
tests/test_auto_session_sync.py

Kiểm thử tự động cho Central Session Sync Watcher (scripts/auto_session_sync.py):
1. uri_to_workspace_path & extract_workspaces_from_uris
2. Debounce timer logic & flush queue (reset khi có activity liên tục)
3. Hard timeout triggering (ép flush sau 180s khi chat liên tục không nghỉ)
4. Graceful shutdown flush handler (flush ngay lập tức khi nhận tín hiệu tắt)
5. Multi-workspace mapping (1 watcher tự động phân loại đúng theo workspace_uris)
6. Cờ --once chạy an toàn cho single repo và watch-all
"""

import json
import os
import shutil
import sqlite3
import tempfile
import time
import pytest

from scripts.auto_session_sync import (
    SessionSyncWatcher,
    uri_to_workspace_path,
    extract_workspaces_from_uris,
    generate_vbs_launcher,
    install_startup,
    uninstall_startup,
    check_watcher_status,
    VBS_LAUNCHER_NAME,
)
from scripts.session_manager import (
    path_to_workspace_uri,
    ensure_conversation_summaries_table,
)


def setup_mock_env(base_dir, repo_name="Project-Test"):
    """Tạo cấu trúc môi trường mock app_data_dir và repo_dir."""
    app_data_dir = os.path.realpath(os.path.join(base_dir, "antigravity_data"))
    repo_dir = os.path.realpath(os.path.join(base_dir, repo_name))
    os.makedirs(app_data_dir, exist_ok=True)
    os.makedirs(repo_dir, exist_ok=True)

    conversations_dir = os.path.join(app_data_dir, "conversations")
    brain_dir = os.path.join(app_data_dir, "brain")
    os.makedirs(conversations_dir, exist_ok=True)
    os.makedirs(brain_dir, exist_ok=True)

    db_path = os.path.join(app_data_dir, "conversation_summaries.db")
    conn = sqlite3.connect(db_path)
    try:
        ensure_conversation_summaries_table(conn)
    finally:
        conn.close()

    return app_data_dir, repo_dir


def create_mock_session(app_data_dir, conv_id, workspace_path, step_count=1, mod_time="2026-10-12T10:00:00Z"):
    """Thêm phiên làm việc mock vào SQLite và tạo file db + brain."""
    db_path = os.path.join(app_data_dir, "conversation_summaries.db")
    ws_uri = path_to_workspace_uri(workspace_path)
    ws_uris_json = json.dumps([ws_uri])

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO conversation_summaries (
                conversation_id, title, preview, step_count, last_modified_time,
                workspace_uris, status, source, app_data_dir, last_user_input_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                f"Title {conv_id}",
                f"Preview {conv_id}",
                step_count,
                mod_time,
                ws_uris_json,
                "active",
                "chat",
                "antigravity",
                mod_time,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Tạo file conversation db
    conv_db_path = os.path.join(app_data_dir, "conversations", f"{conv_id}.db")
    cconn = sqlite3.connect(conv_db_path)
    cconn.execute("CREATE TABLE IF NOT EXISTS messages (id text)")
    cconn.commit()
    cconn.close()

    # Tạo thư mục brain
    b_dir = os.path.join(app_data_dir, "brain", conv_id)
    os.makedirs(b_dir, exist_ok=True)
    with open(os.path.join(b_dir, "state.json"), "w", encoding="utf-8") as f:
        f.write('{"state": "mock"}')


def test_uri_helpers():
    """Kiểm tra hàm trích xuất URI và chuyển đổi thành đường dẫn thư mục."""
    win_uri = "file:///d%3A/AntiGravity/TestApp"
    parsed_win = uri_to_workspace_path(win_uri)
    assert parsed_win is not None
    assert "antigravity" in parsed_win.lower() or "testapp" in parsed_win.lower()

    posix_uri = "file:///home/runner/work/repo"
    parsed_posix = uri_to_workspace_path(posix_uri)
    assert parsed_posix is not None

    uris_json = json.dumps([win_uri, posix_uri])
    extracted = extract_workspaces_from_uris(uris_json)
    assert len(extracted) == 2


def test_debounce_timer_and_flush_queue():
    """Kiểm tra debounce timer: gom hoạt động, chỉ flush khi yên ắng đủ debounce_seconds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app_data_dir, repo_dir = setup_mock_env(tmpdir, "DebounceProject")
        conv_id = "conv-debounce-1"
        create_mock_session(app_data_dir, conv_id, repo_dir, step_count=1, mod_time="10:00:00")

        watcher = SessionSyncWatcher(
            repo_dir=repo_dir,
            app_data_dir=app_data_dir,
            watch_all=False,
            debounce_seconds=60.0,
            max_timeout=180.0,
        )

        t0 = 1000.0
        # 1. Phát hiện thay đổi đầu tiên tại t0
        changed = watcher.scan_changes(now=t0)
        assert repo_dir in changed
        assert repo_dir in watcher.pending_workspaces
        info = watcher.pending_workspaces[repo_dir]
        assert info["first_seen"] == t0
        assert info["last_seen"] == t0

        # 2. Sau 30s (chưa đủ 60s debounce), kiểm tra timer -> chưa flush
        flushed = watcher.evaluate_timers(now=t0 + 30.0)
        assert flushed == []
        assert repo_dir in watcher.pending_workspaces

        # 3. Tại t0 + 40s: có thêm turn chat mới -> debounce reset last_seen
        create_mock_session(app_data_dir, conv_id, repo_dir, step_count=2, mod_time="10:00:40")
        watcher.scan_changes(now=t0 + 40.0)
        assert watcher.pending_workspaces[repo_dir]["first_seen"] == t0
        assert watcher.pending_workspaces[repo_dir]["last_seen"] == t0 + 40.0

        # 4. Tại t0 + 80s: mới 40s trôi qua kể từ lượt chat cuối (40s < 60s debounce) -> chưa flush
        flushed = watcher.evaluate_timers(now=t0 + 80.0)
        assert flushed == []
        assert repo_dir in watcher.pending_workspaces

        # 5. Tại t0 + 105s: 65s yên ắng kể từ lượt chat cuối (105 - 40 = 65s >= 60s) -> Kích hoạt FLUSH!
        flushed = watcher.evaluate_timers(now=t0 + 105.0)
        assert repo_dir in flushed
        assert repo_dir not in watcher.pending_workspaces

        # Kiểm tra file index và session db đã được ghi vào .sessions/
        sessions_dir = os.path.join(repo_dir, ".sessions")
        assert os.path.exists(os.path.join(sessions_dir, "sessions_index.json"))
        assert os.path.exists(os.path.join(sessions_dir, conv_id, f"{conv_id}.db"))


def test_max_timeout_triggering():
    """Kiểm tra hard timeout: ép flush sau max_timeout (180s) nếu chat liên tục không có khoảng lặng 60s."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app_data_dir, repo_dir = setup_mock_env(tmpdir, "HardTimeoutProject")
        conv_id = "conv-hard-timeout"
        create_mock_session(app_data_dir, conv_id, repo_dir, step_count=1, mod_time="10:00:00")

        watcher = SessionSyncWatcher(
            repo_dir=repo_dir,
            app_data_dir=app_data_dir,
            watch_all=False,
            debounce_seconds=60.0,
            max_timeout=180.0,
        )

        t0 = 2000.0
        watcher.scan_changes(now=t0)

        # Mô phỏng chat liên tục mỗi 45 giây (45s < 60s debounce nên debounce không bao giờ kích hoạt)
        for step, offset in enumerate([45.0, 90.0, 135.0, 170.0], start=2):
            now_time = t0 + offset
            create_mock_session(app_data_dir, conv_id, repo_dir, step_count=step, mod_time=f"10:{int(offset)}")
            watcher.scan_changes(now=now_time)
            flushed = watcher.evaluate_timers(now=now_time)
            assert flushed == [], f"Khong duoc flush tai offset {offset}"

        # Tại t0 + 185s: Chat liên tục vượt 180s -> Hard timeout ép flush tức thì!
        flushed = watcher.evaluate_timers(now=t0 + 185.0)
        assert repo_dir in flushed
        assert repo_dir not in watcher.pending_workspaces

        sessions_dir = os.path.join(repo_dir, ".sessions")
        assert os.path.exists(os.path.join(sessions_dir, "sessions_index.json"))


def test_graceful_shutdown_flush_handler():
    """Kiểm tra Graceful Shutdown: khi tiến trình tắt hoặc nhận tín hiệu, flush toàn bộ hàng đợi ngay."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app_data_dir, repo_dir = setup_mock_env(tmpdir, "ShutdownProject")
        conv_id = "conv-shutdown-1"
        create_mock_session(app_data_dir, conv_id, repo_dir, step_count=5)

        watcher = SessionSyncWatcher(
            repo_dir=repo_dir,
            app_data_dir=app_data_dir,
            debounce_seconds=60.0,
            max_timeout=180.0,
        )

        # Enqueue hoạt động nhưng chưa đến hạn debounce
        watcher.scan_changes(now=3000.0)
        assert repo_dir in watcher.pending_workspaces

        # Gọi shutdown() (tương đương SIGINT/SIGTERM/atexit)
        watcher.shutdown()

        # Xác nhận hàng đợi đã được dọn sạch và dữ liệu đã xuất
        assert len(watcher.pending_workspaces) == 0
        sessions_dir = os.path.join(repo_dir, ".sessions")
        assert os.path.exists(os.path.join(sessions_dir, "sessions_index.json"))

        # Kiểm tra tính Idempotent: gọi shutdown lần 2 không gây lỗi
        watcher.shutdown()


def test_multi_workspace_mapping():
    """Kiểm tra Watch-All: 1 watcher phân loại chính xác các phiên vào từng repo tương ứng."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app_data_dir, repo_a = setup_mock_env(tmpdir, "Repo-Alpha")
        repo_b = os.path.realpath(os.path.join(tmpdir, "Repo-Beta"))
        os.makedirs(repo_b, exist_ok=True)

        # Tạo phiên A thuộc Repo-Alpha, phiên B thuộc Repo-Beta
        create_mock_session(app_data_dir, "conv-alpha", repo_a, step_count=3)
        create_mock_session(app_data_dir, "conv-beta", repo_b, step_count=4)

        watcher = SessionSyncWatcher(
            app_data_dir=app_data_dir,
            watch_all=True,
            debounce_seconds=10.0,
            max_timeout=30.0,
        )

        changed = watcher.scan_changes(now=5000.0)
        assert repo_a in changed
        assert repo_b in changed
        assert repo_a in watcher.pending_workspaces
        assert repo_b in watcher.pending_workspaces

        # Flush tất cả
        watcher.flush_all(reason="test")

        # Xác nhận Repo-Alpha chỉ chứa conv-alpha
        index_a_path = os.path.join(repo_a, ".sessions", "sessions_index.json")
        assert os.path.exists(index_a_path)
        with open(index_a_path, "r", encoding="utf-8") as f:
            data_a = json.load(f)
        assert any(c["conversation_id"] == "conv-alpha" for c in data_a["conversations"])
        assert not any(c["conversation_id"] == "conv-beta" for c in data_a["conversations"])

        # Xác nhận Repo-Beta chỉ chứa conv-beta
        index_b_path = os.path.join(repo_b, ".sessions", "sessions_index.json")
        assert os.path.exists(index_b_path)
        with open(index_b_path, "r", encoding="utf-8") as f:
            data_b = json.load(f)
        assert any(c["conversation_id"] == "conv-beta" for c in data_b["conversations"])
        assert not any(c["conversation_id"] == "conv-alpha" for c in data_b["conversations"])


def test_run_once_flag():
    """Kiểm tra cờ --once chạy 1 lượt kiểm tra/flush rồi thoát an toàn."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app_data_dir, repo_dir = setup_mock_env(tmpdir, "RunOnceProject")
        create_mock_session(app_data_dir, "conv-once", repo_dir, step_count=2)

        # 1. Single repo once
        watcher = SessionSyncWatcher(
            repo_dir=repo_dir,
            app_data_dir=app_data_dir,
            watch_all=False,
        )
        res = watcher.run_once()
        assert res["status"] == "success"
        assert res["exported_count"] >= 1
        assert os.path.exists(os.path.join(repo_dir, ".sessions", "sessions_index.json"))

        # 2. Watch-all once
        watcher_all = SessionSyncWatcher(
            app_data_dir=app_data_dir,
            watch_all=True,
        )
        res_all = watcher_all.run_once()
        assert res_all["status"] == "success"
        assert res_all["mode"] == "watch-all"


def test_vbs_launcher_generation():
    """Kiểm tra cú pháp file VBS launcher tàng hình WindowStyle=0."""
    vbs = generate_vbs_launcher(
        python_exe=r"C:\Python312\python.exe",
        script_path=r"D:\Repo\scripts\auto_session_sync.py",
        repo_dir=r"D:\Repo",
    )
    assert 'Set WshShell = CreateObject("WScript.Shell")' in vbs
    assert "WshShell.Run" in vbs
    assert "--watch-all" in vbs
    assert "0, False" in vbs
    assert "Set WshShell = Nothing" in vbs


def test_startup_lifecycle_api(tmp_path):
    """Kiểm tra chu trình API: install_startup -> check_watcher_status -> uninstall_startup."""
    st_dir = tmp_path / "startup"
    app_data = tmp_path / "appdata"
    st_dir.mkdir()
    app_data.mkdir()

    # 1. Cài đặt startup
    res = install_startup(
        app_data_dir=str(app_data),
        startup_dir=str(st_dir),
    )
    assert res["status"] == "success"
    vbs_file = st_dir / VBS_LAUNCHER_NAME
    assert vbs_file.is_file()
    assert "--watch-all" in vbs_file.read_text(encoding="utf-8")
    assert res["pid"] > 0

    # 2. Kiểm tra status khi watcher đang chạy
    status = check_watcher_status(app_data_dir=str(app_data), startup_dir=str(st_dir))
    assert status["status"] == "running"
    assert status["startup_installed"] is True
    assert status["pid"] == res["pid"]

    # 3. Gỡ bỏ startup
    un_res = uninstall_startup(app_data_dir=str(app_data), startup_dir=str(st_dir))
    assert un_res["status"] == "success"
    assert un_res["uninstalled_vbs"] is True
    assert not vbs_file.exists()

    # 4. Kiểm tra status sau khi gỡ bỏ
    post_status = check_watcher_status(app_data_dir=str(app_data), startup_dir=str(st_dir))
    assert post_status["status"] == "stopped"
    assert post_status["startup_installed"] is False


def test_startup_cli_flags(tmp_path):
    """Kiểm tra gọi qua CLI: --install-startup, --status, --uninstall-startup với --startup-dir."""
    import subprocess
    import sys

    st_dir = tmp_path / "startup_cli"
    app_data = tmp_path / "appdata_cli"
    st_dir.mkdir()
    app_data.mkdir()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(repo_root, "scripts", "auto_session_sync.py")

    # 1. CLI --install-startup
    cmd_install = [
        sys.executable, script_path,
        "--install-startup",
        "--startup-dir", str(st_dir),
        "--app-data-dir", str(app_data),
    ]
    p_install = subprocess.run(cmd_install, capture_output=True, text=True, timeout=15)
    assert p_install.returncode == 0, p_install.stderr
    vbs_file = st_dir / VBS_LAUNCHER_NAME
    assert vbs_file.exists()

    # 2. CLI --status
    cmd_status = [
        sys.executable, script_path,
        "--status",
        "--startup-dir", str(st_dir),
        "--app-data-dir", str(app_data),
    ]
    p_status = subprocess.run(cmd_status, capture_output=True, text=True, timeout=10)
    assert p_status.returncode == 0
    assert "RUNNING" in p_status.stdout
    assert "INSTALLED" in p_status.stdout

    # 3. CLI --uninstall-startup
    cmd_uninstall = [
        sys.executable, script_path,
        "--uninstall-startup",
        "--startup-dir", str(st_dir),
        "--app-data-dir", str(app_data),
    ]
    p_uninstall = subprocess.run(cmd_uninstall, capture_output=True, text=True, timeout=15)
    assert p_uninstall.returncode == 0
    assert not vbs_file.exists()

    # 4. CLI --status sau khi gỡ
    p_status_after = subprocess.run(cmd_status, capture_output=True, text=True, timeout=10)
    assert p_status_after.returncode == 0
    assert "STOPPED" in p_status_after.stdout
    assert "NOT INSTALLED" in p_status_after.stdout

