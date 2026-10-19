"""Mutation Testing Gate - Pillar 3 of Antigravity Harness Hub.
Cung cấp khả năng sinh đột biến (mutation generation) và kiểm định tính chí mạng
(lethality verification) của test suite bằng 100% Python standard library.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, List, Optional, Tuple


@dataclass
class Mutant:
    mutant_id: str
    line_no: int
    original_token: str
    mutated_token: str
    original_line: str
    mutated_line: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MutationReport:
    total_mutants: int
    killed: int
    survived: int
    score: float
    is_lethal: bool
    details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Mapping các toán tử so sánh AST
CMP_OP_MUTATIONS: dict[type, type] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}

TOKEN_REPRESENTATIONS: dict[type, str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.GtE: ">=",
    ast.Gt: ">",
    ast.LtE: "<=",
    ast.In: "in",
    ast.NotIn: "not in",
}


class _MutationCandidateCollector(ast.NodeVisitor):
    """Thu thập các vị trí có thể đột biến trong AST."""

    def __init__(self, source_lines: list[str]) -> None:
        self.source_lines = source_lines
        self.candidates: list[dict[str, Any]] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        # Xét từng toán tử so sánh
        for idx, op in enumerate(node.ops):
            op_type = type(op)
            if op_type in CMP_OP_MUTATIONS:
                target_op = CMP_OP_MUTATIONS[op_type]
                line_no = getattr(node, "lineno", 1)
                orig_token = TOKEN_REPRESENTATIONS.get(op_type, str(op_type))
                mut_token = TOKEN_REPRESENTATIONS.get(target_op, str(target_op))
                self.candidates.append({
                    "type": "compare",
                    "node": node,
                    "op_index": idx,
                    "target_op": target_op,
                    "line_no": line_no,
                    "orig_token": orig_token,
                    "mut_token": mut_token,
                })
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        line_no = getattr(node, "lineno", 1)
        # Boolean mutation: True <-> False
        if isinstance(node.value, bool):
            orig_token = str(node.value)
            mut_token = str(not node.value)
            self.candidates.append({
                "type": "bool",
                "node": node,
                "new_value": not node.value,
                "line_no": line_no,
                "orig_token": orig_token,
                "mut_token": mut_token,
            })
        # Numeric offset mutation: N -> N + 1 (cho int và float, loại trừ bool vì bool là subclass của int)
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            orig_token = str(node.value)
            new_val = node.value + 1
            mut_token = str(new_val)
            self.candidates.append({
                "type": "number",
                "node": node,
                "new_value": new_val,
                "line_no": line_no,
                "orig_token": orig_token,
                "mut_token": mut_token,
            })
        self.generic_visit(node)


def generate_mutants(source_code: str, max_mutants: int = 5) -> list[tuple[str, Mutant]]:
    """Phân tích AST và sinh ra danh sách code đột biến cùng thông tin Mutant.

    Mỗi mutant là một biến thể độc lập có 1 đột biến duy nhất so với code gốc.
    """
    if not source_code.strip():
        return []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    source_lines = source_code.splitlines()
    collector = _MutationCandidateCollector(source_lines)
    collector.visit(tree)

    results: list[tuple[str, Mutant]] = []

    for idx, candidate in enumerate(collector.candidates[:max_mutants]):
        # Tạo deep copy AST hoặc parse lại rồi mutate trên node tương ứng
        mutated_tree = ast.parse(source_code)
        target_line = candidate["line_no"]
        mut_type = candidate["type"]

        # Tìm và đột biến node đích trên mutated_tree
        class _SingleNodeMutator(ast.NodeTransformer):
            def __init__(self) -> None:
                self.applied = False

            def visit_Compare(self, node: ast.Compare) -> ast.AST:
                if (
                    not self.applied
                    and mut_type == "compare"
                    and getattr(node, "lineno", None) == target_line
                ):
                    op_idx = candidate["op_index"]
                    if op_idx < len(node.ops):
                        current_op = type(node.ops[op_idx])
                        if current_op in CMP_OP_MUTATIONS:
                            new_op_cls = candidate["target_op"]
                            node.ops[op_idx] = new_op_cls()
                            self.applied = True
                return self.generic_visit(node)

            def visit_Constant(self, node: ast.Constant) -> ast.AST:
                if (
                    not self.applied
                    and mut_type in ("bool", "number")
                    and getattr(node, "lineno", None) == target_line
                ):
                    if mut_type == "bool" and isinstance(node.value, bool):
                        if str(node.value) == candidate["orig_token"]:
                            node.value = candidate["new_value"]
                            self.applied = True
                    elif mut_type == "number" and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                        if str(node.value) == candidate["orig_token"]:
                            node.value = candidate["new_value"]
                            self.applied = True
                return self.generic_visit(node)

        mutator = _SingleNodeMutator()
        mutated_tree = mutator.visit(mutated_tree)
        ast.fix_missing_locations(mutated_tree)

        try:
            mutated_code = ast.unparse(mutated_tree)
        except Exception:
            continue

        orig_line_str = (
            source_lines[target_line - 1]
            if 0 <= target_line - 1 < len(source_lines)
            else ""
        )
        mutated_lines = mutated_code.splitlines()
        mut_line_str = (
            mutated_lines[target_line - 1]
            if 0 <= target_line - 1 < len(mutated_lines)
            else ""
        )

        mutant_obj = Mutant(
            mutant_id=f"mutant_{idx + 1:03d}",
            line_no=target_line,
            original_token=candidate["orig_token"],
            mutated_token=candidate["mut_token"],
            original_line=orig_line_str.strip(),
            mutated_line=mut_line_str.strip(),
        )
        results.append((mutated_code, mutant_obj))

    return results


def verify_test_lethality(
    source_file: str,
    test_command: str,
    max_mutants: int = 3,
    timeout: int = 30,
) -> MutationReport:
    """Kiểm tra tính chí mạng của bộ test đối với file nguồn chỉ định.

    - Đọc file mã nguồn gốc.
    - Sinh tối đa `max_mutants` đột biến.
    - Thay thế tạm thời file nguồn bằng code đột biến, thực thi `test_command`.
    - Nếu test FAIL (exit code != 0): Mutant bị KILLED (test bắt được lỗi -> tốt).
    - Nếu test PASS (exit code == 0): Mutant SURVIVED (test lỏng lẻo -> cảnh báo).
    - Khôi phục 100% file gốc sau mỗi lần thử nghiệm.
    """
    path = Path(source_file).resolve()
    if not path.is_file():
        return MutationReport(
            total_mutants=0,
            killed=0,
            survived=0,
            score=0.0,
            is_lethal=False,
            details=[{"error": f"File not found: {source_file}"}],
        )

    original_code = path.read_text(encoding="utf-8")
    mutants = generate_mutants(original_code, max_mutants=max_mutants)

    if not mutants:
        return MutationReport(
            total_mutants=0,
            killed=0,
            survived=0,
            score=1.0,
            is_lethal=True,
            details=[],
        )

    killed = 0
    survived = 0
    details: list[dict[str, Any]] = []

    try:
        for mutated_code, mutant in mutants:
            # Ghi mã đột biến vào file nguồn
            path.write_text(mutated_code, encoding="utf-8")

            try:
                proc = subprocess.run(
                    test_command,
                    shell=True,
                    cwd=str(path.parent),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                test_exit_code = proc.returncode
                stdout_snippet = (proc.stdout or "")[-300:]
                stderr_snippet = (proc.stderr or "")[-300:]
            except subprocess.TimeoutExpired:
                # Timeout cũng được xem là mutant bị killed (vd lặp vô hạn)
                test_exit_code = -1
                stdout_snippet = ""
                stderr_snippet = "Test execution timed out."
            except Exception as exc:
                test_exit_code = -2
                stdout_snippet = ""
                stderr_snippet = str(exc)

            # Nếu test thất bại (khác 0) -> mutant bị KILLED
            is_killed = test_exit_code != 0
            if is_killed:
                killed += 1
                status = "KILLED"
            else:
                survived += 1
                status = "SURVIVED"

            details.append({
                "mutant": mutant.to_dict(),
                "status": status,
                "exit_code": test_exit_code,
                "output_snippet": stderr_snippet or stdout_snippet,
            })
    finally:
        # Luôn phục hồi mã nguồn gốc tuyệt đối
        path.write_text(original_code, encoding="utf-8")

    total = killed + survived
    score = (killed / total) if total > 0 else 1.0
    is_lethal = survived == 0

    return MutationReport(
        total_mutants=total,
        killed=killed,
        survived=survived,
        score=score,
        is_lethal=is_lethal,
        details=details,
    )
