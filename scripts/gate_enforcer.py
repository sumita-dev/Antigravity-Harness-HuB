import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from audit_code import audit_code_files
from audit_crawl import audit_crawl_dir
from audit_markdown import audit_markdown_files
from gate_tracker import get_state_path, load_state

MAX_GATE_RETRIES = 2


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

    reason_stop = payload.get("terminationReason") or "NO_TOOL_CALL"
    if reason_stop != "NO_TOOL_CALL":
        print("{}")
        return

    state_path = get_state_path(payload)
    if not state_path.exists():
        print("{}")
        return

    state = load_state(state_path)
    if state.get("gate_retries", 0) >= MAX_GATE_RETRIES:
        # Circuit breaker: prevent infinite loop
        state["gate_retries"] = 0
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print("{}")
        return

    all_errors: list[str] = []

    if state.get("dirty_code_files"):
        all_errors.extend(audit_code_files(state["dirty_code_files"]))

    if state.get("dirty_md_files"):
        all_errors.extend(audit_markdown_files(state["dirty_md_files"]))

    if state.get("needs_crawl_audit"):
        for d in state.get("crawl_dirs", []):
            all_errors.extend(audit_crawl_dir(Path(d)))

    if all_errors:
        state["gate_retries"] = state.get("gate_retries", 0) + 1
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = "\n".join(all_errors[:10])
        out = {
            "decision": "continue",
            "reason": (
                f"[UNIVERSAL HARD GATE BLOCKED - Attempt {state['gate_retries']}/{MAX_GATE_RETRIES}]\n"
                f"Phát hiện lỗi chưa đạt chuẩn trước khi hoàn tất:\n{summary}\n"
                "Hãy sửa triệt để các lỗi trên rồi mới kết thúc."
            ),
        }
        print(json.dumps(out, ensure_ascii=False))
        return

    # Clear dirty flags when all gates pass
    state["dirty_code_files"] = []
    state["dirty_md_files"] = []
    state["needs_crawl_audit"] = False
    state["gate_retries"] = 0
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("{}")


if __name__ == "__main__":
    main()
