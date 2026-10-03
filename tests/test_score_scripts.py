"""Test hai script chấm điểm của skill viet-content-seo-geo-v5.

Chuẩn nghiệm thu (theo SKILL.md): `assets/example-scored.md` phải đạt 100/100/100.
Ngoài ra hai bản Node và Python phải cho kết quả giống hệt nhau.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "plugins" / "marketing" / "skills" / "viet-content-seo-geo-v5"
EXAMPLE = SKILL / "assets" / "example-scored.md"
WEAK = REPO / "tests" / "fixtures" / "article-weak.md"
MID = REPO / "tests" / "fixtures" / "article-mid.md"

NODE = shutil.which("node")


# encoding="utf-8" là BẮT BUỘC: trên Windows, text=True mặc định dùng locale (cp1252)
# nên đọc output UTF-8 của tiến trình con sẽ UnicodeDecodeError -> stdout = None.
def run_py(path, *args):
    return subprocess.run([sys.executable, str(SKILL / "scripts" / "score.py"), str(path), *args],
                          cwd=str(SKILL), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def run_js(path, *args):
    return subprocess.run([NODE, str(SKILL / "scripts" / "score.mjs"), str(path), *args],
                          cwd=str(SKILL), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def test_example_dat_100_100_100():
    """Bài mẫu chính thức của skill phải đạt điểm tuyệt đối và exit code 0."""
    r = run_py(EXAMPLE, "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(r.stdout)
    assert d["scores"] == {"seo": 100, "aeo": 100, "geo": 100}
    assert d["publish"] is True
    assert not [i for g in d["groups"].values() for i in g if i["status"] != "pass"]


def test_bai_yeu_khong_dat_va_exit_2():
    r = run_py(WEAK, "--json")
    assert r.returncode == 2
    assert json.loads(r.stdout)["publish"] is False


def test_file_khong_ton_tai_exit_1():
    r = run_py(SKILL / "khong-co-file-nay.md")
    assert r.returncode == 1


@pytest.mark.skipif(NODE is None, reason="máy không có Node")
@pytest.mark.parametrize("path", [EXAMPLE, WEAK, MID])
def test_hai_ban_giong_het_nhau(path):
    """score.mjs (Node) và score.py (Python) phải cho JSON + exit code giống hệt."""
    a, b = run_py(path, "--json"), run_js(path, "--json")
    assert a.returncode == b.returncode, f"exit code lệch: {a.returncode} vs {b.returncode}"
    assert json.loads(a.stdout) == json.loads(b.stdout), "JSON của hai bản khác nhau"


@pytest.mark.skipif(NODE is None, reason="máy không có Node")
def test_text_nguoi_doc_cua_hai_ban_giong_nhau():
    a, b = run_py(EXAMPLE), run_js(EXAMPLE)
    assert a.stdout.replace("\r\n", "\n") == b.stdout.replace("\r\n", "\n")


def test_nguong_publish_dung_dac_ta():
    """Ngưỡng phải là SEO >= 75 AND AEO >= 70 AND GEO >= 70 (checklist.md)."""
    d = json.loads(run_py(MID, "--json").stdout)
    assert d["thresholds"] == {"seo": 75, "aeo": 70, "geo": 70}
    s = d["scores"]
    assert d["publish"] == (s["seo"] >= 75 and s["aeo"] >= 70 and s["geo"] >= 70)
