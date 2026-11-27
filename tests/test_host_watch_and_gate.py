"""Tests for Option 1: 3-Layer Host Watch, Host Gate CLI/Shims, and Cache Hygiene."""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from harness import host_watch
from harness.orchestrator import ChiefOrchestrator
from harness.state_machine import HarnessState
from scripts import auto_skill_router_hook, host_gate, run_pytest_windows, safe_task_runner
from scripts.harness_doctor import HarnessDoctor

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_apply_low_io_priority_windows_and_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """apply_low_io_priority sets OS-appropriate IO/CPU priority and never crashes on errors."""
    fake_proc = MagicMock()
    fake_proc.nice.return_value = 0
    fake_psutil = SimpleNamespace(
        Process=MagicMock(return_value=fake_proc),
        IOPRIO_VERYLOW=0,
        BELOW_NORMAL_PRIORITY_CLASS=16384,
        IOPRIO_CLASS_IDLE=3,
        IOPRIO_CLASS_BE=2,
    )
    monkeypatch.setattr(host_watch, "psutil", fake_psutil)

    # Windows branch (via explicit platform_name; never monkeypatch global os.name)
    assert host_watch.apply_low_io_priority(1234, platform_name="nt") is True
    fake_proc.ionice.assert_called_with(0)
    fake_proc.nice.assert_called_with(16384)

    # POSIX branch with fallback from IDLE -> Best-Effort(7)
    fake_proc.reset_mock()
    fake_proc.nice.return_value = 0
    fake_proc.ionice.side_effect = [PermissionError("denied"), None]
    assert host_watch.apply_low_io_priority(5678, platform_name="posix") is True
    assert fake_proc.ionice.call_args_list[0].args == (3,)
    assert fake_proc.ionice.call_args_list[1].args == (2, 7)
    fake_proc.nice.assert_called_with(10)

    # Patching host_watch._is_windows also controls platform branching cleanly
    fake_proc.reset_mock()
    fake_proc.nice.return_value = 0
    monkeypatch.setattr(host_watch, "_is_windows", lambda platform_name=None: True)
    assert host_watch.apply_low_io_priority(2468) is True
    fake_proc.ionice.assert_called_with(0)
    fake_proc.nice.assert_called_with(16384)

    # Guard against AccessDenied / AttributeError
    bad_proc = MagicMock()
    bad_proc.ionice.side_effect = AttributeError("no ionice")
    bad_proc.nice.side_effect = PermissionError("denied")
    fake_psutil.Process.return_value = bad_proc
    assert host_watch.apply_low_io_priority(9999) is False


