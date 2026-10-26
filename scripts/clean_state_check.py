"""CLI Runner cho Clean State Protocol & Verifier (Harness 2.0).

Chạy độc lập kiểm toán 5 chiều chất lượng của dự án.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Đảm bảo mã hóa UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from harness.validators.clean_state_verifier import (
    CleanStateVerifier,
    DimensionStatus,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Clean State Protocol Verifier (5-D Clock-Out)")
    parser.add_argument("--project-root", default=".", help="Đường dẫn thư mục dự án cần kiểm toán")
    parser.add_argument("--strict", action="store_true", help="Dừng ngay khi 1 chiều kiểm toán bị FAIL")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON")
    parser.add_argument("--output", "-o", default=None, help="Đường dẫn lưu file JSON báo cáo")
    parser.add_argument("--boot-cmd", default=None, help="Lệnh khởi động tùy chỉnh cho chiều D5")
    parser.add_argument("--test-cmd", default=None, help="Lệnh test tùy chỉnh cho chiều D2")
    parser.add_argument("--feature-list", default=None, help="Đường dẫn cụ thể tới feature_list.json")
    parser.add_argument("--fast", action="store_true", help="Chế độ kiểm tra nhanh (fast mode)")

    args = parser.parse_args(argv)

    config = {}
    if args.fast:
        config["fast_mode"] = True
    if args.boot_cmd:
        config["boot_command"] = args.boot_cmd
    if args.test_cmd:
        config["test_command"] = args.test_cmd
    if args.feature_list:
        config["feature_list_path"] = args.feature_list

    verifier = CleanStateVerifier(project_root=args.project_root, config=config)
    report = verifier.audit(strict=args.strict)

    report_dict = report.to_dict()

    if args.output:
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report_dict, ensure_ascii=False, indent=2))
    else:
        print(report.summary())

    return 0 if report.overall_status == DimensionStatus.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
