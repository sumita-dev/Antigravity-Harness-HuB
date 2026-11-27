"""3-Layer Host Watch & Disk I/O Protection for Antigravity Harness Hub.

Provides cross-platform (Windows & POSIX) safeguards against disk thrashing and
concurrent heavy I/O storms:
1. OS priority throttling (`apply_low_io_priority`).
2. Typed atomic concurrency slots (`acquire_host_slot`, `HostGateSlot`).
3. Disk I/O EMA telemetry, admission control, and PreInvocation cooldown notices.
4. Bounded LRU cache pruning, pytest temp cleanup, and read-only storage advisories.
"""

from __future__ import annotations

import json
import ntpath
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence, Union

try:
    import psutil
except ImportError:  # pragma: no cover - declared in requirements.txt
    psutil = None  # type: ignore[assignment]

POOL_CAPS: dict[str, int] = {
    "io_heavy": 1,
    "compute_io": 2,
}

CATEGORY_TO_POOL: dict[str, str] = {
    "io_heavy": "io_heavy",
    "install": "io_heavy",
    "worktree": "io_heavy",
    "compute_io": "compute_io",
    "build": "compute_io",
    "test": "compute_io",
}

DEFAULT_WAIT_TIMEOUT_SEC = 45.0
DEFAULT_MAX_LEASE_SEC = 600.0
RECLAIM_LOCK_TTL_SEC = 5.0
DEFAULT_CACHE_MAX_BYTES = 30 * 1024**3
DEFAULT_CACHE_MAX_AGE_DAYS = 7.0
DEFAULT_COOLDOWN_SEC = 300.0
EMA_ALPHA = 0.35

SEVERITY_RANK: dict[str, int] = {
    "GREEN": 0,
    "YELLOW": 1,
    "RED": 2,
}

_EXE_SUFFIX_RE = re.compile(r"\.(?:exe|cmd|bat|ps1)$", re.IGNORECASE)
_SLOT_LOCK_STEM_RE = re.compile(r"^([a-z_]+)_(\d+)$")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

_PYTHON_VALUE_FLAGS = frozenset({"-X", "-W", "--check-hash-based-pycs"})
_JS_PM_VALUE_FLAGS = frozenset({
    "--filter", "-F", "--prefix", "-C", "--cwd", "--workspace", "-w",
    "--store-dir", "--cache", "--registry", "--config", "--userconfig", "--loglevel",
})
_GIT_VALUE_FLAGS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
_UV_VALUE_FLAGS = frozenset({
    "--directory", "--project", "--python", "--extra", "--with", "--group",
    "--from", "--index", "--index-url", "-p", "-C",
})
_GENERIC_VALUE_FLAGS = frozenset({"-C", "--manifest-path", "--target-dir", "--package", "-p"})


def _is_windows(platform_name: Optional[str] = None) -> bool:
    """Return True when targeting Windows (overridable cleanly in tests)."""
    if platform_name is not None:
        return platform_name.lower() in ("nt", "win32", "windows")
    return os.name == "nt"


class HostGateBusyError(RuntimeError):
    """Raised when a typed concurrency pool remains full after wait_timeout."""

    def __init__(self, pool: str, cap: int, wait_timeout: float) -> None:
        self.pool = pool
        self.cap = cap
        self.wait_timeout = wait_timeout
        super().__init__(
            f"Host gate pool '{pool}' busy (cap={cap}) after waiting {wait_timeout:.1f}s"
        )


@dataclass
class HostGateSlot:
    """Handle for an acquired concurrency slot lock file."""

    pool: str
    slot_index: int
    lock_path: Path
    pid: int
    created_at: float
    token: str = field(default_factory=lambda: uuid.uuid4().hex)
    acquired: bool = True

    def release(self) -> None:
        """Release the slot lock file safely only when PID and token match."""
        if not self.acquired:
            return
        self.acquired = False
        try:
            data = _read_json(self.lock_path)
            if not isinstance(data, dict):
                return
            if data.get("pid") != self.pid or data.get("token") != self.token:
                return
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self) -> "HostGateSlot":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()


