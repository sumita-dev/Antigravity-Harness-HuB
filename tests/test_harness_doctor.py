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

    mock_psutil = MagicMock()
    mock_psutil.process_iter.return_value = [fake_proc]
    mock_psutil.Process.return_value.parent.return_value.pid = 88888

    with patch.dict("sys.modules", {"psutil": mock_psutil}):
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
# STATIC SURFACE VALIDATOR (PHA 2)
# =============================================================================
def test_pillar_1_always_on_warn_and_error_thresholds(tmp_path):
    """Kiểm tra ngưỡng WARN/ERROR always_on mặc định và override qua harness_config.json."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "GEMINI.md").write_text("a" * 100, encoding="utf-8")
    (rules_dir / "r1.md").write_text("b" * 48_000, encoding="utf-8")

    # Mặc định: > 48,000 và <= 100,000 -> WARN_ALWAYS_ON_OVERBUDGET
    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    warn_issues = [i for i in issues if i.code == "WARN_ALWAYS_ON_OVERBUDGET"]
    assert len(warn_issues) == 1
    assert warn_issues[0].severity == "WARN"
    assert warn_issues[0].auto_fixable is False

    # Override ngưỡng qua configs/harness_config.json -> kích hoạt ERR_ALWAYS_ON_OVERBUDGET
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    (configs_dir / "harness_config.json").write_text(
        json.dumps({"always_on_warn_max": 1000, "always_on_max": 10_000}),
        encoding="utf-8",
    )
    issues_err = doctor.check_pillar_1_rules()
    err_issues = [i for i in issues_err if i.code == "ERR_ALWAYS_ON_OVERBUDGET"]
    assert len(err_issues) == 1
    assert err_issues[0].severity == "ERROR"
    assert err_issues[0].auto_fixable is False


def test_pillar_1_hooks_valid_antigravity_schema(tmp_path):
    """Kiểm tra hooks.json và .agents/hooks.json hợp lệ theo chuẩn Antigravity 2.0."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "pre.py").write_text("print('ok')\n", encoding="utf-8")
    (scripts_dir / "stop.py").write_text("print('stop')\n", encoding="utf-8")

    valid_hooks = {
        "auto-code-harvester": {
            "PreInvocation": [
                {"type": "command", "command": "python scripts/pre.py", "timeout": 15}
            ],
            "Stop": [
                {"type": "command", "command": "python scripts/stop.py", "timeout": 60}
            ],
        }
    }
    (tmp_path / "hooks.json").write_text(json.dumps(valid_hooks), encoding="utf-8")
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "hooks.json").write_text(json.dumps(valid_hooks), encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    assert not any(i.code in {"ERR_HOOK_SCHEMA", "WARN_HOOK_EVENT"} for i in issues)


def test_pillar_1_hooks_invalid_json_and_schema(tmp_path):
    """Kiểm tra phát hiện lỗi JSON, sai schema, timeout=True/0, và hook gọi script không tồn tại."""
    # 1. JSON hỏng ở hooks.json
    (tmp_path / "hooks.json").write_text("{invalid json", encoding="utf-8")
    # 2. Sai schema + bool timeout + missing script ở .agents/hooks.json
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    bad_hooks = {
        "ns": {
            "PreInvocation": [
                {"type": "http", "command": "python scripts/missing.py", "timeout": True},
                {"type": "command", "command": "", "timeout": 0},
            ]
        }
    }
    (agents_dir / "hooks.json").write_text(json.dumps(bad_hooks), encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    hook_errors = [i for i in issues if i.code == "ERR_HOOK_SCHEMA"]
    assert len(hook_errors) >= 5
    assert any("scripts/missing.py" in i.message for i in hook_errors)
    assert any("timeout" in i.message for i in hook_errors)
    assert all(i.auto_fixable is False for i in hook_errors)


def test_pillar_1_hooks_unknown_event_warns(tmp_path):
    """Kiểm tra event lạ trong hooks.json phát sinh WARN_HOOK_EVENT (không phải ERROR)."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    hooks = {
        "ns": {
            "CustomUnknownEvent": [
                {"type": "command", "command": "python scripts/ok.py", "timeout": 10}
            ]
        }
    }
    (tmp_path / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_1_rules()
    warns = [i for i in issues if i.code == "WARN_HOOK_EVENT"]
    assert len(warns) == 1
    assert warns[0].severity == "WARN"
    assert not any(i.code == "ERR_HOOK_SCHEMA" for i in issues)


def test_pillar_2_skill_script_ref_resolution(tmp_path):
    """Kiểm tra phân giải 3 dạng tham chiếu scripts/*.py trong SKILL.md, lọc placeholder và bắt missing."""
    # Root script
    root_scripts = tmp_path / "scripts"
    root_scripts.mkdir(parents=True, exist_ok=True)
    (root_scripts / "global_tool.py").write_text("print('global')\n", encoding="utf-8")

    # Skill dir + local scripts
    skill_dir = tmp_path / "plugins" / "pack" / "skills" / "demo-skill"
    local_scripts = skill_dir / "scripts"
    local_scripts.mkdir(parents=True, exist_ok=True)
    (local_scripts / "local_a.py").write_text("print('a')\n", encoding="utf-8")
    (local_scripts / "local_b.py").write_text("print('b')\n", encoding="utf-8")

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: demo-skill\ndescription: Demo skill\n---\n"
        "Run `./scripts/local_a.py`, `scripts/local_b.py`, "
        "`plugins/pack/skills/demo-skill/scripts/local_a.py`, and `scripts/global_tool.py`.\n"
        "Ignore placeholders: `scripts/foo.py`, `scripts/example.py`, `scripts/path/to/bar.py`.\n"
        "Missing ref: `scripts/does_not_exist.py`.\n",
        encoding="utf-8",
    )

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_2_skills()
    missing = [i for i in issues if i.code == "ERR_SKILL_SCRIPT_MISSING"]
    assert len(missing) == 1
    assert "scripts/does_not_exist.py" in missing[0].message
    assert missing[0].auto_fixable is False


def test_pillar_2_python_script_compile_syntax_error(tmp_path):
    """Kiểm tra phát hiện SyntaxError qua compile() và bỏ qua __pycache__."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "good.py").write_text("x = 1 + 2\n", encoding="utf-8")
    (scripts_dir / "broken.py").write_text("def bad(:\n    pass\n", encoding="utf-8")

    pycache_dir = scripts_dir / "__pycache__"
    pycache_dir.mkdir(parents=True, exist_ok=True)
    (pycache_dir / "ignored.py").write_text("def broken_cache(:\n", encoding="utf-8")

    doctor = HarnessDoctor(repo_root=tmp_path)
    issues = doctor.check_pillar_2_skills()
    syntax_errs = [i for i in issues if i.code == "ERR_SCRIPT_SYNTAX"]
    assert len(syntax_errs) == 1
    assert "scripts/broken.py" in syntax_errs[0].message
    assert syntax_errs[0].auto_fixable is False


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
