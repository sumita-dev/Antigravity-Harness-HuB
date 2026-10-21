"""Opik Quantitative Evaluation & Heuristic Metrics Module.

Cung cấp hệ thống đánh giá định lượng lấy cảm hứng từ Opik (Comet ML):
- Tự động phát hiện nếu package `opik` có sẵn trong môi trường (native Opik mode).
- Fallback hoàn chỉnh thuần Python (Zero-Infra Standalone mode, không phụ thuộc server bên ngoài):
  + Heuristic metrics: Levenshtein ratio / similarity, Contains / Regex match, Equals, IsJson.
  + Degeneration detector: Phát hiện lặp từ ngữ, câu lặp vô nghĩa hoặc vòng lặp token thoái hoá.
  + Trajectory Accuracy metric: Đo lường mức độ tuân thủ thứ tự và đầy đủ của các bước kế hoạch.
  + Rubric G-Eval scorer: Đánh giá định lượng Rubric theo trọng số (0.0 - 1.0).
  + Hallucination Score: Tích hợp với `hallucination_detector.py` để tính điểm tin cậy định lượng.
"""

from __future__ import annotations

import bisect
from collections import Counter
from dataclasses import dataclass, field
import difflib
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Thử import rapidfuzz nếu có
try:
    import rapidfuzz.distance.Indel  # type: ignore
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# Thử import opik native nếu có
try:
    import opik  # type: ignore
    from opik.evaluation import metrics as opik_metrics  # type: ignore
    HAS_OPIK_PACKAGE = True
except (ImportError, Exception):
    opik = None  # type: ignore
    opik_metrics = None  # type: ignore
    HAS_OPIK_PACKAGE = False


@dataclass
class ScoreResult:
    """Kết quả tính điểm định lượng theo chuẩn tương thích Opik.

    Attributes:
        name: Tên của metric (vd: 'levenshtein_ratio', 'trajectory_accuracy', 'hallucination_score').
        value: Điểm số định lượng từ 0.0 đến 1.0 (1.0 = hoàn hảo, 0.0 = vi phạm hoàn toàn).
        reason: Diễn giải nguyên nhân / căn cứ chấm điểm.
        metadata: Dữ liệu chi tiết bổ trợ (danh sách vi phạm, thống kê sub-metrics, v.v.).
    """
    name: str
    value: float
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_passing(self) -> bool:
        """Mặc định điểm >= 0.8 là đạt chuẩn chất lượng."""
        return self.value >= 0.8


def is_opik_available() -> bool:
    """Kiểm tra package Opik có cài đặt và import được không."""
    return HAS_OPIK_PACKAGE


# ==============================================================================
# 1. PURE PYTHON HEURISTIC METRICS (Zero-Infra Standalone)
# ==============================================================================

def compute_levenshtein_distance(s1: str, s2: str) -> int:
    """Tính khoảng cách Levenshtein thuần Python (Wagner-Fischer DP)."""
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1] * (len(s2) + 1)
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row[j + 1] = min(insertions, deletions, substitutions)
        prev_row = curr_row
    return prev_row[-1]


def compute_levenshtein_ratio(
    output: str,
    reference: str,
    case_sensitive: bool = False,
) -> float:
    """Tính tỉ lệ tương đồng Levenshtein / Indel normalized similarity [0.0, 1.0]."""
    if not output and not reference:
        return 1.0
    if not output or not reference:
        return 0.0

    val = output if case_sensitive else output.lower()
    ref = reference if case_sensitive else reference.lower()

    if HAS_RAPIDFUZZ:
        score = rapidfuzz.distance.Indel.normalized_similarity(val, ref)
        return round(float(score), 4)

    # Fallback thuần Python
    dist = compute_levenshtein_distance(val, ref)
    max_len = max(len(val), len(ref))
    if max_len == 0:
        return 1.0
    return round(max(0.0, 1.0 - (dist / max_len)), 4)


