import json
import os
from typing import Optional, Tuple

class SkillRouter:
    def __init__(self, config_path: str = "configs/harness_config.json"):
        self.routing_table = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.routing_table = config.get("skill_routing", {})

    def route(self, task_description: str) -> Tuple[Optional[str], str]:
        text = task_description.lower()
        
        matches = []
        for skill_name, data in self.routing_table.items():
            branch = data.get("branch", "app")
            keywords = data.get("keywords", [])
            for kw in keywords:
                if kw.lower() in text:
                    matches.append((len(kw), skill_name, branch))
                    
        if matches:
            matches.sort(key=lambda x: x[0], reverse=True)
            return matches[0][1], matches[0][2]
                    
        # Intelligent fallback
        marketing_keywords = ["marketing", "sale", "content", "story", "ads", "seo", "facebook", "youtube", "quảng cáo", "offer", "kênh", "traffic", "viết bài"]
        if any(w in text for w in marketing_keywords):
            return None, "marketing"
            
        return None, "app"

class SkillLoader:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir

    def load_instructions(self, skill_name: str) -> Optional[str]:
        if not skill_name:
            return None
        skill_path = os.path.join(self.skills_dir, skill_name, "SKILL.md")
        if os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
