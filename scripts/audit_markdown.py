import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.stdout.reconfigure(encoding="utf-8")

LINK_RE = re.compile(r"\[[^\]]*\]\(((?:[^()\s#]+|\([^()\s#]*\))+)(?:#[^)\s]*)?\)")


def audit_markdown_files(paths: list[str]) -> list[str]:
    errors: list[str] = []
    for raw_p in paths:
        p = Path(raw_p)
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            errors.append(f"[MD_UTF8] {p.name}: {e}")
            continue

        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "customization://", "conversation://")):
                continue
            if target.startswith("file:///"):
                parsed = urlparse(target)
                local_path = Path(unquote(parsed.path.lstrip("/")))
            else:
                local_path = (p.parent / unquote(target)).resolve()

            if not local_path.exists():
                errors.append(f"[MD_BROKEN_LINK] {p.name} -> {target}")
    return errors


if __name__ == "__main__":
    errs = audit_markdown_files(sys.argv[1:])
    if errs:
        for e in errs:
            print(e)
        sys.exit(1)
    print("MD_AUDIT_OK")
