#!/usr/bin/env python3
"""AST-based linter for over-engineering, dead abstractions, and single-impl interfaces.

Dune Invariant (Điều 3): Enforce architectural minimalism via deterministic static analysis.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _is_empty_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return stmt.value.value is ...
    return False


class OverengineeringVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[dict] = []
        self.defined_classes: Dict[str, Tuple[int, List[str]]] = {}
        self.abc_classes: Set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)

        self.defined_classes[node.name] = (node.lineno, base_names)
        if "ABC" in base_names or any("abstract" in b.lower() for b in base_names):
            self.abc_classes.add(node.name)

        # Check for empty class (only docstring, pass, or ...)
        body = [stmt for stmt in node.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))]
        if not body or all(_is_empty_stmt(stmt) for stmt in body):
            # If not an exception
            if not any("Error" in b or "Exception" in b for b in base_names):
                self.violations.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "empty_class",
                    "message": f"Class '{node.name}' has no logic or implementation methods (potential empty abstraction).",
                })

        # Check for single-method or wrapper classes with only __init__
        non_init_methods = [
            stmt for stmt in node.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name != "__init__"
        ]
        if len(node.body) > 0 and len(non_init_methods) == 0 and not any("Error" in b or "Exception" in b for b in base_names):
            if "ABC" not in base_names and len(body) > 0:
                self.violations.append({
                    "file": self.filename,
                    "line": node.lineno,
                    "type": "data_only_class",
                    "message": f"Class '{node.name}' contains only __init__ without behavioral methods. Consider using a dataclass, namedtuple, or dict.",
                })

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Ignore dunder methods
        if node.name.startswith("__") and node.name.endswith("__"):
            return

        # Check for empty function (without abstract decorator)
        is_abstract = any(
            (isinstance(d, ast.Name) and "abstract" in d.id) or
            (isinstance(d, ast.Attribute) and "abstract" in d.attr)
            for d in node.decorator_list
        )
        body = [stmt for stmt in node.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))]
        if not is_abstract and (not body or all(_is_empty_stmt(stmt) for stmt in body)):
            self.violations.append({
                "file": self.filename,
                "line": node.lineno,
                "type": "empty_function",
                "message": f"Function '{node.name}' is empty with no implementation.",
            })

        # Check for trivial forwarder wrapper: single return call with identical arguments
        if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Call):
            call = body[0].value
            if isinstance(call.func, (ast.Name, ast.Attribute)):
                arg_names = [arg.arg for arg in node.args.args if arg.arg != "self"]
                call_arg_names = [a.id for a in call.args if isinstance(a, ast.Name)]
                if arg_names and arg_names == call_arg_names:
                    self.violations.append({
                        "file": self.filename,
                        "line": node.lineno,
                        "type": "trivial_passthrough",
                        "message": f"Function '{node.name}' is a trivial passthrough forwarding directly to another call without transformations.",
                    })


def scan_directory(target_path: Path, ignore_dirs: Set[str] = None) -> Tuple[List[dict], Dict[str, int]]:
    ignore_dirs = ignore_dirs or {".git", ".venv", "venv", "__pycache__", ".brain", "node_modules", ".pytest_cache"}
    all_violations: List[dict] = []
    abc_classes: Set[str] = set()
    class_inheritances: Dict[str, List[str]] = {}

    py_files = []
    if target_path.is_file() and target_path.suffix == ".py":
        py_files = [target_path]
    elif target_path.is_dir():
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(Path(root) / file)

    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            visitor = OverengineeringVisitor(str(py_file))
            visitor.visit(tree)
            all_violations.extend(visitor.violations)
            abc_classes.update(visitor.abc_classes)
            for c_name, (_, bases) in visitor.defined_classes.items():
                for b in bases:
                    class_inheritances.setdefault(b, []).append(c_name)
        except (SyntaxError, UnicodeDecodeError):
            continue

    # Check for Single-Implementation ABCs (premature abstractions)
    for abc in abc_classes:
        impls = class_inheritances.get(abc, [])
        if len(impls) <= 1:
            all_violations.append({
                "file": "codebase",
                "line": 0,
                "type": "single_impl_interface",
                "message": f"Abstract base class '{abc}' has {len(impls)} implementation(s) across codebase. Consider inlining until a second implementation exists (YAGNI).",
            })

    counts: Dict[str, int] = {}
    for v in all_violations:
        counts[v["type"]] = counts.get(v["type"], 0) + 1

    return all_violations, counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan codebase for overengineering and dead abstractions.")
    parser.add_argument("--path", default=".", help="Directory or file path to scan (default: current directory)")
    parser.add_argument("--max-violations", type=int, default=0, help="Maximum allowed violations before failure")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--strict", action="store_true", help="Fail if any violation is found")

    args = parser.parse_args()
    target = Path(args.path).resolve()
    if not target.exists():
        print(f"Error: Path {target} does not exist.", file=sys.stderr)
        return 1

    violations, counts = scan_directory(target)

    if args.json:
        print(json.dumps({"violations": violations, "summary": counts, "total": len(violations)}, indent=2))
    else:
        print("=== Ponytail Review: Overengineering & Abstraction Linter ===")
        print(f"Scanned path: {target}")
        print(f"Total potential issues detected: {len(violations)}")
        if counts:
            print("Breakdown by type:")
            for v_type, count in counts.items():
                print(f"  - {v_type}: {count}")
        print("-------------------------------------------------------------")
        for v in violations[:20]:
            print(f"[{v['type']}] {v['file']}:{v['line']} -> {v['message']}")
        if len(violations) > 20:
            print(f"... and {len(violations) - 20} more.")

    limit = 0 if args.strict else args.max_violations
    if len(violations) > limit:
        print(f"\n[FAIL] Found {len(violations)} overengineering issues (threshold: {limit}).", file=sys.stderr)
        return 1

    print("\n[PASS] Codebase is lean within acceptable thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
