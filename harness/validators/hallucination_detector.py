"""Module kiểm định và rào chắn chống ảo giác (Autonomous Anti-Hallucination Guard).

Vận hành 4 trụ cột rào chắn thực chứng tự động:
1. verify_file_paths: Quét các đường dẫn file trong văn bản, kiểm tra tính tồn tại thực tế trên filesystem.
2. detect_speculative_language: Phát hiện và triệt tiêu từ ngữ võ đoán / phỏng đoán không có căn cứ.
3. verify_execution_claims: Bắt buộc các tuyên bố thành công phải có trace log thực thi với exit code == 0.
4. verify_symbol_grounding: Đối soát ký hiệu (Symbol & AST Grounding) với AST mã nguồn hoặc tập known_symbols.
5. audit_response: Kiểm toán tổng hợp và xuất AuditResult (APPROVE / REJECT) tự động.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


# Các từ ngữ/cụm từ võ đoán, phỏng đoán không căn cứ (Red Flag Phrases)
SPECULATIVE_PATTERNS = [
    # Tiếng Anh
    r"\bshould\s+work\b",
    r"\bprobably\b",
    r"\bseems\s+to\b",
    r"\blooks\s+good\s+to\s+me\b",
    r"\bassuming\s+it\b",
    r"\bit\s+should\s+be\s+fine\b",
    r"\blikely\s+works?\b",
    r"\bpresumably\b",
    r"\bcan't\s+go\s+wrong\b",
    r"\bpretty\s+sure\b",
    r"\blooks\s+fine\b",
    # Tiếng Việt
    r"chắc\s+là",
    r"dường\s+như",
    r"có\s+lẽ",
    r"sẽ\s+hoạt\s+động\s+bình\s+thường\s+mà\s+không\s+cần\s+test",
    r"nghĩ\s+là\s+ổn",
    r"chắc\s+chắn\s+sẽ\s+chạy",
    r"không\s+cần\s+kiểm\s+tra\s+lại",
    r"đoán\s+chừng",
    r"không\s+thể\s+sai\s+được",
    r"chắc\s+ăn",
    r"cứ\s+thế\s+mà\s+chạy",
]

# Các tuyên bố hoàn thành / thành công cần bằng chứng thực thi
COMPLETION_CLAIM_PATTERNS = [
    # Tiếng Anh
    r"\btests?\s+(?:have\s+)?passed\b",
    r"\ball\s+tests?\s+pass\b",
    r"\bpassed\s+all\s+tests\b",
    r"\bfixed\s+successfully\b",
    r"\bsuccessfully\s+fixed\b",
    r"\bbuild\s+succeeded\b",
    r"\bverification\s+succeeded\b",
    r"\ball\s+checks\s+passed\b",
    # Tiếng Việt
    r"tất\s+cả\s+test\s+đã\s+pass",
    r"test\s+đã\s+pass",
    r"pass\s+100%",
    r"fix\s+thành\s+công",
    r"sửa\s+thành\s+công",
    r"kiểm\s+thử\s+thành\s+công",
    r"đã\s+hoàn\s+tất\s+kiểm\s+định",
    r"đã\s+pass\s+hết",
]

# Pattern nhận diện đường dẫn file trong markdown/code text
PATH_PATTERNS = [
    re.compile(r"`([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)`"),
    re.compile(r"\]\((?:file:///)?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)\)"),
    re.compile(r"(?:file:\/\/\/)([a-zA-Z0-9_\-\.:/\\]+\.[a-zA-Z0-9_]+)"),
]

# Pattern nhận diện symbols dạng code trong backticks (hàm/class/biến)
SYMBOL_BACKTICK_PATTERN = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*(?:\(\))?)`")

# Bỏ qua các URL web hoặc scheme đặc biệt
IGNORED_PREFIXES = ("http://", "https://", "ftp://", "mailto:", "conversation://")
IGNORED_EXTENSIONS = (".com", ".org", ".net", ".io", ".dev", ".ai", ".vn")

# Bỏ qua các từ khóa phổ biến trong lập trình khi đối soát symbol
COMMON_PROGRAMMING_KEYWORDS = {
    "true", "false", "null", "none", "undefined", "self", "this", "async", "await",
    "return", "yield", "class", "def", "function", "import", "from", "export",
    "try", "catch", "except", "finally", "throw", "raise", "if", "else", "elif",
    "for", "while", "break", "continue", "pass", "in", "is", "not", "and", "or",
    "const", "let", "var", "int", "str", "bool", "float", "dict", "list", "set",
    "tuple", "any", "optional", "union",
}


@dataclass
class AuditResult:
    """Kết quả kiểm toán phản hồi / báo cáo theo chuẩn rào chắn chống ảo giác."""
    verdict: str  # 'APPROVE' hoặc 'REJECT'
    score: float  # Điểm tin cậy từ 0.0 đến 1.0 (1.0 = hoàn toàn đáng tin cậy)
    violations: List[str] = field(default_factory=list)
    verified_paths: List[str] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
    speculative_phrases: List[str] = field(default_factory=list)
    unverified_claims: List[str] = field(default_factory=list)
    verified_symbols: List[str] = field(default_factory=list)
    unverified_symbols: List[str] = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        return self.verdict == "APPROVE"

    def to_score_result(self) -> Any:
        """Chuyển đổi kết quả kiểm toán sang định dạng ScoreResult chuẩn Opik."""
        from harness.validators.opik_evaluator import ScoreResult
        return ScoreResult(
            name="hallucination_score",
            value=self.score,
            reason=(
                f"Phán quyết: {self.verdict}. "
                + (
                    f"Phát hiện {len(self.violations)} vi phạm ảo giác."
                    if self.violations
                    else "Vượt qua toàn bộ 4 trụ cột rào chắn chống ảo giác."
                )
            ),
            metadata={
                "verdict": self.verdict,
                "violations": self.violations,
                "verified_paths": self.verified_paths,
                "missing_paths": self.missing_paths,
                "speculative_phrases": self.speculative_phrases,
                "unverified_claims": self.unverified_claims,
                "verified_symbols": self.verified_symbols,
                "unverified_symbols": self.unverified_symbols,
            },
        )


def verify_file_paths(
    text: str,
    base_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Trụ cột 1: Quét các đường dẫn file trong văn bản, kiểm tra tính tồn tại thực tế.

    Xử lý an toàn cho cả đường dẫn tương đối và tuyệt đối.
    Trả về dict: {
        "valid": bool,
        "verified_paths": [...],
        "missing_paths": [...]
    }
    """
    if base_dir is None:
        base_dir = Path.cwd()
    else:
        base_dir = Path(base_dir).resolve()

    extracted_paths: Set[str] = set()

    for pattern in PATH_PATTERNS:
        for match in pattern.finditer(text):
            p_str = match.group(1).strip()
            # Bỏ qua url web
            if p_str.startswith(IGNORED_PREFIXES):
                continue
            if any(p_str.endswith(ext) for ext in IGNORED_EXTENSIONS):
                continue
            # Bỏ qua nếu không chứa ký tự phân tách thư mục và không phải tên file có đuôi hợp lệ
            if "/" in p_str or "\\" in p_str or "." in p_str:
                extracted_paths.add(p_str)

    verified: List[str] = []
    missing: List[str] = []

    for path_str in sorted(extracted_paths):
        cleaned = path_str.replace("file:///", "").strip()
        p = Path(cleaned)

        target: Path
        if p.is_absolute():
            target = p
        else:
            target = base_dir / p

        try:
            if target.exists():
                verified.append(path_str)
            else:
                missing.append(path_str)
        except OSError:
            missing.append(path_str)

    return {
        "valid": len(missing) == 0,
        "verified_paths": verified,
        "missing_paths": missing,
    }


