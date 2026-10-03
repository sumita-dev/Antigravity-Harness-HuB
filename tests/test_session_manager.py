"""
tests/test_session_manager.py

Unit tests cho module Zero-Friction Portable Session Sync (scripts/session_manager.py).
Kiểm tra toàn diện:
1. path_to_workspace_uri & normalize_uri_or_path
2. export_sessions (quét db, lọc workspace, copy db & brain, ghi metadata)
3. import_sessions (khôi phục db & brain, rewrite workspace URI & app_data_dir, idempotency)
4. Xử lý lỗi ngoại lệ (db trống, thiếu index, đường dẫn không hợp lệ)
"""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
import pytest

from scripts.session_manager import (
    path_to_workspace_uri,
    normalize_uri_or_path,
    safe_copy_sqlite,
    ensure_conversation_summaries_table,
    export_sessions,
    import_sessions,
)


def test_path_to_workspace_uri():
    # Test đường dẫn Windows có ổ đĩa
    uri_win = path_to_workspace_uri("D:\\AntiGravity\\MyProject")
    assert uri_win == "file:///d%3A/AntiGravity/MyProject"

    # Test lowercase drive normalization
    uri_c = path_to_workspace_uri("c:/work/test")
    assert uri_c == "file:///c%3A/work/test"


def test_normalize_uri_or_path():
    uri = "file:///d%3A/AntiGravity/MyProject"
    norm = normalize_uri_or_path(uri)
    expected = os.path.normcase(os.path.normpath("d:/AntiGravity/MyProject"))
    assert norm == expected

    plain_path = "D:\\AntiGravity\\MyProject"
    assert normalize_uri_or_path(plain_path) == expected


def setup_mock_antigravity_env(base_dir, repo_name="Project-Alpha"):
    """Tạo cấu trúc giả lập app_data_dir và repo_dir."""
    app_data_dir = os.path.join(base_dir, "antigravity_app_data")
    repo_dir = os.path.join(base_dir, repo_name)
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


