"""Định tuyến task -> skill và nạp nội dung skill.

Đường dẫn được neo vào GỐC REPO (không phụ thuộc CWD) để CLI, test và
pipeline chạy từ bất kỳ thư mục nào cũng tìm đúng file.
"""

import json
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "harness_config.json"
DEFAULT_SKILL_DIRS = (
    REPO_ROOT / "plugins" / "code" / "skills",
    REPO_ROOT / "plugins" / "marketing" / "skills",
    REPO_ROOT / "skills",
)

# Dùng khi không khớp skill cụ thể nào
MARKETING_HINTS = ("marketing", "sale", "content", "story", "ads", "seo",
                   "facebook", "youtube", "quảng cáo", "offer", "kênh",
                   "traffic", "viết bài", "bóc phốt", "caption")


class SkillRouter:
    def __init__(self, config_path: Optional[str] = None):
        self.routing_table = {}
        path = Path(config_path) if config_path else DEFAULT_CONFIG
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self.routing_table = json.load(f).get("skill_routing", {})

    def route(self, task_description: str) -> Tuple[Optional[str], str]:
        text = task_description.lower()

        matches = []
        for skill_name, data in self.routing_table.items():
            branch = data.get("branch", "app")
            for kw in data.get("keywords", []):
                if kw.lower() in text:
                    # Keyword dài hơn = tín hiệu cụ thể hơn -> ưu tiên
                    matches.append((len(kw), skill_name, branch))

        if matches:
            matches.sort(key=lambda x: x[0], reverse=True)
            return matches[0][1], matches[0][2]

        if any(w in text for w in MARKETING_HINTS):
            return None, "marketing"

        return None, "app"


class SkillLoader:
    def __init__(self, skills_dir: str = "skills", search_dirs: Optional[list] = None):
        if search_dirs:
            self.search_dirs = [Path(d) for d in search_dirs]
        else:
            self.search_dirs = [d for d in DEFAULT_SKILL_DIRS if d.is_dir()]
            self.search_dirs.append(Path(skills_dir))

    def find_skill_path(self, skill_name: Optional[str]) -> Optional[str]:
        if not skill_name:
            return None
        for base_dir in self.search_dirs:
            candidate = base_dir / skill_name / "SKILL.md"
            if candidate.is_file():
                return str(candidate)
        return None

    def load_instructions(self, skill_name: Optional[str]) -> Optional[str]:
        path = self.find_skill_path(skill_name)
        if not path:
            return None
        return Path(path).read_text(encoding="utf-8")
