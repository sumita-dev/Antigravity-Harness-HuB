"""Unit tests cho Opik Quantitative Evaluation & Heuristic Metrics Module."""

from pathlib import Path
import pytest

from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.state_machine import HarnessState, TaskContext
from harness.validators.hallucination_detector import audit_response
from harness.validators.opik_evaluator import (
    ContainsMetric,
    DegenerationMetric,
    EqualsMetric,
    HallucinationScoreMetric,
    IsJsonMetric,
    LevenshteinRatioMetric,
    OpikEvaluator,
    OpikMetricsAdapter,
    RegexMatchMetric,
    RubricGEvalMetric,
    ScoreResult,
    TrajectoryAccuracyMetric,
    compute_levenshtein_distance,
    compute_levenshtein_ratio,
    is_opik_available,
)

REPO_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# 1. TEST ADAPTER & STANDALONE FALLBACK MODE
# ==============================================================================

def test_opik_standalone_mode():
    """Kiểm tra adapter hoạt động chính xác ở chế độ standalone fallback."""
    adapter = OpikMetricsAdapter()
    assert adapter.mode in ("native", "standalone")

    # Kiểm tra factory methods của adapter trả về metric instances hoạt động tốt
    lev = adapter.get_levenshtein_metric(case_sensitive=False)
    res_lev = lev.score("Hello World", "hello world")
    assert res_lev.value == 1.0

    eq = adapter.get_equals_metric(case_sensitive=True)
    res_eq = eq.score("abc", "abc")
    assert res_eq.value == 1.0

    contains = adapter.get_contains_metric()
    res_contains = contains.score("Antigravity Harness Hub", "Harness")
    assert res_contains.value == 1.0

    regex = adapter.get_regex_match_metric()
    res_regex = regex.score("Task #1234 completed", r"#\d+")
    assert res_regex.value == 1.0

    json_m = adapter.get_is_json_metric()
    res_json = json_m.score('{"status": "ok"}', required_keys=["status"])
    assert res_json.value == 1.0


# ==============================================================================
# 2. TEST HEURISTIC METRICS (Levenshtein, Contains, Regex, Equals, IsJson)
# ==============================================================================

def test_levenshtein_distance_and_ratio():
    """Kiểm tra thuật toán tính khoảng cách và tỉ lệ Levenshtein."""
    assert compute_levenshtein_distance("kitten", "sitting") == 3
    assert compute_levenshtein_distance("", "") == 0
    assert compute_levenshtein_distance("a", "") == 1

    # Ratio
    assert compute_levenshtein_ratio("same", "same") == 1.0
    assert compute_levenshtein_ratio("abc", "xyz") == 0.0
    assert compute_levenshtein_ratio("Test", "test", case_sensitive=False) == 1.0
    assert compute_levenshtein_ratio("Test", "test", case_sensitive=True) < 1.0

    metric = LevenshteinRatioMetric(case_sensitive=True)
    res = metric.score("OpenAI", "Opik")
    assert 0.0 < res.value < 1.0
    assert res.name == "levenshtein_ratio"

    # Edge cases
    assert metric.score(None, "abc").value == 0.0  # type: ignore


def test_contains_metric():
    """Kiểm tra metric Contains."""
    metric = ContainsMetric(case_sensitive=False)
    assert metric.score("Alpha Beta Gamma", "beta").value == 1.0
    assert metric.score("Alpha Beta Gamma", "delta").value == 0.0

    metric_cs = ContainsMetric(case_sensitive=True)
    assert metric_cs.score("Alpha Beta Gamma", "beta").value == 0.0
    assert metric_cs.score("Alpha Beta Gamma", "Beta").value == 1.0

    # Non-string input
    assert metric.score(123, "test").value == 0.0  # type: ignore


def test_regex_match_metric():
    """Kiểm tra metric RegexMatch."""
    metric = RegexMatchMetric()
    assert metric.score("Exit code: 0", r"Exit code:\s*0").value == 1.0
    assert metric.score("Exit code: 1", r"Exit code:\s*0").value == 0.0

    # Invalid regex
    res_err = metric.score("abc", r"[unclosed")
    assert res_err.value == 0.0
    assert "không hợp lệ" in (res_err.reason or "")


def test_equals_metric():
    """Kiểm tra metric Equals."""
    metric = EqualsMetric(case_sensitive=False)
    assert metric.score("PASS", "pass").value == 1.0
    assert metric.score("PASS", "FAIL").value == 0.0


