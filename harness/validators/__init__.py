"""Validators package for Antigravity Harness Hub.
Chứa các bộ kiểm định tính toàn vẹn, chống ảo giác và xác thực thực chứng.
"""

from harness.validators.deterministic_rules import (
    RuleAuditResult,
    audit_deterministic_constraints,
    verify_bullet_points,
    verify_forbidden_words,
    verify_json_format,
    verify_markdown_headers,
    verify_paragraph_count,
    verify_required_keywords,
    verify_start_end_phrase,
    verify_word_count,
)
from harness.validators.hallucination_detector import (
    AuditResult,
    audit_response,
    detect_speculative_language,
    verify_execution_claims,
    verify_file_paths,
)
from harness.validators.session_diagnostics import (
    SessionDiagnosticReport,
    calculate_context_growth,
    detect_model_inheritance_waste,
    detect_polling_loops,
    detect_view_file_redundancy,
    diagnose_session,
)

__all__ = [
    "AuditResult",
    "RuleAuditResult",
    "SessionDiagnosticReport",
    "audit_deterministic_constraints",
    "audit_response",
    "calculate_context_growth",
    "detect_model_inheritance_waste",
    "detect_polling_loops",
    "detect_speculative_language",
    "detect_view_file_redundancy",
    "diagnose_session",
    "verify_bullet_points",
    "verify_execution_claims",
    "verify_file_paths",
    "verify_forbidden_words",
    "verify_json_format",
    "verify_markdown_headers",
    "verify_paragraph_count",
    "verify_required_keywords",
    "verify_start_end_phrase",
    "verify_word_count",
]

