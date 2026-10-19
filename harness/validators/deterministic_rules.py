"""Deterministic Compliance Rules inspired by IFEval.

Cung cấp các hàm kiểm định tất định chuẩn xác (100% Python standard library,
không phụ thuộc bên thứ ba) dùng để thẩm định tuân thủ cấu trúc, định dạng và ràng buộc văn bản.
"""

from collections import Counter
from dataclasses import dataclass, field
import json
import re
import string
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RuleAuditResult:
    """Kết quả kiểm định tổng hợp các ràng buộc tất định."""

    valid: bool
    violations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


def verify_word_count(
    text: str,
    min_words: Optional[int] = None,
    max_words: Optional[int] = None,
) -> Tuple[bool, int, str]:
    """Kiểm tra số lượng từ của văn bản có nằm trong khoảng [min_words, max_words] hay không.

    Tách từ bằng regex whitespace split theo chuẩn ngôn ngữ tự nhiên.
    """
    words = text.strip().split()
    count = len(words)

    if min_words is not None and count < min_words:
        return False, count, f"Số từ ({count}) nhỏ hơn giới hạn tối thiểu ({min_words})"
    if max_words is not None and count > max_words:
        return False, count, f"Số từ ({count}) vượt quá giới hạn tối đa ({max_words})"

    return True, count, f"Số từ hợp lệ ({count})"