def test_is_json_metric():
    """Kiểm tra metric IsJson với các định dạng khác nhau."""
    metric = IsJsonMetric()

    # Raw json
    res1 = metric.score('{"name": "Opik", "version": 1}')
    assert res1.value == 1.0
    assert res1.is_passing is True

    # Markdown codeblock json
    codeblock_text = """Here is the result:
```json
{
  "task_id": "T123",
  "status": "APPROVED",
  "score": 0.95
}
```
"""
    res2 = metric.score(codeblock_text, required_keys=["task_id", "status", "score"])
    assert res2.value == 1.0

    # Missing required keys
    res3 = metric.score('{"task_id": "T123"}', required_keys=["task_id", "status", "score"])
    assert res3.value < 1.0
    assert "status" in res3.metadata["missing_keys"]

    # Invalid json
    res4 = metric.score("Not a json string at all")
    assert res4.value == 0.0


# ==============================================================================
# 3. TEST DEGENERATION DETECTOR
# ==============================================================================

def test_degeneration_metric_clean_text():
    """Văn bản tự nhiên phong phú phải đạt điểm cao (1.0)."""
    text = (
        "Báo cáo nghiệm thu hoàn tất hệ thống Antigravity Harness Hub. "
        "Tất cả các module đã được kiểm thử với kết quả xuất sắc. "
        "Không phát hiện lỗi rò rỉ bộ nhớ hoặc xung đột tài nguyên."
    )
    metric = DegenerationMetric()
    res = metric.score(text)
    assert res.value >= 0.8
    assert res.is_passing is True


def test_degeneration_metric_repeated_phrases():
    """Văn bản bị lặp n-gram và dòng liên tiếp phải bị phạt điểm."""
    degenerate_text = (
        "Lặp lại cụm từ này lặp lại cụm từ này lặp lại cụm từ này lặp lại cụm từ này.\n"
        "Và đây là dòng lặp.\n"
        "Và đây là dòng lặp.\n"
        "Và đây là dòng lặp.\n"
        "Và đây là dòng lặp.\n"
    )
    metric = DegenerationMetric()
    res = metric.score(degenerate_text)
    assert res.value < 0.7
    assert res.metadata["consecutive_dup_lines"] >= 3
    assert res.metadata["max_repetition_rate"] > 0.3


def test_degeneration_single_word_stutter():
    """Lặp 1 từ liên tục trong văn bản ngắn."""
    metric = DegenerationMetric()
    res = metric.score("error error error error")
    assert res.value == 0.0


# ==============================================================================
# 4. TEST TRAJECTORY ACCURACY METRIC
# ==============================================================================

def test_trajectory_accuracy_perfect():
    """Thực thi đầy đủ theo đúng thứ tự kế hoạch -> 1.0."""
    planned = ["INIT", "INTAKE", "DESIGN", "IMPLEMENTATION", "AUDIT", "APPROVED"]
    executed = [
        {"name": "INIT", "status": "DONE", "exit_code": 0},
        {"name": "INTAKE", "status": "DONE", "exit_code": 0},
        {"name": "DESIGN", "status": "DONE", "exit_code": 0},
        {"name": "IMPLEMENTATION", "status": "DONE", "exit_code": 0},
        {"name": "AUDIT", "status": "DONE", "exit_code": 0},
        {"name": "APPROVED", "status": "DONE", "exit_code": 0},
    ]

    metric = TrajectoryAccuracyMetric()
    res = metric.score(planned, executed)
    assert res.value == 1.0
    assert res.metadata["coverage_score"] == 1.0
    assert res.metadata["order_score"] == 1.0
    assert res.metadata["failures"] == 0


def test_trajectory_accuracy_scrambled_order():
    """Thực thi lộn xộn thứ tự kế hoạch -> bị giảm điểm order."""
    planned = ["STEP_1", "STEP_2", "STEP_3", "STEP_4"]
    executed = ["STEP_4", "STEP_3", "STEP_2", "STEP_1"]

    metric = TrajectoryAccuracyMetric()
    res = metric.score(planned, executed)
    # Coverage = 1.0, nhưng Order = 1/4 = 0.25 -> Điểm trung bình ~ 0.62
    assert res.value < 0.8
    assert res.metadata["order_score"] < 0.5


def test_trajectory_accuracy_with_failures():
    """Thực thi có bước bị lỗi -> bị trừ penalty."""
    planned = ["BUILD", "TEST", "DEPLOY"]
    executed = [
        {"name": "BUILD", "exit_code": 0},
        {"name": "TEST", "exit_code": 1, "status": "FAILED"},
        {"name": "DEPLOY", "exit_code": 0},
    ]

    metric = TrajectoryAccuracyMetric()
    res = metric.score(planned, executed)
    assert res.metadata["failures"] == 1
    assert res.value < 1.0


