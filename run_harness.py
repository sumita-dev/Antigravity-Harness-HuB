"""CLI của Antigravity Harness (mô phỏng state machine).

Ví dụ:
    python run_harness.py --task "Soạn kịch bản TikTok" --branch marketing
    python run_harness.py --task "Build login" --branch app --review-rounds 3 \
        --checker-output "VERDICT: REJECT"      # kiểm chứng circuit breaker
    python run_harness.py --task "viết content" --dump-skill
"""

import argparse
import json

from harness.orchestrator import ChiefOrchestrator


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity Harness CLI")
    parser.add_argument("--task", required=True, help="Mô tả nhiệm vụ")
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
    args = parser.parse_args(argv)

    orchestrator = ChiefOrchestrator()
    context, verdict = orchestrator.process_task(
        task_description=args.task,
        branch=args.branch,
        mock_checker_output=args.checker_output,
        task_id=args.task_id,
        review_rounds=max(1, args.review_rounds),
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
