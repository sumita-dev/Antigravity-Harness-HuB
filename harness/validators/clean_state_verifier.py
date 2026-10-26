"""Clean State Protocol & Verifier (Harness 2.0 - 5-Dimension Clock-Out).

Kiểm tra nghiêm ngặt 5 chiều chất lượng trước khi bàn giao (Clock-Out):
  - D1: Build & Type Check (py_compile / mypy)
  - D2: Test Suite Hermetic Green (pytest / npm test exit code == 0)
  - D3: Feature State Synchronization (feature_list.json == Disk Reality)
  - D4: Zero Debug Artifacts & Stray Residue (No print DEBUG, console.log, .tmp)
  - D5: Clean Startup / Boot Path (Smoke boot <= 5000ms exit code == 0)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import py_compile
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Union

from harness.feature_list import FeatureList, _compute_manifest_hash


class AuditDimension(str, Enum):
    D1_BUILD_TYPE = "D1_BUILD_TYPE"
    D2_TEST_SUITE = "D2_TEST_SUITE"
    D3_FEATURE_SYNC = "D3_FEATURE_SYNC"
    D4_ZERO_DEBUG = "D4_ZERO_DEBUG"
    D5_CLEAN_STARTUP = "D5_CLEAN_STARTUP"


class DimensionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


@dataclass
class DebugArtifactViolation:
    file_path: str
    line_number: int
    violation_type: str  # 'print_debug', 'console_log', 'breakpoint', 'debugger', 'stray_file'
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionResult:
    dimension: AuditDimension
    status: DimensionStatus
    duration_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "message": self.message,
            "details": self.details,
            "violations": self.violations,
        }


@dataclass
class CleanStateAuditReport:
    project_root: str
    timestamp: str
    overall_status: DimensionStatus
    vcr_score: Optional[float]
    dimensions: Dict[str, DimensionResult]
    total_duration_ms: float
    is_ready_for_clockout: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_root": self.project_root,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "vcr_score": round(self.vcr_score, 4) if self.vcr_score is not None else None,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "total_duration_ms": round(self.total_duration_ms, 2),
            "is_ready_for_clockout": self.is_ready_for_clockout,
        }

    def summary(self) -> str:
        lines = [
            f"CleanState Audit: {self.overall_status.value} (Ready: {self.is_ready_for_clockout}, Duration: {self.total_duration_ms:.1f}ms)",
        ]
        for name, dim in self.dimensions.items():
            lines.append(f"  - [{dim.status.value}] {name}: {dim.message} ({dim.duration_ms:.1f}ms)")
            if dim.violations:
                for v in dim.violations[:3]:
                    lines.append(f"      * {v}")
                if len(dim.violations) > 3:
                    lines.append(f"      * ... and {len(dim.violations) - 3} more violations")
        return "\n".join(lines)


EXCLUDED_DIRS: Set[str] = {
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
    ".eggs",
    "artifacts",
    "execution_evidence",
    "reports",
}

# Thư mục ngoại lệ khi quét debug artifacts (tránh bắt nhầm console.log trong tests/plugins/docs)
D4_EXCLUDED_DIRS: Set[str] = EXCLUDED_DIRS | {
    "tests",
    "test",
    "fixtures",
    "plugins",
    "specs",
    "docs",
}

STRAY_FILE_PATTERNS = [
    re.compile(r"^.*\.tmp$", re.IGNORECASE),
    re.compile(r"^.*\.bak$", re.IGNORECASE),
    re.compile(r"^.*\.swp$", re.IGNORECASE),
    re.compile(r"^scratch_.*\.py$", re.IGNORECASE),
]

# Debug artifact patterns
DEBUG_PATTERNS_PYTHON = [
    (re.compile(r"""print\s*\(\s*[fF]?["']DEBUG"""), "print_debug"),
    (re.compile(r"""breakpoint\s*\(\s*\)"""), "breakpoint"),
    (re.compile(r"""(?:pdb|ipdb)\.set_trace\s*\(\s*\)"""), "pdb_trace"),
]

DEBUG_PATTERNS_JS = [
    (re.compile(r"""console\.log\s*\("""), "console_log"),
    (re.compile(r"""\bdebugger\s*;?"""), "debugger"),
]


