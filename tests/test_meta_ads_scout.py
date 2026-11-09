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
    autolink_urls,
    build_cli_parser,
    build_meta_ads_url,
    compute_coverage,
    is_winning_ad,
    main,
    kill_process_tree,
    map_scrape_js_item_to_ad_creative,
    normalize_raw_ad,
    run_meta_ad_scout,
    run_node_scrape_subprocess,
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
    assert args.cdp_port is None

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
        "--cdp-port", "9222",
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
    assert custom_args.cdp_port == 9222


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
    monkeypatch.setattr(engine, "_fetch_tier1_node", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Node unavailable")))

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



# ==============================================================================
# TEST 11: MAP SCRAPE.JS ITEM TO AD_CREATIVE (ADAPTER PATTERN)
# ==============================================================================

def test_map_scrape_js_item_to_ad_creative():
    """Kiểm tra mapping chính xác 100% schema từ scrape.js sang AdCreative."""
    raw_item = {
        "ad_id": "987654321",
        "library_url": "https://www.facebook.com/ads/library/?id=987654321",
        "page_id": "11223344",
        "page_name": "Nhãn hàng Mẹ & Bé",
        "is_active": True,
        "start_date": "2026-04-01",
        "end_date": None,
        "days_running": 35,
        "variants": 6,
        "collation_id": "coll_99",
        "platforms": ["facebook", "instagram"],
        "format": "VIDEO",
        "body": "Bỉm tã hữu cơ công nghệ Nhật Bản...",
        "title": "Ưu đãi combo sơ sinh",
        "cta": "MUA NGAY",
        "link_url": "https://brand.vn/bim-ta",
        "link_caption": "brand.vn",
        "images": ["https://cdn.brand.vn/thumb.jpg"],
        "videos": ["https://cdn.brand.vn/video.mp4"],
        "video_preview": "https://cdn.brand.vn/preview.jpg",
        "card_count": 1,
    }

    ad = map_scrape_js_item_to_ad_creative(raw_item)
    assert isinstance(ad, AdCreative)
    assert ad.id == "987654321"
    assert ad.ad_archive_id == "987654321"
    assert ad.page_id == "11223344"
    assert ad.page_name == "Nhãn hàng Mẹ & Bé"
    assert ad.is_active is True
    assert ad.start_date == "2026-04-01"
    assert ad.days_active == 35
    assert ad.variant_count == 6
    assert "facebook" in ad.publisher_platforms
    assert "instagram" in ad.publisher_platforms
    assert ad.media_type == "video"
    assert "https://cdn.brand.vn/video.mp4" in ad.media_urls
    assert "https://cdn.brand.vn/thumb.jpg" in ad.media_urls
    assert ad.body_text == "Bỉm tã hữu cơ công nghệ Nhật Bản..."
    assert ad.title == "Ưu đãi combo sơ sinh"
    assert ad.caption == "brand.vn"
    assert ad.cta_text == "MUA NGAY"
    assert ad.link_url == "https://brand.vn/bim-ta"
    assert ad.ad_snapshot_url == "https://www.facebook.com/ads/library/?id=987654321"

    # Kiểm tra static method AdNormalizer.normalize_scrape_js_item
    ad2 = AdNormalizer.normalize_scrape_js_item(raw_item)
    assert ad2.id == ad.id

    # Test carousel detection
    carousel_item = {
        "ad_id": "223344",
        "format": "MULTI_IMAGES",
        "images": ["https://cdn.brand.vn/img1.jpg", "https://cdn.brand.vn/img2.jpg"],
        "card_count": 2,
    }
    ad_carousel = map_scrape_js_item_to_ad_creative(carousel_item)
    assert ad_carousel.media_type == "carousel"
    assert len(ad_carousel.media_urls) == 2

    # Test image detection
    image_item = {
        "ad_id": "334455",
        "format": "IMAGE",
        "images": ["https://cdn.brand.vn/single.jpg"],
    }
    ad_image = map_scrape_js_item_to_ad_creative(image_item)
    assert ad_image.media_type == "image"

    # Test text_only detection
    text_item = {
        "ad_id": "445566",
        "body": "Chỉ có bài viết text",
    }
    ad_text = map_scrape_js_item_to_ad_creative(text_item)
    assert ad_text.media_type == "text_only"


# ==============================================================================
# TEST 12: NODE SCRAPER SUBPROCESS EXECUTION & MOCK
# ==============================================================================

def test_node_scraper_subprocess_success(monkeypatch, tmp_path):
    """Giả lập subprocess node scrape.js chạy thành công và tạo JSON."""
    fake_payload = {
        "query": {"q": "kem dưỡng", "country": "VN"},
        "scraped_at": "2026-11-05T00:00:00Z",
        "total": 1,
        "ads": [{
            "ad_id": "node_999",
            "page_name": "Node Cosmetics",
            "body": "Kem chống nắng kiềm dầu",
            "start_date": "2026-04-10",
            "days_running": 20,
            "variants": 5,
            "format": "IMAGE",
            "images": ["https://cdn.example.com/kcn.jpg"],
        }]
    }

    class DummyProc:
        def __init__(self, cmd):
            self.pid = 99999
            self.returncode = 0
            out_idx = cmd.index("--out")
            self.out_path = Path(cmd[out_idx + 1])

        def communicate(self, timeout=None):
            self.out_path.write_text(json.dumps(fake_payload, ensure_ascii=False), encoding="utf-8")
            return ("OK 1 ads -> out.json", "")

        def poll(self):
            return 0

    monkeypatch.setattr("shutil.which", lambda cmd: "C:\\Program Files\\nodejs\\node.exe")
    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kwargs: DummyProc(cmd))

    fake_script = tmp_path / "scrape.js"
    fake_script.write_text("// dummy", encoding="utf-8")

    ads = run_node_scrape_subprocess("kem dưỡng", limit=10, scrape_script_path=fake_script)
    assert len(ads) == 1
    assert ads[0].id == "node_999"
    assert ads[0].page_name == "Node Cosmetics"
    assert ads[0].days_active == 20
    assert ads[0].variant_count == 5


