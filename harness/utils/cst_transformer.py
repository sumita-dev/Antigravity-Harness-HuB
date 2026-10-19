"""Surgical Concrete Syntax Tree (CST) Transformer - Pillar 4 of Antigravity Harness Hub.
Cung cấp các hàm phẫu thuật mã nguồn Python (surgical transformation) bảo toàn
100% comment, docstring, định dạng và thụt lề bằng standard library (ast, tokenize).
"""

from __future__ import annotations

import ast
import io
import token
import tokenize
from typing import Optional


def get_function_signature(source_code: str, func_name: str) -> Optional[str]:
    """Trích xuất chữ ký hàm (signature) bao gồm def name(...) -> ret:.

    Trả về chuỗi signature chính xác từ mã nguồn, hoặc None nếu không tìm thấy.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return None

    target_node: Optional[ast.FunctionDef | ast.AsyncFunctionDef] = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            target_node = node
            break

    if target_node is None:
        return None

    lines = source_code.splitlines(keepends=True)
    start_lineno = target_node.lineno  # 1-indexed

    # Duyệt từ start_lineno đến khi gặp dấu ':' kết thúc signature (ở paren_depth == 0)
    sub_code = "".join(lines[start_lineno - 1:])
    readline = io.StringIO(sub_code).readline

    paren_depth = 0
    end_line_rel = 0
    end_col = 0
    found_colon = False

    try:
        for tok in tokenize.generate_tokens(readline):
            tok_type = tok.type
            tok_string = tok.string
            s_line, s_col = tok.start
            e_line, e_col = tok.end

            if tok_string in ("(", "[", "{"):
                paren_depth += 1
            elif tok_string in (")", "]", "}"):
                paren_depth -= 1

            if tok_string == ":" and paren_depth == 0:
                end_line_rel = e_line
                end_col = e_col
                found_colon = True
                break
    except Exception:
        pass

    if found_colon:
        # Lấy slice chính xác từ sub_code từ đầu đến (end_line_rel, end_col)
        sub_lines = sub_code.splitlines(keepends=True)
        sig_lines: list[str] = []
        for l_idx in range(end_line_rel):
            if l_idx == end_line_rel - 1:
                sig_lines.append(sub_lines[l_idx][:end_col])
            else:
                sig_lines.append(sub_lines[l_idx])
        return "".join(sig_lines).strip()

    return None



def inject_import_statement(source_code: str, import_stmt: str) -> str:
    """Chèn lệnh import vào vị trí tối ưu trong file Python.

    Bảo toàn:
    - Shebang (`#!/usr/bin/env python`)
    - Encoding cookie (`# -*- coding: utf-8 -*-`)
    - Module docstring (nếu có ở đầu file)
    - Comment và thụt lề
    Nếu import đã tồn tại, không chèn trùng lặp.
    """
    clean_stmt = import_stmt.strip()
    if not clean_stmt:
        return source_code

    # Kiểm tra xem import đã tồn tại trong mã nguồn chưa (đơn giản qua dòng hoặc AST)
    try:
        tree = ast.parse(source_code)
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if ast.unparse(node).strip() == clean_stmt:
                    return source_code
    except SyntaxError:
        pass

    lines = source_code.splitlines(keepends=True)
    if not lines:
        return clean_stmt + "\n"

    insert_idx = 0

    # 1. Bỏ qua shebang hoặc encoding cookie
    while insert_idx < len(lines):
        line_str = lines[insert_idx].strip()
        if insert_idx == 0 and line_str.startswith("#!"):
            insert_idx += 1
            continue
        if insert_idx <= 1 and ("coding=" in line_str or "coding:" in line_str) and line_str.startswith("#"):
            insert_idx += 1
            continue
        break

    # 2. Bỏ qua module docstring nếu có
    try:
        parsed = ast.parse(source_code)
        docstring = ast.get_docstring(parsed, clean=False)
        if docstring is not None and parsed.body:
            first_stmt = parsed.body[0]
            if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant):
                # end_lineno là 1-indexed
                end_line = getattr(first_stmt, "end_lineno", first_stmt.lineno)
                if end_line > insert_idx:
                    insert_idx = end_line
    except SyntaxError:
        pass

    # 3. Tìm khối import hiện có để chèn nối tiếp vào cuối khối import
    # Hoặc nếu chưa có import nào, chèn ngay sau docstring
    last_import_idx = -1
    try:
        parsed = ast.parse(source_code)
        for node in parsed.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                end_line = getattr(node, "end_lineno", node.lineno)
                if end_line > last_import_idx:
                    last_import_idx = end_line
    except SyntaxError:
        pass

    if last_import_idx != -1 and last_import_idx >= insert_idx:
        target_idx = last_import_idx
    else:
        target_idx = insert_idx

    stmt_to_insert = clean_stmt + "\n"

    # Nếu vị trí chèn sau docstring và trước code, thêm dòng trống nếu cần
    new_lines = list(lines)
    # Đảm bảo index hợp lệ
    target_idx = min(target_idx, len(new_lines))
    new_lines.insert(target_idx, stmt_to_insert)

    return "".join(new_lines)


def inject_function_decorator(source_code: str, func_name: str, decorator_code: str) -> str:
    """Chèn decorator vào ngay trước định nghĩa hàm `func_name`.

    Bảo toàn:
    - Đúng mức thụt lề (indentation) của hàm
    - Các decorator đã tồn tại trước đó
    - Docstring và body của hàm nguyên vẹn 100%
    """
    clean_dec = decorator_code.strip()
    if not clean_dec.startswith("@"):
        clean_dec = "@" + clean_dec

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code

    target_node: Optional[ast.FunctionDef | ast.AsyncFunctionDef] = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            target_node = node
            break

    if target_node is None:
        return source_code

    lines = source_code.splitlines(keepends=True)
    def_line_idx = target_node.lineno - 1  # 0-indexed

    # Nếu hàm đã có decorator_list, vị trí chèn là trước decorator đầu tiên hoặc sau decorator cuối
    # Thụt lề lấy theo dòng def hoặc decorator đầu tiên
    if target_node.decorator_list:
        first_dec_line = target_node.decorator_list[0].lineno - 1
        indent_len = len(lines[first_dec_line]) - len(lines[first_dec_line].lstrip())
        indent = lines[first_dec_line][:indent_len]
        insert_line_idx = target_node.decorator_list[-1].end_lineno if hasattr(target_node.decorator_list[-1], 'end_lineno') else (target_node.decorator_list[-1].lineno)
    else:
        indent_len = len(lines[def_line_idx]) - len(lines[def_line_idx].lstrip())
        indent = lines[def_line_idx][:indent_len]
        insert_line_idx = def_line_idx

    # Kiểm tra xem decorator đã tồn tại chưa
    for dec_node in target_node.decorator_list:
        try:
            if ast.unparse(dec_node).strip() == clean_dec.lstrip("@"):
                return source_code
        except Exception:
            pass

    dec_line_to_insert = f"{indent}{clean_dec}\n"
    new_lines = list(lines)
    new_lines.insert(insert_line_idx, dec_line_to_insert)

    return "".join(new_lines)
