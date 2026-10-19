"""Self-Correction Loop inspired by instructor retry loops.

Kết nối trực tiếp với audit_deterministic_constraints và RuleAuditResult
từ harness.validators.deterministic_rules. Tự động lặp lại quy trình sửa lỗi
văn bản/kết quả cho đến khi vượt qua toàn bộ ràng buộc hoặc đạt số lần retry tối đa.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Callable, Dict, List, Optional

from harness.validators.deterministic_rules import (
    RuleAuditResult,
    audit_deterministic_constraints,
)


@dataclass
class CorrectionAttempt:
    """Ghi nhận một lần thử thẩm định và sửa đổi trong vòng lặp."""

    attempt: int
    text: str
    violations: List[str]
    success: bool


@dataclass
class SelfCorrectionResult:
    """Kết quả tổng thể của vòng lặp tự sửa lỗi (Self-Correction Loop)."""

    success: bool
    final_text: str
    attempts: List[CorrectionAttempt]
    total_retries: int


def default_deterministic_fixer(
    text: str,
    violations: List[str],
    constraints: Optional[Dict[str, Any]] = None,
) -> str:
    """Bộ sửa lỗi cơ bản mặc định (fallback heuristic fixer).

    Thực hiện xử lý các lỗi thường gặp:
    - Bọc codeblock ```json ... ``` hoặc parse lại JSON nếu thiếu
    - Cắt tỉa từ thừa nếu vượt quá max_words
    - Thêm tiền tố starts_with hoặc hậu tố ends_with nếu thiếu
    - Loại bỏ các từ cấm (forbidden_words) hoặc từ suy đoán
    - Thêm các từ khóa bắt buộc (required_keywords) nếu thiếu
    """
    fixed = text
    constraints = constraints or {}

    # 1. Khắc phục lỗi JSON: Nếu yêu cầu json_format, json_valid hoặc JSON format fail
    if any("JSON" in v for v in violations) or constraints.get("json_format") or constraints.get("json_valid"):
        # Kiểm tra xem text đã có code block chưa
        if not re.search(r"```(?:json)?\s*[\s\S]*?```", fixed):
            # Thử tìm vùng { ... }
            match = re.search(r"(\{[\s\S]*\})", fixed)
            if match:
                try:
                    # Validate parse được
                    json.loads(match.group(1))
                    fixed = f"```json\n{match.group(1).strip()}\n```"
                except Exception:
                    pass
            else:
                # Nếu không có dấu ngoặc nhọn, tự tạo JSON hợp lệ với required_json_keys / required_keys nếu có
                req_keys = constraints.get("required_json_keys") or constraints.get("required_keys", [])
                obj = {k: "default_value" for k in req_keys}
                fixed = f"```json\n{json.dumps(obj, indent=2, ensure_ascii=False)}\n```"

    # 2. Khắc phục lỗi forbidden_words
    forbidden = constraints.get("forbidden_words", [])
    for word in forbidden:
        # Thay thế bằng chuỗi rỗng hoặc từ trung tính
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        fixed = pattern.sub("", fixed)

    # 3. Khắc phục lỗi starts_with / ends_with
    starts_with = constraints.get("starts_with")
    if starts_with and not fixed.startswith(starts_with):
        fixed = f"{starts_with}\n{fixed}"

    ends_with = constraints.get("ends_with")
    if ends_with and not fixed.endswith(ends_with):
        fixed = f"{fixed.rstrip()}\n{ends_with}"

    # 4. Khắc phục lỗi required_keywords
    required_keywords = constraints.get("required_keywords", [])
    for kw in required_keywords:
        if not re.search(rf"\b{re.escape(kw)}\b", fixed, re.IGNORECASE):
            fixed = f"{fixed}\n{kw}"

    # 5. Khắc phục lỗi max_words
    max_words = constraints.get("max_words")
    if max_words:
        words = fixed.split()
        if len(words) > max_words:
            # Cắt ngắn vừa đủ số từ
            fixed = " ".join(words[:max_words])
            # Đảm bảo nếu có ends_with thì vẫn giữ
            if ends_with and not fixed.endswith(ends_with):
                words = fixed.split()
                if len(words) >= 2:
                    fixed = " ".join(words[:-len(ends_with.split())]) + " " + ends_with
                else:
                    fixed = ends_with

    return fixed.strip()


def run_self_correction_loop(
    initial_text: str,
    constraints: Dict[str, Any],
    corrector_fn: Optional[Callable[[str, List[str]], str]] = None,
    max_retries: int = 2,
) -> SelfCorrectionResult:
    """Thực thi vòng lặp tự sửa lỗi (Self-Correction Loop).

    Quy trình:
    1. Kiểm định văn bản ban đầu bằng audit_deterministic_constraints.
    2. Nếu hợp lệ ngay từ đầu: trả về kết quả thành công mà không cần retry (total_retries = 0).
    3. Nếu có vi phạm:
       - Gọi corrector_fn(current_text, violations) hoặc default_deterministic_fixer.
       - Tái kiểm định văn bản sau khi sửa.
       - Lặp lại tối đa max_retries lần.
    4. Trả về SelfCorrectionResult tổng hợp.

    Args:
        initial_text: Văn bản gốc cần kiểm định và sửa đổi.
        constraints: Dictionary các ràng buộc truyền cho audit_deterministic_constraints.
        corrector_fn: Hàm tùy chọn nhận (text, violations) và trả về text đã sửa.
        max_retries: Số lần thử lại tối đa (mặc định: 2).

    Returns:
        SelfCorrectionResult
    """
    current_text = initial_text
    attempts: List[CorrectionAttempt] = []

    # Lần kiểm định khởi đầu (Attempt 0)
    audit: RuleAuditResult = audit_deterministic_constraints(current_text, constraints)
    attempts.append(
        CorrectionAttempt(
            attempt=0,
            text=current_text,
            violations=audit.violations,
            success=audit.valid,
        )
    )

    if audit.valid:
        return SelfCorrectionResult(
            success=True,
            final_text=current_text,
            attempts=attempts,
            total_retries=0,
        )

    # Vòng lặp retry
    retries_done = 0
    while retries_done < max_retries and not audit.valid:
        retries_done += 1
        if corrector_fn is not None:
            new_text = corrector_fn(current_text, audit.violations)
        else:
            new_text = default_deterministic_fixer(current_text, audit.violations, constraints)

        current_text = new_text
        audit = audit_deterministic_constraints(current_text, constraints)

        attempts.append(
            CorrectionAttempt(
                attempt=retries_done,
                text=current_text,
                violations=audit.violations,
                success=audit.valid,
            )
        )

        if audit.valid:
            break

    return SelfCorrectionResult(
        success=audit.valid,
        final_text=current_text,
        attempts=attempts,
        total_retries=retries_done,
    )