class LevenshteinRatioMetric:
    """Metric đo độ tương đồng Levenshtein giữa output và reference string."""

    def __init__(
        self,
        case_sensitive: bool = False,
        name: str = "levenshtein_ratio",
    ) -> None:
        self.case_sensitive = case_sensitive
        self.name = name

    def score(self, output: str, reference: str, **kwargs: Any) -> ScoreResult:
        if not isinstance(output, str) or not isinstance(reference, str):
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason="Output hoặc reference không phải kiểu str.",
            )

        ratio = compute_levenshtein_ratio(
            output, reference, case_sensitive=self.case_sensitive
        )
        return ScoreResult(
            name=self.name,
            value=ratio,
            reason=f"Tỉ lệ tương đồng Levenshtein: {ratio:.4f}",
            metadata={"case_sensitive": self.case_sensitive},
        )


class ContainsMetric:
    """Metric kiểm tra sự hiện diện của chuỗi con trong output."""

    def __init__(
        self,
        case_sensitive: bool = False,
        name: str = "contains",
    ) -> None:
        self.case_sensitive = case_sensitive
        self.name = name

    def score(self, output: str, substring: str, **kwargs: Any) -> ScoreResult:
        if not isinstance(output, str) or not isinstance(substring, str):
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason="Output hoặc substring không phải kiểu str.",
            )

        val = output if self.case_sensitive else output.lower()
        sub = substring if self.case_sensitive else substring.lower()

        found = sub in val
        return ScoreResult(
            name=self.name,
            value=1.0 if found else 0.0,
            reason=f"Substring '{substring}' {'được tìm thấy' if found else 'không tồn tại'} trong output.",
            metadata={"found": found, "substring": substring},
        )


class RegexMatchMetric:
    """Metric kiểm tra xem output có khớp với biểu thức chính quy (regex) không."""

    def __init__(
        self,
        name: str = "regex_match",
    ) -> None:
        self.name = name

    def score(self, output: str, pattern: str, **kwargs: Any) -> ScoreResult:
        if not isinstance(output, str) or not isinstance(pattern, str):
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason="Output hoặc pattern không phải kiểu str.",
            )

        try:
            matched = bool(re.search(pattern, output))
        except re.error as e:
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason=f"Regex pattern không hợp lệ: {e}",
            )

        return ScoreResult(
            name=self.name,
            value=1.0 if matched else 0.0,
            reason=f"Pattern '{pattern}' {'khớp' if matched else 'không khớp'} với output.",
            metadata={"matched": matched, "pattern": pattern},
        )


class EqualsMetric:
    """Metric kiểm tra output có bằng chính xác reference không."""

    def __init__(
        self,
        case_sensitive: bool = True,
        name: str = "equals",
    ) -> None:
        self.case_sensitive = case_sensitive
        self.name = name

    def score(self, output: str, reference: str, **kwargs: Any) -> ScoreResult:
        val = output if self.case_sensitive else str(output).lower()
        ref = reference if self.case_sensitive else str(reference).lower()
        eq = (val == ref)
        return ScoreResult(
            name=self.name,
            value=1.0 if eq else 0.0,
            reason=f"Output {'bằng chính xác' if eq else 'khác'} reference.",
            metadata={"equals": eq},
        )


class IsJsonMetric:
    """Metric kiểm tra tính hợp lệ của JSON và đối soát các trường bắt buộc."""

    def __init__(
        self,
        name: str = "is_json",
    ) -> None:
        self.name = name

    def score(
        self,
        output: str,
        required_keys: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ScoreResult:
        if not isinstance(output, str):
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason="Output không phải chuỗi ký tự.",
            )

        cleaned = output.strip()
        codeblock = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        candidate = codeblock.group(1).strip() if codeblock else cleaned

        try:
            data = json.loads(candidate)
        except Exception as e:
            # Thử bóc tách giữa '{' và '}'
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end > start:
                try:
                    data = json.loads(candidate[start : end + 1])
                except Exception:
                    return ScoreResult(
                        name=self.name,
                        value=0.0,
                        reason=f"Chuỗi không phải JSON hợp lệ: {e}",
                    )
            else:
                return ScoreResult(
                    name=self.name,
                    value=0.0,
                    reason=f"Chuỗi không phải JSON hợp lệ: {e}",
                )

        if not required_keys:
            return ScoreResult(
                name=self.name,
                value=1.0,
                reason="JSON hợp lệ.",
                metadata={"parsed_keys": list(data.keys()) if isinstance(data, dict) else []},
            )

        if not isinstance(data, dict):
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason="JSON hợp lệ nhưng không phải dictionary (không kiểm tra được keys).",
            )

        missing = [k for k in required_keys if k not in data]
        if missing:
            score = max(0.0, 1.0 - (len(missing) / len(required_keys)))
            return ScoreResult(
                name=self.name,
                value=round(score, 2),
                reason=f"Thiếu các trường bắt buộc: {missing}",
                metadata={"missing_keys": missing, "present_keys": list(data.keys())},
            )

        return ScoreResult(
            name=self.name,
            value=1.0,
            reason="JSON hợp lệ và chứa đầy đủ các trường bắt buộc.",
            metadata={"keys": list(data.keys())},
        )


