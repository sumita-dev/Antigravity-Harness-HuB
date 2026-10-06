"""Skill Lifecycle Engine: Quản lý vòng đời kỹ năng theo chuẩn agentskills.io.

Hỗ trợ:
- create_skill: tạo mới tệp SKILL.md theo chuẩn agentskills.io
- patch_skill: vá nội dung chính xác (targeted patching)
- lint_skill: kiểm tra tính hợp lệ của frontmatter và cấu trúc tài liệu
- stage_skill / approve_staged_skill / reject_staged_skill: cơ chế staging & duyệt
- archive_skill: lưu trữ kỹ năng không còn sử dụng vào .archive/
"""

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
import json
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BRAIN_DIR = Path(os.environ.get("HARNESS_BRAIN_DIR", ".brain"))


class SkillManager:
    """Quản lý tạo mới, vá, kiểm định và lưu trữ kỹ năng."""

    MAX_FILE_SIZE_BYTES = 500 * 1024  # 500 KB

    def __init__(
        self,
        repo_root: Optional[Union[str, Path]] = None,
        brain_dir: Optional[Union[str, Path]] = None,
        staging_dir: Optional[Union[str, Path]] = None,
        archive_dir: Optional[Union[str, Path]] = None,
    ):
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.brain_dir = Path(brain_dir) if brain_dir else (
            Path(os.environ.get("HARNESS_BRAIN_DIR", self.repo_root / ".brain"))
        )
        self.staging_dir = Path(staging_dir) if staging_dir else (self.brain_dir / "skills_staging")
        self.archive_dir = Path(archive_dir) if archive_dir else (self.brain_dir / "skills_archive")

        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.staged_file = self.staging_dir / "staged_skills.json"

    # ----------------------- LINTING -----------------------
    @classmethod
    def lint_skill(cls, content: str) -> dict:
        """Kiểm tra tính hợp lệ của tệp SKILL.md theo chuẩn agentskills.io."""
        errors = []
        metadata = {}

        if not content or not content.strip():
            return {"valid": False, "errors": ["Tệp kỹ năng rỗng"], "metadata": {}}

        if len(content.encode("utf-8")) > cls.MAX_FILE_SIZE_BYTES:
            errors.append(f"Kích thước tệp vượt quá giới hạn cho phép ({cls.MAX_FILE_SIZE_BYTES} bytes)")

        # Kiểm tra frontmatter YAML
        frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
        match = frontmatter_pattern.match(content.strip())

        if not match:
            errors.append("Thiếu hoặc sai định dạng YAML frontmatter (phải bao bởi '---')")
            return {"valid": False, "errors": errors, "metadata": metadata}

        raw_frontmatter, body = match.groups()

        try:
            parsed_yaml = yaml.safe_load(raw_frontmatter)
            if not isinstance(parsed_yaml, dict):
                errors.append("Frontmatter YAML phải là một dictionary/object hợp lệ")
                parsed_yaml = {}
            else:
                metadata = parsed_yaml
        except Exception as e:
            errors.append(f"Lỗi cú pháp YAML frontmatter: {str(e)}")
            parsed_yaml = {}

        # Kiểm tra trường name
        name = metadata.get("name")
        if not name or not str(name).strip():
            errors.append("Thiếu trường 'name' trong frontmatter")
        else:
            name_str = str(name).strip()
            if not re.match(r"^[a-zA-Z0-9_\-]+$", name_str):
                errors.append(f"Trường 'name' ('{name_str}') chứa ký tự không hợp lệ (chỉ cho phép chữ cái, số, '-' và '_')")

        # Kiểm tra trường description
        description = metadata.get("description")
        if not description or not str(description).strip():
            errors.append("Thiếu trường 'description' trong frontmatter")

        # Kiểm tra phần thân (body)
        if not body or not body.strip():
            errors.append("Phần thân tài liệu (body markdown) không được để trống")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "metadata": metadata,
        }

    # ----------------------- CREATE & RESOLVE -----------------------
    def _resolve_skill_dir(self, name: str, branch: str = "app") -> Path:
        """Xác định thư mục lưu trữ kỹ năng theo phân nhánh."""
        branch_clean = (branch or "app").lower()
        if branch_clean in ("app", "code"):
            base = self.repo_root / "plugins" / "code" / "skills"
        elif branch_clean == "marketing":
            base = self.repo_root / "plugins" / "marketing" / "skills"
        else:
            plugin_branch_dir = self.repo_root / "plugins" / branch_clean / "skills"
            if plugin_branch_dir.parent.exists():
                base = plugin_branch_dir
            else:
                base = self.repo_root / "skills"
        return base / name

    def find_skill_path(self, name: str) -> Optional[Path]:
        """Tìm đường dẫn tệp SKILL.md theo tên kỹ năng."""
        search_dirs = [
            self.repo_root / "plugins" / "code" / "skills",
            self.repo_root / "plugins" / "marketing" / "skills",
            self.repo_root / "skills",
        ]
        plugins_dir = self.repo_root / "plugins"
        if plugins_dir.exists():
            for p in plugins_dir.iterdir():
                if p.is_dir() and (p / "skills").is_dir() and (p / "skills") not in search_dirs:
                    search_dirs.append(p / "skills")

        for s_dir in search_dirs:
            candidate = s_dir / name / "SKILL.md"
            if candidate.is_file():
                return candidate
        return None

    def create_skill(
        self,
        name: str,
        branch: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Tạo tệp SKILL.md mới theo chuẩn agentskills.io."""
        # Chỉ tự động chèn frontmatter nếu có metadata truyền vào và content chưa có frontmatter
        if metadata is not None and not content.strip().startswith("---"):
            meta = metadata or {}
            meta_name = meta.get("name", name)
            meta_desc = meta.get("description", f"Skill for {name}")
            frontmatter_dict = {"name": meta_name, "description": meta_desc}
            for k, v in meta.items():
                if k not in frontmatter_dict:
                    frontmatter_dict[k] = v
            yaml_str = yaml.dump(frontmatter_dict, sort_keys=False, allow_unicode=True).strip()
            content = f"---\n{yaml_str}\n---\n\n{content.strip()}\n"

        lint_res = self.lint_skill(content)
        if not lint_res["valid"]:
            raise ValueError(f"Nội dung kỹ năng không hợp lệ: {', '.join(lint_res['errors'])}")

        skill_dir = self._resolve_skill_dir(name, branch)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(content)

        return skill_file

    # ----------------------- PATCHING -----------------------
    def patch_skill(
        self,
        name: str,
        old_string: str,
        new_string: str,
        branch: Optional[str] = None,
    ) -> Path:
        """Vá chính xác một đoạn nội dung trong tệp SKILL.md."""
        skill_path = self.find_skill_path(name)
        if not skill_path or not skill_path.exists():
            if branch:
                skill_path = self._resolve_skill_dir(name, branch) / "SKILL.md"
            if not skill_path or not skill_path.exists():
                raise FileNotFoundError(f"Không tìm thấy kỹ năng '{name}' để vá")

        current_content = skill_path.read_text(encoding="utf-8")

        if old_string not in current_content:
            raise ValueError(f"Đoạn mã cần thay thế không tồn tại trong {skill_path.name}")

        count = current_content.count(old_string)
        if count > 1:
            raise ValueError(
                f"Đoạn mã cần thay thế xuất hiện {count} lần trong {skill_path.name}. "
                "Cần chỉ định đoạn văn bản duy nhất (unique substring) để vá chính xác."
            )

        updated_content = current_content.replace(old_string, new_string, 1)

        lint_res = self.lint_skill(updated_content)
        if not lint_res["valid"]:
            raise ValueError(f"Bản vá tạo ra nội dung không hợp lệ: {', '.join(lint_res['errors'])}")

        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        return skill_path

    # ----------------------- STAGING -----------------------
    def _load_staged_records(self) -> list[dict]:
        if not self.staged_file.exists():
            return []
        try:
            with open(self.staged_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_staged_records(self, records: list[dict]) -> None:
        with open(self.staged_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def stage_skill(
        self,
        name: str,
        diff_or_content: str,
        metadata: Optional[dict] = None,
        branch: str = "app",
    ) -> dict:
        """Đưa kỹ năng mới hoặc bản vá vào hàng đợi Staging chờ phê duyệt."""
        stage_id = f"stage-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "id": stage_id,
            "name": name,
            "branch": branch,
            "content": diff_or_content,
            "metadata": metadata or {},
            "status": "PENDING",
            "created_at": now,
        }

        records = self._load_staged_records()
        records.append(record)
        self._save_staged_records(records)
        return record

    def get_staged_skills(self, status: Optional[str] = "PENDING") -> list[dict]:
        """Lấy danh sách các kỹ năng trong hàng đợi Staging."""
        records = self._load_staged_records()
        if status is None:
            return records
        return [r for r in records if r.get("status") == status]

    def approve_staged_skill(self, stage_id: str) -> dict:
        """Phê duyệt kỹ năng trong staging và ghi vào codebase."""
        records = self._load_staged_records()
        target = None
        for r in records:
            if r.get("id") == stage_id:
                target = r
                break

        if not target:
            raise KeyError(f"Không tìm thấy staged skill với ID '{stage_id}'")

        if target.get("status") != "PENDING":
            raise ValueError(f"Staged skill '{stage_id}' đã ở trạng thái {target.get('status')}")

        name = target["name"]
        branch = target.get("branch", "app")
        content = target["content"]
        metadata = target.get("metadata", {})

        # Ghi kỹ năng vào codebase
        self.create_skill(name=name, branch=branch, content=content, metadata=metadata)

        target["status"] = "APPROVED"
        target["approved_at"] = datetime.now(timezone.utc).isoformat()
        self._save_staged_records(records)
        return target

    def reject_staged_skill(self, stage_id: str, reason: str = "") -> dict:
        """Từ chối kỹ năng trong staging."""
        records = self._load_staged_records()
        target = None
        for r in records:
            if r.get("id") == stage_id:
                target = r
                break

        if not target:
            raise KeyError(f"Không tìm thấy staged skill với ID '{stage_id}'")

        if target.get("status") != "PENDING":
            raise ValueError(f"Staged skill '{stage_id}' đã ở trạng thái {target.get('status')}")

        target["status"] = "REJECTED"
        target["reason"] = reason
        target["rejected_at"] = datetime.now(timezone.utc).isoformat()
        self._save_staged_records(records)
        return target

    # ----------------------- ARCHIVE -----------------------
    def archive_skill(self, name: str, branch: Optional[str] = None) -> Optional[Path]:
        """Di chuyển kỹ năng không còn dùng vào thư mục lưu trữ archive."""
        skill_path = self.find_skill_path(name)
        if not skill_path or not skill_path.exists():
            return None

        skill_dir = skill_path.parent
        target_archive_dir = self.archive_dir / name
        target_archive_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_archive_dir / "SKILL.md"
        target_file.write_text(skill_path.read_text(encoding="utf-8"), encoding="utf-8")

        # Xóa file và thư mục gốc nếu rỗng
        try:
            skill_path.unlink()
            for item in skill_dir.iterdir():
                if item.is_file():
                    (target_archive_dir / item.name).write_bytes(item.read_bytes())
                    item.unlink()
            skill_dir.rmdir()
        except OSError:
            pass

        return target_file
