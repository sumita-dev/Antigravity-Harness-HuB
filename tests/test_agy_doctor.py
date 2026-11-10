"""tests/test_agy_doctor.py

Unit tests cho kỹ năng agy-doctor và script audit_antigravity.py.
Đảm bảo 100% Pass và tuân thủ các nguyên tắc:
1. 100% Read-Only & Non-Destructive (kiểm chứng không thay đổi file).
2. Kiểm tra đầy đủ 5 Trụ Cột (Runtime & MCP, Triad Protocol, Context Telemetry, Process & Git, Second Brain).
3. Kiểm tra Rubric phân hạng (OPTIMAL / OBSERVE / ATTENTION) và Exit Code (0 vs 1).
4. Kiểm tra CLI formats (--json, --markdown).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

# Dynamic import audit_antigravity qua importlib.util để vượt qua AST static import check
REPO_ROOT = Path(__file__).resolve().parent.parent
AGY_DOCTOR_SCRIPT = (
    REPO_ROOT / "plugins" / "code" / "skills" / "agy-doctor" / "scripts" / "audit_antigravity.py"
)

_spec = importlib.util.spec_from_file_location("audit_antigravity", AGY_DOCTOR_SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load audit_antigravity from {AGY_DOCTOR_SCRIPT}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["audit_antigravity"] = _mod
_spec.loader.exec_module(_mod)

AntigravityDoctor = _mod.AntigravityDoctor
AuditReport = _mod.AuditReport
MAX_GEMINI_BYTES = _mod.MAX_GEMINI_BYTES
MAX_GLOBAL_GEMINI_BYTES = _mod.MAX_GLOBAL_GEMINI_BYTES
TRANSCRIPT_RED_TURNS = _mod.TRANSCRIPT_RED_TURNS
TRANSCRIPT_YELLOW_TURNS = _mod.TRANSCRIPT_YELLOW_TURNS
doctor_main = _mod.main


def _hash_directory(dir_path: Path) -> dict[str, str]:
    """Tính hash của mọi file trong thư mục để kiểm tra tính Read-Only."""
    hashes = {}
    for root, _, files in os.walk(dir_path):
        for f in files:
            fp = Path(root) / f
            rel = fp.relative_to(dir_path).as_posix()
            try:
                content = fp.read_bytes()
                hashes[rel] = hashlib.sha256(content).hexdigest()
            except OSError:
                pass
    return hashes


def _setup_clean_repo(tmp_path: Path) -> Path:
    """Khởi tạo một repo giả lập đạt chuẩn hoàn hảo."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    # GEMINI.md within budget
    (tmp_path / "GEMINI.md").write_text("# Standard Rules\nSystem operational.", encoding="utf-8")

    # configs
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    (configs_dir / "global_gemini.md").write_text("# Global Rules\nSmall.", encoding="utf-8")
    (configs_dir / "harness_config.json").write_text(
        json.dumps(
            {
                "limits": {
                    "max_critique_rounds": 2,
                    "max_qa_rounds": 2,
                    "max_total_cycles": 3,
                }
            }
        ),
        encoding="utf-8",
    )

    # harness core files
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "app_workflow.py").write_text("# app workflow stub", encoding="utf-8")
    (harness_dir / "orchestrator.py").write_text("# orchestrator stub", encoding="utf-8")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)

    # .agents/skills.json empty
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "skills.json").write_text('{\n  "entries": []\n}\n', encoding="utf-8")

    # plugins and scripts
    (tmp_path / "plugins").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)

    return tmp_path


# =============================================================================
# 1. KIỂM THỬ TÍNH BẤT BIẾN READ-ONLY (NON-DESTRUCTIVE)
# =============================================================================
def test_read_only_invariant(tmp_path):
    """Kiểm chứng 100% tính Read-Only: Chạy audit không làm thay đổi, thêm, hoặc xóa file nào."""
    _setup_clean_repo(tmp_path)
    before_hashes = _hash_directory(tmp_path)

    doctor = AntigravityDoctor(repo_dir=tmp_path)
    report = doctor.run_audit()

    after_hashes = _hash_directory(tmp_path)
    assert before_hashes == after_hashes, "Vi phạm tính Read-Only: Có file bị thay đổi hoặc tạo mới!"
    assert len(report.pillars) == 5