# ==============================================================================
# 2. DEGENERATION DETECTOR (Chống lặp vô nghĩa / Thoái hoá token)
# ==============================================================================

class DegenerationMetric:
    """Phát hiện suy thoái văn bản (Degeneration): lặp token, lặp cụm từ hoặc lặp dòng vô hạn.

    Trả về điểm số:
    - 1.0: Văn bản phong phú, không có dấu hiệu suy thoái / lặp vòng.
    - < 0.7: Phát hiện lặp cụm từ bất thường hoặc kẹt vòng lặp.
    - 0.0: Văn bản hoàn toàn bị thoái hoá (stuttering loop).
    """

    def __init__(
        self,
        min_ngram: int = 2,
        max_ngram: int = 4,
        threshold: float = 0.3,
        name: str = "degeneration_metric",
    ) -> None:
        self.min_ngram = min_ngram
        self.max_ngram = max_ngram
        self.threshold = threshold
        self.name = name

    def score(self, output: str, **kwargs: Any) -> ScoreResult:
        if not output or not output.strip():
            return ScoreResult(
                name=self.name,
                value=1.0,
                reason="Văn bản rỗng.",
            )

        tokens = re.findall(r"\w+", output.lower())
        total_tokens = len(tokens)

        # Nếu văn bản quá ngắn, kiểm tra xem có phải lặp 1 từ không
        if total_tokens < 6:
            if total_tokens > 2 and len(set(tokens)) == 1:
                return ScoreResult(
                    name=self.name,
                    value=0.0,
                    reason=f"Văn bản ngắn nhưng bị lặp 100% từ '{tokens[0]}'.",
                    metadata={"repeated_tokens": tokens},
                )
            return ScoreResult(
                name=self.name,
                value=1.0,
                reason="Văn bản ngắn, không có dấu hiệu suy thoái.",
            )

        # 1. Đo lường tỷ lệ trùng lặp N-gram
        repetition_rates: List[float] = []
        repeated_ngrams: Dict[str, int] = {}

        for n in range(self.min_ngram, min(self.max_ngram + 1, total_tokens)):
            ngrams = [tuple(tokens[i : i + n]) for i in range(total_tokens - n + 1)]
            if not ngrams:
                continue
            counts = Counter(ngrams)
            duplicates = sum(count - 1 for count in counts.values() if count > 1)
            rate = duplicates / len(ngrams)
            repetition_rates.append(rate)

            # Ghi nhận các n-gram lặp quá 3 lần
            for gram, count in counts.items():
                if count >= 3:
                    repeated_ngrams[" ".join(gram)] = count

        max_rep_rate = max(repetition_rates) if repetition_rates else 0.0

        # 2. Đo lường dòng lặp liên tiếp (consecutive duplicated lines)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        consecutive_dup_lines = 0
        for i in range(len(lines) - 1):
            if lines[i] == lines[i + 1]:
                consecutive_dup_lines += 1

        line_penalty = min(0.5, (consecutive_dup_lines * 0.15))

        # Tính điểm độ sạch (Cleanliness score = 1.0 - max_rep_rate - line_penalty)
        clean_score = max(0.0, 1.0 - max_rep_rate - line_penalty)
        clean_score = round(clean_score, 2)

        violations = []
        if max_rep_rate > self.threshold:
            violations.append(f"Tỉ lệ lặp n-gram cao ({max_rep_rate:.2%})")
        if consecutive_dup_lines > 0:
            violations.append(f"Phát hiện {consecutive_dup_lines} dòng lặp lại liên tiếp")

        reason = (
            "Văn bản đạt độ tự nhiên, không phát hiện suy thoái lặp từ."
            if not violations
            else f"Cảnh báo suy thoái token: {'; '.join(violations)}."
        )

        return ScoreResult(
            name=self.name,
            value=clean_score,
            reason=reason,
            metadata={
                "max_repetition_rate": max_rep_rate,
                "consecutive_dup_lines": consecutive_dup_lines,
                "repeated_ngrams": repeated_ngrams,
            },
        )


