"""Unit tests for scripts/auto_harvest_global.py and hook configurations."""

from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from scripts.auto_harvest_global import (
    get_config_dir,
    harvest_from_transcript,
    harvest_patterns_from_steps,
    main,
    make_dedup_key,
    parse_transcript,
    render_rules_markdown,
    sanitize_text,
    save_patterns,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_jsonl(file_path: Path, items: list[dict[str, Any]]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def test_sanitize_text() -> None:
    """Ensure machine/user paths are sanitized to generic paths."""
    win_prefix = "C:" + "\\Users\\"
    text_win = f"Error at {win_prefix}SampleUser\\project\\main.py line 42"
    sanitized_win = sanitize_text(text_win)
    assert "SampleUser" not in sanitized_win
    assert "~" in sanitized_win

    text_unix = "Error at /home/alice/project/main.py line 10"
    sanitized_unix = sanitize_text(text_unix)
    assert "/home/alice" not in sanitized_unix
    assert "~" in sanitized_unix


def test_get_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ANTIGRAVITY_CONFIG_DIR overrides the default global path."""
    custom_dir = tmp_path / "custom_config"
    monkeypatch.setenv("ANTIGRAVITY_CONFIG_DIR", str(custom_dir))
    resolved = get_config_dir()
    assert resolved == custom_dir.resolve()

    # When override_dir argument is given, it takes highest precedence
    explicit_dir = tmp_path / "explicit"
    assert get_config_dir(str(explicit_dir)) == explicit_dir.resolve()


def test_stdin_empty(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """When stdin is empty, script prints {} and exits safely."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(sys, "argv", ["auto_harvest_global.py"])
    main()
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {}


def test_stdin_invalid_json(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """When stdin is malformed JSON, script prints {} and exits safely."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("INVALID JSON {{"))
    monkeypatch.setattr(sys, "argv", ["auto_harvest_global.py"])
    main()
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {}


def test_transcript_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """When transcriptPath points to a non-existent file, it handles gracefully."""
    fake_path = tmp_path / "does_not_exist.jsonl"
    payload = {"transcriptPath": str(fake_path), "conversationId": "test-conv-1"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "argv", ["auto_harvest_global.py"])
    monkeypatch.setenv("ANTIGRAVITY_CONFIG_DIR", str(tmp_path))

    main()
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {}
    assert not (tmp_path / "global_code_patterns.json").exists()


def test_transcript_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """When transcript is empty, output {} and do not create empty pattern files."""
    empty_t = tmp_path / "empty_transcript.jsonl"
    empty_t.write_text("", encoding="utf-8")

    payload = {"transcriptPath": str(empty_t), "conversationId": "test-conv-empty"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "argv", ["auto_harvest_global.py"])
    monkeypatch.setenv("ANTIGRAVITY_CONFIG_DIR", str(tmp_path))

    main()
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {}
    assert not (tmp_path / "global_code_patterns.json").exists()


def test_transcript_no_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Transcript with only passing commands yields no error patterns."""
    steps = [
        {"step_index": 0, "type": "USER_INPUT", "status": "DONE", "content": "Run tests"},
        {
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest -q"}}],
        },
        {
            "step_index": 2,
            "type": "GENERIC",
            "status": "DONE",
            "content": "The command exited with code 0.\n10 passed in 1.2s",
        },
    ]
    t_file = tmp_path / "clean_transcript.jsonl"
    _write_jsonl(t_file, steps)

    payload = {"transcriptPath": str(t_file), "conversationId": "test-clean"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "argv", ["auto_harvest_global.py"])
    monkeypatch.setenv("ANTIGRAVITY_CONFIG_DIR", str(tmp_path))

    main()
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {}
    assert not (tmp_path / "global_code_patterns.json").exists()


def test_harvest_code_error_and_fix(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Full lifecycle: Error in run_command -> replace_file_content fix -> rerun passes."""
    steps = [
        {
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-04T12:00:00Z",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest tests/test_calc.py"}}],
        },
        {
            "step_index": 2,
            "type": "GENERIC",
            "status": "ERROR",
            "created_at": "2026-10-04T12:00:05Z",
            "content": "The command exited with code 1.\nFAILED tests/test_calc.py - AssertionError: assert 10 == 15",
        },
        {
            "step_index": 3,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-04T12:00:10Z",
            "tool_calls": [
                {
                    "name": "replace_file_content",
                    "args": {
                        "TargetFile": "src/calc.py",
                        "Instruction": "Fix calculation return value to 15",
                    },
                }
            ],
        },
        {
            "step_index": 4,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": "2026-10-04T12:00:15Z",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest tests/test_calc.py"}}],
        },
        {
            "step_index": 5,
            "type": "GENERIC",
            "status": "DONE",
            "created_at": "2026-10-04T12:00:20Z",
            "content": "The command exited with code 0.\n1 passed in 0.05s",
        },
    ]
    t_file = tmp_path / "fix_transcript.jsonl"
    _write_jsonl(t_file, steps)

    config_dir = tmp_path / "config"
    payload = {"transcriptPath": str(t_file), "conversationId": "conv-test-123"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "argv", ["auto_harvest_global.py"])
    monkeypatch.setenv("ANTIGRAVITY_CONFIG_DIR", str(config_dir))

    main()
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {}

    # Verify JSON persistence
    json_path = config_dir / "global_code_patterns.json"
    assert json_path.exists(), "global_code_patterns.json should be created"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["total"] == 1
    pattern = data["patterns"][0]
    assert pattern["error_type"] == "AssertionError"
    assert "assert 10 == 15" in pattern["cause"]
    assert "Fix calculation return value to 15" in pattern["fix"]
    assert "src/calc.py" in pattern["files_modified"]
    assert pattern["occurrences"] == 1
    assert pattern["conversation_id"] == "conv-test-123"

    # Verify Markdown persistence
    md_path = config_dir / "rules" / "learned_code_rules.md"
    assert md_path.exists(), "learned_code_rules.md should be created"
    md_content = md_path.read_text(encoding="utf-8")
    assert "[AssertionError]" in md_content
    assert "assert 10 == 15" in md_content
    assert "Fix calculation return value to 15" in md_content
    assert "src/calc.py" in md_content


def test_harvest_python_exception_and_fix(tmp_path: Path) -> None:
    """Verify harvesting ModuleNotFoundError resolved by write_to_file."""
    steps = [
        {
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "python main.py"}}],
        },
        {
            "step_index": 2,
            "type": "GENERIC",
            "status": "DONE",
            "content": "The command exited with code 1.\nTraceback (most recent call last):\n  File 'main.py', line 1, in <module>\nModuleNotFoundError: No module named 'requests'",
        },
        {
            "step_index": 3,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "tool_calls": [
                {
                    "name": "write_to_file",
                    "args": {
                        "TargetFile": "requirements.txt",
                        "Description": "Add requests to requirements.txt",
                    },
                }
            ],
        },
        {
            "step_index": 4,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "tool_calls": [{"name": "run_command", "args": {"CommandLine": "python main.py"}}],
        },
        {
            "step_index": 5,
            "type": "GENERIC",
            "status": "DONE",
            "content": "The command exited with code 0.\nApp started successfully.",
        },
    ]
    t_file = tmp_path / "module_error.jsonl"
    _write_jsonl(t_file, steps)

    config_dir = tmp_path / "config"
    patterns = harvest_from_transcript(t_file, conversation_id="conv-mod-1", config_dir=config_dir)
    assert len(patterns) == 1
    assert patterns[0]["error_type"] == "ModuleNotFoundError"
    assert "No module named 'requests'" in patterns[0]["cause"]
    assert "Add requests to requirements.txt" in patterns[0]["fix"]
    assert "requirements.txt" in patterns[0]["files_modified"]


def test_deduplication_and_occurrences(tmp_path: Path) -> None:
    """Duplicate errors should increment occurrences and not create new items."""
    config_dir = tmp_path / "config"
    pat1 = {
        "id": "pat_1",
        "error_type": "AssertionError",
        "cause": "AssertionError: assert a == b",
        "fix": "Fix a",
        "command": "pytest",
        "files_modified": ["a.py"],
        "timestamp": "2026-10-04T10:00:00Z",
        "conversation_id": "c1",
        "occurrences": 1,
    }
    save_patterns(config_dir, [pat1])

    # Save same error pattern again
    pat2 = {
        "id": "pat_2",
        "error_type": "AssertionError",
        "cause": "AssertionError: assert a == b",
        "fix": "Updated fix description",
        "command": "pytest",
        "files_modified": ["b.py"],
        "timestamp": "2026-10-04T11:00:00Z",
        "conversation_id": "c2",
        "occurrences": 1,
    }
    save_patterns(config_dir, [pat2])

    data = json.loads((config_dir / "global_code_patterns.json").read_text(encoding="utf-8"))
    assert data["total"] == 1
    assert data["patterns"][0]["occurrences"] == 2
    assert "a.py" in data["patterns"][0]["files_modified"]
    assert "b.py" in data["patterns"][0]["files_modified"]


def test_max_patterns_capping(tmp_path: Path) -> None:
    """Ensure pattern list does not grow unbounded beyond max_patterns."""
    config_dir = tmp_path / "config"
    patterns = [
        {
            "id": f"pat_{i}",
            "error_type": f"ErrorType_{i}",
            "cause": f"Cause number {i}",
            "fix": f"Fix number {i}",
            "command": "test",
            "files_modified": [],
            "timestamp": f"2026-10-04T10:0{i}:00Z",
            "conversation_id": f"conv_{i}",
            "occurrences": i,
        }
        for i in range(10)
    ]
    save_patterns(config_dir, patterns, max_patterns=3)

    data = json.loads((config_dir / "global_code_patterns.json").read_text(encoding="utf-8"))
    assert data["total"] == 3
    # Items with highest occurrences should be kept
    types_kept = [p["error_type"] for p in data["patterns"]]
    assert types_kept == ["ErrorType_9", "ErrorType_8", "ErrorType_7"]


def test_hooks_json_configuration() -> None:
    """Verify that .agents/hooks.json is correctly configured according to Antigravity spec."""
    hooks_file = REPO_ROOT / ".agents" / "hooks.json"
    assert hooks_file.exists(), "Missing .agents/hooks.json"

    data = json.loads(hooks_file.read_text(encoding="utf-8"))
    assert "auto-code-harvester" in data
    hook_cfg = data["auto-code-harvester"]
    assert "Stop" in hook_cfg
    stop_handlers = hook_cfg["Stop"]
    assert isinstance(stop_handlers, list)
    assert len(stop_handlers) >= 1

    handler = stop_handlers[0]
    assert handler.get("type") == "command"
    assert "scripts/auto_harvest_global.py" in handler.get("command", "")
    assert handler.get("timeout") == 30


def test_cli_subprocess_invocation(tmp_path: Path) -> None:
    """Test running scripts/auto_harvest_global.py via real subprocess."""
    script_path = REPO_ROOT / "scripts" / "auto_harvest_global.py"
    config_dir = tmp_path / "cli_cfg"

    payload = {
        "conversationId": "cli-test-conv",
        "transcriptPath": str(tmp_path / "nonexistent.jsonl"),
        "workspacePaths": [str(REPO_ROOT)],
    }
    env = {"ANTIGRAVITY_CONFIG_DIR": str(config_dir)}

    res = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**dict(subprocess.os.environ), **env},
    )

    assert res.returncode == 0
    assert json.loads(res.stdout.strip()) == {}
