import json
import py_compile
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def audit_code_files(paths: list[str]) -> list[str]:
    errors: list[str] = []
    for raw_p in paths:
        p = Path(raw_p)
        if not p.exists():
            continue
        low = p.name.lower()
        if low.endswith(".py"):
            try:
                py_compile.compile(str(p), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"[PY_SYNTAX] {p.name}: {e.msg}")
        elif low.endswith(".json"):
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"[JSON_SYNTAX] {p.name}: {e}")
    return errors


if __name__ == "__main__":
    errs = audit_code_files(sys.argv[1:])
    if errs:
        for e in errs:
            print(e)
        sys.exit(1)
    print("CODE_AUDIT_OK")
