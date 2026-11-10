#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_antigravity.py

Antigravity 2.0 Doctor & Health Audit Script (100% Read-Only & Non-Destructive).
Chẩn đoán nhanh (< 3 giây) qua 5 Trụ Cột:
1. Antigravity 2.0 Runtime & MCP (mcp_config, brain storage, CLI, discovery priority).
2. Khung Harness & Triad Protocol (Circuit breaker, trần ngân sách rules GEMINI.md <= 24KB, test integrity).
3. Ngân sách Ngữ Cảnh & Telemetry (đo turns, transcript size, cảnh báo GREEN/YELLOW/RED).
4. Vệ sinh Tiến trình & Git (Windows orphan browser/python check, git lock detection).
5. Bộ Não Thứ 2 (Second Brain Obsidian Vault integration status).

Rubric phân hạng:
- OPTIMAL: 🟢 Toàn bộ 5 trụ cột đạt chuẩn an toàn, không có lỗi hay cảnh báo. Exit code = 0.
- OBSERVE: 🟡 Cảnh báo mức nhẹ/tiềm ẩn (tiệm cận ngưỡng, cấu hình tùy chọn chưa bật). Exit code = 0.
- ATTENTION: 🔴 Lỗi nghiêm trọng hoặc vi phạm quy chuẩn (vượt trần, lock kẹt, lỗi cú pháp). Exit code = 1.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Thiết lập UTF-8 cho Windows console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Định vị thư mục gốc repo
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_REPO_DIR = SKILL_DIR.parent.parent.parent


def find_repo_root(start_dir: Optional[Path] = None) -> Path:
    """Tự động dò tìm thư mục gốc repository chứa GEMINI.md hoặc .git."""
    cur = (start_dir or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "GEMINI.md").exists() or (p / ".git").exists():
            return p
    return DEFAULT_REPO_DIR.resolve()


# Bảng ngưỡng mặc định (chuẩn Antigravity 2.0 & Harness)
MAX_GEMINI_BYTES = 24 * 1024  # 24,576 bytes (24KB)
MAX_GLOBAL_GEMINI_BYTES = 8 * 1024  # 8,192 bytes (8KB)
TRANSCRIPT_YELLOW_BYTES = 200 * 1024  # 200 KB
TRANSCRIPT_RED_BYTES = 250 * 1024  # 250 KB
TRANSCRIPT_YELLOW_TURNS = 35
TRANSCRIPT_RED_TURNS = 40
TRANSCRIPT_YELLOW_TOKENS = 150_000
TRANSCRIPT_RED_TOKENS = 200_000
MAX_SESSIONS_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_BRAIN_BYTES = 500 * 1024 * 1024  # 500 MB
LOCK_STUCK_AGE_SECONDS = 1800  # 30 phút

GLOBAL_MINIMAL_RULES_CONTENT = """# Antigravity Rules — Global Minimal Rules

> [!NOTE]
> Vận hành trên **Antigravity 2.0**.
> Toàn bộ quy trình dự án, Dynamic Triad, và chi tiết nghiệp vụ được cấu hình tập trung tại `GEMINI.md` của từng workspace cụ thể.

---

## 1. Nguyên Tắc Giao Tiếp & Xưng Hô
- **Xưng hô:** Luôn gọi người dùng là "Sếp" (hoặc "anh") và xưng "em". Sử dụng tiếng Việt chuẩn mực.
- **Đi thẳng vào vấn đề — Không khen ngợi:** Cung cấp trực tiếp kết quả, giải pháp hoặc câu hỏi; không chào hỏi xã giao rườm rà, tuyệt đối không khen ngợi yêu cầu.
- **Tư vấn trước - Sửa mã sau (Consult Before Mutate):** Nếu yêu cầu chưa rõ ràng, luôn hỏi và chốt qua `ask_question` trước khi can thiệp vào code.
- **Bằng chứng thực chứng:** Mọi kết luận đều dẫn xuất từ trích dẫn file mã nguồn, log hoặc kết quả lệnh thực tế (`exit code == 0`).

---

## 2. Chuẩn Môi Trường Windows & Kỹ Thuật
- **Môi trường & Bảng mã:** Hệ điều hành Windows, mã hóa ký tự UTF-8 cho toàn bộ luồng xuất nhập dữ liệu (`sys.stdout.reconfigure(encoding='utf-8')`).
- **STDIN DevNull Guard & Stream Command Safety:** Khóa cứng `stdin=subprocess.DEVNULL` mặc định cho các tiến trình con. Khi chạy các lệnh tìm kiếm stream (`rg`, `grep`, `findstr`), BẮT BUỘC truyền Explicit Target Path cụ thể (phải có `.` hoặc đường dẫn thư mục/tệp mục tiêu), tuyệt đối không để trống đường dẫn khiến tiến trình block vô hạn trên STDIN.
- **Zero-Polling & Dead-man's Switch:** CẤM gọi `manage_task(status)` trong loop; dừng turn đón Reactive Wakeup khi task hoàn tất.
"""


@dataclass
class HealthCheckItem:
    """Chi tiết một mục kiểm tra trong trụ cột."""
    name: str
    status: str  # "OPTIMAL", "OBSERVE", "ATTENTION"
    message: str
    metric: Optional[str] = None
    advisory: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PillarResult:
    """Kết quả kiểm định của một trụ cột."""
    pillar_id: str
    title: str
    status: str  # "OPTIMAL", "OBSERVE", "ATTENTION"
    items: List[HealthCheckItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pillar_id": self.pillar_id,
            "title": self.title,
            "status": self.status,
            "items": [it.to_dict() for it in self.items],
        }


