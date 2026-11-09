"""Unit tests cho module hallucination_detector.py."""

from pathlib import Path
import pytest

from harness.validators.hallucination_detector import (
    AuditResult,
    audit_response,
    detect_speculative_language,
    detect_sycophancy,
    extract_symbols_from_code,
    verify_api_and_investigation_claims,
    verify_evidence_table,
    verify_execution_claims,
    verify_file_paths,
    verify_symbol_grounding,
)


REPO_DIR = Path(__file__).resolve().parent.parent


def test_verify_file_paths_existing():
    """Kiểm tra đường dẫn file có thật trong repo."""
    text = (
        "Chúng ta đã cấu hình file `configs/harness_config.json` và "
        "tham chiếu `requirements.txt` cùng file [README](file:///README.md)."
    )
    res = verify_file_paths(text, base_dir=REPO_DIR)
    assert res["valid"] is True
    assert len(res["missing_paths"]) == 0
    assert len(res["verified_paths"]) >= 3


def test_verify_file_paths_missing():
    """Kiểm tra phát hiện file bịa/không tồn tại."""
    text = "Vui lòng xem `harness/phantom_unknown_file.py` để biết chi tiết."
    res = verify_file_paths(text, base_dir=REPO_DIR)
    assert res["valid"] is False
    assert "harness/phantom_unknown_file.py" in res["missing_paths"]


def test_detect_speculative_language_clean():
    """Văn bản chuẩn, không chứa ngôn ngữ võ đoán."""
    text = "Đã thực hiện cập nhật mã nguồn theo đúng đặc tả kỹ thuật."
    violations = detect_speculative_language(text)
    assert len(violations) == 0


def test_detect_speculative_language_violations():
    """Văn bản chứa từ ngữ võ đoán tiếng Anh & tiếng Việt."""
    text_en = "This fix should work and probably solves the bug without verification."
    violations_en = detect_speculative_language(text_en)
    assert len(violations_en) >= 2
    assert any("should work" in v for v in violations_en)
    assert any("probably" in v for v in violations_en)

    text_vi = "Đoạn code này chắc là ổn, dường như sẽ hoạt động bình thường mà không cần test."
    violations_vi = detect_speculative_language(text_vi)
    assert len(violations_vi) >= 2
    assert any("chắc là" in v for v in violations_vi)
    assert any("dường như" in v for v in violations_vi)


def test_detect_sycophancy_clean():
    """Văn bản khách quan, không chứa cụm từ hùa theo người dùng."""
    text = "Kết quả điều tra thực nghiệm cho thấy module hoạt động theo đúng tài liệu API."
    violations = detect_sycophancy(text)
    assert len(violations) == 0


def test_detect_sycophancy_violations():
    """Phát hiện chính xác các câu hùa theo giả định người dùng (EN & VI)."""
    text_vi = (
        "Giả thuyết của anh hoàn toàn đúng, họ sử dụng shared voices.\n"
        "Đúng như sếp nghi ngờ, giả thuyết đúng 90% và hoàn toàn trùng khớp với giả định."
    )
    violations_vi = detect_sycophancy(text_vi)
    assert len(violations_vi) >= 3
    assert any("giả thuyết" in v for v in violations_vi)
    assert any("đúng như" in v for v in violations_vi)

    text_en = (
        "Your hypothesis is correct and confirms your suspicion.\n"
        "Exactly as you suspected, this proves your theory."
    )
    violations_en = detect_sycophancy(text_en)
    assert len(violations_en) >= 3
    assert any("hypothesis is correct" in v for v in violations_en)
    assert any("suspected" in v for v in violations_en)


def test_verify_api_claims_without_raw_http():
    """Tuyên bố quyền hạn API nhưng thiếu raw HTTP status code -> REJECT / invalid."""
    text = "Tài khoản free tier có thể gọi được API ElevenLabs shared voices mà không cần trả phí."
    res = verify_api_and_investigation_claims(text, execution_logs=None)
    assert res["valid"] is False
    assert len(res["unverified_api_claims"]) >= 1
    assert res["has_raw_http_evidence"] is False

    # Có log nhưng không chứa raw HTTP status code
    invalid_log = "Running test script... done with success."
    res2 = verify_api_and_investigation_claims(text, execution_logs=invalid_log)
    assert res2["valid"] is False