def get_state_dir(state_dir: Optional[Union[str, Path]] = None) -> Path:
    """Return the Host Watch runtime state directory outside the repo."""
    if state_dir is not None:
        return Path(state_dir)
    env_dir = os.environ.get("ANTIGRAVITY_HOST_WATCH_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return Path(tempfile.gettempdir()) / "antigravity-host-watch"


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via sibling temp file + os.replace with lock retry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(payload)
        for attempt in range(6):
            try:
                os.replace(tmp_path, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _read_json(path: Path, default: Any = None) -> Any:
    """Fail-open JSON reader returning default on missing or corrupt files."""
    try:
        if not path.is_file():
            return default
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return default
        return json.loads(raw)
    except (OSError, ValueError, TypeError):
        return default


def apply_low_io_priority(
    pid: Optional[int] = None,
    *,
    platform_name: Optional[str] = None,
) -> bool:
    """Lower I/O and CPU scheduling priority for a target process (fail-open)."""
    if psutil is None:
        return False
    target_pid = pid or os.getpid()
    try:
        proc = psutil.Process(target_pid)
    except Exception:
        return False

    applied_any = False

    if _is_windows(platform_name):
        ioprio = getattr(psutil, "IOPRIO_VERYLOW", None)
        if ioprio is not None and hasattr(proc, "ionice"):
            try:
                proc.ionice(ioprio)
                applied_any = True
            except Exception:
                pass
        cpu_prio = getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", None)
        if cpu_prio is not None and hasattr(proc, "nice"):
            try:
                proc.nice(cpu_prio)
                applied_any = True
            except Exception:
                pass
    else:
        if hasattr(proc, "ionice"):
            idle_cls = getattr(psutil, "IOPRIO_CLASS_IDLE", None)
            be_cls = getattr(psutil, "IOPRIO_CLASS_BE", None)
            if idle_cls is not None:
                try:
                    proc.ionice(idle_cls)
                    applied_any = True
                except Exception:
                    if be_cls is not None:
                        try:
                            proc.ionice(be_cls, 7)
                            applied_any = True
                        except Exception:
                            pass
            elif be_cls is not None:
                try:
                    proc.ionice(be_cls, 7)
                    applied_any = True
                except Exception:
                    pass

        if hasattr(proc, "nice"):
            try:
                current_nice = proc.nice()
                target_nice = max(int(current_nice), 10)
                if target_nice != current_nice:
                    proc.nice(target_nice)
                applied_any = True
            except Exception:
                pass

    return applied_any


def _tokenize_command(cmd: Union[str, Sequence[str]]) -> list[str]:
    if isinstance(cmd, str):
        cleaned = cmd.strip()
        if not cleaned:
            return []
        try:
            return shlex.split(cleaned, posix=(os.name != "nt"))
        except ValueError:
            return cleaned.split()
    return [str(tok) for tok in cmd if str(tok)]


def _norm_exe(token: str) -> str:
    return _EXE_SUFFIX_RE.sub("", Path(token).name.lower())


def _extract_positional_args(
    tokens: Sequence[str],
    value_flags: frozenset[str] = frozenset(),
) -> list[str]:
    """Extract positional tokens while skipping boolean and value-taking flags."""
    pos: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            pos.extend(tokens[i + 1 :])
            break
        if tok in value_flags:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        pos.append(tok)
        i += 1
    return pos


def classify_command_pool(cmd: Union[str, Sequence[str]]) -> Optional[str]:
    """Classify a command into 'io_heavy', 'compute_io', or None (ungated)."""
    tokens = _tokenize_command(cmd)
    if not tokens:
        return None

    exe = _norm_exe(tokens[0])
    rest = tokens[1:]

    # Unwrap python / py invocations (e.g. python -X utf8 -m pytest, py -3.12 scripts/run_pytest_windows.py)
    if exe in ("python", "python3", "py"):
        idx = 0
        while idx < len(rest):
            tok = rest[idx]
            if tok == "-m" and idx + 1 < len(rest):
                mod = rest[idx + 1].lower()
                sub_args = [a.lower() for a in rest[idx + 2 :]]
                if mod == "pip" and "install" in sub_args:
                    return "io_heavy"
                if mod == "pytest":
                    return "compute_io"
                return None
            if tok == "-c":
                return None
            if tok in _PYTHON_VALUE_FLAGS:
                idx += 2
                continue
            if tok.startswith("-"):
                idx += 1
                continue
            script_name = _norm_exe(tok)
            if "run_pytest_windows" in script_name or script_name == "pytest":
                return "compute_io"
            return None
        return None

    if exe in ("pnpm", "npm", "yarn"):
        sub_tokens = [t.lower() for t in _extract_positional_args(rest, _JS_PM_VALUE_FLAGS)]
        if not sub_tokens:
            return None
        sub = sub_tokens[0]
        if sub in ("install", "i", "add", "ci"):
            return "io_heavy"
        if sub in ("test", "t", "build"):
            return "compute_io"
        if sub in ("run", "exec") and len(sub_tokens) >= 2:
            script = sub_tokens[1]
            if script in ("build", "test") or script.startswith(("build:", "test:")):
                return "compute_io"
        return None

    if exe in ("pip", "pip3"):
        sub_tokens = [t.lower() for t in _extract_positional_args(rest)]
        if sub_tokens and sub_tokens[0] == "install":
            return "io_heavy"
        return None

    if exe == "uv":
        sub_tokens = [t.lower() for t in _extract_positional_args(rest, _UV_VALUE_FLAGS)]
        if len(sub_tokens) >= 2 and sub_tokens[0] == "pip" and sub_tokens[1] == "install":
            return "io_heavy"
        if sub_tokens and sub_tokens[0] in ("sync", "add"):
            return "io_heavy"
        if len(sub_tokens) >= 2 and sub_tokens[0] == "run" and _norm_exe(sub_tokens[1]) == "pytest":
            return "compute_io"
        return None

    if exe == "git":
        sub_tokens = [t.lower() for t in _extract_positional_args(rest, _GIT_VALUE_FLAGS)]
        if sub_tokens and sub_tokens[0] == "worktree":
            return "io_heavy"
        return None

    if exe == "go":
        sub_tokens = [t.lower() for t in _extract_positional_args(rest, _GENERIC_VALUE_FLAGS)]
        if sub_tokens and sub_tokens[0] in ("test", "build"):
            return "compute_io"
        return None

    if exe == "cargo":
        sub_tokens = [t.lower() for t in _extract_positional_args(rest, _GENERIC_VALUE_FLAGS)]
        if sub_tokens and sub_tokens[0] in ("build", "test", "check"):
            return "compute_io"
        return None

    if exe in ("pytest", "py.test", "tsc", "vitest", "jest") or "run_pytest_windows" in exe:
        return "compute_io"

    if exe in ("npx", "pnpx", "bunx"):
        sub_tokens = [_norm_exe(t) for t in _extract_positional_args(rest)]
        if sub_tokens and sub_tokens[0] in ("tsc", "vitest", "jest"):
            return "compute_io"
        return None

    return None


def resolve_pool(
    category: Optional[str],
    cmd: Union[str, Sequence[str], None] = None,
) -> Optional[str]:
    """Resolve a category name or 'auto' into a concrete slot pool or None."""
    if category is None:
        return None
    norm = str(category).strip().lower()
    if not norm or norm in ("none", "ungated"):
        return None
    if norm == "auto":
        return classify_command_pool(cmd or "")
    if norm in CATEGORY_TO_POOL:
        return CATEGORY_TO_POOL[norm]
    return None


def _is_lock_stale(lock_path: Path, max_lease_sec: float) -> bool:
    """Return True when a slot lock file belongs to a dead PID or expired lease."""
    try:
        st = lock_path.stat()
    except OSError:
        return False

    now = time.time()
    age_mtime = max(0.0, now - st.st_mtime)
    data = _read_json(lock_path)
    if not isinstance(data, dict) or not data:
        # Leave brand-new empty files briefly so writer between O_EXCL and os.write finishes.
        return age_mtime > min(2.0, max_lease_sec)

    pid = data.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return age_mtime > min(2.0, max_lease_sec)

    if psutil is not None:
        try:
            if not psutil.pid_exists(pid):
                return True
        except Exception:
            pass

    created_at = data.get("created_at")
    if isinstance(created_at, (int, float)):
        return (now - float(created_at)) > max_lease_sec
    return age_mtime > max_lease_sec


def _create_slot_lock_file(
    lock_path: Path,
    pool: str,
    idx: int,
    cmd_str: str,
) -> HostGateSlot:
    """Atomically create slot lock file with PID + unique token, cleaning up on write error."""
    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
    created_at = time.time()
    pid = os.getpid()
    token = uuid.uuid4().hex
    payload = json.dumps(
        {
            "pid": pid,
            "token": token,
            "created_at": created_at,
            "cmd": cmd_str,
            "pool": pool,
            "slot_index": idx,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    write_ok = False
    try:
        os.write(fd, payload)
        write_ok = True
    finally:
        try:
            os.close(fd)
        finally:
            if not write_ok:
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
    return HostGateSlot(
        pool=pool,
        slot_index=idx,
        lock_path=lock_path,
        pid=pid,
        created_at=created_at,
        token=token,
        acquired=True,
    )


def _acquire_reclaim_lock(reclaim_path: Path) -> Optional[str]:
    """Acquire per-slot atomic reclaim lock; evict only if its own TTL/PID expired."""
    token = uuid.uuid4().hex
    for attempt in range(2):
        try:
            fd = os.open(str(reclaim_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            payload = json.dumps(
                {"pid": os.getpid(), "token": token, "created_at": time.time()}
            ).encode("utf-8")
            write_ok = False
            try:
                os.write(fd, payload)
                write_ok = True
            finally:
                try:
                    os.close(fd)
                finally:
                    if not write_ok:
                        try:
                            reclaim_path.unlink(missing_ok=True)
                        except OSError:
                            pass
            return token
        except FileExistsError:
            if attempt == 0 and _is_lock_stale(reclaim_path, RECLAIM_LOCK_TTL_SEC):
                try:
                    reclaim_path.unlink(missing_ok=True)
                    continue
                except OSError:
                    return None
            return None
        except OSError:
            return None
    return None


def _release_reclaim_lock(reclaim_path: Path, token: str) -> None:
    try:
        data = _read_json(reclaim_path)
        if isinstance(data, dict) and data.get("token") == token and data.get("pid") == os.getpid():
            reclaim_path.unlink(missing_ok=True)
    except OSError:
        pass


def _try_acquire_pool_slot(
    pool: str,
    cap: int,
    slots_dir: Path,
    max_lease_sec: float,
    cmd_str: str,
) -> Optional[HostGateSlot]:
    slots_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(cap):
        lock_path = slots_dir / f"{pool}_{idx}.lock"
        try:
            return _create_slot_lock_file(lock_path, pool, idx, cmd_str)
        except FileExistsError:
            if not _is_lock_stale(lock_path, max_lease_sec):
                continue
            reclaim_path = slots_dir / f"{pool}_{idx}.reclaim.lock"
            reclaim_token = _acquire_reclaim_lock(reclaim_path)
            if reclaim_token is None:
                continue
            try:
                # Re-verify staleness inside the atomic reclaim lock to avoid TOCTOU races.
                if lock_path.exists() and not _is_lock_stale(lock_path, max_lease_sec):
                    continue
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    continue
                try:
                    return _create_slot_lock_file(lock_path, pool, idx, cmd_str)
                except (FileExistsError, OSError):
                    continue
            finally:
                _release_reclaim_lock(reclaim_path, reclaim_token)
        except OSError:
            continue
    return None


@contextmanager
def acquire_host_slot(
    category_or_cmd: Optional[str] = "auto",
    *,
    state_dir: Optional[Union[str, Path]] = None,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT_SEC,
    max_lease_sec: float = DEFAULT_MAX_LEASE_SEC,
    cmd: Union[str, Sequence[str], None] = None,
) -> Iterator[Optional[HostGateSlot]]:
    """Acquire a typed concurrency slot, reclaiming stale locks or failing fast."""
    pool = resolve_pool(category_or_cmd, cmd=cmd)
    if pool is None:
        yield None
        return

    cap = POOL_CAPS[pool]
    slots_dir = get_state_dir(state_dir) / "slots"
    if isinstance(cmd, (list, tuple)):
        cmd_str = " ".join(str(x) for x in cmd)
    else:
        cmd_str = str(cmd or category_or_cmd or "")

    timeout = max(0.0, float(wait_timeout))
    deadline = time.monotonic() + timeout
    slot: Optional[HostGateSlot] = None

    while True:
        slot = _try_acquire_pool_slot(pool, cap, slots_dir, max_lease_sec, cmd_str)
        if slot is not None:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HostGateBusyError(pool=pool, cap=cap, wait_timeout=timeout)
        time.sleep(min(0.1, max(0.01, remaining)))

    try:
        yield slot
    finally:
        slot.release()


def count_active_slots(
    state_dir: Optional[Union[str, Path]] = None,
    max_lease_sec: float = DEFAULT_MAX_LEASE_SEC,
) -> dict[str, int]:
    """Count non-stale active slots per pool."""
    counts = {pool: 0 for pool in POOL_CAPS}
    slots_dir = get_state_dir(state_dir) / "slots"
    if not slots_dir.is_dir():
        return counts
    for lock_file in slots_dir.glob("*.lock"):
        if lock_file.name.endswith(".reclaim.lock"):
            continue
        match = _SLOT_LOCK_STEM_RE.match(lock_file.stem)
        if not match:
            continue
        pool = match.group(1)
        if pool not in counts:
            continue
        if _is_lock_stale(lock_file, max_lease_sec):
            continue
        counts[pool] += 1
    return counts


def compute_pressure_level(
    *,
    ema_bytes_per_sec: float = 0.0,
    ema_iops: float = 0.0,
    ema_avg_latency_ms: float = 0.0,
    active_slots: Optional[dict[str, int]] = None,
    memory_percent: float = 0.0,
    disk_free_bytes: Optional[int] = None,
) -> str:
    """Compute host I/O pressure level ('GREEN', 'YELLOW', or 'RED')."""
    slots = active_slots or {}
    io_heavy = int(slots.get("io_heavy", 0))
    compute_io = int(slots.get("compute_io", 0))

    if (
        ema_avg_latency_ms >= 50.0
        or ema_iops >= 15000.0
        or ema_bytes_per_sec >= 400.0 * 1024 * 1024
        or (ema_bytes_per_sec >= 250.0 * 1024 * 1024 and ema_iops >= 5000.0)
        or (io_heavy >= 1 and compute_io >= 2 and ema_avg_latency_ms >= 20.0)
        or memory_percent >= 98.0
        or (disk_free_bytes is not None and disk_free_bytes < 1 * 1024**3)
    ):
        return "RED"

    if (
        ema_avg_latency_ms >= 20.0
        or ema_iops >= 4000.0
        or ema_bytes_per_sec >= 120.0 * 1024 * 1024
        or (io_heavy >= 1 and compute_io >= 1)
        or memory_percent >= 95.0
        or (disk_free_bytes is not None and disk_free_bytes < 5 * 1024**3)
    ):
        return "YELLOW"

    return "GREEN"


def _default_host_status(state_dir: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    return {
        "timestamp": 0.0,
        "level": "GREEN",
        "bytes_per_sec": 0.0,
        "iops": 0.0,
        "avg_latency_ms": 0.0,
        "ema_bytes_per_sec": 0.0,
        "ema_iops": 0.0,
        "ema_avg_latency_ms": 0.0,
        "active_slots": count_active_slots(state_dir=state_dir),
        "memory_percent": 0.0,
        "memory_available_bytes": 0,
        "disk_free_bytes": None,
        "disk_total_bytes": None,
        "last_counters": None,
    }


def sample_host_io(state_dir: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """Sample disk I/O counters, update EMA metrics, and persist host_status.json."""
    resolved_dir = get_state_dir(state_dir)
    status_path = resolved_dir / "host_status.json"
    prev = _read_json(status_path)
    if not isinstance(prev, dict):
        prev = {}

    now = time.time()
    bytes_per_sec = float(prev.get("bytes_per_sec", 0.0) or 0.0)
    iops = float(prev.get("iops", 0.0) or 0.0)
    avg_latency_ms = float(prev.get("avg_latency_ms", 0.0) or 0.0)
    ema_bps = float(prev.get("ema_bytes_per_sec", 0.0) or 0.0)
    ema_iops = float(prev.get("ema_iops", 0.0) or 0.0)
    ema_lat = float(prev.get("ema_avg_latency_ms", 0.0) or 0.0)
    ema_initialized = bool(prev.get("ema_initialized", False))

    last_counters: Optional[dict[str, Any]] = prev.get("last_counters")
    counters = None
    if psutil is not None:
        try:
            counters = psutil.disk_io_counters()
        except Exception:
            counters = None

    if counters is not None:
        cur_counters = {
            "read_count": int(getattr(counters, "read_count", 0) or 0),
            "write_count": int(getattr(counters, "write_count", 0) or 0),
            "read_bytes": int(getattr(counters, "read_bytes", 0) or 0),
            "write_bytes": int(getattr(counters, "write_bytes", 0) or 0),
            "read_time": int(getattr(counters, "read_time", 0) or 0),
            "write_time": int(getattr(counters, "write_time", 0) or 0),
            "timestamp": now,
        }
        if isinstance(last_counters, dict) and last_counters.get("timestamp"):
            dt = now - float(last_counters["timestamp"])
            if dt > 0.001:
                d_reads = max(0, cur_counters["read_count"] - int(last_counters.get("read_count", 0)))
                d_writes = max(0, cur_counters["write_count"] - int(last_counters.get("write_count", 0)))
                d_bytes = max(
                    0,
                    (cur_counters["read_bytes"] - int(last_counters.get("read_bytes", 0)))
                    + (cur_counters["write_bytes"] - int(last_counters.get("write_bytes", 0))),
                )
                d_time_ms = max(
                    0,
                    (cur_counters["read_time"] - int(last_counters.get("read_time", 0)))
                    + (cur_counters["write_time"] - int(last_counters.get("write_time", 0))),
                )
                d_ops = d_reads + d_writes
                bytes_per_sec = d_bytes / dt
                iops = d_ops / dt
                avg_latency_ms = (d_time_ms / d_ops) if d_ops > 0 else 0.0

                if ema_initialized:
                    ema_bps = EMA_ALPHA * bytes_per_sec + (1.0 - EMA_ALPHA) * ema_bps
                    ema_iops = EMA_ALPHA * iops + (1.0 - EMA_ALPHA) * ema_iops
                    ema_lat = EMA_ALPHA * avg_latency_ms + (1.0 - EMA_ALPHA) * ema_lat
                else:
                    ema_bps = bytes_per_sec
                    ema_iops = iops
                    ema_lat = avg_latency_ms
                    ema_initialized = True
        else:
            bytes_per_sec = 0.0
            iops = 0.0
            avg_latency_ms = 0.0
            ema_bps = 0.0
            ema_iops = 0.0
            ema_lat = 0.0
            ema_initialized = False
        last_counters = cur_counters

    mem_percent = 0.0
    mem_avail = 0
    disk_free: Optional[int] = None
    disk_total: Optional[int] = None
    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            mem_percent = float(vm.percent)
            mem_avail = int(vm.available)
        except Exception:
            pass
        try:
            du = psutil.disk_usage(str(resolved_dir if resolved_dir.exists() else Path.cwd()))
            disk_free = int(du.free)
            disk_total = int(du.total)
        except Exception:
            pass

    active_slots = count_active_slots(state_dir=resolved_dir)
    level = compute_pressure_level(
        ema_bytes_per_sec=ema_bps,
        ema_iops=ema_iops,
        ema_avg_latency_ms=ema_lat,
        active_slots=active_slots,
        memory_percent=mem_percent,
        disk_free_bytes=disk_free,
    )

    snapshot = {
        "timestamp": now,
        "level": level,
        "bytes_per_sec": round(bytes_per_sec, 2),
        "iops": round(iops, 2),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "ema_bytes_per_sec": round(ema_bps, 2),
        "ema_iops": round(ema_iops, 2),
        "ema_avg_latency_ms": round(ema_lat, 3),
        "ema_initialized": ema_initialized,
        "active_slots": active_slots,
        "memory_percent": round(mem_percent, 1),
        "memory_available_bytes": mem_avail,
        "disk_free_bytes": disk_free,
        "disk_total_bytes": disk_total,
        "last_counters": last_counters,
    }
    try:
        _atomic_write_json(status_path, snapshot)
    except OSError:
        pass
    return snapshot


def read_host_status(state_dir: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """Read the persisted host_status.json snapshot safely (fail-open to GREEN)."""
    resolved_dir = get_state_dir(state_dir)
    data = _read_json(resolved_dir / "host_status.json")
    if not isinstance(data, dict) or not data:
        return _default_host_status(resolved_dir)
    merged = _default_host_status(resolved_dir)
    merged.update(data)
    if merged.get("level") not in SEVERITY_RANK:
        merged["level"] = "GREEN"
    return merged


def refresh_if_stale(
    state_dir: Optional[Union[str, Path]] = None,
    max_age_sec: float = 10.0,
) -> dict[str, Any]:
    """Refresh host telemetry in-process when snapshot is missing or older than max_age_sec."""
    resolved_dir = get_state_dir(state_dir)
    status_path = resolved_dir / "host_status.json"
    data = _read_json(status_path)
    if isinstance(data, dict) and data:
        ts = data.get("timestamp")
        if ts is None and data.get("level") in SEVERITY_RANK:
            return read_host_status(resolved_dir)
        if isinstance(ts, (int, float)) and (time.time() - float(ts)) <= max_age_sec:
            return read_host_status(resolved_dir)
    return sample_host_io(resolved_dir)


def get_fan_out_admission(
    requested: int,
    state_dir: Optional[Union[str, Path]] = None,
) -> tuple[int, dict[str, Any]]:
    """Read host status once and return (effective_concurrency, status_snapshot)."""
    req = max(1, int(requested))
    status = read_host_status(state_dir=state_dir)
    level = str(status.get("level", "GREEN")).upper()
    if level == "RED":
        return 1, status
    if level == "YELLOW":
        return min(req, 2), status
    return req, status


def recommend_fan_out_concurrency(
    requested: int,
    state_dir: Optional[Union[str, Path]] = None,
) -> int:
    """Compute pressure-aware fan-out concurrency: GREEN->req, YELLOW->min(req,2), RED->1."""
    concurrency, _status = get_fan_out_admission(requested, state_dir=state_dir)
    return concurrency


def get_pre_invocation_host_notice(
    state_dir: Optional[Union[str, Path]] = None,
    conversation_id: str = "",
    cooldown_sec: float = DEFAULT_COOLDOWN_SEC,
) -> Optional[str]:
    """Return a 1-line warning on YELLOW/RED outside cooldown (unless escalated)."""
    resolved_dir = get_state_dir(state_dir)
    status_path = resolved_dir / "host_status.json"
    raw = _read_json(status_path)
    if isinstance(raw, dict) and raw:
        ts = raw.get("timestamp")
        if isinstance(ts, (int, float)) and (time.time() - float(ts)) > 30.0:
            status = sample_host_io(resolved_dir)
        else:
            status = read_host_status(resolved_dir)
    else:
        status = sample_host_io(resolved_dir)

    level = str(status.get("level", "GREEN")).upper()
    cur_rank = SEVERITY_RANK.get(level, 0)
    if cur_rank <= 0:
        return None

    notice_path = resolved_dir / "notice_state.json"
    state = _read_json(notice_path)
    if not isinstance(state, dict):
        state = {}
    by_conv = state.get("by_conversation")
    if not isinstance(by_conv, dict):
        by_conv = {}

    now = time.time()
    key = conversation_id.strip() or "_host"
    prev = by_conv.get(key)
    if isinstance(prev, dict):
        elapsed = now - float(prev.get("last_ts", 0.0) or 0.0)
        prev_rank = SEVERITY_RANK.get(str(prev.get("last_level", "GREEN")).upper(), 0)
        if elapsed < float(cooldown_sec) and cur_rank <= prev_rank:
            return None

    # Prune stale conversation entries older than 24h to keep file compact.
    pruned = {
        k: v
        for k, v in by_conv.items()
        if isinstance(v, dict) and (now - float(v.get("last_ts", 0.0) or 0.0)) < 86400.0
    }
    pruned[key] = {"last_ts": now, "last_level": level}
    try:
        _atomic_write_json(notice_path, {"by_conversation": pruned})
    except OSError:
        pass

    bps_mb = float(status.get("ema_bytes_per_sec", 0.0) or 0.0) / (1024 * 1024)
    iops = float(status.get("ema_iops", 0.0) or 0.0)
    lat_ms = float(status.get("ema_avg_latency_ms", 0.0) or 0.0)
    slots = status.get("active_slots") or {}
    io_cnt = int(slots.get("io_heavy", 0))
    cmp_cnt = int(slots.get("compute_io", 0))
    return (
        f"[{level}] disk={bps_mb:.1f}MB/s iops={iops:.0f} lat={lat_ms:.1f}ms "
        f"slots=io:{io_cnt}/{POOL_CAPS['io_heavy']},cmp:{cmp_cnt}/{POOL_CAPS['compute_io']} "
        "- gate heavy cmds via scripts/host_gate.py"
    )


def resolve_go_cache_dir(go_cache_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Resolve GOCACHE safely via explicit path, env var, or `go env GOCACHE`."""
    if go_cache_dir is not None:
        return Path(go_cache_dir)
    env_val = os.environ.get("GOCACHE", "").strip()
    if env_val and env_val.lower() != "off":
        return Path(env_val)
    go_bin = shutil.which("go")
    if not go_bin:
        return None
    try:
        res = subprocess.run(
            [go_bin, "env", "GOCACHE"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3.0,
            check=False,
        )
        out = (res.stdout or "").strip()
        if res.returncode == 0 and out and out.lower() != "off":
            return Path(out)
    except Exception:
        pass
    return None


def _dir_size_and_count(root: Path) -> tuple[int, int]:
    total_bytes = 0
    file_count = 0
    if not root.exists():
        return 0, 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                total_bytes += fpath.stat().st_size
                file_count += 1
            except OSError:
                continue
    return total_bytes, file_count


def audit_dev_caches(
    go_cache_dir: Optional[Union[str, Path]] = None,
    temp_dir: Optional[Union[str, Path]] = None,
    cache_max_bytes: int = DEFAULT_CACHE_MAX_BYTES,
    pytest_max_age_sec: float = 3600.0,
) -> dict[str, Any]:
    """Audit GOCACHE and leftover antigravity-pytest-* temporary directories."""
    go_path = resolve_go_cache_dir(go_cache_dir)
    go_exists = bool(go_path and go_path.is_dir())
    go_bytes, go_files = _dir_size_and_count(go_path) if go_exists and go_path is not None else (0, 0)

    tdir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    now = time.time()
    pytest_count = 0
    pytest_bytes = 0
    stale_count = 0
    stale_bytes = 0
    stale_paths: list[str] = []

    if tdir.is_dir():
        for entry in sorted(tdir.glob("antigravity-pytest-*")):
            if not entry.is_dir():
                continue
            pytest_count += 1
            sz, _ = _dir_size_and_count(entry)
            pytest_bytes += sz
            try:
                age = now - entry.stat().st_mtime
            except OSError:
                age = 0.0
            if age >= pytest_max_age_sec:
                stale_count += 1
                stale_bytes += sz
                stale_paths.append(str(entry))

    return {
        "go_cache_dir": str(go_path) if go_path else None,
        "go_cache_exists": go_exists,
        "go_cache_bytes": go_bytes,
        "go_cache_files": go_files,
        "go_cache_over_budget": go_bytes > cache_max_bytes,
        "temp_dir": str(tdir),
        "pytest_temp_count": pytest_count,
        "pytest_temp_bytes": pytest_bytes,
        "pytest_stale_count": stale_count,
        "pytest_stale_bytes": stale_bytes,
        "pytest_stale_paths": stale_paths,
    }


def _is_reparse_or_symlink(path: Path) -> bool:
    """Return True if path is a symlink, Windows junction, or reparse point."""
    try:
        if os.path.islink(path):
            return True
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(path):
            return True
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            return True
        if getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
            return True
    except OSError:
        return True
    return False


def _is_inside_git_repo(path: Path) -> bool:
    """Return True if path is a git dir or resides anywhere inside a Git working tree."""
    if ".git" in path.parts:
        return True
    return any((p / ".git").exists() for p in (path, *path.parents))


def prune_dev_cache_lru(
    cache_dir: Union[str, Path],
    max_bytes: int = DEFAULT_CACHE_MAX_BYTES,
    max_age_days: float = DEFAULT_CACHE_MAX_AGE_DAYS,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Trim oldest cache files beyond max_age_days or down to max_bytes (LRU)."""
    cache_path = Path(cache_dir).resolve()
    summary: dict[str, Any] = {
        "cache_dir": str(cache_path),
        "dry_run": dry_run,
        "scanned_files": 0,
        "before_bytes": 0,
        "after_bytes": 0,
        "freed_bytes": 0,
        "deleted_count": 0,
        "deleted_files": [],
        "errors": [],
    }

    if not cache_path.is_dir() or _is_reparse_or_symlink(cache_path):
        return summary
    if cache_path == cache_path.parent or _is_inside_git_repo(cache_path):
        summary["errors"].append("Refusing to prune inside a git repository or filesystem root.")
        return summary

    entries: list[tuple[float, int, Path]] = []
    for dirpath, dirnames, filenames in os.walk(cache_path, followlinks=False):
        dpath = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if d != ".git" and not _is_reparse_or_symlink(dpath / d)
        ]
        for fname in filenames:
            fpath = dpath / fname
            if _is_reparse_or_symlink(fpath):
                continue
            try:
                resolved_file = fpath.resolve()
                if not resolved_file.is_relative_to(cache_path):
                    continue
                st = fpath.lstat()
            except OSError:
                continue
            last_used = max(st.st_atime, st.st_mtime)
            entries.append((last_used, st.st_size, fpath))

    before_bytes = sum(item[1] for item in entries)
    summary["scanned_files"] = len(entries)
    summary["before_bytes"] = before_bytes

    entries.sort(key=lambda item: item[0])  # Oldest first
    now = time.time()
    age_cutoff = (now - float(max_age_days) * 86400.0) if max_age_days is not None and max_age_days >= 0 else None

    to_delete: list[tuple[int, Path]] = []
    survivors: list[tuple[float, int, Path]] = []

    for last_used, size, fpath in entries:
        if age_cutoff is not None and last_used < age_cutoff:
            to_delete.append((size, fpath))
        else:
            survivors.append((last_used, size, fpath))

    remaining_bytes = sum(item[1] for item in survivors)
    idx = 0
    while remaining_bytes > max_bytes and idx < len(survivors):
        _last_used, size, fpath = survivors[idx]
        to_delete.append((size, fpath))
        remaining_bytes -= size
        idx += 1

    freed = 0
    deleted_paths: list[str] = []
    for size, fpath in to_delete:
        if _is_reparse_or_symlink(fpath):
            continue
        try:
            if not fpath.resolve().is_relative_to(cache_path):
                continue
        except OSError:
            continue
        if dry_run:
            freed += size
            deleted_paths.append(str(fpath))
        else:
            try:
                fpath.unlink(missing_ok=True)
                freed += size
                deleted_paths.append(str(fpath))
            except OSError as exc:
                summary["errors"].append(f"{fpath}: {exc}")

    if not dry_run and deleted_paths:
        for dirpath, _dirnames, _filenames in os.walk(cache_path, topdown=False, followlinks=False):
            dpath = Path(dirpath)
            if dpath == cache_path or dpath.name == ".git" or _is_reparse_or_symlink(dpath):
                continue
            try:
                if not any(dpath.iterdir()):
                    dpath.rmdir()
            except OSError:
                pass

    summary["freed_bytes"] = freed
    summary["after_bytes"] = max(0, before_bytes - freed)
    summary["deleted_count"] = len(deleted_paths)
    summary["deleted_files"] = deleted_paths
    return summary


def prune_stale_pytest_temps(
    temp_dir: Optional[Union[str, Path]] = None,
    max_age_sec: float = 3600.0,
    dry_run: bool = False,
    exclude_paths: Optional[Sequence[Union[str, Path]]] = None,
) -> dict[str, Any]:
    """Remove stale antigravity-pytest-* temporary directories safely."""
    tdir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    excluded = {str(Path(p).resolve()) for p in (exclude_paths or [])}
    now = time.time()

    scanned = 0
    stale_count = 0
    removed_count = 0
    freed_bytes = 0
    removed_paths: list[str] = []
    errors: list[str] = []

    if tdir.is_dir():
        for entry in sorted(tdir.glob("antigravity-pytest-*")):
            if not entry.is_dir():
                continue
            scanned += 1
            if str(entry.resolve()) in excluded:
                continue
            try:
                age = now - entry.stat().st_mtime
            except OSError:
                continue
            if age < max_age_sec:
                continue
            stale_count += 1
            sz, _ = _dir_size_and_count(entry)
            if dry_run:
                removed_count += 1
                freed_bytes += sz
                removed_paths.append(str(entry))
            else:
                try:
                    shutil.rmtree(entry, ignore_errors=False)
                    removed_count += 1
                    freed_bytes += sz
                    removed_paths.append(str(entry))
                except OSError as exc:
                    errors.append(f"{entry}: {exc}")

    return {
        "temp_dir": str(tdir),
        "dry_run": dry_run,
        "scanned": scanned,
        "stale_count": stale_count,
        "removed_count": removed_count,
        "freed_bytes": freed_bytes,
        "removed_paths": removed_paths,
        "errors": errors,
    }


def check_storage_advisories(
    workspace_path: Optional[Union[str, Path]] = None,
    *,
    platform_name: Optional[str] = None,
) -> list[dict[str, str]]:
    """Read-only storage advisory check (e.g., Windows NTFS -> Dev Drive / Defender)."""
    if not _is_windows(platform_name) or psutil is None:
        return []

    raw_target = str(workspace_path) if workspace_path is not None else str(Path.cwd())
    if os.name == "nt":
        target = ntpath.normpath(os.path.abspath(raw_target)).lower()
    else:
        target = ntpath.normpath(raw_target).lower()

    best_part = None
    best_len = -1
    try:
        for part in psutil.disk_partitions(all=False):
            mp_raw = str(part.mountpoint or "")
            if not mp_raw:
                continue
            mp = ntpath.normpath(mp_raw).lower()
            matched = (
                target.startswith(mp)
                if mp.endswith("\\")
                else (target == mp or target.startswith(mp + "\\"))
            )
            if matched and len(mp) > best_len:
                best_part = part
                best_len = len(mp)
    except Exception:
        return []

    if best_part is None:
        return []

    fstype = str(best_part.fstype or "").upper()
    if fstype == "NTFS":
        return [
            {
                "code": "ADVISORY_WINDOWS_DEV_DRIVE",
                "filesystem": fstype,
                "mountpoint": str(best_part.mountpoint),
                "message": (
                    f"Workspace resides on {best_part.mountpoint} ({fstype}). Under multi-worktree "
                    "builds/tests, consider a ReFS Dev Drive and Windows Defender folder exclusions "
                    "for workspace & dev caches (GOCACHE, GOMODCACHE, pnpm store)."
                ),
            }
        ]
    return []