# ==============================================================================
# 5. TEST RUBRIC G-EVAL SCORER
# ==============================================================================

def test_rubric_geval_scorer_full_pass():
    """Thẩm định Rubric với đầy đủ các tiêu chuẩn đạt điểm tối đa."""
    content = """# Chiến lược nội dung Bóc Phốt Tài Chính
## Hook
Cảnh báo mô hình Ponzi lừa đảo 200 tỷ đồng của đường dây tiền ảo.
## Body
Phân tích dòng tiền, chiêu trò cam kết lợi nhuận 30%/tháng và bằng chứng ủy nhiệm chi giả mạo.
## Conclusion & CTA
Hãy cẩn trọng trước các lời mời gọi làm giàu nhanh. Đăng ký kênh để cập nhật cảnh báo mới nhất.
"""
    criteria = [
        {
            "name": "structure",
            "weight": 0.4,
            "required_sections": ["## Hook", "## Body", "## Conclusion & CTA"],
        },
        {
            "name": "keywords",
            "weight": 0.3,
            "keywords": ["ponzi", "tiền ảo", "lừa đảo"],
        },
        {
            "name": "no_speculation",
            "weight": 0.3,
            "forbidden": ["chắc là", "dường như", "probably"],
        },
    ]

    metric = RubricGEvalMetric()
    res = metric.score(content, criteria)
    assert res.value >= 0.9
    assert res.is_passing is True
    assert "structure" in res.metadata["criteria_scores"]


def test_rubric_geval_scorer_violations():
    """Thẩm định Rubric vi phạm từ cấm và thiếu section."""
    content = "Bài viết ngắn sơ sài chắc là sẽ hoạt động."
    criteria = [
        {
            "name": "structure",
            "weight": 0.5,
            "required_sections": ["## Hook", "## Evidence"],
        },
        {
            "name": "clean_language",
            "weight": 0.5,
            "forbidden": ["chắc là"],
        },
    ]

    metric = RubricGEvalMetric()
    res = metric.score(content, criteria)
    assert res.value < 0.6
    assert res.is_passing is False


def test_rubric_geval_scorer_none_or_empty_text():
    """Kiểm tra RubricGEvalMetric an toàn tuyệt đối với text rỗng hoặc None."""
    metric = RubricGEvalMetric()
    res_none = metric.score(None, [{"name": "sec", "required_sections": ["## Hook"]}])
    assert res_none.value < 0.5
    res_empty_crit = metric.score(None, [])
    assert res_empty_crit.value == 1.0


# ==============================================================================
# 6. TEST HALLUCINATION SCORE METRIC & AUDIT RESULT CONVERSION
# ==============================================================================

def test_hallucination_score_clean():
    """Kiểm tra báo cáo sạch không có ảo giác đạt điểm 1.0."""
    text = "Đã cấu hình file `configs/harness_config.json` theo đúng đặc tả."
    metric = HallucinationScoreMetric()
    res = metric.score(text, base_dir=REPO_DIR)
    assert res.value == 1.0
    assert res.metadata["verdict"] == "APPROVE"


def test_hallucination_score_with_violations():
    """Kiểm tra báo cáo chứa ảo giác đường dẫn và từ ngữ võ đoán."""
    text = (
        "File `phantom_fake_non_existent.py` probably contains the solution. "
        "Tất cả test đã pass."
    )
    metric = HallucinationScoreMetric()
    res = metric.score(text, base_dir=REPO_DIR, execution_logs=None)
    assert res.value < 0.8
    assert res.metadata["verdict"] == "REJECT"
    assert len(res.metadata["violations"]) >= 2


def test_audit_result_to_score_result():
    """Kiểm tra phương thức AuditResult.to_score_result() chuyển đổi tương thích Opik."""
    text = "Bản báo cáo chuẩn không ảo giác."
    audit_res = audit_response(text, base_dir=REPO_DIR)
    score_res = audit_res.to_score_result()

    assert isinstance(score_res, ScoreResult)
    assert score_res.name == "hallucination_score"
    assert score_res.value == 1.0
    assert score_res.is_passing is True


# ==============================================================================
# 7. TEST OPIK EVALUATOR FACADE
# ==============================================================================