def test_verify_api_claims_with_raw_http():
    """Tuyên bố quyền hạn API có raw HTTP status code đi kèm -> Valid."""
    text = "Tài khoản free tier gọi API ElevenLabs báo lỗi paid_plan_required."
    raw_log = "curl -i https://api.elevenlabs.io/v1/voices -> HTTP 402 Payment Required\nstatus_code=402"
    res = verify_api_and_investigation_claims(text, execution_logs=raw_log)
    assert res["valid"] is True
    assert len(res["unverified_api_claims"]) == 0
    assert res["has_raw_http_evidence"] is True

    # Test với danh sách dict log chứa status code HTTP
    dict_log = [{"command": "curl ...", "status_code": 402, "output": "paid_plan_required"}]
    res_dict = verify_api_and_investigation_claims(text, execution_logs=dict_log)
    assert res_dict["valid"] is True


def test_verify_evidence_table():
    """Kiểm tra định dạng bảng 3 cột thực chứng (Evidence Table)."""
    valid_table_text = """
## Báo Cáo Thực Nghiệm
| Vấn đề nghi vấn | Lệnh thực nghiệm & Raw Response | Kết luận thực chứng |
| :--- | :--- | :--- |
| Free tier có gọi được shared voice không? | `curl -s ...` -> HTTP 402 paid_plan_required | Sai, API chặn mã 402 bắt buộc trả phí |
"""
    res_valid = verify_evidence_table(valid_table_text)
    assert res_valid["valid"] is True
    assert res_valid["has_table"] is True
    assert res_valid["headers_valid"] is True
    assert res_valid["row_count"] == 1

    # Bảng thiếu cột hoặc tiêu đề sai
    invalid_table_text = """
| Cột 1 | Cột 2 |
| --- | --- |
| Dữ liệu 1 | Dữ liệu 2 |
"""
    res_invalid = verify_evidence_table(invalid_table_text)
    assert res_invalid["valid"] is False

    # Văn bản không có bảng
    res_no_table = verify_evidence_table("Chỉ có văn bản thuần túy không có bảng nào.")
    assert res_no_table["valid"] is False


def test_verify_execution_claims_without_log():
    """Tuyên bố thành công nhưng thiếu execution log -> REJECT / invalid."""
    text = "Tất cả test đã pass và fix thành công 100%."
    res = verify_execution_claims(text, execution_logs=None)
    assert res["valid"] is False
    assert len(res["unverified_claims"]) >= 1


def test_verify_execution_claims_with_valid_log():
    """Tuyên bố thành công có log exit code 0 đi kèm -> Valid."""
    text = "Tất cả test đã pass và fix thành công."
    log_str = (
        "Running command: pytest tests/\n"
        "16 passed in 1.2s\n"
        "Command exited with code 0"
    )
    res = verify_execution_claims(text, execution_logs=log_str)
    assert res["valid"] is True
    assert len(res["unverified_claims"]) == 0

    # Test với danh sách dict log
    log_list = [{"command": "pytest", "exit_code": 0, "output": "16 passed"}]
    res_list = verify_execution_claims(text, execution_logs=log_list)
    assert res_list["valid"] is True


def test_verify_symbol_grounding_ast():
    """Kiểm tra đối soát Symbol & AST Grounding."""
    code_snippet = """
class DataService:
    def fetch_records(self):
        pass
    def process_data(self):
        pass
"""
    symbols = extract_symbols_from_code(code_snippet)
    assert "DataService" in symbols
    assert "fetch_records" in symbols
    assert "process_data" in symbols

    # Văn bản trích dẫn symbol đúng
    valid_text = "Hàm `fetch_records()` và class `DataService` đã được triển khai."
    check_valid = verify_symbol_grounding(valid_text, known_symbols=symbols)
    assert check_valid["valid"] is True
    assert "fetch_records" in check_valid["verified_symbols"]
    assert "DataService" in check_valid["verified_symbols"]

    # Văn bản trích dẫn symbol ảo
    invalid_text = "Đã gọi hàm `phantom_method_xyz()` để xử lý ngoại lệ."
    check_invalid = verify_symbol_grounding(invalid_text, known_symbols=symbols)
    assert check_invalid["valid"] is False
    assert "phantom_method_xyz" in check_invalid["unverified_symbols"]


