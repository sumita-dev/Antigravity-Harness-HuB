"""Curator Engine: Giám sát tần suất sử dụng, vòng đời kỹ năng và đề xuất hợp nhất.

Vòng đời kỹ năng:
- Active: Sử dụng trong vòng 14 ngày qua
- Stale: Không sử dụng từ 14 - 30 ngày
- Archive: Không sử dụng trên 30 ngày (đề xuất đưa vào archive)
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Union

from harness.skills.manager import SkillManager
from harness.skills.router import SkillLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))


class SkillCurator:
    """Theo dõi số lần dùng, đánh giá vòng đời và phát hiện trùng lặp kỹ năng."""

    def __init__(
        self,
        brain_dir: Optional[Union[str, Path]] = None,
        skill_loader: Optional[SkillLoader] = None,
        skill_manager: Optional[SkillManager] = None,
    ):
        self.brain_dir = Path(brain_dir) if brain_dir else (
            Path(os.environ.get("HARNESS_BRAIN_DIR", REPO_ROOT / ".brain"))
        )
        self.curation_dir = self.brain_dir / "curation"
        self.curation_dir.mkdir(parents=True, exist_ok=True)
        self.usage_file = self.curation_dir / "usage.json"

        self.skill_loader = skill_loader or SkillLoader()
        self.skill_manager = skill_manager or SkillManager(brain_dir=self.brain_dir)

    # ----------------------- USAGE TRACKING -----------------------
    def _load_usage(self) -> dict:
        if not self.usage_file.exists():
            return {"skills": {}}
        try:
            with open(self.usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) and "skills" in data else {"skills": {}}
        except (json.JSONDecodeError, OSError):
            return {"skills": {}}

    def _save_usage(self, data: dict) -> None:
        with open(self.usage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def track_usage(
        self,
        skill_name: str,
        task_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> dict:
        """Ghi nhận một lần sử dụng kỹ năng."""
        if not skill_name:
            return {}

        now_iso = timestamp or datetime.now(timezone.utc).isoformat()
        data = self._load_usage()
        skills = data.setdefault("skills", {})

        if skill_name not in skills:
            skills[skill_name] = {
                "usage_count": 0,
                "first_used": now_iso,
                "last_used": now_iso,
                "tasks": [],
            }

        entry = skills[skill_name]
        entry["usage_count"] += 1
        entry["last_used"] = now_iso
        if task_id and task_id not in entry["tasks"]:
            entry["tasks"].append(task_id)
            if len(entry["tasks"]) > 50:
                entry["tasks"] = entry["tasks"][-50:]

        self._save_usage(data)
        return entry

    def get_skill_stats(self, skill_name: str) -> dict:
        """Lấy thông số sử dụng của một kỹ năng."""
        data = self._load_usage()
        return data.get("skills", {}).get(skill_name, {
            "usage_count": 0,
            "first_used": None,
            "last_used": None,
            "tasks": [],
        })

    # ----------------------- LIFECYCLE EVALUATION -----------------------
    def _get_all_skill_names(self) -> list[str]:
        skill_names = set()
        for s_dir in self.skill_loader.search_dirs:
            if s_dir.is_dir():
                for item in s_dir.iterdir():
                    if item.is_dir() and (item / "SKILL.md").is_file():
                        skill_names.add(item.name)

        # Thêm các skill có trong usage
        usage_data = self._load_usage()
        for name in usage_data.get("skills", {}).keys():
            skill_names.add(name)

        return sorted(list(skill_names))

    def evaluate_lifecycle(
        self,
        active_days_threshold: int = 14,
        archive_days_threshold: int = 30,
        now_dt: Optional[datetime] = None,
    ) -> dict:
        """Đánh giá trạng thái vòng đời của toàn bộ kỹ năng trong hệ thống."""
        now = now_dt or datetime.now(timezone.utc)
        usage_data = self._load_usage().get("skills", {})
        all_skills = self._get_all_skill_names()

        active = []
        stale = []
        archive_candidates = []

        for name in all_skills:
            stat = usage_data.get(name)
            if stat and stat.get("last_used"):
                try:
                    last_dt = datetime.fromisoformat(stat["last_used"])
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    days_idle = (now - last_dt).total_seconds() / 86400.0
                except (ValueError, TypeError):
                    days_idle = 0.0
            else:
                # Kỹ năng chưa từng dùng: kiểm tra thời gian tạo file
                path = self.skill_loader.find_skill_path(name)
                if path and Path(path).exists():
                    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=timezone.utc)
                    days_idle = (now - mtime).total_seconds() / 86400.0
                else:
                    days_idle = 0.0

            item = {
                "name": name,
                "usage_count": stat.get("usage_count", 0) if stat else 0,
                "last_used": stat.get("last_used") if stat else None,
                "days_idle": round(days_idle, 1),
            }

            if days_idle <= active_days_threshold:
                active.append(item)
            elif days_idle <= archive_days_threshold:
                stale.append(item)
            else:
                archive_candidates.append(item)

        return {
            "active": active,
            "stale": stale,
            "archive_candidates": archive_candidates,
            "total_skills": len(all_skills),
            "timestamp": now.isoformat(),
        }

    # ----------------------- CONSOLIDATION -----------------------
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        words = re.findall(r"\b[a-zA-Z0-9_\u00C0-\u1EF9]{3,}\b", text.lower())
        stopwords = {
            "cho", "các", "những", "với", "trong", "được", "này", "của", "khi", "tại",
            "the", "and", "for", "with", "this", "that", "from", "use", "when",
        }
        return {w for w in words if w not in stopwords}

    def find_consolidation_candidates(self, similarity_threshold: float = 0.6) -> list[dict]:
        """Phát hiện các kỹ năng có nội dung hoặc mục đích trùng lặp để đề xuất hợp nhất."""
        all_skills = self._get_all_skill_names()
        skill_texts = {}

        for name in all_skills:
            content = self.skill_loader.load_instructions(name)
            if content:
                skill_texts[name] = content
            else:
                skill_texts[name] = name

        names = list(skill_texts.keys())
        proposals = []

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                name_a = names[i]
                name_b = names[j]

                tokens_a = self._tokenize(skill_texts[name_a])
                tokens_b = self._tokenize(skill_texts[name_b])

                if not tokens_a or not tokens_b:
                    continue

                intersection = tokens_a & tokens_b
                union = tokens_a | tokens_b
                jaccard = len(intersection) / float(len(union)) if union else 0.0

                if jaccard >= similarity_threshold:
                    overlap_keywords = sorted(list(intersection))[:8]
                    proposals.append({
                        "skill_a": name_a,
                        "skill_b": name_b,
                        "similarity": round(jaccard, 3),
                        "common_keywords": overlap_keywords,
                        "reason": f"Độ tương đồng nội dung đạt {round(jaccard * 100, 1)}% với các từ khóa chung: {', '.join(overlap_keywords)}",
                        "recommendation": f"Đề xuất hợp nhất `{name_b}` vào `{name_a}` hoặc chuẩn hóa thành một kỹ năng duy nhất.",
                    })

        proposals.sort(key=lambda x: x["similarity"], reverse=True)
        return proposals

    def auto_archive_stale_skills(
        self,
        dry_run: bool = True,
        manager: Optional[SkillManager] = None,
        archive_days_threshold: int = 30,
        now_dt: Optional[datetime] = None,
    ) -> list[str]:
        """Tự động lưu trữ các kỹ năng không hoạt động quá thời hạn."""
        report = self.evaluate_lifecycle(archive_days_threshold=archive_days_threshold, now_dt=now_dt)
        candidates = [c["name"] for c in report["archive_candidates"]]
        mgr = manager or self.skill_manager

        archived = []
        for name in candidates:
            if not dry_run and mgr:
                mgr.archive_skill(name)
            archived.append(name)
        return archived
