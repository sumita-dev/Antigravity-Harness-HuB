#!/usr/bin/env python3
"""Validate skill metadata, relative references, and router coverage."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Đảm bảo UTF-8 cho Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import yaml

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
LOCAL_CHECKOUT = re.compile(r"(?i)(?:file:///|[A-Z]:[/\\])[^\s)]*(?:antigravity-harness-hub|antigravity-harness)")


def lint(root: Path) -> list[str]:
    errors: list[str] = []
    skills: dict[str, list[Path]] = defaultdict(list)
    skill_files = sorted((root / "plugins").rglob("SKILL.md"))
    for path in skill_files:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            errors.append(f"{relative}: missing or invalid YAML frontmatter")
            continue
        try:
            metadata = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            errors.append(f"{relative}: invalid YAML frontmatter: {exc}")
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{relative}: frontmatter must be a mapping")
            continue
        name, description = metadata.get("name"), metadata.get("description")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{relative}: missing required name")
        else:
            skills[name].append(path)
        if not isinstance(description, str) or not description.strip():
            errors.append(f"{relative}: missing required description")
        if LOCAL_CHECKOUT.search(text):
            errors.append(f"{relative}: contains absolute local file reference")
        for target in LINK.findall(text):
            target = target.strip().split()[0].strip("<>") if target.strip() else ""
            if not target or target.lower() in ("url", "your-url") or target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            if target.startswith("file:"):
                errors.append(f"{relative}: forbidden file:/// link: {target}")
                continue
            local_target = target.split("#", 1)[0].split("?", 1)[0]
            if local_target and not (path.parent / local_target).exists():
                errors.append(f"{relative}: missing link target {target}")

    for name, paths in sorted(skills.items()):
        if len(paths) > 1:
            display = ", ".join(p.relative_to(root).as_posix() for p in paths)
            errors.append(f"duplicate skill name {name}: {display}")

    config_path = root / "configs" / "harness_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return errors + [f"configs/harness_config.json: cannot read router config: {exc}"]
    routes = config.get("skill_routing", {})
    direct_only = config.get("skill_direct_only", [])
    if not isinstance(routes, dict):
        errors.append("configs/harness_config.json: skill_routing must be an object")
        routes = {}
    if not isinstance(direct_only, list) or any(not isinstance(item, str) for item in direct_only):
        errors.append("configs/harness_config.json: skill_direct_only must be a list of names")
        direct_only = []
    for name, route in routes.items():
        if name not in skills:
            errors.append(f"router route {name}: skill does not exist")
        if not isinstance(route, dict) or route.get("branch") not in ("app", "marketing"):
            errors.append(f"router route {name}: branch must be app or marketing")
        elif not isinstance(route.get("keywords"), list) or not route["keywords"]:
            errors.append(f"router route {name}: keywords must be a non-empty list")
    for name in direct_only:
        if name not in skills:
            errors.append(f"direct-only skill {name}: skill does not exist")
        if name in routes:
            errors.append(f"skill {name}: cannot be both routed and direct-only")
    for name in sorted(skills):
        if name not in routes and name not in direct_only:
            errors.append(f"skill {name}: unclassified (add a route or skill_direct_only entry)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = lint(args.root.resolve())
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print(f"Skill integrity OK: {len(list((args.root / 'plugins').rglob('SKILL.md')))} skills checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
