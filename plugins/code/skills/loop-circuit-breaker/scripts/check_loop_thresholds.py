#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plugins/code/skills/loop-circuit-breaker/scripts/check_loop_thresholds.py

Scaffolding Script Kiểm Định Ngưỡng Vòng Lặp & Ngắt Mạch AST (Dune Invariant).
Phân tích AST Python để phát hiện:
1. Vòng lặp while True thiếu điều kiện thoát (break/return/raise) hoặc thiếu timeout timer.
2. Hàm đệ quy gọi lại chính nó mà thiếu điều kiện dừng cơ sở (base case).
3. Vòng lặp retry không giới hạn số lần lặp tối đa.

CLI:
  python check_loop_thresholds.py [FILES...] [--dir PATH] [--json]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class LoopFinding:
    file_path: str
    line_number: int
    rule_code: str
    severity: str  # "ERROR" hoặc "WARN"
    message: str
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_truthy_constant(node: ast.expr) -> bool:
    """Kiểm tra xem biểu thức điều kiện có phải là hằng số luôn Đúng không."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.NameConstant):  # Python < 3.8 compat
        return bool(node.value)
    return False


class LoopASTVisitor(ast.NodeVisitor):
    """AST Visitor quét các vòng lặp và đệ quy nguy hiểm."""

    def __init__(self, filename: str, content: str):
        self.filename = filename
        self.lines = content.splitlines()
        self.findings: List[LoopFinding] = []
        self.current_function: Optional[str] = None
        self.function_has_if: bool = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        old_func = self.current_function
        self.current_function = node.name

        # Kiểm tra đệ quy trong thân hàm
        self._check_recursion(node)

        self.generic_visit(node)
        self.current_function = old_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        old_func = self.current_function
        self.current_function = node.name

        self._check_recursion(node)

        self.generic_visit(node)
        self.current_function = old_func

    def _check_recursion(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Kiểm tra xem hàm có đệ quy không và đệ quy có được bảo vệ bởi base case không."""
        func_name = func_node.name
        recursive_calls: List[ast.Call] = []
        has_conditional_guard = False

        for n in ast.walk(func_node):
            if isinstance(n, (ast.If, ast.IfExp)):
                has_conditional_guard = True
            elif isinstance(n, ast.Call):
                # Gọi hàm cùng tên
                if isinstance(n.func, ast.Name) and n.func.id == func_name:
                    recursive_calls.append(n)
                elif isinstance(n.func, ast.Attribute) and n.func.attr == func_name:
                    recursive_calls.append(n)

        if recursive_calls and not has_conditional_guard:
            lineno = recursive_calls[0].lineno
            snippet = self.lines[lineno - 1].strip() if 0 < lineno <= len(self.lines) else ""
            self.findings.append(
                LoopFinding(
                    file_path=self.filename,
                    line_number=lineno,
                    rule_code="ERR_UNGUARDED_RECURSION",
                    severity="ERROR",
                    message=f"Hàm '{func_name}' gọi đệ quy nhưng không có bất kỳ cấu trúc rẽ nhánh 'if' nào làm base case.",
                    snippet=snippet,
                )
            )

    def visit_While(self, node: ast.While) -> None:
        lineno = node.lineno
        snippet = self.lines[lineno - 1].strip() if 0 < lineno <= len(self.lines) else ""

        is_while_true = is_truthy_constant(node.test)

        # Quét thân vòng lặp tìm điểm thoát
        has_break = False
        has_return = False
        has_raise = False
        has_timeout_check = False

        timeout_keywords = {"timeout", "deadman", "timer", "schedule", "deadline", "max_retries", "max_rounds", "time.time"}

        for child in ast.walk(node):
            if isinstance(child, ast.Break):
                has_break = True
            elif isinstance(child, ast.Return):
                has_return = True
            elif isinstance(child, ast.Raise):
                has_raise = True
            elif isinstance(child, ast.Name):
                if child.id.lower() in timeout_keywords:
                    has_timeout_check = True
            elif isinstance(child, ast.Attribute):
                if child.attr.lower() in timeout_keywords:
                    has_timeout_check = True

        has_termination = has_break or has_return or has_raise

        if is_while_true:
            if not has_termination and not has_timeout_check:
                self.findings.append(
                    LoopFinding(
                        file_path=self.filename,
                        line_number=lineno,
                        rule_code="ERR_UNBOUNDED_WHILE_LOOP",
                        severity="ERROR",
                        message="Phát hiện vòng lặp while True không có bất kỳ lệnh break, return, raise hay timeout timer nào.",
                        snippet=snippet,
                    )
                )
            elif not has_timeout_check:
                # Có break/return nhưng không có timeout timer bảo vệ
                self.findings.append(
                    LoopFinding(
                        file_path=self.filename,
                        line_number=lineno,
                        rule_code="WARN_MISSING_TIMEOUT_TIMER",
                        severity="WARN",
                        message="Vòng lặp while True có lệnh thoát nhưng thiếu Dead-man's Switch / timeout timer phòng ngừa treo vĩnh viễn.",
                        snippet=snippet,
                    )
                )

        self.generic_visit(node)


