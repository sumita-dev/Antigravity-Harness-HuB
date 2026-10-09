"""Test chặn lỗi cấu trúc & an toàn cho toàn repo.

Bộ test này tồn tại vì các lỗi sau từng lọt qua 31 test cũ:
- 29 thư mục skill bị lồng chính nó (skills/<x>/<x>/)
- 62 file chỉ chứa thông báo lỗi "Không có file ..." bị commit như nội dung
- path tuyệt đối gắn với máy cá nhân trong SKILL.md
- dữ liệu runtime (.brain) bị commit và bị test ghi thêm
- secret (Page token, API key) hardcode
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO / "plugins"
DOC_SUFFIXES = {".md", ".json", ".py", ".js", ".mjs", ".ps1", ".sh", ".txt"}

# Con trỏ trỏ ra NGOÀI skill (artifact do agent tự tạo trong dự án người dùng,
# hoặc file thuộc repo khác) — không phải file của skill nên không cần tồn tại.
EXTERNAL_REF_OK = {
    "CONTEXT.md",
    "CONTEXT-MAP.md",
    "STATE.md",
}
EXTERNAL_PREFIX_OK = (
    "http://", "https://", "~", "/",
    "docs/", "eval/", "gitnexus/", ".agents/", ".claude/",
)

# File phụ trợ được tài liệu nhắc tới nhưng CHƯA từng có trong repo (đã tra git
# history + toàn máy): không tự bịa nội dung, chỉ ghi nhận để port sau.
# Mỗi mục đều có ghi chú "TRẠNG THÁI SKILL" ngay trong SKILL.md tương ứng.
# File phụ trợ được tài liệu nhắc tới nhưng CHƯA từng có trong repo:
# Toàn bộ tham chiếu ảo của skill /app đã được dọn sạch và chuyển đổi sang Native SubAgents.
KNOWN_GAPS = set()


def _skill_dirs():
    return sorted(p for p in SKILL_ROOT.glob("*/skills/*") if p.is_dir())


def _doc_files():
    for p in REPO.rglob("*"):
        parts = p.relative_to(REPO).parts
        if not p.is_file() or ".git" in parts or ".venv" in parts or ".gitnexus" in parts or ".brain" in parts:
            continue
        if any(part.startswith(".pytest") for part in parts):
            continue
        if p.suffix.lower() in DOC_SUFFIXES:
            yield p


def test_no_self_nested_skill_dirs():
    """Không được có skills/<ten>/<ten>/ (rác sinh ra khi copy sai tầng)."""
    nested = [str(p.relative_to(REPO)) for p in _skill_dirs() if (p / p.name).is_dir()]
    assert not nested, f"Thư mục skill bị lồng chính nó: {nested}"


def test_no_error_stub_files():
    """Không file nào chỉ chứa thông báo lỗi thay vì nội dung thật."""
    pat = re.compile(r'^Không có file ".*" trong skill ".*"\.\s*$')
    bad = []
    for p in _doc_files():
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if len(t) < 300 and pat.match(t.strip()):
            bad.append(str(p.relative_to(REPO)))
    assert not bad, f"File rác chứa thông báo lỗi: {bad}"


def test_no_machine_specific_paths():
    """Không lộ path/hostname gắn với máy cá nhân trong tài liệu & script."""
    patterns = [
        re.compile(r"[A-Za-z]:\\Users\\(?!<)"),
        re.compile("trong-" + "zero-zone"),  # tách chuỗi để test không tự khớp chính nó
        re.compile(r"AntiGravity\\crawl4ai"),
    ]
    bad = []
    for p in _doc_files():
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(t.splitlines(), 1):
            if any(rx.search(line) for rx in patterns):
                bad.append(f"{p.relative_to(REPO)}:{i}")
    assert not bad, f"Path/hostname cá nhân còn sót: {bad}"


def test_skill_doc_references_resolve():
    """Mọi file được SKILL.md nhắc tới (dạng `path/file.md`) phải tồn tại."""
    missing = []
    for skill in _skill_dirs():
        f = skill / "SKILL.md"
        if not f.exists():
            missing.append(f"{skill.relative_to(REPO)}: thiếu SKILL.md")
            continue
        text = f.read_text(encoding="utf-8")
        refs = set(re.findall(r"`([\w][\w./\-]*\.(?:md|py|js|mjs|json|html|txt|sh|ts))`", text))
        refs |= set(re.findall(r"\]\(([\w][\w./\-]*\.(?:md|py|js|mjs|json|html|txt|sh|ts))\)", text))
        for ref in refs:
            if "/" not in ref:
                continue  # mention trong câu văn, không phải đường dẫn
            if ref.startswith(EXTERNAL_PREFIX_OK) or ref in EXTERNAL_REF_OK:
                continue
            if (skill / ref).exists() or (REPO / ref).exists():
                continue
            entry = f"{skill.relative_to(REPO).as_posix()} -> {ref}"
            if entry in KNOWN_GAPS:
                continue
            missing.append(entry)
    assert not missing, f"Con trỏ file không tồn tại: {missing}"


def test_skill_frontmatter_matches_dirname():
    bad = []
    for skill in _skill_dirs():
        f = skill / "SKILL.md"
        if not f.exists():
            continue
        m = re.match(r"---\s*\n(.*?)\n---", f.read_text(encoding="utf-8"), re.S)
        if not m:
            bad.append(f"{skill.name}: không có frontmatter")
            continue
        nm = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
        if not nm or nm.group(1).strip().strip("\"'") != skill.name:
            bad.append(f"{skill.name}: name không khớp tên thư mục")
    assert not bad, bad


def test_plugin_manifest_valid():
    for plug in sorted(p for p in SKILL_ROOT.iterdir() if p.is_dir()):
        pj = plug / "plugin.json"
        assert pj.exists(), f"Thiếu plugin.json cho plugin {plug.name}"
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert data.get("name") == plug.name, f"plugin.json name lệch: {plug.name}"
        assert data.get("description"), f"plugin.json thiếu description: {plug.name}"
        assert (plug / "skills").is_dir(), f"Plugin {plug.name} không có thư mục skills/"


def test_skill_config_paths_exist():
    """Mọi search path trong .agent/.agents phải trỏ tới thư mục có thật."""
    for cfg in (REPO / ".agent/skills.json", REPO / ".agents/skills.json"):
        assert cfg.exists(), f"Thiếu {cfg.relative_to(REPO)}"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        for entry in data.get("entries", []):
            path = entry.get("path", "")
            assert (REPO / path).exists(), f"{cfg.relative_to(REPO)}: path chết '{path}'"


def test_no_committed_secrets():
    """Không secret thật (Page token / API key) trong working tree."""
    patterns = [
        re.compile(r"EAA[A-Za-z0-9]{30,}"),
        re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    ]
    allow = {"EAAAAALAAAAAABAAEAAAIBRAA7"}  # header GIF trong thư viện screenshot
    bad = []
    for p in _doc_files():
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rx in patterns:
            for m in rx.finditer(t):
                if m.group(0) not in allow:
                    bad.append(f"{p.relative_to(REPO)}: {m.group(0)[:6]}...")
    assert not bad, f"Secret lộ trong repo: {bad}"


def test_brain_runtime_data_not_tracked():
    """Dữ liệu runtime .brain không được git theo dõi."""
    out = subprocess.run(["git", "ls-files", ".brain"], cwd=REPO,
                         capture_output=True, text=True).stdout.strip()
    assert out == "", f"Dữ liệu runtime bị commit: {out}"


def test_requirements_declared():
    req = REPO / "requirements.txt"
    assert req.exists(), "Thiếu requirements.txt"
    low = req.read_text(encoding="utf-8").lower()
    for dep in ("pytest", "pyyaml", "requests"):
        assert dep in low, f"requirements.txt thiếu {dep}"


def test_all_skills_documented_in_gemini_md():
    gem = (REPO / "GEMINI.md").read_text(encoding="utf-8")
    missing = [s.name for s in _skill_dirs() if f"/{s.name}" not in gem]
    assert not missing, f"Skill chưa được ghi trong GEMINI.md: {missing}"


def test_readme_not_claiming_stale_test_count():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "8 passed" not in readme, "README còn số test cũ (8 passed)"


def test_agents_and_gemini_md_in_sync():
    """AGENTS.md là pointer stub tới GEMINI.md để chống duplicate token trên Antigravity 2.0."""
    stub = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "GEMINI.md" in stub, "AGENTS.md phải trỏ tới GEMINI.md"
    assert len(stub.encode("utf-8")) < 1000, "AGENTS.md phải là stub nhẹ (< 1KB) để không lãng phí token"


def test_gemini_md_under_antigravity_token_limit():
    """GEMINI.md phải <= 24,000 bytes để không bao giờ bị Antigravity 2.0 cắt cụt (truncate)."""
    size = (REPO / "GEMINI.md").stat().st_size
    assert size <= 24000, f"GEMINI.md quá lớn ({size} bytes > 24000) khiến Antigravity 2.0 bị truncate"


def test_env_example_duoc_commit():
    """File mẫu .env.example phải tồn tại VÀ được git theo dõi.

    Bẫy đã từng xảy ra: mẫu '.env*' trong .gitignore chặn luôn .env.example.
    """
    example = REPO / ".env.example"
    assert example.exists(), "Thiếu .env.example"
    tracked = subprocess.run(["git", "ls-files", ".env.example"], cwd=REPO,
                             capture_output=True, text=True).stdout.strip()
    assert tracked, ".env.example bị gitignore — thêm '!.env.example' vào .gitignore"
    # Không được chứa giá trị thật (chỉ để trống sau dấu =)
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            assert val.strip() in ("", "<điền-giá-trị-thật>"), f"{key} phải để trống trong file mẫu"

def test_no_phantom_python_scripts_in_skill_codeblocks():
    """Mọi script python trong code block bash (python scripts/<x>.py) phải tồn tại trong repo hoặc skill."""
    missing = []
    pat = re.compile(r"```(?:bash|sh|shell)?\s*\n(.*?)\n```", re.DOTALL)
    for skill in _skill_dirs():
        f = skill / "SKILL.md"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        codeblocks = pat.findall(text)
        for block in codeblocks:
            for line in block.splitlines():
                line = line.strip()
                matches = re.findall(
                    r"(?:python|python3)\s+(?:-[^\s]+\s+)*(?:(?:\./)?((?:[\w./\-]+/)?scripts/[\w./\-]+\.py))",
                    line,
                )
                for script_rel in matches:
                    if not (skill / script_rel).exists() and not (REPO / script_rel).exists():
                        missing.append(f"{skill.relative_to(REPO).as_posix()}: {script_rel}")
    assert not missing, f"Script python ảo trong code block SKILL.md: {missing}"

