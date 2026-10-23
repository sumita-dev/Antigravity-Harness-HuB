#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/harness_doctor.py

Hệ thống Bác Sĩ Nội Trú tự chẩn đoán & tự động đề xuất hướng fix
(Harness Doctor & Self-Healing Engine) cho Antigravity Harness Hub.

Vận hành 5 Trụ Cột Tự Chẩn Đoán & Tự Chữa Lành:
1. Rules & Context Budget:
   - Kiểm tra dung lượng GEMINI.md (trần 24KB) và configs/global_gemini.md (trần 8KB).
   - Kiểm tra .agents/skills.json (bắt buộc rỗng {"entries": []} chống double loading).
   - Mã lỗi: ERR_CTX_OVERBUDGET, ERR_DOUBLE_LOADING.
2. Skills & Composition Integrity:
   - Chạy kiểm định lint từ scripts/lint_harness_skills.py.
   - Kiểm tra chu trình phụ thuộc lặp (cyclic dependencies).
   - Kiểm tra trần ngân sách phối hợp kỹ năng (skill_composition trong configs/harness_config.json).
   - Mã lỗi: ERR_SKILL_LINT, ERR_SKILL_CYCLE.
3. Anti-Hallucination & Evidence Watchdog:
   - Tích hợp trực tiếp module harness/validators/hallucination_detector.py.
   - Quét đường dẫn file vật lý (verify_file_paths), từ ngữ võ đoán (detect_speculative_language),
     và chứng thực log thực thi exit code 0 (verify_execution_claims).
   - Mã lỗi: ERR_HALLUCINATION_PATH, ERR_HALLUCINATION_SPECULATION.
4. Workflow Checkpoint & Circuit Breaker State:
   - Quét .brain/app_workflows và .brain/marketing_workflows.
   - Phát hiện task bị bế tắc / reject_counts chạm trần (>= 2) mà chưa ESCALATED.
   - Phát hiện và dọn dẹp các file khóa mồ côi (*.lock).
   - Mã lỗi: ERR_WORKFLOW_STUCK, ERR_ORPHAN_LOCK.
5. Process & Storage Hygiene:
   - Kiểm tra dung lượng thư mục .sessions/ (cảnh báo > 500MB).
   - Quét tiến trình mồ côi (WINWORD.EXE, EXCEL.EXE treo modal, headless test shells).
   - Mã lỗi: WARN_STORAGE_SESSIONS, WARN_ORPHAN_PROCESS.

Cơ chế Tự Sửa Lỗi (--fix):
   - Tự động xóa file .lock mồ côi.
   - Tự động reset .agents/skills.json về {"entries": []}.
   - Tự động dọn dẹp tiến trình COM mồ côi qua safe_com_runner.cleanup_com_processes().
   - Xuất đơn thuốc khuyến nghị chạy các lệnh tương ứng (switch-profile.ps1, cắt tỉa văn bản...).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Thêm repo root vào sys.path nếu cần
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.validators.hallucination_detector import (
    detect_speculative_language,
    verify_execution_claims,
    verify_file_paths,
)

# Giới hạn dung lượng theo quy chuẩn kiến trúc
MAX_GEMINI_BYTES = 24 * 1024       # 24,576 bytes
MAX_GLOBAL_GEMINI_BYTES = 8 * 1024  # 8,192 bytes
MAX_SESSIONS_BYTES = 500 * 1024 * 1024  # 524,288,000 bytes (~500MB)

FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


@dataclass
class DoctorIssue:
    """Đại diện cho một vấn đề được phát hiện bởi Bác Sĩ Nội Trú."""
    code: str
    severity: str  # "ERROR" hoặc "WARN"
    pillar: str
    message: str
    remediation: str
    auto_fixable: bool = False
    fixed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DoctorReport:
    """Báo cáo tổng hợp từ Bác Sĩ Nội Trú."""
    healthy: bool
    issues: List[DoctorIssue] = field(default_factory=list)
    fixed_count: int = 0
    checks_run: int = 0
    repo_root: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "checks_run": self.checks_run,
            "fixed_count": self.fixed_count,
            "issue_count": len(self.issues),
            "errors": sum(1 for i in self.issues if i.severity == "ERROR" and not i.fixed),
            "warnings": sum(1 for i in self.issues if i.severity == "WARN" and not i.fixed),
            "repo_root": self.repo_root,
            "issues": [i.to_dict() for i in self.issues],
        }


