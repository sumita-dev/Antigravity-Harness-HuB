#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End Test Suite for YouTube Keyword Intelligence & SERP Audit Engine (VKOS v3.0)
Standard library only: unittest, subprocess, os, json, sys, tempfile
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

# Add scripts directory to path for unit tests
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, SCRIPT_DIR)

import keyword_intelligence as ki


class TestYouTubeKeywordIntelligence(unittest.TestCase):

    def test_01_keyword_clustering_five_groups(self):
        """Verify semantic classification correctly populates all 5 clusters."""
        sample_keywords = [
            "forex là gì",
            "cách mở tài khoản forex exness",
            "forex có lừa đảo không",
            "đánh giá sàn forex uy tín nhất",
            "chiến lược scalping forex hiệu quả"
        ]
        
        clustered = ki.cluster_keywords(sample_keywords)
        self.assertEqual(len(clustered), 5)
        self.assertIn("forex là gì", clustered["Dinh_Nghia_Khai_Niem"])
        self.assertIn("cách mở tài khoản forex exness", clustered["Huong_Dan_Thuc_Hanh"])
        self.assertIn("forex có lừa đảo không", clustered["Hoai_Nghi_Rui_Ro_Phap_Ly"])
        self.assertIn("đánh giá sàn forex uy tín nhất", clustered["Danh_Gia_Chon_San"])
        self.assertIn("chiến lược scalping forex hiệu quả", clustered["Chien_Thuat_Kinh_Nghiem"])

    def test_02_policy_safety_evaluation(self):
        """Verify Yellow Dollar detection vs Green Safe zone."""
        # Red flag test
        red_result = ki.evaluate_policy_safety("kéo tài xỉu forex bao lỗ 100%")
        self.assertEqual(red_result["status"], "HIGH_RISK_RED")
        self.assertLessEqual(red_result["pms_score"], 30.0)

        # Caution test
        caution_result = ki.evaluate_policy_safety("kiếm tiền nhanh làm giàu từ forex")
        self.assertEqual(caution_result["status"], "CAUTION_YELLOW")
        self.assertEqual(caution_result["pms_score"], 60.0)

        # Green test
        green_result = ki.evaluate_policy_safety("quản lý vốn forex cho người mới bắt đầu")
        self.assertEqual(green_result["status"], "SAFE_GREEN")
        self.assertEqual(green_result["pms_score"], 100.0)

    def test_03_vkos_v3_scoring_formula(self):
        """Verify VKOS v3.0 formula calculation and mathematical integrity."""
        mock_serp = {
            "median_views": 50000,
            "pct_evergreen_videos": 65.0,
            "shorts_shelf_present": False,
            "pct_long_videos": 30.0,
            "avg_views": 80000,
        }
        mock_policy = {
            "status": "SAFE_GREEN",
            "pms_score": 100.0,
        }

        scores = ki.compute_vkos_scores(
            keyword="hướng dẫn trade forex cho người mới",
            cluster_key="Huong_Dan_Thuc_Hanh",
            serp=mock_serp,
            policy=mock_policy
        )

        # Verify keys
        expected_keys = ["VKOS", "VMS", "EDO", "CSG", "LRP", "PMS", "CCV"]
        for k in expected_keys:
            self.assertIn(k, scores)

        # Verify range 0 - 100
        for k, v in scores.items():
            self.assertGreaterEqual(v, 0.0, f"{k} is below 0")
            self.assertLessEqual(v, 100.0, f"{k} exceeds 100")

        # Verify formula weighting
        expected_vkos = round(
            0.25 * scores["VMS"] +
            0.20 * scores["EDO"] +
            0.20 * scores["CSG"] +
            0.15 * scores["LRP"] +
            0.10 * scores["PMS"] +
            0.10 * scores["CCV"],
            1
        )
        self.assertAlmostEqual(scores["VKOS"], expected_vkos, places=1)

    def test_04_actionable_briefing_generation(self):
        """Verify actionable briefing generates all required fields."""
        mock_serp = {
            "median_views": 25000,
            "pct_evergreen_videos": 70.0,
            "shorts_shelf_present": True,
            "pct_long_videos": 50.0,
            "avg_views": 45000,
        }
        mock_policy = ki.evaluate_policy_safety("học forex cơ bản")
        scores = ki.compute_vkos_scores("học forex cơ bản", "Huong_Dan_Thuc_Hanh", mock_serp, mock_policy)
        briefing = ki.generate_actionable_briefing("học forex cơ bản", "Huong_Dan_Thuc_Hanh", scores, mock_serp, mock_policy)

        self.assertIn("winning_keyword", briefing)
        self.assertIn("why_it_wins", briefing)
        self.assertIn("content_angle", briefing)
        self.assertIn("recommended_duration", briefing)
        self.assertIn("thumbnail_hook_strategy", briefing)
        self.assertIn("policy_guardrail", briefing)

    def test_05_e2e_cli_execution_and_exports(self):
        """Run CLI in fast mode on 'forex' and verify all export formats exist."""
        script_path = os.path.join(SCRIPT_DIR, "keyword_intelligence.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_prefix = os.path.join(tmpdir, "test_run")
            cmd = [
                sys.executable,
                script_path,
                "-k", "forex",
                "--fast",
                "--format", "all",
                "-o", out_prefix
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res.returncode, 0, f"CLI exited with error: {res.stderr}")

            md_path = f"{out_prefix}.md"
            json_path = f"{out_prefix}.json"
            csv_path = f"{out_prefix}.csv"

            self.assertTrue(os.path.exists(md_path), "Markdown report was not created")
            self.assertTrue(os.path.exists(json_path), "JSON data file was not created")
            self.assertTrue(os.path.exists(csv_path), "CSV dataset was not created")

            # Check JSON contents
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["seed_keyword"], "forex")
                self.assertGreater(data["total_harvested"], 0)
                self.assertEqual(len(data["top_winners"]), 5)

            # Check Markdown contents
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("BÁO CÁO NGHIÊN CỨU TỪ KHÓA & SERP AUDIT YOUTUBE", content)
                self.assertIn("VKOS v3.0", content)
                self.assertIn("1. Định nghĩa / Khái niệm", content)


if __name__ == "__main__":
    unittest.main()