def test_audit_response_approve():
    """Kiểm toán trường hợp đạt chuẩn: đường dẫn thật, không võ đoán, có log chứng thực."""
    text = (
        "Đã hoàn thành cấu hình trong `configs/harness_config.json`.\n"
        "Tất cả test đã pass sau khi chạy kiểm thử."
    )
    logs = "pytest tests/ -> 16 passed, exited with code 0"
    audit = audit_response(text, base_dir=REPO_DIR, execution_logs=logs)
    assert audit.verdict == "APPROVE"
    assert audit.is_approved is True
    assert audit.score == 1.0
    assert len(audit.violations) == 0


def test_audit_response_reject():
    """Kiểm toán trường hợp vi phạm đa trụ cột: file ảo, ngôn ngữ võ đoán, thiếu log."""
    text = (
        "Code mới trong `harness/fake_module.py` chắc là sẽ chạy tốt.\n"
        "Tất cả test đã pass mà không gặp vấn đề gì."
    )
    audit = audit_response(text, base_dir=REPO_DIR, execution_logs=None)
    assert audit.verdict == "REJECT"
    assert audit.is_approved is False
    assert audit.score < 1.0
    assert len(audit.violations) >= 3
    assert any("Ảo giác đường dẫn" in v for v in audit.violations)
    assert any("Ngôn ngữ võ đoán" in v for v in audit.violations)
    assert any("Tuyên bố thành công" in v for v in audit.violations)


def test_audit_response_symbol_rejection():
    """Kiểm toán vi phạm symbol ảo dẫn tới REJECT."""
    code = "def real_function(): pass"
    text = "Đã gọi `hallucinated_function_abc()` để cập nhật dữ liệu."
    audit = audit_response(text, base_dir=REPO_DIR, source_code=code)
    assert audit.verdict == "REJECT"
    assert any("Ảo giác ký hiệu" in v for v in audit.violations)


def test_audit_response_with_sycophancy_rejection():
    """Kiểm toán phát hiện câu hùa theo (Sycophancy) dẫn tới REJECT."""
    text = (
        "Giả thuyết của anh hoàn toàn đúng, họ chắc chắn là họ dùng proxy.\n"
        "Tất cả test đã pass."
    )
    logs = "pytest tests/ -> 10 passed, exited with code 0"
    audit = audit_response(text, base_dir=REPO_DIR, execution_logs=logs)
    assert audit.verdict == "REJECT"
    assert audit.is_approved is False
    assert any("Sycophancy" in v for v in audit.violations)
    assert len(audit.sycophancy_phrases) >= 1


def test_audit_response_with_api_claim_rejection():
    """Kiểm toán tuyên bố API thiếu mã raw HTTP dẫn tới REJECT."""
    text = (
        "Gói cước free tier có thể gọi được API ElevenLabs shared voices.\n"
        "Tất cả test đã pass."
    )
    # Log chỉ có exit code 0 nhưng thiếu raw HTTP status code
    logs = "pytest tests/ -> 10 passed, exited with code 0"
    audit = audit_response(text, base_dir=REPO_DIR, execution_logs=logs)
    assert audit.verdict == "REJECT"
    assert audit.is_approved is False
    assert any("raw HTTP" in v for v in audit.violations)
    assert len(audit.unverified_api_claims) >= 1


def test_audit_response_all_valid_with_evidence_table():
    """Kiểm toán hoàn chỉnh với Evidence Table, API log raw HTTP và exit code 0 -> APPROVE."""
    text = """
Đã xác minh cấu hình tại `configs/harness_config.json`.
Tất cả test đã pass.

| Vấn đề nghi vấn | Lệnh thực nghiệm & Raw Response | Kết luận thực chứng |
| :--- | :--- | :--- |
| Tài khoản free tier gọi được API không? | `curl -i ...` -> HTTP 402 Payment Required | Không gọi được, bắt buộc gói trả phí |
"""
    logs = "curl https://... -> HTTP 402 Payment Required\npytest tests/ -> 10 passed, exited with code 0"
    audit = audit_response(
        text,
        base_dir=REPO_DIR,
        execution_logs=logs,
        require_evidence_table=True,
    )
    assert audit.verdict == "APPROVE"
    assert audit.is_approved is True
    assert audit.has_evidence_table is True
    assert audit.score == 1.0
    assert len(audit.violations) == 0


