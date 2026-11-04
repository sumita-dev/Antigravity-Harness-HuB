"""Unit tests for GitHub Event Watcher & Deterministic Pre-LLM Filter.

Tests:
1. EventFilter: Bot filtering, deduplication, ANSI/HTML stripping, and 40-line log windowing.
2. GitHubEventWatcher: Mocking `gh` CLI, verifying --once and --dry-run flows.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List
import pytest

from harness.validators.event_filter import (
    DEFAULT_BOT_PATTERNS,
    EventFilter,
    FilterResult,
    clean_and_truncate_log,
)
from harness.runners.event_watcher import GitHubEventWatcher, main, parse_args


# ==============================================================================
# 1. Tests for EventFilter
# ==============================================================================


def test_event_filter_detects_and_rejects_bots():
    """Kiểm tra bot (dependabot, github-actions) bị từ chối không tốn LLM token."""
    ef = EventFilter()

    # Dependabot
    bot_issue = {
        "number": 1,
        "title": "Bump lodash from 4.17.20 to 4.17.21",
        "body": "Bumps lodash to address vulnerability.",
        "author": {"login": "dependabot[bot]"},
    }
    res = ef.filter_issue(bot_issue)
    assert res.is_accepted is False
    assert "BOT_AUTHOR" in res.reason

    # GitHub Actions
    gha_issue = {
        "number": 2,
        "title": "CI failure notification",
        "body": "Automated workflow failure report",
        "author": "github-actions[bot]",
    }
    res2 = ef.filter_issue(gha_issue)
    assert res2.is_accepted is False
    assert "BOT_AUTHOR" in res2.reason

    # Human developer
    human_issue = {
        "number": 3,
        "title": "Payment gateway timeout on checkout",
        "body": "User encounters 504 error when clicking Pay.",
        "author": {"login": "developer-alice"},
    }
    res3 = ef.filter_issue(human_issue)
    assert res3.is_accepted is True
    assert res3.reason == "ACCEPTED"
    assert res3.cleaned_payload["title"] == "Payment gateway timeout on checkout"


def test_event_filter_deduplication():
    """Kiểm tra khử trùng lặp sự kiện dựa trên SHA256 hash."""
    ef = EventFilter()
    issue = {
        "number": 42,
        "title": "Database connection drop",
        "body": "Connection refused at 127.0.0.1:5432",
        "author": {"login": "dev_bob"},
    }

    # Lần 1: Chấp nhận
    res1 = ef.filter_issue(issue)
    assert res1.is_accepted is True
    assert res1.reason == "ACCEPTED"

    # Lần 2 với cùng nội dung: Bị loại do trùng lặp
    res2 = ef.filter_issue(issue)
    assert res2.is_accepted is False
    assert res2.reason == "DUPLICATE_ISSUE"


def test_clean_and_truncate_log_strips_ansi_and_html():
    """Kiểm tra làm sạch mã màu ANSI và thẻ HTML."""
    raw_log = "\x1B[31m\x1B[1mError: Connection timeout\x1B[0m\n<p>HTML paragraph</p>"
    cleaned = clean_and_truncate_log(raw_log)

    assert "\x1B[" not in cleaned
    assert "<p>" not in cleaned
    assert "</p>" not in cleaned
    assert "Error: Connection timeout" in cleaned
    assert "HTML paragraph" in cleaned


def test_clean_and_truncate_log_windows_core_40_lines():
    """Kiểm tra cắt gọt log dài về đúng tối đa 40 dòng quanh frame lỗi."""
    # Tạo log 120 dòng với lỗi traceback ở dòng 80
    lines = [f"Info line {i}" for i in range(120)]
    lines[80] = "Traceback (most recent call last):"
    lines[81] = "  File 'app.py', line 45, in process"
    lines[82] = "ZeroDivisionError: division by zero"
    lines[83] = "FAILED tests/test_app.py::test_process"

    long_log = "\n".join(lines)
    cleaned = clean_and_truncate_log(long_log, max_lines=40)

    result_lines = cleaned.splitlines()
    assert len(result_lines) <= 40
    assert "ZeroDivisionError: division by zero" in cleaned
    assert "Traceback (most recent call last):" in cleaned


def test_event_filter_ci_failure():
    """Kiểm tra lọc và xử lý CI failure thành công."""
    ef = EventFilter()
    run_data = {
        "databaseId": 123456,
        "name": "Integration Tests",
        "headBranch": "feature/checkout",
        "headSha": "abc123def456",
        "url": "https://github.com/org/repo/actions/runs/123456",
        "actor": {"login": "human-tester"},
    }
    raw_log = "Run tests\n" * 50 + "FAILED tests/test_payment.py\nAssertionError: 500 != 200\n"

    res = ef.filter_ci_failure(run_data, raw_log)
    assert res.is_accepted is True
    assert res.reason == "ACCEPTED"
    assert res.cleaned_payload["source"] == "github_ci"
    assert "AssertionError: 500 != 200" in res.cleaned_payload["cleaned_log"]

    # Thử lại cùng run_id -> Bị khử trùng
    res_dup = ef.filter_ci_failure(run_data, raw_log)
    assert res_dup.is_accepted is False
    assert res_dup.reason == "DUPLICATE_CI_RUN"


# ==============================================================================
# 2. Tests for GitHubEventWatcher
# ==============================================================================


def test_event_watcher_once_and_dry_run():
    """Kiểm tra GitHubEventWatcher với cờ --once và dry_run=True."""
    mock_issues = [
        {
            "number": 10,
            "title": "Bug in authentication",
            "body": "User cannot login with Google SSO",
            "author": {"login": "lead-qa"},
            "labels": [{"name": "bug"}],
            "url": "https://github.com/org/repo/issues/10",
        },
        {
            "number": 11,
            "title": "Dependabot bump",
            "body": "Bump package",
            "author": {"login": "dependabot[bot]"},
            "labels": [],
            "url": "https://github.com/org/repo/issues/11",
        },
    ]

    mock_runs = [
        {
            "databaseId": 98765,
            "name": "Nightly Build",
            "headBranch": "main",
            "headSha": "987abc",
            "url": "https://github.com/org/repo/actions/runs/98765",
            "actor": {"login": "ci-user"},
        }
    ]

    def mock_runner(cmd: List[str]) -> subprocess.CompletedProcess:
        cmd_str = " ".join(cmd)
        if "issue" in cmd_str and "list" in cmd_str:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps(mock_issues), stderr=""
            )
        elif "run" in cmd_str and "list" in cmd_str:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps(mock_runs), stderr=""
            )
        elif "run" in cmd_str and "view" in cmd_str:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="FAILED tests/test_core.py\nError: NullPointer", stderr=""
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    watcher = GitHubEventWatcher(
        repo="my-org/my-repo",
        dry_run=True,
        command_runner=mock_runner,
    )

    tasks = watcher.poll_once()

    # Issue 10 (chấp nhận) + CI run 98765 (chấp nhận) = 2 tasks
    # Issue 11 (dependabot) bị loại
    assert len(tasks) == 2

    issue_task = next(t for t in tasks if t["source"] == "github_issue")
    assert "Bug in authentication" in issue_task["title"]
    assert issue_task["dry_run"] is True

    ci_task = next(t for t in tasks if t["source"] == "github_ci")
    assert "Resolve CI Failure in Nightly Build" in ci_task["title"]
    assert ci_task["dry_run"] is True


def test_event_watcher_dispatcher_callback():
    """Kiểm tra dispatcher callback được kích hoạt khi không chạy dry-run."""
    dispatched_items = []

    def mock_runner(cmd: List[str]) -> subprocess.CompletedProcess:
        cmd_str = " ".join(cmd)
        if "issue" in cmd_str:
            issues = [
                {
                    "number": 50,
                    "title": "Crash on file upload",
                    "body": "MemoryError when uploading 2GB file",
                    "author": {"login": "user-smith"},
                }
            ]
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps(issues), stderr=""
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

    def custom_dispatcher(payload: Dict[str, Any]):
        dispatched_items.append(payload)

    watcher = GitHubEventWatcher(
        dry_run=False,
        command_runner=mock_runner,
        dispatcher_callback=custom_dispatcher,
    )

    tasks = watcher.poll_once()
    assert len(tasks) == 1
    assert len(dispatched_items) == 1
    assert dispatched_items[0]["payload"]["issue_number"] == 50


def test_event_watcher_main_cli_once_dry_run(monkeypatch):
    """Kiểm tra entrypoint CLI với các tham số --once và --dry-run."""
    # Mock subprocess.run để không gọi gh thật
    def mock_subprocess_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="[]", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    exit_code = main(["--once", "--dry-run", "--interval", "5", "--repo", "owner/repo"])
    assert exit_code == 0