# ==============================================================================
# TEST 13: NODE SCRAPER TIMEOUT & PROCESS HYGIENE
# ==============================================================================

def test_node_scraper_timeout_and_process_hygiene(monkeypatch, tmp_path):
    """Khi subprocess bị TimeoutExpired, phải kích hoạt kill_process_tree và ném TimeoutError."""
    import subprocess

    killed_pids = []
    monkeypatch.setattr("scripts.meta_ads_scout.kill_process_tree", lambda pid: killed_pids.append(pid))

    class TimeoutProc:
        def __init__(self, cmd):
            self.pid = 12345
            self.returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="node scrape.js", timeout=timeout)

        def poll(self):
            return None

    monkeypatch.setattr("shutil.which", lambda cmd: "node")
    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kwargs: TimeoutProc(cmd))

    fake_script = tmp_path / "scrape.js"
    fake_script.write_text("// dummy", encoding="utf-8")

    with pytest.raises(TimeoutError) as exc_info:
        run_node_scrape_subprocess("sơ sinh", timeout=2, scrape_script_path=fake_script)

    assert "bị timeout sau 2 giây" in str(exc_info.value)
    assert 12345 in killed_pids


# ==============================================================================
# TEST 14: MULTI-TIER ENGINE INTEGRATION & FALLBACK
# ==============================================================================