def detect_speculative_language(text: str) -> List[str]:
    """Trụ cột 2: Quét các từ ngữ võ đoán / phỏng đoán không có căn cứ thực chứng.

    Trả về danh sách các cụm từ vi phạm tìm thấy trong text.
    """
    violations: List[str] = []
    text_lower = text.lower()

    for pattern in SPECULATIVE_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for m in matches:
            if m not in violations:
                violations.append(m)

    return violations


def verify_execution_claims(
    text: str,
    execution_logs: Optional[Union[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Trụ cột 3: Bắt buộc các tuyên bố thành công phải có trace log với exit code == 0 đi kèm.

    Trả về dict: {
        "valid": bool,
        "claims_found": [...],
        "has_valid_execution": bool,
        "unverified_claims": [...]
    }
    """
    text_lower = text.lower()
    claims_found: List[str] = []

    for pattern in COMPLETION_CLAIM_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for m in matches:
            if m not in claims_found:
                claims_found.append(m)

    # Nếu không có tuyên bố thành công nào, mặc định là hợp lệ
    if not claims_found:
        return {
            "valid": True,
            "claims_found": [],
            "has_valid_execution": True,
            "unverified_claims": [],
        }

    # Kiểm tra log thực thi
    has_valid_execution = False

    if execution_logs:
        if isinstance(execution_logs, str):
            # Kiểm tra xem log text có dấu hiệu exit code 0 hoặc kết quả pass thực tế
            has_exit_zero = (
                "exited with code 0" in execution_logs
                or "exit code: 0" in execution_logs
                or "returncode=0" in execution_logs
                or "code 0" in execution_logs
            )
            has_pass_summary = (
                "passed in" in execution_logs
                or "100% passed" in execution_logs
                or "tests passed" in execution_logs
                or "passed" in execution_logs
            )
            if has_exit_zero or has_pass_summary:
                has_valid_execution = True
        elif isinstance(execution_logs, list):
            for entry in execution_logs:
                if isinstance(entry, dict) and entry.get("exit_code") == 0:
                    has_valid_execution = True
                    break

    unverified = claims_found if not has_valid_execution else []

    return {
        "valid": has_valid_execution,
        "claims_found": claims_found,
        "has_valid_execution": has_valid_execution,
        "unverified_claims": unverified,
    }


def extract_symbols_from_code(source_code: str) -> Set[str]:
    """Trích xuất symbols (hàm, class, biến gán) từ mã nguồn Python qua AST."""
    symbols: Set[str] = set()
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.add(node.name)
            elif isinstance(node, ast.ClassDef):
                symbols.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                symbols.add(node.id)
    except SyntaxError:
        # Fallback regex nếu là ngôn ngữ khác (JS/TS/v.v.) hoặc lỗi cú pháp
        matches = re.findall(r"(?:class|function|def|const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)", source_code)
        symbols.update(matches)
    return symbols


def verify_symbol_grounding(
    text: str,
    known_symbols: Optional[Set[str]] = None,
    source_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Trụ cột 4: Đối soát Symbol & AST Grounding.

    Kiểm tra xem các symbols được trích dẫn trong văn bản (`func()` hoặc `Class`)
    có tồn tại trong `known_symbols` hoặc trong `source_code` đã khai báo hay không.
    """
    valid_symbols: Set[str] = set()
    if known_symbols:
        valid_symbols.update(known_symbols)
    if source_code:
        valid_symbols.update(extract_symbols_from_code(source_code))

    if not valid_symbols:
        return {
            "valid": True,
            "verified_symbols": [],
            "unverified_symbols": [],
        }

    # Trích xuất các symbol trong backticks
    extracted = SYMBOL_BACKTICK_PATTERN.findall(text)
    verified: List[str] = []
    unverified: List[str] = []

    for sym in extracted:
        clean = sym.replace("()", "").strip()
        # Bỏ qua keywords thông dụng hoặc tên quá ngắn
        if clean.lower() in COMMON_PROGRAMMING_KEYWORDS or len(clean) <= 2:
            continue
        # Bỏ qua nếu là tên file (có dấu chấm)
        if "." in clean:
            continue

        if clean in valid_symbols:
            verified.append(clean)
        else:
            unverified.append(clean)

    return {
        "valid": len(unverified) == 0,
        "verified_symbols": sorted(list(set(verified))),
        "unverified_symbols": sorted(list(set(unverified))),
    }


def audit_response(
    text: str,
    base_dir: Optional[Union[str, Path]] = None,
    execution_logs: Optional[Union[str, List[Dict[str, Any]]]] = None,
    known_symbols: Optional[Set[str]] = None,
    source_code: Optional[str] = None,
) -> AuditResult:
    """Kiểm toán tổng hợp phản hồi/báo cáo theo 4 trụ cột rào chắn chống ảo giác tự động.

    Trả về AuditResult với phán quyết (APPROVE / REJECT) và score.
    """
    violations: List[str] = []

    # 1. Trụ cột Path Veracity
    path_check = verify_file_paths(text, base_dir=base_dir)
    if not path_check["valid"]:
        for p in path_check["missing_paths"]:
            violations.append(f"Ảo giác đường dẫn: file không tồn tại '{p}'")

    # 2. Trụ cột Strict Evidence-First (Speculative Language)
    speculative_phrases = detect_speculative_language(text)
    if speculative_phrases:
        for phrase in speculative_phrases:
            violations.append(f"Ngôn ngữ võ đoán không có căn cứ: '{phrase}'")

    # 3. Trụ cột Deterministic Execution Claims
    exec_check = verify_execution_claims(text, execution_logs=execution_logs)
    if not exec_check["valid"]:
        for claim in exec_check["unverified_claims"]:
            violations.append(
                f"Tuyên bố thành công không có bằng chứng thực thi (exit code 0): '{claim}'"
            )

    # 4. Trụ cột Symbol & AST Grounding
    symbol_check = verify_symbol_grounding(
        text, known_symbols=known_symbols, source_code=source_code
    )
    if not symbol_check["valid"]:
        for sym in symbol_check["unverified_symbols"]:
            violations.append(
                f"Ảo giác ký hiệu: symbol `{sym}` không tồn tại trong AST hoặc tập declared symbols"
            )

    # Tính toán điểm tin cậy (Score)
    total_penalties = (
        len(path_check["missing_paths"]) * 0.3
        + len(speculative_phrases) * 0.2
        + len(exec_check["unverified_claims"]) * 0.3
        + len(symbol_check["unverified_symbols"]) * 0.2
    )
    score = max(0.0, 1.0 - total_penalties)
    score = round(score, 2)

    verdict = "APPROVE" if not violations else "REJECT"

    return AuditResult(
        verdict=verdict,
        score=score,
        violations=violations,
        verified_paths=path_check["verified_paths"],
        missing_paths=path_check["missing_paths"],
        speculative_phrases=speculative_phrases,
        unverified_claims=exec_check["unverified_claims"],
        verified_symbols=symbol_check["verified_symbols"],
        unverified_symbols=symbol_check["unverified_symbols"],
    )
