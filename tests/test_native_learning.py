"""Test suite cho Cơ chế Tự học và Nâng cấp Thực chiến trên Antigravity 2.0 (Phương án 1).

Bao gồm:
1. Auto-hook trong AppWorkflowStore (APPROVED & ESCALATED)
2. Auto-hook trong MarketingWorkflowStore (APPROVED & ESCALATED)
3. Phân loại 5 danh mục lỗi (SPEC_GAP, LINT_REGRESSION, TEST_FAILURE, POLICY_VIOLATION, STAGNATION)
4. Tra cứu song ngữ Việt - Anh, không dấu, loại bỏ dấu câu của LearningHarvester
5. format_patterns_for_prompt và get_intake_lessons
6. Bóc tách thông tin thực tế trong SkillDistiller
"""

import json
from pathlib import Path
import pytest

from harness.app_workflow import AppWorkflowStore
from harness.marketing_workflow import MarketingWorkflowStore
from harness.memory.harvester import (
    CATEGORIES,
    LearningHarvester,
    get_intake_lessons,
    strip_vietnamese_accents,
    tokenize_and_normalize,
)
from harness.memory.trajectory import TrajectoryStore
from harness.memory.distiller import SkillDistiller


# =====================================================================
# 1. AUTO-HOOK TRONG APP WORKFLOW
# =====================================================================

def test_app_workflow_auto_hook_approved(tmp_path):
    brain_dir = tmp_path / "brain"
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True)
    code_file = project_root / "main.py"
    code_file.write_text("print('hello')", encoding="utf-8")

    store = AppWorkflowStore(root=brain_dir)
    task_id = "test-app-approve-001"

    # Init
    store.create(task_id, "Tích hợp cổng thanh toán Stripe", project_root)

    # Spec
    spec = {
        "scope": "Tích hợp cổng thanh toán Stripe",
        "design": "REST webhook handler",
        "contracts": "POST /stripe/webhook",
        "risks": "Idempotency",
        "acceptance_criteria": [
            {"id": "AC1", "description": "Xử lý thành công webhook", "ui": False, "applicable": True}
        ],
        "verification_commands": [
            {"id": "cmd-1", "command": "python -c 'pass'", "cwd": ".", "ac_ids": ["AC1"]}
        ]
    }
    store.submit_spec(task_id, spec, "architect-1")
    state = store.status(task_id)

    # Review Design -> APPROVE
    store.review_design(task_id, "APPROVE", "reviewer-1", state["spec_sha256"], "Design approved")
    state = store.status(task_id)

    # Sign Off
    store.sign_off(task_id, state["spec_sha256"], "Duyệt")

    # Tạo file log kiểm thử trước khi nộp implementation để manifest khớp chính xác
    log_file = project_root / "test.log"
    log_file.write_text("OK", encoding="utf-8")

    # Implementation
    store.submit_implementation(task_id, "builder-1", "Done implement")
    state = store.status(task_id)

    # Audit -> APPROVE
    audit_payload = {
        "report": "All tests passed",
        "spec_sha256": state["spec_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "commands": [
            {"id": "cmd-1", "command": "python -c 'pass'", "cwd": str(project_root), "exit_code": 0, "log": str(log_file), "ac_ids": ["AC1"]}
        ],
        "preview": {
            "checks": [
                {"id": "AC1", "status": "PASS", "evidence": str(log_file)}
            ]
        }
    }
    store.audit(task_id, "APPROVE", "auditor-1", audit_payload)

    # Kiểm tra TrajectoryStore được ghi nhận tự động
    t_store = TrajectoryStore(path=brain_dir / "trajectories" / "trajectories.jsonl")
    trajectories = t_store.get_trajectories(branch="app")
    assert len(trajectories) == 1
    t = trajectories[0]
    assert t["task_id"] == task_id
    assert t["branch"] == "app"
    assert t["final_verdict"] == "APPROVE"
    assert "Stripe" in t["task_description"]
    assert len(t["steps"]) > 0

    # Kiểm tra LearningHarvester được gọi tự động
    harvester = LearningHarvester(path=brain_dir / "learnings" / "patterns.json")
    assert len(harvester.patterns) == 1
    p = harvester.patterns[0]
    assert p["pattern_type"] == "SUCCESS"
    assert p["branch"] == "app"
    assert "Stripe" in p["description"]