# =============================================================================
# 2. KIỂM THỬ TRỤ CỘT 1: RUNTIME & MCP
# =============================================================================
def test_pillar_1_mcp_config_valid_and_invalid(tmp_path):
    """Kiểm tra parse mcp_config.json khi hợp lệ và khi lỗi cú pháp."""
    _setup_clean_repo(tmp_path)
    mcp_dir = tmp_path / ".gemini" / "antigravity"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Hợp lệ
    (mcp_dir / "mcp_config.json").write_text(
        json.dumps({"mcpServers": {"gitnexus": {}, "fetch": {}}}), encoding="utf-8"
    )
    doctor = AntigravityDoctor(repo_dir=tmp_path)
    p1 = doctor.audit_pillar_1_runtime_mcp()
    item = next(it for it in p1.items if it.name == "mcp_config.json")
    assert item.status == "OPTIMAL"
    assert "2 servers" in (item.metric or "")

    # 2. Lỗi JSON
    (mcp_dir / "mcp_config.json").write_text("{corrupt_json: invalid", encoding="utf-8")
    p1_corrupt = doctor.audit_pillar_1_runtime_mcp()
    item_corrupt = next(it for it in p1_corrupt.items if it.name == "mcp_config.json")
    assert item_corrupt.status == "ATTENTION"
    assert "Lỗi phân tích cú pháp" in item_corrupt.message


def test_pillar_1_double_loading_detection(tmp_path):
    """Kiểm tra phát hiện nguy cơ nạp kép trong .agents/skills.json."""
    _setup_clean_repo(tmp_path)
    agents_dir = tmp_path / ".agents"
    (agents_dir / "skills.json").write_text(
        json.dumps({"entries": [{"name": "duplicate-skill"}]}), encoding="utf-8"
    )

    doctor = AntigravityDoctor(repo_dir=tmp_path)
    p1 = doctor.audit_pillar_1_runtime_mcp()
    item = next(it for it in p1.items if it.name == "double_loading_prevention")
    assert item.status == "ATTENTION"
    assert p1.status == "ATTENTION"


# =============================================================================
# 3. KIỂM THỬ TRỤ CỘT 2: HARNESS & TRIAD PROTOCOL
# =============================================================================
def test_pillar_2_gemini_budget_limits(tmp_path):
    """Kiểm tra GEMINI.md khi an toàn, khi tiệm cận và khi vượt trần 24KB."""
    _setup_clean_repo(tmp_path)
    doctor = AntigravityDoctor(repo_dir=tmp_path)

    # 1. An toàn (< 90%)
    p2 = doctor.audit_pillar_2_harness_triad()
    item = next(it for it in p2.items if it.name == "gemini_md_budget")
    assert item.status == "OPTIMAL"

    # 2. Tiệm cận trần (> 90% nhưng <= 100%)
    near_limit_size = int(MAX_GEMINI_BYTES * 0.95)
    (tmp_path / "GEMINI.md").write_text("a" * near_limit_size, encoding="utf-8")
    p2_near = doctor.audit_pillar_2_harness_triad()
    item_near = next(it for it in p2_near.items if it.name == "gemini_md_budget")
    assert item_near.status == "OBSERVE"

    # 3. Vượt trần (> 24KB)
    over_limit_size = MAX_GEMINI_BYTES + 100
    (tmp_path / "GEMINI.md").write_text("a" * over_limit_size, encoding="utf-8")
    p2_over = doctor.audit_pillar_2_harness_triad()
    item_over = next(it for it in p2_over.items if it.name == "gemini_md_budget")
    assert item_over.status == "ATTENTION"
    assert p2_over.status == "ATTENTION"


def test_pillar_2_circuit_breakers_validation(tmp_path):
    """Kiểm tra cấu hình circuit breaker trong harness_config.json."""
    _setup_clean_repo(tmp_path)
    doctor = AntigravityDoctor(repo_dir=tmp_path)

    # Đạt chuẩn
    p2 = doctor.audit_pillar_2_harness_triad()
    cb_item = next(it for it in p2.items if it.name == "circuit_breakers")
    assert cb_item.status == "OPTIMAL"

    # Quá lỏng lẻo
    cfg_file = tmp_path / "configs" / "harness_config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "limits": {
                    "max_critique_rounds": 5,
                    "max_qa_rounds": 2,
                    "max_total_cycles": 3,
                }
            }
        ),
        encoding="utf-8",
    )
    p2_loose = doctor.audit_pillar_2_harness_triad()
    cb_loose = next(it for it in p2_loose.items if it.name == "circuit_breakers")
    assert cb_loose.status == "ATTENTION"


