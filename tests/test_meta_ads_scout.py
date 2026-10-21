# -*- coding: utf-8 -*-
"""Test suite for Meta Ads Library Intelligence Scout (/meta-ad-scout).

Bao phủ 8 tiêu chí kiểm thử trọng yếu theo Mục 5 Bản Đặc Tả Kỹ Thuật:
1. test_cli_help_and_defaults: Tham số CLI, mặc định, và BooleanOptionalAction (--active-only / --no-active-only).
2. test_url_encoding_vietnamese_exact_phrase: Mã hóa URL tiếng Việt có dấu, exact phrase quote, chuẩn hóa ISO country.
3. test_ad_normalization_and_hallucination_prevention: Chuẩn hóa dữ liệu null-safe, thiếu start_date -> 'N/A' & days_active=0.
4. test_creative_angle_analyzer_heuristics: Phân tích góc tiếp cận, Hook types, Offer, Pain points, Persuasion score.
5. test_seed_data_integrity: Toàn vẹn bộ dữ liệu Rich Seed Data (ngách Sơ sinh & TPCN).
6. test_html_dashboard_xss_prevention: Chống lỗ hổng XSS, nút copy an toàn qua copyCardContent(this), lọc URL scheme độc hại.
7. test_coverage_metrics: Theo dõi chỉ số bao phủ và phát hiện các trường dữ liệu thiếu (missing_fields).
8. test_repo_and_cli_end_to_end: Thực thi CLI main() hoàn chỉnh, xuất JSON/MD/HTML, validation tham số và graceful error handling.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
from pathlib import Path
import pytest

from scripts.meta_ads_scout import (
    AdCreative,
    AdNormalizer,
    CoverageMetrics,
    CreativeAnalysis,
    CreativeAngleAnalyzer,
    MetaScraperEngine,
    ReportExporter,
    ScoutReport,
    SEED_ADS,
    _parse_ad_start_date,
    build_cli_parser,
    build_meta_ads_url,
    compute_coverage,
    is_winning_ad,
    main,
    normalize_raw_ad,
    run_meta_ad_scout,
)


# ==============================================================================
# TEST 1: CLI HELP & DEFAULTS
# ==============================================================================

def test_cli_help_and_defaults():
    """Kiểm tra parser CLI, các cờ mặc định và BooleanOptionalAction cho --active-only."""
    parser = build_cli_parser()
    assert parser.prog == "meta_ads_scout.py"

    # 1. Kiểm tra giá trị mặc định
    args = parser.parse_args([])
    assert args.keyword == "sơ sinh"
    assert args.country == "VN"
    assert args.limit == 20
    assert args.sort == "total_impressions"
    assert args.min_days == 14
    assert args.media_type == "all"
    assert args.active_only is True
    assert args.format == "all"
    assert args.seed is False
    assert args.no_analyze is False
    assert args.json is False

    # 2. Kiểm tra BooleanOptionalAction cho --active-only
    args_inactive = parser.parse_args(["--no-active-only"])
    assert args_inactive.active_only is False

    args_active = parser.parse_args(["--active-only"])
    assert args_active.active_only is True

    # 3. Kiểm tra các tham số tùy chỉnh khác
    custom_args = parser.parse_args([
        "--keyword", "thực phẩm chức năng",
        "--country", "US",
        "--limit", "50",
        "--sort", "start_date",
        "--min-days", "21",
        "--media-type", "video",
        "--format", "json",
        "--seed",
        "--no-analyze",
    ])
    assert custom_args.keyword == "thực phẩm chức năng"
    assert custom_args.country == "US"
    assert custom_args.limit == 50
    assert custom_args.sort == "start_date"
    assert custom_args.min_days == 21
    assert custom_args.media_type == "video"
    assert custom_args.format == "json"
    assert custom_args.seed is True
    assert custom_args.no_analyze is True


# ==============================================================================
# TEST 2: URL ENCODING (TIẾNG VIỆT CÓ DẤU & EXACT PHRASE)
# ==============================================================================

def test_url_encoding_vietnamese_exact_phrase():
    """Kiểm tra hàm tạo URL chuẩn Meta Ads Library: UTF-8 quote, exact phrase, country ISO."""
    url = build_meta_ads_url(
        keyword="sơ sinh",
        country="VN",
        sort="total_impressions",
        active_only=True,
        media_type="all",
    )
    assert "https://www.facebook.com/ads/library/" in url
    assert "country=VN" in url
    assert "active_status=active" in url
    assert "search_type=keyword_exact_phrase" in url
    assert "media_type=all" in url
    assert "sort_data%5Bmode%5D=total_impressions" in url or "sort_data[mode]=total_impressions" in url

    # Kiểm tra exact phrase quote: "sơ sinh" phải được bọc trong dấu ngoặc kép khi mã hóa (%22)
    assert "%22" in url

    # Kiểm tra từ khóa đã có dấu nháy không bị lặp kép
    url_pre_quoted = build_meta_ads_url('"canxi sinh học"', country="vn")
    assert url_pre_quoted.count("%22") == 2
    assert "country=VN" in url_pre_quoted

    # Kiểm tra cờ active_only=False -> active_status=all
    url_all = build_meta_ads_url("mẹ bỉm", active_only=False)
    assert "active_status=all" in url_all

    # Kiểm tra truyền media_type video
    url_video = build_meta_ads_url("tã dán", media_type="video")
    assert "media_type=video" in url_video

    # Kiểm tra mã quốc gia không hợp lệ (phải là 2 ký tự ISO Alpha-2)
    with pytest.raises(ValueError, match="Mã quốc gia không hợp lệ"):
        build_meta_ads_url("test", country="VIETNAM")


# ==============================================================================
# TEST 3: DATA NORMALIZATION & ANTI-HALLUCINATION
# ==============================================================================

def test_ad_normalization_and_hallucination_prevention():
    """Kiểm tra AdNormalizer tuân thủ Anti-hallucination: thiếu start_date -> 'N/A' và days_active=0."""
    # Case 1: Thiếu hoàn toàn start_date -> BẮT BUỘC start_date="N/A", days_active=0
    raw_node_missing_date = {
        "id": "123456",
        "page_name": "Shop Sơ Sinh An Lành",
        "body_text": "Tã dán cho bé sơ sinh dịu nhẹ",
    }
    ad1 = normalize_raw_ad(raw_node_missing_date)
    assert ad1.id == "123456"
    assert ad1.page_name == "Shop Sơ Sinh An Lành"
    assert ad1.start_date == "N/A"
    assert ad1.days_active == 0
    assert "https://www.facebook.com/ads/library/?id=123456" in ad1.ad_snapshot_url

    # Case 2: start_date rỗng hoặc None
    raw_node_empty_date = {
        "id": "123457",
        "start_date": "",
    }
    ad_empty = normalize_raw_ad(raw_node_empty_date)
    assert ad_empty.start_date == "N/A"
    assert ad_empty.days_active == 0

    # Case 3: start_date hợp lệ
    raw_node_valid_date = {
        "id": "789012",
        "page_name": "Bestical Vietnam",
        "start_date": "2026-09-01",
        "body_text": "Canxi sinh học cho bé",
        "media_type": "video",
        "media_urls": ["https://example.com/video.mp4"],
    }
    ad2 = normalize_raw_ad(raw_node_valid_date)
    assert ad2.start_date == "2026-09-01"
    assert ad2.days_active >= 0
    assert ad2.media_urls == ["https://example.com/video.mp4"]

    # Case 4: Lọc bỏ URL scheme không an toàn (javascript:...)
    raw_unsafe_urls = {
        "id": "999999",
        "ad_snapshot_url": "javascript:alert('pwned')",
        "page_profile_picture_url": "javascript:void(0)",
        "media_urls": ["javascript:evil()", "https://valid.com/pic.jpg"],
    }
    ad3 = normalize_raw_ad(raw_unsafe_urls)
    assert ad3.ad_snapshot_url == "https://www.facebook.com/ads/library/?id=999999"
    assert ad3.page_profile_picture_url is None
    assert ad3.media_urls == ["https://valid.com/pic.jpg"]


# ==============================================================================
# TEST 4: HEURISTICS ANALYZER
# ==============================================================================

def test_creative_angle_analyzer_heuristics():
    """Kiểm tra CreativeAngleAnalyzer phân tích Hook types, Offer, Angle và Persuasion Score."""
    analyzer = CreativeAngleAnalyzer()

    # Case A: Hook Nỗi sợ & Cảnh báo (Fear / Problem-Agitate)
    ad_fear = AdCreative(
        id="a1",
        ad_archive_id="a1",
        page_id="p1",
        page_name="Page 1",
        page_profile_picture_url=None,
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=10,
        variant_count=2,
        publisher_platforms=["facebook"],
        body_text="Cảnh báo sai lầm khi chọn tã khiến bé bị hăm loét!\nMẹ cần kiểm tra ngay.",
        title="Tã dán Organic",
        caption=None,
        cta_text="Mua ngay",
        link_url="https://example.com",
        media_type="image",
        media_urls=[],
        ad_snapshot_url="https://www.facebook.com/ads/library/?id=a1",
    )
    analysis_fear = analyzer.analyze(ad_fear)
    assert "Nỗi sợ & Cảnh báo" in analysis_fear.hook_type
    assert 1 <= analysis_fear.persuasion_score <= 10
    assert any("hăm" in p.lower() for p in analysis_fear.pain_points)

    # Case B: Hook Tò mò & Đặt câu hỏi (Curiosity / Question)
    ad_curiosity = AdCreative(
        id="a2",
        ad_archive_id="a2",
        page_id="p2",
        page_name="Page 2",
        page_profile_picture_url=None,
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=5,
        variant_count=1,
        publisher_platforms=["facebook"],
        body_text="Tại sao 90% mẹ bỉm sữa lại đổi sang dòng gối chống trào ngược này?\nBí mật nằm ở góc nghiêng 15 độ.",
        title=None,
        caption=None,
        cta_text=None,
        link_url=None,
        media_type="video",
        media_urls=[],
        ad_snapshot_url="https://www.facebook.com/ads/library/?id=a2",
    )
    analysis_curiosity = analyzer.analyze(ad_curiosity)
    assert "Tò mò & Đặt câu hỏi" in analysis_curiosity.hook_type

    # Case C: Hook Khuyến mãi & Offer
    ad_promo = AdCreative(
        id="a3",
        ad_archive_id="a3",
        page_id="p3",
        page_name="Page 3",
        page_profile_picture_url=None,
        start_date="2026-09-01",
        end_date=None,
        is_active=True,
        days_active=30,
        variant_count=5,
        publisher_platforms=["facebook"],
        body_text="Ưu đãi giảm 30% khi mua Combo 2 hộp sữa bột dinh dưỡng.\nFreeship toàn quốc hôm nay!",
        title="Combo tiết kiệm",
        caption=None,
        cta_text="Nhận ưu đãi",
        link_url="https://example.com",
        media_type="image",
        media_urls=[],
        ad_snapshot_url="https://www.facebook.com/ads/library/?id=a3",
    )
    analysis_promo = analyzer.analyze(ad_promo)
    assert "Khuyến mãi & Ưu đãi" in analysis_promo.hook_type
    assert is_winning_ad(ad_promo, min_days=14) is True


# ==============================================================================
# TEST 5: SEED DATA INTEGRITY
# ==============================================================================

def test_seed_data_integrity():
    """Kiểm tra bộ dữ liệu mẫu Rich Seed Data (SEED_ADS) phong phú và toàn vẹn."""
    assert isinstance(SEED_ADS, list)
    assert len(SEED_ADS) >= 5, "SEED_ADS phải có tối thiểu 5 mẫu quảng cáo phong phú"

    categories = []
    for idx, raw in enumerate(SEED_ADS):
        assert "id" in raw or "ad_archive_id" in raw, f"Sample #{idx} thiếu ID"
        assert "page_name" in raw, f"Sample #{idx} thiếu page_name"
        assert "body_text" in raw and len(raw["body_text"]) > 20, f"Sample #{idx} body_text quá ngắn"
        assert "start_date" in raw, f"Sample #{idx} thiếu start_date"

        # Đảm bảo chuẩn hóa thành công
        ad = normalize_raw_ad(raw)
        assert isinstance(ad, AdCreative)
        assert ad.days_active >= 0
        assert ad.ad_snapshot_url.startswith("http")

        text = (ad.body_text + " " + ad.page_name).lower()
        if "sơ sinh" in text or "bé" in text or "tã" in text:
            categories.append("so_sinh")
        if "não" in text or "canxi" in text or "sức khỏe" in text:
            categories.append("tpcn")

    assert "so_sinh" in categories, "SEED_ADS phải chứa sản phẩm ngách sơ sinh"
    assert "tpcn" in categories, "SEED_ADS phải chứa sản phẩm ngách thực phẩm chức năng"


# ==============================================================================
# TEST 6: HTML DASHBOARD XSS ESCAPING & COPY BUTTON SAFETY
# ==============================================================================

def test_html_dashboard_xss_prevention(tmp_path: Path):
    """Kiểm tra Dashboard HTML miễn nhiễm XSS và nút Copy sử dụng copyCardContent(this)."""
    malicious_ad = AdCreative(
        id="xss1",
        ad_archive_id="xss1",
        page_id="pxss",
        page_name="<script>alert('XSS Page')</script>",
        page_profile_picture_url="javascript:alert('xss_avatar')",
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=15,
        variant_count=3,
        publisher_platforms=["facebook"],
        body_text="Bé hay bị hăm? Xem ngay: <img src=x onerror=alert(1)> & test \"quotes\" and `backticks`",
        title="<svg onload=alert(2)>",
        caption="safe caption",
        cta_text="Click <script>",
        link_url="https://safe.com",
        media_type="image",
        media_urls=["https://safe.com/img.jpg"],
        ad_snapshot_url="javascript:alert('xss_snapshot')",
    )

    analyzer = CreativeAngleAnalyzer()
    analysis = analyzer.analyze(malicious_ad)

    report = ScoutReport(
        keyword="<img src=x onerror=alert(3)>",
        country="VN",
        scouted_at="2026-10-20 12:00:00",
        target_url="javascript:alert(4)",
        total_found=1,
        coverage=CoverageMetrics(1, 1, 0, True, []),
        ads=[malicious_ad],
        analyses={malicious_ad.id: analysis},
    )

    exporter = ReportExporter(tmp_path)
    html_file = exporter.export_html(report, min_days=14)
    content = html_file.read_text(encoding="utf-8")

    # 1. Toàn bộ thẻ HTML nguy hiểm phải được escape
    assert "<script>alert('XSS Page')</script>" not in content
    assert "&lt;script&gt;alert(&#x27;XSS Page&#x27;)&lt;/script&gt;" in content or "&lt;script&gt;" in content
    assert "<img src=x onerror=alert(1)>" not in content

    # 2. Nút Copy KHÔNG được truyền inline body_text vào onclick
    assert 'onclick="copyCardContent(this)"' in content
    assert 'onclick="copyAdCopy(this' not in content

    # 3. Scheme javascript: trong snapshot & avatar & target_url phải bị chặn
    assert 'href="javascript:' not in content
    assert 'src="javascript:' not in content

    # 4. Hàm copyCardContent có mặt trong thẻ <script>
    assert "function copyCardContent(btn)" in content


# ==============================================================================
# TEST 7: COVERAGE METRICS DYNAMIC TRACKING
# ==============================================================================

def test_coverage_metrics():
    """Kiểm tra tính toán chỉ số bao phủ CoverageMetrics và danh sách missing_fields."""
    # Tập ad 1: Đầy đủ các trường
    full_ad = AdCreative(
        id="f1",
        ad_archive_id="f1",
        page_id="p1",
        page_name="Full Page",
        page_profile_picture_url="https://img.com/p.jpg",
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=10,
        variant_count=1,
        publisher_platforms=["facebook"],
        body_text="Nội dung đầy đủ",
        title="Tiêu đề",
        caption="Mô tả",
        cta_text="Mua",
        link_url="https://link.com",
        media_type="image",
        media_urls=["https://img.com/1.jpg"],
        ad_snapshot_url="https://facebook.com/ads/library/?id=f1",
    )
    cov1 = compute_coverage([full_ad], requested=1)
    assert cov1.requested == 1
    assert cov1.collected == 1
    assert cov1.failed == 0
    assert cov1.complete is True
    assert cov1.missing_fields == []

    # Tập ad 2: Khuyết trường title, caption, start_date (gán "N/A")
    partial_ad = AdCreative(
        id="p1",
        ad_archive_id="p1",
        page_id="p1",
        page_name="Partial Page",
        page_profile_picture_url=None,
        start_date="N/A",
        end_date=None,
        is_active=True,
        days_active=0,
        variant_count=1,
        publisher_platforms=["facebook"],
        body_text="Chỉ có body",
        title=None,
        caption=None,
        cta_text=None,
        link_url=None,
        media_type="image",
        media_urls=[],
        ad_snapshot_url="https://facebook.com/ads/library/?id=p1",
    )
    cov2 = compute_coverage([partial_ad], requested=5)
    assert cov2.requested == 5
    assert cov2.collected == 1
    assert cov2.failed == 4
    assert cov2.complete is False
    assert "title" in cov2.missing_fields
    assert "start_date" in cov2.missing_fields
    assert "page_profile_picture_url" in cov2.missing_fields


# ==============================================================================
# TEST 8: CLI END-TO-END EXECUTION & ERROR HANDLING
# ==============================================================================

def test_repo_and_cli_end_to_end(tmp_path: Path):
    """Kiểm tra thực thi CLI main() hoàn chỉnh ở chế độ Seed và bắt lỗi đầu vào."""
    out_dir = str(tmp_path / "cli_test_out")

    # 1. Chạy thành công với định dạng all
    exit_code = main([
        "--keyword", "sơ sinh",
        "--country", "VN",
        "--limit", "3",
        "--format", "all",
        "--seed",
        "--output-dir", out_dir,
    ])
    assert exit_code == 0
    assert (Path(out_dir) / "scout_report.json").exists()
    assert (Path(out_dir) / "scout_report.md").exists()
    assert (Path(out_dir) / "scout_dashboard.html").exists()

    # 2. Chạy với --json in ra stdout
    exit_json = main([
        "--keyword", "canxi",
        "--seed",
        "--limit", "2",
        "--json",
        "--output-dir", out_dir,
    ])
    assert exit_json == 0

    # 3. Lỗi validation --limit (vượt quá 100 hoặc < 1) -> exit code 1, không crash traceback
    exit_bad_limit = main([
        "--limit", "150",
        "--seed",
        "--output-dir", out_dir,
    ])
    assert exit_bad_limit == 1

    exit_zero_limit = main([
        "--limit", "0",
        "--seed",
        "--output-dir", out_dir,
    ])
    assert exit_zero_limit == 1

    # 4. Lỗi mã quốc gia -> exit code 1
    exit_bad_country = main([
        "--country", "VIETNAM",
        "--seed",
        "--output-dir", out_dir,
    ])
    assert exit_bad_country == 1


# ==============================================================================
# TEST 9: PARSE AD START DATE HELPER
# ==============================================================================

def test_parse_ad_start_date_formats():
    """Kiểm tra độ chính xác của hàm bóc tách ngày bắt đầu chạy quảng cáo."""
    assert _parse_ad_start_date("Ngày bắt đầu chạy: 16 Tháng 4, 2026") == "2026-04-16"
    assert _parse_ad_start_date("Bắt đầu chạy vào: 5 thg 12, 2025") == "2025-12-05"
    assert _parse_ad_start_date("Started running on April 16, 2026") == "2026-04-16"
    assert _parse_ad_start_date("Started running on 16 Apr, 2026") == "2026-04-16"
    assert _parse_ad_start_date("15/07/2025") == "2025-07-15"
    assert _parse_ad_start_date("Không có ngày tháng nào") == "N/A"


# ==============================================================================
# TEST 10: ANTI-SILENT FALLBACK IN FETCH (PLAYWRIGHT LIVE VS SEED)
# ==============================================================================

def test_fetch_strictly_forbids_silent_fallback_when_live_fails(monkeypatch):
    """Khi không truyền cờ --seed, nếu Playwright và API thất bại, BẮT BUỘC ném RuntimeError thay vì tự ý fallback về Seed."""
    engine = MetaScraperEngine()

    # 1. Chế độ có cờ seed (--seed / use_seed_only=True) -> Nạp seed bình thường
    ads_seed, cov_seed, tier_seed = engine.fetch("sơ sinh", use_seed_only=True)
    assert len(ads_seed) > 0
    assert tier_seed == "tier4_seed_fallback"

    # 2. Chế độ Live: Giả lập Playwright thành công -> trả về tier1_playwright_live
    fake_ad = AdNormalizer.normalize_node({
        "id": "live_123",
        "page_name": "Live Page",
        "start_date": "2026-04-16",
        "body_text": "Live ad content",
    })
    monkeypatch.setattr(engine, "_fetch_tier1_playwright", lambda url, limit: [fake_ad])
    ads_live, cov_live, tier_live = engine.fetch("sơ sinh", use_seed_only=False)
    assert len(ads_live) == 1
    assert ads_live[0].id == "live_123"
    assert tier_live == "tier1_playwright_live"

    # 3. Chế độ Live: Giả lập Playwright lỗi và không có META_ACCESS_TOKEN -> Ném RuntimeError
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(engine, "_fetch_tier1_playwright", lambda url, limit: (_ for _ in ()).throw(RuntimeError("Network blocked")))

    with pytest.raises(RuntimeError) as exc_info:
        engine.fetch("sơ sinh", use_seed_only=False)

    err_msg = str(exc_info.value)
    assert "Không thể cào dữ liệu trực tiếp từ Meta Ads Library" in err_msg
    assert "--seed" in err_msg