def test_classify_command_pool_and_typed_slot_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify pool classification, cap=1 / cap=2 limits, fail-fast timeout, and stale PID reclaim."""
    assert host_watch.classify_command_pool("pnpm install") == "io_heavy"
    assert host_watch.classify_command_pool("npm ci") == "io_heavy"
    assert host_watch.classify_command_pool("yarn install") == "io_heavy"
    assert host_watch.classify_command_pool(["git", "-C", "wt", "worktree", "add", "b"]) == "io_heavy"
    assert host_watch.classify_command_pool(["python", "-m", "pip", "install", "pytest"]) == "io_heavy"

    assert host_watch.classify_command_pool("go test ./...") == "compute_io"
    assert host_watch.classify_command_pool("pytest -q") == "compute_io"
    assert host_watch.classify_command_pool("python scripts/run_pytest_windows.py -q") == "compute_io"
    assert host_watch.classify_command_pool("cargo build") == "compute_io"
    assert host_watch.classify_command_pool("tsc --noEmit") == "compute_io"
    assert host_watch.classify_command_pool("npm run build") == "compute_io"
    assert host_watch.classify_command_pool("pnpm run test") == "compute_io"
    assert host_watch.classify_command_pool("git status") is None
    assert host_watch.classify_command_pool("echo hello") is None

    state_dir = tmp_path / "state"

    # io_heavy cap = 1
    with host_watch.acquire_host_slot("io_heavy", state_dir=state_dir, wait_timeout=0.5, cmd="npm install"):
        with pytest.raises(host_watch.HostGateBusyError) as exc_info:
            with host_watch.acquire_host_slot("install", state_dir=state_dir, wait_timeout=0.1, cmd="pnpm add x"):
                pass
        assert exc_info.value.pool == "io_heavy"
        assert exc_info.value.cap == 1

    # Re-acquiring after release succeeds
    with host_watch.acquire_host_slot("worktree", state_dir=state_dir, wait_timeout=0.1) as slot:
        assert slot is not None and slot.pool == "io_heavy"

    # compute_io cap = 2
    with host_watch.acquire_host_slot("build", state_dir=state_dir, wait_timeout=0.5):
        with host_watch.acquire_host_slot("test", state_dir=state_dir, wait_timeout=0.5):
            with pytest.raises(host_watch.HostGateBusyError) as exc2:
                with host_watch.acquire_host_slot("compute_io", state_dir=state_dir, wait_timeout=0.1):
                    pass
            assert exc2.value.pool == "compute_io"
            assert exc2.value.cap == 2

    # Stale-PID lock reclamation
    slots_dir = state_dir / "slots"
    slots_dir.mkdir(parents=True, exist_ok=True)
    stale_lock = slots_dir / "io_heavy_0.lock"
    stale_lock.write_text(json.dumps({"pid": 9999999, "created_at": 1000.0, "cmd": "dead"}), encoding="utf-8")
    monkeypatch.setattr(host_watch.psutil, "pid_exists", lambda pid: pid == os.getpid())

    with host_watch.acquire_host_slot("io_heavy", state_dir=state_dir, wait_timeout=0.1, cmd="reclaimed") as slot:
        assert slot is not None
        data = json.loads(stale_lock.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()
    assert not stale_lock.exists()


def test_atomic_json_and_ema_pressure_transitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify atomic JSON I/O and GREEN -> YELLOW -> RED telemetry EMA transitions."""
    state_dir = tmp_path / "hw"
    target_json = state_dir / "probe.json"
    host_watch._atomic_write_json(target_json, {"ok": True, "n": 1})
    assert host_watch._read_json(target_json) == {"ok": True, "n": 1}

    corrupt = state_dir / "corrupt.json"
    corrupt.write_text("{broken", encoding="utf-8")
    assert host_watch._read_json(corrupt, default={"fallback": 1}) == {"fallback": 1}

    fake_now = [1000.0]
    monkeypatch.setattr(host_watch.time, "time", lambda: fake_now[0])
    monkeypatch.setattr(
        host_watch.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(percent=50.0, available=8 * 1024**3),
    )
    monkeypatch.setattr(
        host_watch.psutil,
        "disk_usage",
        lambda _p: SimpleNamespace(free=100 * 1024**3, total=500 * 1024**3),
    )

    samples = [
        SimpleNamespace(read_count=100, write_count=100, read_bytes=10_000, write_bytes=10_000, read_time=10, write_time=10),
        # +1s: 1000 ops, 30ms avg latency (30_000 ms), 150 MB/s -> YELLOW
        SimpleNamespace(read_count=600, write_count=600, read_bytes=100_010_000, write_bytes=50_010_000, read_time=15_010, write_time=15_010),
        # +1s: 16000 ops, 150ms avg latency -> EMA jumps > 50ms -> RED
        SimpleNamespace(read_count=8600, write_count=8600, read_bytes=400_010_000, write_bytes=200_010_000, read_time=1_215_010, write_time=1_215_010),
    ]
    sample_idx = [0]

    def _fake_counters():
        c = samples[sample_idx[0]]
        return c

    monkeypatch.setattr(host_watch.psutil, "disk_io_counters", _fake_counters)

    s1 = host_watch.sample_host_io(state_dir=state_dir)
    assert s1["level"] == "GREEN"

    fake_now[0] = 1001.0
    sample_idx[0] = 1
    s2 = host_watch.sample_host_io(state_dir=state_dir)
    assert s2["level"] == "YELLOW"
    assert s2["ema_avg_latency_ms"] >= 20.0

    fake_now[0] = 1002.0
    sample_idx[0] = 2
    s3 = host_watch.sample_host_io(state_dir=state_dir)
    assert s3["level"] == "RED"
    assert s3["ema_avg_latency_ms"] >= 50.0


