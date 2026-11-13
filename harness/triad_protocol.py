#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness/triad_protocol.py

Giao thức Bàn Giao Triad (Triad Handoff Contract v2) & Đồng Bộ Không Gian Làm Việc (Workspace Sync).
Chuẩn hóa cấu trúc payload bàn giao giữa Maker -> Critic -> QA Auditor:
- Bắt buộc đính kèm Git Commit SHA (`commit_sha`) bất biến thay vì diff rời rạc trên disk.
- Bắt buộc đính kèm biên lai xác minh thực thi (`verification_receipt`) với `exit_code == 0`.
- Đối soát ma trận tiêu chí nghiệm thu (`acceptance_criteria_matrix`).
- Đồng bộ nhánh làm việc (`sync_workspace_for_qa`) giải quyết lỗ hổng Branch Blindness (VULN-05).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_V2_URI = "https://antigravity.dev/schemas/triad-handoff.v2.json"
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")
HEX_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class HandoffValidationError(ValueError):
    """Ngoại lệ khi payload handoff không thỏa mãn Triad Handoff Contract v2."""
    pass


@dataclass
class TriadHandoffV2:
    """Đối tượng đại diện hợp đồng bàn giao Triad Handoff Contract v2."""
    task_id: str
    commit_sha: str
    verification_receipt: Dict[str, Any]
    source_branch: str = "main"
    spec_sha256: Optional[str] = None
    modified_files: List[Dict[str, Any]] = field(default_factory=list)
    acceptance_criteria_matrix: List[Dict[str, Any]] = field(default_factory=list)
    digest: Optional[str] = None
    report_path: Optional[str] = None
    evidence_paths: List[str] = field(default_factory=list)
    schema: str = SCHEMA_V2_URI
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi thành từ điển JSON-serializable."""
        d = {
            "$schema": self.schema,
            "task_id": self.task_id,
            "source_branch": self.source_branch,
            "commit_sha": self.commit_sha,
            "verification_receipt": self.verification_receipt,
            "modified_files": self.modified_files,
            "acceptance_criteria_matrix": self.acceptance_criteria_matrix,
        }
        if self.spec_sha256:
            d["spec_sha256"] = self.spec_sha256
        if self.digest:
            d["digest"] = self.digest
        if self.report_path:
            d["report_path"] = self.report_path
        if self.evidence_paths:
            d["evidence_paths"] = self.evidence_paths
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    def to_json(self, indent: int = 2) -> str:
        """Xuất định dạng chuỗi JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def validate_handoff_v2(
    payload: Dict[str, Any],
    require_report_path: bool = False,
) -> Tuple[bool, List[str]]:
    """Kiểm tra tính hợp lệ của payload Triad Handoff Contract v2.

    Trả về:
        (is_valid: bool, errors: List[str])
    """
    errors: List[str] = []

    if not isinstance(payload, dict):
        return False, ["Payload phải là một từ điển (JSON object)"]

    # 1. Kiểm tra task_id
    task_id = payload.get("task_id")
    if not task_id or not isinstance(task_id, str) or not task_id.strip():
        errors.append("Thiếu trường bắt buộc 'task_id' (string)")

    # 2. Kiểm tra commit_sha (bắt buộc, 7-40 hex chars)
    commit_sha = payload.get("commit_sha")
    if not commit_sha or not isinstance(commit_sha, str):
        errors.append("Thiếu trường bắt buộc 'commit_sha'")
    elif not COMMIT_SHA_PATTERN.match(commit_sha.strip()):
        errors.append(f"Giá trị 'commit_sha' không hợp lệ: '{commit_sha}' (yêu cầu 7-40 ký tự hex)")

    # 3. Kiểm tra verification_receipt (bắt buộc, exit_code == 0)
    receipt = payload.get("verification_receipt")
    if not receipt or not isinstance(receipt, dict):
        errors.append("Thiếu trường bắt buộc 'verification_receipt' (dict)")
    else:
        cmd = receipt.get("command")
        if not cmd or not isinstance(cmd, str) or not cmd.strip():
            errors.append("Trường 'verification_receipt.command' bắt buộc không được để trống")

        if "exit_code" not in receipt:
            errors.append("Thiếu trường bắt buộc 'verification_receipt.exit_code'")
        else:
            ec = receipt.get("exit_code")
            if not isinstance(ec, int) or isinstance(ec, bool) or ec != 0:
                errors.append(f"verification_receipt.exit_code bắt buộc phải bằng 0 (nhận được: {ec})")

        stdout_hash = receipt.get("stdout_hash")
        if not stdout_hash or not isinstance(stdout_hash, str) or not stdout_hash.strip():
            errors.append("Thiếu trường bắt buộc 'verification_receipt.stdout_hash'")

    # 4. Kiểm tra modified_files (nếu có, phải là list)
    if "modified_files" in payload:
        mf = payload["modified_files"]
        if not isinstance(mf, list):
            errors.append("'modified_files' bắt buộc phải là một danh sách (list)")
        else:
            for idx, item in enumerate(mf):
                if not isinstance(item, dict) or not item.get("path"):
                    errors.append(f"Mục modified_files[{idx}] thiếu thông tin 'path'")

    # 5. Kiểm tra spec_sha256 (nếu có)
    spec_sha = payload.get("spec_sha256")
    if spec_sha and isinstance(spec_sha, str):
        if not HEX_SHA256_PATTERN.match(spec_sha.strip()):
            errors.append(f"Giá trị 'spec_sha256' không hợp lệ: '{spec_sha}' (yêu cầu 64 ký tự hex)")

    # 6. Kiểm tra acceptance_criteria_matrix (nếu có)
    if "acceptance_criteria_matrix" in payload:
        ac_matrix = payload["acceptance_criteria_matrix"]
        if not isinstance(ac_matrix, list):
            errors.append("'acceptance_criteria_matrix' bắt buộc phải là một danh sách (list)")

    # 7. Kiểm tra digest (Rule 1.12: < 100 từ)
    digest = payload.get("digest")
    if digest and isinstance(digest, str):
        words = digest.strip().split()
        if len(words) > 100:
            errors.append(f"Digest vượt quá giới hạn 100 từ theo Rule 1.12 (đếm được {len(words)} từ)")

    # 8. Kiểm tra report_path (Hợp đồng bàn giao & Chốt chặn đọc Artifact)
    report_path = payload.get("report_path")
    if "report_path" in payload and report_path is not None:
        if not isinstance(report_path, str) or not report_path.strip():
            errors.append("'report_path' phải là chuỗi không rỗng (non-empty string)")
    elif require_report_path:
        errors.append("Thiếu trường bắt buộc 'report_path' (non-empty string)")

    # 9. Kiểm tra evidence_paths (nếu có, phải là list các non-empty string)
    if "evidence_paths" in payload and payload["evidence_paths"] is not None:
        ep = payload["evidence_paths"]
        if not isinstance(ep, list):
            errors.append("'evidence_paths' bắt buộc phải là một danh sách (list)")
        else:
            for idx, item in enumerate(ep):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"Mục evidence_paths[{idx}] phải là chuỗi không rỗng (non-empty string)")

    is_valid = len(errors) == 0
    return is_valid, errors


