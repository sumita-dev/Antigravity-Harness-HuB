#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plugins/code/skills/database-migrations/scripts/lint_migration_safety.py

Scaffolding Script Kiểm Định An Toàn Migration Cơ Sở Dữ Liệu (Dune Invariant).
Phân tích tĩnh các tệp migration (.sql, .py/Alembic) để phát hiện vi phạm:
1. Lệnh phá hủy dữ liệu: DROP TABLE, DROP COLUMN, TRUNCATE.
2. Thiếu hàm rollback/downgrade hoặc downgrade rỗng (chỉ pass/NotImplementedError).
3. Thêm cột NOT NULL trên bảng hiện có mà thiếu giá trị DEFAULT.

CLI:
  python lint_migration_safety.py [FILES...] [--dir PATH] [--json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class MigrationViolation:
    file_path: str
    line_number: int
    rule_code: str
    severity: str  # "ERROR" hoặc "WARN"
    message: str
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Biểu thức chính quy cho SQL
RE_DROP_TABLE = re.compile(r"(?i)\bDROP\s+TABLE\b(?:\s+IF\s+EXISTS)?\s+([a-zA-Z0-9_.\"\`]+)")
RE_DROP_COLUMN = re.compile(r"(?i)\b(?:ALTER\s+TABLE\s+[a-zA-Z0-9_.\"\`]+\s+)?DROP\s+COLUMN\b\s+([a-zA-Z0-9_.\"\`]+)")
RE_TRUNCATE = re.compile(r"(?i)\bTRUNCATE(?:\s+TABLE)?\b\s+([a-zA-Z0-9_.\"\`]+)")
RE_ADD_COLUMN = re.compile(r"(?i)\bADD\s+(?:COLUMN\s+)?([a-zA-Z0-9_.\"\`]+)\s+([^;]+)")
RE_NOT_NULL = re.compile(r"(?i)\bNOT\s+NULL\b")
RE_DEFAULT = re.compile(r"(?i)\bDEFAULT\b")


def lint_sql_content(content: str, filename: str = "migration.sql") -> List[MigrationViolation]:
    """Phân tích nội dung file SQL migration."""
    violations: List[MigrationViolation] = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, 1):
        clean_line = line.strip()
        if clean_line.startswith("--") or clean_line.startswith("/*"):
            continue

        # 1. Phát hiện DROP TABLE
        m = RE_DROP_TABLE.search(line)
        if m:
            table_name = m.group(1)
            violations.append(
                MigrationViolation(
                    file_path=filename,
                    line_number=idx,
                    rule_code="ERR_DROP_TABLE",
                    severity="ERROR",
                    message=f"Phát hiện lệnh DROP TABLE nguy hiểm đối với bảng '{table_name}'. Cần thay bằng forward-only deprecation.",
                    snippet=clean_line,
                )
            )

        # 2. Phát hiện DROP COLUMN
        m = RE_DROP_COLUMN.search(line)
        if m:
            col_name = m.group(1)
            violations.append(
                MigrationViolation(
                    file_path=filename,
                    line_number=idx,
                    rule_code="ERR_DROP_COLUMN",
                    severity="ERROR",
                    message=f"Phát hiện lệnh DROP COLUMN nguy hiểm đối với cột '{col_name}'. Có thể gây mất dữ liệu và gãy zero-downtime.",
                    snippet=clean_line,
                )
            )

        # 3. Phát hiện TRUNCATE
        m = RE_TRUNCATE.search(line)
        if m:
            table_name = m.group(1)
            violations.append(
                MigrationViolation(
                    file_path=filename,
                    line_number=idx,
                    rule_code="ERR_TRUNCATE_TABLE",
                    severity="ERROR",
                    message=f"Phát hiện lệnh TRUNCATE TABLE làm trắng dữ liệu bảng '{table_name}'.",
                    snippet=clean_line,
                )
            )

        # 4. Phát hiện ADD COLUMN NOT NULL thiếu DEFAULT
        m_add = RE_ADD_COLUMN.search(line)
        if m_add:
            col_name = m_add.group(1)
            rest_of_clause = m_add.group(2)
            if RE_NOT_NULL.search(rest_of_clause) and not RE_DEFAULT.search(rest_of_clause):
                violations.append(
                    MigrationViolation(
                        file_path=filename,
                        line_number=idx,
                        rule_code="ERR_NOT_NULL_WITHOUT_DEFAULT",
                        severity="ERROR",
                        message=f"Thêm cột '{col_name}' có thuộc tính NOT NULL nhưng thiếu DEFAULT clause trên bảng đang hoạt động.",
                        snippet=clean_line,
                    )
                )

    return violations