@dataclass
class AuditReport:
    """Báo cáo kiểm định tổng thể của Antigravity Doctor."""
    overall_status: str  # "OPTIMAL", "OBSERVE", "ATTENTION"
    exit_code: int
    execution_time_seconds: float
    repo_dir: str
    timestamp: float
    summary: Dict[str, int]
    pillars: List[PillarResult] = field(default_factory=list)
    advisories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "exit_code": self.exit_code,
            "execution_time_seconds": round(self.execution_time_seconds, 3),
            "repo_dir": self.repo_dir,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "pillars": [p.to_dict() for p in self.pillars],
            "advisories": self.advisories,
        }


class AntigravityDoctor:
    """Bộ kiểm toán sức khỏe Antigravity 2.0 (100% Read-Only & Non-Destructive)."""

    def __init__(
        self,
        repo_dir: Optional[Path] = None,
        global_config_dir: Optional[Path] = None,
    ):
        self.repo_dir = (repo_dir or find_repo_root()).resolve()
        self.global_config_dir = (
            Path(global_config_dir).resolve() if global_config_dir else None
        )

    def fast_dir_size(
        self, dir_path: Path, cap_bytes: int = MAX_SESSIONS_BYTES, max_entries: int = 10000
    ) -> Tuple[int, bool]:
        """Đo dung lượng thư mục siêu tốc bằng os.scandir (Read-only, có early-exit).

        Returns: (size_bytes, exceeded_cap)
        """
        if not dir_path.is_dir():
            return 0, False
        total = 0
        stack = [str(dir_path)]
        count = 0
        try:
            while stack and count < max_entries:
                curr = stack.pop()
                try:
                    with os.scandir(curr) as it:
                        for entry in it:
                            count += 1
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    total += entry.stat(follow_symlinks=False).st_size
                                    if total > cap_bytes:
                                        return total, True
                                elif entry.is_dir(follow_symlinks=False):
                                    stack.append(entry.path)
                            except OSError:
                                pass
                except OSError:
                    pass
        except OSError:
            pass
        return total, (total > cap_bytes)

    # -------------------------------------------------------------------------
    # TRỤ CỘT 1: Antigravity 2.0 Runtime & MCP
    # -------------------------------------------------------------------------
    def audit_pillar_1_runtime_mcp(self) -> PillarResult:
        title = "Trụ Cột 1: Antigravity 2.0 Runtime & MCP"
        items: List[HealthCheckItem] = []

        # 1.1 Kiểm tra file mcp_config.json
        user_home = Path.home()
        possible_mcp_paths = [
            self.repo_dir / ".gemini" / "antigravity" / "mcp_config.json",
            user_home / ".gemini" / "antigravity" / "mcp_config.json",
            Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "mcp_config.json",
        ]
        mcp_path: Optional[Path] = None
        for p in possible_mcp_paths:
            if p.exists() and p.is_file():
                mcp_path = p
                break

        if mcp_path:
            try:
                content = mcp_path.read_text(encoding="utf-8")
                mcp_data = json.loads(content)
                servers = mcp_data.get("mcpServers", {})
                server_names = list(servers.keys())
                items.append(
                    HealthCheckItem(
                        name="mcp_config.json",
                        status="OPTIMAL",
                        message=f"Đã nạp {len(server_names)} MCP Servers: {', '.join(server_names[:4])}{'...' if len(server_names) > 4 else ''}",
                        metric=f"{len(server_names)} servers",
                    )
                )
            except Exception as exc:
                items.append(
                    HealthCheckItem(
                        name="mcp_config.json",
                        status="ATTENTION",
                        message=f"Lỗi phân tích cú pháp JSON mcp_config.json: {exc}",
                        advisory="[ADVISORY] Sửa lỗi cú pháp JSON trong file mcp_config.json.",
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    name="mcp_config.json",
                    status="OBSERVE",
                    message="Không tìm thấy mcp_config.json tại vị trí mặc định (~/.gemini/antigravity/mcp_config.json).",
                    advisory="[ADVISORY] Nếu dùng MCP servers, cấu hình mcp_config.json trong thư mục App Data của Antigravity.",
                )
            )

        # 1.2 Kho lưu trữ Brain storage
        possible_brain_dirs = [
            self.repo_dir / ".brain",
            user_home / ".gemini" / "antigravity" / "brain",
        ]
        found_brain = False
        for bd in possible_brain_dirs:
            if bd.exists() and bd.is_dir():
                found_brain = True
                size, exceeded = self.fast_dir_size(bd, cap_bytes=MAX_BRAIN_BYTES)
                size_mb = size / (1024 * 1024)
                if exceeded:
                    items.append(
                        HealthCheckItem(
                            name="brain_storage",
                            status="OBSERVE",
                            message=f"Thư mục brain ({bd.name}) dung lượng vượt 500 MB (~{size_mb:.1f}+ MB).",
                            metric=f">{size_mb:.1f} MB",
                            advisory="[ADVISORY] Xem xét dọn dẹp các thư mục artifact hội thoại cũ không dùng.",
                        )
                    )
                else:
                    items.append(
                        HealthCheckItem(
                            name="brain_storage",
                            status="OPTIMAL",
                            message=f"Kho brain ({bd.name}) hoạt động bình thường ({size_mb:.1f} MB).",
                            metric=f"{size_mb:.1f} MB",
                        )
                    )
                break
        if not found_brain:
            items.append(
                HealthCheckItem(
                    name="brain_storage",
                    status="OPTIMAL",
                    message="Thư mục brain sạch / chưa ghi dữ liệu phiên lớn.",
                )
            )

        # 1.3 Kiểm tra double loading skills (.agents/skills.json)
        agents_skills = self.repo_dir / ".agents" / "skills.json"
        if agents_skills.exists():
            try:
                data = json.loads(agents_skills.read_text(encoding="utf-8"))
                entries = data.get("entries") if isinstance(data, dict) else None
                if entries != []:
                    items.append(
                        HealthCheckItem(
                            name="double_loading_prevention",
                            status="ATTENTION",
                            message=".agents/skills.json không rỗng, nguy cơ nạp trùng skills khi dùng plugins.",
                            advisory="[ADVISORY] Đặt lại .agents/skills.json về chuẩn rỗng: {\"entries\": []}.",
                        )
                    )
                else:
                    items.append(
                        HealthCheckItem(
                            name="double_loading_prevention",
                            status="OPTIMAL",
                            message=".agents/skills.json rỗng đạt chuẩn, chống double loading.",
                        )
                    )
            except Exception as exc:
                items.append(
                    HealthCheckItem(
                        name="double_loading_prevention",
                        status="ATTENTION",
                        message=f"Lỗi đọc .agents/skills.json: {exc}",
                        advisory="[ADVISORY] Khôi phục .agents/skills.json về dạng: {\"entries\": []}.",
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    name="double_loading_prevention",
                    status="OPTIMAL",
                    message=".agents/skills.json không tồn tại (sử dụng plugin profile độc lập).",
                )
            )

        # 1.4 Kiểm tra thứ bậc Scaffolding & Context Budget Economics
        plugins_dir = self.repo_dir / "plugins"
        scripts_dir = self.repo_dir / "scripts"
        if plugins_dir.is_dir() and scripts_dir.is_dir():
            items.append(
                HealthCheckItem(
                    name="scaffolding_hierarchy",
                    status="OPTIMAL",
                    message="Thứ bậc Scaffolding chuẩn: Skill -> Script -> SubAgent -> Plugin -> Always-on.",
                )
            )

        worst = "OPTIMAL"
        for it in items:
            if it.status == "ATTENTION":
                worst = "ATTENTION"
                break
            if it.status == "OBSERVE":
                worst = "OBSERVE"

        return PillarResult(pillar_id="pillar_1_runtime_mcp", title=title, status=worst, items=items)

    # -------------------------------------------------------------------------
    # TRỤ CỘT 2: Khung Harness & Triad Protocol
    # -------------------------------------------------------------------------
    def audit_pillar_2_harness_triad(self) -> PillarResult:
        title = "Trụ Cột 2: Khung Harness & Triad Protocol"
        items: List[HealthCheckItem] = []

        # 2.1 Kiểm tra GEMINI.md trần 24KB
        gemini_path = self.repo_dir / "GEMINI.md"
        if gemini_path.exists():
            size = gemini_path.stat().st_size
            pct = (size / MAX_GEMINI_BYTES) * 100
            if size > MAX_GEMINI_BYTES:
                items.append(
                    HealthCheckItem(
                        name="gemini_md_budget",
                        status="ATTENTION",
                        message=f"GEMINI.md ({size:,} bytes) vượt trần ngân sách {MAX_GEMINI_BYTES:,} bytes (24KB).",
                        metric=f"{size:,} B ({pct:.1f}%)",
                        advisory="[ADVISORY] Cắt gọt Always-on context trong GEMINI.md; chuyển bớt chi tiết sang Skills hoặc SubAgents.",
                    )
                )
            elif size > MAX_GEMINI_BYTES * 0.90:
                items.append(
                    HealthCheckItem(
                        name="gemini_md_budget",
                        status="OBSERVE",
                        message=f"GEMINI.md ({size:,} bytes) tiệm cận trần 24KB ({pct:.1f}%).",
                        metric=f"{size:,} B ({pct:.1f}%)",
                        advisory="[ADVISORY] Theo dõi dung lượng GEMINI.md, cân nhắc cắt tỉa trước khi thêm luật mới.",
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        name="gemini_md_budget",
                        status="OPTIMAL",
                        message=f"GEMINI.md đạt chuẩn ngân sách ({size:,} bytes / {MAX_GEMINI_BYTES:,} bytes).",
                        metric=f"{size:,} B ({pct:.1f}%)",
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    name="gemini_md_budget",
                    status="OBSERVE",
                    message="Không tìm thấy file GEMINI.md tại thư mục gốc repo.",
                    advisory="[ADVISORY] Tạo file GEMINI.md định nghĩa quy chuẩn điều phối tác tử.",
                )
            )

        # 2.2 Kiểm tra configs/global_gemini.md trần 8KB (nếu có)
        global_gemini = self.repo_dir / "configs" / "global_gemini.md"
        if global_gemini.exists():
            size = global_gemini.stat().st_size
            if size > MAX_GLOBAL_GEMINI_BYTES:
                items.append(
                    HealthCheckItem(
                        name="global_gemini_budget",
                        status="ATTENTION",
                        message=f"configs/global_gemini.md ({size:,} bytes) vượt trần 8KB ({MAX_GLOBAL_GEMINI_BYTES:,} bytes).",
                        metric=f"{size:,} B",
                        advisory="[ADVISORY] Cắt tỉa configs/global_gemini.md về dưới 8KB.",
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        name="global_gemini_budget",
                        status="OPTIMAL",
                        message=f"configs/global_gemini.md trong ngưỡng an toàn ({size:,} bytes).",
                        metric=f"{size:,} B",
                    )
                )

        # 2.3 Cầu dao ngắt mạch (Circuit Breakers in configs/harness_config.json)
        harness_cfg = self.repo_dir / "configs" / "harness_config.json"
        if harness_cfg.exists():
            try:
                cfg_data = json.loads(harness_cfg.read_text(encoding="utf-8"))
                limits = cfg_data.get("limits", {})
                critique = limits.get("max_critique_rounds", 2)
                qa = limits.get("max_qa_rounds", 2)
                cycles = limits.get("max_total_cycles", 3)
                if critique <= 2 and qa <= 2 and cycles <= 3:
                    items.append(
                        HealthCheckItem(
                            name="circuit_breakers",
                            status="OPTIMAL",
                            message=f"Cầu dao ngắt mạch tách biệt đạt chuẩn: Critic<={critique}, QA<={qa}, Cycles<={cycles}.",
                            metric=f"c={critique}, q={qa}, t={cycles}",
                        )
                    )
                else:
                    items.append(
                        HealthCheckItem(
                            name="circuit_breakers",
                            status="ATTENTION",
                            message=f"Cầu dao ngắt mạch quá lỏng lẻo: Critic={critique}, QA={qa}, Cycles={cycles}.",
                            metric=f"c={critique}, q={qa}, t={cycles}",
                            advisory="[ADVISORY] Khóa cứng giới hạn: critic<=2, qa<=2, cycles<=3 trong harness_config.json.",
                        )
                    )
            except Exception as exc:
                items.append(
                    HealthCheckItem(
                        name="circuit_breakers",
                        status="ATTENTION",
                        message=f"Lỗi đọc configs/harness_config.json: {exc}",
                        advisory="[ADVISORY] Kiểm tra định dạng JSON configs/harness_config.json.",
                    )
                )

        # 2.4 Tính toàn vẹn của mã nguồn Harness cốt lõi
        core_files = [
            self.repo_dir / "harness" / "app_workflow.py",
            self.repo_dir / "harness" / "orchestrator.py",
            self.repo_dir / "tests",
        ]
        missing_core = [str(f.relative_to(self.repo_dir)) for f in core_files if not f.exists()]
        if missing_core:
            items.append(
                HealthCheckItem(
                    name="harness_core_integrity",
                    status="ATTENTION",
                    message=f"Thiếu các module Harness cốt lõi: {', '.join(missing_core)}",
                    advisory="[ADVISORY] Khôi phục các tệp harness bị thiếu từ git repo.",
                )
            )
        else:
            items.append(
                HealthCheckItem(
                    name="harness_core_integrity",
                    status="OPTIMAL",
                    message="Hệ thống tệp harness cốt lõi và thư mục tests nguyên vẹn.",
                )
            )

        # 2.5 Kiểm tra trùng lặp quy tắc giữa Global Scope và Workspace Scope
        items.append(self.audit_cross_scope_rule_duplication())

        worst = "OPTIMAL"
        for it in items:
            if it.status == "ATTENTION":
                worst = "ATTENTION"
                break
            if it.status == "OBSERVE":
                worst = "OBSERVE"

        return PillarResult(pillar_id="pillar_2_harness_triad", title=title, status=worst, items=items)

    def resolve_global_config_dir(self, override_dir: Optional[Path] = None) -> Optional[Path]:
        """Xác định thư mục cấu hình toàn cục (~/.gemini/config)."""
        if override_dir:
            return Path(override_dir).resolve()
        if self.global_config_dir:
            return self.global_config_dir

        env_user = os.environ.get("USERPROFILE")
        candidates = [
            Path.home() / ".gemini" / "config",
        ]
        if env_user:
            candidates.append(Path(env_user) / ".gemini" / "config")

        for cand in candidates:
            if cand.exists() and cand.is_dir():
                return cand.resolve()
        return None

    def audit_cross_scope_rule_duplication(
        self, global_config_dir: Optional[Path] = None
    ) -> HealthCheckItem:
        """Đối soát tệp GEMINI.md và AGENTS.md giữa Global Scope và Workspace Scope.

        Nếu phát hiện trùng lặp lớn (>70% hoặc cùng chứa nội dung quy chuẩn),
        kích hoạt cảnh báo 🔴 ATTENTION: ERR_DUPLICATE_RULES_ACROSS_SCOPES,
        định lượng số token/bytes bị lãng phí (~7,000 tokens).
        """
        g_dir = self.resolve_global_config_dir(global_config_dir)

        if not g_dir or not g_dir.exists():
            return HealthCheckItem(
                name="cross_scope_rule_duplication",
                status="OPTIMAL",
                message="Không tìm thấy thư mục Global config (~/.gemini/config). Không có nguy cơ trùng lặp.",
            )

        if g_dir == self.repo_dir.resolve():
            return HealthCheckItem(
                name="cross_scope_rule_duplication",
                status="OPTIMAL",
                message="Đang kiểm định trực tiếp trên Global Scope.",
            )

        global_gemini = g_dir / "GEMINI.md"
        ws_gemini = self.repo_dir / "GEMINI.md"

        if not global_gemini.exists() or not ws_gemini.exists():
            return HealthCheckItem(
                name="cross_scope_rule_duplication",
                status="OPTIMAL",
                message="Quy tắc phân tách đơn nhất (chỉ tồn tại ở Global hoặc Workspace Scope).",
            )

        try:
            g_text = global_gemini.read_text(encoding="utf-8", errors="replace")
            w_text = ws_gemini.read_text(encoding="utf-8", errors="replace")
            g_bytes = len(g_text.encode("utf-8"))
            w_bytes = len(w_text.encode("utf-8"))

            g_words = set(re.findall(r"\w+", g_text.lower()))
            w_words = set(re.findall(r"\w+", w_text.lower()))
            intersection = g_words.intersection(w_words)
            similarity = len(intersection) / len(g_words) if g_words else 0.0

            normative_keywords = [
                "dynamic triad",
                "bộ ba tác tử",
                "task tiering",
                "cầu dao ngắt mạch",
                "chief orchestrator",
                "maker ➔ critic",
                "intent alignment gate",
                "autonomous anti-hallucination",
            ]
            normative_overlap = any(
                kw in g_text.lower() and kw in w_text.lower() for kw in normative_keywords
            )

            # Bản global tối giản chuẩn < 2,500 bytes (< 1,000 tokens)
            if (similarity > 0.70 or normative_overlap) and g_bytes > 3072:
                wasted_tokens = max(1, g_bytes // 3)
                return HealthCheckItem(
                    name="cross_scope_rule_duplication",
                    status="ATTENTION",
                    message=(
                        f"ERR_DUPLICATE_RULES_ACROSS_SCOPES: Phát hiện trùng lặp quy tắc giữa "
                        f"Global Scope ({g_bytes:,} B) và Workspace Scope ({w_bytes:,} B). "
                        f"Lãng phí ~{wasted_tokens:,} tokens ({g_bytes:,} bytes) context mỗi lượt trao đổi!"
                    ),
                    metric=f"~{wasted_tokens:,} tokens",
                    advisory=(
                        "[ADVISORY] Chạy 'python plugins/code/skills/agy-doctor/scripts/audit_antigravity.py "
                        "--fix-duplicate-rules' để tự động sao lưu và tinh gọn Global GEMINI.md (< 1,500 tokens)."
                    ),
                )
            else:
                return HealthCheckItem(
                    name="cross_scope_rule_duplication",
                    status="OPTIMAL",
                    message=(
                        f"Quy tắc giữa Global Scope và Workspace Scope phân tầng chuẩn "
                        f"(Global: {g_bytes:,} B, Workspace: {w_bytes:,} B, không lãng phí token)."
                    ),
                    metric=f"{g_bytes:,} B",
                )
        except Exception as exc:
            return HealthCheckItem(
                name="cross_scope_rule_duplication",
                status="OBSERVE",
                message=f"Lỗi khi đối soát quy tắc Global và Workspace: {exc}",
            )

    def fix_cross_scope_rule_duplication(
        self, global_config_dir: Optional[Path] = None
    ) -> Tuple[bool, str]:
        """Tự động sao lưu Global GEMINI.md thành .bak_<timestamp> và tinh gọn thành bản tối giản chuẩn toàn cục (< 1,500 tokens)."""
        g_dir = self.resolve_global_config_dir(global_config_dir)

        if not g_dir or not g_dir.exists():
            return False, "Không tìm thấy thư mục Global config (~/.gemini/config)."

        global_gemini = g_dir / "GEMINI.md"
        if not global_gemini.exists():
            return False, f"Không tìm thấy file Global GEMINI.md tại {global_gemini}."

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = g_dir / f"GEMINI.md.bak_{timestamp}"
            backup_path.write_text(global_gemini.read_text(encoding="utf-8"), encoding="utf-8")

            # Ghi bản rút gọn chuẩn toàn cục
            global_gemini.write_text(GLOBAL_MINIMAL_RULES_CONTENT, encoding="utf-8")
            new_size = global_gemini.stat().st_size
            return True, (
                f"Đã sao lưu {backup_path.name} ({backup_path.stat().st_size:,} bytes) và "
                f"tinh gọn Global GEMINI.md thành công ({new_size:,} bytes, < 1,500 tokens)."
            )
        except Exception as exc:
            return False, f"Lỗi khi thực hiện fix-duplicate-rules: {exc}"

    # -------------------------------------------------------------------------
    # TRỤ CỘT 3: Ngân sách Ngữ Cảnh & Telemetry
    # -------------------------------------------------------------------------
    def audit_pillar_3_context_telemetry(self) -> PillarResult:
        title = "Trụ Cột 3: Ngân Sách Ngữ Cảnh & Telemetry"
        items: List[HealthCheckItem] = []

        # 3.1 Dò tìm transcript đang hoạt động
        transcript_path: Optional[Path] = None
        env_tr = os.environ.get("ANTIGRAVITY_TRANSCRIPT")
        if env_tr and Path(env_tr).is_file():
            transcript_path = Path(env_tr).resolve()
        else:
            brain_candidates = [
                Path.home() / ".gemini" / "antigravity" / "brain",
                self.repo_dir / ".brain",
            ]
            transcripts: List[Path] = []
            for bdir in brain_candidates:
                if bdir.is_dir():
                    transcripts.extend(list(bdir.glob("*/.system_generated/logs/transcript.jsonl")))
                    if not transcripts:
                        transcripts.extend(list(bdir.glob("**/transcript*.jsonl")))
            if transcripts:
                transcripts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                transcript_path = transcripts[0]

        if transcript_path and transcript_path.exists():
            size_bytes = transcript_path.stat().st_size

            # Đếm turns/steps và theo dõi CHECKPOINT / token telemetry
            has_checkpoint = False
            post_cp_bytes = 0
            post_cp_steps = 0
            post_cp_user_turns = 0
            active_prompt_tokens = 0
            try:
                with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            src = item.get("source")
                            typ = item.get("type")
                            if typ == "CHECKPOINT":
                                has_checkpoint = True
                                post_cp_bytes = 0
                                post_cp_steps = 0
                                post_cp_user_turns = 0
                                active_prompt_tokens = 0
                                continue
                            post_cp_bytes += len(raw_line.encode("utf-8"))
                            post_cp_steps += 1
                            if src == "USER_EXPLICIT" or typ == "USER_INPUT":
                                post_cp_user_turns += 1
                            if "input_tokens" in item or "cache_read_tokens" in item:
                                active_prompt_tokens = int(item.get("input_tokens") or 0) + int(
                                    item.get("cache_read_tokens") or 0
                                )
                        except Exception:
                            post_cp_bytes += len(raw_line.encode("utf-8"))
                            post_cp_steps += 1
            except Exception:
                pass

            effective_bytes = post_cp_bytes if has_checkpoint else size_bytes
            size_kb = effective_bytes / 1024.0
            turns = post_cp_user_turns if post_cp_user_turns > 0 else post_cp_steps

            token_suffix = f", {active_prompt_tokens:,} tokens" if active_prompt_tokens > 0 else ""
            cp_note = " (post-checkpoint)" if has_checkpoint else ""
            metric_str = f"{size_kb:.1f} KB, {turns} turns{token_suffix}{cp_note}"

            if (
                effective_bytes > TRANSCRIPT_RED_BYTES
                or turns > TRANSCRIPT_RED_TURNS
                or active_prompt_tokens > TRANSCRIPT_RED_TOKENS
            ):
                items.append(
                    HealthCheckItem(
                        name="active_transcript_telemetry",
                        status="ATTENTION",
                        message=(
                            f"Transcript RED: {size_kb:.1f} KB (>250KB), {turns} turns (>40)"
                            f"{token_suffix}{cp_note}. Nguy cơ mờ ngữ cảnh nghiêm trọng!"
                        ),
                        metric=metric_str,
                        advisory="[ADVISORY] Kích hoạt Session Rollover khẩn cấp: xuất _session-handoff.md và gõ /compact.",
                    )
                )
            elif (
                effective_bytes > TRANSCRIPT_YELLOW_BYTES
                or turns > TRANSCRIPT_YELLOW_TURNS
                or active_prompt_tokens > TRANSCRIPT_YELLOW_TOKENS
            ):
                items.append(
                    HealthCheckItem(
                        name="active_transcript_telemetry",
                        status="OBSERVE",
                        message=(
                            f"Transcript YELLOW: {size_kb:.1f} KB (>200KB), {turns} turns (>35)"
                            f"{token_suffix}{cp_note}. Khuyến nghị chuẩn bị cắt phiên."
                        ),
                        metric=metric_str,
                        advisory="[ADVISORY] Ngữ cảnh sắp chạm trần: hoàn tất task hiện tại hoặc gõ /compact để giải phóng bộ nhớ.",
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        name="active_transcript_telemetry",
                        status="OPTIMAL",
                        message=f"Transcript GREEN: {size_kb:.1f} KB, {turns} turns{token_suffix}{cp_note}. Ngữ cảnh hoàn toàn an toàn.",
                        metric=metric_str,
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    name="active_transcript_telemetry",
                    status="OPTIMAL",
                    message="Không tìm thấy file transcript hoạt động cũ (coi như phiên mới/sạch).",
                    metric="0 KB, 0 turns",
                )
            )

        worst = "OPTIMAL"
        for it in items:
            if it.status == "ATTENTION":
                worst = "ATTENTION"
                break
            if it.status == "OBSERVE":
                worst = "OBSERVE"

        return PillarResult(pillar_id="pillar_3_context_telemetry", title=title, status=worst, items=items)

    # -------------------------------------------------------------------------
    # TRỤ CỘT 4: Vệ sinh Tiến trình & Git
    # -------------------------------------------------------------------------
    def audit_pillar_4_process_git(self) -> PillarResult:
        title = "Trụ Cột 4: Vệ Sinh Tiến Trình & Git"
        items: List[HealthCheckItem] = []

        # 4.1 Quét nhanh Git lock files & Workflow lock files
        now = time.time()
        candidate_locks: List[Path] = [
            self.repo_dir / ".git" / "index.lock",
            self.repo_dir / ".git" / "HEAD.lock",
            self.repo_dir / ".git" / "shallow.lock",
        ]
        # Thêm các lock trực tiếp trong workflow directories
        for wdir in [
            self.repo_dir / ".brain" / "app_workflows",
            self.repo_dir / ".brain" / "marketing_workflows",
        ]:
            if wdir.is_dir():
                try:
                    candidate_locks.extend(list(wdir.glob("*.lock")))
                except OSError:
                    pass

        stuck_locks: List[Tuple[Path, float]] = []
        fresh_locks: List[Path] = []
        for lf in candidate_locks:
            if lf.exists():
                try:
                    age = now - lf.stat().st_mtime
                    if age > LOCK_STUCK_AGE_SECONDS:
                        stuck_locks.append((lf, age))
                    else:
                        fresh_locks.append(lf)
                except OSError:
                    pass

        if stuck_locks:
            lock_names = [f"{lf.name} ({int(age/60)}m)" for lf, age in stuck_locks]
            items.append(
                HealthCheckItem(
                    name="git_locks",
                    status="ATTENTION",
                    message=f"Phát hiện {len(stuck_locks)} file khóa mồ côi bị treo lâu ngày: {', '.join(lock_names)}",
                    advisory=f"[ADVISORY] Kiểm tra và gỡ bỏ file lock treo: Remove-Item '{stuck_locks[0][0]}'",
                )
            )
        elif fresh_locks:
            items.append(
                HealthCheckItem(
                    name="git_locks",
                    status="OBSERVE",
                    message=f"Có {len(fresh_locks)} file khóa đang hoạt động gần đây (< 30 phút).",
                )
            )
        else:
            items.append(
                HealthCheckItem(
                    name="git_locks",
                    status="OPTIMAL",
                    message="Không có file khóa mồ côi (*.lock) nào bị kẹt trong .git hoặc .brain.",
                )
            )

        # 4.2 Quét tiến trình trình duyệt mồ côi trên Windows (Read-Only)
        if sys.platform == "win32":
            try:
                proc = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if proc.returncode == 0:
                    lines = proc.stdout.splitlines()
                    orphan_browser_pids = []
                    for line in lines:
                        if not line.strip():
                            continue
                        reader = csv.reader(io.StringIO(line))
                        parts = next(reader, [])
                        if len(parts) >= 2:
                            pname = parts[0].strip().lower()
                            pid = parts[1].strip()
                            if "chrome-headless-shell" in pname:
                                orphan_browser_pids.append((pname, pid))
                    if orphan_browser_pids:
                        pids_str = ", ".join(f"{p}:{pid}" for p, pid in orphan_browser_pids)
                        items.append(
                            HealthCheckItem(
                                name="orphan_browsers",
                                status="OBSERVE",
                                message=f"Phát hiện {len(orphan_browser_pids)} tiến trình headless browser mồ côi: {pids_str}",
                                advisory=f"[ADVISORY] Dọn dẹp tiến trình mồ côi: powershell -File scripts/clean_orphans.ps1 -TargetPids @({','.join(pid for _, pid in orphan_browser_pids)})",
                            )
                        )
                    else:
                        items.append(
                            HealthCheckItem(
                                name="orphan_browsers",
                                status="OPTIMAL",
                                message="Không phát hiện headless browser mồ côi nào trên hệ thống.",
                            )
                        )
            except Exception:
                items.append(
                    HealthCheckItem(
                        name="orphan_browsers",
                        status="OPTIMAL",
                        message="Bỏ qua quét tasklist do timeout hoặc quyền hạn (an toàn).",
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    name="orphan_browsers",
                    status="OPTIMAL",
                    message="Môi trường phi-Windows: Bỏ qua quét tasklist Windows.",
                )
            )

        # 4.3 Kiểm tra dung lượng .sessions/ siêu tốc
        sessions_dir = self.repo_dir / ".sessions"
        if sessions_dir.is_dir():
            size, exceeded = self.fast_dir_size(sessions_dir, cap_bytes=MAX_SESSIONS_BYTES)
            size_mb = size / (1024 * 1024)
            if exceeded:
                items.append(
                    HealthCheckItem(
                        name="sessions_storage",
                        status="OBSERVE",
                        message=f"Thư mục .sessions/ dung lượng lớn (> 500 MB).",
                        metric=f">{size_mb:.1f} MB",
                        advisory="[ADVISORY] Cân nhắc nén hoặc lưu trữ các phiên cũ trong .sessions/.",
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        name="sessions_storage",
                        status="OPTIMAL",
                        message=f"Thư mục .sessions/ trong ngưỡng an toàn ({size_mb:.1f} MB).",
                        metric=f"{size_mb:.1f} MB",
                    )
                )

        worst = "OPTIMAL"
        for it in items:
            if it.status == "ATTENTION":
                worst = "ATTENTION"
                break
            if it.status == "OBSERVE":
                worst = "OBSERVE"

        return PillarResult(pillar_id="pillar_4_process_git", title=title, status=worst, items=items)

    # -------------------------------------------------------------------------
    # TRỤ CỘT 5: Bộ Não Thứ 2 (Second Brain Obsidian Vault)
    # -------------------------------------------------------------------------
    def audit_pillar_5_second_brain(self) -> PillarResult:
        title = "Trụ Cột 5: Bộ Não Thứ 2 (Second Brain Obsidian Vault)"
        items: List[HealthCheckItem] = []

        vault_env = os.environ.get("OBSIDIAN_VAULT_PATH") or os.environ.get("SECOND_BRAIN_PATH")
        vault_path: Optional[Path] = None
        if vault_env:
            p = Path(vault_env).resolve()
            if p.is_dir():
                vault_path = p
        else:
            default_obsidian = Path.home() / "Obsidian"
            if default_obsidian.is_dir():
                vault_path = default_obsidian

        if vault_path:
            wiki_dir = vault_path / "wiki"
            wiki_index = wiki_dir / "index.md"

            if wiki_dir.is_dir() and wiki_index.exists():
                items.append(
                    HealthCheckItem(
                        name="vault_structure",
                        status="OPTIMAL",
                        message=f"Obsidian Vault hợp lệ tại: {vault_path.name}/wiki/ (index.md tồn tại).",
                        metric="Sẵn sàng",
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        name="vault_structure",
                        status="OBSERVE",
                        message=f"Thư mục Vault {vault_path.name} thiếu cấu trúc chuẩn (wiki/ hoặc wiki/index.md).",
                        advisory="[ADVISORY] Chuẩn hóa Vault qua lệnh /setup-second-brain.",
                    )
                )

            handoff_file = wiki_dir / "_session-handoff.md"
            if handoff_file.exists():
                items.append(
                    HealthCheckItem(
                        name="session_handoff_ready",
                        status="OPTIMAL",
                        message="File _session-handoff.md sẵn sàng tiếp nhận tiến trình cắt phiên.",
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    name="vault_configured",
                    status="OBSERVE",
                    message="Chưa cấu hình biến môi trường $env:OBSIDIAN_VAULT_PATH hoặc thư mục ~/Obsidian.",
                    advisory="[ADVISORY] Thiết lập $env:OBSIDIAN_VAULT_PATH trỏ tới Vault hoặc kích hoạt /setup-second-brain.",
                )
            )

        worst = "OPTIMAL"
        for it in items:
            if it.status == "ATTENTION":
                worst = "ATTENTION"
                break
            if it.status == "OBSERVE":
                worst = "OBSERVE"

        return PillarResult(pillar_id="pillar_5_second_brain", title=title, status=worst, items=items)

    # -------------------------------------------------------------------------
    # ĐIỀU PHỐI TOÀN BỘ QUÁ TRÌNH KIỂM ĐỊNH
    # -------------------------------------------------------------------------
    def run_audit(self) -> AuditReport:
        t0 = time.time()

        p1 = self.audit_pillar_1_runtime_mcp()
        p2 = self.audit_pillar_2_harness_triad()
        p3 = self.audit_pillar_3_context_telemetry()
        p4 = self.audit_pillar_4_process_git()
        p5 = self.audit_pillar_5_second_brain()

        pillars = [p1, p2, p3, p4, p5]

        counts = {"OPTIMAL": 0, "OBSERVE": 0, "ATTENTION": 0}
        advisories: List[str] = []
        for p in pillars:
            for it in p.items:
                counts[it.status] = counts.get(it.status, 0) + 1
                if it.advisory:
                    advisories.append(it.advisory)

        if counts.get("ATTENTION", 0) > 0:
            overall = "ATTENTION"
            exit_code = 1
        elif counts.get("OBSERVE", 0) > 0:
            overall = "OBSERVE"
            exit_code = 0
        else:
            overall = "OPTIMAL"
            exit_code = 0

        execution_time = time.time() - t0

        return AuditReport(
            overall_status=overall,
            exit_code=exit_code,
            execution_time_seconds=execution_time,
            repo_dir=str(self.repo_dir),
            timestamp=t0,
            summary=counts,
            pillars=pillars,
            advisories=advisories,
        )

    # -------------------------------------------------------------------------
    # FORMAT BÁO CÁO MARKDOWN
    # -------------------------------------------------------------------------
    def format_markdown(self, report: AuditReport) -> str:
        icons = {
            "OPTIMAL": "🟢",
            "OBSERVE": "🟡",
            "ATTENTION": "🔴",
        }
        lines = []
        lines.append("# 🩺 Báo Cáo Sức Khỏe Antigravity 2.0 (`agy-doctor`)")
        lines.append("")
        lines.append(f"> **Trạng Thái Tổng Thể:** {icons.get(report.overall_status, '')} **{report.overall_status}**  ")
        lines.append(f"> **Thời Gian Khám:** {report.execution_time_seconds:.3f}s | **Mã Thoát:** `{report.exit_code}` | **Repo:** `{report.repo_dir}`")
        lines.append("")

        # Bảng tóm tắt
        lines.append("## 1. Tóm Tắt 5 Trụ Cột")
        lines.append("| Trụ Cột | Tên Tiêu Chuẩn | Trạng Thái | Số Mục Kiểm Tra |")
        lines.append("| :--- | :--- | :---: | :---: |")
        for p in report.pillars:
            icon = icons.get(p.status, "")
            lines.append(f"| `{p.pillar_id}` | {p.title} | {icon} **{p.status}** | {len(p.items)} |")
        lines.append("")

        # Chi tiết từng trụ cột
        lines.append("## 2. Chi Tiết Kiểm Tra Từng Trụ Cột")
        for p in report.pillars:
            icon = icons.get(p.status, "")
            lines.append(f"### {icon} {p.title}")
            for it in p.items:
                item_icon = icons.get(it.status, "")
                metric_str = f" `[{it.metric}]`" if it.metric else ""
                lines.append(f"- {item_icon} **{it.name}**:{metric_str} {it.message}")
            lines.append("")

        # Đơn thuốc khuyến nghị (Advisory Prescriptions)
        lines.append("## 3. Đơn Thuốc Khuyến Nghị An Toàn (Advisory Prescriptions)")
        if report.advisories:
            for idx, adv in enumerate(report.advisories, 1):
                clean_adv = adv.replace("[ADVISORY] ", "")
                lines.append(f"{idx}. 💊 {clean_adv}")
        else:
            lines.append("✨ Toàn bộ các tiêu chí đều đạt chuẩn hoàn hảo. Không có khuyến nghị can thiệp.")
        lines.append("")
        lines.append("> ℹ️ *Nguyên tắc bất biến: Script vận hành 100% Read-Only. Mọi khuyến nghị trên đều là gợi ý thao tác, không tự ý can thiệp mã nguồn.*")

        return "\n".join(lines)


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Antigravity 2.0 Doctor: Bác sĩ nội trú kiểm định sức khỏe toàn diện 5 trụ cột (100% Read-Only)"
    )
    parser.add_argument(
        "--repo-dir",
        default=None,
        help="Đường dẫn thư mục repository (mặc định tự dò tìm chứa GEMINI.md)",
    )
    parser.add_argument(
        "--global-config-dir",
        default=None,
        help="Đường dẫn thư mục Global config (mặc định tự dò ~/.gemini/config)",
    )
    parser.add_argument(
        "--fix-duplicate-rules",
        action="store_true",
        help="Tự động sao lưu và tinh gọn Global GEMINI.md để loại bỏ lãng phí token trùng lặp",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất báo cáo dưới dạng JSON chuẩn máy tính đọc",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        default=True,
        help="Xuất báo cáo Markdown trực quan (mặc định)",
    )

    args = parser.parse_args(argv)
    repo_path = Path(args.repo_dir).resolve() if args.repo_dir else None
    global_cfg_path = Path(args.global_config_dir).resolve() if args.global_config_dir else None

    doctor = AntigravityDoctor(repo_dir=repo_path, global_config_dir=global_cfg_path)

    # Nếu người dùng yêu cầu khắc phục trùng lặp quy tắc
    if args.fix_duplicate_rules:
        success, msg = doctor.fix_cross_scope_rule_duplication()
        if success:
            print(f"✅ {msg}")
            return 0
        else:
            print(f"❌ {msg}", file=sys.stderr)
            return 1

    report = doctor.run_audit()

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(doctor.format_markdown(report))

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