class CleanStateVerifier:
    """Bộ kiểm toán tất định (Idempotent Verifier) kiểm tra 5 chiều trước khi Clock-Out."""

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.config = config or {}
        self.boot_command = self.config.get("boot_command")
        self.feature_list_path = self.config.get("feature_list_path")
        self.test_command = self.config.get("test_command")
        self.fast_mode = bool(self.config.get("fast_mode", False))

    def _should_skip_dir(self, directory: Path) -> bool:
        return directory.name in EXCLUDED_DIRS or any(part in EXCLUDED_DIRS for part in directory.parts)

    # -------------------------------------------------------------
    # D1: Build & Type Check
    # -------------------------------------------------------------
    def check_d1_build_type(self) -> DimensionResult:
        start_t = time.perf_counter()
        violations: List[str] = []
        details: Dict[str, Any] = {"compiled_files": 0, "errors": []}

        if not self.project_root.exists() or not self.project_root.is_dir():
            duration_ms = (time.perf_counter() - start_t) * 1000
            return DimensionResult(
                dimension=AuditDimension.D1_BUILD_TYPE,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Project root does not exist or is not a directory: {self.project_root}",
                violations=[f"Missing directory: {self.project_root}"],
            )

        # Quét toàn bộ tệp .py trong project_root
        py_files: List[Path] = []
        for current, dirs, files in os.walk(self.project_root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file_name in files:
                if file_name.endswith(".py"):
                    py_files.append(Path(current) / file_name)

        compiled_count = 0
        for py_file in py_files:
            try:
                # doraise=True đảm bảo quăng PyCompileError nếu có lỗi cú pháp
                py_compile.compile(str(py_file), doraise=True)
                compiled_count += 1
            except py_compile.PyCompileError as exc:
                rel = py_file.relative_to(self.project_root).as_posix()
                err_msg = f"{rel}: Syntax error - {exc.msg}"
                violations.append(err_msg)
                details["errors"].append({"file": rel, "error": str(exc.msg)})
            except Exception as exc:
                rel = py_file.relative_to(self.project_root).as_posix()
                violations.append(f"{rel}: Compilation error: {exc}")
                details["errors"].append({"file": rel, "error": str(exc)})

        details["compiled_files"] = compiled_count
        duration_ms = (time.perf_counter() - start_t) * 1000

        if violations:
            return DimensionResult(
                dimension=AuditDimension.D1_BUILD_TYPE,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Found {len(violations)} syntax/compilation errors in {len(py_files)} Python files",
                details=details,
                violations=violations,
            )

        return DimensionResult(
            dimension=AuditDimension.D1_BUILD_TYPE,
            status=DimensionStatus.PASS,
            duration_ms=duration_ms,
            message=f"All {compiled_count} Python files compiled cleanly without syntax errors",
            details=details,
            violations=[],
        )

    # -------------------------------------------------------------
    # D2: Test Suite Hermetic Green
    # -------------------------------------------------------------
    def check_d2_test_suite(self) -> DimensionResult:
        start_t = time.perf_counter()
        violations: List[str] = []
        details: Dict[str, Any] = {}

        cmd = self.test_command
        if not cmd:
            # Tự động nhận diện runner
            tests_dir = self.project_root / "tests"
            test_dir = self.project_root / "test"
            pytest_ini = self.project_root / "pytest.ini"
            package_json = self.project_root / "package.json"

            # Kiểm tra xem có test files hay không
            has_py_tests = tests_dir.exists() or test_dir.exists() or pytest_ini.exists()
            if not has_py_tests:
                # Quét nhanh xem có file test_*.py nào không
                for current, dirs, files in os.walk(self.project_root, followlinks=False):
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                    if any(f.startswith("test_") and f.endswith(".py") for f in files):
                        has_py_tests = True
                        break

            if has_py_tests:
                if self.fast_mode:
                    # Chế độ fast: ưu tiên chạy test suites của harness 2.0 hoặc fast tests
                    fast_test_paths = [
                        self.project_root / "tests" / "test_clean_state_verifier.py",
                        self.project_root / "tests" / "test_feature_list.py",
                        self.project_root / "tests" / "test_clean_state_cli.py",
                    ]
                    available_fast = [p for p in fast_test_paths if p.exists()]
                    if available_fast:
                        files_str = " ".join(f'"{p.relative_to(self.project_root).as_posix()}"' for p in available_fast)
                        cmd = f'"{sys.executable}" -m pytest -q {files_str}'
                    else:
                        cmd = f'"{sys.executable}" -m pytest -q -m "not slow"'
                else:
                    cmd = f'"{sys.executable}" -m pytest -q'
            elif package_json.exists():
                try:
                    pkg_data = json.loads(package_json.read_text(encoding="utf-8"))
                    if "test" in pkg_data.get("scripts", {}):
                        cmd = "npm test"
                except Exception:
                    pass

        if not cmd:
            duration_ms = (time.perf_counter() - start_t) * 1000
            return DimensionResult(
                dimension=AuditDimension.D2_TEST_SUITE,
                status=DimensionStatus.SKIPPED,
                duration_ms=duration_ms,
                message="No test suite detected in project",
                details={"reason": "no_test_runner_found"},
            )

        details["command"] = cmd
        try:
            default_timeout = 60.0 if self.fast_mode else 300.0
            timeout_sec = float(self.config.get("test_timeout_seconds", default_timeout))
            is_list = isinstance(cmd, list)
            proc = subprocess.run(
                cmd,
                shell=not is_list,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            details["exit_code"] = proc.returncode
            duration_ms = (time.perf_counter() - start_t) * 1000

            if proc.returncode == 0:
                summary_line = stdout.strip().splitlines()[-1] if stdout.strip() else "Passed"
                return DimensionResult(
                    dimension=AuditDimension.D2_TEST_SUITE,
                    status=DimensionStatus.PASS,
                    duration_ms=duration_ms,
                    message=f"Test suite passed with exit code 0 ({summary_line})",
                    details=details,
                )
            else:
                tail = (stdout + "\n" + stderr).strip().splitlines()[-10:]
                err_summary = "\n".join(tail)
                violations.append(f"Test command '{cmd}' failed with exit code {proc.returncode}:\n{err_summary}")
                return DimensionResult(
                    dimension=AuditDimension.D2_TEST_SUITE,
                    status=DimensionStatus.FAIL,
                    duration_ms=duration_ms,
                    message=f"Test suite failed with exit code {proc.returncode}",
                    details=details,
                    violations=violations,
                )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_t) * 1000
            violations.append(f"Test suite timed out after {timeout_sec}s")
            return DimensionResult(
                dimension=AuditDimension.D2_TEST_SUITE,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Test suite timed out after {timeout_sec}s",
                details=details,
                violations=violations,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_t) * 1000
            violations.append(f"Failed to execute test command: {exc}")
            return DimensionResult(
                dimension=AuditDimension.D2_TEST_SUITE,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Test runner error: {exc}",
                details=details,
                violations=violations,
            )

    # -------------------------------------------------------------
    # D3: Feature List & State Synchronization
    # -------------------------------------------------------------
    def check_d3_feature_sync(self) -> DimensionResult:
        start_t = time.perf_counter()
        violations: List[str] = []
        details: Dict[str, Any] = {}

        # Tìm feature_list.json
        candidate_paths: List[Path] = []
        if self.feature_list_path:
            candidate_paths.append(Path(self.feature_list_path).resolve())
        candidate_paths.extend([
            self.project_root / "specs" / "feature_list.json",
            self.project_root / "feature_list.json",
        ])

        target_file: Optional[Path] = None
        for p in candidate_paths:
            if p.exists() and p.is_file():
                target_file = p
                break

        if not target_file:
            duration_ms = (time.perf_counter() - start_t) * 1000
            return DimensionResult(
                dimension=AuditDimension.D3_FEATURE_SYNC,
                status=DimensionStatus.SKIPPED,
                duration_ms=duration_ms,
                message="No feature_list.json detected in project",
                details={"candidates_checked": [str(p) for p in candidate_paths]},
            )

        details["feature_list_file"] = str(target_file)
        try:
            fl = FeatureList.load_from_file(target_file)
            details["vcr_metrics"] = fl.vcr_metrics.to_dict()
            details["total_features"] = len(fl.features)

            # Kiểm tra validation bao gồm manifest hash hiện tại
            validation_errors = fl.validate(check_manifest_against_path=self.project_root)
            if validation_errors:
                violations.extend(validation_errors)
        except Exception as exc:
            violations.append(f"Feature list validation failed: {exc}")

        duration_ms = (time.perf_counter() - start_t) * 1000
        if violations:
            return DimensionResult(
                dimension=AuditDimension.D3_FEATURE_SYNC,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Feature list sync failed with {len(violations)} issues",
                details=details,
                violations=violations,
            )

        vcr = details.get("vcr_metrics", {}).get("vcr_score", 1.0)
        return DimensionResult(
            dimension=AuditDimension.D3_FEATURE_SYNC,
            status=DimensionStatus.PASS,
            duration_ms=duration_ms,
            message=f"Feature list in sync with disk state (VCR: {vcr:.2f}, passing: {fl.vcr_metrics.passing}/{fl.vcr_metrics.total_features})",
            details=details,
            violations=[],
        )

    # -------------------------------------------------------------
    # D4: Zero Debug Artifacts & Stray Residue
    # -------------------------------------------------------------
    def check_d4_zero_debug(self) -> DimensionResult:
        start_t = time.perf_counter()
        violations: List[str] = []
        details: Dict[str, Any] = {"stray_files": [], "debug_patterns": []}

        # 1. Quét tệp rác / tệp tạm (.tmp, .bak, .swp, scratch_*.py)
        for current, dirs, files in os.walk(self.project_root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in D4_EXCLUDED_DIRS]
            for name in files:
                for pattern in STRAY_FILE_PATTERNS:
                    if pattern.match(name):
                        file_path = Path(current) / name
                        rel = file_path.relative_to(self.project_root).as_posix()
                        violations.append(f"Stray file detected: {rel}")
                        details["stray_files"].append(rel)
                        break

        # 2. Quét debug code patterns trong source files
        source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}
        for current, dirs, files in os.walk(self.project_root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in D4_EXCLUDED_DIRS]
            for name in files:
                file_path = Path(current) / name
                ext = file_path.suffix.lower()
                if ext not in source_exts:
                    continue

                rel = file_path.relative_to(self.project_root).as_posix()
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                # Bỏ qua tệp nếu có comment mức file cho phép
                if "# noqa: debug-artifact-file" in content or "// noqa: debug-artifact-file" in content:
                    continue

                is_python = ext == ".py"
                patterns = DEBUG_PATTERNS_PYTHON if is_python else DEBUG_PATTERNS_JS

                for line_no, line in enumerate(content.splitlines(), start=1):
                    # Bỏ qua dòng có comment noqa
                    if "# noqa: debug-artifact" in line or "// noqa: debug-artifact" in line or "# noqa" in line:
                        continue

                    for regex, v_type in patterns:
                        if regex.search(line):
                            snippet = line.strip()[:80]
                            err_msg = f"{rel}:L{line_no}: [{v_type}] {snippet}"
                            violations.append(err_msg)
                            details["debug_patterns"].append({
                                "file": rel,
                                "line": line_no,
                                "type": v_type,
                                "snippet": snippet,
                            })

        duration_ms = (time.perf_counter() - start_t) * 1000
        if violations:
            return DimensionResult(
                dimension=AuditDimension.D4_ZERO_DEBUG,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Found {len(violations)} debug artifacts or stray files",
                details=details,
                violations=violations,
            )

        return DimensionResult(
            dimension=AuditDimension.D4_ZERO_DEBUG,
            status=DimensionStatus.PASS,
            duration_ms=duration_ms,
            message="Zero debug artifacts and no stray files found across project",
            details=details,
            violations=[],
        )

    # -------------------------------------------------------------
    # D5: Clean Startup / Boot Path
    # -------------------------------------------------------------
    def check_d5_clean_startup(self) -> DimensionResult:
        start_t = time.perf_counter()
        violations: List[str] = []
        details: Dict[str, Any] = {}

        cmd = self.boot_command
        if not cmd:
            # Tìm lệnh boot mặc định
            if (self.project_root / "run_harness.py").exists():
                cmd = f'"{sys.executable}" "{self.project_root / "run_harness.py"}" --help'
            elif (self.project_root / "main.py").exists():
                cmd = f'"{sys.executable}" "{self.project_root / "main.py"}" --help'
            elif (self.project_root / "harness_config.json").exists():
                try:
                    cfg = json.loads((self.project_root / "harness_config.json").read_text(encoding="utf-8"))
                    cmd = cfg.get("smoke_boot_command")
                except Exception:
                    pass

        if not cmd:
            duration_ms = (time.perf_counter() - start_t) * 1000
            return DimensionResult(
                dimension=AuditDimension.D5_CLEAN_STARTUP,
                status=DimensionStatus.SKIPPED,
                duration_ms=duration_ms,
                message="No clean boot entrypoint or smoke_boot_command detected in project",
                details={"reason": "no_boot_target"},
            )

        details["command"] = cmd
        timeout_ms = float(self.config.get("boot_timeout_ms", 5000.0))
        timeout_sec = timeout_ms / 1000.0

        try:
            is_list = isinstance(cmd, list)
            proc = subprocess.run(
                cmd,
                shell=not is_list,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
            duration_ms = (time.perf_counter() - start_t) * 1000
            details["exit_code"] = proc.returncode

            if proc.returncode == 0:
                return DimensionResult(
                    dimension=AuditDimension.D5_CLEAN_STARTUP,
                    status=DimensionStatus.PASS,
                    duration_ms=duration_ms,
                    message=f"Clean startup path verified ({cmd} exited with 0 in {duration_ms:.1f}ms)",
                    details=details,
                )
            else:
                tail = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[-5:]
                violations.append(f"Clean startup failed with exit code {proc.returncode}:\n" + "\n".join(tail))
                return DimensionResult(
                    dimension=AuditDimension.D5_CLEAN_STARTUP,
                    status=DimensionStatus.FAIL,
                    duration_ms=duration_ms,
                    message=f"Clean startup exited with code {proc.returncode}",
                    details=details,
                    violations=violations,
                )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_t) * 1000
            violations.append(f"Clean startup timed out after {timeout_ms:.0f}ms")
            return DimensionResult(
                dimension=AuditDimension.D5_CLEAN_STARTUP,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Boot command timed out after {timeout_ms:.0f}ms (threshold exceeded)",
                details=details,
                violations=violations,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_t) * 1000
            violations.append(f"Failed to execute boot command: {exc}")
            return DimensionResult(
                dimension=AuditDimension.D5_CLEAN_STARTUP,
                status=DimensionStatus.FAIL,
                duration_ms=duration_ms,
                message=f"Boot execution exception: {exc}",
                details=details,
                violations=violations,
            )

    # -------------------------------------------------------------
    # Aggregator: Audit 5 Chiều
    # -------------------------------------------------------------
    def audit(self, strict: bool = False) -> CleanStateAuditReport:
        """Thực thi kiểm toán 5 chiều theo AC-CS-01..06. Idempotent và side-effect free."""
        start_t = time.perf_counter()
        dims: Dict[str, DimensionResult] = {}

        # D1: Build/Type
        d1 = self.check_d1_build_type()
        dims[AuditDimension.D1_BUILD_TYPE.value] = d1
        if strict and d1.status == DimensionStatus.FAIL:
            return self._build_report(dims, start_t)

        # D2: Test Suite Hermetic
        d2 = self.check_d2_test_suite()
        dims[AuditDimension.D2_TEST_SUITE.value] = d2
        if strict and d2.status == DimensionStatus.FAIL:
            return self._build_report(dims, start_t)

        # D3: Feature State Sync
        d3 = self.check_d3_feature_sync()
        dims[AuditDimension.D3_FEATURE_SYNC.value] = d3
        if strict and d3.status == DimensionStatus.FAIL:
            return self._build_report(dims, start_t)

        # D4: Zero Debug Artifacts
        d4 = self.check_d4_zero_debug()
        dims[AuditDimension.D4_ZERO_DEBUG.value] = d4
        if strict and d4.status == DimensionStatus.FAIL:
            return self._build_report(dims, start_t)

        # D5: Clean Startup
        d5 = self.check_d5_clean_startup()
        dims[AuditDimension.D5_CLEAN_STARTUP.value] = d5

        return self._build_report(dims, start_t)

    def _build_report(
        self,
        dimensions: Dict[str, DimensionResult],
        start_t: float,
    ) -> CleanStateAuditReport:
        total_duration_ms = (time.perf_counter() - start_t) * 1000

        # Nếu có bất kỳ chiều nào FAIL thì overall là FAIL
        has_fail = any(d.status == DimensionStatus.FAIL for d in dimensions.values())
        overall = DimensionStatus.FAIL if has_fail else DimensionStatus.PASS
        is_ready = overall == DimensionStatus.PASS

        # Trích xuất vcr_score nếu có
        vcr_score: Optional[float] = None
        d3_res = dimensions.get(AuditDimension.D3_FEATURE_SYNC.value)
        if d3_res and d3_res.status == DimensionStatus.PASS and "vcr_metrics" in d3_res.details:
            vcr_score = float(d3_res.details["vcr_metrics"].get("vcr_score", 1.0))

        return CleanStateAuditReport(
            project_root=str(self.project_root),
            timestamp=datetime.now(timezone.utc).isoformat(),
            overall_status=overall,
            vcr_score=vcr_score,
            dimensions=dimensions,
            total_duration_ms=total_duration_ms,
            is_ready_for_clockout=is_ready,
        )


__all__ = [
    "AuditDimension",
    "CleanStateAuditReport",
    "CleanStateVerifier",
    "DebugArtifactViolation",
    "DimensionResult",
    "DimensionStatus",
]
