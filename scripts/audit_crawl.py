import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import urldefrag

sys.stdout.reconfigure(encoding="utf-8")

MIN_CHARS = 300
BAD_MARKERS = [
    "bài viết đã được chuyển đến địa chỉ mới",
    "404 not found",
    "access denied",
    "verify you are human",
]


def audit_crawl_dir(crawl_dir: Path) -> list[str]:
    errors: list[str] = []
    if not crawl_dir.exists() or not crawl_dir.is_dir():
        return [f"[CRAWL_MISSING_DIR] {crawl_dir}"]

    md_files = sorted(p for p in crawl_dir.rglob("*.md") if not p.name.startswith("00_"))
    if not md_files:
        return [f"[CRAWL_EMPTY] No markdown files in {crawl_dir}"]

    seen_hashes: dict[str, str] = {}
    crawled_urls: set[str] = set()
    referenced_urls: set[str] = set()
    domains: set[str] = set()

    for p in md_files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        body = txt
        if txt.startswith("---"):
            parts = txt.split("---", 2)
            if len(parts) == 3:
                fm, body = parts[1], parts[2].strip()
                m_u = re.search(r"^url:\s*(.+)$", fm, re.M)
                if m_u:
                    cu = urldefrag(m_u.group(1).strip())[0].rstrip("/")
                    crawled_urls.add(cu)
                    m_dom = re.search(r"https?://([^/]+)", cu)
                    if m_dom:
                        parts_dom = m_dom.group(1).split(".")
                        domains.add(".".join(parts_dom[-2:]))

        body_no_h1 = re.sub(r"^#\s+.*\n+", "", body, count=1).strip()
        if len(body_no_h1) < MIN_CHARS:
            errors.append(f"[CRAWL_TOO_SHORT] {p.relative_to(crawl_dir)} ({len(body_no_h1)} chars)")
            continue

        low_b = body_no_h1.lower()
        for bm in BAD_MARKERS:
            if bm in low_b and len(body_no_h1) < 1000:
                errors.append(f"[CRAWL_BAD_MARKER] {p.relative_to(crawl_dir)} ({bm})")

        h = hashlib.sha256(body_no_h1.encode("utf-8")).hexdigest()[:16]
        if h in seen_hashes:
            errors.append(f"[CRAWL_DUP] {p.name} duplicates {seen_hashes[h]}")
        else:
            seen_hashes[h] = p.name

        for u in re.findall(r"https?://[^\s\)\]>\"'`]+", body_no_h1):
            nu = urldefrag(u.strip().rstrip(".,;:"))[0].rstrip("/")
            if any(d in nu for d in domains):
                referenced_urls.add(nu)

    # Optional ignore list
    ignore_file = crawl_dir / "audit_ignore.txt"
    ignored_patterns = []
    if ignore_file.exists():
        ignored_patterns = [l.strip().lower() for l in ignore_file.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]

    if crawled_urls and referenced_urls:
        missing = []
        for u in sorted(referenced_urls):
            if u in crawled_urls:
                continue
            low = u.lower()
            if any(ig in low for ig in ignored_patterns):
                continue
            missing.append(u)
        if missing:
            errors.append(f"[CRAWL_MISSING_REFS] {len(missing)} referenced URLs not crawled (e.g. {missing[0]})")

    return errors


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errs = audit_crawl_dir(target)
    if errs:
        for e in errs:
            print(e)
        sys.exit(1)
    print("CRAWL_AUDIT_OK")
