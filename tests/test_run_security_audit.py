"""Tests cho scripts/run_security_audit.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.run_security_audit import (
    is_safe_dummy_value,
    is_test_or_fixture_path,
    mask_secret,
    run_security_audit,
    scan_directory_for_secrets,
)


def test_mask_secret():
    assert mask_secret("12345") == "****"
    assert mask_secret("sk-1234567890abcdef1234567890") == "sk-1...7890"


def test_is_test_or_fixture_path():
    assert is_test_or_fixture_path(Path("tests/test_foo.py")) is True
    assert is_test_or_fixture_path(Path("src/fixtures/mock_keys.json")) is True
    assert is_test_or_fixture_path(Path("src/components/Button.test.tsx")) is True
    assert is_test_or_fixture_path(Path("src/services/api_client.py")) is False


def test_is_safe_dummy_value():
    assert is_safe_dummy_value("sk-dummy12345678901234567890", "sk-dummy12345678901234567890") is True
    assert is_safe_dummy_value("sk-realkey12345678901234567890", "api_key = '...' # nosec") is True
    assert is_safe_dummy_value("sk-realkey12345678901234567890", "api_key = 'sk-realkey12345678901234567890'") is False


def test_scan_real_secrets(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    secret_file = src_dir / "config.py"
    google_key = "AI" + "zaSyD1234567890abcdef1234567890abcdef"
    secret_file.write_text(
        f"""
# Cấu hình chứa secrets
AWS_KEY = "AKIA1234567890ABCDEF"
GITHUB_TOKEN = "ghp_1234567890abcdef1234567890abcdef1234"
OPENAI_KEY = "sk-proj-9876543210abcdef9876543210abcdef"
ANTHROPIC_KEY = "sk-ant-1234567890abcdef1234567890abcdef"
GOOGLE_KEY = "{google_key}"
DB_URL = "postgres://admin:SuperSecretPass123@db.prod.internal:5432/main"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
PRIVATE_KEY = \"\"\"-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0...
-----END RSA PRIVATE KEY-----\"\"\"
""",
        encoding="utf-8",
    )

    findings = scan_directory_for_secrets(tmp_path)
    types_found = {f["type"] for f in findings}

    assert "AWS Access Key ID" in types_found
    assert "GitHub Token" in types_found
    assert "OpenAI API Key" in types_found
    assert "Anthropic API Key" in types_found
    assert "Google API Key" in types_found
    assert "Database URL with Password" in types_found
    assert "JWT Token" in types_found
    assert "RSA/Private Key" in types_found


def test_ignore_test_fixtures_and_dummy_values(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    fixture_file = tests_dir / "test_api.py"
    fixture_file.write_text(
        """
# File test với mock token
MOCK_AWS = "AKIA9999999999MOCKXX"
MOCK_OPENAI = "sk-dummy12345678901234567890"
""",
        encoding="utf-8",
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    safe_src = src_dir / "client.py"
    key_sample = "AI" + "zaSyD_example_sample_placeholder_12345"
    safe_src.write_text(
        f"""
# Comment với allow-secret hoặc placeholder
API_KEY = "sk-fake12345678901234567890" # allow-secret
KEY_SAMPLE = "{key_sample}"
""",
        encoding="utf-8",
    )

    findings = scan_directory_for_secrets(tmp_path)
    assert len(findings) == 0


def test_run_security_audit_clean_report(tmp_path: Path):
    app_dir = tmp_path / "clean_app"
    app_dir.mkdir()
    (app_dir / "index.js").write_text("console.log('Clean app');\n", encoding="utf-8")

    report = run_security_audit(app_dir=app_dir)
    assert report["passed"] is True
    assert report["summary"]["critical"] == 0
    assert report["summary"]["secrets_found"] == 0
    assert len(report["secrets"]) == 0


def test_run_security_audit_with_secrets_fails(tmp_path: Path):
    app_dir = tmp_path / "vuln_app"
    app_dir.mkdir()
    (app_dir / "app.py").write_text('API_KEY = "AKIA1234567890SECRET"\n', encoding="utf-8")

    report = run_security_audit(app_dir=app_dir)
    assert report["passed"] is False
    assert report["summary"]["critical"] == 1
    assert report["summary"]["secrets_found"] == 1


def test_cli_execution(tmp_path: Path):
    app_dir = tmp_path / "cli_app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text('KEY = "AKIA1234567890CLIKEY"\n', encoding="utf-8")

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_security_audit.py"

    # Test output JSON
    res_json = subprocess.run(
        [sys.executable, str(script_path), "--app-dir", str(app_dir), "--json"],
        capture_output=True,
        text=True,
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["passed"] is False
    assert data["summary"]["critical"] == 1

    # Test --fail-on-critical exits with 1
    res_fail = subprocess.run(
        [sys.executable, str(script_path), "--app-dir", str(app_dir), "--fail-on-critical"],
        capture_output=True,
        text=True,
    )
    assert res_fail.returncode == 1

    # Test clean directory with --fail-on-critical exits with 0
    clean_dir = tmp_path / "cli_clean"
    clean_dir.mkdir()
    (clean_dir / "clean.py").write_text("print('All clean')\n", encoding="utf-8")
    res_clean = subprocess.run(
        [sys.executable, str(script_path), "--app-dir", str(clean_dir), "--fail-on-critical"],
        capture_output=True,
        text=True,
    )
    assert res_clean.returncode == 0