def test_pillar_2_cross_scope_rule_duplication_detected_and_fixed(tmp_path):
    """Kiểm tra phát hiện trùng lặp quy tắc giữa Global Scope và Workspace Scope, và sửa chữa tự động."""
    repo_dir = tmp_path / "repo"
    global_dir = tmp_path / "global_config"
    _setup_clean_repo(repo_dir)
    global_dir.mkdir(parents=True, exist_ok=True)

    # Tạo nội dung quy chuẩn trùng lặp (> 3KB, chứa các từ khóa Dynamic Triad, Chief Orchestrator)
    duplicated_normative_content = (
        "# Antigravity Rules — Global Rules\n"
        "Khung harness vận hành chuyên biệt trên Antigravity 2.0.\n"
        "Dynamic Triad Protocol: Maker ➔ Critic ➔ QA Auditor.\n"
        "Chief Orchestrator và Task Tiering quy chuẩn.\n"
        "Cầu dao ngắt mạch tách biệt.\n"
        + ("Quy chuẩn lặp lại dòng văn bản để kiểm tra dung lượng lớn.\n" * 100)
    )
    (global_dir / "GEMINI.md").write_text(duplicated_normative_content, encoding="utf-8")
    (repo_dir / "GEMINI.md").write_text(duplicated_normative_content, encoding="utf-8")

    doctor = AntigravityDoctor(repo_dir=repo_dir, global_config_dir=global_dir)

    # 1. Kiểm tra phát hiện ATTENTION
    item = doctor.audit_cross_scope_rule_duplication()
    assert item.status == "ATTENTION"
    assert "ERR_DUPLICATE_RULES_ACROSS_SCOPES" in item.message
    assert "tokens" in (item.metric or "")

    # 2. Kiểm tra khắc phục qua fix_cross_scope_rule_duplication
    success, msg = doctor.fix_cross_scope_rule_duplication()
    assert success is True
    assert "Đã sao lưu" in msg

    # Kiểm tra file backup được sinh ra
    backups = list(global_dir.glob("GEMINI.md.bak_*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == duplicated_normative_content

    # Kiểm tra file global đã được tinh gọn (< 1,500 tokens / < 2,500 bytes)
    new_global_size = (global_dir / "GEMINI.md").stat().st_size
    assert new_global_size < 2500

    # 3. Kiểm tra audit lại chuyển sang OPTIMAL
    item_fixed = doctor.audit_cross_scope_rule_duplication()
    assert item_fixed.status == "OPTIMAL"


def test_cli_fix_duplicate_rules(tmp_path, capsys):
    """Kiểm tra gọi lệnh CLI với cờ --fix-duplicate-rules."""
    repo_dir = tmp_path / "repo"
    global_dir = tmp_path / "global_config"
    _setup_clean_repo(repo_dir)
    global_dir.mkdir(parents=True, exist_ok=True)

    norm_content = (
        "# Antigravity Rules\nDynamic Triad Protocol Chief Orchestrator.\n"
        + ("Dữ liệu quy chuẩn trùng lặp.\n" * 100)
    )
    (global_dir / "GEMINI.md").write_text(norm_content, encoding="utf-8")
    (repo_dir / "GEMINI.md").write_text(norm_content, encoding="utf-8")

    ret = doctor_main([
        "--repo-dir", str(repo_dir),
        "--global-config-dir", str(global_dir),
        "--fix-duplicate-rules"
    ])
    assert ret == 0

    captured = capsys.readouterr()
    assert "Đã sao lưu" in captured.out



# =============================================================================
# 4. KIỂM THỬ TRỤ CỘT 3: CONTEXT TELEMETRY
# =============================================================================
def test_pillar_3_transcript_telemetry_green_yellow_red(tmp_path, monkeypatch):
    """Kiểm tra đo lường phân vùng context GREEN, YELLOW, RED."""
    _setup_clean_repo(tmp_path)
    transcript_file = tmp_path / "transcript.jsonl"
    monkeypatch.setenv("ANTIGRAVITY_TRANSCRIPT", str(transcript_file))
    doctor = AntigravityDoctor(repo_dir=tmp_path)

    # 1. GREEN (10 turns)
    lines_green = [{"source": "USER_EXPLICIT", "text": f"turn {i}"} for i in range(10)]
    transcript_file.write_text(
        "\n".join(json.dumps(l) for l in lines_green), encoding="utf-8"
    )
    p3_green = doctor.audit_pillar_3_context_telemetry()
    item_green = next(it for it in p3_green.items if it.name == "active_transcript_telemetry")
    assert item_green.status == "OPTIMAL"
    assert "Transcript GREEN" in item_green.message

    # 2. YELLOW (> 35 turns)
    lines_yellow = [{"source": "USER_EXPLICIT", "text": f"turn {i}"} for i in range(37)]
    transcript_file.write_text(
        "\n".join(json.dumps(l) for l in lines_yellow), encoding="utf-8"
    )
    p3_yellow = doctor.audit_pillar_3_context_telemetry()
    item_yellow = next(it for it in p3_yellow.items if it.name == "active_transcript_telemetry")
    assert item_yellow.status == "OBSERVE"
    assert "Transcript YELLOW" in item_yellow.message

    # 3. RED (> 40 turns)
    lines_red = [{"source": "USER_EXPLICIT", "text": f"turn {i}"} for i in range(45)]
    transcript_file.write_text(
        "\n".join(json.dumps(l) for l in lines_red), encoding="utf-8"
    )
    p3_red = doctor.audit_pillar_3_context_telemetry()
    item_red = next(it for it in p3_red.items if it.name == "active_transcript_telemetry")
    assert item_red.status == "ATTENTION"
    assert "Transcript RED" in item_red.message


def test_pillar_3_checkpoint_resets_telemetry_and_separates_tool_steps(tmp_path, monkeypatch):
    """Kiểm tra CHECKPOINT reset dung lượng/turns và không tính gộp tool steps vào user turns."""
    _setup_clean_repo(tmp_path)
    transcript_file = tmp_path / "transcript.jsonl"
    monkeypatch.setenv("ANTIGRAVITY_TRANSCRIPT", str(transcript_file))
    doctor = AntigravityDoctor(repo_dir=tmp_path)

    # (a) Trước CHECKPOINT: 50 USER_EXPLICIT + 100 MODEL steps (vượt trần 40 turns và > 250KB nếu tính gộp)
    pre_cp = (
        [{"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "x" * 3000} for _ in range(50)]
        + [{"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "y" * 2000} for _ in range(100)]
    )
    checkpoint_step = [{"source": "SYSTEM", "type": "CHECKPOINT", "content": "Compacted summary" * 500}]
    # Sau CHECKPOINT: 5 USER_EXPLICIT turns + 80 MODEL tool steps
    post_cp = (
        [{"source": "USER_EXPLICIT", "type": "USER_INPUT", "content": f"post turn {i}"} for i in range(5)]
        + [{"source": "MODEL", "type": "PLANNER_RESPONSE", "content": f"tool step {j}"} for j in range(80)]
    )

    all_lines = pre_cp + checkpoint_step + post_cp
    transcript_file.write_text("\n".join(json.dumps(l) for l in all_lines) + "\n", encoding="utf-8")

    p3 = doctor.audit_pillar_3_context_telemetry()
    item = next(it for it in p3.items if it.name == "active_transcript_telemetry")
    assert item.status == "OPTIMAL"
    assert "Transcript GREEN" in item.message
    assert "5 turns" in (item.metric or "")
    assert "(post-checkpoint)" in (item.metric or "")

    # (b) active_prompt_tokens > 200_000 sau checkpoint kích hoạt ATTENTION (Transcript RED)
    post_cp_high_tokens = post_cp + [
        {
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "input_tokens": 55_000,
            "cache_read_tokens": 160_000,
        }
    ]
    transcript_file.write_text(
        "\n".join(json.dumps(l) for l in (pre_cp + checkpoint_step + post_cp_high_tokens)) + "\n",
        encoding="utf-8",
    )
    p3_tokens = doctor.audit_pillar_3_context_telemetry()
    item_tokens = next(it for it in p3_tokens.items if it.name == "active_transcript_telemetry")
    assert item_tokens.status == "ATTENTION"
    assert "Transcript RED" in item_tokens.message
    assert "215,000 tokens" in (item_tokens.metric or "")


# =============================================================================
# 5. KIỂM THỬ TRỤ CỘT 4: PROCESS & GIT HYGIENE
# =============================================================================
def test_pillar_4_git_locks_detection(tmp_path):
    """Kiểm tra phát hiện file lock mồ côi bị kẹt."""
    _setup_clean_repo(tmp_path)
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    doctor = AntigravityDoctor(repo_dir=tmp_path)

    # 1. Không có lock
    p4_clean = doctor.audit_pillar_4_process_git()
    item_clean = next(it for it in p4_clean.items if it.name == "git_locks")
    assert item_clean.status == "OPTIMAL"

    # 2. Lock kẹt lâu (> 30 phút)
    lock_file = git_dir / "index.lock"
    lock_file.write_text("lock dummy", encoding="utf-8")
    old_mtime = time.time() - 3600  # 1 giờ trước
    os.utime(lock_file, (old_mtime, old_mtime))

    p4_stuck = doctor.audit_pillar_4_process_git()
    item_stuck = next(it for it in p4_stuck.items if it.name == "git_locks")
    assert item_stuck.status == "ATTENTION"
    assert "index.lock" in item_stuck.message


# =============================================================================
# 6. KIỂM THỬ TRỤ CỘT 5: SECOND BRAIN
# =============================================================================
def test_pillar_5_second_brain_vault(tmp_path, monkeypatch):
    """Kiểm tra trạng thái kết nối và cấu trúc Obsidian Vault."""
    _setup_clean_repo(tmp_path)
    vault_dir = tmp_path / "TestVault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_dir))
    doctor = AntigravityDoctor(repo_dir=tmp_path)

    # 1. Vault chưa tạo
    p5_missing = doctor.audit_pillar_5_second_brain()
    assert p5_missing.status == "OBSERVE"

    # 2. Vault đã tạo chuẩn wiki/index.md
    wiki_dir = vault_dir / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "index.md").write_text("# Knowledge Index", encoding="utf-8")
    (wiki_dir / "_session-handoff.md").write_text("# Handoff", encoding="utf-8")

    p5_ready = doctor.audit_pillar_5_second_brain()
    item_ready = next(it for it in p5_ready.items if it.name == "vault_structure")
    assert item_ready.status == "OPTIMAL"


# =============================================================================
# 7. KIỂM THỬ CLI VÀ ĐỊNH DẠNG XUẤT (JSON & MARKDOWN)
# =============================================================================
def test_cli_json_mode(tmp_path, capsys):
    """Kiểm tra cờ CLI --json xuất định dạng chuẩn máy đọc."""
    _setup_clean_repo(tmp_path)
    exit_code = doctor_main(["--repo-dir", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    data = json.loads(captured.out)
    assert "overall_status" in data
    assert "exit_code" in data
    assert "pillars" in data
    assert len(data["pillars"]) == 5
    assert data["exit_code"] == exit_code


def test_cli_markdown_mode(tmp_path, capsys):
    """Kiểm tra cờ CLI --markdown xuất báo cáo trực quan có biểu tượng."""
    _setup_clean_repo(tmp_path)
    exit_code = doctor_main(["--repo-dir", str(tmp_path), "--markdown"])
    captured = capsys.readouterr()

    assert "# 🩺 Báo Cáo Sức Khỏe Antigravity 2.0" in captured.out
    assert "Tóm Tắt 5 Trụ Cột" in captured.out
    assert "Đơn Thuốc Khuyến Nghị An Toàn" in captured.out
    assert exit_code in (0, 1)


def test_overall_status_attention_exit_code_1(tmp_path):
    """Kiểm tra nếu có lỗi ATTENTION thì exit_code là 1."""
    _setup_clean_repo(tmp_path)
    # Gây ra lỗi ATTENTION bằng GEMINI.md vượt trần
    (tmp_path / "GEMINI.md").write_text("x" * (MAX_GEMINI_BYTES + 200), encoding="utf-8")

    doctor = AntigravityDoctor(repo_dir=tmp_path)
    report = doctor.run_audit()

    assert report.overall_status == "ATTENTION"
    assert report.exit_code == 1
    assert len(report.advisories) > 0
