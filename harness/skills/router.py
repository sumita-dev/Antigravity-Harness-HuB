"""Định tuyến task -> skill và nạp nội dung skill.

Đường dẫn được neo vào GỐC REPO (không phụ thuộc CWD) để CLI, test và
pipeline chạy từ bất kỳ thư mục nào cũng tìm đúng file.
"""

import json
import re
import yaml
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "harness_config.json"
DEFAULT_SKILL_DIRS = (
    REPO_ROOT / "plugins" / "code" / "skills",
    REPO_ROOT / "plugins" / "marketing" / "skills",
    REPO_ROOT / "plugins" / "impeccable" / "skills",
    REPO_ROOT / "plugins" / "apple-inspired-design" / "skills",
    REPO_ROOT / "plugins" / "second-brain" / "skills",
    REPO_ROOT / "plugins" / "computer" / "skills",
    REPO_ROOT / "skills",
)

# Dùng khi không khớp skill cụ thể nào
MARKETING_HINTS = ("marketing", "sale", "content", "story", "ads", "seo",
                   "facebook", "youtube", "quảng cáo", "offer", "kênh",
                   "traffic", "viết bài", "bóc phốt", "caption")


class SkillRouter:
    def __init__(self, config_path: Optional[str] = None):
        self.routing_table = {}
        self.composition = {}
        self.aliases = {}
        path = Path(config_path) if config_path else DEFAULT_CONFIG
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.routing_table = config.get("skill_routing", {})
                self.composition = config.get("skill_composition", {})
                self.aliases = config.get("aliases", {}) or config.get("skill_aliases", {})
                for skill_name, data in self.routing_table.items():
                    if isinstance(data, dict) and "alias" in data:
                        self.aliases[skill_name] = data["alias"]

    def resolve_alias(self, skill_name: Optional[str]) -> Optional[str]:
        if not skill_name:
            return None
        visited = set()
        current = skill_name
        while current in self.aliases and current not in visited:
            visited.add(current)
            current = self.aliases[current]
        return current

    def route(self, task_description: str) -> Tuple[Optional[str], str]:
        text = task_description.lower()

        candidates = []
        for skill_name, data in self.routing_table.items():
            branch = data.get("branch", "app")
            matched_kws = [kw for kw in data.get("keywords", []) if kw.lower() in text]
            if matched_kws:
                max_len = max(len(kw) for kw in matched_kws)
                count = len(matched_kws)
                # Score = (độ dài từ khóa dài nhất * 10) + tổng số từ khóa của skill đó xuất hiện trong prompt
                score = (max_len * 10) + count
                candidates.append((score, count, max_len, skill_name, branch))

        if candidates:
            # Sắp xếp theo score giảm dần; nếu bằng nhau ưu tiên count, max_len
            candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
            winner_skill = candidates[0][3]
            winner_branch = candidates[0][4]
            final_skill = self.resolve_alias(winner_skill)
            final_branch = self.routing_table.get(final_skill, {}).get("branch", winner_branch)
            return final_skill, final_branch

        if any(w in text for w in MARKETING_HINTS):
            return None, "marketing"

        return None, "app"


    def compose(self, stage, role, stack, risk, task_description="", *,
                max_skills=None, max_chars=None, loader=None):
        """Compose existing skills; fail explicitly rather than truncate policy."""
        selected = []
        for dimension, value in (("stage", stage), ("role", role), ("stack", stack), ("risk", risk)):
            for name in self.composition.get(dimension, {}).get(value, []):
                if name not in selected:
                    selected.append(name)
        keyword, _ = self.route(task_description)
        if keyword and keyword not in selected:
            selected.append(keyword)
        skill_limit = self.composition.get("max_skills", 6) if max_skills is None else max_skills
        char_limit = self.composition.get("max_chars", 48000) if max_chars is None else max_chars
        if not isinstance(skill_limit, int) or not isinstance(char_limit, int) or skill_limit < 0 or char_limit < 0:
            raise ValueError("Invalid composition budget")
        loader = loader or SkillLoader()
        closure = []
        def expand(name, active):
            if name in active:
                raise ValueError(f"Skill dependency cycle: {name}")
            if name in closure:
                return
            if not loader.find_skill_path(name):
                raise ValueError(f"Missing skill dependency: {name}")
            for dependency in loader.get_skill_dependencies(name):
                expand(dependency, active | {name})
            closure.append(name)
        for name in selected:
            expand(name, set())
        if len(closure) > skill_limit:
            raise ValueError("Skill composition exceeds skill budget")
        instructions = "\n\n".join(loader.load_instructions(name, include_dependencies=False) for name in closure)
        if len(instructions) > char_limit:
            raise ValueError("Skill composition exceeds context budget")
        return {"skills": closure, "instructions": instructions, "chars": len(instructions)}