def test_pre_invocation_notice_cooldown_and_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify 5-min cooldown suppression and YELLOW -> RED escalation bypass."""
    state_dir = tmp_path / "notice_state"
    monkeypatch.setenv("ANTIGRAVITY_HOST_WATCH_DIR", str(state_dir))
    now = [2000.0]
    monkeypatch.setattr(host_watch.time, "time", lambda: now[0])

    # GREEN -> no notice
    host_watch._atomic_write_json(state_dir / "host_status.json", {"level": "GREEN", "timestamp": now[0]})
    assert host_watch.get_pre_invocation_host_notice(state_dir=state_dir, conversation_id="conv-1") is None

    # YELLOW -> initial notice fires
    host_watch._atomic_write_json(
        state_dir / "host_status.json",
        {"level": "YELLOW", "timestamp": now[0], "ema_bytes_per_sec": 130 * 1024**2, "ema_iops": 5000, "ema_avg_latency_ms": 25.0},
    )
    msg1 = host_watch.get_pre_invocation_host_notice(state_dir=state_dir, conversation_id="conv-1", cooldown_sec=300.0)
    assert msg1 is not None and "[YELLOW]" in msg1

    # Same YELLOW within 300s -> suppressed
    now[0] = 2100.0
    assert host_watch.get_pre_invocation_host_notice(state_dir=state_dir, conversation_id="conv-1", cooldown_sec=300.0) is None

    # Escalation YELLOW -> RED within 300s -> bypasses cooldown
    host_watch._atomic_write_json(
        state_dir / "host_status.json",
        {"level": "RED", "timestamp": now[0], "ema_bytes_per_sec": 300 * 1024**2, "ema_iops": 16000, "ema_avg_latency_ms": 65.0},
    )
    msg2 = host_watch.get_pre_invocation_host_notice(state_dir=state_dir, conversation_id="conv-1", cooldown_sec=300.0)
    assert msg2 is not None and "[RED]" in msg2

    # Same RED within 300s -> suppressed
    now[0] = 2200.0
    assert host_watch.get_pre_invocation_host_notice(state_dir=state_dir, conversation_id="conv-1", cooldown_sec=300.0) is None

    # Cooldown expired -> fires again via PreInvocation hook
    now[0] = 2505.0
    host_watch._atomic_write_json(
        state_dir / "host_status.json",
        {"level": "RED", "timestamp": now[0], "ema_bytes_per_sec": 300 * 1024**2, "ema_iops": 16000, "ema_avg_latency_ms": 65.0},
    )
    hook_resp = auto_skill_router_hook.evaluate_pre_invocation_payload(
        {"conversationId": "conv-1", "invocationNum": 1, "lastUserInput": "build api"}
    )
    injected = hook_resp["injectSteps"][0]["ephemeralMessage"]
    assert "host_io=[RED]" in injected


def test_recommend_concurrency_and_orchestrator_fanout_throttling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify admission control throttles ChiefOrchestrator.fan_out_tasks under RED pressure."""
    state_dir = tmp_path / "adm"
    monkeypatch.setenv("ANTIGRAVITY_HOST_WATCH_DIR", str(state_dir))

    host_watch._atomic_write_json(state_dir / "host_status.json", {"level": "GREEN", "timestamp": 1e12})
    assert host_watch.recommend_fan_out_concurrency(6, state_dir=state_dir) == 6

    host_watch._atomic_write_json(state_dir / "host_status.json", {"level": "YELLOW", "timestamp": 1e12})
    assert host_watch.recommend_fan_out_concurrency(6, state_dir=state_dir) == 2

    host_watch._atomic_write_json(state_dir / "host_status.json", {"level": "RED", "timestamp": 1e12})
    assert host_watch.recommend_fan_out_concurrency(6, state_dir=state_dir) == 1

    observed_workers: list[int] = []
    real_executor = concurrent.futures.ThreadPoolExecutor

    class _SpyExecutor(real_executor):
        def __init__(self, max_workers=None, *args, **kwargs):
            observed_workers.append(max_workers)
            super().__init__(max_workers=max_workers, *args, **kwargs)

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", _SpyExecutor)
    orch = ChiefOrchestrator()
    results = orch.fan_out_tasks(["Task 1", "Task 2", "Task 3"], branch="app", max_concurrency=4)
    assert len(results) == 3
    assert observed_workers == [1]
    for sub_ctx, verdict in results:
        assert verdict.value == "APPROVE"
        assert sub_ctx.state == HarnessState.APPROVED
        adm_steps = [s for s in sub_ctx.trace_steps if s["step"] == "HOST_ADMISSION"]
        assert len(adm_steps) == 1
        assert adm_steps[0]["payload"]["effective"] == 1
        assert adm_steps[0]["payload"]["level"] == "RED"