class HarnessDoctor:
    """Lớp điều phối Bác Sĩ Nội Trú và Cỗ Máy Tự Sửa Lỗi (Self-Healing Engine)."""

    def __init__(
        self,
        repo_root: Optional[Union[str, Path]] = None,
        auto_fix: bool = False,
        verbose: bool = False,
        target_file: Optional[Union[str, Path]] = None,
    ):
        self.repo_root = Path(repo_root or REPO_ROOT).resolve()
        self.auto_fix = auto_fix
        self.verbose = verbose
        self.target_file = Path(target_file).resolve() if target_file else None

    def get_directory_size(self, path: Path) -> int:
        """Tính tổng dung lượng (bytes) của một thư mục."""
        try:
            return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        except Exception:
            return 0

    def run(self) -> DoctorReport:
        """Thực thi toàn bộ 5 trụ cột chẩn đoán và tự sửa lỗi nếu được bật."""
        issues: List[DoctorIssue] = []
        checks_run = 0

        # Trụ cột 1: Rules & Context Budget
        p1_issues = self.check_pillar_1_rules()
        issues.extend(p1_issues)
        checks_run += 1

        # Trụ cột 2: Skills & Composition Integrity
        p2_issues = self.check_pillar_2_skills()
        issues.extend(p2_issues)
        checks_run += 1

        # Trụ cột 3: Anti-Hallucination & Evidence Watchdog
        p3_issues = self.check_pillar_3_hallucination()
        issues.extend(p3_issues)
        checks_run += 1

        # Trụ cột 4: Workflow Checkpoint & Circuit Breaker State
        p4_issues = self.check_pillar_4_workflows()
        issues.extend(p4_issues)
        checks_run += 1

        # Trụ cột 5: Process & Storage Hygiene
        p5_issues = self.check_pillar_5_hygiene()
        issues.extend(p5_issues)
        checks_run += 1

        fixed_count = 0
        if self.auto_fix:
            fixed_count = self.apply_fixes(issues)

        # Trạng thái healthy nếu không còn lỗi ERROR chưa sửa
        unresolved_errors = [i for i in issues if i.severity == "ERROR" and not i.fixed]
        healthy = len(unresolved_errors) == 0

        return DoctorReport(
            healthy=healthy,
            issues=issues,
            fixed_count=fixed_count,
            checks_run=checks_run,
            repo_root=str(self.repo_root),
        )

    # =========================================================================
    # TRỤ CỘT 1: RULES & CONTEXT BUDGET
    # =========================================================================
    def check_pillar_1_rules(self) -> List[DoctorIssue]:
        """Kiểm tra trần ngân sách context và chống double loading skills."""
        issues: List[DoctorIssue] = []
        pillar = "Pillar 1: Rules & Context Budget"

        # 1.1 Kiểm tra GEMINI.md
        gemini_path = self.repo_root / "GEMINI.md"
        if gemini_path.exists():
            size = gemini_path.stat().st_size
            if size > MAX_GEMINI_BYTES:
                issues.append(
                    DoctorIssue(
                        code="ERR_CTX_OVERBUDGET",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Dung lượng GEMINI.md ({size} bytes) vượt trần ngân sách {MAX_GEMINI_BYTES} bytes (24KB).",
                        remediation="Cắt gọt Always-on context trong GEMINI.md; chuyển bớt chi tiết sang Skills hoặc SubAgents.",
                        auto_fixable=False,
                    )
                )

        # 1.2 Kiểm tra configs/global_gemini.md
        global_gemini_path = self.repo_root / "configs" / "global_gemini.md"
        if global_gemini_path.exists():
            size = global_gemini_path.stat().st_size
            if size > MAX_GLOBAL_GEMINI_BYTES:
                issues.append(
                    DoctorIssue(
                        code="ERR_CTX_OVERBUDGET",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Dung lượng configs/global_gemini.md ({size} bytes) vượt trần {MAX_GLOBAL_GEMINI_BYTES} bytes (8KB).",
                        remediation="Cắt tỉa configs/global_gemini.md về dưới ngưỡng 8KB.",
                        auto_fixable=False,
                    )
                )

        # 1.3 Kiểm tra .agents/skills.json (chống double loading)
        skills_json_path = self.repo_root / ".agents" / "skills.json"
        if skills_json_path.exists():
            try:
                content = skills_json_path.read_text(encoding="utf-8")
                data = json.loads(content)
                entries = data.get("entries") if isinstance(data, dict) else None
                if entries != []:
                    issues.append(
                        DoctorIssue(
                            code="ERR_DOUBLE_LOADING",
                            severity="ERROR",
                            pillar=pillar,
                            message=".agents/skills.json không rỗng, gây nguy cơ double loading kỹ năng khi đã nạp qua plugins.json.",
                            remediation="Reset .agents/skills.json về rỗng: {\"entries\": []}.",
                            auto_fixable=True,
                        )
                    )
            except Exception as exc:
                issues.append(
                    DoctorIssue(
                        code="ERR_DOUBLE_LOADING",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Không thể đọc hoặc parse .agents/skills.json: {exc}",
                        remediation="Khôi phục .agents/skills.json về chuẩn: {\"entries\": []}.",
                        auto_fixable=True,
                    )
                )

        return issues

    # =========================================================================
    # TRỤ CỘT 2: SKILLS & COMPOSITION INTEGRITY
    # =========================================================================
    def check_pillar_2_skills(self) -> List[DoctorIssue]:
        """Kiểm định lint kỹ năng, chu trình phụ thuộc và composition budget."""
        issues: List[DoctorIssue] = []
        pillar = "Pillar 2: Skills & Composition Integrity"

        # 2.1 Chạy lint từ scripts/lint_harness_skills.py
        try:
            from scripts.lint_harness_skills import lint
            lint_errors = lint(self.repo_root)
            for err in lint_errors:
                issues.append(
                    DoctorIssue(
                        code="ERR_SKILL_LINT",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Lỗi kiểm định kỹ năng: {err}",
                        remediation="Sửa lỗi frontmatter, đường dẫn tham chiếu hoặc routing trong configs/harness_config.json.",
                        auto_fixable=False,
                    )
                )
        except Exception as exc:
            issues.append(
                DoctorIssue(
                    code="ERR_SKILL_LINT",
                    severity="ERROR",
                    pillar=pillar,
                    message=f"Không thể chạy lint_harness_skills: {exc}",
                    remediation="Kiểm tra script scripts/lint_harness_skills.py và môi trường Python.",
                    auto_fixable=False,
                )
            )

        # 2.2 Đọc toàn bộ skills và kiểm tra Cyclic Dependencies
        import yaml
        skill_files = sorted((self.repo_root / "plugins").rglob("SKILL.md"))
        skills_deps: Dict[str, List[str]] = {}
        skill_char_sizes: Dict[str, int] = {}

        for sf in skill_files:
            try:
                txt = sf.read_text(encoding="utf-8")
                m = FRONTMATTER_PATTERN.match(txt)
                if not m:
                    continue
                meta = yaml.safe_load(m.group(1)) or {}
                name = meta.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                deps = meta.get("dependencies", [])
                if isinstance(deps, list):
                    skills_deps[name] = [d for d in deps if isinstance(d, str)]
                else:
                    skills_deps[name] = []
                skill_char_sizes[name] = len(txt)
            except Exception:
                continue

        # Phát hiện cycle bằng DFS
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        cycle_detected: Optional[List[str]] = None

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited[node] = 1
            for neighbor in skills_deps.get(node, []):
                if neighbor not in skills_deps:
                    continue
                if visited.get(neighbor) == 1:
                    idx = path.index(neighbor) if neighbor in path else 0
                    return path[idx:] + [neighbor]
                elif visited.get(neighbor) != 2:
                    c = dfs(neighbor, path + [neighbor])
                    if c:
                        return c
            visited[node] = 2
            return None

        for s_name in skills_deps:
            if visited.get(s_name) != 2:
                cycle_detected = dfs(s_name, [s_name])
                if cycle_detected:
                    break

        if cycle_detected:
            cycle_str = " -> ".join(cycle_detected)
            issues.append(
                DoctorIssue(
                    code="ERR_SKILL_CYCLE",
                    severity="ERROR",
                    pillar=pillar,
                    message=f"Phát hiện chu trình phụ thuộc lặp giữa các kỹ năng: {cycle_str}",
                    remediation=f"Cắt đứt phụ thuộc vòng lặp giữa {cycle_str}.",
                    auto_fixable=False,
                )
            )

        # 2.3 Kiểm tra composition budget trong configs/harness_config.json
        config_path = self.repo_root / "configs" / "harness_config.json"
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                comp = cfg.get("skill_composition", {})
                max_skills = comp.get("max_skills", 8)
                max_chars = comp.get("max_chars", 72000)

                for category, groups in comp.items():
                    if not isinstance(groups, dict):
                        continue
                    for group_name, skill_list in groups.items():
                        if not isinstance(skill_list, list):
                            continue
                        if len(skill_list) > max_skills:
                            issues.append(
                                DoctorIssue(
                                    code="ERR_SKILL_LINT",
                                    severity="ERROR",
                                    pillar=pillar,
                                    message=(
                                        f"Nhóm cấu thành kỹ năng '{category}.{group_name}' có {len(skill_list)} skills, "
                                        f"vượt ngưỡng max_skills={max_skills}."
                                    ),
                                    remediation=f"Giảm số lượng kỹ năng nạp đồng thời trong '{category}.{group_name}'.",
                                    auto_fixable=False,
                                )
                            )
                        # Tính tổng số ký tự
                        total_chars = sum(skill_char_sizes.get(sk, 0) for sk in skill_list)
                        if total_chars > max_chars:
                            issues.append(
                                DoctorIssue(
                                    code="ERR_SKILL_LINT",
                                    severity="ERROR",
                                    pillar=pillar,
                                    message=(
                                        f"Tổng dung lượng ký tự nhóm '{category}.{group_name}' là {total_chars} chars, "
                                        f"vượt ngưỡng max_chars={max_chars}."
                                    ),
                                    remediation=f"Cắt tỉa nội dung hoặc giảm bớt skills trong '{category}.{group_name}'.",
                                    auto_fixable=False,
                                )
                            )
            except Exception as exc:
                issues.append(
                    DoctorIssue(
                        code="ERR_SKILL_LINT",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Lỗi đọc skill_composition trong harness_config.json: {exc}",
                        remediation="Đảm bảo configs/harness_config.json có định dạng JSON hợp lệ.",
                        auto_fixable=False,
                    )
                )

        return issues

    # =========================================================================
    # TRỤ CỘT 3: ANTI-HALLUCINATION & EVIDENCE WATCHDOG
    # =========================================================================
    def check_pillar_3_hallucination(self) -> List[DoctorIssue]:
        """Tích hợp module hallucination_detector để quét báo cáo / log thực chứng."""
        issues: List[DoctorIssue] = []
        pillar = "Pillar 3: Anti-Hallucination & Evidence Watchdog"

        files_to_scan: List[Path] = []
        if self.target_file:
            if self.target_file.exists():
                files_to_scan.append(self.target_file)
            else:
                issues.append(
                    DoctorIssue(
                        code="ERR_HALLUCINATION_PATH",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"File mục tiêu được chỉ định không tồn tại: {self.target_file}",
                        remediation="Cung cấp đường dẫn file vật lý có thật.",
                        auto_fixable=False,
                    )
                )
                return issues
        else:
            # Quét các file báo cáo markdown gần nhất trong reports/
            reports_dir = self.repo_root / "reports"
            if reports_dir.exists():
                md_reports = sorted(
                    reports_dir.glob("*.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                files_to_scan.extend(md_reports[:3])

        # Cache các file trong repo để đối soát nhanh
        common_lookup_dirs = [".", "setup", "configs", "plugins", "harness", "scripts"]

        for fpath in files_to_scan:
            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_file = fpath.relative_to(self.repo_root).as_posix() if fpath.is_relative_to(self.repo_root) else fpath.name

            # 3.1 Kiểm tra file paths
            res_paths = verify_file_paths(content, base_dir=self.repo_root)
            missing = res_paths.get("missing_paths", [])
            truly_missing: List[str] = []

            for p_str in missing:
                cleaned = p_str.replace("file:///", "").strip()
                # Kiểm tra tồn tại tương đối với repo_root hoặc file cha
                if (self.repo_root / cleaned).exists() or (fpath.parent / cleaned).exists():
                    continue
                # Kiểm tra trong các thư mục chính
                exists_in_subdirs = any(
                    (self.repo_root / d / cleaned).exists() for d in common_lookup_dirs
                )
                if exists_in_subdirs:
                    continue
                # Kiểm tra rglob trong plugins cho các file SKILL.md/tài liệu tham chiếu
                if cleaned.startswith("references/") or cleaned.endswith(".md"):
                    if any((self.repo_root / "plugins").glob(f"**/{cleaned}")):
                        continue
                truly_missing.append(p_str)

            if truly_missing:
                issues.append(
                    DoctorIssue(
                        code="ERR_HALLUCINATION_PATH",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Phát hiện đường dẫn ảo / không tồn tại trong {rel_file}: {', '.join(truly_missing)}",
                        remediation=f"Đảm bảo mọi đường dẫn trích dẫn trong {rel_file} đều tồn tại trên filesystem.",
                        auto_fixable=False,
                    )
                )

            # 3.2 Kiểm tra từ ngữ võ đoán (Red Flag Phrases)
            spec_violations = detect_speculative_language(content)
            if spec_violations:
                issues.append(
                    DoctorIssue(
                        code="ERR_HALLUCINATION_SPECULATION",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Phát hiện ngôn ngữ võ đoán trong {rel_file}: {', '.join(spec_violations)}",
                        remediation="Loại bỏ các từ ngữ 'should work', 'chắc là'..., thay bằng bằng chứng đo đạc thực nghiệm.",
                        auto_fixable=False,
                    )
                )

            # 3.3 Kiểm tra tuyên bố hoàn thành cần có log exit code 0
            # Khi kiểm tra file báo cáo, bản thân nội dung file được dùng làm execution_logs
            claims_check = verify_execution_claims(content, execution_logs=content)
            unverified = claims_check.get("unverified_claims", [])
            if unverified:
                issues.append(
                    DoctorIssue(
                        code="ERR_HALLUCINATION_SPECULATION",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Tuyên bố thành công nhưng thiếu log thực thi exit code 0 trong {rel_file}: {', '.join(unverified)}",
                        remediation="Bổ sung lệnh chạy thực tế kèm exit code 0 chứng minh kết quả.",
                        auto_fixable=False,
                    )
                )

        return issues

    # =========================================================================
    # TRỤ CỘT 4: WORKFLOW CHECKPOINT & CIRCUIT BREAKER STATE
    # =========================================================================
    def check_pillar_4_workflows(self) -> List[DoctorIssue]:
        """Quét các workflow checkpoint, phát hiện bế tắc và lock mồ côi."""
        issues: List[DoctorIssue] = []
        pillar = "Pillar 4: Workflow Checkpoint & Circuit Breaker State"

        workflow_dirs = [
            self.repo_root / ".brain" / "app_workflows",
            self.repo_root / ".brain" / "marketing_workflows",
        ]

        for wdir in workflow_dirs:
            if not wdir.exists():
                continue

            # 4.1 Quét các file .lock
            for lock_file in wdir.glob("*.lock"):
                issues.append(
                    DoctorIssue(
                        code="ERR_ORPHAN_LOCK",
                        severity="ERROR",
                        pillar=pillar,
                        message=f"Phát hiện file khóa mồ côi: {lock_file.relative_to(self.repo_root).as_posix()}",
                        remediation=f"Xóa file khóa mồ côi {lock_file.name} (chạy với --fix để tự động xóa).",
                        auto_fixable=True,
                    )
                )

            # 4.2 Quét các file checkpoint .json
            for json_file in wdir.glob("*.json"):
                rel_path = json_file.relative_to(self.repo_root).as_posix()
                try:
                    state = json.loads(json_file.read_text(encoding="utf-8"))
                    if not isinstance(state, dict):
                        continue

                    stage = state.get("stage")
                    reject_counts = state.get("reject_counts")

                    # Kiểm tra trần reject_counts chưa chuyển ESCALATED
                    if isinstance(reject_counts, dict):
                        # App workflow: {"design": int, "code": int}
                        reached_ceiling = any(
                            isinstance(cnt, int) and cnt >= 2 for cnt in reject_counts.values()
                        )
                        if reached_ceiling and stage != "ESCALATED":
                            issues.append(
                                DoctorIssue(
                                    code="ERR_WORKFLOW_STUCK",
                                    severity="ERROR",
                                    pillar=pillar,
                                    message=(
                                        f"Task {state.get('task_id', json_file.stem)} trong {rel_path} "
                                        f"đã chạm trần reject ({reject_counts}) nhưng stage='{stage}' (chưa ESCALATED)."
                                    ),
                                    remediation=f"Chuyển trạng thái task {state.get('task_id')} sang ESCALATED để kích hoạt cầu dao ngắt mạch.",
                                    auto_fixable=False,
                                )
                            )
                    elif isinstance(reject_counts, int) and reject_counts >= 2:
                        # Dạng integer reject counter
                        if stage != "ESCALATED":
                            issues.append(
                                DoctorIssue(
                                    code="ERR_WORKFLOW_STUCK",
                                    severity="ERROR",
                                    pillar=pillar,
                                    message=(
                                        f"Task {state.get('task_id', json_file.stem)} trong {rel_path} "
                                        f"đã có reject_counts={reject_counts} nhưng chưa chuyển sang ESCALATED."
                                    ),
                                    remediation=f"Chuyển task {state.get('task_id')} sang ESCALATED.",
                                    auto_fixable=False,
                                )
                            )
                except Exception as exc:
                    issues.append(
                        DoctorIssue(
                            code="ERR_WORKFLOW_STUCK",
                            severity="ERROR",
                            pillar=pillar,
                            message=f"File checkpoint {rel_path} bị hỏng hoặc không thể đọc: {exc}",
                            remediation=f"Kiểm tra hoặc lưu trữ checkpoint {json_file.name}.",
                            auto_fixable=False,
                        )
                    )

        return issues

    # =========================================================================
    # TRỤ CỘT 5: PROCESS & STORAGE HYGIENE
    # =========================================================================
    def check_pillar_5_hygiene(self) -> List[DoctorIssue]:
        """Kiểm tra dung lượng lưu trữ phiên và tiến trình mồ côi."""
        issues: List[DoctorIssue] = []
        pillar = "Pillar 5: Process & Storage Hygiene"

        # 5.1 Kiểm tra dung lượng thư mục .sessions/
        sessions_dir = self.repo_root / ".sessions"
        if sessions_dir.exists():
            try:
                total_bytes = self.get_directory_size(sessions_dir)
                if total_bytes > MAX_SESSIONS_BYTES:
                    size_mb = total_bytes / (1024 * 1024)
                    issues.append(
                        DoctorIssue(
                            code="WARN_STORAGE_SESSIONS",
                            severity="WARN",
                            pillar=pillar,
                            message=f"Dung lượng thư mục .sessions ({size_mb:.1f} MB) vượt ngưỡng cảnh báo 500 MB.",
                            remediation="Lưu trữ hoặc dọn bớt các phiên cũ bằng python scripts/session_manager.py.",
                            auto_fixable=False,
                        )
                    )
            except Exception as exc:
                if self.verbose:
                    print(f"[VERBOSE] Không thể tính dung lượng .sessions: {exc}")

        # 5.2 Kiểm tra tiến trình mồ côi tiềm ẩn (WINWORD, EXCEL, headless browsers)
        try:
            import psutil
            current_pid = os.getpid()
            ignored_pids = {current_pid}
            try:
                ignored_pids.add(psutil.Process().parent().pid)
            except Exception:
                pass

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    pid = proc.info.get("pid")
                    if pid in ignored_pids:
                        continue
                    pname = (proc.info.get("name") or "").upper()

                    # COM processes
                    if pname in ("WINWORD.EXE", "EXCEL.EXE"):
                        issues.append(
                            DoctorIssue(
                                code="WARN_ORPHAN_PROCESS",
                                severity="WARN",
                                pillar=pillar,
                                message=f"Phát hiện tiến trình Office COM tiềm ẩn nguy cơ treo modal ngầm: {pname} (PID: {pid}).",
                                remediation="Chạy 'python scripts/safe_com_runner.py cleanup' để giải phóng tiến trình Office.",
                                auto_fixable=True,
                            )
                        )

                    # Headless test browser shells
                    elif pname in ("CHROME.EXE", "CHROMIUM.EXE", "MSEDGE.EXE", "CHROMEDRIVER.EXE"):
                        cmdline_str = " ".join(proc.info.get("cmdline") or []).lower()
                        if "--headless" in cmdline_str or "--test-type" in cmdline_str:
                            issues.append(
                                DoctorIssue(
                                    code="WARN_ORPHAN_PROCESS",
                                    severity="WARN",
                                    pillar=pillar,
                                    message=f"Phát hiện headless test browser shell chạy ngầm: {pname} (PID: {pid}).",
                                    remediation="Dọn dẹp tiến trình qua kỹ năng /browser-hygiene hoặc taskkill.",
                                    auto_fixable=False,
                                )
                            )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except ImportError:
            if self.verbose:
                print("[VERBOSE] Thư viện psutil chưa cài đặt, bỏ qua quét tiến trình hệ thống.")
        except Exception as exc:
            if self.verbose:
                print(f"[VERBOSE] Lỗi khi quét tiến trình: {exc}")

        return issues

    # =========================================================================
    # CƠ CHẾ TỰ SỬA LỖI (SELF-HEALING ENGINE --fix)
    # =========================================================================
    def apply_fixes(self, issues: List[DoctorIssue]) -> int:
        """Tự động sửa chữa các lỗi có cờ auto_fixable=True."""
        fixed_count = 0

        for issue in issues:
            if not issue.auto_fixable or issue.fixed:
                continue

            # Fix 1: Reset .agents/skills.json về {"entries": []}
            if issue.code == "ERR_DOUBLE_LOADING":
                skills_json = self.repo_root / ".agents" / "skills.json"
                try:
                    skills_json.parent.mkdir(parents=True, exist_ok=True)
                    skills_json.write_text('{\n  "entries": []\n}\n', encoding="utf-8")
                    issue.fixed = True
                    fixed_count += 1
                except Exception as exc:
                    issue.message += f" (Tự sửa thất bại: {exc})"

            # Fix 2: Xóa lock file mồ côi
            elif issue.code == "ERR_ORPHAN_LOCK":
                match = re.search(r"file khóa mồ côi: ([^\s]+)", issue.message)
                if match:
                    lock_rel = match.group(1).strip()
                    lock_path = self.repo_root / lock_rel
                    try:
                        if lock_path.exists():
                            lock_path.unlink()
                        issue.fixed = True
                        fixed_count += 1
                    except Exception as exc:
                        issue.message += f" (Xóa lock thất bại: {exc})"

            # Fix 3: Dọn dẹp tiến trình COM qua safe_com_runner
            elif issue.code == "WARN_ORPHAN_PROCESS" and ("WINWORD" in issue.message or "EXCEL" in issue.message):
                try:
                    from scripts.safe_com_runner import cleanup_com_processes
                    cleanup_com_processes("all")
                    issue.fixed = True
                    fixed_count += 1
                except Exception as exc:
                    issue.message += f" (Dọn tiến trình COM thất bại: {exc})"

        return fixed_count

    # =========================================================================
    # ĐỊNH DẠNG BÁO CÁO HIỂN THỊ
    # =========================================================================
    def format_report(self, report: DoctorReport) -> str:
        """Định dạng báo cáo chẩn đoán dễ đọc cho người dùng."""
        lines: List[str] = []
        lines.append("=" * 70)
        lines.append("🏥  BÁC SĨ NỘI TRÚ HARNESS (HARNESS DOCTOR & SELF-HEALING ENGINE)")
        lines.append("=" * 70)
        lines.append(f"Thư mục làm việc: {report.repo_root}")
        lines.append(f"Số trụ cột đã kiểm tra: {report.checks_run}/5")

        unresolved_errors = [i for i in report.issues if i.severity == "ERROR" and not i.fixed]
        unresolved_warns = [i for i in report.issues if i.severity == "WARN" and not i.fixed]
        fixed_issues = [i for i in report.issues if i.fixed]

        lines.append(
            f"Trạng thái tổng thể: {'🟢 HOÀN TOÀN KHỎE MẠNH (HEALTHY)' if report.healthy else '🔴 CẦN XỬ LÝ (UNHEALTHY)'}"
        )
        lines.append(
            f"Tổng số vấn đề: {len(report.issues)} "
            f"(Lỗi: {len(unresolved_errors)}, Cảnh báo: {len(unresolved_warns)}, Đã sửa tự động: {len(fixed_issues)})"
        )
        lines.append("-" * 70)

        if not report.issues:
            lines.append("✨ Toàn bộ 5 trụ cột đều đạt chuẩn hoàn hảo. Không phát hiện bất thường.")
            lines.append("=" * 70)
            return "\n".join(lines)

        # Phân nhóm theo Trụ Cột
        by_pillar: Dict[str, List[DoctorIssue]] = {}
        for issue in report.issues:
            by_pillar.setdefault(issue.pillar, []).append(issue)

        for pillar_name, p_issues in by_pillar.items():
            lines.append(f"\n📌 {pillar_name}:")
            for issue in p_issues:
                if issue.fixed:
                    tag = "✅ [ĐÃ TỰ SỬA]"
                elif issue.severity == "ERROR":
                    tag = "❌ [LỖI NGHIÊM TRỌNG]"
                else:
                    tag = "⚠️  [CẢNH BÁO]"

                lines.append(f"  {tag} [{issue.code}] {issue.message}")
                if not issue.fixed:
                    lines.append(f"     💊 Đơn thuốc: {issue.remediation}")

        # Mục đơn thuốc tổng hợp nếu có lỗi cần người dùng quyết định
        actionable_issues = [i for i in report.issues if not i.fixed]
        if actionable_issues:
            lines.append("\n" + "=" * 70)
            lines.append("📋  DANH SÁCH ĐƠN THUỐC ĐỀ XUẤT (REMEDIATION PRESCRIPTIONS):")
            lines.append("=" * 70)
            for idx, issue in enumerate(actionable_issues, 1):
                lines.append(f"{idx}. [{issue.code}] {issue.remediation}")

        lines.append("=" * 70)
        return "\n".join(lines)


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Harness Doctor & Self-Healing Engine: Bác sĩ nội trú tự chẩn đoán & tự sửa lỗi"
    )
    parser.add_argument(
        "--root", "--app-dir",
        dest="repo_root",
        default=str(REPO_ROOT),
        help="Đường dẫn thư mục repository gốc của Harness",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Bật cỗ máy tự động sửa chữa các lỗi mồ côi / cấu hình an toàn",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất báo cáo dưới định dạng JSON",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="In chi tiết quá trình quét nội bộ",
    )
    parser.add_argument(
        "--target-file",
        default=None,
        help="Chỉ định file văn bản/báo cáo cụ thể để kiểm toán chống ảo giác (Trụ cột 3)",
    )

    args = parser.parse_args(argv)

    doctor = HarnessDoctor(
        repo_root=args.repo_root,
        auto_fix=args.fix,
        verbose=args.verbose,
        target_file=args.target_file,
    )

    report = doctor.run()

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(doctor.format_report(report))

    # Thoát với mã 0 nếu hoàn toàn khỏe mạnh hoặc đã sửa hết lỗi nghiêm trọng
    unresolved_errors = [i for i in report.issues if i.severity == "ERROR" and not i.fixed]
    return 0 if len(unresolved_errors) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