def parse_handoff_v2(
    data: Union[str, Dict[str, Any]],
    require_report_path: bool = False,
) -> TriadHandoffV2:
    """Parse và xác thực payload Handoff Contract v2.
    
    Ném ra HandoffValidationError nếu payload không đạt chuẩn.
    """
    if isinstance(data, str):
        try:
            payload = json.loads(data)
        except Exception as e:
            raise HandoffValidationError(f"Dữ liệu handoff không phải JSON hợp lệ: {e}") from e
    elif isinstance(data, dict):
        payload = data
    else:
        raise HandoffValidationError("Payload handoff phải là dict hoặc chuỗi JSON")

    is_valid, errors = validate_handoff_v2(payload, require_report_path=require_report_path)
    if not is_valid:
        raise HandoffValidationError("Handoff Schema v2 vi phạm:\n- " + "\n- ".join(errors))

    return TriadHandoffV2(
        task_id=str(payload["task_id"]),
        commit_sha=str(payload["commit_sha"]),
        verification_receipt=payload["verification_receipt"],
        source_branch=str(payload.get("source_branch", "main")),
        spec_sha256=payload.get("spec_sha256"),
        modified_files=payload.get("modified_files", []),
        acceptance_criteria_matrix=payload.get("acceptance_criteria_matrix", []),
        digest=payload.get("digest"),
        report_path=payload.get("report_path"),
        evidence_paths=payload.get("evidence_paths") or [],
        schema=payload.get("$schema") or payload.get("schema") or SCHEMA_V2_URI,
        metadata=payload.get("metadata", {}),
    )


