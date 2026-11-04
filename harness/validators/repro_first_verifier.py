"""Repro-First Policy Verifier (Harness 2.0 / Super-Agent Architecture).

Thẩm định quy chuẩn "Silently Reproduce First" (Repro-First Invariant):
1. Kiểm tra sự tồn tại của tệp test tái hiện tại tests/repro/test_issue_<id>.py.
2. Thực thi kiểm thử độc lập qua subprocess hermetic (stdin=DEVNULL, utf-8).
3. Xác nhận trạng thái RED (fail ban đầu, chứng minh bug tồn tại) hoặc GREEN (pass sau khi vá).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union


@dataclass
class ReproVerificationResult:
    """Kết quả thẩm định quy chuẩn Reproduce-First."""

    is_valid: bool
    status: str  # 'RED_CONFIRMED', 'GREEN_CONFIRMED', 'MISSING_REPRO', 'INVALID_FAILURE'
    exit_code: Optional[int]
    stdout: str = ""
    stderr: str = ""
    test_path: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dict cho handoff payload hoặc json logging."""
        return asdict(self)


def _find_repro_test_file(repro_dir: Union[str, Path], issue_id: str) -> Optional[Path]:
    """Tìm kiếm file test tái hiện tương ứng với issue_id."""
    base = Path(repro_dir)

    # Nếu truyền thẳng file cụ thể
    if base.is_file():
        return base if base.exists() else None

    # Chuẩn hoá issue_id
    raw_id = str(issue_id).strip()
    clean_id = re.sub(r"^issue[_-]?", "", raw_id, flags=re.IGNORECASE)

    candidate_names = [
        f"test_issue_{raw_id}.py",
        f"test_issue_{clean_id}.py",
        f"test_{raw_id}.py",
        f"test_{clean_id}.py",
    ]
    # Khử trùng lặp giữ nguyên thứ tự
    seen = set()
    unique_candidates: List[str] = []
    for name in candidate_names:
        if name not in seen:
            seen.add(name)
            unique_candidates.append(name)

    search_dirs = [
        base,
        base / "tests" / "repro",
        base / "repro",
    ]

    for directory in search_dirs:
        if directory.exists() and directory.is_dir():
            for name in unique_candidates:
                candidate_path = directory / name
                if candidate_path.exists() and candidate_path.is_file():
                    return candidate_path.resolve()

    return None


def verify_repro_first(
    repro_dir: Union[str, Path],
    issue_id: str,
    run_test: bool = True,
    expected_status: str = "RED",
    timeout_seconds: int = 45,
    cwd: Optional[Union[str, Path]] = None,
) -> ReproVerificationResult:
    """Xác minh sự hiện diện và trạng thái thực thi của repro test.

    Args:
        repro_dir: Thư mục chứa repro test hoặc project root.
        issue_id: Mã định danh của issue/bug (ví dụ: '101', 'issue_101').
        run_test: Có thực thi pytest trên file test hay chỉ kiểm tra tồn tại.
        expected_status: Trạng thái kỳ vọng ('RED' cho bug ban đầu, 'GREEN' sau khi sửa).
        timeout_seconds: Thời gian chạy tối đa trước khi ngắt mạch (mặc định 45s).
        cwd: Thư mục làm việc cho subprocess (mặc định là repro_dir hoặc project root).

    Returns:
        ReproVerificationResult chứa is_valid, status, exit_code, stdout, stderr, test_path, message.
    """
    found_file = _find_repro_test_file(repro_dir, issue_id)

    if not found_file or not found_file.exists():
        return ReproVerificationResult(
            is_valid=False,
            status="MISSING_REPRO",
            exit_code=None,
            stdout="",
            stderr="",
            test_path=None,
            message=f"Reproduction test file not found for issue '{issue_id}' in '{repro_dir}'.",
        )

    expected_upper = expected_status.upper().strip()

    if not run_test:
        # Nếu không chạy thực tế, xác nhận file tồn tại
        is_red = expected_upper == "RED"
        return ReproVerificationResult(
            is_valid=True,
            status="RED_CONFIRMED" if is_red else "GREEN_CONFIRMED",
            exit_code=None,
            stdout="",
            stderr="",
            test_path=str(found_file),
            message=f"Reproduction test file located at '{found_file}' (run_test=False).",
        )

    # Chạy test qua subprocess với STDIN DevNull Guard và UTF-8
    work_dir = Path(cwd).resolve() if cwd else (Path(repro_dir).resolve() if Path(repro_dir).is_dir() else found_file.parent)
    cmd = [sys.executable, "-m", "pytest", "-q", str(found_file)]

    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            cwd=str(work_dir),
        )
        exit_code = proc.returncode
        stdout_txt = proc.stdout
        stderr_txt = proc.stderr
    except subprocess.TimeoutExpired as exc:
        return ReproVerificationResult(
            is_valid=False,
            status="INVALID_FAILURE",
            exit_code=-1,
            stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
            stderr=f"Repro test timed out after {timeout_seconds}s.",
            test_path=str(found_file),
            message=f"Reproduction test timed out after {timeout_seconds} seconds.",
        )
    except Exception as exc:
        return ReproVerificationResult(
            is_valid=False,
            status="INVALID_FAILURE",
            exit_code=-2,
            stdout="",
            stderr=str(exc),
            test_path=str(found_file),
            message=f"Unexpected error executing repro test: {exc}",
        )

    if expected_upper == "RED":
        # Kỳ vọng RED: exit_code != 0 (test fail chứng minh bug tồn tại)
        if exit_code != 0:
            return ReproVerificationResult(
                is_valid=True,
                status="RED_CONFIRMED",
                exit_code=exit_code,
                stdout=stdout_txt,
                stderr=stderr_txt,
                test_path=str(found_file),
                message="Reproduction test failed as expected (RED confirmed; bug verified).",
            )
        else:
            return ReproVerificationResult(
                is_valid=False,
                status="INVALID_FAILURE",
                exit_code=exit_code,
                stdout=stdout_txt,
                stderr=stderr_txt,
                test_path=str(found_file),
                message="Reproduction test passed unexpectedly; bug was not reproduced on current code.",
            )
    else:  # expected_upper == "GREEN"
        # Kỳ vọng GREEN: exit_code == 0 (test pass chứng minh bug đã được vá)
        if exit_code == 0:
            return ReproVerificationResult(
                is_valid=True,
                status="GREEN_CONFIRMED",
                exit_code=exit_code,
                stdout=stdout_txt,
                stderr=stderr_txt,
                test_path=str(found_file),
                message="Reproduction test passed successfully (GREEN confirmed; fix verified).",
            )
        else:
            return ReproVerificationResult(
                is_valid=False,
                status="INVALID_FAILURE",
                exit_code=exit_code,
                stdout=stdout_txt,
                stderr=stderr_txt,
                test_path=str(found_file),
                message="Reproduction test failed unexpectedly when expecting GREEN.",
            )


class ReproFirstVerifier:
    """Lớp tiện ích thẩm định quy chuẩn Repro-First."""

    @staticmethod
    def verify(
        repro_dir: Union[str, Path],
        issue_id: str,
        run_test: bool = True,
        expected_status: str = "RED",
        timeout_seconds: int = 45,
        cwd: Optional[Union[str, Path]] = None,
    ) -> ReproVerificationResult:
        """Thực hiện thẩm định repro-first."""
        return verify_repro_first(
            repro_dir=repro_dir,
            issue_id=issue_id,
            run_test=run_test,
            expected_status=expected_status,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
        )


__all__ = [
    "ReproFirstVerifier",
    "ReproVerificationResult",
    "verify_repro_first",
]
