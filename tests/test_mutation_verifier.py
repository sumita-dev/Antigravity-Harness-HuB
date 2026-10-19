"""Tests for Mutation Testing Gate (Pillar 3)."""

from pathlib import Path
import pytest
import sys
import tempfile

from harness.validators.mutation_verifier import (
    Mutant,
    MutationReport,
    generate_mutants,
    verify_test_lethality,
)


def test_generate_mutants_comparison():
    code = "def is_positive(x):\n    return x > 0\n"
    mutants = generate_mutants(code, max_mutants=5)
    assert len(mutants) >= 1
    mut_code, mutant = mutants[0]
    assert "<=" in mut_code
    assert mutant.original_token == ">"
    assert mutant.mutated_token == "<="
    assert mutant.line_no == 2


def test_generate_mutants_boolean():
    code = "def flag():\n    return True\n"
    mutants = generate_mutants(code, max_mutants=5)
    assert len(mutants) >= 1
    mut_code, mutant = mutants[0]
    assert "False" in mut_code
    assert mutant.original_token == "True"
    assert mutant.mutated_token == "False"


def test_generate_mutants_arithmetic_offset():
    code = "def get_offset():\n    return 10\n"
    mutants = generate_mutants(code, max_mutants=5)
    assert len(mutants) >= 1
    mut_code, mutant = mutants[0]
    assert "11" in mut_code
    assert mutant.original_token == "10"
    assert mutant.mutated_token == "11"


def test_verify_test_lethality_killed():
    """Khi test chặt chẽ, mutant phải bị KILLED (test fail -> lethal)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_file = Path(tmpdir) / "calc.py"
        src_file.write_text("def add_one(x):\n    return x + 1\n", encoding="utf-8")

        test_file = Path(tmpdir) / "test_calc.py"
        test_file.write_text(
            "from calc import add_one\n\n"
            "def test_add_one():\n"
            "    assert add_one(5) == 6\n",
            encoding="utf-8",
        )

        test_cmd = f'"{sys.executable}" -m pytest test_calc.py -q'
        report = verify_test_lethality(str(src_file), test_cmd, max_mutants=2)

        assert report.total_mutants > 0
        assert report.killed == report.total_mutants
        assert report.survived == 0
        assert report.score == 1.0
        assert report.is_lethal is True


def test_verify_test_lethality_survived():
    """Khi test lỏng lẻo (vd test rỗng hoặc assert True), mutant SURVIVED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_file = Path(tmpdir) / "calc.py"
        src_file.write_text("def is_even(x):\n    return x == 2\n", encoding="utf-8")

        test_file = Path(tmpdir) / "test_calc.py"
        # Test không assert kết quả trả về của is_even
        test_file.write_text(
            "from calc import is_even\n\n"
            "def test_loose():\n"
            "    is_even(2)\n"
            "    assert True\n",
            encoding="utf-8",
        )

        test_cmd = f'"{sys.executable}" -m pytest test_calc.py -q'
        report = verify_test_lethality(str(src_file), test_cmd, max_mutants=2)

        assert report.total_mutants > 0
        assert report.survived > 0
        assert report.is_lethal is False