class SkillLoader:
    def __init__(self, skills_dir: str = "skills", search_dirs: Optional[list] = None, aliases: Optional[dict] = None):
        if search_dirs:
            self.search_dirs = [Path(d) for d in search_dirs]
        else:
            self.search_dirs = [d for d in DEFAULT_SKILL_DIRS if d.is_dir()]
            self.search_dirs.append(Path(skills_dir))
        self.aliases = aliases or {}
        if not self.aliases and DEFAULT_CONFIG.exists():
            try:
                with open(DEFAULT_CONFIG, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.aliases = cfg.get("aliases", {}) or cfg.get("skill_aliases", {})
                    for s_name, data in cfg.get("skill_routing", {}).items():
                        if isinstance(data, dict) and "alias" in data:
                            self.aliases[s_name] = data["alias"]
            except Exception:
                pass

    def resolve_alias(self, skill_name: Optional[str]) -> Optional[str]:
        if not skill_name:
            return None
        visited = set()
        current = skill_name
        while current in self.aliases and current not in visited:
            visited.add(current)
            current = self.aliases[current]
        return current

    def find_skill_path(self, skill_name: Optional[str]) -> Optional[str]:
        if not skill_name:
            return None
        for base_dir in self.search_dirs:
            candidate = base_dir / skill_name / "SKILL.md"
            if candidate.is_file():
                return str(candidate)
        target = self.resolve_alias(skill_name)
        if target and target != skill_name:
            for base_dir in self.search_dirs:
                candidate = base_dir / target / "SKILL.md"
                if candidate.is_file():
                    return str(candidate)
        return None

    def get_skill_dependencies(self, skill_name: str) -> list[str]:
        path = self.find_skill_path(skill_name)
        if not path:
            return []
        
        content = Path(path).read_text(encoding="utf-8")
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return []
            
        # Legacy frontmatter contains prose that is not valid YAML. Only the
        # declared dependency field belongs to this parser's contract.
        lines = match.group(1).splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r"^dependencies\s*:", line)]
        if not starts:
            return []
        if len(starts) != 1:
            raise ValueError(f"Invalid dependencies: {skill_name} (duplicate field)")
        start = starts[0]
        end = next((i for i in range(start + 1, len(lines))
                    if re.match(r"^[A-Za-z_][\w-]*\s*:", lines[i])), len(lines))
        try:
            metadata = yaml.safe_load("\n".join(lines[start:end]))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid dependencies: {skill_name}") from exc
        deps = metadata.get("dependencies", [])
        if not isinstance(deps, list) or any(not isinstance(d, str) or not d for d in deps):
            raise ValueError(f"Invalid dependencies: {skill_name}")
        return deps

    def load_instructions(self, skill_name: Optional[str], include_dependencies: bool = True, _visited: Optional[set] = None) -> Optional[str]:
        if not skill_name:
            return None
            
        if _visited is None:
            _visited = set()
            
        if skill_name in _visited:
            return ""
            
        _visited.add(skill_name)
        
        path = self.find_skill_path(skill_name)
        if not path:
            return None
            
        content = Path(path).read_text(encoding="utf-8")
        
        if not include_dependencies:
            return content
            
        deps = self.get_skill_dependencies(skill_name)
        if not deps:
            return content
            
        result = []
        for dep in deps:
            dep_content = self.load_instructions(dep, include_dependencies=True, _visited=_visited)
            if dep_content is None:
                raise ValueError(f"Missing skill dependency: {dep}")
            if dep_content:
                result.append(f"<!-- DEPENDENCY: {dep} -->\n{dep_content}")
                
        result.append(f"<!-- ROOT SKILL: {skill_name} -->\n{content}")
        return "\n\n".join(result)