def test_host_gate_cli_execution_busy_75_and_shim_anti_recursion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify host_gate.py executes children, returns 75 on busy slots, and generates recursion-safe shims."""
    state_dir = tmp_path / "gate_state"
    gate_script = REPO_ROOT / "scripts" / "host_gate.py"

    # 1. Real child execution through host_gate.py CLI
    proc = subprocess.run(
        [
            sys.executable,
            str(gate_script),
            "--state-dir",
            str(state_dir),
            "--category",
            "compute_io",
            "--",
            sys.executable,
            "-c",
            "print('HOST_GATE_CHILD_OK')",
        ],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert "HOST_GATE_CHILD_OK" in proc.stdout

    # 2. Exit code 75 when io_heavy slot is busy
    with host_watch.acquire_host_slot("io_heavy", state_dir=state_dir, wait_timeout=1.0, cmd="holder"):
        busy_proc = subprocess.run(
            [
                sys.executable,
                str(gate_script),
                "--state-dir",
                str(state_dir),
                "--category",
                "io_heavy",
                "--wait-timeout",
                "0.1",
                "--",
                sys.executable,
                "-c",
                "print('SHOULD_NOT_RUN')",
            ],
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert busy_proc.returncode == 75
        assert "[HOST-GATE-BUSY]" in busy_proc.stderr
        assert "SHOULD_NOT_RUN" not in busy_proc.stdout

    # 3. Shim generation for both Windows and POSIX templates + real execution without recursion
    win_name, win_content = host_gate.generate_shim_script("faketool", platform_name="windows")
    assert win_name == "faketool.cmd"
    assert "ANTIGRAVITY_SHIM_ACTIVE" in win_content
    assert "--shim-exec" in win_content
    assert "--shim-bypass" in win_content

    posix_name, posix_content = host_gate.generate_shim_script("faketool", platform_name="posix")
    assert posix_name == "faketool"
    assert "ANTIGRAVITY_SHIM_ACTIVE" in posix_content
    assert "--shim-exec" in posix_content
    assert 'export PATH="$CLEAN_PATH"' in posix_content

    shim_dir = tmp_path / "shims"
    real_dir = tmp_path / "real_bin"
    shim_dir.mkdir(parents=True)
    real_dir.mkdir(parents=True)

    res_install = host_gate.main(["--install-shims", str(shim_dir), "--shim", "faketool"])
    assert res_install == 0

    if os.name == "nt":
        real_tool = real_dir / "faketool.cmd"
        real_tool.write_text(
            "@echo off\r\n"
            'if "%1"=="inner" (\r\n'
            '  echo INNER_REAL_OK ACTIVE=%ANTIGRAVITY_SHIM_ACTIVE%\r\n'
            "  exit /b 0\r\n"
            ")\r\n"
            'echo OUTER_REAL_OK ACTIVE=%ANTIGRAVITY_SHIM_ACTIVE%\r\n'
            "call faketool inner\r\n",
            encoding="utf-8",
        )
        shim_entry = str(shim_dir / "faketool.cmd")
    else:
        real_tool = real_dir / "faketool"
        real_tool.write_text(
            "#!/usr/bin/env sh\n"
            'if [ "${1:-}" = "inner" ]; then\n'
            '  echo "INNER_REAL_OK ACTIVE=${ANTIGRAVITY_SHIM_ACTIVE:-}"\n'
            "  exit 0\n"
            "fi\n"
            'echo "OUTER_REAL_OK ACTIVE=${ANTIGRAVITY_SHIM_ACTIVE:-}"\n'
            "faketool inner\n",
            encoding="utf-8",
        )
        real_tool.chmod(0o755)
        shim_entry = str(shim_dir / "faketool")

    test_env = os.environ.copy()
    test_env.pop("ANTIGRAVITY_SHIM_ACTIVE", None)
    test_env["ANTIGRAVITY_HOST_WATCH_DIR"] = str(state_dir)
    test_env["PATH"] = os.pathsep.join([str(shim_dir), str(real_dir), test_env.get("PATH", "")])

    shim_run = subprocess.run(
        [shim_entry],
        cwd=REPO_ROOT,
        env=test_env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert shim_run.returncode == 0, shim_run.stderr
    assert "OUTER_REAL_OK ACTIVE=1" in shim_run.stdout
    assert "INNER_REAL_OK ACTIVE=1" in shim_run.stdout


def test_prune_dev_cache_lru_and_git_safety(tmp_path: Path) -> None:
    """Verify prune_dev_cache_lru enforces max_age_days and max_bytes while keeping newest files."""
    # Use OS temp dir so repo-local --basetemp=.pytest_temp_run does not trigger ancestor .git safety guard.
    with tempfile.TemporaryDirectory(prefix="ag_cache_lru_") as td:
        cache_dir = Path(td) / "go_cache"
        cache_dir.mkdir(parents=True)
        now = host_watch.time.time()

        expired = cache_dir / "a_expired.bin"
        older = cache_dir / "b_older.bin"
        newer = cache_dir / "c_newer.bin"
        newest = cache_dir / "d_newest.bin"

        expired.write_bytes(b"x" * 100)
        older.write_bytes(b"x" * 200)
        newer.write_bytes(b"x" * 200)
        newest.write_bytes(b"x" * 200)

        os.utime(expired, (now - 10 * 86400, now - 10 * 86400))
        os.utime(older, (now - 2 * 86400, now - 2 * 86400))
        os.utime(newer, (now - 3600, now - 3600))
        os.utime(newest, (now - 10, now - 10))

        # Dry run preserves all files
        dry = host_watch.prune_dev_cache_lru(cache_dir, max_bytes=450, max_age_days=7, dry_run=True)
        assert dry["deleted_count"] == 2
        assert dry["freed_bytes"] == 300
        assert dry["after_bytes"] == 400
        assert expired.exists() and older.exists() and newer.exists() and newest.exists()

        # Real run deletes expired + older, keeps newer + newest
        real = host_watch.prune_dev_cache_lru(cache_dir, max_bytes=450, max_age_days=7, dry_run=False)
        assert real["deleted_count"] == 2
        assert not expired.exists()
        assert not older.exists()
        assert newer.exists()
        assert newest.exists()

    # Safety guard: refuses .git repository
    git_dir = tmp_path / "repo"
    (git_dir / ".git").mkdir(parents=True)
    (git_dir / "source.py").write_text("print(1)\n", encoding="utf-8")
    guarded = host_watch.prune_dev_cache_lru(git_dir, max_bytes=0, max_age_days=0, dry_run=False)
    assert guarded["deleted_count"] == 0
    assert guarded["errors"]
    assert (git_dir / "source.py").exists()


def test_pytest_temp_cleanup_and_doctor_pillar5_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_pytest_windows cleanup, stale pytest pruning, storage advisory, and Doctor Pillar 5."""
    # 1. Cross-platform stale pytest temp cleanup
    tdir = tmp_path / "temp_root"
    tdir.mkdir()
    stale_dir = tdir / "antigravity-pytest-stale1"
    fresh_dir = tdir / "antigravity-pytest-fresh1"
    stale_dir.mkdir()
    fresh_dir.mkdir()
    (stale_dir / "junk.txt").write_text("old", encoding="utf-8")
    (fresh_dir / "keep.txt").write_text("new", encoding="utf-8")
    now = host_watch.time.time()
    os.utime(stale_dir, (now - 7200, now - 7200))
    os.utime(fresh_dir, (now - 10, now - 10))

    prune_res = host_watch.prune_stale_pytest_temps(temp_dir=tdir, max_age_sec=3600.0, dry_run=False)
    assert prune_res["removed_count"] == 1
    assert not stale_dir.exists()
    assert fresh_dir.exists()

    # 2. run_pytest_windows.py auto-basetemp cleanup in try...finally
    if os.name == "nt":
        win_temp = tmp_path / "win_tmp"
        win_temp.mkdir()
        monkeypatch.setenv("TEMP", str(win_temp))
        monkeypatch.setenv("ANTIGRAVITY_NO_LOW_IO", "1")
        captured_basetemp: list[Path] = []

        def _fake_pytest_main(args):
            idx = args.index("--basetemp")
            bdir = Path(args[idx + 1])
            bdir.mkdir(parents=True, exist_ok=True)
            (bdir / "marker.txt").write_text("created", encoding="utf-8")
            captured_basetemp.append(bdir)
            return 0

        fake_pytest = types.ModuleType("pytest")
        fake_pytest.main = _fake_pytest_main  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pytest", fake_pytest)
        monkeypatch.setattr(sys, "argv", ["run_pytest_windows.py", "-q"])
        rc = run_pytest_windows.main()
        assert rc == 0
        assert len(captured_basetemp) == 1
        assert not captured_basetemp[0].exists()

    # 3. Storage advisory check (read-only, cross-platform via platform_name="nt" and raw string)
    monkeypatch.setattr(
        host_watch.psutil,
        "disk_partitions",
        lambda all=False: [SimpleNamespace(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed")],
    )
    advs = host_watch.check_storage_advisories("C:/workspace/project", platform_name="nt")
    assert len(advs) == 1
    assert advs[0]["code"] == "ADVISORY_WINDOWS_DEV_DRIVE"

    # 4. HarnessDoctor Pillar 5: WARN_HOST_DISK_IO + WARN_DEV_CACHE_BLOAT + auto-fix pytest only
    monkeypatch.setattr(
        host_watch,
        "read_host_status",
        lambda state_dir=None: {"level": "RED", "ema_bytes_per_sec": 300 * 1024**2, "ema_avg_latency_ms": 75.0},
    )
    monkeypatch.setattr(
        host_watch,
        "audit_dev_caches",
        lambda **kwargs: {
            "pytest_stale_count": 25,
            "pytest_temp_bytes": 10 * 1024**2,
            "go_cache_over_budget": True,
            "go_cache_bytes": 35 * 1024**3,
        },
    )
    prune_called: list[dict] = []
    monkeypatch.setattr(
        host_watch,
        "prune_stale_pytest_temps",
        lambda **kwargs: (prune_called.append(kwargs) or {"removed_count": 25}),
    )

    doc_root = tmp_path / "repo_doc"
    doc_root.mkdir()
    doctor = HarnessDoctor(repo_root=doc_root, auto_fix=False)
    issues = doctor.check_pillar_5_hygiene()
    assert any(i.code == "WARN_HOST_DISK_IO" for i in issues)
    bloat_issues = [i for i in issues if i.code == "WARN_DEV_CACHE_BLOAT"]
    assert len(bloat_issues) == 2
    assert any(i.auto_fixable is True and "antigravity-pytest" in i.message for i in bloat_issues)
    assert any(i.auto_fixable is False and "GOCACHE" in i.message for i in bloat_issues)

    fixed = doctor.apply_fixes(issues)
    assert fixed == 1
    assert len(prune_called) == 1
    assert next(i for i in bloat_issues if i.auto_fixable).fixed is True
    assert next(i for i in bloat_issues if not i.auto_fixable).fixed is False


def test_safe_task_runner_low_io_and_host_gate_busy(tmp_path: Path) -> None:
    """Verify safe_task_runner backward compatibility and --host-gate busy behavior."""
    state_dir = tmp_path / "runner_state"
    os.environ["ANTIGRAVITY_HOST_WATCH_DIR"] = str(state_dir)
    try:
        res_ok = safe_task_runner.run_command_with_timeout(
            [sys.executable, "-c", "print('SAFE_OK')"],
            timeout_sec=5.0,
            low_io_priority=True,
            gate_category="compute_io",
            wait_timeout_sec=1.0,
        )
        assert res_ok["status"] == "SUCCESS"
        assert res_ok["exit_code"] == 0
        assert "SAFE_OK" in res_ok["stdout"]

        with host_watch.acquire_host_slot("io_heavy", state_dir=state_dir, wait_timeout=1.0):
            res_busy = safe_task_runner.run_command_with_timeout(
                [sys.executable, "-c", "print('NO')"],
                timeout_sec=5.0,
                gate_category="io_heavy",
                wait_timeout_sec=0.1,
            )
            assert res_busy["status"] == "BUSY"
            assert res_busy["exit_code"] == 75
            assert "[HOST-GATE-BUSY]" in res_busy["stderr"]
    finally:
        os.environ.pop("ANTIGRAVITY_HOST_WATCH_DIR", None)


def test_host_watch_skill_routing_and_refresh_if_stale(tmp_path: Path) -> None:
    """Verify host-watch skill routes cleanly and refresh_if_stale respects max_age_sec."""
    from harness.skills.router import SkillLoader, SkillRouter

    router = SkillRouter()
    skill, branch = router.route("máy bị nghẽn disk và quá tải ổ cứng, bật host gate")
    assert (skill, branch) == ("host-watch", "app")

    loader = SkillLoader()
    instructions = loader.load_instructions("host-watch")
    assert instructions is not None and "name: host-watch" in instructions

    state_dir = tmp_path / "refresh"
    s_fresh = host_watch.refresh_if_stale(state_dir=state_dir, max_age_sec=10.0)
    assert s_fresh["level"] == "GREEN"
    ts1 = s_fresh["timestamp"]
    s_cached = host_watch.refresh_if_stale(state_dir=state_dir, max_age_sec=60.0)
    assert s_cached["timestamp"] == ts1


def test_classify_command_pool_value_taking_flags() -> None:
    """Verify classify_command_pool handles value-taking flags before subcommands."""
    assert host_watch.classify_command_pool("pnpm --filter @app test") == "compute_io"
    assert host_watch.classify_command_pool("npm --prefix web install") == "io_heavy"
    assert host_watch.classify_command_pool("python -X utf8 -m pytest") == "compute_io"
    assert host_watch.classify_command_pool("uv run --extra dev pytest") == "compute_io"
    assert host_watch.classify_command_pool(["pnpm", "-F", "@web", "build"]) == "compute_io"
    assert host_watch.classify_command_pool(["uv", "--project", "app", "pip", "install", "ruff"]) == "io_heavy"


def test_concurrent_stale_lock_reclamation_race_preserves_mutual_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two threads racing to reclaim a dead-PID lock must preserve io_heavy cap=1 mutual exclusion."""
    state_dir = tmp_path / "race_state"
    slots_dir = state_dir / "slots"
    slots_dir.mkdir(parents=True, exist_ok=True)
    stale_lock = slots_dir / "io_heavy_0.lock"
    stale_lock.write_text(
        json.dumps({"pid": 9999999, "token": "dead-token", "created_at": 1000.0, "cmd": "dead"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(host_watch.psutil, "pid_exists", lambda pid: pid == os.getpid())

    barrier = threading.Barrier(2)
    guard = threading.Lock()
    loser_done = threading.Event()
    stats = {"active": 0, "max_active": 0, "acquired": 0, "busy": 0}

    def _worker(idx: int) -> None:
        barrier.wait(timeout=5.0)
        try:
            with host_watch.acquire_host_slot(
                "io_heavy", state_dir=state_dir, wait_timeout=0.05, cmd=f"racer-{idx}"
            ):
                with guard:
                    stats["acquired"] += 1
                    stats["active"] += 1
                    stats["max_active"] = max(stats["max_active"], stats["active"])
                loser_done.wait(timeout=1.5)
                with guard:
                    stats["active"] -= 1
        except host_watch.HostGateBusyError:
            with guard:
                stats["busy"] += 1
            loser_done.set()

    t1 = threading.Thread(target=_worker, args=(1,))
    t2 = threading.Thread(target=_worker, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert not t1.is_alive() and not t2.is_alive()
    assert stats["max_active"] == 1
    assert stats["acquired"] == 1
    assert stats["busy"] == 1
    assert not stale_lock.exists()


def test_host_gate_direct_execution_with_shims_on_path_no_deadlock(tmp_path: Path) -> None:
    """Direct host_gate.py --category io_heavy execution must not self-deadlock when shims are on PATH."""
    state_dir = tmp_path / "gate_direct_state"
    shim_dir = tmp_path / "shims"
    real_dir = tmp_path / "real_bin"
    shim_dir.mkdir(parents=True)
    real_dir.mkdir(parents=True)

    host_gate.install_shims(shim_dir, tools=["faketool"])

    if os.name == "nt":
        real_tool = real_dir / "faketool.cmd"
        real_tool.write_text(
            "@echo off\r\n"
            "echo DIRECT_SHIM_OK ARGS=%* ACTIVE=%ANTIGRAVITY_SHIM_ACTIVE% POOLS=%ANTIGRAVITY_HELD_POOLS%\r\n",
            encoding="utf-8",
        )
        shim_entry = str(shim_dir / "faketool.cmd")
    else:
        real_tool = real_dir / "faketool"
        real_tool.write_text(
            "#!/usr/bin/env sh\n"
            'echo "DIRECT_SHIM_OK ARGS=$* ACTIVE=${ANTIGRAVITY_SHIM_ACTIVE:-} POOLS=${ANTIGRAVITY_HELD_POOLS:-}"\n',
            encoding="utf-8",
        )
        real_tool.chmod(0o755)
        shim_entry = str(shim_dir / "faketool")

    test_env = os.environ.copy()
    test_env.pop("ANTIGRAVITY_SHIM_ACTIVE", None)
    test_env.pop("ANTIGRAVITY_HELD_POOLS", None)
    test_env["ANTIGRAVITY_HOST_WATCH_DIR"] = str(state_dir)
    test_env["PATH"] = os.pathsep.join([str(shim_dir), str(real_dir), test_env.get("PATH", "")])

    gate_script = REPO_ROOT / "scripts" / "host_gate.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(gate_script),
            "--state-dir",
            str(state_dir),
            "--category",
            "io_heavy",
            "--wait-timeout",
            "0.5",
            "--",
            shim_entry,
            "arg1",
        ],
        cwd=REPO_ROOT,
        env=test_env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.returncode != 75
    assert "DIRECT_SHIM_OK" in proc.stdout
    assert "ACTIVE=1" in proc.stdout


def test_resolve_real_tool_ignores_cwd_shim_and_cmd_handles_unquoted_parens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """resolve_real_tool ignores cwd==shim_dir, and Windows .cmd shim handles unquoted ')' args."""
    shim_dir = tmp_path / "shims"
    real_dir = tmp_path / "real_bin"
    state_dir = tmp_path / "paren_state"
    shim_dir.mkdir(parents=True)
    real_dir.mkdir(parents=True)

    host_gate.install_shims(shim_dir, tools=["faketool"])

    if os.name == "nt":
        real_tool = real_dir / "faketool.cmd"
        real_tool.write_text("@echo off\r\necho PAREN_OK %*\r\n", encoding="utf-8")
    else:
        real_tool = real_dir / "faketool"
        real_tool.write_text("#!/usr/bin/env sh\necho \"PAREN_OK $*\"\n", encoding="utf-8")
        real_tool.chmod(0o755)

    monkeypatch.chdir(shim_dir)

    # Even with cwd == shim_dir and shim_dir first in env_path, resolve_real_tool picks real_dir
    resolved, clean_path = host_gate.resolve_real_tool(
        "faketool",
        shim_dir,
        env_path=os.pathsep.join([str(shim_dir), str(real_dir)]),
    )
    assert resolved is not None
    assert Path(resolved).resolve() == real_tool.resolve()
    assert str(shim_dir.resolve()) not in [str(Path(p).resolve()) for p in clean_path.split(os.pathsep) if p]

    # With only shim_dir in PATH and cwd == shim_dir, must return None rather than picking .\faketool.cmd
    missing, _ = host_gate.resolve_real_tool("faketool", shim_dir, env_path=str(shim_dir))
    assert missing is None

    # Verify Windows .cmd template uses goto :bypass (no parenthesized if/else wrapping %*)
    _, win_cmd = host_gate.generate_shim_script("faketool", platform_name="windows")
    assert 'if "%ANTIGRAVITY_SHIM_ACTIVE%"=="1" goto :bypass' in win_cmd

    if os.name == "nt":
        test_env = os.environ.copy()
        test_env.pop("ANTIGRAVITY_SHIM_ACTIVE", None)
        test_env["ANTIGRAVITY_HOST_WATCH_DIR"] = str(state_dir)
        test_env["PATH"] = os.pathsep.join([str(shim_dir), str(real_dir), test_env.get("PATH", "")])

        proc = subprocess.run(
            [str(shim_dir / "faketool.cmd"), "-k", "not(slow)"],
            cwd=shim_dir,
            env=test_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        assert "PAREN_OK" in proc.stdout
        assert "not(slow)" in proc.stdout


def test_prune_dev_cache_lru_ancestor_git_symlinks_and_nested_empty_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prune_dev_cache_lru refuses <repo>/subdir, skips symlinks/junctions, and prunes empty dirs."""
    # 1. Refuses subdirectory inside an ancestor .git repository
    repo_root = tmp_path / "repo_ancestor"
    (repo_root / ".git").mkdir(parents=True)
    sub_cache = repo_root / "nested" / "cache"
    sub_cache.mkdir(parents=True)
    sub_file = sub_cache / "artifact.bin"
    sub_file.write_bytes(b"keep-me")
    guarded = host_watch.prune_dev_cache_lru(sub_cache, max_bytes=0, max_age_days=0, dry_run=False)
    assert guarded["deleted_count"] == 0
    assert guarded["errors"]
    assert sub_file.exists()

    # 2. Skips symlinks/junctions and removes nested emptied directories
    # Use OS temp dir so repo-local --basetemp=.pytest_temp_run does not trigger ancestor .git safety guard.
    with tempfile.TemporaryDirectory(prefix="ag_cache_sym_") as td:
        sym_root = Path(td)
        cache_dir = sym_root / "cache_root"
        nested_dir = cache_dir / "lvl1" / "lvl2" / "lvl3"
        nested_dir.mkdir(parents=True)
        old_file = nested_dir / "expired.bin"
        old_file.write_bytes(b"x" * 64)
        now = host_watch.time.time()
        os.utime(old_file, (now - 10 * 86400, now - 10 * 86400))

        outside_dir = sym_root / "outside_target"
        outside_dir.mkdir()
        outside_file = outside_dir / "must_survive.bin"
        outside_file.write_bytes(b"safe")

        link_dir = cache_dir / "link_dir"
        created_link = False
        try:
            os.symlink(outside_dir, link_dir, target_is_directory=True)
            created_link = True
        except OSError:
            if os.name == "nt":
                mk = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link_dir), str(outside_dir)],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                )
                created_link = mk.returncode == 0

        if not created_link:
            # Unprivileged fallback: verify symlink/reparse skip via explicit sentinel directory
            fake_link = cache_dir / "reparse_dir"
            fake_link.mkdir()
            (fake_link / "protected.bin").write_bytes(b"keep")
            orig_reparse = host_watch._is_reparse_or_symlink
            monkeypatch.setattr(
                host_watch,
                "_is_reparse_or_symlink",
                lambda p: True if Path(p) == fake_link else orig_reparse(p),
            )

        res = host_watch.prune_dev_cache_lru(cache_dir, max_bytes=0, max_age_days=0, dry_run=False)
        assert res["deleted_count"] == 1
        assert not old_file.exists()
        assert not (cache_dir / "lvl1").exists()
        assert cache_dir.exists()
        assert outside_file.exists()
        if not created_link:
            assert (cache_dir / "reparse_dir" / "protected.bin").exists()