def test_opik_evaluator_composite():
    """Kiểm tra tính toán điểm tổng hợp có trọng số trong OpikEvaluator."""
    evaluator = OpikEvaluator()

    scores = {
        "m1": ScoreResult(name="m1", value=1.0),
        "m2": ScoreResult(name="m2", value=0.5),
    }
    # Trọng số đều -> 0.75
    comp = evaluator.compute_composite_score(scores)
    assert comp == 0.75

    # Trọng số m1 gấp 3 lần m2 -> (3*1.0 + 1*0.5)/4 = 3.5/4 = 0.88
    comp_weighted = evaluator.compute_composite_score(scores, weights={"m1": 3.0, "m2": 1.0})
    assert comp_weighted == 0.88


# ==============================================================================
# 8. TEST QUALITY GATE INTEGRATION (App & Marketing Quality Gates)
# ==============================================================================

def test_quality_gate_evaluate_quantitative():
    """Kiểm tra evaluate_quantitative trên AdversarialQualityGate."""
    gate = AdversarialQualityGate()

    text = "Hệ thống `README.md` đã được đối soát kỹ lưỡng."
    quant_res = gate.evaluate_quantitative(
        response_text=text,
        reference_text=text,
        planned_steps=["INIT", "AUDIT"],
        executed_steps=["INIT", "AUDIT"],
    )

    assert "composite_score" in quant_res
    assert quant_res["composite_score"] >= 0.8
    assert quant_res["is_passing"] is True
    assert "hallucination" in quant_res["metrics"]
    assert "degeneration" in quant_res["metrics"]
    assert "levenshtein" in quant_res["metrics"]
    assert "trajectory" in quant_res["metrics"]


def test_quality_gate_app_quality_gate_pass():
    """Kiểm tra App Quality Gate phê duyệt khi đáp ứng đủ tiêu chuẩn."""
    gate = AdversarialQualityGate()
    context = TaskContext(task_id="APP-001", branch="app")
    context.state = HarnessState.AUDIT
    context.steps = ["STEP_1", "STEP_2"]

    text = "Cập nhật hoàn tất trong `README.md`."
    log_evidence = "exit code: 0\n2 passed in 0.5s"

    verdict, details = gate.evaluate_app_quality_gate(
        task_context=context,
        response_text=text,
        execution_logs=log_evidence,
        planned_steps=["STEP_1", "STEP_2"],
        threshold=0.8,
    )

    assert verdict == Verdict.APPROVE
    assert details["is_passing"] is True
    assert context.state == HarnessState.APPROVED


def test_quality_gate_app_quality_gate_reject_and_escalate():
    """Kiểm tra App Quality Gate REJECT khi vi phạm và ESCALATE khi hết quota."""
    gate = AdversarialQualityGate(max_qa_rounds=2)
    context = TaskContext(task_id="APP-002", branch="app")
    context.state = HarnessState.AUDIT
    context.steps = ["STEP_1"]

    # Văn bản ảo giác nặng
    bad_text = "File `phantom_ghost_file.py` probably works. Tất cả test đã pass."

    # Lần 1: REJECT -> chuyển về IMPLEMENTATION
    verdict1, details1 = gate.evaluate_app_quality_gate(
        task_context=context,
        response_text=bad_text,
        execution_logs=None,
    )
    assert verdict1 == Verdict.REJECT
    assert details1["is_passing"] is False
    assert context.state == HarnessState.IMPLEMENTATION

    # Lần 2: Giả sử sau khi sửa xong trong IMPLEMENTATION, quay lại AUDIT
    context.state = HarnessState.AUDIT
    # Vượt quá max_qa_rounds (2) -> ESCALATE
    verdict2, details2 = gate.evaluate_app_quality_gate(
        task_context=context,
        response_text=bad_text,
        execution_logs=None,
    )
    assert verdict2 == Verdict.ESCALATE
    assert context.state == HarnessState.ESCALATED


def test_quality_gate_marketing_quality_gate():
    """Kiểm tra Marketing Quality Gate thẩm định nội dung theo Rubric."""
    gate = AdversarialQualityGate()
    context = TaskContext(task_id="MKT-001", branch="marketing")
    context.state = HarnessState.AUDIT

    good_content = """# Quảng cáo chuyển đổi cao
## Hook
Giải pháp tối ưu chuyển đổi chiến dịch Meta Ads cho doanh nghiệp vừa và nhỏ.
## Offer
Miễn phí 14 ngày trải nghiệm và hỗ trợ thiết lập 1-1.
"""
    criteria = [
        {
            "name": "structure",
            "required_sections": ["## Hook", "## Offer"],
        }
    ]

    verdict, details = gate.evaluate_marketing_quality_gate(
        task_context=context,
        content_text=good_content,
        rubric_criteria=criteria,
        threshold=0.8,
    )

    assert verdict == Verdict.APPROVE
    assert details["is_passing"] is True
    assert context.state == HarnessState.APPROVED
