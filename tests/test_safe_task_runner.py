"""Unit tests for safe_task_runner (Execution Timeout & Safe Process Guard)."""

import sys
from pathlib import Path
import pytest
from scripts.safe_task_runner import run_command_with_timeout, TIMEOUT_EXIT_CODE
from scripts.safe_com_runner import safe_convert_doc, safe_convert_xls


def test_safe_runner_success():
    cmd = [sys.executable, "-c", "print('hello from safe runner')"]
    res = run_command_with_timeout(cmd, timeout_sec=5.0)
    assert res["status"] == "SUCCESS"
    assert res["exit_code"] == 0
    assert not res["timed_out"]
    assert "hello from safe runner" in res["stdout"]


def test_safe_runner_timeout():
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    res = run_command_with_timeout(cmd, timeout_sec=1.0)
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
