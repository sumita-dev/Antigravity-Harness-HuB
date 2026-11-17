import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def get_state_path(payload: dict) -> Path:
    art_dir = payload.get("artifactDirectoryPath") or ""
    if art_dir:
        base = Path(art_dir)
    else:
        base = Path(payload.get("cwd") or ".") / ".agents" / ".state"
    base.mkdir(parents=True, exist_ok=True)
    conv_id = payload.get("conversationId") or "default"
    safe_id = "".join(c for c in conv_id if c.isalnum() or c in "-_")[:40] or "default"
    return base / f"gate_state_{safe_id}.json"


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "dirty_code_files": [],
        "dirty_md_files": [],
        "needs_crawl_audit": False,
        "crawl_dirs": [],
        "gate_retries": 0,
    }


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("{}")
        return

    try:
        payload = json.loads(raw)
    except Exception:
        print("{}")
        return

    tool_call = payload.get("toolCall") or {}
    name = (tool_call.get("name") or "").lower()
    args = tool_call.get("args") or {}

    state_path = get_state_path(payload)
    state = load_state(state_path)

    if name in ("write_file", "edit_file"):
        fpath = args.get("Path") or args.get("path") or ""
        if fpath:
            low = fpath.lower()
            if low.endswith((".py", ".json")):
                if fpath not in state["dirty_code_files"]:
                    state["dirty_code_files"].append(fpath)
            elif low.endswith(".md") and not low.endswith("skill.md"):
                if fpath not in state["dirty_md_files"]:
                    state["dirty_md_files"].append(fpath)

    elif name == "run_command":
        cmd = (args.get("CommandLine") or args.get("commandLine") or "").lower()
        if "crawl" in cmd and "verify_crawl_audit" not in cmd and "audit_crawl" not in cmd:
            state["needs_crawl_audit"] = True
            cwd = payload.get("cwd") or "."
            for d in Path(cwd).glob("*_crawled"):
                if d.is_dir() and str(d) not in state["crawl_dirs"]:
                    state["crawl_dirs"].append(str(d))

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("{}")


if __name__ == "__main__":
    main()
