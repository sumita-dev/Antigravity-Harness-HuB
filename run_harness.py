"""CLI của Antigravity Harness (mô phỏng state machine & vòng lặp tự học).

Ví dụ:
    python run_harness.py --task "Soạn kịch bản TikTok" --branch marketing
    python run_harness.py --task "Build login" --branch app --review-rounds 3 \
        --checker-output "VERDICT: REJECT"      # kiểm chứng circuit breaker
    python run_harness.py --task "viết content" --dump-skill
    python run_harness.py --curate              # đánh giá vòng đời & trùng lặp skill
    python run_harness.py --skills-pending      # xem hàng đợi kỹ năng chờ duyệt
    python run_harness.py --skills-approve <id> # duyệt kỹ năng từ staging
    python run_harness.py --distill <task_id>   # chưng cất kỹ năng từ trajectory
    python run_harness.py --doctor              # tự chẩn đoán sức khỏe 5 trụ cột hệ thống
    python run_harness.py --doctor-fix          # tự chẩn đoán và tự động sửa chữa lỗi an toàn
"""

import argparse
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from harness.orchestrator import ChiefOrchestrator
from harness.app_workflow import AppWorkflowStore, WorkflowError
from harness.marketing_workflow import MarketingWorkflowStore
from pathlib import Path


def workflow_action(args):
    """Record native checkpoints; execute explicitly runs signed verification commands."""
    store = AppWorkflowStore()
    payload = {}
    if args.payload:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise WorkflowError("Payload must be a JSON object")
    if args.workflow == "init":
        return store.create(args.task_id, args.task, args.project_root)
    if args.workflow == "status":
        return store.status(args.task_id)
    if args.workflow == "revise":
        return store.revise(args.task_id, payload.get("reason"))
    if args.workflow == "migrate-legacy":
        return store.migrate_legacy(args.task_id, payload.get("reason"))
    if args.workflow == "spec":
        return store.submit_spec(args.task_id, payload, args.actor)
    if args.workflow == "design-review":
        return store.review_design(args.task_id, payload.get("verdict"), args.actor,
                                   payload.get("spec_sha256"), payload.get("report"))
    if args.workflow == "code-review":
        return store.review_code(args.task_id, payload.get("verdict"), args.actor, payload.get("spec_sha256"), payload.get("manifest_sha256"), payload.get("report"))
    if args.workflow == "execute":
        return store.execute(args.task_id, args.actor, payload.get("command_id"))
    if args.workflow == "sign-off":
        return store.sign_off(args.task_id, payload.get("spec_sha256"), payload.get("human_message"))
    if args.workflow == "implementation":
        return store.submit_implementation(args.task_id, args.actor, payload.get("report"))
    if args.workflow == "audit-pending-browser":
        return store.request_browser_verification(args.task_id, args.actor, payload.get("report", "Awaiting human browser verification"))
    if args.workflow == "verify-browser":
        return store.verify_browser(args.task_id, args.actor, payload)
    return store.audit(args.task_id, payload.get("verdict"), args.actor, payload)


