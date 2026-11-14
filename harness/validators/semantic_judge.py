"""Module đánh giá tính thực chứng ngữ nghĩa (Semantic Judge / Semantic Grounding Evaluator).

Cung cấp khả năng đánh giá thực chứng xác định (deterministic / lightweight evaluator)
nhằm rà soát các phát biểu võ đoán (speculation), thiên kiến hùa theo người dùng (sycophancy)
và các tuyên bố không có bằng chứng (unverified claims), kèm cơ chế xử lý lỗi/fallback an toàn.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
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


def verify_marketing_claim_grounding(
    script_text: str,
    dossier: dict[str, Any],
    *,
    claims: Optional[list[str]] = None,
    use_llm_judge: bool = False,
) -> dict[str, Any]:
    """Deterministic 1:1 claim_id mapping against dossier + optional google.genai entailment check."""
    dossier_map: dict[str, Any] = {}
    if isinstance(dossier, dict):
        raw_claims = dossier.get("claims") or dossier.get("facts") or []
        if isinstance(raw_claims, list):
            for item in raw_claims:
                if isinstance(item, dict):
                    cid = str(item.get("id") or item.get("claim_id") or "").strip()
                    if cid:
                        dossier_map[cid] = item
                elif isinstance(item, str) and item.strip():
                    dossier_map[item.strip()] = {"id": item.strip(), "text": item.strip()}
        elif isinstance(raw_claims, dict):
            for k, v in raw_claims.items():
                dossier_map[str(k)] = v

    cited_ids: list[str] = []
    seen_ids: set[str] = set()

    def _add_cited(cid: str) -> None:
        cid_clean = cid.strip()
        if cid_clean and cid_clean not in seen_ids:
            seen_ids.add(cid_clean)
            cited_ids.append(cid_clean)

    if isinstance(script_text, str):
        for match in re.findall(r"\[([a-zA-Z0-9_\-]+)\]", script_text):
            if match.lower().startswith("claim") or re.fullmatch(r"C\d+", match, re.IGNORECASE) or match in dossier_map:
                _add_cited(match)
        for known_id in dossier_map:
            if re.search(r"\b" + re.escape(known_id) + r"\b", script_text):
                _add_cited(known_id)

    if claims:
        for c in claims:
            if isinstance(c, str):
                _add_cited(c)

    matched_claims = [cid for cid in cited_ids if cid in dossier_map]
    ungrounded_claims = [cid for cid in cited_ids if cid not in dossier_map]
    claim_mapping = {cid: dossier_map[cid] for cid in matched_claims}

    errors: list[str] = []
    if ungrounded_claims:
        errors.append(f"Ungrounded claim IDs not found in dossier: {', '.join(ungrounded_claims)}")

    llm_judge_used = False
    llm_judge_result: Optional[dict[str, Any]] = None

    if use_llm_judge and os.environ.get("GEMINI_API_KEY"):
        try:
            from google import genai  # type: ignore

            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            entailment_schema = {
                "type": "object",
                "properties": {
                    "entailed": {"type": "boolean"},
                    "ungrounded_statements": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["entailed", "ungrounded_statements", "reason"],
            }
            prompt = (
                "Verify whether all factual claims in the script are entailed by the dossier.\n"
                f"Dossier:\n{json.dumps(dossier, ensure_ascii=False)}\n\n"
                f"Script:\n{script_text}"
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": entailment_schema,
                },
            )
            parsed = json.loads(getattr(resp, "text", "") or "{}")
            llm_judge_used = True
            llm_judge_result = parsed
            if not parsed.get("entailed", True):
                ungrounded_llm = parsed.get("ungrounded_statements") or []
                errors.append(
                    f"LLM entailment check failed: {parsed.get('reason', '')} ({', '.join(ungrounded_llm)})"
                )
        except Exception as exc:
            llm_judge_result = {"error": str(exc)}

    is_grounded = len(errors) == 0
    return {
        "is_grounded": is_grounded,
        "verdict": "APPROVE" if is_grounded else "REJECT",
        "matched_claims": matched_claims,
        "ungrounded_claims": ungrounded_claims,
        "claim_mapping": claim_mapping,
        "llm_judge_used": llm_judge_used,
        "llm_judge_result": llm_judge_result,
        "errors": errors,
    }


_DUMMY_COMMAND_PATTERNS = (
    re.compile(r"^\s*(?:true|:|echo\b|printf\b)", re.IGNORECASE),
    re.compile(r"python(?:\d+(?:\.\d+)?)?(?:\.exe)?\s+-c\s+[\"'](?:print\s*\(|pass\b|sys\.exit\s*\(\s*0\s*\))", re.IGNORECASE),
)

_REAL_TEST_COMMAND_PATTERNS = (
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bunittest\b", re.IGNORECASE),
    re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b", re.IGNORECASE),
    re.compile(r"\b(?:vitest|jest|mocha)\b", re.IGNORECASE),
    re.compile(r"\bcargo\s+test\b", re.IGNORECASE),
    re.compile(r"\bgo\s+test\b", re.IGNORECASE),
)


def verify_diff_test_coverage(
    diff_files: list[str],
    executed_commands: list[str],
    test_output: str = "",
) -> dict[str, Any]:
    """Detect dummy execution commands vs real test runs covering modified modules/tests."""
    dummy_commands_detected: list[str] = []
    real_test_commands: list[str] = []

    for cmd in executed_commands or []:
        if not isinstance(cmd, str) or not cmd.strip():
            continue
        is_dummy = any(p.search(cmd) for p in _DUMMY_COMMAND_PATTERNS)
        is_real = any(p.search(cmd) for p in _REAL_TEST_COMMAND_PATTERNS)
        if is_dummy and not is_real:
            dummy_commands_detected.append(cmd)
        elif is_real:
            real_test_commands.append(cmd)

    reasons: list[str] = []
    uncovered_files: list[str] = []

    if not real_test_commands:
        if dummy_commands_detected:
            reasons.append(f"Only dummy execution commands detected: {dummy_commands_detected}")
        else:
            reasons.append("No real test runner commands executed")
    else:
        # Check if targeted test commands omit modified test files or modules
        # A broad suite run (e.g. `pytest`, `python -m pytest -q`) covers all files.
        is_broad_run = any(
            re.search(r"\bpytest\b(?:\s+-[a-zA-Z0-9=_]+)*\s*$", cmd.strip())
            or re.search(r"\bpytest\b.*\btests/?\s*$", cmd.strip())
            or re.search(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b", cmd.strip())
            for cmd in real_test_commands
        )
        if not is_broad_run and diff_files:
            combined_cmds = " ".join(real_test_commands).lower()
            combined_out = (test_output or "").lower()
            for fpath in diff_files:
                stem = Path(fpath).stem.lower()
                if stem.startswith("test_"):
                    if stem not in combined_cmds and stem not in combined_out:
                        uncovered_files.append(fpath)
                elif fpath.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                    # Source file: covered if its name or test_<stem> appears in commands or output
                    if stem not in combined_cmds and f"test_{stem}" not in combined_cmds and stem not in combined_out:
                        uncovered_files.append(fpath)
            if uncovered_files:
                reasons.append(f"Modified files not covered by targeted test commands: {uncovered_files}")

    is_covered = len(real_test_commands) > 0 and len(reasons) == 0
    return {
        "is_covered": is_covered,
        "verdict": "APPROVE" if is_covered else "REJECT",
        "real_test_commands": real_test_commands,
        "dummy_commands_detected": dummy_commands_detected,
        "uncovered_files": uncovered_files,
        "reasons": reasons,
    }
