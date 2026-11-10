"""Module đánh giá tính thực chứng ngữ nghĩa (Semantic Judge / Semantic Grounding Evaluator).

Cung cấp khả năng đánh giá thực chứng xác định (deterministic / lightweight evaluator)
nhằm rà soát các phát biểu võ đoán (speculation), thiên kiến hùa theo người dùng (sycophancy)
và các tuyên bố không có bằng chứng (unverified claims), kèm cơ chế xử lý lỗi/fallback an toàn.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from harness.validators.hallucination_detector import (
    SPECULATIVE_PATTERNS,
    SYCOPHANCY_PATTERNS,
    COMPLETION_CLAIM_PATTERNS,
    API_CLAIM_PATTERNS,
    detect_speculative_language,
    detect_sycophancy,
    verify_api_and_investigation_claims,
    verify_execution_claims,
)

logger = logging.getLogger(__name__)


def evaluate_semantic_grounding(
    text: str,
    *,
    execution_logs: Optional[list[dict[str, Any]]] = None,
    allow_unverified_claims: bool = False,
) -> dict[str, Any]:
    """Đánh giá tính thực chứng ngữ nghĩa của văn bản.

    Args:
        text: Chuỗi văn bản cần kiểm định (báo cáo của Maker, Critic, hoặc kết luận).
        execution_logs: Danh sách logs thực thi (nếu có) để đối soát các tuyên bố pass test / API.
        allow_unverified_claims: Cho phép bỏ qua kiểm tra completion claim nếu đang trong giai đoạn design.

    Returns:
        dict chứa:
            - is_grounded: bool (True nếu không có vi phạm nghiêm trọng)
            - verdict: "APPROVE" | "REJECT"
            - score: float (0.0 đến 1.0)
            - violations: list[str]
            - speculative_phrases: list[str]
            - sycophancy_phrases: list[str]
            - unverified_claims: list[str]
            - unverified_api_claims: list[str]
            - details: dict[str, Any]
    """
    fallback_res: dict[str, Any] = {
        "is_grounded": True,
        "verdict": "APPROVE",
        "score": 1.0,
        "violations": [],
        "speculative_phrases": [],
        "sycophancy_phrases": [],
        "unverified_claims": [],
        "unverified_api_claims": [],
        "details": {"status": "empty_input"},
    }

    if not isinstance(text, str) or not text.strip():
        return fallback_res

    try:
        violations: list[str] = []
        score = 1.0

        # 1. Phát hiện từ ngữ võ đoán / phỏng đoán (Speculation)
        speculative_phrases = detect_speculative_language(text)
        if speculative_phrases:
            score -= min(0.4, 0.15 * len(speculative_phrases))
            violations.append(
                f"Phát hiện {len(speculative_phrases)} cụm từ võ đoán: {', '.join(speculative_phrases[:3])}"
            )

        # 2. Phát hiện thiên kiến xác nhận / hùa theo người dùng (Sycophancy)
        sycophancy_phrases = detect_sycophancy(text)
        if sycophancy_phrases:
            score -= min(0.4, 0.20 * len(sycophancy_phrases))
            violations.append(
                f"Phát hiện {len(sycophancy_phrases)} câu hùa theo giả định (sycophancy): {', '.join(sycophancy_phrases[:3])}"
            )

        # 3. Kiểm định tuyên bố hoàn thành / test pass (Execution Claims)
        unverified_claims: list[str] = []
        if not allow_unverified_claims:
            exec_res = verify_execution_claims(text, execution_logs)
            is_exec_verified = exec_res.get("valid", True) if isinstance(exec_res, dict) else True
            unverified_exec = exec_res.get("unverified_claims", []) if isinstance(exec_res, dict) else []
            if not is_exec_verified or unverified_exec:
                unverified_claims.extend(unverified_exec)
                score -= min(0.4, 0.20 * len(unverified_exec))
                violations.append(
                    f"Tuyên bố kiểm thử/thành công thiếu bằng chứng thực thi: {', '.join(unverified_exec[:2])}"
                )

        # 4. Kiểm định tuyên bố quyền hạn API / hạ tầng (API Claims)
        api_res = verify_api_and_investigation_claims(text, execution_logs)
        unverified_api = api_res.get("unverified_api_claims", []) if isinstance(api_res, dict) else []
        is_api_verified = api_res.get("valid", True) if isinstance(api_res, dict) else True
        if not is_api_verified or unverified_api:
            score -= min(0.4, 0.20 * len(unverified_api))
            violations.append(
                f"Tuyên bố quyền hạn API/hạ tầng thiếu raw HTTP log: {', '.join(unverified_api[:2])}"
            )

        final_score = max(0.0, min(1.0, round(score, 2)))
        verdict = "APPROVE" if not violations and final_score >= 0.8 else "REJECT"
        is_grounded = verdict == "APPROVE"

        return {
            "is_grounded": is_grounded,
            "verdict": verdict,
            "score": final_score,
            "violations": violations,
            "speculative_phrases": speculative_phrases,
            "sycophancy_phrases": sycophancy_phrases,
            "unverified_claims": unverified_claims,
            "unverified_api_claims": unverified_api,
            "details": {
                "text_length": len(text),
                "total_violations": len(violations),
            },
        }

    except Exception as exc:
        logger.warning("Error evaluating semantic grounding, falling back: %s", exc)
        return {
            "is_grounded": False,
            "verdict": "REJECT",
            "score": 0.0,
            "violations": [f"Lỗi phân tích cú pháp/ngữ nghĩa: {str(exc)}"],
            "speculative_phrases": [],
            "sycophancy_phrases": [],
            "unverified_claims": [],
            "unverified_api_claims": [],
            "details": {"error": str(exc), "status": "fallback_error"},
        }