# ==============================================================================
# 3. TRAJECTORY ACCURACY METRIC (Tuân thủ thứ tự các bước kế hoạch)
# ==============================================================================

class TrajectoryAccuracyMetric:
    """Đo lường độ tuân thủ thứ tự và tính đầy đủ của các bước trong kế hoạch (Plan vs Trajectory).

    Đánh giá 3 khía cạnh:
    1. Step Coverage: Tỉ lệ các bước kế hoạch đã được thực thi.
    2. Order Adherence: Thứ tự thực thi có bảo toàn thứ tự kế hoạch (Longest Increasing Subsequence).
    3. Status Health: Tỉ lệ các bước thực thi thành công không bị gãy hoặc fail.
    """

    def __init__(self, name: str = "trajectory_accuracy") -> None:
        self.name = name

    def _normalize_step(self, step: Union[str, Dict[str, Any]]) -> str:
        if isinstance(step, dict):
            # Lấy trường định danh bước
            candidate = (
                step.get("name")
                or step.get("step")
                or step.get("phase")
                or step.get("action")
                or step.get("state")
                or ""
            )
            return str(candidate).strip().lower()
        return str(step).strip().lower()

    def _step_matches(self, planned_step: str, executed_step: str) -> bool:
        if not planned_step or not executed_step:
            return False
        if planned_step == executed_step:
            return True
        if planned_step in executed_step or executed_step in planned_step:
            return True
        # So khớp mờ
        return compute_levenshtein_ratio(planned_step, executed_step) >= 0.7

    def score(
        self,
        planned_steps: List[Union[str, Dict[str, Any]]],
        executed_steps: List[Union[str, Dict[str, Any]]],
        **kwargs: Any,
    ) -> ScoreResult:
        if not planned_steps:
            return ScoreResult(
                name=self.name,
                value=1.0,
                reason="Không có planned steps nào được yêu cầu.",
            )

        if not executed_steps:
            return ScoreResult(
                name=self.name,
                value=0.0,
                reason="Không có bước thực thi nào (executed steps rỗng).",
                metadata={"coverage": 0.0, "order": 0.0},
            )

        norm_planned = [self._normalize_step(s) for s in planned_steps]
        norm_executed = [self._normalize_step(s) for s in executed_steps]

        # 1. Tìm ánh xạ vị trí executed đầu tiên cho từng planned step
        matched_indices: List[Optional[int]] = []
        for p_step in norm_planned:
            found_idx = None
            for e_idx, e_step in enumerate(norm_executed):
                if self._step_matches(p_step, e_step):
                    found_idx = e_idx
                    break
            matched_indices.append(found_idx)

        successful_matches = [idx for idx in matched_indices if idx is not None]
        coverage_score = len(successful_matches) / len(norm_planned)

        # 2. Kiểm tra tính bảo toàn thứ tự (Longest Increasing Subsequence trên matched_indices)
        if len(successful_matches) <= 1:
            order_score = 1.0 if successful_matches else 0.0
        else:
            # Thuật toán tìm LIS
            lis: List[int] = []
            for x in successful_matches:
                # Tìm vị trí chèn
                idx = bisect.bisect_left(lis, x)
                if idx == len(lis):
                    lis.append(x)
                else:
                    lis[idx] = x
            order_score = len(lis) / len(successful_matches)

        # 3. Kiểm tra trạng thái lỗi nếu executed_steps là list dict
        failures = 0
        for s in executed_steps:
            if isinstance(s, dict):
                exit_code = s.get("exit_code")
                status = str(s.get("status", "")).upper()
                if exit_code is not None and exit_code != 0:
                    failures += 1
                elif status in ("FAILED", "FAIL", "REJECTED", "ERROR"):
                    failures += 1

        failure_penalty = min(0.3, (failures * 0.1))

        # Tổng hợp điểm: 50% Coverage + 50% Order - Penalty
        final_score = max(0.0, (0.5 * coverage_score + 0.5 * order_score) - failure_penalty)
        final_score = round(final_score, 2)

        reason = (
            f"Trajectory Accuracy: {final_score:.2f} "
            f"(Coverage: {coverage_score:.1%}, Thứ tự chuẩn: {order_score:.1%}, Lỗi: {failures})"
        )

        return ScoreResult(
            name=self.name,
            value=final_score,
            reason=reason,
            metadata={
                "coverage_score": round(coverage_score, 2),
                "order_score": round(order_score, 2),
                "failures": failures,
                "planned_count": len(norm_planned),
                "executed_count": len(norm_executed),
                "matched_indices": matched_indices,
            },
        )