def compute_content_sha256(content: Union[str, bytes]) -> str:
    """Tính toán mã băm SHA256 của nội dung văn bản hoặc bytes."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


def sync_workspace_for_qa(
    maker_branch: str,
    target_workspace: Union[str, Path],
    repo_root: Optional[Union[str, Path]] = None,
    allow_dirty: bool = False,
) -> Dict[str, Any]:
    """Đồng bộ mã nguồn từ nhánh làm việc của Maker sang workspace của QA Auditor (Chống VULN-05 Branch Blindness).

    Thực hiện:
    1. Kiểm tra nhánh maker_branch có tồn tại trên repository không.
    2. Cập nhật target_workspace bằng cách checkout nhánh hoặc merge branch của Maker.
    3. Trả về thông tin trạng thái đồng bộ và commit SHA hiện thời.
    """
    root = Path(repo_root or REPO_ROOT).resolve()
    target_dir = Path(target_workspace).resolve()

    result: Dict[str, Any] = {
        "synced": False,
        "maker_branch": maker_branch,
        "target_workspace": str(target_dir),
        "commit_sha": "",
        "message": "",
    }

    # Kiểm tra Git repository
    git_dir = root / ".git"
    if not git_dir.exists():
        result["message"] = "Không tìm thấy thư mục .git; chế độ filesystem fallback"
        result["synced"] = True
        return result

    try:
        # Lấy commit SHA của maker_branch
        rev_cmd = ["git", "rev-parse", maker_branch]
        cp = subprocess.run(
            rev_cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if cp.returncode != 0:
            result["message"] = f"Không tìm thấy branch/ref '{maker_branch}': {cp.stderr.strip()}"
            return result

        commit_sha = cp.stdout.strip()
        result["commit_sha"] = commit_sha

        # Kiểm tra working tree tại root trước khi checkout commit_sha
        status_cp = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        if status_cp.returncode != 0:
            result["synced"] = False
            result["message"] = f"Lỗi kiểm tra git status tại '{root}': {status_cp.stderr.strip()}"
            return result

        if status_cp.stdout.strip() and not allow_dirty:
            result["synced"] = False
            result["message"] = (
                f"Working tree tại '{root}' có thay đổi chưa commit (uncommitted/untracked); "
                "yêu cầu commit hoặc sync cả working tree để tránh mất file của Maker."
            )
            return result

        # Nếu target_workspace là chính root repo hoặc worktree khác có .git
        if target_dir.exists() and (target_dir / ".git").exists():
            checkout_cp = subprocess.run(
                ["git", "checkout", "--detach", commit_sha],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )
            if checkout_cp.returncode == 0:
                result["synced"] = True
                result["message"] = f"Đã checkout commit '{commit_sha[:8]}' (từ nhánh '{maker_branch}') tại {target_dir}"
            else:
                result["synced"] = False
                result["message"] = f"Lỗi checkout --detach: {checkout_cp.stderr.strip()}"
        else:
            result["synced"] = False
            result["message"] = f"Target workspace '{target_dir}' không phải là Git repository hoặc worktree hợp lệ (thiếu .git)"

    except Exception as exc:
        result["message"] = f"Ngoại lệ khi đồng bộ workspace: {exc}"

    return result
