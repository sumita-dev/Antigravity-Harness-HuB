"""Unit tests for Policy Interceptor (Hard Policy Boundary)."""

import pytest
from harness.validators.policy_interceptor import (
    PolicyAction,
    PolicyDecision,
    evaluate_command_policy,
    is_command_safe,
)


def test_safe_commands_allowed():
    """Các lệnh shell thông thường an toàn phải được ALLOW."""
    safe_commands = [
        "pytest tests/ -q",
        "git status",
        "git diff HEAD~1",
        "python run_harness.py --task 'test task'",
        "ls -la",
        "dir",
        "npm test",
        "pip list",
        "echo 'Hello World'",
    ]
    for cmd in safe_commands:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.ALLOW, f"Expected ALLOW for safe command: {cmd}"
        assert is_command_safe(cmd) is True


def test_empty_command_allowed():
    """Lệnh rỗng trả về ALLOW."""
    decision = evaluate_command_policy("   ")
    assert decision.action == PolicyAction.ALLOW
    assert is_command_safe("   ") is True


def test_destructive_commands_blocked():
    """Các lệnh xóa hàng loạt, phá hủy hệ thống, drop database phải bị BLOCK."""
    destructive_commands = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -rf ..",
        "rm -rf *",
        "del /f /s /q C:\\Windows",
        "del /s /q *",
        "format C:",
        ":(){ :|:& };:",
        "DROP DATABASE production;",
        "DROP SCHEMA public CASCADE;",
        "DELETE FROM users WHERE 1=1;",
        "DELETE FROM orders;",
        "Remove-Item -Recurse -Force C:\\Windows",
        "Remove-Item -Force -Recurse C:\\Windows\\System32",
        "shutdown -h now",
        "kill -9 1",
    ]
    for cmd in destructive_commands:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.BLOCK, f"Expected BLOCK for destructive command: {cmd}, got: {decision.action}"
        assert is_command_safe(cmd) is False


def test_destructive_commands_warned():
    """Các lệnh có tính rủi ro nhưng có thể cần thiết trong dev/migration phải là WARN."""
    warning_commands = [
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git push origin main --force",
        "DROP TABLE temp_logs;",
        "TRUNCATE TABLE audit_cache;",
        "Remove-Item -Recurse .\\*",
    ]
    for cmd in warning_commands:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.WARN, f"Expected WARN for command: {cmd}, got: {decision.action}"
        assert is_command_safe(cmd) is True  # is_command_safe trả về True cho WARN


def test_sensitive_system_paths():
    """Kiểm tra việc truy cập vào đường dẫn hệ thống nhạy cảm."""
    # Write / delete on sensitive paths -> BLOCK
    block_cmds = [
        "rm /etc/passwd",
        "del C:\\Windows\\System32\\drivers\\etc\\hosts",
        "rm -f /boot/vmlinuz",
        "rmdir /s /q C:\\Windows",
    ]
    for cmd in block_cmds:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.BLOCK, f"Expected BLOCK for command targeting sensitive path: {cmd}"

    # Read-only or reference to sensitive paths -> WARN
    warn_cmds = [
        "cat /etc/passwd",
        "type C:\\Windows\\win.ini",
    ]
    for cmd in warn_cmds:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.WARN, f"Expected WARN for read command on sensitive path: {cmd}"


def test_sensitive_cwd_blocked():
    """Thực thi từ thư mục hệ thống nhạy cảm phải bị BLOCK."""
    decision = evaluate_command_policy("dir", cwd="C:\\Windows\\System32")
    assert decision.action == PolicyAction.BLOCK

    decision_posix = evaluate_command_policy("ls", cwd="/etc")
    assert decision_posix.action == PolicyAction.BLOCK


def test_stream_search_missing_path_warned():
    """Lệnh tìm kiếm stream (rg/grep) thiếu target path phải nhận cảnh báo WARN về STDIN hang."""
    warn_commands = [
        'rg -i "pattern"',
        'rg -i "pattern" -g "!*.pyc"',
        'rg "TODO"',
        'grep -rn "fixme"',
        'git status && rg -i "pattern"',
        'rg -i "pattern" | head -n 5',
    ]
    for cmd in warn_commands:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.WARN, f"Expected WARN for missing target path: {cmd}, got: {decision.action}"
        assert "STDIN" in decision.reason or "đường dẫn mục tiêu" in decision.reason
        assert is_command_safe(cmd) is True

    # Khi có target path cụ thể (như '.' hoặc thư mục), phải được ALLOW
    allowed_commands = [
        'rg -i "pattern" .',
        'rg -i "pattern" -g "!*.pyc" .',
        'rg "TODO" src/',
        'grep -rn "fixme" .',
        'cat file.txt | grep "pattern"',
    ]
    for cmd in allowed_commands:
        decision = evaluate_command_policy(cmd)
        assert decision.action == PolicyAction.ALLOW, f"Expected ALLOW for command with target path: {cmd}, got: {decision.action}"