def marketing_workflow_action(args):
    """Record marketing evidence; never execute agents or external publishing."""
    store = MarketingWorkflowStore()
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8")) if args.payload else {}
    if not isinstance(payload, dict):
        raise WorkflowError("Payload must be a JSON object")
    action = args.marketing_workflow
    if action == "init":
        return store.create(args.task_id, args.task, args.marketing_mode)
    if action == "status":
        return store.status(args.task_id)
    if action == "revise":
        return store.revise(args.task_id, payload.get("reason"))
    if action == "research":
        return store.submit_dossier(args.task_id, args.actor, payload)
    if action == "content":
        return store.submit_content(args.task_id, args.actor, payload)
    if action == "audit":
        return store.audit(args.task_id, args.actor, payload)
    if action == "publish-prepare":
        store.prepare_publish(args.task_id, args.actor, payload)
    elif action == "publish-authorize":
        store.authorize_publish(args.task_id, payload.get("publish_id"), payload.get("raw_authorization"))
    elif action == "publish-reconcile":
        store.reconcile_publish(args.task_id, payload.get("publish_id"), args.actor, payload)
    return store.status(args.task_id)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity Harness CLI")
    parser.add_argument("--task", default=None, help="Mô tả nhiệm vụ")
    parser.add_argument("--marketing-workflow", choices=["init", "status", "research", "content", "audit", "revise", "publish-prepare", "publish-authorize", "publish-reconcile"],
                        help="Native marketing evidence checkpoints; no agents or external writes executed")
    parser.add_argument("--marketing-mode", choices=["content", "research-only"], default="content")
    parser.add_argument("--workflow", choices=["init", "status", "spec", "design-review", "sign-off", "implementation", "code-review", "execute", "audit", "audit-pending-browser", "verify-browser", "revise", "migrate-legacy"],
                        help="Native checkpoints; execute runs signed commands, never calls LLM agents")
    parser.add_argument("--project-root", help="Thư mục app local (workflow init)")
    parser.add_argument("--actor", help="ID phiên tác tử do runtime cung cấp")
    parser.add_argument("--payload", help="File JSON artifact/checkpoint")
    parser.add_argument("--branch", choices=["app", "marketing", "auto"],
                        default="auto", help="Nhánh xử lý (mặc định: tự định tuyến)")
    parser.add_argument("--checker-output", default="VERDICT: APPROVE",
                        help='Phán quyết của Checker, ví dụ "VERDICT: REJECT"')
    parser.add_argument("--review-rounds", type=int, default=1,
                        help="Số vòng review mô phỏng (>1 để thử circuit breaker)")
    parser.add_argument("--task-id", default=None, help="ID tùy chọn cho task")
    parser.add_argument("--dump-skill", action="store_true",
                        help="In nội dung skill đã nạp (cho pipeline bên ngoài)")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả dạng JSON")
    parser.add_argument("--auto-distill", action="store_true",
                        help="Tự động chưng cất kỹ năng vào staging khi task hoàn thành APPROVE")
    parser.add_argument("--distill", metavar="TASK_ID", default=None,
                        help="Chưng cất kỹ năng mới từ trajectory của task_id đã lưu")
    parser.add_argument("--curate", action="store_true",
                        help="Chạy Curator đánh giá vòng đời kỹ năng và phát hiện trùng lặp")
    parser.add_argument("--skills-pending", action="store_true",
                        help="Xem danh sách các kỹ năng đang chờ duyệt trong hàng đợi Staging")
    parser.add_argument("--skills-approve", metavar="STAGE_ID", default=None,
                        help="Phê duyệt một kỹ năng trong staging theo ID")
    parser.add_argument("--skills-reject", metavar="STAGE_ID", default=None,
                        help="Từ chối một kỹ năng trong staging theo ID")
    parser.add_argument("--doctor", action="store_true",
                        help="Chạy Bác Sĩ Nội Trú (Harness Doctor) tự chẩn đoán 5 trụ cột hệ thống")
    parser.add_argument("--doctor-fix", action="store_true",
                        help="Chạy Bác Sĩ Nội Trú và tự động kích hoạt cỗ máy tự sửa lỗi (--fix)")
    parser.add_argument("--clean-state-check", action="store_true",
                        help="Kiểm toán Clean State 5 chiều (D1-D5)")
    parser.add_argument("--feature-list", metavar="PATH", default=None,
                        help="Đường dẫn tới tệp feature_list.json")
    parser.add_argument("--vcr-audit", action="store_true",
                        help="Kiểm toán chỉ số VCR và tính toàn vẹn của Feature List")
    parser.add_argument("--verify-feature", metavar="FEAT_ID", default=None,
                        help="Thực thi kiểm chứng một feature cụ thể trong Feature List")
    parser.add_argument("--fast", action="store_true",
                        help="Chạy chế độ nhanh cho clean-state-check")

    args = parser.parse_args(argv)

    # ----------------------- CLEAN STATE CHECK -----------------------
    if args.clean_state_check:
        from harness.validators.clean_state_verifier import CleanStateVerifier, DimensionStatus
        proj_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parent
        cfg = {}
        if args.fast:
            cfg["fast_mode"] = True
        if args.feature_list:
            cfg["feature_list_path"] = args.feature_list
        verifier = CleanStateVerifier(project_root=proj_root, config=cfg)
        report = verifier.audit()
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(report.summary())
        return 0 if report.overall_status == DimensionStatus.PASS else 1

    # ----------------------- FEATURE LIST & VCR AUDIT -----------------------
    if args.vcr_audit:
        from harness.feature_list import FeatureList, WIPViolationError, FakePassingError, FeatureListValidationError
        fl_path = Path(args.feature_list).resolve() if args.feature_list else Path("specs/feature_list.json").resolve()
        if not fl_path.exists():
            msg = f"Feature list file not found: {fl_path}"
            print(json.dumps({"error": msg}, ensure_ascii=False) if args.json else f"Error: {msg}")
            return 1
        try:
            fl = FeatureList.load_from_file(fl_path)
            proj_root = Path(args.project_root).resolve() if args.project_root else fl_path.parent
            fl.validate(check_manifest_against_path=proj_root)
            res = {
                "status": "VALID",
                "project_id": fl.project_id,
                "vcr_metrics": fl.vcr_metrics.to_dict(),
            }
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                print(f"Feature List '{fl.project_id}' is VALID (VCR: {fl.vcr_metrics.vcr_score:.2f}, passing: {fl.vcr_metrics.passing}/{fl.vcr_metrics.total_features})")
            return 0
        except (WIPViolationError, FakePassingError, FeatureListValidationError, Exception) as exc:
            if args.json:
                print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
            else:
                print(f"Feature List validation failed: {exc}")
            return 1

    # ----------------------- VERIFY FEATURE -----------------------
    if args.verify_feature:
        from harness.feature_list import FeatureList, VerificationFailedError
        fl_path = Path(args.feature_list).resolve() if args.feature_list else Path("specs/feature_list.json").resolve()
        if not fl_path.exists():
            msg = f"Feature list file not found: {fl_path}"
            print(json.dumps({"error": msg}, ensure_ascii=False) if args.json else f"Error: {msg}")
            return 1
        fl = FeatureList.load_from_file(fl_path)
        actor = args.actor or "QA_Auditor"
        proj_root = Path(args.project_root).resolve() if args.project_root else fl_path.parent
        try:
            feat = fl.verify_feature(args.verify_feature, actor=actor, project_root=proj_root)
            fl.save()
            if args.json:
                print(json.dumps(feat.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(f"Feature {feat.id} verified successfully! State: {feat.state}")
                if feat.completion_evidence:
                    print(f"Receipt: command='{feat.completion_evidence.executed_command}', exit_code=0, output_hash={feat.completion_evidence.output_sha256[:12]}...")
            return 0
        except (VerificationFailedError, KeyError, Exception) as exc:
            if args.json:
                print(json.dumps({"error": str(exc)}, ensure_ascii=False))
            else:
                print(f"Verification failed: {exc}")
            return 1

    # ----------------------- HARNESS DOCTOR -----------------------
    if args.doctor or args.doctor_fix:
        from scripts.harness_doctor import HarnessDoctor
        doctor = HarnessDoctor(
            repo_root=Path(__file__).resolve().parent,
            auto_fix=args.doctor_fix,
        )
        report = doctor.run()
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(doctor.format_report(report))
        unresolved_errors = [i for i in report.issues if i.severity == "ERROR" and not i.fixed]
        return 0 if len(unresolved_errors) == 0 else 1

    if args.workflow and args.marketing_workflow:
        parser.error("Choose only one checkpoint workflow")
    if args.workflow or args.marketing_workflow:
        try:
            state = marketing_workflow_action(args) if args.marketing_workflow else workflow_action(args)
        except (WorkflowError, OSError, ValueError, TypeError) as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False) if args.json else f"Workflow error: {exc}")
            return 1
        print(json.dumps(state, ensure_ascii=False, indent=2) if args.json else
              f"Task {state['task_id']}: {state['stage']}; next_agent={state['next_agent']}; revision={state['revision']}")
        return 0
    orchestrator = ChiefOrchestrator()

    # ----------------------- DISTILL TASK -----------------------
    if args.distill:
        distilled = orchestrator.skill_distiller.distill_task(args.distill, stage_immediately=True)
        if not distilled:
            print(f"Không tìm thấy trajectory cho task_id '{args.distill}'")
            return 1
        if args.json:
            print(json.dumps(distilled, ensure_ascii=False, indent=2))
        else:
            print(f"Đã chưng cất thành công kỹ năng '{distilled['name']}' từ task {args.distill}!")
            if "stage_record" in distilled:
                print(f"Staged ID: {distilled['stage_record']['id']} (Status: PENDING)")
            print("\n--- NỘI DUNG SKILL.MD ---")
            print(distilled["content"])
        return 0

    # ----------------------- CURATE -----------------------
    if args.curate:
        report = orchestrator.skill_curator.evaluate_lifecycle()
        proposals = orchestrator.skill_curator.find_consolidation_candidates()
        if args.json:
            print(json.dumps({
                "lifecycle": report,
                "consolidation_proposals": proposals,
            }, ensure_ascii=False, indent=2))
        else:
            print("=== BÁO CÁO VÒNG ĐỜI KỸ NĂNG (CURATOR) ===")
            print(f"Tổng số kỹ năng: {report['total_skills']}")
            print(f"- Active (<= 14 ngày): {len(report['active'])}")
            print(f"- Stale (14 - 30 ngày): {len(report['stale'])}")
            print(f"- Ứng viên Archive (> 30 ngày): {len(report['archive_candidates'])}")
            if report['archive_candidates']:
                print("  Các kỹ năng đề xuất lưu trữ:")
                for c in report['archive_candidates']:
                    print(f"  * {c['name']} (không dùng {c['days_idle']} ngày)")

            if proposals:
                print("\n=== ĐỀ XUẤT HỢP NHẤT KỸ NĂNG TRÙNG LẶP ===")
                for p in proposals:
                    print(f"- [{p['skill_a']}] <-> [{p['skill_b']}]: Tương đồng {round(p['similarity']*100, 1)}%")
                    print(f"  Lý do: {p['reason']}")
                    print(f"  Khuyến nghị: {p['recommendation']}")
            else:
                print("\nKhông phát hiện kỹ năng nào trùng lặp vượt ngưỡng.")
        return 0

    # ----------------------- STAGED SKILLS -----------------------
    if args.skills_pending:
        pending = orchestrator.skill_manager.get_staged_skills("PENDING")
        if args.json:
            print(json.dumps(pending, ensure_ascii=False, indent=2))
        else:
            print(f"=== HÀNG ĐỢI SKILLS CHỜ DUYỆT ({len(pending)}) ===")
            for item in pending:
                print(f"- ID: {item['id']} | Tên: {item['name']} | Phân nhánh: {item.get('branch', 'app')}")
                print(f"  Tạo lúc: {item.get('created_at')}")
            if not pending:
                print("Không có kỹ năng nào đang chờ duyệt.")
        return 0

    if args.skills_approve:
        try:
            approved = orchestrator.skill_manager.approve_staged_skill(args.skills_approve)
            if args.json:
                print(json.dumps(approved, ensure_ascii=False, indent=2))
            else:
                print(f"Đã duyệt và kích hoạt thành công kỹ năng '{approved['name']}' (ID: {args.skills_approve})!")
            return 0
        except Exception as e:
            print(f"Lỗi khi duyệt skill: {str(e)}")
            return 1

    if args.skills_reject:
        try:
            rejected = orchestrator.skill_manager.reject_staged_skill(args.skills_reject, reason="Từ chối qua CLI")
            if args.json:
                print(json.dumps(rejected, ensure_ascii=False, indent=2))
            else:
                print(f"Đã từ chối kỹ năng ID '{args.skills_reject}'.")
            return 0
        except Exception as e:
            print(f"Lỗi khi từ chối skill: {str(e)}")
            return 1

    # ----------------------- TASK PROCESSING -----------------------
    if not args.task:
        parser.print_help()
        return 1

    context, verdict = orchestrator.process_task(
        task_description=args.task,
        branch=args.branch,
        mock_checker_output=args.checker_output,
        task_id=args.task_id,
        review_rounds=max(1, args.review_rounds),
        auto_distill=args.auto_distill,
    )
    verdict_str = verdict.value if hasattr(verdict, "value") else str(verdict)

    if args.dump_skill:
        print(context.skill_instructions or "(không có skill nào được nạp)")

    if args.json:
        print(json.dumps({
            "task_id": context.task_id,
            "branch": context.branch,
            "state": context.state.name,
            "verdict": verdict_str,
            "critique_rounds": context.critique_rounds,
            "active_skill": context.active_skill,
            "skill_path": context.skill_path,
            "execution_mode": "simulation",
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Simulation finished (no agents executed). Status: {context.state}, Verdict: {verdict_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
