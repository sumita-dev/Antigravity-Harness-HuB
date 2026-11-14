#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness/evidence_cache.py

Pha 3: Evidence-as-Files & Fingerprinting Cache (Antigravity 2.0).
- EvidenceTree / EvidenceTreeBuilder: Ghi bằng chứng/artifact vượt ngưỡng ra cây thư mục
  chuẩn (task.md, deliverables/, INDEX.md, MISSION.md) thay cho cắt xén chuỗi thô.
- compute_deliverables_digest / call_fingerprint: Băm SHA-256 tất định, hỗ trợ streaming
  file lớn và chuẩn hóa kiểu dữ liệu không thuần JSON.
- EvaluationCache / CacheLedgerEntry: Cache kết quả đánh giá thread-safe (in-memory
  mặc định, tùy chọn lưu đĩa atomic trên Windows) với copy.deepcopy bảo vệ bất biến.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_WINDOWS_INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})
_CHUNK_SIZE = 65536


def sanitize_filename(name: str, default: str = "item") -> str:
    """Làm sạch tên file cho Windows (loại bỏ <>:\"/\\|?* và reserved names)."""
    cleaned = _WINDOWS_INVALID_FILENAME_RE.sub("_", str(name or ""))
    cleaned = cleaned.strip().rstrip(". ")
    if not cleaned:
        cleaned = default
    stem, dot, ext = cleaned.partition(".")
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"{stem}_file{dot}{ext}"
    return cleaned


def _json_default(obj: Any) -> Any:
    """Fallback an toàn cho json.dumps đối với Path, Enum, dataclass, bytes, object."""
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, Enum):
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, (bytes, bytearray)):
        raw = bytes(obj)
        return {
            "__bytes_sha256__": hashlib.sha256(raw).hexdigest(),
            "len": len(raw),
        }
    if isinstance(obj, (set, frozenset)):
        return sorted((_json_default_safe(x) for x in obj), key=repr)
    return repr(obj)


