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
"""

import argparse
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from harness.orchestrator import ChiefOrchestrator


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity Harness CLI")
    parser.add_argument("--task", default=None, help="Mô tả nhiệm vụ")
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

    args = parser.parse_args(argv)
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
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Task processing finished. Status: {context.state}, Verdict: {verdict_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
