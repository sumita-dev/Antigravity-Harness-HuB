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
from harness.validators.mutation_verifier import (
    Mutant,
    MutationReport,
    generate_mutants,
    verify_test_lethality,
)
from harness.validators.policy_interceptor import (
    DESTRUCTIVE_SHELL_PATTERNS,
    PolicyAction,
    PolicyDecision,
    SENSITIVE_SYSTEM_PATHS,
    evaluate_command_policy,
    is_command_safe,
)
from harness.validators.self_correction import (
    CorrectionAttempt,
    SelfCorrectionResult,
    default_deterministic_fixer,
    run_self_correction_loop,
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
    "CorrectionAttempt",
    "DESTRUCTIVE_SHELL_PATTERNS",
    "Mutant",
    "MutationReport",
    "PolicyAction",
    "PolicyDecision",
    "RuleAuditResult",
    "SENSITIVE_SYSTEM_PATHS",
    "SelfCorrectionResult",
    "SessionDiagnosticReport",
    "audit_deterministic_constraints",
    "audit_response",
    "calculate_context_growth",
    "default_deterministic_fixer",
    "detect_model_inheritance_waste",
    "detect_polling_loops",
    "detect_speculative_language",
    "detect_view_file_redundancy",
    "diagnose_session",
    "evaluate_command_policy",
    "generate_mutants",
    "is_command_safe",
    "run_self_correction_loop",
    "verify_bullet_points",
    "verify_execution_claims",
    "verify_file_paths",
    "verify_forbidden_words",
    "verify_json_format",
    "verify_markdown_headers",
    "verify_paragraph_count",
    "verify_required_keywords",
    "verify_start_end_phrase",
    "verify_test_lethality",
    "verify_word_count",
]

