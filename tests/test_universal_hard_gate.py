import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
TRACKER = SCRIPTS_DIR / "gate_tracker.py"
ENFORCER = SCRIPTS_DIR / "gate_enforcer.py"


def run_hook(script: Path, payload: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=15,
    )
    out = json.loads(proc.stdout.strip() or "{}")
    return proc.returncode, out


class TestUniversalHardGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.art_dir = self.tmp_path / "artifacts"
        self.art_dir.mkdir(parents=True, exist_ok=True)
        self.conv_id = "test-gate-001"

    def tearDown(self):
        self.tmp.cleanup()

    def _base_payload(self) -> dict:
        return {
            "conversationId": self.conv_id,
            "artifactDirectoryPath": str(self.art_dir),
            "cwd": str(self.tmp_path),
            "terminationReason": "NO_TOOL_CALL",
        }

    def test_1_code_gate_blocks_syntax_error_and_passes_after_fix(self):
        bad_py = self.tmp_path / "broken.py"
        bad_py.write_text("def foo(:\n    pass\n", encoding="utf-8")

        p_track = self._base_payload()
        p_track["toolCall"] = {"name": "write_file", "args": {"Path": str(bad_py)}}
        rc, out = run_hook(TRACKER, p_track)
        self.assertEqual(rc, 0)
        self.assertEqual(out, {})

        rc, out = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(rc, 0)
        self.assertEqual(out.get("decision"), "continue")
        self.assertIn("PY_SYNTAX", out.get("reason", ""))

        bad_py.write_text("def foo():\n    return 1\n", encoding="utf-8")
        rc, out = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(rc, 0)
        self.assertEqual(out, {})

    def test_2_markdown_gate_blocks_broken_local_link(self):
        md_file = self.tmp_path / "report.md"
        md_file.write_text("Xem [file thiếu](./khong_ton_tai.md) nhé.\n", encoding="utf-8")

        p_track = self._base_payload()
        p_track["toolCall"] = {"name": "write_file", "args": {"Path": str(md_file)}}
        run_hook(TRACKER, p_track)

        rc, out = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(out.get("decision"), "continue")
        self.assertIn("MD_BROKEN_LINK", out.get("reason", ""))

    def test_3_crawl_gate_blocks_short_stub_and_missing_refs(self):
        crawl_dir = self.tmp_path / "demo_crawled"
        crawl_dir.mkdir()
        (crawl_dir / "stub.md").write_text(
            "---\ntitle: \"Stub\"\nurl: https://example.com/a\n---\n\n# Stub\n\nBài viết đã được chuyển đến địa chỉ mới\n",
            encoding="utf-8",
        )
        (crawl_dir / "good.md").write_text(
            "---\ntitle: \"Good\"\nurl: https://example.com/b\n---\n\n# Good\n\n" + ("Nội dung chính sách hợp lệ. " * 20) + "\nXem thêm https://example.com/missing_page\n",
            encoding="utf-8",
        )

        p_track = self._base_payload()
        p_track["toolCall"] = {"name": "run_command", "args": {"CommandLine": "python crawl_demo.py"}}
        run_hook(TRACKER, p_track)

        rc, out = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(out.get("decision"), "continue")
        self.assertIn("CRAWL_TOO_SHORT", out.get("reason", ""))

    def test_4_circuit_breaker_prevents_infinite_loop(self):
        bad_json = self.tmp_path / "bad.json"
        bad_json.write_text("{broken json", encoding="utf-8")

        p_track = self._base_payload()
        p_track["toolCall"] = {"name": "write_file", "args": {"Path": str(bad_json)}}
        run_hook(TRACKER, p_track)

        _, out1 = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(out1.get("decision"), "continue")
        _, out2 = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(out2.get("decision"), "continue")
        _, out3 = run_hook(ENFORCER, self._base_payload())
        self.assertEqual(out3, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