def test_engine_tier1_node_scraper_and_fallback(monkeypatch):
    """Engine ưu tiên Tier 1 (Node Scraper). Nếu Node Scraper lỗi, graceful fallback sang Tier 2 (Playwright)."""
    engine = MetaScraperEngine()
    fake_node_ad = AdNormalizer.normalize_node({
        "id": "node_winner_1",
        "page_name": "Top Brand",
        "start_date": "2026-04-01",
        "body_text": "Node scraper victory",
    })
    fake_pw_ad = AdNormalizer.normalize_node({
        "id": "pw_winner_2",
        "page_name": "Fallback Brand",
        "start_date": "2026-04-01",
        "body_text": "Playwright fallback victory",
    })

    # Case 1: Node scraper thành công -> engine_used == "tier1_node_scraper"
    monkeypatch.setattr(engine, "_fetch_tier1_node", lambda **kwargs: [fake_node_ad])
    ads1, cov1, tier1 = engine.fetch("sơ sinh", use_seed_only=False)
    assert len(ads1) == 1
    assert ads1[0].id == "node_winner_1"
    assert tier1 == "tier1_node_scraper"

    # Case 2: Node scraper thất bại -> Fallback sang Playwright Python
    monkeypatch.setattr(engine, "_fetch_tier1_node", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Node not available")))
    monkeypatch.setattr(engine, "_fetch_tier1_playwright", lambda url, limit: [fake_pw_ad])
    ads2, cov2, tier2 = engine.fetch("sơ sinh", use_seed_only=False)
    assert len(ads2) == 1
    assert ads2[0].id == "pw_winner_2"
    assert tier2 == "tier1_playwright_live"


# ==============================================================================
# TEST 15: AUTOLINK URLS & XSS PREVENTION
# ==============================================================================

def test_autolink_urls_and_xss_prevention():
    """Kiểm tra nhận diện hyperlink an toàn, bóc tách dấu câu, và chống XSS."""
    # 1. URL có scheme https://
    text1 = "Sản phẩm tốt ghé https://s.shopee.vn/123xyz nhé!"
    linked1 = autolink_urls(text1)
    assert '<a href="https://s.shopee.vn/123xyz" target="_blank" rel="noopener noreferrer" class="post-url-link">https://s.shopee.vn/123xyz</a>' in linked1
    assert linked1.endswith(" nhé!")

    # 2. Domain không có scheme (shopee.vn, zalo.me)
    text2 = "Mua ngay tại shopee.vn/deal-hot hoặc zalo.me/0988776655."
    linked2 = autolink_urls(text2)
    assert 'href="https://shopee.vn/deal-hot"' in linked2
    assert 'href="https://zalo.me/0988776655"' in linked2
    assert linked2.endswith(".</a>") is False
    assert linked2.endswith(".")

    # 3. Viết tắt như TP.HCM không bị nhận diện nhầm thành link
    text3 = "Giao hàng hỏa tốc tại TP.HCM trong 2h."
    linked3 = autolink_urls(text3)
    assert '<a href=' not in linked3
    assert "TP.HCM" in linked3

    # 4. Chống XSS trong URL và văn bản
    text4 = "<script>alert('xss')</script> ghé https://example.com/test?a=1&b=2"
    linked4 = autolink_urls(text4)
    assert "<script>" not in linked4
    assert "&lt;script&gt;" in linked4
    assert 'href="https://example.com/test?a=1&amp;b=2"' in linked4


# ==============================================================================
# TEST 16: HTML DASHBOARD MEDIA INTERACTION & NO-REFERRER
# ==============================================================================

def test_html_dashboard_media_interaction_and_no_referrer(tmp_path: Path):
    """Kiểm tra Dashboard HTML có meta no-referrer, referrerpolicy, video player, carousel và link_url."""
    video_ad = AdCreative(
        id="vid1",
        ad_archive_id="vid1",
        page_id="pvid",
        page_name="Video Brand",
        page_profile_picture_url="https://fbcdn.net/avatar.jpg",
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=20,
        variant_count=2,
        publisher_platforms=["facebook"],
        body_text="Video ad demo: ghé https://shopee.vn/vid để mua!",
        title="Tiêu đề video",
        caption="Caption",
        cta_text="Mua ngay",
        link_url="https://shopee.vn/landing-page",
        media_type="video",
        media_urls=["https://video.fbcdn.net/clip.mp4", "https://fbcdn.net/poster.jpg"],
        ad_snapshot_url="https://facebook.com/ads/library/?id=vid1",
    )

    carousel_ad = AdCreative(
        id="car1",
        ad_archive_id="car1",
        page_id="pcar",
        page_name="Carousel Brand",
        page_profile_picture_url="https://fbcdn.net/avatar2.jpg",
        start_date="2026-10-05",
        end_date=None,
        is_active=True,
        days_active=10,
        variant_count=1,
        publisher_platforms=["instagram"],
        body_text="Bộ sưu tập sơ sinh cho bé.",
        title="BST Sơ sinh",
        caption="BST",
        cta_text="Xem ngay",
        link_url=None,
        media_type="carousel",
        media_urls=["https://fbcdn.net/img1.jpg", "https://fbcdn.net/img2.jpg", "https://fbcdn.net/img3.jpg"],
        ad_snapshot_url="https://facebook.com/ads/library/?id=car1",
    )

    report = ScoutReport(
        keyword="sơ sinh",
        country="VN",
        scouted_at="2026-11-05 10:00:00",
        target_url="https://facebook.com/ads/library/?q=test",
        total_found=2,
        coverage=CoverageMetrics(2, 2, 0, True, []),
        ads=[video_ad, carousel_ad],
        analyses={},
    )

    exporter = ReportExporter(tmp_path)
    html_file = exporter.export_html(report, min_days=14)
    content = html_file.read_text(encoding="utf-8")

    # 1. Meta no-referrer trong thẻ head
    assert '<meta name="referrer" content="no-referrer">' in content

    # 2. Thuộc tính referrerpolicy="no-referrer" trên media
    assert 'referrerpolicy="no-referrer"' in content

    # 3. Video player và nút mở video tab mới
    assert '<video controls playsinline preload="metadata" referrerpolicy="no-referrer"' in content
    assert '<source src="https://video.fbcdn.net/clip.mp4" type="video/mp4">' in content
    assert 'Mở Video tab mới ↗' in content

    # 4. Carousel thumbnail strip và hàm switchCarouselImage
    assert 'carousel-thumbnails-strip' in content
    assert 'switchCarouselImage(this' in content
    assert 'Album Carousel (3 ảnh)' in content

    # 5. Link đích nổi bật (link_url)
    assert '🔗 Link đích:' in content
    assert 'href="https://shopee.vn/landing-page"' in content

    # 6. Lightbox phóng to và ESC listener
    assert 'id="mediaLightbox"' in content
    assert 'openMediaLightbox' in content
    assert 'closeMediaLightbox' in content
    assert "handleMediaError" in content


def test_url_builder_loose_and_sort_modes():
    """Kiểm tra build_meta_ads_url với cờ --loose và các mode sort mới."""
    # 1. Mode loose: không bọc ngoặc kép, search_type=keyword_unordered
    url_loose = build_meta_ads_url("sữa hạt dinh dưỡng", loose=True)
    assert "search_type=keyword_unordered" in url_loose
    assert "%22" not in url_loose

    # 2. Sort new và relevance
    url_new = build_meta_ads_url("sữa hạt", sort="new")
    assert "sort_data%5Bmode%5D=relevancy_monthly_grouped" in url_new or "sort_data[mode]=relevancy_monthly_grouped" in url_new

    url_rel = build_meta_ads_url("sữa hạt", sort="relevance")
    assert "sort_data%5Bmode%5D=relevancy_monthly_grouped" in url_rel or "sort_data[mode]=relevancy_monthly_grouped" in url_rel


def test_cli_parser_new_flags():
    """Kiểm tra các cờ CLI mới: --sort, --loose, --scrape-lp, --download-media."""
    parser = build_cli_parser()
    args = parser.parse_args([
        "--keyword", "sữa hạt",
        "--sort", "new",
        "--loose",
        "--scrape-lp",
        "--download-media",
    ])
    assert args.sort == "new"
    assert args.loose is True
    assert args.scrape_lp is True
    assert args.download_media is True


def test_html_dashboard_landing_page_insights_and_local_media(tmp_path: Path):
    """Kiểm tra Dashboard HTML hiển thị Landing Page Insights và Local Media Offline."""
    ad_with_lp = AdCreative(
        id="lp1",
        ad_archive_id="arc_lp1",
        page_id="112233",
        page_name="Ovisure Gold",
        page_profile_picture_url=None,
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=35,
        variant_count=8,
        publisher_platforms=["facebook"],
        body_text="Sữa hạt Ovisure Gold chính hãng.",
        title="Ovisure Gold",
        caption="ovisuregold.vn",
        cta_text="Đặt hàng ngay",
        link_url="https://ovisuregold.vn/landing",
        media_type="image",
        media_urls=["https://fbcdn.net/sample.jpg"],
        ad_snapshot_url="https://facebook.com/ads/library/?id=arc_lp1",
        landing_page_data={
            "title": "Ovisure Gold - Sữa hạt chuyên biệt cho xương khớp",
            "prices": ["550.000đ", "990.000đ"],
            "offers": ["Mua 2 tặng 1", "Miễn phí vận chuyển toàn quốc"],
            "has_phone_form": True,
            "buttons": ["Đặt hàng ngay", "Nhận ưu đãi"],
        },
        local_media_paths=[str(tmp_path / "creative" / "sample_img.jpg")],
    )

    report = ScoutReport(
        keyword="sữa hạt",
        country="VN",
        scouted_at="2026-11-06 12:00:00",
        target_url="https://facebook.com/ads/library/?q=test",
        total_found=1,
        coverage=CoverageMetrics(1, 1, 0, True, []),
        ads=[ad_with_lp],
        analyses={},
    )

    exporter = ReportExporter(tmp_path)
    html_file = exporter.export_html(report, min_days=14)
    content = html_file.read_text(encoding="utf-8")

    # Kiểm tra Landing Page Spy box
    assert "Landing Page Spy Insights" in content
    assert "Chốt đơn Form SĐT" in content
    assert "550.000đ" in content
    assert "Mua 2 tặng 1" in content
    assert "ad-lp-box" in content