def test_audit_response_separates_verification_and_api_execution_logs() -> None:
    """VULN-02: api_execution_logs satisfies Pillar 6 without spoofing Pillar 3 execution claims."""
    text = (
        "Tài khoản free tier gọi API ElevenLabs báo lỗi paid_plan_required.\n"
        "Tất cả test đã pass 100%!"
    )
    api_only_log = "curl -i https://api.elevenlabs.io/v1/voices -> HTTP 402 Payment Required"
    res_blocked = audit_response(
        text,
        base_dir=REPO_DIR,
        execution_logs=None,
        api_execution_logs=api_only_log,
        check_paths=False,
    )
    assert res_blocked.verdict == "REJECT"
    assert len(res_blocked.unverified_api_claims) == 0
    assert len(res_blocked.unverified_claims) >= 1

    # Unittest output format in execution_logs satisfies Pillar 3
    unittest_log = "Ran 6 tests in 0.04s\n\nOK"
    res_approved = audit_response(
        text,
        base_dir=REPO_DIR,
        execution_logs=unittest_log,
        api_execution_logs=api_only_log,
        check_paths=False,
    )
    assert res_approved.verdict == "APPROVE"


def test_verify_file_paths_anchors_url_unquote_wildcards_and_bare_filenames(tmp_path: Path) -> None:
    """VULN-03: verify_file_paths strips #L.../?..., unquotes %20, skips templates, and ignores bare prose names."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    spaced_file = docs_dir / "my spec.md"
    spaced_file.write_text("# Spec\n", encoding="utf-8")
    root_file = tmp_path / "README.md"
    root_file.write_text("# Root\n", encoding="utf-8")

    spaced_uri = f"file:///{spaced_file.as_posix().replace(' ', '%20')}#L10-L25"
    text_clean = (
        f"Xem [my spec.md]({spaced_uri}) và `README.md?version=2`.\n"
        "Các mẫu `tests/test_*.py`, `plugins/<name>/SKILL.md`, `$HOME/demo.py`, `path/to/sample.py`, "
        "`/api/v1/orders.json` và tên file trần `nonexistent_prose_mention.py` được bỏ qua an toàn."
    )
    res_ok = verify_file_paths(text_clean, base_dir=tmp_path)
    assert res_ok["valid"] is True
    assert res_ok["missing_paths"] == []
    assert "README.md" in res_ok["verified_paths"]
    assert any("my spec.md" in p for p in res_ok["verified_paths"])

    ghost_uri = f"file:///{(tmp_path / 'docs' / 'ghost.md').as_posix()}#L1-L5"
    text_missing = f"Tham chiếu `src/missing_router.py` và [ghost]({ghost_uri})."
    res_bad = verify_file_paths(text_missing, base_dir=tmp_path)
    assert res_bad["valid"] is False
    assert len(res_bad["missing_paths"]) == 2


def test_natural_sycophancy_and_green_run_paraphrase_detection() -> None:
    """VULN-05: Detect natural Vietnamese and English sycophancy and green-run completion claims."""
    vi_text = (
        "Nhận định của Sếp hoàn toàn chính xác, anh bắt đúng bệnh hệ thống! "
        "Em đã kiểm chứng toàn bộ luồng xử lý, mọi kịch bản đều chạy xanh mượt và không phát sinh lỗi nào."
    )
    vi_res = audit_response(vi_text, base_dir=REPO_DIR, execution_logs=None, check_paths=False)
    assert vi_res.verdict == "REJECT"
    assert len(vi_res.sycophancy_phrases) >= 2
    assert len(vi_res.unverified_claims) >= 1

    en_text = "Your diagnosis is spot-on! All test scenarios ran green."
    en_res = audit_response(en_text, base_dir=REPO_DIR, execution_logs=None, check_paths=False)
    assert en_res.verdict == "REJECT"
    assert len(en_res.sycophancy_phrases) >= 1
    assert len(en_res.unverified_claims) >= 1