class PythonMigrationVisitor(ast.NodeVisitor):
    """AST Visitor phân tích migration Python / Alembic."""

    def __init__(self, filename: str, content: str):
        self.filename = filename
        self.lines = content.splitlines()
        self.violations: List[MigrationViolation] = []
        self.has_upgrade = False
        self.has_downgrade = False
        self.downgrade_body_nodes: List[ast.stmt] = []
        self.downgrade_lineno = 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "upgrade":
            self.has_upgrade = True
        elif node.name == "downgrade":
            self.has_downgrade = True
            self.downgrade_body_nodes = node.body
            self.downgrade_lineno = node.lineno

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        lineno = getattr(node, "lineno", 1)
        snippet = self.lines[lineno - 1].strip() if 0 < lineno <= len(self.lines) else ""

        # Kiểm tra op.drop_table
        if func_name == "drop_table":
            self.violations.append(
                MigrationViolation(
                    file_path=self.filename,
                    line_number=lineno,
                    rule_code="ERR_DROP_TABLE",
                    severity="ERROR",
                    message="Phát hiện op.drop_table() trong migration Python.",
                    snippet=snippet,
                )
            )

        # Kiểm tra op.drop_column
        elif func_name == "drop_column":
            self.violations.append(
                MigrationViolation(
                    file_path=self.filename,
                    line_number=lineno,
                    rule_code="ERR_DROP_COLUMN",
                    severity="ERROR",
                    message="Phát hiện op.drop_column() trong migration Python.",
                    snippet=snippet,
                )
            )

        # Kiểm tra op.add_column với nullable=False thiếu server_default
        elif func_name == "add_column":
            is_not_null = False
            has_default = False
            for kw in node.keywords:
                if kw.arg == "nullable" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    is_not_null = True
                if kw.arg in ("server_default", "default"):
                    has_default = True

            # Kiểm tra trong các arguments con (sa.Column)
            for arg in node.args:
                if isinstance(arg, ast.Call):
                    for kw in arg.keywords:
                        if kw.arg == "nullable" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                            is_not_null = True
                        if kw.arg in ("server_default", "default"):
                            has_default = True

            if is_not_null and not has_default:
                self.violations.append(
                    MigrationViolation(
                        file_path=self.filename,
                        line_number=lineno,
                        rule_code="ERR_NOT_NULL_WITHOUT_DEFAULT",
                        severity="ERROR",
                        message="op.add_column() thiết lập nullable=False nhưng thiếu server_default.",
                        snippet=snippet,
                    )
                )

        # Kiểm tra op.execute với raw SQL nguy hiểm
        elif func_name == "execute":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                sql_text = node.args[0].value
                sql_violations = lint_sql_content(sql_text, filename=self.filename)
                for v in sql_violations:
                    v.line_number = lineno
                    self.violations.append(v)

        self.generic_visit(node)


