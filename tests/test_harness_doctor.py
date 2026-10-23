"""Unit tests cho hệ thống Bác Sĩ Nội Trú (Harness Doctor & Self-Healing Engine).

Kiểm thử toàn diện 5 Trụ Cột:
1. Rules & Context Budget (ERR_CTX_OVERBUDGET, ERR_DOUBLE_LOADING, auto-fix reset).
2. Skills & Composition Integrity (ERR_SKILL_LINT, ERR_SKILL_CYCLE).
3. Anti-Hallucination & Evidence Watchdog (ERR_HALLUCINATION_PATH, ERR_HALLUCINATION_SPECULATION).
4. Workflow Checkpoint & Circuit Breaker State (ERR_WORKFLOW_STUCK, ERR_ORPHAN_LOCK, auto-fix lock).
5. Process & Storage Hygiene (WARN_STORAGE_SESSIONS, WARN_ORPHAN_PROCESS).
6. CLI & Runner Integration (--doctor, --doctor-fix, --json).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.harness_doctor import (
    HarnessDoctor,
    DoctorIssue,
    DoctorReport,
    MAX_GEMINI_BYTES,
    MAX_GLOBAL_GEMINI_BYTES,
    MAX_SESSIONS_BYTES,
    main as doctor_main,
)
import run_harness


REPO_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# TRỤ CỘT 1: RULES & CONTEXT BUDGET
# =============================================================================
def test_pillar_1_healthy(tmp_path):
    """Kiểm tra Pillar 1 khi file đúng chuẩn ngân sách và skills.json rỗng."""
    (tmp_path / "GEMINI.md").write_text("# Standard Rules\nContent within budget.", encoding="utf-8")
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    (configs_dir / "global_gemini.md").write_text("# Global Rules\nSmall file.", encoding="utf-8")
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "skills.json").write_text('{\n  "entries": []\n}\n', encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    assert len(issues) == 0


def test_pillar_1_gemini_overbudget(tmp_path):
    """Kiểm tra phát hiện GEMINI.md vượt trần 24KB."""
    oversized_text = "x" * (MAX_GEMINI_BYTES + 100)
    (tmp_path / "GEMINI.md").write_text(oversized_text, encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    assert any(i.code == "ERR_CTX_OVERBUDGET" and "GEMINI.md" in i.message for i in issues)


def test_pillar_1_global_gemini_overbudget(tmp_path):
    """Kiểm tra phát hiện configs/global_gemini.md vượt trần 8KB."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    oversized_text = "x" * (MAX_GLOBAL_GEMINI_BYTES + 50)
    (configs_dir / "global_gemini.md").write_text(oversized_text, encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    assert any(i.code == "ERR_CTX_OVERBUDGET" and "global_gemini.md" in i.message for i in issues)


def test_pillar_1_double_loading_detection_and_fix(tmp_path):
    """Kiểm tra phát hiện và tự sửa .agents/skills.json bị nạp trùng."""
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    bad_skills_json = agents_dir / "skills.json"
    bad_skills_json.write_text('{\n  "entries": ["legacy-skill-1", "legacy-skill-2"]\n}\n', encoding="utf-8")

    # 1. Chẩn đoán thấy lỗi
    doctor = HarnessDoctor(repo_root=tmp_path, auto_fix=False)
    issues = doctor.check_pillar_1_rules()
    assert any(i.code == "ERR_DOUBLE_LOADING" for i in issues)

    # 2. Chạy với auto_fix=True -> reset về {"entries": []}
    doctor_fix = HarnessDoctor(repo_root=tmp_path, auto_fix=True)
    report = doctor_fix.run()
    assert report.fixed_count >= 1
    fixed_issue = next(i for i in report.issues if i.code == "ERR_DOUBLE_LOADING")
    assert fixed_issue.fixed is True

    # Kiểm tra nội dung file đã được reset
    updated_data = json.loads(bad_skills_json.read_text(encoding="utf-8"))
    assert updated_data == {"entries": []}


# =============================================================================
# TRỤ CỘT 2: SKILLS & COMPOSITION INTEGRITY
# =============================================================================
def test_pillar_2_cyclic_dependencies(tmp_path):
    """Kiểm tra phát hiện chu trình phụ thuộc lặp giữa các kỹ năng."""
    plugins_dir = tmp_path / "plugins" / "test-pack" / "skills"
    skill_a_dir = plugins_dir / "skill-a"
    skill_b_dir = plugins_dir / "skill-b"
    skill_a_dir.mkdir(parents=True, exist_ok=True)
    skill_b_dir.mkdir(parents=True, exist_ok=True)

    # Skill A depends on Skill B
    (skill_a_dir / "SKILL.md").write_text(
        "---\nname: skill-a\ndependencies: [\"skill-b\"]\ndescription: Skill A\n---\nBody A",
        encoding="utf-8",
    )
    # Skill B depends on Skill A -> CYCLE!
    (skill_b_dir / "SKILL.md").write_text(
        "---\nname: skill-b\ndependencies: [\"skill-a\"]\ndescription: Skill B\n---\nBody B",
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_2_skills()
    assert any(i.code == "ERR_SKILL_CYCLE" for i in issues)


def test_pillar_2_composition_budget_exceeded(tmp_path):
    """Kiểm tra phát hiện vi phạm composition budget (max_skills)."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    config_data = {
        "skill_composition": {
            "max_skills": 2,
            "max_chars": 5000,
            "stage": {
                "OVERLOADED": ["skill-1", "skill-2", "skill-3"]  # 3 skills > 2
            }
        }
    }
    (configs_dir / "harness_config.json").write_text(json.dumps(config_data), encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_2_skills()
    assert any(i.code == "ERR_SKILL_LINT" and "max_skills=2" in i.message for i in issues)


# =============================================================================
# TRỤ CỘT 3: ANTI-HALLUCINATION & EVIDENCE WATCHDOG
# =============================================================================
def test_pillar_3_missing_paths(tmp_path):
    """Kiểm tra phát hiện đường dẫn file ảo / không tồn tại."""
    target_file = tmp_path / "report_fake_paths.md"
    target_file.write_text(
        "Xem chi tiết cấu hình tại `harness/phantom_ghost_module_xyz.py`.",
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path, target_file=target_file)
    issues = doctor.check_pillar_3_hallucination()
    assert any(i.code == "ERR_HALLUCINATION_PATH" for i in issues)


def test_pillar_3_speculative_language(tmp_path):
    """Kiểm tra phát hiện từ ngữ võ đoán (Red Flag Phrases)."""
    target_file = tmp_path / "report_speculative.md"
    target_file.write_text(
        "Bản vá này should work và chắc là sẽ không gặp lỗi nào.",
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path, target_file=target_file)
    issues = doctor.check_pillar_3_hallucination()
    assert any(i.code == "ERR_HALLUCINATION_SPECULATION" and "should work" in i.message for i in issues)


def test_pillar_3_unverified_claims(tmp_path):
    """Kiểm tra phát hiện tuyên bố hoàn thành nhưng thiếu log thực thi exit code 0."""
    target_file = tmp_path / "report_unverified.md"
    target_file.write_text(
        "Tất cả test đã pass và fix thành công hoàn toàn mà không cần xem log.",
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path, target_file=target_file)
    issues = doctor.check_pillar_3_hallucination()
    assert any(i.code == "ERR_HALLUCINATION_SPECULATION" and "thiếu log thực thi" in i.message for i in issues)


def test_pillar_3_verified_evidence_passes(tmp_path):
    """Kiểm tra báo cáo đạt chuẩn với file thật và log exit code 0."""
    real_file = tmp_path / "actual_file.py"
    real_file.write_text("def hello(): pass", encoding="utf-8")

    target_file = tmp_path / "valid_report.md"
    target_file.write_text(
        "Đã hoàn thành chỉnh sửa trong `actual_file.py`.\n"
        "Tất cả test đã pass.\n"
        "pytest run exited with code 0\n",
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path, target_file=target_file)
    issues = doctor.check_pillar_3_hallucination()
    assert len(issues) == 0


# =============================================================================
# TRỤ CỘT 4: WORKFLOW CHECKPOINT & CIRCUIT BREAKER STATE
# =============================================================================
def test_pillar_4_orphan_lock_and_fix(tmp_path):
    """Kiểm tra phát hiện file .lock mồ côi và cơ chế tự động dọn dẹp qua --fix."""
    wf_dir = tmp_path / ".brain" / "app_workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    orphan_lock = wf_dir / "stuck-task.lock"
    orphan_lock.write_text("", encoding="utf-8")

    # 1. Không fix -> thấy lỗi
    doctor = HarnessDoctor(repo_root=tmp_path, auto_fix=False)
    issues = doctor.check_pillar_4_workflows()
    assert any(i.code == "ERR_ORPHAN_LOCK" for i in issues)
    assert orphan_lock.exists()

    # 2. Có fix -> tự xóa lock
    doctor_fix = HarnessDoctor(repo_root=tmp_path, auto_fix=True)
    report = doctor_fix.run()
    assert report.fixed_count >= 1
    assert not orphan_lock.exists()


def test_pillar_4_workflow_stuck_ceiling_not_escalated(tmp_path):
    """Kiểm tra phát hiện task chạm trần reject (>= 2) nhưng chưa chuyển ESCALATED."""
    wf_dir = tmp_path / ".brain" / "app_workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    stuck_task = wf_dir / "task-100.json"
    stuck_task.write_text(
        json.dumps({
            "task_id": "task-100",
            "stage": "IMPLEMENTATION",  # Sai! Đã reject 2 lần thì bắt buộc ESCALATED
            "reject_counts": {"design": 0, "code": 2},
        }),
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_4_workflows()
    assert any(i.code == "ERR_WORKFLOW_STUCK" and "task-100" in i.message for i in issues)


# =============================================================================
# TRỤ CỘT 5: PROCESS & STORAGE HYGIENE
# =============================================================================
def test_pillar_5_sessions_storage_warning(tmp_path):
    """Kiểm tra cảnh báo dung lượng .sessions vượt trần 500MB."""
    sessions_dir = tmp_path / ".sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    doctor = HarnessDoctor(repo_root=tmp_path)
    doctor.get_directory_size = MagicMock(return_value=MAX_SESSIONS_BYTES + 1024 * 1024)

    issues = doctor.check_pillar_5_hygiene()
    assert any(i.code == "WARN_STORAGE_SESSIONS" for i in issues)


def test_pillar_5_orphan_office_process_and_fix(tmp_path):
    """Kiểm tra cảnh báo tiến trình Office mồ côi và cơ chế tự động dọn dẹp."""
    fake_proc = MagicMock()
    fake_proc.info = {"pid": 99999, "name": "WINWORD.EXE", "cmdline": ["WINWORD.EXE"]}

    with patch("psutil.process_iter", return_value=[fake_proc]):
        with patch("scripts.safe_com_runner.cleanup_com_processes") as mock_cleanup:
            # 1. Chẩn đoán
            doctor = HarnessDoctor(repo_root=tmp_path, auto_fix=False)
            issues = doctor.check_pillar_5_hygiene()
            assert any(i.code == "WARN_ORPHAN_PROCESS" and "WINWORD.EXE" in i.message for i in issues)
            mock_cleanup.assert_not_called()

            # 2. Tự sửa lỗi qua --fix
            doctor_fix = HarnessDoctor(repo_root=tmp_path, auto_fix=True)
            report = doctor_fix.run()
            mock_cleanup.assert_called_with("all")


# =============================================================================
# KIỂM THỬ CLI & TÍCH HỢP RUN_HARNESS
# =============================================================================
def test_doctor_cli_healthy():
    """Kiểm tra chạy lệnh CLI doctor trên repository hiện tại đạt exit code 0."""
    exit_code = doctor_main(["--json"])
    assert exit_code == 0


def test_run_harness_integration_doctor():
    """Kiểm tra tích hợp trực tiếp tham số --doctor vào run_harness.py."""
    exit_code = run_harness.main(["--doctor", "--json"])
    assert exit_code == 0


def test_run_harness_integration_doctor_fix():
    """Kiểm tra tích hợp trực tiếp tham số --doctor-fix vào run_harness.py."""
    exit_code = run_harness.main(["--doctor-fix", "--json"])
    assert exit_code == 0
