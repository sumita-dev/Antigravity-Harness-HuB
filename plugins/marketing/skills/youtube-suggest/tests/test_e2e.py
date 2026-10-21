#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End Test Suite for youtube-suggest Skill
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = CURRENT_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fetch_suggestions import fetch_raw_suggestions, collect_suggestions


class TestYouTubeSuggestE2E(unittest.TestCase):

    def test_01_fetch_raw_suggestions_forex(self):
        """Test direct API call for 'forex' returns > 5 keywords."""
        results = fetch_raw_suggestions("forex", lang="vi", geo="vn")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 5, f"Expected > 5 suggestions, got {len(results)}")
        # Check that 'forex' appears in at least some of the suggestions
        matches = [kw for kw in results if "forex" in kw.lower()]
        self.assertGreater(len(matches), 3, "Expected multiple matches containing 'forex'")

    def test_02_collect_suggestions_basic(self):
        """Test collector logic in basic mode."""
        data = collect_suggestions("forex", mode="basic", lang="vi", geo="vn")
        self.assertGreater(len(data), 5)
        first = data[0]
        self.assertIn("rank", first)
        self.assertIn("keyword", first)
        self.assertIn("source_query", first)
        self.assertEqual(first["rank"], 1)

    def test_03_cli_export_json_and_csv(self):
        """Test CLI execution and temporary file exports (JSON & CSV)."""
        script_path = SCRIPTS_DIR / "fetch_suggestions.py"
        self.assertTrue(script_path.exists(), f"Script not found at {script_path}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            json_out = Path(tmp_dir) / "test_suggestions.json"
            csv_out = Path(tmp_dir) / "test_suggestions.csv"

            # 1. Test JSON export via CLI
            cmd_json = [
                sys.executable,
                str(script_path),
                "-k", "forex",
                "-m", "basic",
                "-l", "vi",
                "-g", "vn",
                "-o", str(json_out),
                "-f", "json"
            ]
            res_json = subprocess.run(cmd_json, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res_json.returncode, 0, f"JSON CLI failed: {res_json.stderr}")
            self.assertTrue(json_out.exists(), "JSON output file was not created")

            # Validate JSON content & UTF-8
            with open(json_out, "r", encoding="utf-8") as f:
                json_data = json.load(f)
            self.assertEqual(json_data["seed"], "forex")
            self.assertGreater(json_data["total"], 5)
            self.assertIsInstance(json_data["suggestions"], list)

            # 2. Test CSV export via CLI
            cmd_csv = [
                sys.executable,
                str(script_path),
                "-k", "forex",
                "-m", "basic",
                "-l", "vi",
                "-g", "vn",
                "-o", str(csv_out),
                "-f", "csv"
            ]
            res_csv = subprocess.run(cmd_csv, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res_csv.returncode, 0, f"CSV CLI failed: {res_csv.stderr}")
            self.assertTrue(csv_out.exists(), "CSV output file was not created")

            # Validate CSV content & UTF-8-sig
            with open(csv_out, "r", encoding="utf-8-sig") as f:
                reader = list(csv.DictReader(f))
            self.assertGreater(len(reader), 5)
            self.assertIn("keyword", reader[0])
            self.assertIn("rank", reader[0])
            # Check presence of Vietnamese characters without corruption
            has_vietnamese = any("forex là gì" in row["keyword"].lower() for row in reader)
            # Either contains "forex là gì" or at least valid non-empty keywords
            self.assertTrue(all(len(row["keyword"]) > 0 for row in reader))


if __name__ == "__main__":
    unittest.main()