def check_loop_content(content: str, filename: str = "module.py") -> List[LoopFinding]:
    """Phân tích AST một chuỗi mã nguồn Python."""
    try:
        tree = ast.parse(content, filename=filename)
    except SyntaxError as e:
        return [
            LoopFinding(
                file_path=filename,
                line_number=e.lineno or 1,
                rule_code="ERR_SYNTAX_ERROR",
                severity="ERROR",
                message=f"Lỗi cú pháp Python: {e}",
            )
        ]

    visitor = LoopASTVisitor(filename, content)
    visitor.visit(tree)
    return visitor.findings


def check_loop_file(path: Path) -> List[LoopFinding]:
    """Phân tích một file Python cụ thể."""
    if not path.is_file():
        return []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [
            LoopFinding(
                file_path=str(path),
                line_number=1,
                rule_code="ERR_READ_FILE",
                severity="ERROR",
                message=f"Không thể đọc file: {exc}",
            )
        ]

    return check_loop_content(content, filename=str(path))


def check_loops(paths: Sequence[Path]) -> Dict[str, Any]:
    """Kiểm tra danh sách các file hoặc thư mục Python."""
    all_findings: List[LoopFinding] = []
    files_checked = 0

    for p in paths:
        if p.is_file() and p.suffix.lower() == ".py":
            findings = check_loop_file(p)
            all_findings.extend(findings)
            files_checked += 1
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                findings = check_loop_file(f)
                all_findings.extend(findings)
                files_checked += 1

    unresolved_errors = [f for f in all_findings if f.severity == "ERROR"]

    return {
        "files_checked": files_checked,
        "finding_count": len(all_findings),
        "errors": len(unresolved_errors),
        "warnings": len(all_findings) - len(unresolved_errors),
        "is_safe": len(unresolved_errors) == 0,
        "findings": [f.to_dict() for f in all_findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Loop Threshold & Circuit Breaker Checker")
    parser.add_argument("files", nargs="*", help="Danh sách file Python cần phân tích")
    parser.add_argument("--dir", type=str, default=None, help="Thư mục chứa mã nguồn Python")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON")

    args = parser.parse_args()

    target_paths: List[Path] = []
    if args.dir:
        target_paths.append(Path(args.dir).resolve())
    for f in args.files:
        target_paths.append(Path(f).resolve())

    if not target_paths:
        print("Không có tệp hoặc thư mục Python nào được chỉ định để kiểm tra.")
        return 0

    result = check_loops(target_paths)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print("ANTIGRAVITY LOOP THRESHOLD & CIRCUIT BREAKER CHECKER")
        print("=" * 65)
        print(f"- Số file đã kiểm tra: {result['files_checked']}")
        print(f"- Trạng thái: {'🟢 AN TOÀN (SAFE)' if result['is_safe'] else '🔴 VI PHẠM VÒNG LẶP (UNBOUNDED)'}")
        print(f"- Tổng số phát hiện: {result['finding_count']} (Lỗi: {result['errors']}, Cảnh báo: {result['warnings']})")

        for f in result["findings"]:
            icon = "🔴" if f["severity"] == "ERROR" else "🟡"
            print(f"\n  {icon} [{f['rule_code']}] {f['file_path']}:{f['line_number']}")
            print(f"     Thông điệp: {f['message']}")
            if f["snippet"]:
                print(f"     Mã nguồn: {f['snippet']}")
        print("=" * 65)

    return 0 if result["is_safe"] else 1


if __name__ == "__main__":
    sys.exit(main())