def _json_default_safe(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return _json_default(obj)


def _canonical_json(obj: Any) -> str:
    """Serialize tất định UTF-8, không thoát ASCII."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=_json_default)


def _hash_single_file(file_path: Path, hasher: "hashlib._Hash", max_file_bytes: int) -> None:
    """Đọc file theo chunk 64KB, giới hạn max_file_bytes và băm kèm metadata nếu bị cắt."""
    st = file_path.stat()
    remaining = max_file_bytes
    truncated = False
    with file_path.open("rb") as fh:
        while remaining > 0:
            chunk = fh.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            hasher.update(chunk)
            remaining -= len(chunk)
        if remaining == 0 and st.st_size > max_file_bytes:
            truncated = True
    if truncated:
        meta = f"|truncated=True|size={st.st_size}|mtime_ns={st.st_mtime_ns}".encode("utf-8")
        hasher.update(meta)


def compute_deliverables_digest(
    deliverables: Any,
    *,
    max_file_bytes: int = 16 * 1024 * 1024,
) -> str:
    """Tính SHA-256 tất định cho deliverables (Path thư mục/file, dict, list, str, object)."""
    if isinstance(deliverables, os.PathLike):
        p = Path(deliverables)
        hasher = hashlib.sha256()
        if p.is_dir():
            entries = sorted(p.rglob("*"), key=lambda item: item.relative_to(p).as_posix())
            for entry in entries:
                rel = entry.relative_to(p)
                if "__pycache__" in rel.parts:
                    continue
                if entry.is_file():
                    hasher.update(rel.as_posix().encode("utf-8"))
                    hasher.update(b"\0")
                    _hash_single_file(entry, hasher, max_file_bytes)
                    hasher.update(b"\0")
            return hasher.hexdigest()
        if p.is_file():
            hasher.update(p.name.encode("utf-8"))
            hasher.update(b"\0")
            _hash_single_file(p, hasher, max_file_bytes)
            return hasher.hexdigest()
        hasher.update(f"missing:{p.as_posix()}".encode("utf-8"))
        return hasher.hexdigest()

    return hashlib.sha256(_canonical_json(deliverables).encode("utf-8")).hexdigest()


def call_fingerprint(
    stage: str,
    task_prompt: str,
    deliverables_digest: str = "",
    rubrics: Any = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Tạo mã băm SHA-256 rút gọn (32 hex chars) tất định cho một lần đánh giá/tổng hợp."""
    hasher = hashlib.sha256()
    parts = [
        str(stage).encode("utf-8"),
        str(task_prompt).encode("utf-8"),
        str(deliverables_digest).encode("utf-8"),
        _canonical_json(rubrics).encode("utf-8"),
        _canonical_json(extra or {}).encode("utf-8"),
    ]
    for idx, part in enumerate(parts):
        if idx > 0:
            hasher.update(b"\0")
        hasher.update(part)
    return hasher.hexdigest()[:32]


@dataclass
class EvidenceTree:
    """Cấu trúc cây thư mục bằng chứng trên đĩa."""

    root: Path
    task_file: Path
    deliverables_dir: Path
    index_file: Path
    mission_file: Path
    files: List[str] = field(default_factory=list)
    total_bytes: int = 0
    deliverables_digest: str = ""
    mission_text: str = ""
    auto_created_tmp: bool = False

    def to_evidence_paths(self) -> List[str]:
        """Trả về danh sách đường dẫn tương thích với TriadHandoffV2.evidence_paths."""
        paths = [
            str(self.index_file),
            str(self.mission_file),
            str(self.task_file),
        ]
        for rel in self.files:
            candidate = str(self.root / rel)
            if candidate not in paths:
                paths.append(candidate)
        return paths

    def cleanup(self) -> None:
        """Xóa thư mục gốc nếu được tạo tự động trong temp dir."""
        if self.auto_created_tmp and self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


class EvidenceTreeBuilder:
    """Ghi toàn bộ bằng chứng/artifact vượt ngưỡng ra cấu trúc thư mục chuẩn."""

    def __init__(
        self,
        threshold_chars: int = 4000,
        base_dir: Optional[Union[str, Path]] = None,
    ):
        self.threshold_chars = max(0, int(threshold_chars))
        self.base_dir = Path(base_dir) if base_dir is not None else None

    def should_spill(self, *parts: Any) -> bool:
        """Kiểm tra tổng độ dài ký tự UTF-8 có vượt threshold_chars hay không."""
        total = 0
        for part in parts:
            if part is None:
                continue
            if isinstance(part, str):
                total += len(part)
            else:
                total += len(_canonical_json(part))
            if total > self.threshold_chars:
                return True
        return False

    def build(
        self,
        task_id: str,
        task_prompt: str,
        deliverables: Dict[str, Any],
        *,
        stage: str = "EVALUATION",
        dest_dir: Optional[Union[str, Path]] = None,
        mission_instructions: str = "",
    ) -> EvidenceTree:
        """Tạo cây thư mục bằng chứng (task.md, deliverables/*, INDEX.md, MISSION.md)."""
        if dest_dir is not None:
            root = Path(dest_dir)
            auto_created_tmp = False
        elif self.base_dir is not None:
            safe_dir_name = sanitize_filename(f"{task_id}_{stage}", default="evidence")
            root = self.base_dir / safe_dir_name
            auto_created_tmp = False
        else:
            root = Path(tempfile.mkdtemp(prefix="ag_evidence_"))
            auto_created_tmp = True

        deliverables_dir = root / "deliverables"
        deliverables_dir.mkdir(parents=True, exist_ok=True)

        task_file = root / "task.md"
        task_content = (
            f"# Task Context: {task_id}\n\n"
            f"- **Stage:** `{stage}`\n\n"
            f"## Prompt / Specification\n\n{task_prompt or '(empty)'}\n"
        )
        task_file.write_text(task_content, encoding="utf-8")

        written_files: List[str] = []
        index_rows: List[str] = []
        total_bytes = task_file.stat().st_size
        used_names: set[str] = set()

        for idx, (key, value) in enumerate(deliverables.items()):
            raw_name = str(key)
            safe_name = sanitize_filename(raw_name, default=f"deliverable_{idx}")
            is_str = isinstance(value, str)

            if "." not in safe_name:
                lower_key = raw_name.lower()
                if is_str:
                    ext = ".log" if any(t in lower_key for t in ("log", "stdout", "stderr")) else ".md"
                else:
                    ext = ".json"
                safe_name = f"{safe_name}{ext}"

            while safe_name in used_names:
                stem, dot, ext = safe_name.rpartition(".")
                if dot:
                    safe_name = f"{stem}_{idx}{dot}{ext}"
                else:
                    safe_name = f"{safe_name}_{idx}"
            used_names.add(safe_name)

            if is_str:
                serialized = value
            else:
                serialized = json.dumps(value, indent=2, ensure_ascii=False, default=_json_default)

            target_path = deliverables_dir / safe_name
            target_path.write_text(serialized, encoding="utf-8")
            raw_bytes = target_path.read_bytes()
            file_size = len(raw_bytes)
            file_sha = hashlib.sha256(raw_bytes).hexdigest()
            total_bytes += file_size

            rel_path = f"deliverables/{safe_name}"
            written_files.append(rel_path)
            index_rows.append(f"| `{rel_path}` | {file_size} | `{file_sha[:16]}...` |")

        deliverables_digest = compute_deliverables_digest(deliverables)

        index_file = root / "INDEX.md"
        index_lines = [
            f"# Evidence Index — {task_id} ({stage})",
            "",
            f"- **Deliverables Digest:** `{deliverables_digest}`",
            f"- **Total Deliverables:** {len(written_files)}",
            "",
            "| File | Bytes | SHA-256 |",
            "|---|---:|---|",
            *index_rows,
            "",
        ]
        index_file.write_text("\n".join(index_lines), encoding="utf-8")
        total_bytes += index_file.stat().st_size

        mission_file = root / "MISSION.md"
        mission_body = [
            f"# Mission Brief — {task_id} ({stage})",
            "",
            "Bằng chứng vượt ngưỡng kích thước đã được ghi đầy đủ ra tệp để tránh cắt xén ngữ cảnh:",
            f"- Đề bài & ngữ cảnh: `{task_file}`",
            f"- Mục lục & checksum: `{index_file}`",
            f"- Thư mục hiện vật: `{deliverables_dir}`",
        ]
        if mission_instructions:
            mission_body.extend(["", "## Chỉ dẫn kiểm định", "", mission_instructions])
        mission_text = "\n".join(mission_body) + "\n"
        mission_file.write_text(mission_text, encoding="utf-8")
        total_bytes += mission_file.stat().st_size

        return EvidenceTree(
            root=root,
            task_file=task_file,
            deliverables_dir=deliverables_dir,
            index_file=index_file,
            mission_file=mission_file,
            files=written_files,
            total_bytes=total_bytes,
            deliverables_digest=deliverables_digest,
            mission_text=mission_text,
            auto_created_tmp=auto_created_tmp,
        )


@dataclass
class CacheLedgerEntry:
    """Mục sổ cái ghi nhận vòng đời một fingerprint trong cache."""

    fingerprint: str
    stage: str
    created_at: float
    hits: int = 0


class EvaluationCache:
    """Cache kết quả đánh giá thread-safe (in-memory mặc định, tùy chọn lưu đĩa atomic)."""

    def __init__(
        self,
        cache_dir: Optional[Union[str, Path]] = None,
        enabled: bool = True,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.enabled = bool(enabled)
        self._lock = threading.RLock()
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ledger: Dict[str, CacheLedgerEntry] = {}
        self._hits = 0
        self._misses = 0
        self._puts = 0

    def _disk_path(self, fingerprint: str) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{sanitize_filename(fingerprint)}.json"

    def get(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        with self._lock:
            if fingerprint in self._store:
                self._hits += 1
                entry = self._ledger.get(fingerprint)
                if entry is not None:
                    entry.hits += 1
                return copy.deepcopy(self._store[fingerprint])

            disk_path = self._disk_path(fingerprint)
            if disk_path is not None and disk_path.is_file():
                try:
                    raw = json.loads(disk_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        payload = raw.get("value", raw)
                        stage = str(raw.get("stage", "")) if isinstance(raw, dict) else ""
                        if isinstance(payload, dict):
                            self._store[fingerprint] = copy.deepcopy(payload)
                            self._ledger[fingerprint] = CacheLedgerEntry(
                                fingerprint=fingerprint,
                                stage=stage,
                                created_at=float(raw.get("created_at", time.time())),
                                hits=1,
                            )
                            self._hits += 1
                            return copy.deepcopy(payload)
                except Exception:
                    pass

            self._misses += 1
            return None

    def put(self, fingerprint: str, value: Dict[str, Any], *, stage: str = "") -> None:
        if not self.enabled:
            return
        with self._lock:
            cloned = copy.deepcopy(value)
            now = time.time()
            self._store[fingerprint] = cloned
            self._ledger[fingerprint] = CacheLedgerEntry(
                fingerprint=fingerprint,
                stage=stage,
                created_at=now,
                hits=0,
            )
            self._puts += 1

            disk_path = self._disk_path(fingerprint)
            if disk_path is not None:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                envelope = {
                    "fingerprint": fingerprint,
                    "stage": stage,
                    "created_at": now,
                    "value": cloned,
                }
                serialized = json.dumps(envelope, ensure_ascii=False, indent=2, default=_json_default)
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=str(self.cache_dir),
                        delete=False,
                        suffix=".tmp",
                    ) as tf:
                        tf.write(serialized)
                        tmp_path = tf.name
                    os.replace(tmp_path, disk_path)
                except Exception:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                    raise

    def invalidate(self, fingerprint: str) -> bool:
        with self._lock:
            removed = False
            if fingerprint in self._store:
                del self._store[fingerprint]
                removed = True
            if fingerprint in self._ledger:
                del self._ledger[fingerprint]
                removed = True
            disk_path = self._disk_path(fingerprint)
            if disk_path is not None and disk_path.exists():
                disk_path.unlink()
                removed = True
            return removed

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._ledger.clear()
            self._hits = 0
            self._misses = 0
            self._puts = 0
            if self.cache_dir is not None and self.cache_dir.is_dir():
                for item in self.cache_dir.glob("*.json"):
                    try:
                        item.unlink()
                    except OSError:
                        pass

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "hits": self._hits,
                "misses": self._misses,
                "puts": self._puts,
                "entries": len(self._store),
                "ledger": {
                    fp: dataclasses.asdict(entry)
                    for fp, entry in self._ledger.items()
                },
            }
