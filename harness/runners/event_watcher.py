"""GitHub Event Watcher Daemon & CLI (Harness 2.0 / Super-Agent Architecture).

Thăm dò sự kiện từ GitHub CLI (`gh`) và chuyển giao cho Orchestrator sau khi qua Pre-LLM Filter:
- Quét các GitHub Issues (nhãn bug / agent-task)
- Quét các GitHub Actions CI failures gần nhất
- Hỗ trợ các cờ CLI: --once, --dry-run, --interval, --repo
- Đảm bảo STDIN DevNull Guard và UTF-8
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Union

from harness.validators.event_filter import EventFilter, FilterResult


class GitHubEventWatcher:
    """Lớp giám sát và lọc sự kiện GitHub định kỳ."""

    def __init__(
        self,
        repo: Optional[str] = None,
        event_filter: Optional[EventFilter] = None,
        dry_run: bool = False,
        poll_interval: int = 60,
        command_runner: Optional[Callable[[List[str]], subprocess.CompletedProcess]] = None,
        dispatcher_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.repo = repo
        self.filter = event_filter or EventFilter()
        self.dry_run = dry_run
        self.poll_interval = poll_interval
        self._custom_runner = command_runner
        self._dispatcher = dispatcher_callback

    def run_gh_command(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Thực thi lệnh `gh` với STDIN DevNull Guard và UTF-8 encoding."""
        cmd = ["gh"] + args
        if self._custom_runner:
            return self._custom_runner(cmd)

        return subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def fetch_issues(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Lấy danh sách các issue mở từ GitHub qua `gh issue list`."""
        args = ["issue", "list", "--state", "open", "--json", "number,title,body,author,labels,updatedAt,url", "--limit", str(limit)]
        if self.repo:
            args.extend(["-R", self.repo])

        try:
            proc = self.run_gh_command(args)
            if proc.returncode != 0:
                return []
            return json.loads(proc.stdout)
        except Exception:
            return []

    def fetch_ci_failures(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Lấy danh sách các workflow runs bị fail gần nhất."""
        args = ["run", "list", "--status", "failure", "--json", "databaseId,name,headBranch,headSha,event,url,conclusion", "--limit", str(limit)]
        if self.repo:
            args.extend(["-R", self.repo])

        try:
            proc = self.run_gh_command(args)
            if proc.returncode != 0:
                return []
            return json.loads(proc.stdout)
        except Exception:
            return []

    def fetch_ci_log(self, run_id: Union[str, int]) -> str:
        """Lấy chi tiết log lỗi của workflow run."""
        args = ["run", "view", str(run_id), "--log-failed"]
        if self.repo:
            args.extend(["-R", self.repo])

        try:
            proc = self.run_gh_command(args, timeout=60)
            if proc.returncode != 0:
                return proc.stderr or ""
            return proc.stdout or ""
        except Exception as exc:
            return f"Error fetching CI log for run {run_id}: {exc}"

    def build_task_payload(self, filter_result: FilterResult) -> Dict[str, Any]:
        """Tạo task payload chuẩn bị bàn giao cho Orchestrator."""
        payload = filter_result.cleaned_payload or {}
        source = payload.get("source", "unknown")

        if source == "github_issue":
            title = f"Fix Issue #{payload.get('issue_number')}: {payload.get('title')}"
            desc = payload.get("cleaned_body", "")
        elif source == "github_ci":
            title = f"Resolve CI Failure in {payload.get('workflow_name')} (Run #{payload.get('run_id')})"
            desc = payload.get("cleaned_log", "")
        else:
            title = "Unknown GitHub Event"
            desc = ""

        return {
            "task_id": f"event_{filter_result.event_hash[:12]}" if filter_result.event_hash else f"event_{int(time.time())}",
            "source": source,
            "title": title,
            "description": desc,
            "event_hash": filter_result.event_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
            "payload": payload,
        }

    def dispatch_task(self, task_payload: Dict[str, Any]) -> bool:
        """Chuyển giao task cho Orchestrator hoặc callback."""
        if self.dry_run:
            print(f"[DRY-RUN] Task payload generated: {task_payload.get('title')} ({task_payload.get('task_id')})")
            return True

        if self._dispatcher:
            try:
                self._dispatcher(task_payload)
                return True
            except Exception as exc:
                print(f"[ERROR] Dispatcher failed: {exc}", file=sys.stderr)
                return False

        # Mặc định ghi file task payload vào đĩa để orchestrator tiếp nhận
        payload_dir = Path(".brain") / "tasks"
        payload_dir.mkdir(parents=True, exist_ok=True)
        task_file = payload_dir / f"{task_payload['task_id']}.json"
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task_payload, f, ensure_ascii=False, indent=2)
        print(f"[DISPATCH] Task payload saved to {task_file}")
        return True

    def poll_once(self) -> List[Dict[str, Any]]:
        """Thực hiện một chu kỳ quét sự kiện."""
        dispatched_tasks: List[Dict[str, Any]] = []

        # 1. Quét Issues
        issues = self.fetch_issues()
        for issue in issues:
            res = self.filter.filter_issue(issue)
            if res.is_accepted:
                task = self.build_task_payload(res)
                if self.dispatch_task(task):
                    dispatched_tasks.append(task)

        # 2. Quét CI Failures
        ci_failures = self.fetch_ci_failures()
        for run in ci_failures:
            run_id = run.get("databaseId") or run.get("id")
            if not run_id:
                continue
            log_content = self.fetch_ci_log(run_id)
            res = self.filter.filter_ci_failure(run, log_content)
            if res.is_accepted:
                task = self.build_task_payload(res)
                if self.dispatch_task(task):
                    dispatched_tasks.append(task)

        return dispatched_tasks

    def run_loop(self) -> None:
        """Vòng lặp thăm dò liên tục với cờ ngắt mạch."""
        print(f"[START] GitHubEventWatcher daemon started. Interval={self.poll_interval}s, DryRun={self.dry_run}")
        try:
            while True:
                self.poll_once()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\n[STOP] GitHubEventWatcher daemon stopped by user.")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Xây dựng bộ phân tích tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="GitHub Event Watcher Daemon & CLI (Harness 2.0 Super-Agent)."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Chạy đúng 1 chu kỳ thăm dò rồi thoát thay vì loop liên tục.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ trích xuất và in payload sự kiện, không dispatch sang Orchestrator.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Thời gian lặp lại giữa các lần thăm dò tính bằng giây (mặc định 60s).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Repository mục tiêu dạng 'owner/repo' (mặc định là repository hiện tại).",
    )
    return parser.parse_args(args)


def main(argv: Optional[List[str]] = None) -> int:
    """Điểm nhập chính cho CLI."""
    opts = parse_args(argv)
    watcher = GitHubEventWatcher(
        repo=opts.repo,
        dry_run=opts.dry_run,
        poll_interval=opts.interval,
    )
    if opts.once:
        tasks = watcher.poll_once()
        print(f"[DONE] Poll once completed. Processed {len(tasks)} valid task(s).")
        return 0
    else:
        watcher.run_loop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