def create_mock_conversation(app_data_dir, conv_id, title, workspace_path, has_brain=True):
    """Tạo một phiên hội thoại giả lập trong SQLite, file .db và thư mục brain."""
    db_path = os.path.join(app_data_dir, "conversation_summaries.db")
    ws_uri = path_to_workspace_uri(workspace_path)
    ws_uris_json = json.dumps([ws_uri])

    # 1. Chèn vào SQLite
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO conversation_summaries (
                conversation_id, title, preview, step_count, last_modified_time,
                workspace_uris, status, source, app_data_dir, raw_summary, last_user_input_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                title,
                f"Preview for {title}",
                5,
                datetime.now(timezone.utc).isoformat(),
                ws_uris_json,
                "DONE",
                "USER",
                "antigravity",
                b"\x08\x01\x12\x04test",  # Giả lập protobuf blob
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # 2. Tạo file conversation db
    conv_db_path = os.path.join(app_data_dir, "conversations", f"{conv_id}.db")
    c_conn = sqlite3.connect(conv_db_path)
    try:
        c_conn.execute("CREATE TABLE mock_steps (id int, content text);")
        c_conn.execute("INSERT INTO mock_steps VALUES (1, 'Step 1 output');")
        c_conn.commit()
    finally:
        c_conn.close()

    # 3. Tạo thư mục brain nếu cần
    if has_brain:
        conv_brain_dir = os.path.join(app_data_dir, "brain", conv_id)
        os.makedirs(os.path.join(conv_brain_dir, "scratch"), exist_ok=True)
        with open(os.path.join(conv_brain_dir, "scratch", "note.txt"), "w", encoding="utf-8") as f:
            f.write("Brain scratch content")


def test_export_sessions():
    with tempfile.TemporaryDirectory() as temp_root:
        app_data_dir, repo_dir = setup_mock_antigravity_env(temp_root, "Test-Repo")
        other_repo_dir = os.path.join(temp_root, "Other-Project")
        os.makedirs(other_repo_dir, exist_ok=True)

        # Tạo 2 conversation: 1 thuộc Test-Repo, 1 thuộc Other-Project
        create_mock_conversation(app_data_dir, "conv-001", "Phiên Alpha", repo_dir)
        create_mock_conversation(app_data_dir, "conv-002", "Phiên Beta", other_repo_dir)

        # Thực thi export cho Test-Repo
        res = export_sessions(repo_dir=repo_dir, app_data_dir=app_data_dir)
        assert res["status"] == "success"
        assert res["exported_count"] == 1
        assert "conv-001" in res["conversations"]
        assert "conv-002" not in res["conversations"]

        # Kiểm tra cấu trúc thư mục .sessions được tạo ra
        sessions_dir = os.path.join(repo_dir, ".sessions")
        assert os.path.exists(sessions_dir)
        assert os.path.exists(os.path.join(sessions_dir, "conv-001", "conv-001.db"))
        assert os.path.exists(os.path.join(sessions_dir, "conv-001", "brain", "scratch", "note.txt"))

        # Kiểm tra file index
        index_file = os.path.join(sessions_dir, "sessions_index.json")
        assert os.path.exists(index_file)
        with open(index_file, "r", encoding="utf-8") as f:
            idx = json.load(f)
        assert idx["count"] == 1
        assert idx["conversations"][0]["conversation_id"] == "conv-001"
        assert idx["conversations"][0]["raw_summary_b64"] is not None


def test_import_sessions_to_new_machine_and_rewrite():
    with tempfile.TemporaryDirectory() as temp_root:
        # Bước 1: Máy A export
        app_data_a, repo_a = setup_mock_antigravity_env(temp_root, "MachineA-Repo")
        create_mock_conversation(app_data_a, "conv-sync-100", "Portable Session", repo_a)
        exp_res = export_sessions(repo_dir=repo_a, app_data_dir=app_data_a)
        assert exp_res["status"] == "success"

        # Bước 2: Giả lập chuyển repo sang Máy B tại một ổ đĩa / thư mục khác
        repo_b = os.path.join(temp_root, "MachineB-Copied-Repo")
        shutil.copytree(repo_a, repo_b)

        # Máy B có app_data_dir hoàn toàn mới, chưa từng chạy phiên nào
        app_data_b = os.path.join(temp_root, "MachineB-AppData")

        # Bước 3: Thực thi import trên Máy B
        imp_res = import_sessions(repo_dir=repo_b, app_data_dir=app_data_b)
        assert imp_res["status"] == "success"
        assert imp_res["imported_count"] == 1
        assert "conv-sync-100" in imp_res["conversations"]

        # Kiểm tra các file được khôi phục trên Máy B
        target_db = os.path.join(app_data_b, "conversations", "conv-sync-100.db")
        assert os.path.exists(target_db)

        # Kiểm tra dữ liệu trong db phiên con
        conn = sqlite3.connect(target_db)
        try:
            cur = conn.cursor()
            cur.execute("SELECT content FROM mock_steps WHERE id = 1;")
            assert cur.fetchone()[0] == "Step 1 output"
        finally:
            conn.close()

        target_brain = os.path.join(app_data_b, "brain", "conv-sync-100", "scratch", "note.txt")
        assert os.path.exists(target_brain)

        # Kiểm tra SQLite conversation_summaries.db trên Máy B đã được rewrite đường dẫn mới
        summary_db = os.path.join(app_data_b, "conversation_summaries.db")
        assert os.path.exists(summary_db)

        s_conn = sqlite3.connect(summary_db)
        try:
            cur = s_conn.cursor()
            cur.execute("SELECT workspace_uris, raw_summary, title FROM conversation_summaries WHERE conversation_id = 'conv-sync-100';")
            row = cur.fetchone()
            assert row is not None
            uris_stored = json.loads(row[0])
            expected_new_uri = path_to_workspace_uri(repo_b)
            assert uris_stored == [expected_new_uri]
            assert row[1] == b"\x08\x01\x12\x04test"  # Protobuf blob restored
            assert row[2] == "Portable Session"
        finally:
            s_conn.close()


def test_import_idempotency():
    with tempfile.TemporaryDirectory() as temp_root:
        app_data_dir, repo_dir = setup_mock_antigravity_env(temp_root, "Idempotent-Repo")
        create_mock_conversation(app_data_dir, "conv-idem", "Idempotent Test", repo_dir)
        export_sessions(repo_dir=repo_dir, app_data_dir=app_data_dir)

        # Chạy import lần 1
        res1 = import_sessions(repo_dir=repo_dir, app_data_dir=app_data_dir)
        assert res1["status"] == "success"

        # Chạy import lần 2 (cùng database đích)
        res2 = import_sessions(repo_dir=repo_dir, app_data_dir=app_data_dir)
        assert res2["status"] == "success"

        # Đảm bảo không bị duplicate row
        summary_db = os.path.join(app_data_dir, "conversation_summaries.db")
        conn = sqlite3.connect(summary_db)
        try:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM conversation_summaries WHERE conversation_id = 'conv-idem';")
            assert cur.fetchone()[0] == 1
        finally:
            conn.close()


def test_error_handling():
    with tempfile.TemporaryDirectory() as temp_root:
        # 1. Export khi không có DB
        res_exp = export_sessions(repo_dir=temp_root, app_data_dir=os.path.join(temp_root, "non_existent"))
        assert res_exp["status"] == "error"

        # 2. Import khi không có sessions_index.json
        res_imp = import_sessions(repo_dir=temp_root, app_data_dir=temp_root)
        assert res_imp["status"] == "error"