def test_app_workflow_auto_hook_escalated(tmp_path):
    brain_dir = tmp_path / "brain"
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True)

    store = AppWorkflowStore(root=brain_dir)
    task_id = "test-app-escalate-001"

    store.create(task_id, "Nhiệm vụ bị lỗi kiến trúc", project_root)
    spec = {
        "scope": "Nhiệm vụ bị lỗi kiến trúc",
        "design": "Design",
        "contracts": "Contracts",
        "risks": "Risks",
        "acceptance_criteria": [
            {"id": "AC1", "description": "Tiêu chí 1", "ui": False, "applicable": True}
        ]
    }
    store.submit_spec(task_id, spec, "architect-1")
    state = store.status(task_id)

    # Reject lần 1 -> về lại DESIGN
    store.review_design(task_id, "REJECT", "reviewer-1", state["spec_sha256"], "Thiếu chi tiết")
    # Nộp lại spec
    store.submit_spec(task_id, spec, "architect-1")
    state = store.status(task_id)

    # Reject lần 2 -> Circuit breaker kích hoạt -> ESCALATED
    store.review_design(task_id, "REJECT", "reviewer-1", state["spec_sha256"], "Vẫn thiếu chi tiết")
    state = store.status(task_id)
    assert state["stage"] == "ESCALATED"

    # Kiểm tra TrajectoryStore
    t_store = TrajectoryStore(path=brain_dir / "trajectories" / "trajectories.jsonl")
    trajectories = t_store.get_trajectories(branch="app")
    assert len(trajectories) == 1
    t = trajectories[0]
    assert t["task_id"] == task_id
    assert t["final_verdict"] == "ESCALATE"
    assert t["critique_rounds"] >= 2

    # Kiểm tra LearningHarvester
    harvester = LearningHarvester(path=brain_dir / "learnings" / "patterns.json")
    assert len(harvester.patterns) == 1
    p = harvester.patterns[0]
    assert p["pattern_type"] == "ANTI_PATTERN"
    assert p["category"] in CATEGORIES


# =====================================================================
# 2. AUTO-HOOK TRONG MARKETING WORKFLOW
# =====================================================================

