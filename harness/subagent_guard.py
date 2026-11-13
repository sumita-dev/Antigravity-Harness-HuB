#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness/subagent_guard.py

Hệ Thống Giám Sát & Vệ Sinh Tiến Trình SubAgent (SubAgent Hygiene & Process Guard).
Ngăn chặn tiến trình mồ côi (orphaned processes), rò rỉ file khóa (orphan locks),
quản lý Dead-man's Switch động theo phân tầng nhiệm vụ và dọn dẹp sau chu trình Triad.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

# Cấu hình Dead-man Switch theo phân tầng test/task
FAST_TIER_TIMEOUT = 45   # 45 giây cho fast-tier / smoke checks
FULL_TIER_TIMEOUT = 240  # 240 giây cho full test suite / batch tasks
import time


def get_deadman_timeout(tier: str = "full") -> int:
    """Trả về thời gian Dead-man's Switch (giây) tương ứng với phân tầng nhiệm vụ.
    
    Args:
        tier: Phân tầng thực thi ('fast', 'smoke', 'full', 'batch', etc.)
    Returns:
        45 (giây) nếu là fast/smoke; 240 (giây) nếu là full/batch.
    """
    normalized = str(tier).lower().strip()
    if normalized in ("fast", "smoke"):
        return FAST_TIER_TIMEOUT
    return FULL_TIER_TIMEOUT


@dataclass
class SubagentInfo:
    """Thông tin tiến trình hoặc tác tử được giám sát."""
    pid: int
    name: str
    cmdline: List[str] = field(default_factory=list)
    status: str = "running"  # "running", "idle", "orphaned", "terminated"
    parent_pid: Optional[int] = None
    parent_alive: bool = True
    is_orphaned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Export alias theo yêu cầu chuẩn hóa QA Auditor
SubAgentState = SubagentInfo