# ==============================================================================
# 4. RUBRIC G-EVAL SCORER (Chấm điểm Rubric định lượng theo trọng số)
# ==============================================================================

class RubricGEvalMetric:
    """Đánh giá định lượng Rubric theo trọng số (0.0 - 1.0) không phụ thuộc API bên ngoài.

    Mỗi tiêu chí (Rubric item) có cấu trúc:
    {
        "name": str,
        "description": str,
        "weight": float,  # Trọng số tương đối
        "required_sections": Optional[List[str]], # Header markdown bắt buộc
        "keywords": Optional[List[str]],          # Từ khóa bắt buộc
        "forbidden": Optional[List[str]],         # Từ khóa cấm
        "min_words": Optional[int],               # Độ dài tối thiểu
        "check_fn": Optional[Callable[[str], float]] # Hàm tính điểm tự định nghĩa
    }
    """

    def __init__(self, name: str = "rubric_geval") -> None:
        self.name = name

    def score(
        self,
        text: str,
        criteria: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ScoreResult:
        text = text or ""
        if not criteria:
            return ScoreResult(
                name=self.name,
                value=1.0,
                reason="Danh sách tiêu chí Rubric rỗng.",
            )

        total_weight = sum(c.get("weight", 1.0) for c in criteria)
        if total_weight <= 0:
            total_weight = float(len(criteria))

        criteria_scores: Dict[str, float] = {}
        criteria_details: Dict[str, Any] = {}
        weighted_sum = 0.0

        for crit in criteria:
            c_name = crit.get("name", "criterion")
            weight = crit.get("weight", 1.0)
            c_score = 1.0
            reasons: List[str] = []

            # 1. Custom check function
            check_fn = crit.get("check_fn")
            if callable(check_fn):
                try:
                    c_score = float(check_fn(text))
                    reasons.append(f"Custom check: {c_score:.2f}")
                except Exception as e:
                    c_score = 0.0
                    reasons.append(f"Custom check error: {e}")

            # 2. Kiểm tra Required Sections (Headers)
            req_sections = crit.get("required_sections")
            if req_sections:
                missing_sec = [sec for sec in req_sections if sec.lower() not in text.lower()]
                if missing_sec:
                    sec_score = max(0.0, 1.0 - (len(missing_sec) / len(req_sections)))
                    c_score = min(c_score, sec_score)
                    reasons.append(f"Thiếu sections: {missing_sec}")

            # 3. Kiểm tra Keywords
            keywords = crit.get("keywords")
            if keywords:
                text_lower = text.lower()
                found_kw = [kw for kw in keywords if kw.lower() in text_lower]
                kw_score = len(found_kw) / len(keywords)
                c_score = min(c_score, kw_score)
                if kw_score < 1.0:
                    missing_kw = [kw for kw in keywords if kw not in found_kw]
                    reasons.append(f"Thiếu keywords: {missing_kw}")

            # 4. Kiểm tra Forbidden words
            forbidden = crit.get("forbidden")
            if forbidden:
                text_lower = text.lower()
                found_forbidden = [w for w in forbidden if w.lower() in text_lower]
                if found_forbidden:
                    c_score = max(0.0, c_score - (len(found_forbidden) * 0.3))
                    reasons.append(f"Vi phạm từ cấm: {found_forbidden}")

            # 5. Kiểm tra Min Words
            min_words = crit.get("min_words")
            if min_words:
                actual_words = len(text.strip().split())
                if actual_words < min_words:
                    word_score = actual_words / min_words
                    c_score = min(c_score, word_score)
                    reasons.append(f"Độ dài chưa đạt ({actual_words}/{min_words} words)")

            c_score = max(0.0, min(1.0, round(c_score, 2)))
            criteria_scores[c_name] = c_score
            criteria_details[c_name] = {
                "score": c_score,
                "weight": weight,
                "reasons": reasons or ["Đạt tiêu chuẩn"],
            }
            weighted_sum += c_score * weight

        final_score = round(weighted_sum / total_weight, 2)

        return ScoreResult(
            name=self.name,
            value=final_score,
            reason=f"Điểm Rubric G-Eval: {final_score:.2f} dựa trên {len(criteria)} tiêu chí.",
            metadata={
                "criteria_scores": criteria_scores,
                "criteria_details": criteria_details,
            },
        )


# ==============================================================================
# 5. HALLUCINATION SCORE METRIC (Tích hợp hallucination_detector.py)
# ==============================================================================

class HallucinationScoreMetric:
    """Tích hợp trực tiếp với `harness/validators/hallucination_detector.py`.

    Đo lường 4 trụ cột thực chứng và chuyển đổi thành điểm định lượng chuẩn Opik.
    """

    def __init__(self, name: str = "hallucination_score") -> None:
        self.name = name

    def score(
        self,
        text: str,
        base_dir: Optional[Union[str, Path]] = None,
        execution_logs: Optional[Union[str, List[Dict[str, Any]]]] = None,
        known_symbols: Optional[Set[str]] = None,
        source_code: Optional[str] = None,
        **kwargs: Any,
    ) -> ScoreResult:
        from harness.validators.hallucination_detector import audit_response

        audit_res = audit_response(
            text=text,
            base_dir=base_dir,
            execution_logs=execution_logs,
            known_symbols=known_symbols,
            source_code=source_code,
        )

        reason = (
            f"Phán quyết: {audit_res.verdict}. "
            + (
                f"Phát hiện {len(audit_res.violations)} vi phạm ảo giác."
                if audit_res.violations
                else "Vượt qua toàn bộ 4 trụ cột rào chắn chống ảo giác."
            )
        )

        return ScoreResult(
            name=self.name,
            value=audit_res.score,
            reason=reason,
            metadata={
                "verdict": audit_res.verdict,
                "violations": audit_res.violations,
                "missing_paths": audit_res.missing_paths,
                "speculative_phrases": audit_res.speculative_phrases,
                "unverified_claims": audit_res.unverified_claims,
                "unverified_symbols": audit_res.unverified_symbols,
                "verified_paths": audit_res.verified_paths,
                "verified_symbols": audit_res.verified_symbols,
            },
        )


# ==============================================================================
# 6. OPIK METRICS ADAPTER & OPIK EVALUATOR (Unified Orchestration Facade)
# ==============================================================================

class OpikMetricsAdapter:
    """Adapter cầu nối linh hoạt giữa Opik Native (khi có package opik) và Standalone Fallback."""

    def __init__(self) -> None:
        self.has_native = HAS_OPIK_PACKAGE
        self.mode = "native" if self.has_native else "standalone"
        logger.info(f"OpikMetricsAdapter khởi tạo ở chế độ: {self.mode}")

    def get_levenshtein_metric(self, case_sensitive: bool = False) -> Any:
        if self.has_native and hasattr(opik_metrics, "LevenshteinRatio"):
            try:
                return opik_metrics.LevenshteinRatio(case_sensitive=case_sensitive)
            except Exception:
                pass
        return LevenshteinRatioMetric(case_sensitive=case_sensitive)

    def get_equals_metric(self, case_sensitive: bool = True) -> Any:
        if self.has_native and hasattr(opik_metrics, "Equals"):
            try:
                return opik_metrics.Equals(case_sensitive=case_sensitive)
            except Exception:
                pass
        return EqualsMetric(case_sensitive=case_sensitive)

    def get_contains_metric(self, case_sensitive: bool = False) -> Any:
        if self.has_native and hasattr(opik_metrics, "Contains"):
            try:
                return opik_metrics.Contains(case_sensitive=case_sensitive)
            except Exception:
                pass
        return ContainsMetric(case_sensitive=case_sensitive)

    def get_regex_match_metric(self) -> Any:
        if self.has_native and hasattr(opik_metrics, "RegexMatch"):
            try:
                return opik_metrics.RegexMatch()
            except Exception:
                pass
        return RegexMatchMetric()

    def get_is_json_metric(self) -> Any:
        if self.has_native and hasattr(opik_metrics, "IsJson"):
            try:
                return opik_metrics.IsJson()
            except Exception:
                pass
        return IsJsonMetric()


class OpikEvaluator:
    """Bộ đánh giá định lượng tích hợp toàn diện cho Antigravity Harness Hub.

    Đóng gói mọi metrics Opik:
    - Heuristics: Levenshtein, Contains, Regex, Equals, JSON.
    - Token Quality: Degeneration Detector.
    - Workflow Planning: Trajectory Accuracy.
    - Rubric Evaluation: Rubric G-Eval.
    - Anti-Hallucination: Hallucination Score.
    """

    def __init__(self) -> None:
        self.adapter = OpikMetricsAdapter()
        self.levenshtein_metric = LevenshteinRatioMetric()
        self.contains_metric = ContainsMetric()
        self.regex_metric = RegexMatchMetric()
        self.equals_metric = EqualsMetric()
        self.json_metric = IsJsonMetric()
        self.degeneration_metric = DegenerationMetric()
        self.trajectory_metric = TrajectoryAccuracyMetric()
        self.rubric_metric = RubricGEvalMetric()
        self.hallucination_metric = HallucinationScoreMetric()

    # Convenience shortcuts
    def evaluate_levenshtein(self, output: str, reference: str, case_sensitive: bool = False) -> ScoreResult:
        return self.levenshtein_metric.score(output, reference, case_sensitive=case_sensitive)

    def evaluate_contains(self, output: str, substring: str, case_sensitive: bool = False) -> ScoreResult:
        return self.contains_metric.score(output, substring, case_sensitive=case_sensitive)

    def evaluate_regex(self, output: str, pattern: str) -> ScoreResult:
        return self.regex_metric.score(output, pattern)

    def evaluate_equals(self, output: str, reference: str, case_sensitive: bool = True) -> ScoreResult:
        return self.equals_metric.score(output, reference, case_sensitive=case_sensitive)

    def evaluate_json(self, output: str, required_keys: Optional[List[str]] = None) -> ScoreResult:
        return self.json_metric.score(output, required_keys=required_keys)

    def evaluate_degeneration(self, output: str) -> ScoreResult:
        return self.degeneration_metric.score(output)

    def evaluate_trajectory(
        self,
        planned_steps: List[Union[str, Dict[str, Any]]],
        executed_steps: List[Union[str, Dict[str, Any]]],
    ) -> ScoreResult:
        return self.trajectory_metric.score(planned_steps, executed_steps)

    def evaluate_rubric(self, text: str, criteria: List[Dict[str, Any]]) -> ScoreResult:
        return self.rubric_metric.score(text, criteria)

    def evaluate_hallucination(
        self,
        text: str,
        base_dir: Optional[Union[str, Path]] = None,
        execution_logs: Optional[Union[str, List[Dict[str, Any]]]] = None,
        known_symbols: Optional[Set[str]] = None,
        source_code: Optional[str] = None,
    ) -> ScoreResult:
        return self.hallucination_metric.score(
            text=text,
            base_dir=base_dir,
            execution_logs=execution_logs,
            known_symbols=known_symbols,
            source_code=source_code,
        )

    def compute_composite_score(
        self,
        scores: Dict[str, ScoreResult],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Tính điểm tổng hợp có trọng số từ tập các ScoreResult."""
        if not scores:
            return 1.0

        if weights is None:
            weights = {k: 1.0 for k in scores.keys()}

        total_weight = sum(weights.get(k, 1.0) for k in scores.keys())
        if total_weight <= 0:
            return 1.0

        weighted_val = sum(res.value * weights.get(k, 1.0) for k, res in scores.items())
        return round(weighted_val / total_weight, 2)
