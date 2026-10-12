"""Bộ kiểm thử cho module chẩn đoán & kiểm toán phiên làm việc (session_diagnostics).

Kiểm thử 4 rào chắn:
1. Phát hiện polling loops (manage_task status).
2. Phát hiện lãng phí model inheritance (Model='inherit' cho Critic/QA).
3. Phát hiện đọc file lặp lại (view_file redundancy).
4. Phán quyết tổng thể (CLEAN / WARNING / EXCESSIVE_WASTE) và nạp file jsonl.
"""

import json
from pathlib import Path
import pytest

from harness.validators.session_diagnostics import (
    SessionDiagnosticReport,
    calculate_context_growth,
    detect_model_inheritance_waste,
    detect_polling_loops,
    detect_view_file_redundancy,
    diagnose_session,
)


def test_detect_polling_loops_no_violation():
    """Một lần check task hoặc các action khác không bị coi là polling loop."""
    records = [
        {
            "step_index": 1,
            "tool_calls": [
                {"name": "run_command", "args": {"CommandLine": "pytest"}}
            ],
        },
        {
            "step_index": 2,
            "tool_calls": [
                {"name": "manage_task", "args": {"Action": "status", "TaskId": "task-10"}}
            ],
        },
        {
            "step_index": 3,
            "tool_calls": [
                {"name": "run_command", "args": {"CommandLine": "git status"}}
            ],
        },
    ]
    violations = detect_polling_loops(records)
    assert len(violations) == 0


def test_detect_polling_loops_violation():
    """Nhiều lần gọi manage_task(status) liên tiếp bị bắt vi phạm Reactive Wakeup."""
    records = [
        {
            "step_index": 1,
            "tool_calls": [
                {"name": "manage_task", "args": {"Action": "status", "TaskId": "task-10"}}
            ],
        },
        {
            "step_index": 2,
            "tool_calls": [
                {"name": "manage_task", "args": {"Action": "status", "TaskId": "task-10"}}
            ],
        },
        {
            "step_index": 3,
            "tool_calls": [
                {"name": "manage_task", "args": {"Action": "status", "TaskId": "task-10"}}
            ],
        },
    ]
    violations = detect_polling_loops(records)
    assert len(violations) == 1
    assert violations[0]["consecutive_count"] == 3
    assert violations[0]["step_indices"] == [1, 2, 3]
    assert "task-10" in violations[0]["task_ids"]


def test_detect_model_inheritance_waste_catches_critic_and_qa():
    """Bắt lỗi khi Critic hoặc QA Auditor dùng Model='inherit'."""
    records = [
        {
            "step_index": 1,
            "tool_calls": [
                {
                    "name": "invoke_subagent",
                    "args": {
                        "Subagents": [
                            {
                                "Role": "Code Critic",
                                "TypeName": "code_critic",
                                "Model": "inherit",
                            },
                            {
                                "Role": "QA Auditor",
                                "TypeName": "qa_auditor",
                                "Model": "inherit",
                            },
                        ]
                    },
                }
            ],
        }
    ]
    violations = detect_model_inheritance_waste(records)
    assert len(violations) == 2
    roles = [v["role"] for v in violations]
    assert "Code Critic" in roles
    assert "QA Auditor" in roles


def test_detect_model_inheritance_waste_allows_builder_and_flash():
    """Builder được phép inherit, Critic dùng flash thì không bị vi phạm."""
    records = [
        {
            "step_index": 1,
            "tool_calls": [
                {
                    "name": "invoke_subagent",
                    "args": {
                        "Subagents": [
                            {
                                "Role": "System Builder",
                                "TypeName": "builder",
                                "Model": "inherit",
                            },
                            {
                                "Role": "Compliance Critic",
                                "TypeName": "critic",
                                "Model": "flash",
                            },
                            {
                                "Role": "QA Checker",
                                "TypeName": "qa",
                                "Model": "flash_lite",
                            },
                        ]
                    },
                }
            ],
        }
    ]
    violations = detect_model_inheritance_waste(records)
    assert len(violations) == 0


def test_detect_view_file_redundancy():
    """Bắt lỗi đọc file lặp lại >= threshold."""
    records = [
        {
            "step_index": 1,
            "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "d:/project/GEMINI.md"}}],
        },
        {
            "step_index": 2,
            "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "d:/project/other.py"}}],
        },
        {
            "step_index": 3,
            "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "D:\\project\\GEMINI.md"}}],
        },
        {
            "step_index": 4,
            "tool_calls": [{"name": "view_file", "args": {"AbsolutePath": "d:/project/gemini.md"}}],
        },
    ]
    # Với threshold = 3, GEMINI.md bị đọc 3 lần -> vi phạm
    violations = detect_view_file_redundancy(records, threshold=3)
    assert len(violations) == 1
    assert violations[0]["count"] == 3
    assert violations[0]["step_indices"] == [1, 3, 4]

    # Với threshold = 4, không vi phạm
    assert len(detect_view_file_redundancy(records, threshold=4)) == 0


def test_calculate_context_growth():
    """Kiểm tra tính toán tăng trưởng context và token."""
    records = [
        {"step_index": i, "content": "a" * 400, "thinking": "b" * 400}
        for i in range(1, 10)
    ]
    growth = calculate_context_growth(records)
    assert growth["total_steps"] == 9
    assert growth["total_characters"] == 9 * 800
    assert growth["estimated_total_tokens"] == (9 * 800) // 4
    assert growth["growth_trend"] in ("STABLE", "MODERATE", "RAPID", "CRITICAL")


def test_diagnose_session_clean():
    """Phiên sạch hoàn toàn cho kết quả CLEAN."""
    records = [
        {
            "step_index": 1,
            "tool_calls": [
                {
                    "name": "invoke_subagent",
                    "args": {
                        "Subagents": [
                            {"Role": "Critic", "TypeName": "critic", "Model": "flash"}
                        ]
                    },
                }
            ],
            "content": "Running task",
        },
        {
            "step_index": 2,
            "tool_calls": [
                {"name": "view_file", "args": {"AbsolutePath": "d:/project/file.py"}}
            ],
            "content": "Reading file",
        },
    ]
    report = diagnose_session(records)
    assert report.verdict == "CLEAN"
    assert len(report.polling_violations) == 0
    assert len(report.model_waste_violations) == 0
    assert len(report.redundancy_violations) == 0
    assert "CLEAN" in report.summary()


def test_diagnose_session_excessive_waste_and_file_loading(tmp_path: Path):
    """Phiên lãng phí nặng cho kết quả EXCESSIVE_WASTE khi nạp từ file jsonl."""
    jsonl_file = tmp_path / "transcript.jsonl"
    lines = [
        # Polling loop 3 lần liên tiếp
        {"step_index": 1, "tool_calls": [{"name": "manage_task", "args": {"Action": "status", "TaskId": "t1"}}]},
        {"step_index": 2, "tool_calls": [{"name": "manage_task", "args": {"Action": "status", "TaskId": "t1"}}]},
        {"step_index": 3, "tool_calls": [{"name": "manage_task", "args": {"Action": "status", "TaskId": "t1"}}]},
        # Model waste
        {"step_index": 4, "tool_calls": [{"name": "invoke_subagent", "args": {"Role": "QA Auditor", "Model": "inherit"}}]},
    ]
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for item in lines:
            f.write(json.dumps(item) + "\n")

    report = diagnose_session(jsonl_file)
    assert report.verdict == "EXCESSIVE_WASTE"
    assert len(report.polling_violations) == 1
    assert len(report.model_waste_violations) == 1
    assert len(report.recommendations) >= 2
    assert "Zero-Polling" in report.summary()
