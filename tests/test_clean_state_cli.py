"""Integration tests for Clean State and Feature List CLI interfaces (AC-INT-02 & CLI flags).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

import run_harness
from harness.feature_list import CompletionEvidence, FeatureItem, FeatureList
from scripts import clean_state_check


def test_scripts_clean_state_check_cli(tmp_path, capsys):
    """AC-INT-02: Script runner scripts/clean_state_check.py chạy độc lập và hỗ trợ --json, --output."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "main.py").write_text("print('clean')\n", encoding="utf-8")

    out_json = tmp_path / "report.json"
    rc = clean_state_check.main([
        "--project-root", str(project),
        "--boot-cmd", f'"{sys.executable}" -c "print(1)"',
        "--test-cmd", f'"{sys.executable}" -c "print(1)"',
        "--json",
        "--output", str(out_json),
    ])
    assert rc == 0
    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["overall_status"] == "PASS"
    assert data["is_ready_for_clockout"] is True


def test_run_harness_clean_state_check_cli(tmp_path, capsys):
    """run_harness.py --clean-state-check."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("print('ok')\n", encoding="utf-8")

    rc = run_harness.main([
        "--clean-state-check",
        "--project-root", str(project),
        "--json",
    ])
    # Không có test suite và boot cmd -> SKIPPED/PASS -> overall PASS
    assert rc == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["overall_status"] == "PASS"


def test_run_harness_vcr_audit_cli(tmp_path, capsys):
    """run_harness.py --feature-list <path> --vcr-audit."""
    project = tmp_path / "proj"
    project.mkdir()
    fl_file = project / "feature_list.json"

    f1 = FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="User authentication service",
        verification_command="pytest",
        state="not_started",
    )
    fl = FeatureList("cli-test", [f1], file_path=fl_file)
    fl.save()

    rc = run_harness.main([
        "--feature-list", str(fl_file),
        "--vcr-audit",
        "--json",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "VALID"
    assert res["project_id"] == "cli-test"
    assert res["vcr_metrics"]["total_features"] == 1


def test_run_harness_verify_feature_cli(tmp_path, capsys):
    """run_harness.py --verify-feature FEAT-001."""
    project = tmp_path / "proj"
    project.mkdir()
    fl_file = project / "feature_list.json"
    (project / "verify_me.py").write_text("print('verified'); import sys; sys.exit(0)\n", encoding="utf-8")

    f1 = FeatureItem(
        id="FEAT-001",
        category="core",
        behavior_description="Verified CLI command feature",
        verification_command=f'"{sys.executable}" verify_me.py',
        state="active",
    )
    fl = FeatureList("cli-verify-test", [f1], file_path=fl_file)
    fl.save()

    rc = run_harness.main([
        "--project-root", str(project),
        "--feature-list", str(fl_file),
        "--verify-feature", "FEAT-001",
        "--actor", "QA_Chief",
        "--json",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    feat_res = json.loads(captured.out)
    assert feat_res["state"] == "passing"
    assert feat_res["completion_evidence"]["verified_by"] == "QA_Chief"
