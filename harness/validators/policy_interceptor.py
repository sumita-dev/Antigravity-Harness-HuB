"""Hard Policy Interceptor inspired by inspect_ai/approval/_policy.py.

Thực hiện cơ chế chặn cứng (hard boundary) và cảnh báo các lệnh shell nguy hiểm,
phá hủy dữ liệu, hoặc truy cập trái phép vào các thư mục hệ thống nhạy cảm.
100% Python standard library (dataclasses, enum, re, fnmatch, typing, pathlib).
"""

from dataclasses import dataclass
from enum import Enum
import fnmatch
from pathlib import Path
import re
from typing import List, Optional, Tuple


class PolicyAction(str, Enum):
    """Hành động kiểm soát chính sách bảo mật lệnh shell."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class PolicyDecision:
    """Kết quả thẩm định chính sách cho một lệnh shell."""

    action: PolicyAction
    reason: str
    command: str
    matched_pattern: Optional[str] = None


# Các mẫu lệnh shell nguy hiểm/phá hủy dữ liệu (Destructive patterns)
# Bao gồm lệnh xóa hàng loạt, broad delete, drop table, reset hard, format, fork bomb...
DESTRUCTIVE_SHELL_PATTERNS: List[Tuple[str, str, PolicyAction]] = [
    # Fork bomb & system freeze
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb signature detected", PolicyAction.BLOCK),
    # Format / dd to disk
    (r"\bformat\s+[a-zA-Z]:", "Disk format command detected", PolicyAction.BLOCK),
    (r"\bmkfs(\.\w+)?\s+", "Filesystem creation command detected", PolicyAction.BLOCK),
    (r"\bdd\s+.*if=.*of=(/dev/|\\\\.\\[a-zA-Z]:)", "Raw disk overwrite (dd) detected", PolicyAction.BLOCK),
    # Massive destruction in Unix / POSIX
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(?:\s|$|\*)", "Root filesystem recursive deletion (rm -rf /) detected", PolicyAction.BLOCK),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+~", "User home recursive deletion detected", PolicyAction.BLOCK),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+\.\.(?:/|\s|$)", "Parent directory recursive deletion detected", PolicyAction.BLOCK),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+\*", "Mass wild-card recursive deletion (rm -rf *) detected", PolicyAction.BLOCK),
    # Windows destructive deletes
    (r"\bdel\s+.*(?:\/s|\/q).*(?:[a-zA-Z]:\\|\*|\bC:\\Windows)", "Recursive silent deletion of system/broad scope detected", PolicyAction.BLOCK),
    (r"\brd\s+\/s\s+\/q\s+(?:[a-zA-Z]:\\|\bC:\\Windows)", "Silent directory tree removal of system scope detected", PolicyAction.BLOCK),
    # PowerShell destructive commands
    (r"(?i)\b(Remove-Item|ri|rmdir|rd)\b.*-Recurse.*-Force.*(?:\b[a-zA-Z]:\\|\bC:\\Windows|\$env:SystemRoot|\$HOME|\b\.\.)", "PowerShell destructive recursive deletion of system/parent scope", PolicyAction.BLOCK),
    (r"(?i)\b(Remove-Item|ri|rmdir|rd)\b.*-Force.*-Recurse.*(?:\b[a-zA-Z]:\\|\bC:\\Windows|\$env:SystemRoot|\$HOME|\b\.\.)", "PowerShell destructive recursive deletion of system/parent scope", PolicyAction.BLOCK),
    (r"(?i)\b(Remove-Item|ri|rmdir|rd)\b.*-Recurse.*(?:\s*\*|\s*\.\\\*)", "Broad PowerShell recursive wildcard deletion", PolicyAction.WARN),
    # Database destructive commands
    (r"(?i)\bDROP\s+(DATABASE|SCHEMA)\b", "Destructive DROP DATABASE/SCHEMA detected", PolicyAction.BLOCK),
    (r"(?i)\bDROP\s+TABLE\b", "Destructive DROP TABLE detected", PolicyAction.WARN),
    (r"(?i)\bTRUNCATE(\s+TABLE)?\b", "Destructive TRUNCATE detected", PolicyAction.WARN),
    (r"(?i)\bDELETE\s+FROM\s+\w+\s*(?:;|$|\s+WHERE\s+(?:1=1|true)\b)", "Broad DELETE without safe filter detected", PolicyAction.BLOCK),
    # Git destructive commands
    (r"\bgit\s+reset\s+--hard\b", "Git destructive reset hard detected", PolicyAction.WARN),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*\s+-[a-zA-Z]*d\b", "Git force clean untracked files and directories", PolicyAction.WARN),
    (r"\bgit\s+clean\s+-[a-zA-Z]*fd[a-zA-Z]*\b", "Git force clean untracked files and directories", PolicyAction.WARN),
    (r"\bgit\s+push\s+.*--force\b", "Git force push detected", PolicyAction.WARN),
    # Process / system control
    (r"(?i)\b(shutdown|reboot|init\s+0|init\s+6)\b", "System shutdown/reboot detected", PolicyAction.BLOCK),
    (r"\bkill\s+-9\s+1\b", "Init/PID 1 termination detected", PolicyAction.BLOCK),
]

# Danh sách đường dẫn hệ thống nhạy cảm (Sensitive system paths)
SENSITIVE_SYSTEM_PATHS = [
    # Windows
    r"^[a-zA-Z]:\\windows",
    r"^[a-zA-Z]:\\windows\\system32",
    r"^[a-zA-Z]:\\boot",
    r"^[a-zA-Z]:\\recovery",
    # Unix / Linux / macOS
    r"^/etc(/|$)",
    r"^/boot(/|$)",
    r"^/root(/|$)",
    r"^/dev(/|$)",
    r"^/proc(/|$)",
    r"^/sys(/|$)",
    r"^/usr(/|$)",
    r"^/bin(/|$)",
    r"^/sbin(/|$)",
]


def _is_path_sensitive(path_str: str) -> bool:
    """Kiểm tra đường dẫn có rơi vào thư mục hệ thống nhạy cảm hay không."""
    normalized = path_str.replace("/", "\\").lower() if "\\" in path_str or ":" in path_str else path_str.lower()
    
    # Check Windows sensitive paths
    for pattern in SENSITIVE_SYSTEM_PATHS:
        if pattern.startswith("^[a-zA-Z]:\\\\"):
            clean_p = pattern[1:].replace("\\\\", "\\").lower()
            if normalized.startswith(clean_p) or re.search(pattern, path_str, re.IGNORECASE):
                return True
        else:
            # POSIX sensitive paths
            posix_norm = path_str.replace("\\", "/")
            if re.search(pattern, posix_norm):
                return True
    return False


def evaluate_command_policy(
    command: str,
    cwd: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> PolicyDecision:
    """Thẩm định chính sách an toàn cho lệnh shell.

    Args:
        command: Chuỗi lệnh shell cần kiểm tra.
        cwd: Thư mục thực thi hiện tại (nếu có).
        workspace_root: Thư mục gốc của workspace (nếu có).

    Returns:
        PolicyDecision gồm action (ALLOW/WARN/BLOCK), reason, command và matched_pattern.
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return PolicyDecision(action=PolicyAction.ALLOW, reason="Empty command", command=command)

    # 1. Thẩm định qua danh sách DESTRUCTIVE_SHELL_PATTERNS
    for pattern, reason, action in DESTRUCTIVE_SHELL_PATTERNS:
        match = re.search(pattern, cmd_clean)
        if match:
            return PolicyDecision(
                action=action,
                reason=reason,
                command=command,
                matched_pattern=pattern,
            )

    # 2. Thẩm định truy cập hoặc phá hoại đường dẫn nhạy cảm
    # Bắt các đối số đường dẫn trong câu lệnh (ví dụ: rm C:\Windows\System32, del /f /q /etc/passwd)
    tokens = re.split(r"[\s\"'|;&]+", cmd_clean)
    for token in tokens:
        # Nếu token trông giống đường dẫn tuyệt đối
        if token.startswith("/") or re.match(r"^[a-zA-Z]:[\\/]", token):
            if _is_path_sensitive(token):
                # Nếu lệnh là thao tác ghi / xóa
                write_delete_cmds = {"rm", "del", "erase", "rd", "rmdir", "remove-item", "unlink", "shred", "mv", "move"}
                first_token = tokens[0].lower() if tokens else ""
                if first_token in write_delete_cmds or any(w in cmd_clean.lower() for w in ["del ", "rm ", "remove-item"]):
                    return PolicyDecision(
                        action=PolicyAction.BLOCK,
                        reason=f"Thao tác xóa/ghi trên đường dẫn hệ thống nhạy cảm: {token}",
                        command=command,
                        matched_pattern=token,
                    )
                else:
                    return PolicyDecision(
                        action=PolicyAction.WARN,
                        reason=f"Tham chiếu đường dẫn hệ thống nhạy cảm: {token}",
                        command=command,
                        matched_pattern=token,
                    )

    # 3. Kiểm tra cwd có nằm trong sensitive system path không
    if cwd and _is_path_sensitive(cwd):
        return PolicyDecision(
            action=PolicyAction.BLOCK,
            reason=f"Thực thi lệnh từ thư mục hệ thống nhạy cảm: {cwd}",
            command=command,
            matched_pattern=cwd,
        )

    return PolicyDecision(
        action=PolicyAction.ALLOW,
        reason="Lệnh nằm trong giới hạn an toàn",
        command=command,
    )


def is_command_safe(command: str) -> bool:
    """Hàm tiện ích nhanh kiểm tra lệnh có được phép thực thi (không bị BLOCK) hay không.

    Lệnh trả về True nếu là ALLOW hoặc WARN, trả về False nếu là BLOCK.
    """
    decision = evaluate_command_policy(command)
    return decision.action != PolicyAction.BLOCK