class SubagentGuard:
    """Tiện ích phát hiện và dọn dẹp subagents mồ côi/idle."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = Path(repo_root or REPO_ROOT).resolve()

    def list_active_subagents(self) -> List[SubagentInfo]:
        """Liệt kê các tiến trình subagent hoặc background runners đang hoạt động."""
        results: List[SubagentInfo] = []
        try:
            import psutil
        except ImportError:
            return results

        current_pid = os.getpid()
        try:
            current_proc = psutil.Process(current_pid)
            parent_pid = current_proc.parent().pid if current_proc.parent() else None
        except Exception:
            parent_pid = None

        ignored_pids = {current_pid}
        if parent_pid:
            ignored_pids.add(parent_pid)

        # Từ khóa nhận diện subagents/runners của Antigravity
        subagent_keywords = [
            "run_harness.py",
            "dispatch_subagents.py",
            "subagent",
            "session_guard.py",
            "lint_migration_safety.py",
            "audit_desktop_binary_tamper.py",
            "check_loop_thresholds.py",
        ]

        for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid", "status"]):
            try:
                pid = proc.info.get("pid")
                if not pid or pid in ignored_pids:
                    continue

                cmdline = proc.info.get("cmdline") or []
                cmd_str = " ".join(cmdline).lower()

                # Kiểm tra xem có phải tiến trình subagent / test runner không
                is_subagent_proc = any(kw.lower() in cmd_str for kw in subagent_keywords)

                if is_subagent_proc:
                    ppid = proc.info.get("ppid")
                    parent_alive = False
                    if ppid:
                        try:
                            parent_proc = psutil.Process(ppid)
                            parent_alive = parent_proc.is_running() and parent_proc.status() != psutil.STATUS_ZOMBIE
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            parent_alive = False

                    is_orphaned = not parent_alive

                    results.append(
                        SubagentInfo(
                            pid=pid,
                            name=proc.info.get("name") or "python",
                            cmdline=cmdline,
                            status="orphaned" if is_orphaned else "running",
                            parent_pid=ppid,
                            parent_alive=parent_alive,
                            is_orphaned=is_orphaned,
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return results

    def list_idle(self) -> List[SubagentInfo]:
        """Liệt kê các subagents đang ở trạng thái idle hoặc orphaned."""
        return [sa for sa in self.list_active_subagents() if sa.status == "idle" or sa.is_orphaned]

    def detect_orphaned_subagents(self) -> List[SubagentInfo]:
        """Lọc ra các tiến trình subagents mồ côi (tiến trình cha đã chết)."""
        all_subagents = self.list_active_subagents()
        return [sa for sa in all_subagents if sa.is_orphaned]

    def scan_orphan_locks(self) -> List[Path]:
        """Quét các file .lock mồ côi trong .brain/."""
        locks: List[Path] = []
        for workflow_dir in [
            self.repo_root / ".brain" / "app_workflows",
            self.repo_root / ".brain" / "marketing_workflows",
            self.repo_root / ".brain",
        ]:
            if workflow_dir.is_dir():
                locks.extend(workflow_dir.glob("*.lock"))
        return locks

    def cleanup_subagents(
        self,
        target_pids: Optional[List[int]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Dọn dẹp an toàn các tiến trình subagent mồ côi hoặc theo danh sách PID."""
        terminated: List[int] = []
        failed: List[int] = []

        try:
            import psutil
        except ImportError:
            return {"terminated": [], "failed": [], "cleaned_locks": [], "dry_run": dry_run}

        if target_pids is not None:
            pids_to_kill = target_pids
        else:
            orphaned = self.detect_orphaned_subagents()
            pids_to_kill = [sa.pid for sa in orphaned]

        for pid in pids_to_kill:
            if pid == os.getpid():
                continue
            try:
                proc = psutil.Process(pid)
                if not dry_run:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                terminated.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                failed.append(pid)

        # Dọn dẹp orphan locks
        cleaned_locks: List[str] = []
        for lock in self.scan_orphan_locks():
            cleaned_locks.append(str(lock))
            if not dry_run:
                try:
                    lock.unlink(missing_ok=True)
                except Exception:
                    pass

        return {
            "terminated": terminated,
            "failed": failed,
            "cleaned_locks": cleaned_locks,
            "dry_run": dry_run,
        }

    def cleanup_triad_cycle(
        self,
        cycle_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Dọn dẹp tài nguyên và trạng thái sau khi hoàn thành chu trình Dynamic Triad."""
        result = self.cleanup_subagents(dry_run=dry_run)
        return {
            "cycle_id": cycle_id or "default",
            "terminated_pids": result["terminated"],
            "cleaned_locks": result["cleaned_locks"],
            "dry_run": dry_run,
            "status": "CLEAN",
        }

    def record_handoff(
        self,
        handoff_data: Dict[str, Any],
        require_report_path: bool = False,
        verify_report_exists: bool = False,
    ) -> Any:
        """Ghi nhận và xác thực Triad Handoff Contract v2."""
        from harness.triad_protocol import parse_handoff_v2
        return parse_handoff_v2(
            handoff_data,
            require_report_path=require_report_path,
            verify_report_exists=verify_report_exists,
        )

    def sync_qa_workspace(
        self,
        maker_branch: str,
        target_dir: Optional[Path] = None,
        allow_dirty: bool = False,
    ) -> Dict[str, Any]:
        """Đồng bộ nhánh của Maker sang QA workspace (Chống VULN-05)."""
        from harness.triad_protocol import sync_workspace_for_qa
        dest = target_dir or self.repo_root
        return sync_workspace_for_qa(
            maker_branch,
            dest,
            repo_root=self.repo_root,
            allow_dirty=allow_dirty,
        )


def validate_triad_handoff(
    payload: Dict[str, Any],
    require_report_path: bool = False,
    verify_report_exists: bool = False,
) -> Tuple[bool, List[str]]:
    """Hàm module-level xác thực payload Triad Handoff v2."""
    from harness.triad_protocol import validate_handoff_v2
    return validate_handoff_v2(
        payload,
        require_report_path=require_report_path,
        verify_report_exists=verify_report_exists,
    )


def sync_qa_branch(
    maker_branch: str,
    target_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    allow_dirty: bool = False,
) -> Dict[str, Any]:
    """Hàm module-level đồng bộ branch giữa Maker và QA Auditor."""
    from harness.triad_protocol import sync_workspace_for_qa
    root = Path(repo_root or REPO_ROOT).resolve()
    dest = target_dir or root
    return sync_workspace_for_qa(maker_branch, dest, repo_root=root, allow_dirty=allow_dirty)


def list_idle_subagents(repo_root: Optional[Path] = None) -> List[SubagentInfo]:
    """Hàm module-level liệt kê danh sách subagents idle hoặc mồ côi."""
    return SubagentGuard(repo_root).list_idle()


def cleanup_triad_cycle(cycle_id: Optional[str] = None, dry_run: bool = False, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Hàm module-level dọn dẹp tài nguyên chu trình Dynamic Triad."""
    return SubagentGuard(repo_root).cleanup_triad_cycle(cycle_id=cycle_id, dry_run=dry_run)


@dataclass
class MonitoredProcess:
    """Thông tin tiến trình đang được Watchdog giám sát."""
    pid: int
    cmdline: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    timeout: int = FULL_TIER_TIMEOUT
    tier: str = "full"
    name: str = "python"
    proc: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("proc", None)
        return d


class ProcessWatchdog:
    """Giám sát tiến trình thời gian thực, phát hiện và dọn dẹp tiến trình treo (Hung/Stall)."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or REPO_ROOT).resolve()
        self._monitored: Dict[int, MonitoredProcess] = {}

    def register_process(
        self,
        pid: int,
        cmdline: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        tier: str = "full",
        name: str = "python",
        proc: Optional[Any] = None,
    ) -> MonitoredProcess:
        """Đăng ký tiến trình cần giám sát."""
        resolved_timeout = timeout if timeout is not None else get_deadman_timeout(tier)
        item = MonitoredProcess(
            pid=pid,
            cmdline=cmdline or [],
            start_time=time.time(),
            timeout=resolved_timeout,
            tier=tier,
            name=name,
            proc=proc,
        )
        self._monitored[pid] = item
        return item

    def unregister_process(self, pid: int) -> Optional[MonitoredProcess]:
        """Hủy giám sát tiến trình."""
        return self._monitored.pop(pid, None)

    def is_process_hung(self, pid: int, timeout_override: Optional[int] = None) -> bool:
        """Kiểm tra xem một tiến trình có đang bị treo/vượt quá thời gian cho phép hay không."""
        item = self._monitored.get(pid)
        if not item:
            return False

        limit = timeout_override if timeout_override is not None else item.timeout
        elapsed = time.time() - item.start_time
        return elapsed >= limit

    def get_elapsed_time(self, pid: int) -> float:
        """Lấy thời gian đã trôi qua (giây) của tiến trình."""
        item = self._monitored.get(pid)
        if not item:
            return 0.0
        return time.time() - item.start_time

    def terminate_hung_process(self, pid: int) -> bool:
        """Dọn dẹp an toàn tiến trình treo và giải phóng tài nguyên."""
        item = self._monitored.pop(pid, None)
        killed = False

        # 1. Thử terminate qua proc object nếu được lưu trữ (subprocess.Popen)
        if item and item.proc is not None:
            try:
                item.proc.terminate()
                try:
                    item.proc.wait(timeout=2)
                except Exception:
                    item.proc.kill()
                killed = True
            except Exception:
                pass

        # 2. Thử terminate qua psutil nếu có
        try:
            import psutil
            if psutil.pid_exists(pid):
                p = psutil.Process(pid)
                p.terminate()
                try:
                    p.wait(timeout=2)
                except psutil.TimeoutExpired:
                    p.kill()
                killed = True
        except ImportError:
            # Fallback nếu không có psutil
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                else:
                    import signal
                    os.kill(pid, signal.SIGKILL)
                killed = True
            except Exception:
                pass
        except Exception:
            pass

        return killed

    def sweep_all_hung(self, timeout_override: Optional[int] = None) -> List[SubagentInfo]:
        """Quét và kết thúc tất cả tiến trình bị treo theo phân tầng hạn ngạch."""
        hung_list: List[SubagentInfo] = []
        pids = list(self._monitored.keys())

        for pid in pids:
            if self.is_process_hung(pid, timeout_override=timeout_override):
                item = self._monitored.get(pid)
                name = item.name if item else "python"
                cmdline = item.cmdline if item else []
                self.terminate_hung_process(pid)
                hung_list.append(
                    SubagentInfo(
                        pid=pid,
                        name=name,
                        cmdline=cmdline,
                        status="terminated_hung",
                        is_orphaned=True,
                    )
                )

        return hung_list


class L3BranchGuard:
    """Rào chắn an toàn nhánh chuẩn Autonomy Level 3 (L3 Autonomy Guard).

    - Chặn hoàn toàn thao tác merge trực tiếp hoặc push trực tiếp vào main/master.
    - Bắt buộc tác tử hoạt động trên nhánh phụ (fix/..., feature/..., agent/...).
    - Yêu cầu tạo PR Draft và trả về trạng thái AWAITING_HUMAN_APPROVAL.
    """

    PROTECTED_BRANCHES = {"main", "master", "release", "prod", "production"}

    @classmethod
    def enforce(cls, current_branch: str, target_branch: str = "main") -> Dict[str, Any]:
        """Kiểm tra và thực thi chính sách bảo vệ nhánh L3."""
        curr = (current_branch or "").strip()
        target = (target_branch or "main").strip()

        if not curr:
            return {
                "is_allowed": False,
                "status": "INVALID_BRANCH",
                "message": "Current branch name cannot be empty.",
                "current_branch": curr,
                "target_branch": target,
                "requires_human_gate": True,
            }

        curr_lower = curr.lower()

        # Nếu tác tử đang đứng trên nhánh chính hoặc cố tác động trực tiếp vào nhánh chính
        if curr_lower in cls.PROTECTED_BRANCHES:
            return {
                "is_allowed": False,
                "status": "REJECTED_DIRECT_MERGE",
                "message": (
                    f"Direct modification/merge on protected branch '{curr}' is strictly "
                    "prohibited by L3 Autonomy Guard. Work must be isolated in a secondary branch."
                ),
                "current_branch": curr,
                "target_branch": target,
                "requires_human_gate": True,
            }

        # Nếu target_branch là protected (như main) và current_branch là nhánh hợp lệ
        return {
            "is_allowed": True,
            "status": "AWAITING_HUMAN_APPROVAL",
            "message": (
                f"L3 Autonomy Gate: Branch '{curr}' is verified. Direct merge to '{target}' "
                "is locked; PR Draft required awaiting human signoff."
            ),
            "current_branch": curr,
            "target_branch": target,
            "requires_human_gate": True,
        }


def enforce_l3_branch_policy(current_branch: str, target_branch: str = "main") -> Dict[str, Any]:
    """Hàm module-level kiểm tra tuân thủ chính sách nhánh L3."""
    return L3BranchGuard.enforce(current_branch=current_branch, target_branch=target_branch)


__all__ = [
    "FAST_TIER_TIMEOUT",
    "FULL_TIER_TIMEOUT",
    "get_deadman_timeout",
    "SubagentInfo",
    "SubAgentState",
    "SubagentGuard",
    "list_idle_subagents",
    "cleanup_triad_cycle",
    "MonitoredProcess",
    "ProcessWatchdog",
    "L3BranchGuard",
    "enforce_l3_branch_policy",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity SubAgent Hygiene & Process Guard")
    parser.add_argument("--scan", action="store_true", default=True, help="Quét danh sách subagents đang chạy/mồ côi")
    parser.add_argument("--cleanup", action="store_true", help="Dọn dẹp an toàn subagents mồ côi và lock files")
    parser.add_argument("--cleanup-triad", action="store_true", help="Dọn dẹp tài nguyên chu trình Triad")
    parser.add_argument("--cycle-id", type=str, default="default", help="Mã chu trình Triad cần dọn dẹp")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử không tắt tiến trình thật")
    parser.add_argument("--tier", choices=["fast", "smoke", "full"], default="full", help="In timeout Dead-man Switch theo tier")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON")

    args = parser.parse_args()

    guard = SubagentGuard()

    if args.cleanup_triad:
        res = guard.cleanup_triad_cycle(cycle_id=args.cycle_id, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Đã dọn dẹp chu trình Triad '{res['cycle_id']}': {len(res['terminated_pids'])} tiến trình, {len(res['cleaned_locks'])} file khóa. Trạng thái: {res['status']}.")
        return 0

    if args.cleanup:
        res = guard.cleanup_subagents(dry_run=args.dry_run)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Đã dọn dẹp {len(res['terminated'])} tiến trình mồ côi, {len(res['cleaned_locks'])} file khóa.")
        return 0

    subagents = guard.list_active_subagents()
    orphan_locks = guard.scan_orphan_locks()
    timeout = get_deadman_timeout(args.tier)

    if args.json:
        data = {
            "subagents": [sa.to_dict() for sa in subagents],
            "orphan_locks": [str(l) for l in orphan_locks],
            "deadman_timeout_seconds": timeout,
            "tier": args.tier,
        }
        print(json.dumps(data, indent=2))
    else:
        print("=" * 65)
        print("ANTIGRAVITY SUBAGENT HYGIENE & PROCESS GUARD")
        print("=" * 65)
        print(f"- Dead-man's Switch Timeout ({args.tier} tier): {timeout}s")
        print(f"- Số subagent phát hiện: {len(subagents)}")
        for sa in subagents:
            icon = "🔴 Mồ côi" if sa.is_orphaned else "🟢 Hoạt động"
            print(f"  [{icon}] PID {sa.pid} ({sa.name}) - PPID: {sa.parent_pid}")
        print(f"- Số file khóa mồ côi: {len(orphan_locks)}")
        for lock in orphan_locks:
            print(f"  [LOCK] {lock.name}")
        print("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
