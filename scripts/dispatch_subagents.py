import argparse
import json
import os
import glob
import yaml
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.policy import resolve_runtime_policy
from harness.skills.router import SkillRouter

APP_STAGES = {"architect": "DESIGN", "design_reviewer": "DESIGN_REVIEW",
              "builder": "IMPLEMENTATION", "code_critic": "CRITIQUE", "qa_auditor": "AUDIT",
              "e2e_engineer": "AUDIT", "e2e_critic": "AUDIT", "apple_design_critic": "DESIGN_REVIEW"}
MARKETING_STAGES = {"web_researcher": "RESEARCH", "creator": "CREATION", "compliance_critic": "AUDIT"}
ALL_STAGES = {**APP_STAGES, **MARKETING_STAGES}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def parse_agent_file(filepath, *, stage=None, stack="", risk="low"):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = content.split('---')
    if len(parts) >= 3:
        frontmatter = parts[1].strip()
        system_prompt = '---'.join(parts[2:]).strip()
    else:
        frontmatter = ""
        system_prompt = content.strip()

    metadata = {}
    if frontmatter:
        try:
            metadata = yaml.safe_load(frontmatter)
        except Exception:
            pass

    agent_id = Path(filepath).stem
    data = {
        "name": agent_id,
        "agent_name": metadata.get("agent_name", agent_id),
        "branch": metadata.get("branch"),
        "role": metadata.get("role"),
        "model": metadata.get("model", "inherit"),
        "workspace": metadata.get("workspace", "inherit"),
        "runtime_enforcement": "Metadata only; native runtime must apply tool permissions and agent isolation",
        "description": metadata.get("description", ""),
        "system_prompt": system_prompt,
        "enable_write_tools": metadata.get("enable_write_tools", False),
        "enable_mcp_tools": metadata.get("enable_mcp_tools", False),
        "enable_subagent_tools": metadata.get("enable_subagent_tools", False),
    }
    if metadata.get("branch") in ("app", "marketing"):
        policy = resolve_runtime_policy(agent_id, metadata=metadata)
        data["model"] = policy["model_tier"]
        data["model_preference"] = policy["model_preference"]
        data["runtime_policy"] = policy
        selected_stage = stage or ALL_STAGES.get(agent_id, "AUDIT")
        try:
            selection = SkillRouter().compose(selected_stage, agent_id, stack, risk)
            data["skill_selection"] = dict(selection, stage=selected_stage, role=agent_id, stack=stack, risk=risk)
        except Exception:
            data["skill_selection"] = {
                "skills": [],
                "instructions": "",
                "chars": 0,
                "stage": selected_stage,
                "role": agent_id,
                "stack": stack,
                "risk": risk,
            }
    return data


def get_all_agents(agents_dir="agents", *, stage=None, stack="", risk="low"):
    agents = {}
    for subdir in ["app", "marketing"]:
        search_path = os.path.join(agents_dir, subdir, "**", "*.md")
        for filepath in glob.glob(search_path, recursive=True):
            agent_data = parse_agent_file(filepath, stage=stage, stack=stack, risk=risk)
            agents[agent_data["name"]] = agent_data
    return agents

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List all agents")
    parser.add_argument("--export-schema", type=str, help="Export schema for specific agent")
    parser.add_argument("--export-all", action="store_true", help="Export schema for all agents")
    parser.add_argument("--stage", choices=sorted(set(ALL_STAGES.values())), help="Authoritative workflow stage for skill composition")
    parser.add_argument("--stack", default="", help="Configured skill stack profile, e.g. database or ui")
    parser.add_argument("--risk", default="low", choices=["low", "medium", "high", "critical"])
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    agents_dir = project_root / "agents"
    # Compose only requested export; unrelated role profiles must not consume its budget.
    if args.export_schema:
        matches = list(agents_dir.glob(f"*/{args.export_schema}.md")) if args.export_schema.isidentifier() else []
        agents = {args.export_schema: parse_agent_file(matches[0], stage=args.stage, stack=args.stack, risk=args.risk)} if matches else {}
    else:
        agents = get_all_agents(str(agents_dir), stage=args.stage, stack=args.stack, risk=args.risk)

    if args.list:
        for name in sorted(agents.keys()):
            print(name)
    elif args.export_schema:
        agent_name = args.export_schema
        if agent_name in agents:
            print(json.dumps(agents[agent_name], indent=2, ensure_ascii=False))
        else:
            print(f"Agent {agent_name} not found.")
    elif args.export_all:
        print(json.dumps(list(agents.values()), indent=2, ensure_ascii=False))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