def test_marketing_workflow_auto_hook_approved(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir(parents=True)
    evidence_file = brain_dir / "evidence.txt"
    evidence_file.write_text("Bằng chứng thực tế thị trường", encoding="utf-8")
    report_file = brain_dir / "report.txt"
    report_file.write_text("Báo cáo audit chuẩn", encoding="utf-8")

    store = MarketingWorkflowStore(root=brain_dir)
    task_id = "test-mkt-approve-001"
    store.create(task_id, "Kịch bản quảng cáo sản phẩm mới", "research-only")

    # Submit dossier
    dossier_payload = {
        "schema_version": 1,
        "brief": "Kịch bản quảng cáo sản phẩm mới",
        "sources": [
            {"id": "src-1", "reference": "https://example.com", "retrieved_at": "2026-10-09", "evidence": str(evidence_file)}
        ],
        "claims": [
            {"id": "clm-1", "statement": "Tăng trưởng 50%", "source_ids": ["src-1"], "status": "verified", "units": "%", "timeframe": "2026"}
        ],
        "limitations": ["Không áp dụng thị trường quốc tế"]
    }
    store.submit_dossier(task_id, "researcher-1", dossier_payload)
    state = store.status(task_id)

    # Audit APPROVE (research-only mode)
    audit_payload = {
        "verdict": "APPROVE",
        "report": str(report_file),
        "dossier_sha256": state["dossier_sha256"],
        "baseline_sha256": state["baseline_sha256"],
        "claim_checks": [
            {"claim_id": "clm-1", "status": "PASS", "evidence": str(evidence_file)}
        ],
        "checklist": [
            {"id": "source_accuracy", "status": "PASS", "evidence": str(evidence_file)},
            {"id": "policy", "status": "PASS", "evidence": str(evidence_file)},
            {"id": "integrity", "status": "PASS", "evidence": str(evidence_file)},
            {"id": "task_quality", "status": "PASS", "evidence": str(evidence_file)},
        ]
    }
    store.audit(task_id, "checker-1", audit_payload)
    state = store.status(task_id)
    assert state["stage"] == "APPROVED"

    # Kiểm tra TrajectoryStore
    t_store = TrajectoryStore(path=brain_dir / "trajectories" / "trajectories.jsonl")
    trajectories = t_store.get_trajectories(branch="marketing")
    assert len(trajectories) == 1
    t = trajectories[0]
    assert t["task_id"] == task_id
    assert t["branch"] == "marketing"
    assert t["final_verdict"] == "APPROVE"

    # Kiểm tra Harvester
    harvester = LearningHarvester(path=brain_dir / "learnings" / "patterns.json")
    assert len(harvester.patterns) == 1
    p = harvester.patterns[0]
    assert p["pattern_type"] == "SUCCESS"
    assert p["branch"] == "marketing"


def test_marketing_workflow_auto_hook_escalated(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir(parents=True)
    evidence_file = brain_dir / "ev.txt"
    evidence_file.write_text("Data", encoding="utf-8")
    report_file = brain_dir / "rep.txt"
    report_file.write_text("Report", encoding="utf-8")

    store = MarketingWorkflowStore(root=brain_dir)
    task_id = "test-mkt-escalate-001"
    store.create(task_id, "Chiến dịch chứa AI Slop vi phạm", "research-only")

    dossier_payload = {
        "schema_version": 1,
        "brief": "Chiến dịch chứa AI Slop vi phạm",
        "sources": [
            {"id": "s1", "reference": "ref", "retrieved_at": "now", "evidence": str(evidence_file)}
        ],
        "claims": [
            {"id": "c1", "statement": "claim", "source_ids": ["s1"], "status": "verified", "units": "u", "timeframe": "t"}
        ],
        "limitations": ["none"]
    }
    store.submit_dossier(task_id, "res-1", dossier_payload)
    state = store.status(task_id)

    # Audit ESCALATE
    audit_payload = {
        "verdict": "ESCALATE",
        "report": str(report_file),
        "dossier_sha256": state["dossier_sha256"],
        "baseline_sha256": state["baseline_sha256"],
    }
    store.audit(task_id, "chk-1", audit_payload)
    state = store.status(task_id)
    assert state["stage"] == "ESCALATED"

    # Trajectory & Harvester check
    t_store = TrajectoryStore(path=brain_dir / "trajectories" / "trajectories.jsonl")
    trajectories = t_store.get_trajectories(branch="marketing")
    assert len(trajectories) == 1
    assert trajectories[0]["final_verdict"] == "ESCALATE"

    harvester = LearningHarvester(path=brain_dir / "learnings" / "patterns.json")
    assert len(harvester.patterns) == 1
    assert harvester.patterns[0]["pattern_type"] == "ANTI_PATTERN"


# =====================================================================
# 3. PHÂN LOẠI 5 DANH MỤC LỖI TRONG HARVESTER
# =====================================================================

def test_harvester_failure_category_classification():
    # 1. SPEC_GAP
    traj_spec = {
        "task_description": "Xây dựng tính năng chat",
        "final_verdict": "REJECT",
        "failure_reason": "Thiếu acceptance criteria AC2 và sai spec hợp đồng API",
    }
    assert LearningHarvester._classify_failure_category(traj_spec) == "SPEC_GAP"

    # 2. LINT_REGRESSION
    traj_lint = {
        "task_description": "Refactor codebase",
        "final_verdict": "REJECT",
        "failure_reason": "Lỗi flake8 style violation và typecheck hồi quy mã nguồn",
    }
    assert LearningHarvester._classify_failure_category(traj_lint) == "LINT_REGRESSION"

    # 3. TEST_FAILURE
    traj_test = {
        "task_description": "Viết module parser",
        "final_verdict": "REJECT",
        "failure_reason": "Bộ kiểm thử tự động pytest thất bại với exit code 1",
    }
    assert LearningHarvester._classify_failure_category(traj_test) == "TEST_FAILURE"

    # 4. POLICY_VIOLATION
    traj_policy = {
        "task_description": "Soạn bài viết tuyển dụng",
        "final_verdict": "REJECT",
        "failure_reason": "Vi phạm chính sách cộng đồng và phát hiện AI Slop trong hook",
    }
    assert LearningHarvester._classify_failure_category(traj_policy) == "POLICY_VIOLATION"

    # 5. STAGNATION
    traj_stagnation = {
        "task_description": "Sửa lỗi crash",
        "final_verdict": "ESCALATE",
        "critique_rounds": 2,
        "failure_reason": "Chạm ngưỡng circuit breaker do lặp lỗi liên tiếp",
    }
    assert LearningHarvester._classify_failure_category(traj_stagnation) == "STAGNATION"

    # Explicit override
    traj_override = {
        "task_description": "Nhiệm vụ custom",
        "final_verdict": "REJECT",
        "category": "TEST_FAILURE",
        "failure_reason": "Không rõ",
    }
    assert LearningHarvester._classify_failure_category(traj_override) == "TEST_FAILURE"


# =====================================================================
# 4. TRA CỨU SONG NGỮ VIỆT - ANH, KHÔNG DẤU, LOẠI BỎ DẤU CÂU
# =====================================================================

def test_harvester_bilingual_and_punctuation_retrieval(tmp_path):
    harvester = LearningHarvester(path=tmp_path / "patterns.json")

    # Seed patterns
    p1 = harvester.harvest({
        "task_id": "t1",
        "branch": "app",
        "task_description": "Xây dựng xác thực JWT bảo mật với Refresh Token",
        "final_verdict": "APPROVE",
        "steps": [{"step": "INTAKE"}, {"step": "AUDIT"}],
    })
    p2 = harvester.harvest({
        "task_id": "t2",
        "branch": "app",
        "task_description": "Optimize Redis database cache performance",
        "final_verdict": "APPROVE",
        "steps": [{"step": "INTAKE"}, {"step": "AUDIT"}],
    })
    p3 = harvester.harvest({
        "task_id": "t3",
        "branch": "marketing",
        "task_description": "Soạn kịch bản video TikTok 6 format chống AI Slop",
        "final_verdict": "ESCALATE",
        "failure_reason": "Chứa từ ngữ AI Slop và vi phạm chính sách",
    })

    # Test 1: Khớp tiếng Việt có dấu
    res1 = harvester.retrieve_relevant_patterns("xác thực JWT bảo mật", branch="app")
    assert len(res1) >= 1
    assert res1[0]["id"] == p1["id"]

    # Test 2: Khớp tiếng Việt không dấu (accent-insensitive)
    res2 = harvester.retrieve_relevant_patterns("xac thuc jwt bao mat", branch="app")
    assert len(res2) >= 1
    assert res2[0]["id"] == p1["id"]

    # Test 3: Tiếng Anh kèm dấu câu ([CRITICAL] punctuation stripping)
    res3 = harvester.retrieve_relevant_patterns("[CRITICAL] Redis: cache & database?!", branch="app")
    assert len(res3) >= 1
    assert res3[0]["id"] == p2["id"]

    # Test 4: Lọc theo phân nhánh
    res_mkt = harvester.retrieve_relevant_patterns("AI Slop", branch="marketing")
    assert len(res_mkt) == 1
    assert res_mkt[0]["id"] == p3["id"]

    res_app = harvester.retrieve_relevant_patterns("AI Slop", branch="app")
    assert len(res_app) == 0


def test_strip_accents_and_tokenization():
    assert strip_vietnamese_accents("Đặc tả kiến trúc") == "Dac ta kien truc"
    res = tokenize_and_normalize("  [ERROR] Lỗi kiểm thử: Pytest failed!  ")
    assert "error" in res["raw_words"]
    assert "kiểm" in res["raw_words"]
    assert "kiem" in res["unaccented_words"]
    assert "pytest" in res["raw_words"]


# =====================================================================
# 5. FORMAT PATTERNS CHO PROMPT & GET_INTAKE_LESSONS
# =====================================================================

def test_format_patterns_for_prompt_and_get_intake_lessons(tmp_path):
    harvester = LearningHarvester(path=tmp_path / "patterns.json")

    # Trường hợp danh sách rỗng
    assert LearningHarvester.format_patterns_for_prompt([]) == ""
    assert get_intake_lessons("Không có gì", harvester=harvester) == ""

    # Gieo bài học
    harvester.harvest({
        "task_id": "succ-1",
        "branch": "app",
        "task_description": "Xử lý ảnh đại diện avatar upload",
        "final_verdict": "APPROVE",
        "steps": [{"step": "DESIGN"}],
    })
    harvester.harvest({
        "task_id": "fail-1",
        "branch": "app",
        "task_description": "Lưu trữ file ảnh người dùng",
        "final_verdict": "ESCALATE",
        "failure_reason": "Lỗi flake8 lint regression và thiếu type hints",
    })

    # Lấy intake lessons
    lessons = get_intake_lessons("Xử lý file ảnh avatar", branch="app", harvester=harvester)
    assert lessons != ""
    assert "BÀI HỌC KINH NGHIỆM TỪ CÁC TÁC VỤ TRƯỚC" in lessons
    assert "SUCCESS" in lessons
    assert "ANTI_PATTERN" in lessons
    assert "Nguyên nhân thất bại" in lessons


# =====================================================================
# 6. TỐI ƯU HÓA TRÍCH XUẤT THỰC TẾ TRONG SKILL DISTILLER
# =====================================================================

def test_distiller_extracts_practical_metadata(tmp_path):
    distiller = SkillDistiller()

    trajectory = {
        "task_id": "practical-task-1",
        "branch": "app",
        "task_description": "Tích hợp OAuth2 Google",
        "final_verdict": "APPROVE",
        "critique_rounds": 1,
        "failure_reason": "Vòng 1 bị từ chối do thiếu refresh token rotation",
        "category": "SPEC_GAP",
        "steps": [
            {"step": "INIT", "data": {"action": "Khởi tạo repo", "actor": "builder-1"}},
            {"step": "AUDIT", "data": {"verdict": "APPROVE", "actor": "auditor-1"}}
        ],
        "metadata": {
            "verification_commands": [
                {"id": "v1", "command": "pytest tests/test_oauth.py"}
            ],
            "required_checks": ["token_expiry_check"],
            "acceptance_criteria": [
                {"id": "AC1", "description": "Người dùng đăng nhập thành công qua Google"}
            ]
        }
    }

    distilled = distiller.distill_from_trajectory(trajectory)
    content = distilled["content"]

    # Kiểm tra trích xuất thực tế trong Procedure
    assert "Actor: builder-1" in content
    # Kiểm tra trích xuất thực tế trong Pitfalls
    assert "Nguyên nhân thất bại thực tế ghi nhận" in content
    assert "Thiếu sót đặc tả (Spec Gap)" in content
    # Kiểm tra trích xuất thực tế trong Verification
    assert "pytest tests/test_oauth.py" in content
    assert "token_expiry_check" in content
    assert "AC1" in content
