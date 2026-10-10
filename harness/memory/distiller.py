"""Skill Distiller: Chưng cất bài học từ Trajectory thành SKILL.md có cấu trúc chuẩn.

Tuân thủ triết lý "Lessons, not logs":
- When to Use
- Procedure
- Pitfalls & Mechanisms
- Verification
"""

import os
import re
import unicodedata
from pathlib import Path
from typing import Optional, Union
import yaml

from harness.memory.harvester import LearningHarvester
from harness.memory.trajectory import TrajectoryStore
from harness.skills.manager import SkillManager

BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))


class SkillDistiller:
    """Tác tử chưng cất bài học kinh nghiệm và quy trình từ quỹ đạo thực thi."""

    def __init__(
        self,
        trajectory_store: Optional[TrajectoryStore] = None,
        harvester: Optional[LearningHarvester] = None,
        skill_manager: Optional[SkillManager] = None,
    ):
        self.trajectory_store = trajectory_store or TrajectoryStore()
        self.harvester = harvester or LearningHarvester()
        self.skill_manager = skill_manager or SkillManager()

    @staticmethod
    def _slugify(text: str) -> str:
        """Chuyển đổi văn bản thành slug hợp lệ (chữ cái ASCII không dấu, số, dấu gạch ngang)."""
        # Chuẩn hóa unicode và loại bỏ dấu tiếng Việt
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        slug = text.strip("-")
        return slug[:40] if slug else "distilled-skill"

    def _extract_when_to_use(self, trajectory: dict) -> str:
        desc = trajectory.get("task_description", "Thực hiện nhiệm vụ kỹ thuật hoặc nội dung.")
        branch = trajectory.get("branch", "app")
        metadata = trajectory.get("metadata") or {}
        active_skill = metadata.get("active_skill")

        lines = [
            f"Kích hoạt khi cần xử lý các tác vụ tương tự: **{desc}**.",
            f"- **Phân nhánh áp dụng:** `{branch}`.",
        ]
        if active_skill and active_skill != "không dùng skill":
            lines.append(f"- **Kỹ năng gốc liên quan:** `{active_skill}`.")
        lines.append("- Áp dụng khi cần quy trình chuẩn hóa có cơ chế phản biện độc lập và kiểm chứng thực tế.")
        return "\n".join(lines)

    def _extract_procedure(self, trajectory: dict) -> str:
        steps = trajectory.get("steps") or []
        branch = trajectory.get("branch", "app")
        metadata = trajectory.get("metadata") or {}

        if not steps:
            meta_steps = metadata.get("steps") or metadata.get("procedure")
            if isinstance(meta_steps, list) and meta_steps:
                steps = [{"step": s} if isinstance(s, str) else s for s in meta_steps]

        if not steps:
            if branch == "marketing":
                return (
                    "1. **Trinh sát & Nghiên cứu:** Thu thập dữ liệu thực địa, chỉ số và insight.\n"
                    "2. **Xác nhận Ý định:** Trình duyệt góc tiếp cận và khung sườn chính.\n"
                    "3. **Sản xuất Nội dung:** Triển khai bản thảo theo cấu trúc (Hook, Body, CTA).\n"
                    "4. **Kiểm định Chính sách:** Đối soát với tiêu chuẩn nền tảng và quét AI Slop."
                )
            return (
                "1. **Phân tích Yêu cầu:** Xác định phạm vi và ràng buộc kỹ thuật.\n"
                "2. **Thiết kế Kiến trúc:** Lập đặc tả schema và hợp đồng giao tiếp.\n"
                "3. **Triển khai Mã nguồn:** Viết mã tối thiểu, tuân thủ nguyên tắc TDD.\n"
                "4. **Thẩm định Chất lượng:** Chạy bộ kiểm thử tự động và review độc lập."
            )

        lines = []
        for i, s in enumerate(steps, 1):
            step_name = s.get("step", f"Bước {i}")
            data = s.get("data") or {}
            detail = ""
            if "description" in data:
                detail = f": {data['description']}"
            elif "action" in data:
                detail = f": {data['action']}"
            elif "skill" in data:
                detail = f": Nạp kỹ năng `{data['skill']}`"
            elif "verdict" in data:
                detail = f": Kết quả thẩm định `{data['verdict']}`"
            elif "stage" in data:
                detail = f": Chuyển sang giai đoạn `{data['stage']}`"

            actor = data.get("actor")
            if actor:
                detail += f" (Actor: {actor})"
            lines.append(f"{i}. **{step_name}**{detail}")
        return "\n".join(lines)

    def _extract_pitfalls(self, trajectory: dict) -> str:
        rounds = trajectory.get("critique_rounds", 0)
        verdict = trajectory.get("final_verdict", "APPROVE")
        branch = trajectory.get("branch", "app")
        metadata = trajectory.get("metadata") or {}
        failure_reason = trajectory.get("failure_reason") or metadata.get("failure_reason")
        category = trajectory.get("category") or metadata.get("category")

        pitfalls = [
            "- **Bẫy tự phê duyệt (Self-approval Pitfall):** Maker tuyệt đối không tự duyệt sản phẩm của mình; luôn bàn giao cho Checker độc lập.",
            "- **Thiếu bằng chứng thực chứng:** Mọi tuyên bố thành công phải kèm log kiểm thử hoặc tài liệu đối soát cụ thể.",
        ]

        if failure_reason:
            pitfalls.append(f"- **Nguyên nhân thất bại thực tế ghi nhận:** {failure_reason}")

        if category == "TEST_FAILURE":
            pitfalls.append("- **Lỗi kiểm thử (Test Failure):** Các ca kiểm thử tự động không đạt; phải kiểm tra test pass tại máy cục bộ trước khi bàn giao.")
        elif category == "LINT_REGRESSION":
            pitfalls.append("- **Hồi quy mã nguồn / Lint (Lint Regression):** Mã nguồn vi phạm coding standards, types hoặc linter rules.")
        elif category == "SPEC_GAP":
            pitfalls.append("- **Thiếu sót đặc tả (Spec Gap):** Mã nguồn không bao phủ toàn bộ acceptance criteria hoặc làm sai so với kiến trúc đã ký duyệt.")
        elif category == "POLICY_VIOLATION":
            pitfalls.append("- **Vi phạm chính sách (Policy Violation):** Nội dung vi phạm tiêu chuẩn cộng đồng, chính sách nền tảng hoặc lạm dụng AI Slop.")
        elif category == "STAGNATION":
            pitfalls.append("- **Bế tắc & Circuit Breaker (Stagnation):** Tác vụ lặp đi lặp lại lỗi quá ngưỡng cho phép mà không đạt tiến triển.")

        # Check steps for rejection info
        steps = trajectory.get("steps") or []
        rejections = []
        for s in steps:
            data = s.get("data") or {}
            if data.get("verdict") == "REJECT" or s.get("step") == "REJECT":
                reason = data.get("report") or data.get("reason")
                if reason:
                    rejections.append(f"Vòng '{s.get('step')}': {reason}")
        if rejections:
            pitfalls.append("- **Lỗi phát hiện trong các bước thẩm định:** " + "; ".join(rejections[:2]))

        if rounds > 0:
            pitfalls.append(
                f"- **Lặp lỗi qua các vòng phản biện:** Tác vụ này từng trải qua {rounds} vòng phản biện trước khi hoàn tất. "
                "Cần kiểm tra kỹ các tiêu chí nghiệm thu ngay từ bước đầu để tránh kích hoạt Circuit Breaker."
            )

        if verdict in ("REJECT", "ESCALATE") and not failure_reason:
            pitfalls.append(
                "- **Rủi ro bế tắc (Stagnation Risk):** Khi phát hiện thiếu dữ liệu hoặc mâu thuẫn yêu cầu, dừng lại phỏng vấn ngay thay vì tự suy đoán."
            )

        if branch == "marketing":
            pitfalls.append("- **AI Slop & Vi phạm Chính sách:** Tránh lạm dụng từ ngữ sáo rỗng và luôn kiểm tra quy định nền tảng (Meta/YouTube).")
        else:
            pitfalls.append("- **Mã phình & Trừu tượng hóa dư thừa:** Giữ giải pháp tối giản, bám sát spec, không code trước các tính năng giả định.")

        return "\n".join(pitfalls)

    def _extract_verification(self, trajectory: dict) -> str:
        branch = trajectory.get("branch", "app")
        metadata = trajectory.get("metadata") or {}
        items = []

        # Trích xuất lệnh kiểm thử thực tế từ metadata
        v_cmds = metadata.get("verification_commands") or metadata.get("commands")
        if isinstance(v_cmds, list):
            for cmd in v_cmds:
                if isinstance(cmd, dict):
                    cmd_str = cmd.get("command", cmd.get("id", "command"))
                    items.append(f"- [ ] Chạy lệnh thẩm định: `{cmd_str}` (phải có exit_code = 0).")
                elif isinstance(cmd, str):
                    items.append(f"- [ ] Chạy lệnh thẩm định: `{cmd}` (phải có exit_code = 0).")

        # Trích xuất các tiêu chí bắt buộc (marketing required checks)
        req_checks = metadata.get("required_checks")
        if isinstance(req_checks, list):
            for chk in req_checks:
                items.append(f"- [ ] Tiêu chí bắt buộc `{chk}` phải đạt trạng thái PASS kèm bằng chứng.")

        # Trích xuất Acceptance Criteria
        acs = metadata.get("acceptance_criteria")
        if isinstance(acs, list):
            for ac in acs:
                if isinstance(ac, dict):
                    items.append(f"- [ ] Nghiệm thu tiêu chí `{ac.get('id', 'AC')}`: {ac.get('description', '')}.")

        # Bằng chứng thực chứng
        evidence = metadata.get("evidence")
        if isinstance(evidence, list) and evidence:
            items.append(f"- [ ] Xác minh tính toàn vẹn của {len(evidence)} tệp bằng chứng thực chứng (evidence SHA-256).")

        if branch == "marketing":
            items.extend([
                "- [ ] Kiểm tra tính chính xác của số liệu thực địa đối chiếu với Research Dossier.",
                "- [ ] Quét sạch từ ngữ trong danh sách đen AI Slop.",
                "- [ ] Đảm bảo 100% tuân thủ chính sách nền tảng mục tiêu.",
                "- [ ] Checker độc lập đưa ra phán quyết `VERDICT: APPROVE`.",
            ])
        else:
            items.extend([
                "- [ ] Chạy toàn bộ test suite liên quan và đảm bảo tất cả test cases đều PASS.",
                "- [ ] Kiểm tra không có hồi quy mã nguồn (`pytest -q` hoặc test runner tương ứng).",
                "- [ ] Đối chiếu mã nguồn thực tế với đặc tả kiến trúc ban đầu.",
                "- [ ] QA Auditor độc lập đưa ra phán quyết `VERDICT: APPROVE`.",
            ])

        seen = set()
        deduped = []
        for line in items:
            if line not in seen:
                seen.add(line)
                deduped.append(line)
        return "\n".join(deduped)

    def distill_from_trajectory(
        self,
        trajectory: dict,
        skill_name: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> dict:
        """Chuyển đổi một bản ghi trajectory thành tài liệu SKILL.md hoàn chỉnh."""
        task_desc = trajectory.get("task_description", "distilled-skill")
        task_branch = branch or trajectory.get("branch", "app")
        name = skill_name or self._slugify(task_desc)

        # Chuẩn bị metadata frontmatter
        metadata = {
            "name": name,
            "description": f"Chưng cất từ kinh nghiệm thực thi: {task_desc}",
            "branch": task_branch,
            "source_task_id": trajectory.get("task_id", "unknown"),
            "critique_rounds": trajectory.get("critique_rounds", 0),
        }

        frontmatter_yaml = yaml.dump(
            {"name": name, "description": metadata["description"]},
            sort_keys=False,
            allow_unicode=True,
        ).strip()

        when_to_use = self._extract_when_to_use(trajectory)
        procedure = self._extract_procedure(trajectory)
        pitfalls = self._extract_pitfalls(trajectory)
        verification = self._extract_verification(trajectory)

        title = name.replace("-", " ").replace("_", " ").title()

        content = (
            f"---\n{frontmatter_yaml}\n---\n\n"
            f"# {title}\n\n"
            f"## Overview\n\n"
            f"Quy trình kỹ năng được chưng cất tự động từ thực tế thực thi tác vụ `{task_desc}`.\n\n"
            f"## When to Use\n\n"
            f"{when_to_use}\n\n"
            f"## Procedure\n\n"
            f"{procedure}\n\n"
            f"## Pitfalls & Mechanisms\n\n"
            f"{pitfalls}\n\n"
            f"## Verification\n\n"
            f"{verification}\n"
        )

        lint_res = SkillManager.lint_skill(content)
        if not lint_res["valid"]:
            raise ValueError(f"Nội dung chưng cất không đạt chuẩn lint: {', '.join(lint_res['errors'])}")

        return {
            "name": name,
            "branch": task_branch,
            "content": content,
            "metadata": metadata,
        }

    def distill_task(self, task_id: str, stage_immediately: bool = True) -> Optional[dict]:
        """Tìm trajectory theo task_id, chưng cất và đưa vào staging nếu yêu cầu."""
        trajectories = self.trajectory_store.get_trajectories()
        target = None
        for t in trajectories:
            if t.get("task_id") == task_id:
                target = t
                break

        if not target:
            return None

        distilled = self.distill_from_trajectory(target)

        if stage_immediately and self.skill_manager:
            stage_rec = self.skill_manager.stage_skill(
                name=distilled["name"],
                diff_or_content=distilled["content"],
                metadata=distilled["metadata"],
                branch=distilled["branch"],
            )
            distilled["stage_record"] = stage_rec

        return distilled

    def auto_distill(self, trajectory: dict) -> Optional[dict]:
        """Tự động chưng cất sau khi tác vụ hoàn thành thành công (APPROVED)."""
        verdict = trajectory.get("final_verdict")
        if verdict != "APPROVE":
            return None

        distilled = self.distill_from_trajectory(trajectory)
        if self.skill_manager:
            stage_rec = self.skill_manager.stage_skill(
                name=distilled["name"],
                diff_or_content=distilled["content"],
                metadata=distilled["metadata"],
                branch=distilled["branch"],
            )
            distilled["stage_record"] = stage_rec
        return distilled
