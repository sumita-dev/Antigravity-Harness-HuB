"""Deterministic Pre-LLM Event Filter (Harness 2.0 / Super-Agent Architecture).

Thực hiện tiền lọc tất định (Pre-LLM Filter) không tiêu tốn token LLM:
1. Lọc bỏ bot (github-actions[bot], dependabot, etc.).
2. Khử trùng lặp (Deduplication) dựa trên SHA256 hash.
3. Làm sạch và cắt gọt stack trace: loại bỏ ANSI escape sequences, HTML tags,
   giữ 40 dòng cốt lõi quanh frame lỗi/traceback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Union

# ANSI escape sequence regex
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# HTML tag regex
HTML_TAG_RE = re.compile(r"<[^<]+?>")

# Danh sách mặc định các bot phổ biến cần lọc bỏ
DEFAULT_BOT_PATTERNS = {
    "github-actions[bot]",
    "github-actions",
    "dependabot[bot]",
    "dependabot",
    "renovate[bot]",
    "renovate",
    "snyk-bot",
    "codecov[bot]",
    "stale[bot]",
}


@dataclass
class FilterResult:
    """Kết quả lọc sự kiện tất định."""

    is_accepted: bool
    reason: str  # 'ACCEPTED', 'BOT_AUTHOR', 'DUPLICATE_ISSUE', 'DUPLICATE_CI_RUN', etc.
    cleaned_payload: Optional[Dict[str, Any]] = None
    event_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dict."""
        return asdict(self)


def clean_and_truncate_log(log_content: str, max_lines: int = 40) -> str:
    """Làm sạch log: loại bỏ ANSI codes, HTML tags và cắt giữ max_lines quanh frame lỗi.

    Args:
        log_content: Nội dung log thô.
        max_lines: Số dòng tối đa cần giữ lại (mặc định 40 dòng).

    Returns:
        Chuỗi log đã làm sạch và cắt gọt.
    """
    if not log_content:
        return ""

    # 1. Bóc tách ANSI escape sequences
    text = ANSI_ESCAPE_RE.sub("", log_content)

    # 2. Bóc tách HTML tags
    text = HTML_TAG_RE.sub("", text)

    lines = [line.rstrip() for line in text.splitlines()]
    if len(lines) <= max_lines:
        return "\n".join(lines).strip()

    # 3. Tìm kiếm vị trí marker lỗi
    error_patterns = [
        re.compile(r"traceback\s*\(most recent call last\)", re.IGNORECASE),
        re.compile(r"FAILED\s+", re.IGNORECASE),
        re.compile(r"(?:error|exception|failure):\s*", re.IGNORECASE),
        re.compile(r"assertionerror", re.IGNORECASE),
    ]

    marker_idx = -1
    # Quét ngược từ dưới lên để bắt cụm lỗi gần kết thúc nhất
    for idx in range(len(lines) - 1, -1, -1):
        line = lines[idx]
        if any(pat.search(line) for pat in error_patterns):
            marker_idx = idx
            break

    if marker_idx == -1:
        # Nếu không thấy marker rõ ràng, lấy max_lines dòng cuối cùng
        selected = lines[-max_lines:]
    else:
        # Trích xuất cửa sổ quanh marker: 1/3 dòng trước, 2/3 dòng sau
        half_before = max_lines // 3
        start = max(0, marker_idx - half_before)
        end = min(len(lines), start + max_lines)
        if end - start < max_lines:
            start = max(0, end - max_lines)
        selected = lines[start:end]

    return "\n".join(selected).strip()


