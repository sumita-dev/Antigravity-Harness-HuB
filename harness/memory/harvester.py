"""Learning Harvester: rút thông tin thật từ trajectory để tái sử dụng.

Lưu ý: đây là bộ trích xuất dựa trên luật (rule-based), KHÔNG phải học máy.
Nó ghi lại: task nào thành công/thất bại, dùng skill nào, qua bao nhiêu bước,
bao nhiêu vòng phản biện — để lần sau tra cứu nhanh.
"""

import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))

SUCCESS_VERDICTS = {"APPROVE"}
FAILURE_VERDICTS = {"REJECT", "ESCALATE"}

# 5 danh mục bài học / anti-pattern chuẩn hóa
CATEGORIES = {
    "SPEC_GAP",
    "LINT_REGRESSION",
    "TEST_FAILURE",
    "POLICY_VIOLATION",
    "STAGNATION",
}


def strip_vietnamese_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để hỗ trợ tìm kiếm không dấu."""
    nfkd = unicodedata.normalize("NFKD", text)
    without_combining = "".join(c for c in nfkd if not unicodedata.combining(c))
    return without_combining.replace("đ", "d").replace("Đ", "D")


def tokenize_and_normalize(text: str) -> dict:
    """Chuẩn hóa văn bản tiếng Việt & tiếng Anh:
    - Loại bỏ dấu câu
    - Sinh tập từ nguyên bản và không dấu
    - Tạo chuỗi text sạch
    """
    text_lower = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", text_lower)
    unaccented = strip_vietnamese_accents(cleaned)

    raw_words = {w for w in cleaned.split() if len(w) >= 2}
    unaccented_words = {w for w in unaccented.split() if len(w) >= 2}

    return {
        "raw_words": raw_words,
        "unaccented_words": unaccented_words,
        "clean_text": " ".join(cleaned.split()),
        "clean_unaccented": " ".join(unaccented.split()),
    }


class LearningHarvester:
    DEFAULT_PATH = BRAIN_DIR / "learnings" / "patterns.json"
    MAX_PATTERNS = 50

    def __init__(self, path=None, max_patterns: int = None):
        self.path = Path(path) if path else self.DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_patterns = max_patterns or self.MAX_PATTERNS
        self.patterns = self._load_patterns()

    # ----------------------- I/O -----------------------
    def _load_patterns(self) -> list:
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_patterns(self) -> None:
        if len(self.patterns) > self.max_patterns:
            # Giữ các pattern mới nhất theo timestamp (ISO-8601 so sánh chuỗi được)
            self.patterns = sorted(
                self.patterns,
                key=lambda p: p.get("timestamp", ""),
            )[-self.max_patterns:]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.patterns, f, indent=2, ensure_ascii=False)

    # ----------------------- trích xuất & phân loại -----------------------
    @staticmethod
    def _summarize_steps(steps: list) -> str:
        names = [s.get("step", "?") for s in steps]
        return "→".join(names) if names else "không có bước nào"

    @classmethod
    def _classify_failure_category(cls, trajectory: dict) -> str:
        """Phân loại danh mục lỗi: SPEC_GAP, LINT_REGRESSION, TEST_FAILURE, POLICY_VIOLATION, STAGNATION."""
        # 1. Ưu tiên khai báo tường minh từ metadata hoặc trajectory
        metadata = trajectory.get("metadata") or {}
        explicit = trajectory.get("category") or metadata.get("category")
        if explicit and str(explicit).upper() in CATEGORIES:
            return str(explicit).upper()

        # 2. Thu thập toàn bộ ngữ cảnh từ trajectory
        task_desc = str(trajectory.get("task_description", "")).lower()
        failure_reason = str(trajectory.get("failure_reason", "")).lower()
        steps = trajectory.get("steps") or []
        step_texts = []
        for s in steps:
            if isinstance(s, dict):
                data = s.get("data") or {}
                for k in ("report", "error", "reason", "verdict", "action", "description"):
                    if k in data and data[k]:
                        step_texts.append(str(data[k]).lower())

        meta_texts = [str(v).lower() for v in metadata.values() if isinstance(v, (str, int, float))]
        all_text = f"{task_desc} {failure_reason} {' '.join(meta_texts)} {' '.join(step_texts)}"

        # 3. Phân loại theo từ khóa quy chuẩn
        # Vi phạm chính sách / AI Slop
        if any(w in all_text for w in [
            "policy", "chính sách", "vi phạm", "ai slop", "slop", "blacklist",
            "bản quyền", "quy chuẩn cộng đồng", "guideline", "platform standard"
        ]):
            return "POLICY_VIOLATION"

        # Lỗi Lint / formatting / syntax
        if any(w in all_text for w in [
            "lint", "regression", "flake8", "ruff", "eslint", "syntaxerror",
            "formatting", "style violation", "typecheck", "mypy", "hồi quy mã nguồn"
        ]):
            return "LINT_REGRESSION"

        # Lỗi Test
        if any(w in all_text for w in [
            "test", "pytest", "assertion", "test failure", "failed test", "exit code",
            "lỗi kiểm thử", "kiểm thử thất bại", "unit test", "smoke"
        ]):
            return "TEST_FAILURE"

        # Thiếu sót Spec / Acceptance Criteria
        if any(w in all_text for w in [
            "spec", "đặc tả", "scope", "acceptance criteria", "thiếu ac", "sai spec",
            "hợp đồng", "contract", "design review", "yêu cầu chưa đạt"
        ]):
            return "SPEC_GAP"

        # Bế tắc / Vượt ngưỡng Circuit Breaker
        rounds = trajectory.get("critique_rounds", 0)
        if rounds >= 2 or any(w in all_text for w in [
            "circuit breaker", "stagnation", "bế tắc", "lặp lỗi", "quá số vòng", "circuit_breaker"
        ]):
            return "STAGNATION"

        # Fallback theo phân nhánh
        if trajectory.get("branch") == "marketing":
            return "POLICY_VIOLATION"
        return "SPEC_GAP"

    @staticmethod
    def _get_avoidance_advice(category: str, trajectory: dict) -> str:
        metadata = trajectory.get("metadata") or {}
        custom_advice = metadata.get("avoidance_advice")
        if custom_advice:
            return custom_advice

        advices = {
            "SPEC_GAP": (
                "Rà soát kỹ scope và Acceptance Criteria trong bản đặc tả trước khi code; "
                "đảm bảo Maker và Checker đối soát từng tiêu chí nghiệm thu."
            ),
            "LINT_REGRESSION": (
                "Chạy bộ công cụ kiểm tra tĩnh (linter, format, typecheck) ở máy cục bộ trước khi bàn giao; "
                "không để sót lỗi syntax hoặc vi phạm chuẩn quy ước mã nguồn."
            ),
            "TEST_FAILURE": (
                "Chạy trọn vẹn test suite tự động cục bộ và đảm bảo 100% tests PASS với exit_code=0 "
                "kèm log kiểm thử trước khi nộp kết quả cho Checker."
            ),
            "POLICY_VIOLATION": (
                "Kiểm định nghiêm ngặt nội dung trước danh sách đen AI Slop, đối soát nguồn tin cậy "
                "và tuân thủ tuyệt đối chính sách nền tảng đích."
            ),
            "STAGNATION": (
                "Dừng vòng lặp sửa lỗi mù quáng khi chạm circuit breaker. Cần dừng lại, đối thoại "
                "hoặc phỏng vấn làm rõ với người dùng/kiến trúc sư thay vì thử sai liên tục."
            ),
        }
        return advices.get(
            category,
            "Xem lại trajectory: đối soát đặc tả và bằng chứng thực chứng độc lập."
        )

    def harvest(self, trajectory: dict):
        """Rút pattern từ 1 trajectory. Trả về pattern hoặc None."""
        verdict = str(trajectory.get("final_verdict", ""))
        steps = trajectory.get("steps") or []
        rounds = trajectory.get("critique_rounds", 0)
        metadata = trajectory.get("metadata") or {}
        skill = metadata.get("active_skill") or "không dùng skill"
        steps_summary = self._summarize_steps(steps)
        now = datetime.now(timezone.utc).isoformat()
        pattern = None

        if verdict in SUCCESS_VERDICTS:
            category = trajectory.get("category") or metadata.get("category") or "SUCCESS"
            pattern = {
                "id": str(uuid.uuid4()),
                "branch": trajectory.get("branch"),
                "pattern_type": "SUCCESS",
                "category": category,
                "description": trajectory.get("task_description"),
                "trigger": f"skill={skill}",
                "solution_summary": (
                    f"APPROVE sau {len(steps)} bước ({steps_summary}), "
                    f"{rounds} vòng phản biện"
                ),
                "timestamp": now,
            }
        elif verdict in FAILURE_VERDICTS:
            category = self._classify_failure_category(trajectory)
            pattern = {
                "id": str(uuid.uuid4()),
                "branch": trajectory.get("branch"),
                "pattern_type": "ANTI_PATTERN",
                "category": category,
                "description": trajectory.get("task_description"),
                "trigger": f"skill={skill}",
                "failure_reason": (
                    trajectory.get("failure_reason") or
                    f"Kết thúc {verdict} sau {rounds} vòng phản biện ({steps_summary})"
                ),
                "avoidance_advice": self._get_avoidance_advice(category, trajectory),
                "timestamp": now,
            }

        if pattern:
            self.patterns.append(pattern)
            self._save_patterns()
        return pattern

    def retrieve_relevant_patterns(self, task_description: str, branch: str = None) -> list:
        """Tìm pattern liên quan bằng chuẩn hóa từ khóa Việt/Anh, loại bỏ dấu câu và chấm điểm đa chiều."""
        if not task_description:
            return []

        q_info = tokenize_and_normalize(task_description)
        q_words = q_info["raw_words"]
        q_unacc_words = q_info["unaccented_words"]
        q_text = q_info["clean_text"]
        q_unacc = q_info["clean_unaccented"]

        scored = []
        for p in self.patterns:
            if branch and p.get("branch") and p.get("branch") != branch:
                continue

            desc = str(p.get("description", ""))
            category = str(p.get("category", "")).lower()
            trigger = str(p.get("trigger", "")).lower()
            reason = str(p.get("failure_reason", "")).lower()

            full_p_text = f"{desc} {category} {trigger} {reason}"
            p_info = tokenize_and_normalize(full_p_text)
            p_desc_info = tokenize_and_normalize(desc)

            score = 0

            # 1. Trùng khớp từ có dấu
            exact_matches = q_words & p_info["raw_words"]
            score += len(exact_matches) * 3

            # 2. Trùng khớp từ không dấu (cho phép người dùng gõ không dấu hoặc biến thể)
            unacc_matches = q_unacc_words & p_info["unaccented_words"]
            score += len(unacc_matches) * 2

            # 3. Trùng khớp cụm từ trong description
            if p_desc_info["clean_text"] and p_desc_info["clean_text"] in q_text:
                score += 10
            elif q_text and q_text in p_desc_info["clean_text"]:
                score += 8
            elif p_desc_info["clean_unaccented"] and p_desc_info["clean_unaccented"] in q_unacc:
                score += 6
            elif q_unacc and q_unacc in p_desc_info["clean_unaccented"]:
                score += 5

            # 4. Trùng khớp danh mục (category)
            if category and (category in q_text or category in q_unacc):
                score += 4

            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored]

    @classmethod
    def format_patterns_for_prompt(cls, patterns: list) -> str:
        """Định dạng danh sách patterns thành khối Markdown sẵn sàng chèn vào prompt SubAgent."""
        if not patterns:
            return ""

        lines = [
            "### 🧠 BÀI HỌC KINH NGHIỆM TỪ CÁC TÁC VỤ TRƯỚC (LESSONS LEARNED):",
            "Dưới đây là các bài học và cạm bẫy thực chiến đã được đúc kết từ các phiên trước. Hãy tuân thủ để tránh lặp lại sai lầm:",
            ""
        ]

        for i, p in enumerate(patterns, 1):
            p_type = p.get("pattern_type", "PATTERN")
            cat = p.get("category")
            desc = p.get("description", "Không có mô tả")
            tag = f"[{p_type} | {cat}]" if cat else f"[{p_type}]"

            if p_type == "ANTI_PATTERN":
                lines.append(f"{i}. ⚠️ **{tag}** {desc}")
                if p.get("failure_reason"):
                    lines.append(f"   - **Nguyên nhân thất bại:** {p['failure_reason']}")
                if p.get("avoidance_advice"):
                    lines.append(f"   - **Lời khuyên phòng tránh:** {p['avoidance_advice']}")
            else:
                lines.append(f"{i}. ✅ **{tag}** {desc}")
                if p.get("solution_summary"):
                    lines.append(f"   - **Giải pháp thành công:** {p['solution_summary']}")
                if p.get("trigger"):
                    lines.append(f"   - **Điều kiện áp dụng:** {p['trigger']}")
            lines.append("")

        return "\n".join(lines).strip()


def get_intake_lessons(task_description: str, branch: str = None, harvester: LearningHarvester = None) -> str:
    """Tra cứu các bài học liên quan và định dạng sẵn sàng để chèn vào prompt SubAgent."""
    h = harvester or LearningHarvester()
    patterns = h.retrieve_relevant_patterns(task_description, branch=branch)
    if not patterns:
        return ""
    return h.format_patterns_for_prompt(patterns)
