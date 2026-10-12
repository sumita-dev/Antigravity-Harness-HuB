"""Module kiểm toán & chẩn đoán phiên làm việc (Session Diagnostics).

Chuyên trách phân tích transcript phiên làm việc (.jsonl) để phát hiện lãng phí token:
1. detect_polling_loops: Phát hiện các chuỗi gọi manage_task(status) liên tiếp (vi phạm Reactive Wakeup).
2. detect_model_inheritance_waste: Quét các lệnh invoke_subagent dùng Model='inherit' cho Critic/QA/Auditor.
3. detect_view_file_redundancy: Phát hiện các file bị view_file lặp lại nhiều lần.
4. calculate_context_growth: Đo lường tốc độ phình to context/tokens qua từng bước.
5. diagnose_session: Tổng hợp chẩn đoán thành SessionDiagnosticReport với phán quyết (CLEAN / WARNING / EXCESSIVE_WASTE).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union


# Danh sách từ khoá nhận diện vai trò thẩm định/kiểm thử cần dùng model nhẹ
LIGHTWEIGHT_ROLES_KEYWORDS = (
    "critic",
    "qa",
    "auditor",
    "checker",
    "review",
    "reviewer",
    "inspector",
    "compliance",
    "audit",
)


def _clean_arg_val(val: Any) -> Any:
    """Loại bỏ bọc nháy kép chuỗi JSON bị escape thừa."""
    if isinstance(val, str):
        trimmed = val.strip()
        if (trimmed.startswith('"') and trimmed.endswith('"')) or (
            trimmed.startswith("'") and trimmed.endswith("'")
        ):
            try:
                parsed = json.loads(trimmed)
                return parsed
            except Exception:
                return trimmed[1:-1]
        return trimmed
    return val


def _extract_tool_calls(record: dict) -> list[dict]:
    """Trích xuất danh sách tool calls chuẩn hoá từ một bản ghi transcript."""
    raw_calls = record.get("tool_calls")
    if not raw_calls:
        return []
    if isinstance(raw_calls, str):
        try:
            raw_calls = json.loads(raw_calls)
        except Exception:
            return []

    if not isinstance(raw_calls, list):
        return []

    calls = []
    for tc in raw_calls:
        if not isinstance(tc, dict):
            continue
        name = tc.get("name") or tc.get("tool") or ""
        args = tc.get("args") or tc.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        calls.append({"name": str(name), "args": args if isinstance(args, dict) else {}})
    return calls


def detect_polling_loops(records: Sequence[dict]) -> list[dict]:
    """Phát hiện các chuỗi gọi manage_task(status) liên tiếp (vi phạm Reactive Wakeup).

    Nguyên tắc Antigravity: Hệ thống tự đánh thức khi tác vụ nền xong (Reactive Wakeup).
    Việc gọi lặp đi lặp lại manage_task status gây hao tổn token vô ích.
    """
    violations: list[dict] = []
    status_sequence: list[dict] = []

    def flush_sequence(seq: list[dict]):
        if len(seq) >= 2:
            task_ids = list({s["task_id"] for s in seq if s.get("task_id")})
            step_indices = [s["step_index"] for s in seq]
            violations.append(
                {
                    "type": "POLLING_LOOP",
                    "consecutive_count": len(seq),
                    "task_ids": task_ids,
                    "step_indices": step_indices,
                    "message": (
                        f"Phát hiện chuỗi {len(seq)} lần polling manage_task(status) liên tiếp "
                        f"tại các bước {step_indices}. Vi phạm Reactive Wakeup Invariant."
                    ),
                }
            )

    for record in records:
        step_idx = record.get("step_index", 0)
        tool_calls = _extract_tool_calls(record)
        has_status_call = False

        for tc in tool_calls:
            name = tc.get("name", "").lower()
            if "manage_task" in name:
                args = tc.get("args", {})
                action = str(_clean_arg_val(args.get("Action", ""))).lower()
                task_id = str(_clean_arg_val(args.get("TaskId", "")))

                if action == "status":
                    has_status_call = True
                    status_sequence.append(
                        {
                            "step_index": step_idx,
                            "task_id": task_id,
                        }
                    )
                else:
                    flush_sequence(status_sequence)
                    status_sequence = []
            else:
                flush_sequence(status_sequence)
                status_sequence = []

        # Nếu bước này không có manage_task status nhưng có hành động khác ngoài tool call (hoặc không có status call)
        if not tool_calls:
            # Record không có tool call (vd user input hoặc phản hồi) -> ngắt chuỗi nếu có
            flush_sequence(status_sequence)
            status_sequence = []

    flush_sequence(status_sequence)
    return violations


def detect_model_inheritance_waste(records: Sequence[dict]) -> list[dict]:
    """Quét các lệnh invoke_subagent dùng Model='inherit' cho Critic/QA/Auditor.

    Nguyên tắc Antigravity: Các vai trò rà soát độc lập (Critic, QA Auditor, Checker)
    bắt buộc dùng model flash hoặc flash_lite để tiết kiệm token và tránh suy thoái ngân sách.
    """
    violations: list[dict] = []

    for record in records:
        step_idx = record.get("step_index", 0)
        tool_calls = _extract_tool_calls(record)

        for tc in tool_calls:
            name = tc.get("name", "").lower()
            if "invoke_subagent" in name:
                args = tc.get("args", {})
                raw_subagents = args.get("Subagents", [])
                if isinstance(raw_subagents, str):
                    try:
                        raw_subagents = json.loads(raw_subagents)
                    except Exception:
                        raw_subagents = []

                if isinstance(raw_subagents, dict):
                    raw_subagents = [raw_subagents]

                # Nếu invoke_subagent truyền trực tiếp dạng flat args
                if not raw_subagents and ("Role" in args or "TypeName" in args):
                    raw_subagents = [args]

                for sub in raw_subagents:
                    if not isinstance(sub, dict):
                        continue
                    role = str(_clean_arg_val(sub.get("Role", "")))
                    type_name = str(_clean_arg_val(sub.get("TypeName", "")))
                    model = str(_clean_arg_val(sub.get("Model", "inherit"))).lower()

                    target_text = f"{role} {type_name}".lower()
                    is_lightweight_role = any(
                        kw in target_text for kw in LIGHTWEIGHT_ROLES_KEYWORDS
                    )

                    # Model mặc định là inherit nếu không chỉ định hoặc gán explicit 'inherit'
                    if is_lightweight_role and (model in ("inherit", "", "default")):
                        violations.append(
                            {
                                "type": "MODEL_INHERITANCE_WASTE",
                                "step_index": step_idx,
                                "role": role or type_name,
                                "type_name": type_name,
                                "model": model or "inherit",
                                "message": (
                                    f"Subagent vai trò kiểm định '{role or type_name}' tại bước {step_idx} "
                                    f"sử dụng Model='{model or 'inherit'}' thay vì phân tầng 'flash'/'flash_lite'."
                                ),
                            }
                        )
    return violations


def detect_view_file_redundancy(
    records: Sequence[dict], threshold: int = 3
) -> list[dict]:
    """Phát hiện các tệp tin bị view_file lặp lại nhiều lần vượt ngưỡng."""
    violations: list[dict] = []
    file_views: dict[str, list[int]] = {}

    for record in records:
        step_idx = record.get("step_index", 0)
        tool_calls = _extract_tool_calls(record)

        for tc in tool_calls:
            name = tc.get("name", "").lower()
            if "view_file" in name:
                args = tc.get("args", {})
                file_path = (
                    args.get("AbsolutePath")
                    or args.get("TargetFile")
                    or args.get("path")
                    or args.get("file")
                    or ""
                )
                file_path = str(_clean_arg_val(file_path)).strip()
                if not file_path:
                    continue

                # Chuẩn hoá path để so khớp chính xác
                norm_path = os.path.normpath(file_path).lower()
                if norm_path not in file_views:
                    file_views[norm_path] = []
                file_views[norm_path].append(step_idx)

    for norm_path, steps in file_views.items():
        if len(steps) >= threshold:
            violations.append(
                {
                    "type": "VIEW_FILE_REDUNDANCY",
                    "file_path": norm_path,
                    "count": len(steps),
                    "threshold": threshold,
                    "step_indices": steps,
                    "message": (
                        f"Tệp tin '{norm_path}' bị đọc lặp lại {len(steps)} lần "
                        f"(ngưỡng cho phép: < {threshold}) tại các bước {steps}. "
                        f"Cần nạp bộ nhớ đệm hoặc tóm tắt vào artifact."
                    ),
                }
            )

    return violations


def calculate_context_growth(records: Sequence[dict]) -> dict:
    """Đo lường dung lượng ký tự và ước lượng tokens qua từng bước."""
    total_steps = len(records)
    total_chars = 0
    step_tokens: list[int] = []
    step_chars: list[int] = []

    for record in records:
        char_count = 0
        for key in ("content", "thinking"):
            val = record.get(key)
            if isinstance(val, str):
                char_count += len(val)

        tool_calls = record.get("tool_calls")
        if tool_calls:
            if isinstance(tool_calls, str):
                char_count += len(tool_calls)
            else:
                char_count += len(json.dumps(tool_calls))

        # Ước lượng tokens trung bình ~ 4 ký tự / token
        tokens = max(1, char_count // 4)
        step_chars.append(char_count)
        step_tokens.append(tokens)
        total_chars += char_count

    estimated_total_tokens = sum(step_tokens)
    avg_tokens = (estimated_total_tokens / total_steps) if total_steps > 0 else 0

    # Đánh giá xu hướng tăng trưởng
    if total_steps >= 6:
        mid = total_steps // 2
        first_half_avg = sum(step_tokens[:mid]) / mid
        second_half_avg = sum(step_tokens[mid:]) / (total_steps - mid)
        growth_ratio = (second_half_avg / first_half_avg) if first_half_avg > 0 else 1.0
        if growth_ratio > 2.5 or estimated_total_tokens > 200000:
            trend = "CRITICAL"
        elif growth_ratio > 1.5 or estimated_total_tokens > 100000:
            trend = "RAPID"
        elif growth_ratio > 1.1:
            trend = "MODERATE"
        else:
            trend = "STABLE"
    else:
        trend = "STABLE"

    return {
        "total_steps": total_steps,
        "total_characters": total_chars,
        "estimated_total_tokens": estimated_total_tokens,
        "average_tokens_per_step": round(avg_tokens, 2),
        "peak_step_tokens": max(step_tokens) if step_tokens else 0,
        "growth_trend": trend,
        "per_step_tokens": step_tokens,
    }


@dataclass
class SessionDiagnosticReport:
    """Báo cáo kiểm toán và chẩn đoán toàn diện phiên làm việc."""

    session_id: str
    verdict: str  # CLEAN, WARNING, EXCESSIVE_WASTE
    total_steps: int
    estimated_tokens: int
    polling_violations: list[dict] = field(default_factory=list)
    model_waste_violations: list[dict] = field(default_factory=list)
    redundancy_violations: list[dict] = field(default_factory=list)
    context_growth: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"=== BÁO CÁO CHẨN ĐOÁN PHIÊN [{self.session_id}] ===",
            f"Phán quyết: {self.verdict}",
            f"Tổng số bước: {self.total_steps} | Ước lượng tokens: {self.estimated_tokens:,}",
            f"- Lỗi polling lặp: {len(self.polling_violations)}",
            f"- Lãng phí model inherit: {len(self.model_waste_violations)}",
            f"- Tệp đọc dư thừa: {len(self.redundancy_violations)}",
            f"- Xu hướng tăng trưởng: {self.context_growth.get('growth_trend', 'N/A')}",
        ]
        if self.recommendations:
            lines.append("Khuyến nghị:")
            for rec in self.recommendations:
                lines.append(f"  * {rec}")
        return "\n".join(lines)


def _load_transcript_records(session_id_or_path: Union[str, Path, Sequence[dict]]) -> tuple[str, list[dict]]:
    """Đọc và nạp các bản ghi transcript từ path, session ID hoặc dữ liệu thô."""
    if isinstance(session_id_or_path, list):
        return ("in-memory", list(session_id_or_path))

    path_candidate = Path(str(session_id_or_path))
    session_id = path_candidate.stem

    target_file: Optional[Path] = None

    if path_candidate.is_file():
        target_file = path_candidate
    elif path_candidate.is_dir():
        for fname in ("transcript.jsonl", "transcript_full.jsonl"):
            f = path_candidate / fname
            if f.is_file():
                target_file = f
                break
        if not target_file:
            sub = path_candidate / ".system_generated" / "logs" / "transcript.jsonl"
            if sub.is_file():
                target_file = sub
    else:
        # Thử tìm theo Session ID trong Antigravity Brain
        app_data = os.environ.get("USERPROFILE", "")
        if app_data:
            brain_dir = Path(app_data) / ".gemini" / "antigravity" / "brain" / str(session_id_or_path)
            for fname in ("transcript.jsonl", "transcript_full.jsonl"):
                f = brain_dir / ".system_generated" / "logs" / fname
                if f.is_file():
                    target_file = f
                    session_id = str(session_id_or_path)
                    break

    if not target_file or not target_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file transcript cho: {session_id_or_path}")

    records = []
    with open(target_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return (session_id, records)


def diagnose_session(
    session_id_or_path: Union[str, Path, Sequence[dict]],
    view_threshold: int = 3,
) -> SessionDiagnosticReport:
    """Chẩn đoán toàn diện phiên làm việc và xuất báo cáo phán quyết."""
    session_id, records = _load_transcript_records(session_id_or_path)

    polling_violations = detect_polling_loops(records)
    model_waste_violations = detect_model_inheritance_waste(records)
    redundancy_violations = detect_view_file_redundancy(records, threshold=view_threshold)
    growth = calculate_context_growth(records)

    total_steps = growth.get("total_steps", len(records))
    estimated_tokens = growth.get("estimated_total_tokens", 0)

    # Xác định recommendations
    recommendations: list[str] = []
    if polling_violations:
        recommendations.append(
            "Tuân thủ Zero-Polling Invariant: Dừng turn để đón Reactive Wakeup, tuyệt đối không gọi lặp manage_task(status)."
        )
    if model_waste_violations:
        recommendations.append(
            "Ép phân tầng Model tường minh: Cấm dùng Model='inherit' cho Critic/QA, chuyển sang 'flash' hoặc 'flash_lite'."
        )
    if redundancy_violations:
        recommendations.append(
            f"Giảm đọc file lặp (>= {view_threshold} lần): Cache thông tin vào bộ nhớ phiên hoặc tóm tắt vào artifact."
        )
    if total_steps >= 40 or estimated_tokens >= 150000 or growth.get("growth_trend") == "CRITICAL":
        recommendations.append(
            "Kích hoạt Session Rollover Gate: Phiên vượt ngưỡng an toàn (40 turns / 150k tokens), đúc kết _session-handoff.md và mở phiên mới."
        )

    # Phán quyết (verdict)
    has_critical_polling = any(v.get("consecutive_count", 0) >= 3 for v in polling_violations)
    has_heavy_model_waste = len(model_waste_violations) >= 3
    has_heavy_redundancy = any(v.get("count", 0) >= 5 for v in redundancy_violations)
    is_excessive_growth = growth.get("growth_trend") == "CRITICAL" or total_steps >= 50

    if (
        has_critical_polling
        or has_heavy_model_waste
        or has_heavy_redundancy
        or is_excessive_growth
    ):
        verdict = "EXCESSIVE_WASTE"
    elif polling_violations or model_waste_violations or redundancy_violations or total_steps >= 40:
        verdict = "WARNING"
    else:
        verdict = "CLEAN"

    return SessionDiagnosticReport(
        session_id=session_id,
        verdict=verdict,
        total_steps=total_steps,
        estimated_tokens=estimated_tokens,
        polling_violations=polling_violations,
        model_waste_violations=model_waste_violations,
        redundancy_violations=redundancy_violations,
        context_growth=growth,
        recommendations=recommendations,
    )
