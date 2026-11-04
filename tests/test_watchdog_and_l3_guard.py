"""Unit tests for ProcessWatchdog & L3BranchGuard (Harness 2.0 / Super-Agent Architecture).

Tests:
1. ProcessWatchdog: Real subprocess registration, hung detection, termination, and sweep.
2. L3BranchGuard: Enforcing secondary branch isolation, blocking direct merge to main, and requiring human gate approval.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import pytest

from harness.subagent_guard import (
    FAST_TIER_TIMEOUT,
    FULL_TIER_TIMEOUT,
    L3BranchGuard,
    MonitoredProcess,
    ProcessWatchdog,
    enforce_l3_branch_policy,
    get_deadman_timeout,
)


# ==============================================================================
# 1. Tests for ProcessWatchdog
# ==============================================================================


def test_process_watchdog_tier_timeouts():
    """Kiểm tra thời gian timeout theo phân tầng fast vs full."""
    assert get_deadman_timeout("fast") == FAST_TIER_TIMEOUT == 45
    assert get_deadman_timeout("smoke") == FAST_TIER_TIMEOUT == 45
    assert get_deadman_timeout("full") == FULL_TIER_TIMEOUT == 240
    assert get_deadman_timeout("batch") == FULL_TIER_TIMEOUT == 240


def test_process_watchdog_hung_detection_and_termination():
    """Kiểm tra ProcessWatchdog phát hiện và kết thúc tiến trình thực sự bị treo."""
    watchdog = ProcessWatchdog()

    # Khởi chạy một subprocess sleep 10 giây
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pid = proc.pid

    try:
        # Đăng ký với timeout 1 giây
        item = watchdog.register_process(pid=pid, timeout=1, tier="fast", proc=proc)
        assert item.pid == pid
        assert item.timeout == 1

        # Ngay sau khi spawn: chưa bị treo
        assert watchdog.is_process_hung(pid) is False
        assert proc.poll() is None  # Vẫn đang chạy

        # Đợi 1.2 giây để kích hoạt ngưỡng hung
        time.sleep(1.2)

        # Đã bị hung
        assert watchdog.is_process_hung(pid) is True
        assert watchdog.get_elapsed_time(pid) >= 1.0

        # Terminate tiến trình treo
        terminated = watchdog.terminate_hung_process(pid)
        assert terminated is True

        # Đợi tiến trình dừng hoàn toàn
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

        assert proc.poll() is not None  # Tiến trình đã kết thúc

    finally:
        # Dọn dẹp an toàn trong khối finally
        if proc.poll() is None:
            proc.kill()


def test_process_watchdog_sweep_all_hung():
    """Kiểm tra sweep_all_hung quét và diệt hàng loạt tiến trình treo."""
    watchdog = ProcessWatchdog()

    proc1 = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.DEVNULL,
    )
    proc2 = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.DEVNULL,
    )

    try:
        watchdog.register_process(pid=proc1.pid, timeout=1, proc=proc1, name="worker_1")
        watchdog.register_process(pid=proc2.pid, timeout=1, proc=proc2, name="worker_2")

        # Chờ vượt timeout
        time.sleep(1.2)

        swept = watchdog.sweep_all_hung()
        swept_pids = [s.pid for s in swept]

        assert proc1.pid in swept_pids
        assert proc2.pid in swept_pids

        # Cả hai tiến trình đều đã bị kết thúc
        proc1.wait(timeout=3)
        proc2.wait(timeout=3)
        assert proc1.poll() is not None
        assert proc2.poll() is not None

    finally:
        for p in (proc1, proc2):
            if p.poll() is None:
                p.kill()


# ==============================================================================
# 2. Tests for L3BranchGuard & enforce_l3_branch_policy
# ==============================================================================


def test_l3_branch_guard_rejects_empty_branch():
    """Kiểm tra nhánh rỗng bị từ chối với INVALID_BRANCH."""
    res = enforce_l3_branch_policy("")
    assert res["is_allowed"] is False
    assert res["status"] == "INVALID_BRANCH"
    assert res["requires_human_gate"] is True


@pytest.mark.parametrize("branch", ["main", "master", "release", "prod", "production"])
def test_l3_branch_guard_rejects_direct_operations_on_protected_branches(branch: str):
    """Kiểm tra mọi thao tác trực tiếp trên nhánh chính bị chặn hoàn toàn."""
    res = enforce_l3_branch_policy(branch, target_branch="main")
    assert res["is_allowed"] is False
    assert res["status"] == "REJECTED_DIRECT_MERGE"
    assert "prohibited" in res["message"].lower()
    assert res["requires_human_gate"] is True


def test_l3_branch_guard_accepts_secondary_branch_and_requires_approval():
    """Kiểm tra nhánh phụ hợp lệ được chấp nhận kèm trạng thái AWAITING_HUMAN_APPROVAL."""
    # Nhánh fix
    res_fix = enforce_l3_branch_policy("fix/issue-101", target_branch="main")
    assert res_fix["is_allowed"] is True
    assert res_fix["status"] == "AWAITING_HUMAN_APPROVAL"
    assert res_fix["requires_human_gate"] is True
    assert "PR Draft required" in res_fix["message"]

    # Nhánh feature
    res_feat = L3BranchGuard.enforce("feature/superagent-pipeline", target_branch="main")
    assert res_feat["is_allowed"] is True
    assert res_feat["status"] == "AWAITING_HUMAN_APPROVAL"

    # Nhánh agent
    res_agent = enforce_l3_branch_policy("agent/repro-tests", target_branch="master")
    assert res_agent["is_allowed"] is True
    assert res_agent["status"] == "AWAITING_HUMAN_APPROVAL"
