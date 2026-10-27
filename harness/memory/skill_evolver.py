#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness/memory/skill_evolver.py

Recursive Self-Improvement (RSI) Loop Engine (inspired by Hermit GEPA / SkillOpt).
Adheres strictly to L3 Autonomy Mode (Human Gate):
- Ingests execution errors from TrajectoryStore and Obsidian wiki/log.md.
- Maps failure events to the corresponding SKILL.md.
- Generates surgical micro-patches targeting '### Pitfalls & Edge Cases' or '### Procedure'.
- Enforces ContextBudgetGuard (delta lines <= 15, delta tokens <= 120) and YAMLFrontmatterGuard.
- Generates Git Diff / PR markdown proposals for L3 approval.
- CẤM TUYỆT ĐỐI tự tiện ghi đè SKILL.md gốc; chỉ thực thi ghi đè qua apply_proposal() khi có phê duyệt.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
from pathlib import Path
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", REPO_ROOT / ".brain"))


# ==============================================================================
# DATA STRUCTURES & GUARDS
# ==============================================================================

@dataclass
class TriadLesson:
    """Structured lesson schema extracted from failure trajectory."""
    cue: str        # Triggering condition / context
    lesson: str     # Prescriptive rule to prevent failure
    evidence: str   # Concrete proof from logs/exit code/stack trace


@dataclass
class SkillDocument:
    """Represents a SKILL.md document with YAML frontmatter and markdown body."""
    raw_content: str
    frontmatter: Dict[str, Any]
    body: str

    @classmethod
    def from_text(cls, text: str) -> "SkillDocument":
        match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.DOTALL)
        if not match:
            raise ValueError("Invalid SKILL.md format: Missing YAML frontmatter delimiters (---)")
        fm_text = match.group(1)
        body = match.group(2)
        try:
            fm = yaml.safe_load(fm_text)
            if not isinstance(fm, dict):
                raise ValueError("Frontmatter is not a valid YAML dictionary")
        except yaml.YAMLError as exc:
            raise ValueError(f"YAML parsing error: {exc}") from exc
        return cls(raw_content=text, frontmatter=fm, body=body)

    def to_text(self) -> str:
        fm_str = yaml.dump(self.frontmatter, default_flow_style=False, sort_keys=False).strip()
        return f"---\n{fm_str}\n---\n{self.body}"

    @property
    def line_count(self) -> int:
        return len(self.to_text().splitlines())

    @property
    def token_count(self) -> int:
        text = self.to_text()
        return len(re.findall(r"\w+|[^\w\s]", text))


@dataclass
class RSIMutationResult:
    """Result of an RSI mutation attempt."""
    success: bool
    mutated_doc: Optional[SkillDocument]
    error_message: Optional[str] = None
    delta_lines: int = 0
    delta_tokens: int = 0


