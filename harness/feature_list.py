"""Feature List Machine-Readable Primitive & WIP=1 Enforcement (Harness 2.0).

Cung cấp cấu trúc Triple Structure (behavior description, verification command, current state, completion evidence),
kiểm soát FSM chặt chẽ (not_started, active, blocked, passing), ép luật cứng WIP=1 và đo lường VCR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Union


class WIPViolationError(Exception):
    """Ném ra khi vi phạm nguyên tắc Work-In-Progress WIP=1 (nhiều hơn 1 feature active)."""


class FakePassingError(Exception):
    """Ném ra khi feature mang nhãn passing nhưng thiếu hoặc giả mạo evidence thực thi."""


class FeatureListValidationError(Exception):
    """Lỗi cấu trúc hoặc schema của feature_list.json."""


class VerificationFailedError(Exception):
    """Lỗi khi lệnh verification_command trả về exit code khác 0."""


VALID_CATEGORIES = {"core", "ui", "api", "sec", "harness", "perf"}
VALID_STATES = {"not_started", "active", "blocked", "passing"}
FEATURE_ID_REGEX = re.compile(r"^FEAT-[0-9]{3,}$")


def _compute_manifest_hash(root: Path) -> str:
    """Tính SHA256 tổng thể của các file mã nguồn trong thư mục root (loại trừ các thư mục tạm/rác)."""
    excluded_dirs = {
        ".git",
        ".brain",
        ".sessions",
        ".pytest_temp_run",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
        "artifacts",
        "execution_evidence",
        "reports",
    }
    entries: Dict[str, str] = {}
    if not root.exists() or not root.is_dir():
        return hashlib.sha256(b"empty").hexdigest()

    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in sorted(dirs) if d not in excluded_dirs]
        for name in sorted(files):
            file_path = Path(current) / name
            if (
                file_path.suffix.lower() in {".pyc", ".pyo", ".tmp", ".bak", ".swp"}
                or file_path.name == "feature_list.json"
            ):
                continue
            try:
                rel = file_path.relative_to(root).as_posix()
                entries[rel] = hashlib.sha256(file_path.read_bytes()).hexdigest()
            except (OSError, PermissionError):
                continue

    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass
class CompletionEvidence:
    executed_command: str
    exit_code: int
    output_sha256: str
    manifest_sha256: str
    verified_at: str
    verified_by: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CompletionEvidence:
        return cls(
            executed_command=str(data["executed_command"]),
            exit_code=int(data["exit_code"]),
            output_sha256=str(data["output_sha256"]),
            manifest_sha256=str(data["manifest_sha256"]),
            verified_at=str(data["verified_at"]),
            verified_by=str(data["verified_by"]),
        )


@dataclass
class VCRMetrics:
    total_features: int = 0
    not_started: int = 0
    active: int = 0
    blocked: int = 0
    passing: int = 0
    vcr_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_features": self.total_features,
            "not_started": self.not_started,
            "active": self.active,
            "blocked": self.blocked,
            "passing": self.passing,
            "vcr_score": round(self.vcr_score, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VCRMetrics:
        return cls(
            total_features=int(data.get("total_features", 0)),
            not_started=int(data.get("not_started", 0)),
            active=int(data.get("active", 0)),
            blocked=int(data.get("blocked", 0)),
            passing=int(data.get("passing", 0)),
            vcr_score=float(data.get("vcr_score", 1.0)),
        )


@dataclass
class FeatureItem:
    id: str
    category: str
    behavior_description: str
    verification_command: str
    state: str = "not_started"
    blocked_reason: Optional[str] = None
    completion_evidence: Optional[CompletionEvidence] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "behavior_description": self.behavior_description,
            "verification_command": self.verification_command,
            "state": self.state,
            "blocked_reason": self.blocked_reason,
            "completion_evidence": self.completion_evidence.to_dict() if self.completion_evidence else None,
        }
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FeatureItem:
        ev_data = data.get("completion_evidence")
        ev = CompletionEvidence.from_dict(ev_data) if ev_data else None
        return cls(
            id=str(data["id"]),
            category=str(data["category"]),
            behavior_description=str(data["behavior_description"]),
            verification_command=str(data["verification_command"]),
            state=str(data.get("state", "not_started")),
            blocked_reason=data.get("blocked_reason"),
            completion_evidence=ev,
        )


class FeatureList:
    """Quản lý danh sách tính năng máy đọc được với quy chuẩn Triple Structure và rào chắn WIP=1."""

    def __init__(
        self,
        project_id: str,
        features: Optional[List[FeatureItem]] = None,
        schema_version: str = "2.0.0",
        last_updated: Optional[str] = None,
        file_path: Optional[Path] = None,
    ):
        self.schema_version = schema_version
        self.project_id = project_id
        self.features: List[FeatureItem] = features or []
        self.last_updated = last_updated or datetime.now(timezone.utc).isoformat()
        self.file_path = file_path
        self.vcr_metrics = self.recalculate_vcr()

    def recalculate_vcr(self) -> VCRMetrics:
        """Tính toán lại chỉ số VCR (Verified Completion Rate) theo công thức chuẩn."""
        total = len(self.features)
        not_started = sum(1 for f in self.features if f.state == "not_started")
        active = sum(1 for f in self.features if f.state == "active")
        blocked = sum(1 for f in self.features if f.state == "blocked")
        passing = sum(1 for f in self.features if f.state == "passing")

        denominator = passing + active + blocked
        if denominator == 0:
            vcr_score = 1.0
        else:
            vcr_score = passing / denominator

        metrics = VCRMetrics(
            total_features=total,
            not_started=not_started,
            active=active,
            blocked=blocked,
            passing=passing,
            vcr_score=vcr_score,
        )
        self.vcr_metrics = metrics
        return metrics

    def validate(self, check_manifest_against_path: Optional[Path] = None) -> List[str]:
        """Xác thực toàn bộ danh sách tính năng theo AC-FL-01..05."""
        errors: List[str] = []

        if not self.project_id or not isinstance(self.project_id, str):
            errors.append("project_id must be a non-empty string")

        seen_ids = set()
        active_features: List[str] = []

        for idx, feat in enumerate(self.features):
            prefix = f"Feature[{idx}] ({feat.id}):"

            # AC-FL-01: Triple Structure fields validation
            if not FEATURE_ID_REGEX.match(feat.id):
                errors.append(f"{prefix} invalid ID format (must match ^FEAT-[0-9]{{3,}}$)")
            if feat.id in seen_ids:
                errors.append(f"{prefix} duplicate feature ID '{feat.id}'")
            seen_ids.add(feat.id)

            if feat.category not in VALID_CATEGORIES:
                errors.append(f"{prefix} invalid category '{feat.category}' (must be one of {sorted(VALID_CATEGORIES)})")

            if not feat.behavior_description or len(feat.behavior_description.strip()) < 10:
                errors.append(f"{prefix} behavior_description must be at least 10 characters")

            if not feat.verification_command or len(feat.verification_command.strip()) < 3:
                errors.append(f"{prefix} verification_command must be at least 3 characters")

            if feat.state not in VALID_STATES:
                errors.append(f"{prefix} invalid state '{feat.state}' (must be one of {sorted(VALID_STATES)})")

            # AC-FL-02: Track active features for WIP=1 constraint
            if feat.state == "active":
                active_features.append(feat.id)

            # AC-FL-05: Blocked state handling
            if feat.state == "blocked":
                if not feat.blocked_reason or len(feat.blocked_reason.strip()) < 10:
                    errors.append(f"{prefix} state is 'blocked' but blocked_reason is missing or < 10 chars")

            # AC-FL-03: Anti-Fake-Passing Execution Gate
            if feat.state == "passing":
                if not feat.completion_evidence:
                    errors.append(f"{prefix} state is 'passing' but completion_evidence is missing (Fake Passing rejected)")
                else:
                    ev = feat.completion_evidence
                    if ev.exit_code != 0:
                        errors.append(f"{prefix} completion_evidence has non-zero exit_code ({ev.exit_code})")
                    if not re.fullmatch(r"^[a-f0-9]{64}$", ev.output_sha256 or ""):
                        errors.append(f"{prefix} output_sha256 must be a 64-char hex string")
                    if not re.fullmatch(r"^[a-f0-9]{64}$", ev.manifest_sha256 or ""):
                        errors.append(f"{prefix} manifest_sha256 must be a 64-char hex string")

                    if check_manifest_against_path:
                        current_manifest = _compute_manifest_hash(check_manifest_against_path)
                        if ev.manifest_sha256 != current_manifest:
                            errors.append(f"{prefix} STALE completion_evidence (manifest mismatch: recorded {ev.manifest_sha256[:12]} vs current {current_manifest[:12]})")

        # Hard constraint WIP=1 enforcement
        if len(active_features) > 1:
            msg = f"WIP=1 Invariant Violated: {len(active_features)} features active simultaneously ({', '.join(active_features)})"
            raise WIPViolationError(msg)

        # Check for fake passing
        fake_passings = [e for e in errors if "Fake Passing rejected" in e or "non-zero exit_code" in e]
        if fake_passings:
            raise FakePassingError("; ".join(fake_passings))

        if errors:
            raise FeatureListValidationError("; ".join(errors))

        return errors

    def get_feature(self, feature_id: str) -> FeatureItem:
        """Tìm tính năng theo ID."""
        for feat in self.features:
            if feat.id == feature_id:
                return feat
        raise KeyError(f"Feature '{feature_id}' not found in feature list")

    def add_feature(self, feature: FeatureItem) -> FeatureItem:
        """Thêm một tính năng mới vào danh sách."""
        if any(f.id == feature.id for f in self.features):
            raise ValueError(f"Feature with ID '{feature.id}' already exists")
        if feature.state == "active":
            active_existing = [f.id for f in self.features if f.state == "active"]
            if active_existing:
                raise WIPViolationError(f"Cannot add active feature '{feature.id}': Feature '{active_existing[0]}' is already active (WIP=1 invariant)")
        self.features.append(feature)
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.recalculate_vcr()
        return feature

    def start_feature(self, feature_id: str) -> FeatureItem:
        """Kích hoạt làm một tính năng (chuyển sang 'active'), bắt buộc tuân thủ WIP=1."""
        feat = self.get_feature(feature_id)
        if feat.state == "active":
            return feat

        # Kiểm tra invariant WIP=1
        active_feats = [f for f in self.features if f.state == "active" and f.id != feature_id]
        if active_feats:
            raise WIPViolationError(
                f"Cannot activate '{feature_id}': Feature '{active_feats[0].id}' is currently active. "
                f"You must complete it (passing) or mark it blocked before starting a new feature (WIP=1 invariant)."
            )

        feat.state = "active"
        if feat.blocked_reason:
            feat.blocked_reason = None
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.recalculate_vcr()
        return feat

    def block_feature(self, feature_id: str, reason: str) -> FeatureItem:
        """Tạm dừng tính năng và chuyển sang 'blocked' kèm lý do tối thiểu 10 ký tự."""
        if not reason or len(reason.strip()) < 10:
            raise ValueError("blocked_reason must be a non-empty string of at least 10 characters")
        feat = self.get_feature(feature_id)
        feat.state = "blocked"
        feat.blocked_reason = reason.strip()
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.recalculate_vcr()
        return feat

    def unblock_feature(self, feature_id: str) -> FeatureItem:
        """Gỡ block và chuyển tính năng sang active (tuân thủ WIP=1)."""
        return self.start_feature(feature_id)

    def verify_feature(
        self,
        feature_id: str,
        actor: str = "QA_Auditor",
        project_root: Optional[Path] = None,
        timeout_seconds: float = 60.0,
    ) -> FeatureItem:
        """Thực thi verification_command thực tế độc lập; chỉ chuyển 'passing' khi exit code == 0."""
        feat = self.get_feature(feature_id)
        cmd_str = feat.verification_command.strip()

        # Kiểm tra chống mock lệnh ảo (Risk R5)
        trivial_cmds = {"exit 0", "true", "echo ok", "echo pass", "echo 1"}
        if cmd_str.lower() in trivial_cmds:
            raise VerificationFailedError(f"Rejected trivial verification_command '{cmd_str}'. Command must invoke real tests or scripts.")

        root = project_root or (self.file_path.parent if self.file_path else Path.cwd())
        root = Path(root).resolve()

        # Chạy lệnh kiểm chứng thực tế
        try:
            # Trên Windows, hỗ trợ chạy lệnh PowerShell / shell nếu cần
            proc = subprocess.run(
                cmd_str,
                shell=True,
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            combined_output = stdout + ("\n" + stderr if stderr else "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            raise VerificationFailedError(f"Verification command timed out after {timeout_seconds}s for {feature_id}") from exc
        except Exception as exc:
            raise VerificationFailedError(f"Execution failed for {feature_id}: {exc}") from exc

        if exit_code != 0:
            raise VerificationFailedError(
                f"Feature {feature_id} verification command failed with exit code {exit_code}.\nOutput:\n{combined_output}"
            )

        output_sha = hashlib.sha256(combined_output.encode("utf-8")).hexdigest()
        manifest_sha = _compute_manifest_hash(root)

        feat.completion_evidence = CompletionEvidence(
            executed_command=cmd_str,
            exit_code=0,
            output_sha256=output_sha,
            manifest_sha256=manifest_sha,
            verified_at=datetime.now(timezone.utc).isoformat(),
            verified_by=actor,
        )
        feat.state = "passing"
        self.last_updated = datetime.now(timezone.utc).isoformat()
        self.recalculate_vcr()
        return feat

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển thành từ điển JSON khớp JSON Schema v2.0.0."""
        self.recalculate_vcr()
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "last_updated": self.last_updated,
            "vcr_metrics": self.vcr_metrics.to_dict(),
            "features": [f.to_dict() for f in self.features],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        target = Path(path) if path else self.file_path
        if not target:
            raise ValueError("No file path specified to save feature_list.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(), encoding="utf-8")
        self.file_path = target
        return target

    @classmethod
    def from_dict(cls, data: Dict[str, Any], file_path: Optional[Path] = None) -> FeatureList:
        features = [FeatureItem.from_dict(item) for item in data.get("features", [])]
        inst = cls(
            project_id=str(data["project_id"]),
            features=features,
            schema_version=str(data.get("schema_version", "2.0.0")),
            last_updated=data.get("last_updated"),
            file_path=file_path,
        )
        return inst

    @classmethod
    def load_from_file(cls, path: Union[str, Path]) -> FeatureList:
        target = Path(path).resolve()
        if not target.exists():
            raise FileNotFoundError(f"Feature list file not found: {target}")
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
        return cls.from_dict(data, file_path=target)

    @classmethod
    def create_empty(cls, project_id: str, file_path: Optional[Path] = None) -> FeatureList:
        return cls(project_id=project_id, features=[], file_path=file_path)
