"""Tests for Ephemeral Database Sandbox (Pillar 5)."""

import os
from pathlib import Path
import pytest
import sqlite3

from scripts.db_sandbox import DatabaseSandbox


def test_db_sandbox_sqlite_direct():
    with DatabaseSandbox(db_type="sqlite", db_name="test_app") as db:
        url = db.get_connection_url()
        assert url.startswith("sqlite:///")
        assert db.actual_db_type == "sqlite"
        assert db.temp_dir is not None
        assert os.path.exists(db.temp_dir)

        # Test ghi/đọc SQLite thực tế
        db_file = db.sqlite_file_path
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        cur.execute("INSERT INTO users (name) VALUES ('Alice');")
        conn.commit()

        cur.execute("SELECT name FROM users;")
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Alice"
        conn.close()

    # Sau khi thoát context manager, temp_dir phải bị dọn dẹp sạch sẽ
    assert not os.path.exists(db.temp_dir or "/tmp/does_not_exist")


def test_db_sandbox_graceful_fallback(monkeypatch):
    """Khi Docker không khả dụng, DatabaseSandbox(db_type='postgres') phải tự động fallback sang sqlite."""
    monkeypatch.setattr(DatabaseSandbox, "is_docker_available", staticmethod(lambda: False))

    with DatabaseSandbox(db_type="postgres", db_name="test_pg") as db:
        url = db.get_connection_url()

        assert url.startswith("sqlite:///")
        assert db.actual_db_type == "sqlite"
        assert db.container_id is None
        assert db.temp_dir is not None
        assert os.path.exists(db.temp_dir)

    # Dọn dẹp sau khi thoát
    assert not os.path.exists(db.temp_dir or "/tmp/does_not_exist")
