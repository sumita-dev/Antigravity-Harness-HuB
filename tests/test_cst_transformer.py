"""Tests for Surgical CST Transformer (Pillar 4)."""

import pytest

from harness.utils.cst_transformer import (
    get_function_signature,
    inject_function_decorator,
    inject_import_statement,
)


def test_get_function_signature():
    code = (
        "# Some comment\n"
        "def compute_total(a: int, b: int = 10) -> int:\n"
        "    '''Compute total.'''\n"
        "    return a + b\n"
    )
    sig = get_function_signature(code, "compute_total")
    assert sig is not None
    assert "def compute_total" in sig
    assert "-> int:" in sig


def test_inject_import_statement_with_docstring():
    code = (
        '"""Module docstring explaining things."""\n\n'
        'import os\n\n'
        'def main():\n'
        '    pass\n'
    )
    res = inject_import_statement(code, "import sys")
    assert "import sys" in res
    # Đảm bảo module docstring vẫn ở đầu tiên
    assert res.startswith('"""Module docstring explaining things."""')
    # Không inject trùng lặp
    res_repeat = inject_import_statement(res, "import sys")
    assert res_repeat.count("import sys") == 1


def test_inject_function_decorator_preserves_comments():
    code = (
        "# Top level comment\n"
        "def service_handler(data):\n"
        "    # Inside handler comment\n"
        "    '''Process data docstring.'''\n"
        "    return data\n"
    )
    res = inject_function_decorator(code, "service_handler", "@pytest.mark.asyncio")
    assert "@pytest.mark.asyncio\ndef service_handler(data):" in res
    assert "# Top level comment" in res
    assert "# Inside handler comment" in res
    assert "'''Process data docstring.'''" in res


def test_inject_function_decorator_with_indent():
    code = (
        "class ApiClient:\n"
        "    def request(self):\n"
        "        pass\n"
    )
    res = inject_function_decorator(code, "request", "@retry")
    assert "    @retry\n    def request(self):" in res
