"""Tests cho scripts/generate_launcher.py và scripts/run_dev_logger.py."""

import http.server
import socket
import threading
from pathlib import Path

import pytest

from scripts.generate_launcher import generate_launcher
from scripts.run_dev_logger import is_port_in_use, wait_for_http_ok


def test_generate_launcher_node_app(tmp_path: Path):
    bat, doc = generate_launcher(
        app_dir=tmp_path,
        port=5173,
        start_cmd="npm run dev",
        title="Vite App",
        data_file="data/mockData.json",
    )

    assert bat.exists()
    assert doc.exists()

    bat_text = bat.read_text(encoding="utf-8")
    assert "Port: 5173" in bat_text
    assert "npm run dev" in bat_text
    assert "where node >nul 2>nul" in bat_text
    assert "http://localhost:5173" in bat_text

    doc_text = doc.read_text(encoding="utf-8")
    assert "Vite App" in doc_text
    assert "http://localhost:5173" in doc_text
    assert "data/mockData.json" in doc_text
    assert "start-app.bat" in doc_text


def test_generate_launcher_python_app(tmp_path: Path):
    bat, doc = generate_launcher(
        app_dir=tmp_path,
        port=8000,
        start_cmd="python main.py",
        title="Python Tool",
        data_file="seed.json",
    )

    assert bat.exists()
    assert doc.exists()

    bat_text = bat.read_text(encoding="utf-8")
    assert "where python >nul 2>nul" in bat_text
    assert "http://localhost:8000" in bat_text

    doc_text = doc.read_text(encoding="utf-8")
    assert "seed.json" in doc_text


def test_is_port_in_use():
    # Mở một socket tạm thời trên localhost để chiếm port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]

        assert is_port_in_use(port) is True

    # Sau khi đóng, port không còn in use (hoặc khả dụng)
    # Có thể cần một port ngẫu nhiên chưa ai dùng
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
        s2.bind(("127.0.0.1", 0))
        free_port = s2.getsockname()[1]
    assert is_port_in_use(free_port) is False


def test_wait_for_http_ok():
    class SimpleHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), SimpleHandler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    ok = wait_for_http_ok(f"http://127.0.0.1:{port}", timeout=5.0)
    assert ok is True
    server.server_close()


def test_wait_for_http_ok_timeout():
    # Thăm dò một port không có server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    ok = wait_for_http_ok(f"http://127.0.0.1:{free_port}", timeout=1.0)
    assert ok is False