def lint_python_migration_content(content: str, filename: str = "migration.py") -> List[MigrationViolation]:
    """Phân tích AST file Python / Alembic migration."""
    violations: List[MigrationViolation] = []
    try:
        tree = ast.parse(content, filename=filename)
    except SyntaxError as e:
        return [
            MigrationViolation(
                file_path=filename,
                line_number=e.lineno or 1,
                rule_code="ERR_MIGRATION_SYNTAX",
                severity="ERROR",
                message=f"Lỗi cú pháp Python trong migration: {e}",
            )
        ]

    visitor = PythonMigrationVisitor(filename, content)
    visitor.visit(tree)
    violations.extend(visitor.violations)

    # Kiểm tra hàm downgrade trong migration file Alembic
    if visitor.has_upgrade:
        if not visitor.has_downgrade:
            violations.append(
                MigrationViolation(
                    file_path=filename,
                    line_number=1,
                    rule_code="ERR_MISSING_DOWNGRADE",
                    severity="ERROR",
                    message="Thiếu hàm downgrade() trong file migration. Mọi migration bắt buộc phải có phương án rollback.",
                )
            )
        else:
            # Kiểm tra xem hàm downgrade có rỗng không
            is_empty_or_noop = True
            for stmt in visitor.downgrade_body_nodes:
                if isinstance(stmt, ast.Pass):
                    continue
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    # Docstring
                    continue
                if isinstance(stmt, ast.Raise):
                    # raise NotImplementedError
                    continue
                is_empty_or_noop = False
                break

            if is_empty_or_noop:
                violations.append(
                    MigrationViolation(
                        file_path=filename,
                        line_number=visitor.downgrade_lineno,
                        rule_code="ERR_EMPTY_DOWNGRADE",
                        severity="ERROR",
                        message="Hàm downgrade() rỗng hoặc chỉ chứa 'pass' / 'raise NotImplementedError'. Bắt buộc triển khai logic rollback.",
                    )
                )

    return violations


def lint_migration_file(path: Path) -> List[MigrationViolation]:
    """Kiểm tra một file migration cụ thể (.sql hoặc .py)."""
    if not path.is_file():
        return []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [
            MigrationViolation(
                file_path=str(path),
                line_number=1,
                rule_code="ERR_READ_FILE",
                severity="ERROR",
                message=f"Không thể đọc file migration: {exc}",
            )
        ]

    suffix = path.suffix.lower()
    if suffix == ".sql":
        return lint_sql_content(content, filename=str(path))
    elif suffix == ".py":
        return lint_python_migration_content(content, filename=str(path))

    return []


def lint_migrations(paths: Sequence[Path]) -> Dict[str, Any]:
    """Kiểm tra danh sách các file hoặc thư mục migration."""
    all_violations: List[MigrationViolation] = []
    files_checked = 0

    for p in paths:
        if p.is_file():
            violations = lint_migration_file(p)
            all_violations.extend(violations)
            files_checked += 1
        elif p.is_dir():
            for f in sorted(list(p.rglob("*.sql")) + list(p.rglob("*.py"))):
                violations = lint_migration_file(f)
                all_violations.extend(violations)
                files_checked += 1

    return {
        "files_checked": files_checked,
        "violation_count": len(all_violations),
        "is_safe": len(all_violations) == 0,
        "violations": [v.to_dict() for v in all_violations],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Database Migration Safety Linter")
    parser.add_argument("files", nargs="*", help="Danh sách file migration cần kiểm tra")
    parser.add_argument("--dir", type=str, default=None, help="Thư mục chứa các tệp migration")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON")

    args = parser.parse_args()

    target_paths: List[Path] = []
    if args.dir:
        target_paths.append(Path(args.dir).resolve())
    for f in args.files:
        target_paths.append(Path(f).resolve())

    if not target_paths:
        # Nếu không truyền đường dẫn, tìm kiếm trong thư mục migrations chuẩn nếu có
        default_dir = REPO_ROOT / "migrations"
        if default_dir.is_dir():
            target_paths.append(default_dir)
        else:
            print("Không có tệp hoặc thư mục migration nào được chỉ định để kiểm tra.")
            return 0

    result = lint_migrations(target_paths)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 65)
        print("ANTIGRAVITY DATABASE MIGRATION SAFETY LINTER")
        print("=" * 65)
        print(f"- Số file đã kiểm tra: {result['files_checked']}")
        print(f"- Trạng thái: {'🟢 AN TOÀN (SAFE)' if result['is_safe'] else '🔴 NGUY HIỂM (UNSAFE)'}")
        print(f"- Số vi phạm: {result['violation_count']}")

        for v in result["violations"]:
            print(f"\n  ⚠️  [{v['rule_code']}] {v['file_path']}:{v['line_number']}")
            print(f"     Thông điệp: {v['message']}")
            if v["snippet"]:
                print(f"     Mã vi phạm: {v['snippet']}")
        print("=" * 65)

    return 0 if result["is_safe"] else 1


if __name__ == "__main__":
    sys.exit(main())
