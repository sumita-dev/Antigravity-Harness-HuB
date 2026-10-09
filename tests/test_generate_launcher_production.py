"""Tests cho các tính năng production handoff trong scripts/generate_launcher.py."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.generate_launcher import generate_launcher


def test_generate_launcher_production_node(tmp_path: Path):
    result = generate_launcher(
        app_dir=tmp_path,
        port=3000,
        start_cmd="npm run dev",
        title="Production Node Portal",
        data_file="data/seed.json",
        docker=True,
    )

    assert result.bat.exists()
    assert result.doc.exists()
    assert result.dockerfile is not None and result.dockerfile.exists()
    assert result.docker_compose is not None and result.docker_compose.exists()
    assert result.ci_workflow is not None and result.ci_workflow.exists()
    assert result.env_example is not None and result.env_example.exists()
    assert result.architecture is not None and result.architecture.exists()

    # Kiểm tra Dockerfile Node
    docker_text = result.dockerfile.read_text(encoding="utf-8")
    assert "FROM node:20-alpine AS deps" in docker_text
    assert "FROM node:20-alpine AS runner" in docker_text
    assert "USER appuser" in docker_text
    assert "EXPOSE 3000" in docker_text
    assert "HEALTHCHECK" in docker_text

    # Kiểm tra docker-compose.yml
    compose_text = result.docker_compose.read_text(encoding="utf-8")
    assert "3000:3000" in compose_text
    assert "restart: unless-stopped" in compose_text
    assert "data/seed.json" in compose_text

    # Kiểm tra .github/workflows/ci.yml
    ci_text = result.ci_workflow.read_text(encoding="utf-8")
    assert "run_security_audit.py" in ci_text
    assert "pytest" in ci_text

    # Kiểm tra .env.example
    env_text = result.env_example.read_text(encoding="utf-8")
    assert "PORT=3000" in env_text
    assert "DATA_FILE_PATH=\"data/seed.json\"" in env_text

    # Kiểm tra ARCHITECTURE.md
    arch_text = result.architecture.read_text(encoding="utf-8")
    assert "mermaid" in arch_text
    assert "AC-HEALTH" in arch_text
    assert "AC-SEED" in arch_text
    assert "/health" in arch_text


def test_generate_launcher_production_python(tmp_path: Path):
    result = generate_launcher(
        app_dir=tmp_path,
        port=8080,
        start_cmd="uvicorn main:app --host 0.0.0.0 --port 8080",
        title="Python Backend API",
        data_file="mockData.json",
        docker=True,
    )

    assert result.dockerfile is not None and result.dockerfile.exists()
    docker_text = result.dockerfile.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim AS builder" in docker_text
    assert "FROM python:3.12-slim AS runner" in docker_text
    assert "USER appuser" in docker_text
    assert "EXPOSE 8080" in docker_text
    assert "HEALTHCHECK" in docker_text


def test_launcher_result_compatibility(tmp_path: Path):
    # Unpack 2 phần tử như code cũ vẫn hoạt động chuẩn xác
    bat, doc = generate_launcher(
        app_dir=tmp_path,
        port=4000,
        docker=True,
    )
    assert bat.name == "start-app.bat"
    assert doc.name == "HDSD-NHANH.md"

    # Hỗ trợ truy cập thuộc tính và dict access
    res = generate_launcher(app_dir=tmp_path, docker=True)
    assert len(res.created_files) == 7
    assert res["dockerfile"] == res.dockerfile
    assert res["architecture"] == res.architecture


def test_cli_docker_generation(tmp_path: Path):
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "generate_launcher.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--app-dir",
        str(tmp_path),
        "--port",
        "5000",
        "--title",
        "CLI Tested App",
        "--docker",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / "docker-compose.yml").exists()
    assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()
    assert (tmp_path / "ARCHITECTURE.md").exists()