def verify_json_format(
    text: str,
    required_keys: Optional[List[str]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Kiểm tra và trích xuất JSON từ văn bản.

    Hỗ trợ bóc tách JSON thô hoặc JSON được bao bọc trong markdown codeblock ```json ... ```.
    Nếu required_keys được cung cấp, kiểm tra đầy đủ các key bắt buộc ở root object.
    """
    cleaned = text.strip()

    # Bóc tách markdown code block nếu có
    codeblock_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if codeblock_match:
        candidate = codeblock_match.group(1).strip()
    else:
        # Nếu không có code block, thử tìm vùng JSON giữa { và } hoặc [ và ]
        candidate = cleaned

    parsed: Any = None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        # Thử tìm first '{' to last '}' nếu chuỗi có lẫn text râu ria
        start_brace = candidate.find("{")
        end_brace = candidate.rfind("}")
        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            try:
                parsed = json.loads(candidate[start_brace : end_brace + 1])
            except json.JSONDecodeError as err:
                return False, None, f"Lỗi cú pháp JSON: {err}"
        else:
            return False, None, "Không tìm thấy cấu trúc JSON hợp lệ"

    if required_keys:
        if not isinstance(parsed, dict):
            return False, parsed, "Dữ liệu JSON không phải là dictionary (object)"
        missing = [k for k in required_keys if k not in parsed]
        if missing:
            return False, parsed, f"JSON thiếu các key bắt buộc: {', '.join(missing)}"

    return True, parsed, "JSON hợp lệ và đầy đủ các key yêu cầu"


def verify_forbidden_words(
    text: str,
    forbidden_words: List[str],
) -> Tuple[bool, List[str], str]:
    """Kiểm tra sự xuất hiện của các từ cấm (case-insensitive, ranh giới từ word boundary)."""
    detected: List[str] = []
    for word in forbidden_words:
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(word)

    if detected:
        return False, detected, f"Phát hiện các từ cấm: {', '.join(detected)}"
    return True, [], "Không phát hiện từ cấm nào"


def verify_required_keywords(
    text: str,
    required_keywords: List[str],
    min_occurrences: int = 1,
) -> Tuple[bool, Dict[str, int], str]:
    """Kiểm tra các từ khóa bắt buộc và tần suất xuất hiện tối thiểu.

    Case-insensitive, kiểm tra ranh giới từ.
    """
    counts: Dict[str, int] = {}
    missing_or_insufficient: List[str] = []

    for kw in required_keywords:
        pattern = rf"\b{re.escape(kw)}\b"
        matches = re.findall(pattern, text, re.IGNORECASE)
        count = len(matches)
        counts[kw] = count
        if count < min_occurrences:
            missing_or_insufficient.append(f"'{kw}' (xuất hiện {count}/{min_occurrences} lần)")

    if missing_or_insufficient:
        return False, counts, f"Từ khóa chưa đạt yêu cầu: {', '.join(missing_or_insufficient)}"
    return True, counts, "Tất cả từ khóa bắt buộc đều đạt tần suất tối thiểu"


def verify_start_end_phrase(
    text: str,
    starts_with: Optional[str] = None,
    ends_with: Optional[str] = None,
) -> Tuple[bool, str]:
    """Kiểm tra văn bản có bắt đầu hoặc kết thúc bằng cụm từ chỉ định (bỏ qua khoảng trắng đầu/cuối)."""
    cleaned = text.strip()
    errors: List[str] = []

    if starts_with is not None:
        if not cleaned.startswith(starts_with.strip()):
            errors.append(f"Văn bản không bắt đầu bằng '{starts_with}'")

    if ends_with is not None:
        if not cleaned.endswith(ends_with.strip()):
            errors.append(f"Văn bản không kết thúc bằng '{ends_with}'")

    if errors:
        return False, "; ".join(errors)
    return True, "Cụm từ đầu/cuối khớp yêu cầu"


def verify_markdown_headers(
    text: str,
    min_headers: Optional[int] = None,
    max_headers: Optional[int] = None,
    level: Optional[int] = None,
) -> Tuple[bool, int, str]:
    """Kiểm tra số lượng markdown header (#, ##, ###, ...).

    Nếu level được chỉ định (1-6), chỉ đếm header đúng cấp độ đó.
    """
    if level is not None:
        pattern = rf"^{re.escape('#' * level)}\s+\S.*$"
    else:
        pattern = r"^#{1,6}\s+\S.*$"

    matches = re.findall(pattern, text, re.MULTILINE)
    count = len(matches)

    target_desc = f"cấp độ {level}" if level is not None else "mọi cấp độ"

    if min_headers is not None and count < min_headers:
        return False, count, f"Số header {target_desc} ({count}) nhỏ hơn mức tối thiểu ({min_headers})"
    if max_headers is not None and count > max_headers:
        return False, count, f"Số header {target_desc} ({count}) vượt mức tối đa ({max_headers})"

    return True, count, f"Số header {target_desc} hợp lệ ({count})"


def verify_paragraph_count(
    text: str,
    min_paragraphs: Optional[int] = None,
    max_paragraphs: Optional[int] = None,
) -> Tuple[bool, int, str]:
    """Kiểm tra số lượng đoạn văn.

    Các đoạn văn được phân tách bởi ít nhất hai dòng trống liên tiếp (\n\s*\n).
    """
    raw_paragraphs = re.split(r"\n\s*\n+", text.strip())
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]
    count = len(paragraphs)

    if min_paragraphs is not None and count < min_paragraphs:
        return False, count, f"Số đoạn văn ({count}) nhỏ hơn tối thiểu ({min_paragraphs})"
    if max_paragraphs is not None and count > max_paragraphs:
        return False, count, f"Số đoạn văn ({count}) vượt tối đa ({max_paragraphs})"

    return True, count, f"Số đoạn văn hợp lệ ({count})"


def verify_bullet_points(
    text: str,
    min_bullets: Optional[int] = None,
    max_bullets: Optional[int] = None,
) -> Tuple[bool, int, str]:
    """Kiểm tra số lượng gạch đầu dòng / bullet items (*, -, +, 1., 2.)."""
    bullet_pattern = r"^\s*(?:[-*+]|\d+\.)\s+\S.*$"
    matches = re.findall(bullet_pattern, text, re.MULTILINE)
    count = len(matches)

    if min_bullets is not None and count < min_bullets:
        return False, count, f"Số bullet points ({count}) nhỏ hơn tối thiểu ({min_bullets})"
    if max_bullets is not None and count > max_bullets:
        return False, count, f"Số bullet points ({count}) vượt quá tối đa ({max_bullets})"

    return True, count, f"Số bullet points hợp lệ ({count})"


def audit_deterministic_constraints(text: str, constraints: Dict[str, Any]) -> RuleAuditResult:
    """Thực thi kiểm định tổng hợp danh sách các ràng buộc định dạng trên text.

    Các constraint hỗ trợ trong dict:
    - min_words: int
    - max_words: int
    - json_format: bool
    - required_json_keys: list[str]
    - forbidden_words: list[str]
    - required_keywords: list[str]
    - min_keyword_occurrences: int (default 1)
    - starts_with: str
    - ends_with: str
    - min_headers: int
    - max_headers: int
    - header_level: int
    - min_paragraphs: int
    - max_paragraphs: int
    - min_bullets: int
    - max_bullets: int
    """
    violations: List[str] = []
    metrics: Dict[str, Any] = {}

    # 1. Word count
    if "min_words" in constraints or "max_words" in constraints:
        ok, cnt, msg = verify_word_count(
            text,
            min_words=constraints.get("min_words"),
            max_words=constraints.get("max_words"),
        )
        metrics["word_count"] = cnt
        if not ok:
            violations.append(msg)

    # 2. JSON format
    if constraints.get("json_format") or "required_json_keys" in constraints:
        ok, parsed, msg = verify_json_format(
            text,
            required_keys=constraints.get("required_json_keys"),
        )
        metrics["json_valid"] = ok
        metrics["json_parsed"] = parsed is not None
        if not ok:
            violations.append(msg)

    # 3. Forbidden words
    if "forbidden_words" in constraints:
        ok, detected, msg = verify_forbidden_words(
            text,
            forbidden_words=constraints["forbidden_words"],
        )
        metrics["forbidden_words_detected"] = detected
        if not ok:
            violations.append(msg)

    # 4. Required keywords
    if "required_keywords" in constraints:
        min_occ = constraints.get("min_keyword_occurrences", 1)
        ok, counts, msg = verify_required_keywords(
            text,
            required_keywords=constraints["required_keywords"],
            min_occurrences=min_occ,
        )
        metrics["keyword_counts"] = counts
        if not ok:
            violations.append(msg)

    # 5. Start / End phrase
    if "starts_with" in constraints or "ends_with" in constraints:
        ok, msg = verify_start_end_phrase(
            text,
            starts_with=constraints.get("starts_with"),
            ends_with=constraints.get("ends_with"),
        )
        metrics["start_end_valid"] = ok
        if not ok:
            violations.append(msg)

    # 6. Markdown headers
    if any(k in constraints for k in ("min_headers", "max_headers", "header_level")):
        ok, cnt, msg = verify_markdown_headers(
            text,
            min_headers=constraints.get("min_headers"),
            max_headers=constraints.get("max_headers"),
            level=constraints.get("header_level"),
        )
        metrics["header_count"] = cnt
        if not ok:
            violations.append(msg)

    # 7. Paragraph count
    if "min_paragraphs" in constraints or "max_paragraphs" in constraints:
        ok, cnt, msg = verify_paragraph_count(
            text,
            min_paragraphs=constraints.get("min_paragraphs"),
            max_paragraphs=constraints.get("max_paragraphs"),
        )
        metrics["paragraph_count"] = cnt
        if not ok:
            violations.append(msg)

    # 8. Bullet points
    if "min_bullets" in constraints or "max_bullets" in constraints:
        ok, cnt, msg = verify_bullet_points(
            text,
            min_bullets=constraints.get("min_bullets"),
            max_bullets=constraints.get("max_bullets"),
        )
        metrics["bullet_count"] = cnt
        if not ok:
            violations.append(msg)

    return RuleAuditResult(
        valid=len(violations) == 0,
        violations=violations,
        metrics=metrics,
    )
