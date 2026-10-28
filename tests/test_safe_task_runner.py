"""Unit tests for safe_task_runner (Execution Timeout & Safe Process Guard)."""

import sys
from pathlib import Path
import pytest
from scripts.safe_task_runner import (
    run_command_with_timeout,
    sanitize_stream_command,
    TIMEOUT_EXIT_CODE,
)
from scripts.safe_com_runner import safe_convert_doc, safe_convert_xls


def test_safe_runner_success():
    cmd = [sys.executable, "-c", "print('hello from safe runner')"]
    res = run_command_with_timeout(cmd, timeout_sec=5.0)
    assert res["status"] == "SUCCESS"
    assert res["exit_code"] == 0
    assert not res["timed_out"]
    assert "hello from safe runner" in res["stdout"]


def test_safe_runner_timeout():
    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    res = run_command_with_timeout(cmd, timeout_sec=0.5)
    assert res["status"] == "TIMEOUT"
    assert res["exit_code"] == TIMEOUT_EXIT_CODE
    assert res["timed_out"] is True
    assert "[SAFE_RUNNER_TIMEOUT]" in res["stderr"]


def test_safe_com_rejects_pdf():
    ok, msg = safe_convert_doc(Path("dummy_file.pdf"))
    assert ok is False
    assert "CẤM: Không được sử dụng Word COM để mở PDF" in msg


def test_safe_com_missing_file():
    ok, msg = safe_convert_doc(Path("non_existent_file.doc"))
    assert ok is False
    assert "File không tồn tại" in msg


def test_safe_runner_stdin_devnull_prevents_hang():
    """Kiểm tra lệnh đọc stdin hoàn thành ngay lập tức và không bị treo nhờ stdin=subprocess.DEVNULL."""
    cmd = [sys.executable, "-c", "import sys; sys.stdin.read()"]
    res = run_command_with_timeout(cmd, timeout_sec=3.0)
    assert res["status"] == "SUCCESS"
    assert res["exit_code"] == 0
    assert not res["timed_out"]
    assert res["elapsed_sec"] < 2.5


def test_sanitize_stream_command():
    """Kiểm tra lệnh rg/grep thiếu path được tự động bổ sung '.' an toàn."""
    # List format: thiếu path -> tự động thêm '.'
    assert sanitize_stream_command(["rg", "-i", "pattern"]) == ["rg", "-i", "pattern", "."]
    assert sanitize_stream_command(["rg", "-i", "pattern", "-g", "!*.pyc"]) == ["rg", "-i", "pattern", "-g", "!*.pyc", "."]

    # List format: đã có path -> giữ nguyên
    assert sanitize_stream_command(["rg", "-i", "pattern", "."]) == ["rg", "-i", "pattern", "."]
    assert sanitize_stream_command(["rg", "foo", "src/"]) == ["rg", "foo", "src/"]

    # String format: thiếu path -> tự động thêm ' .'
    assert sanitize_stream_command('rg -i "pattern"') == 'rg -i "pattern" .'
    assert sanitize_stream_command('rg -i "pattern" -g "!*.pyc"') == 'rg -i "pattern" -g "!*.pyc" .'

    # String format: đã có path -> giữ nguyên
    assert sanitize_stream_command('rg -i "pattern" .') == 'rg -i "pattern" .'
    assert sanitize_stream_command('rg -i "pattern" -g "!*.pyc" .') == 'rg -i "pattern" -g "!*.pyc" .'

    # Grep commands
    assert sanitize_stream_command(["grep", "-rn", "TODO"]) == ["grep", "-rn", "TODO", "."]
    assert sanitize_stream_command(["grep", "-rn", "TODO", "."]) == ["grep", "-rn", "TODO", "."]

    # Lệnh khác (python, git) không bị ảnh hưởng
    py_cmd = [sys.executable, "-c", "print(1)"]
    assert sanitize_stream_command(py_cmd) == py_cmd
