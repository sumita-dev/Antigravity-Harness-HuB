import argparse
import json
import os
import glob
import yaml
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def parse_agent_file(filepath):
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
    return {
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

def get_all_agents(agents_dir="agents"):
    agents = {}
    for subdir in ["app", "marketing"]:
        search_path = os.path.join(agents_dir, subdir, "**", "*.md")
        for filepath in glob.glob(search_path, recursive=True):
            agent_data = parse_agent_file(filepath)
            agents[agent_data["name"]] = agent_data
    return agents

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List all agents")
    parser.add_argument("--export-schema", type=str, help="Export schema for specific agent")
    parser.add_argument("--export-all", action="store_true", help="Export schema for all agents")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    agents_dir = project_root / "agents"
    agents = get_all_agents(str(agents_dir))

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