class EventFilter:
    """Lớp xử lý tiền lọc tất định cho GitHub Issues & CI Failures."""

    def __init__(
        self,
        bot_patterns: Optional[Set[str]] = None,
        max_log_lines: int = 40,
    ) -> None:
        self.bot_patterns = set(bot_patterns) if bot_patterns is not None else set(DEFAULT_BOT_PATTERNS)
        self.max_log_lines = max_log_lines
        self.seen_hashes: Set[str] = set()

    def is_bot(self, author: Union[str, Dict[str, Any], None]) -> bool:
        """Kiểm tra author có phải là bot hay không."""
        if not author:
            return False
        if isinstance(author, dict):
            login = author.get("login", "")
        else:
            login = str(author)
        login_clean = login.strip().lower()
        for bot in self.bot_patterns:
            if bot.lower() in login_clean or login_clean in bot.lower():
                return True
        return False

    def compute_issue_hash(self, title: str, body: str) -> str:
        """Tính SHA256 hash chuẩn hóa cho Issue."""
        norm = f"{(title or '').strip().lower()}\n{(body or '').strip().lower()}"
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def compute_ci_hash(self, run_id: Union[str, int], branch: str) -> str:
        """Tính SHA256 hash cho CI failure run."""
        norm = f"ci_run_{run_id}_{branch.strip().lower()}"
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def filter_issue(self, issue_data: Dict[str, Any]) -> FilterResult:
        """Lọc deterministic cho GitHub Issue.

        Args:
            issue_data: Dữ liệu thô từ gh issue list/view.

        Returns:
            FilterResult với quyết định is_accepted và cleaned_payload.
        """
        # 1. Kiểm tra Bot
        author = issue_data.get("author")
        if self.is_bot(author):
            author_name = author.get("login") if isinstance(author, dict) else str(author)
            return FilterResult(
                is_accepted=False,
                reason=f"BOT_AUTHOR: {author_name}",
                cleaned_payload=None,
                event_hash=None,
                metadata={"issue_number": issue_data.get("number")},
            )

        title = str(issue_data.get("title") or "")
        raw_body = str(issue_data.get("body") or "")

        # 2. Khử trùng lặp (Deduplication)
        event_hash = self.compute_issue_hash(title, raw_body)
        if event_hash in self.seen_hashes:
            return FilterResult(
                is_accepted=False,
                reason="DUPLICATE_ISSUE",
                cleaned_payload=None,
                event_hash=event_hash,
                metadata={"issue_number": issue_data.get("number")},
            )

        # 3. Làm sạch nội dung body
        cleaned_body = clean_and_truncate_log(raw_body, max_lines=self.max_log_lines)

        self.seen_hashes.add(event_hash)

        cleaned_payload = {
            "source": "github_issue",
            "issue_number": issue_data.get("number"),
            "title": title.strip(),
            "cleaned_body": cleaned_body,
            "raw_body": raw_body,
            "author": author.get("login") if isinstance(author, dict) else author,
            "labels": issue_data.get("labels", []),
            "url": issue_data.get("url", ""),
            "event_hash": event_hash,
        }

        return FilterResult(
            is_accepted=True,
            reason="ACCEPTED",
            cleaned_payload=cleaned_payload,
            event_hash=event_hash,
            metadata={"issue_number": issue_data.get("number")},
        )

    def filter_ci_failure(self, run_data: Dict[str, Any], log_content: str) -> FilterResult:
        """Lọc deterministic cho CI failure.

        Args:
            run_data: Dữ liệu thô từ gh run list/view.
            log_content: Nội dung log lỗi chi tiết.

        Returns:
            FilterResult với quyết định is_accepted và cleaned_payload.
        """
        # 1. Kiểm tra actor/author nếu có
        actor = run_data.get("actor") or run_data.get("headCommit", {}).get("author", {})
        if self.is_bot(actor):
            actor_name = actor.get("login") if isinstance(actor, dict) else str(actor)
            return FilterResult(
                is_accepted=False,
                reason=f"BOT_AUTHOR: {actor_name}",
                cleaned_payload=None,
                event_hash=None,
                metadata={"run_id": run_data.get("databaseId") or run_data.get("id")},
            )

        run_id = str(run_data.get("databaseId") or run_data.get("id") or "")
        branch = str(run_data.get("headBranch") or "")

        # 2. Khử trùng lặp
        event_hash = self.compute_ci_hash(run_id, branch)
        if event_hash in self.seen_hashes:
            return FilterResult(
                is_accepted=False,
                reason="DUPLICATE_CI_RUN",
                cleaned_payload=None,
                event_hash=event_hash,
                metadata={"run_id": run_id},
            )

        # 3. Làm sạch và cắt gọt stack trace
        cleaned_log = clean_and_truncate_log(log_content, max_lines=self.max_log_lines)

        self.seen_hashes.add(event_hash)

        cleaned_payload = {
            "source": "github_ci",
            "run_id": run_id,
            "workflow_name": run_data.get("name") or run_data.get("workflowName", ""),
            "branch": branch,
            "commit_sha": run_data.get("headSha", ""),
            "cleaned_log": cleaned_log,
            "url": run_data.get("url", ""),
            "event_hash": event_hash,
        }

        return FilterResult(
            is_accepted=True,
            reason="ACCEPTED",
            cleaned_payload=cleaned_payload,
            event_hash=event_hash,
            metadata={"run_id": run_id},
        )


__all__ = [
    "DEFAULT_BOT_PATTERNS",
    "EventFilter",
    "FilterResult",
    "clean_and_truncate_log",
]
