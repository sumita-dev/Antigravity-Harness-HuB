"""Adversarial Tests: Rubber Stamp Approval Vulnerability in App Workflow Critique Gate.

Kiểm thử lỗ hổng phê duyệt hình thức (Rubber Stamping) tại `harness.app_workflow`:
1. Lỗ hổng Regex trong `review_code`:
   - `has_ac = bool(re.search(r"\\b(?:ac\\d*|acceptance\\s+criteria)\\b", report, re.IGNORECASE))`
   - `has_assertion = bool(re.search(r"\\b(?:test_\\w*|assertion\\w*)\\b", report, re.IGNORECASE))`
   - Báo cáo rỗng tuếch hoặc hoàn toàn không có nội dung kỹ thuật chỉ cần chứa 2 từ khóa:
     `ac1` và `test_dummy` từng có thể qua mặt kiểm duyệt regex đơn thuần.
2. Vá lỗ hổng bằng AST Verification trên `AppWorkflowStore.review_code`:
   - Báo cáo "ac1 test_dummy" tham chiếu hàm test không tồn tại trên đĩa bị REJECT bởi AST check.
   - Báo cáo tham chiếu hàm test rỗng (chỉ chứa `pass`) bị REJECT bởi AST check.
   - Báo cáo tham chiếu hàm test có assertion thực sự được APPROVE và chuyển workflow sang stage AUDIT.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

from harness.app_workflow import AppWorkflowStore, WorkflowError


class TestRubberStampRegexVulnerability:
    """Kiểm thử trực tiếp biểu thức chính quy (Regex) của cổng phê duyệt Critique."""

    AC_PATTERN = re.compile(r"\b(?:ac\d*|acceptance\s+criteria)\b", re.IGNORECASE)
    ASSERTION_PATTERN = re.compile(r"\b(?:test_\w*|assertion\w*)\b", re.IGNORECASE)

    def test_hollow_report_passes_regex_gate(self):
        """Báo cáo chỉ chứa từ khóa `ac1` và `test_dummy` nhưng không có nội dung kỹ thuật vẫn pass regex."""
        hollow_report = "ac1 test_dummy"

        has_ac = bool(self.AC_PATTERN.search(hollow_report))
        has_assertion = bool(self.ASSERTION_PATTERN.search(hollow_report))

        # Cả hai điều kiện đều thỏa mãn mặc dù báo cáo hoàn toàn không có giá trị kỹ thuật
        assert has_ac is True, "ac1 phải kích hoạt has_ac"
        assert has_assertion is True, "test_dummy phải kích hoạt has_assertion"
        assert (has_ac and has_assertion) is True

    def test_variations_of_minimal_keyword_stuffing(self):
        """Các chuỗi vô nghĩa hoặc tối giản khác chứa token khóa đều qua mặt regex."""
        payloads = [
            "ac1 test_dummy",
            "AC test_0",
            "acceptance criteria test_anything",
            "ac99 assertion_done",
        ]
        for p in payloads:
            has_ac = bool(self.AC_PATTERN.search(p))
            has_assertion = bool(self.ASSERTION_PATTERN.search(p))
            assert has_ac and has_assertion, f"Payload '{p}' thất bại ngoài ý muốn"

    def test_substantive_technical_review_rejected_due_to_missing_exact_tokens(self):
        """Điểm mù đối nghịch: Báo cáo kỹ thuật chi tiết nhưng không có từ khóa máy móc bị từ chối."""
        detailed_report = (
            "Đã kiểm tra toàn bộ mã nguồn, cấu trúc dữ liệu và xử lý ngoại lệ. "
            "Các tiêu chí nghiệm thu đều được thỏa mãn và logic chạy an toàn."
        )
        has_ac = bool(self.AC_PATTERN.search(detailed_report))
        has_assertion = bool(self.ASSERTION_PATTERN.search(detailed_report))

        # Phân tích sâu nhưng thiếu từ khóa 'ac' và 'test_' -> bị chặn
        assert not (has_ac and has_assertion), (
            "Báo cáo thiếu token máy móc phải bị regex đánh giá là thiếu mapping"
        )


class TestRubberStampGateInWorkflow:
    """Kiểm thử tích hợp trên AppWorkflowStore để chứng minh lỗ hổng end-to-end."""

    def _setup_workflow(self, tmp_path: Path, extra_files: dict[str, str] | None = None) -> tuple[AppWorkflowStore, dict]:
        """Thiết lập task và đưa workflow đến trạng thái CRITIQUE sẵn sàng review."""
        project = tmp_path / "app"
        project.mkdir()
        (project / "index.html").write_text("<html><body>app</body></html>", encoding="utf-8")
        if extra_files:
            for fname, fcontent in extra_files.items():
                (project / fname).write_text(fcontent, encoding="utf-8")

        store = AppWorkflowStore(tmp_path / "brain")
        store.create("task-rubber-stamp", "Kiểm thử lỗ hổng rubber stamp", project)

        spec_data = {
            "scope": "test app",
            "design": "minimal design",
            "contracts": "none",
            "acceptance_criteria": [{"id": "AC1", "description": "basic check", "ui": False}],
            "risks": "none",
            "verification_commands": [
                {"id": "TEST", "argv": ["python", "-c", "print('ok')"], "cwd": ".", "ac_ids": ["AC1"]}
            ],
        }

        s = store.submit_spec("task-rubber-stamp", spec_data, "architect-1")
        store.review_design(
            "task-rubber-stamp", "APPROVE", "reviewer-1", s["spec_sha256"], "Spec validated"
        )
        store.sign_off("task-rubber-stamp", s["spec_sha256"], "Sếp: Duyệt bản đặc tả này")
        state = store.submit_implementation(
            "task-rubber-stamp", "builder-1", "Triển khai hoàn tất mã nguồn"
        )
        return store, state

    def test_workflow_rejects_hollow_code_review_referencing_non_existent_test(self, tmp_path: Path):
        """Xác nhận review_code từ chối báo cáo 'ac1 test_dummy' vì hàm test_dummy không tồn tại trên đĩa."""
        store, state = self._setup_workflow(tmp_path)

        hollow_report = "ac1 test_dummy"

        # Báo cáo tham chiếu hàm không tồn tại bị AST check chặn đứng
        with pytest.raises(WorkflowError, match="Critique report references non-existent or empty test function: test_dummy"):
            store.review_code(
                "task-rubber-stamp",
                "APPROVE",
                "critic-1",
                state["spec_sha256"],
                state["manifest_sha256"],
                hollow_report,
            )

    def test_workflow_rejects_critique_referencing_empty_test_function(self, tmp_path: Path):
        """Xác nhận review_code từ chối báo cáo nếu hàm test tồn tại trên đĩa nhưng chỉ chứa pass hoặc không có assertion."""
        store, state = self._setup_workflow(
            tmp_path, extra_files={"test_app.py": "def test_dummy():\n    pass\n"}
        )

        with pytest.raises(WorkflowError, match="Critique report references non-existent or empty test function: test_dummy"):
            store.review_code(
                "task-rubber-stamp",
                "APPROVE",
                "critic-1",
                state["spec_sha256"],
                state["manifest_sha256"],
                "ac1 test_dummy",
            )

    def test_workflow_accepts_valid_critique_with_ast_verified_test(self, tmp_path: Path):
        """Xác nhận review_code chấp thuận báo cáo khi hàm test tồn tại trên đĩa và có chứa assertion thực sự."""
        store, state = self._setup_workflow(
            tmp_path, extra_files={"test_app.py": "def test_dummy():\n    assert 1 == 1\n"}
        )

        reviewed_state = store.review_code(
            "task-rubber-stamp",
            "APPROVE",
            "critic-1",
            state["spec_sha256"],
            state["manifest_sha256"],
            "ac1 test_dummy",
        )

        assert reviewed_state["stage"] == "AUDIT"
        assert reviewed_state["actors"]["code_critic"] == "critic-1"
        assert reviewed_state["code_review"]["verdict"] == "APPROVE"

    def test_workflow_rejects_report_without_ac_or_assertion(self, tmp_path: Path):
        """Đối chứng: Báo cáo không chứa ac hoặc test_ sẽ bị quăng WorkflowError."""
        store, state = self._setup_workflow(tmp_path)

        unmapped_report = "Mã nguồn rất sạch sẽ và đã kiểm tra toàn bộ logic."

        with pytest.raises(WorkflowError, match="Critique report must contain AC-to-Assertion mapping"):
            store.review_code(
                "task-rubber-stamp",
                "APPROVE",
                "critic-1",
                state["spec_sha256"],
                state["manifest_sha256"],
                unmapped_report,
            )