class YAMLFrontmatterGuard:
    """Guarantees structural validity and non-corruption of SKILL.md YAML frontmatter."""

    @staticmethod
    def verify(text: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        try:
            doc = SkillDocument.from_text(text)
            if "name" not in doc.frontmatter:
                return False, "Missing mandatory 'name' key in frontmatter", None
            if "description" not in doc.frontmatter:
                return False, "Missing mandatory 'description' key in frontmatter", None
            return True, None, doc.frontmatter
        except Exception as exc:
            return False, f"YAML Frontmatter Guard violation: {exc}", None


class ContextBudgetGuard:
    """Enforces Scaffolding & Context Budget Economics (delta lines <= 15, delta tokens <= 120)."""

    MAX_DELTA_LINES: int = 15
    MAX_DELTA_TOKENS: int = 120
    MAX_TOTAL_LINES: int = 250

    @classmethod
    def verify(cls, original_doc: SkillDocument, mutated_doc: SkillDocument) -> Tuple[bool, Optional[str], int, int]:
        delta_lines = mutated_doc.line_count - original_doc.line_count
        delta_tokens = mutated_doc.token_count - original_doc.token_count

        if delta_lines > cls.MAX_DELTA_LINES:
            return False, f"Context budget exceeded: delta_lines={delta_lines} > {cls.MAX_DELTA_LINES}", delta_lines, delta_tokens

        if delta_tokens > cls.MAX_DELTA_TOKENS:
            return False, f"Context budget exceeded: delta_tokens={delta_tokens} > {cls.MAX_DELTA_TOKENS}", delta_lines, delta_tokens

        if mutated_doc.line_count > cls.MAX_TOTAL_LINES:
            return False, f"Total line ceiling exceeded: {mutated_doc.line_count} > {cls.MAX_TOTAL_LINES}", delta_lines, delta_tokens

        return True, None, delta_lines, delta_tokens


# ==============================================================================
# RSI MUTATION ENGINE (HERMIT GEPA)
# ==============================================================================

class SkillOptRSIEngine:
    """
    Recursive Self-Improvement (RSI) Loop Engine.
    Transforms failure events into surgical, budget-bounded mutations of SKILL.md.
    """

    MAX_DELTA_LINES: int = ContextBudgetGuard.MAX_DELTA_LINES
    MAX_DELTA_TOKENS: int = ContextBudgetGuard.MAX_DELTA_TOKENS
    MAX_TOTAL_LINES: int = ContextBudgetGuard.MAX_TOTAL_LINES

    @classmethod
    def formulate_mutation(cls, skill_doc: SkillDocument, failure_lesson: TriadLesson) -> str:
        """Constructs an atomic, surgical rule to append to the Pitfalls & Edge Cases section."""
        rule_block = (
            f"\n### Rào Chắn Tự Trị (RSI Invariant): {failure_lesson.cue}\n"
            f"- **Nguyên tắc**: {failure_lesson.lesson}\n"
            f"- **Chứng cứ thực nghiệm**: `{failure_lesson.evidence}`\n"
        )
        return rule_block

    @classmethod
    def apply_mutation(
        cls,
        current_skill: SkillDocument,
        failure_lesson: TriadLesson,
        adversarial_bloat: bool = False,
    ) -> RSIMutationResult:
        """
        Attempts to apply a mutation patch to current_skill.
        Strictly enforces:
        1. Frontmatter Integrity (valid YAML, required keys preserved).
        2. Context Budget Economics (delta lines <= 15, delta tokens <= 120, total <= 250).
        3. Deduplication (consolidates if cue already present).
        """
        # Check deduplication
        if failure_lesson.cue in current_skill.body:
            return RSIMutationResult(
                success=True,
                mutated_doc=current_skill,
                delta_lines=0,
                delta_tokens=0,
            )

        if adversarial_bloat:
            mutation_snippet = "\n### Bloated Section\n" + ("- Unnecessary repetitive text line\n" * 35)
        else:
            mutation_snippet = cls.formulate_mutation(current_skill, failure_lesson)

        # Kiểm tra chèn vào mục Pitfalls & Edge Cases hoặc Procedure nếu có, nếu không thì append
        body = current_skill.body
        if "### Pitfalls & Edge Cases" in body:
            parts = body.split("### Pitfalls & Edge Cases", 1)
            new_body = parts[0] + "### Pitfalls & Edge Cases" + mutation_snippet + parts[1]
        elif "## Procedure" in body:
            new_body = body + mutation_snippet
        else:
            new_body = body + mutation_snippet

        new_text = f"---\n{yaml.dump(current_skill.frontmatter, default_flow_style=False).strip()}\n---\n{new_body}"

        # 1. Frontmatter Integrity check
        valid_fm, err_fm, _ = YAMLFrontmatterGuard.verify(new_text)
        if not valid_fm:
            return RSIMutationResult(
                success=False,
                mutated_doc=None,
                error_message=f"Frontmatter integrity violation: {err_fm}",
            )

        mutated_doc = SkillDocument.from_text(new_text)

        # 2. Context Budget Economics checks
        valid_budget, err_budget, d_lines, d_tokens = ContextBudgetGuard.verify(current_skill, mutated_doc)
        if not valid_budget:
            return RSIMutationResult(
                success=False,
                mutated_doc=None,
                error_message=err_budget,
                delta_lines=d_lines,
                delta_tokens=d_tokens,
            )

        return RSIMutationResult(
            success=True,
            mutated_doc=mutated_doc,
            delta_lines=d_lines,
            delta_tokens=d_tokens,
        )


# ==============================================================================
# SKILL EVOLVER (L3 HUMAN GATE FOR RSI)
# ==============================================================================

class SkillEvolver:
    """
    Skill Evolver with L3 Human Gate:
    - Scans failures from TrajectoryStore and Obsidian log.md.
    - Generates Git Diff / PR markdown proposals.
    - Enforces ZERO direct mutation without explicit human approval (apply_proposal).
    """

    def __init__(
        self,
        repo_root: Optional[Union[str, Path]] = None,
        brain_dir: Optional[Union[str, Path]] = None,
        obsidian_log_path: Optional[Union[str, Path]] = None,
    ):
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.brain_dir = Path(brain_dir) if brain_dir else (
            Path(os.environ.get("HARNESS_BRAIN_DIR", self.repo_root / ".brain"))
        )
        self.proposals_dir = self.brain_dir / "skill_proposals"
        self.proposals_dir.mkdir(parents=True, exist_ok=True)

        if obsidian_log_path:
            self.obsidian_log_path = Path(obsidian_log_path)
        else:
            vault_base = os.environ.get("OBSIDIAN_VAULT_PATH") or os.environ.get("SECOND_BRAIN_PATH")
            if vault_base:
                self.obsidian_log_path = Path(vault_base) / "wiki" / "log.md"
            else:
                self.obsidian_log_path = Path.home() / "Obsidian" / "wiki" / "log.md"
        self.rsi_engine = SkillOptRSIEngine()

    def find_skill_file(self, skill_name: str) -> Optional[Path]:
        """Tra cứu vị trí vật lý của tệp SKILL.md theo tên kỹ năng."""
        candidate_dirs = [
            self.repo_root / "plugins" / "code" / "skills",
            self.repo_root / "plugins" / "marketing" / "skills",
            self.repo_root / "plugins" / "impeccable" / "skills",
            self.repo_root / "plugins" / "apple-inspired-design" / "skills",
            self.repo_root / "plugins" / "second-brain" / "skills",
            self.repo_root / "plugins" / "computer" / "skills",
            self.repo_root / "skills",
        ]

        # 1. Tìm trực tiếp thư mục trùng tên skill
        for d in candidate_dirs:
            p = d / skill_name / "SKILL.md"
            if p.exists():
                return p

        # 2. Tìm kiếm đệ quy toàn bộ thư mục plugins & skills
        for pattern in (f"**/{skill_name}/SKILL.md", f"**/{skill_name}.md"):
            for found in self.repo_root.glob(pattern):
                if found.is_file():
                    return found

        return None

    def ingest_errors(self) -> List[Dict[str, Any]]:
        """
        Thu thập các lỗi và bài học kinh nghiệm từ:
        1. TrajectoryStore (.brain/trajectories/trajectories.jsonl hoặc .brain/trajectories.jsonl)
        2. Obsidian Vault (wiki/log.md nếu tồn tại)
        """
        extracted_errors: List[Dict[str, Any]] = []

        # 1. Quét từ TrajectoryStore
        traj_paths = [
            self.brain_dir / "trajectories" / "trajectories.jsonl",
            self.brain_dir / "trajectories.jsonl",
        ]
        for p in traj_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            rec = json.loads(line)
                            verdict = rec.get("final_verdict", "")
                            if verdict in ("REJECT", "ESCALATE"):
                                # Bóc tách thông tin lỗi
                                metadata = rec.get("metadata", {})
                                active_skill = metadata.get("active_skill") or rec.get("branch", "app")
                                task_desc = rec.get("task_description", "")
                                steps = rec.get("steps", [])
                                
                                # Tìm lý do reject từ bước CRITIC hoặc CHECKER
                                last_err = ""
                                for step in reversed(steps):
                                    payload = step.get("payload", {})
                                    if "raw" in payload and "REJECT" in payload["raw"]:
                                        last_err = payload["raw"]
                                        break
                                    if "stderr" in payload and payload["stderr"]:
                                        last_err = payload["stderr"]
                                        break

                                extracted_errors.append({
                                    "source": "trajectory",
                                    "task_id": rec.get("task_id", "unknown"),
                                    "skill_name": active_skill,
                                    "cue": f"when executing task '{task_desc[:60]}'",
                                    "lesson": f"BẮT BUỘC rà soát tiêu chí bị REJECT: {last_err[:120]}",
                                    "evidence": last_err or f"Verdict {verdict} at task {rec.get('task_id')}",
                                })
                except Exception as exc:
                    logger.warning("Error reading trajectory file %s: %s", p, exc)

        # 2. Quét từ Obsidian log.md (nếu tồn tại)
        if self.obsidian_log_path.exists():
            try:
                content = self.obsidian_log_path.read_text(encoding="utf-8")
                # Tìm kiếm các block dạng Triad Lesson Schema: cue, lesson, evidence
                pattern = re.compile(
                    r"- \*\*cue\*\*:\s*(.*?)\n- \*\*lesson\*\*:\s*(.*?)\n- \*\*evidence\*\*:\s*(.*?)(?=\n- \*\*|$)",
                    re.IGNORECASE | re.DOTALL,
                )
                for match in pattern.finditer(content):
                    cue, lesson, evidence = match.groups()
                    extracted_errors.append({
                        "source": "obsidian",
                        "skill_name": "app",  # Mặc định định tuyến
                        "cue": cue.strip(),
                        "lesson": lesson.strip(),
                        "evidence": evidence.strip(),
                    })
            except Exception as exc:
                logger.warning("Error reading Obsidian log %s: %s", self.obsidian_log_path, exc)

        return extracted_errors

    def generate_diff_proposal(
        self,
        skill_name: str,
        patch_content: Optional[str] = None,
        lesson: Optional[TriadLesson] = None,
        target_file: Optional[Path] = None,
        cue: str = "",
        lesson_text: str = "",
        evidence_text: str = "",
    ) -> Dict[str, Any]:
        """
        Sinh đề xuất sửa đổi (Diff/PR Markdown) theo Chế độ L3.
        CẤM tự tiện ghi đè file gốc; đề xuất được lưu vào .brain/skill_proposals/ để Sếp duyệt.
        """
        file_path = target_file or self.find_skill_file(skill_name)
        if not file_path or not file_path.exists():
            return {
                "success": False,
                "error": f"Không tìm thấy tệp SKILL.md cho kỹ năng '{skill_name}'",
            }

        orig_text = file_path.read_text(encoding="utf-8")
        try:
            skill_doc = SkillDocument.from_text(orig_text)
        except Exception as exc:
            return {
                "success": False,
                "error": f"Không thể phân tích tệp SKILL.md gốc: {exc}",
            }

        # Xác định đối tượng TriadLesson
        if lesson is None:
            c = cue or f"when executing '{skill_name}' edge case"
            l = lesson_text or (patch_content.strip() if patch_content else "Cần tuân thủ rào chắn an toàn")
            e = evidence_text or "Defect detected in runtime audit"
            lesson = TriadLesson(cue=c, lesson=l, evidence=e)

        # Chạy kiểm tra qua RSI Mutation Engine
        mutation_res = self.rsi_engine.apply_mutation(skill_doc, lesson)
        if not mutation_res.success:
            return {
                "success": False,
                "error": mutation_res.error_message,
                "delta_lines": mutation_res.delta_lines,
                "delta_tokens": mutation_res.delta_tokens,
            }

        mutated_doc = mutation_res.mutated_doc
        new_text = mutated_doc.to_text()

        # Tạo Git Diff chuẩn
        orig_lines = orig_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        rel_path = file_path.relative_to(self.repo_root) if file_path.is_relative_to(self.repo_root) else file_path.name
        diff_lines = list(difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        ))
        diff_text = "".join(diff_lines)

        proposal_id = f"rsi_prop_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Soạn nội dung PR Markdown cho L3
        pr_markdown = (
            f"# Đề Xuất Nâng Cấp Kỹ Năng (RSI L3 Proposal: {proposal_id})\n\n"
            f"> [!IMPORTANT]\n"
            f"> **Chế độ L3 (Human Gate Active)**: Tác tử không tự ý sửa file. Vui lòng bấm Duyệt để áp dụng bản vá.\n\n"
            f"- **Mã Đề Xuất (ID)**: `{proposal_id}`\n"
            f"- **Kỹ Năng (Skill)**: `{skill_name}`\n"
            f"- **Tệp Đích (Path)**: `{file_path}`\n"
            f"- **Chỉ Dấu (Cue)**: {lesson.cue}\n"
            f"- **Bài Học (Lesson)**: {lesson.lesson}\n"
            f"- **Bằng Chứng (Evidence)**: `{lesson.evidence}`\n"
            f"- **Ngân Sách Thay Đổi**: `+{mutation_res.delta_lines} dòng` (Trần <= 15), `+{mutation_res.delta_tokens} tokens` (Trần <= 120)\n\n"
            f"### Git Diff Chi Tiết\n"
            f"```diff\n{diff_text}```\n\n"
            f"Để duyệt đề xuất này từ CLI, thực hiện:\n"
            f"```powershell\npython run_harness.py --apply-proposal {proposal_id}\n```\n"
        )

        proposal_data = {
            "proposal_id": proposal_id,
            "skill_name": skill_name,
            "target_file": str(file_path),
            "cue": lesson.cue,
            "lesson": lesson.lesson,
            "evidence": lesson.evidence,
            "delta_lines": mutation_res.delta_lines,
            "delta_tokens": mutation_res.delta_tokens,
            "diff": diff_text,
            "pr_markdown": pr_markdown,
            "new_content": new_text,
            "status": "PENDING",
            "created_at": created_at,
        }

        # Lưu proposal vào file JSON
        prop_file = self.proposals_dir / f"{proposal_id}.json"
        prop_file.write_text(json.dumps(proposal_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "success": True,
            "proposal_id": proposal_id,
            "proposal_data": proposal_data,
            "diff": diff_text,
            "pr_markdown": pr_markdown,
        }

    def apply_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """
        Áp dụng đề xuất nâng cấp kỹ năng sau khi được Sếp phê duyệt (Cổng L3).
        CHỈ hàm này mới được quyền ghi đè tệp SKILL.md gốc!
        """
        prop_file = self.proposals_dir / f"{proposal_id}.json"
        if not prop_file.exists():
            raise FileNotFoundError(f"Không tìm thấy đề xuất '{proposal_id}' trong {self.proposals_dir}")

        proposal = json.loads(prop_file.read_text(encoding="utf-8"))
        if proposal.get("status") == "APPLIED":
            return {
                "success": True,
                "message": f"Đề xuất '{proposal_id}' đã được áp dụng trước đó.",
                "proposal": proposal,
            }

        target_file = Path(proposal["target_file"])
        new_content = proposal["new_content"]

        # Kiểm tra tính toàn vẹn lần cuối trước khi ghi
        valid_fm, err_fm, _ = YAMLFrontmatterGuard.verify(new_content)
        if not valid_fm:
            raise ValueError(f"Không thể áp dụng: {err_fm}")

        # Ghi đè vào tệp đích
        target_file.write_text(new_content, encoding="utf-8")

        # Cập nhật trạng thái đề xuất
        proposal["status"] = "APPLIED"
        proposal["applied_at"] = datetime.now(timezone.utc).isoformat()
        prop_file.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "success": True,
            "message": f"Đã áp dụng thành công đề xuất '{proposal_id}' cho kỹ năng '{proposal['skill_name']}'!",
            "proposal": proposal,
        }

    def reject_proposal(self, proposal_id: str, reason: str = "") -> Dict[str, Any]:
        """Từ chối một đề xuất nâng cấp kỹ năng."""
        prop_file = self.proposals_dir / f"{proposal_id}.json"
        if not prop_file.exists():
            raise FileNotFoundError(f"Không tìm thấy đề xuất '{proposal_id}'")

        proposal = json.loads(prop_file.read_text(encoding="utf-8"))
        proposal["status"] = "REJECTED"
        proposal["rejection_reason"] = reason
        proposal["rejected_at"] = datetime.now(timezone.utc).isoformat()
        prop_file.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "success": True,
            "message": f"Đã từ chối đề xuất '{proposal_id}'.",
            "proposal": proposal,
        }

    def list_proposals(self, status: Optional[str] = "PENDING") -> List[Dict[str, Any]]:
        """Liệt kê các đề xuất nâng cấp kỹ năng."""
        proposals = []
        if not self.proposals_dir.exists():
            return []

        for p in self.proposals_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if status is None or data.get("status") == status:
                    proposals.append(data)
            except Exception:
                continue
        return proposals

    def scan_and_propose(self) -> List[Dict[str, Any]]:
        """
        Quét các lỗi chưa xử lý và tự động sinh đề xuất nâng cấp kỹ năng L3.
        Hoàn toàn an toàn: không ghi đè bất kỳ tệp SKILL.md nào.
        """
        errors = self.ingest_errors()
        generated_proposals = []

        for err in errors:
            skill_name = err.get("skill_name", "app")
            cue = err.get("cue", "")
            lesson_txt = err.get("lesson", "")
            evidence_txt = err.get("evidence", "")

            # Kiểm tra xem đã có proposal pending tương tự chưa
            existing = [
                p for p in self.list_proposals("PENDING")
                if p.get("skill_name") == skill_name and p.get("cue") == cue
            ]
            if existing:
                continue

            res = self.generate_diff_proposal(
                skill_name=skill_name,
                cue=cue,
                lesson_text=lesson_txt,
                evidence_text=evidence_txt,
            )
            if res.get("success"):
                generated_proposals.append(res)

        return generated_proposals
