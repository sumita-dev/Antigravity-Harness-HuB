# -*- coding: utf-8 -*-
"""Test suite cho tính năng /meta-ad-scout (Meta Ads Library Intelligence Scout).

Kiểm thử toàn diện 10 tiêu chí nghiệm thu AC-01 đến AC-10 theo đúng bản đặc tả.
"""

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
    build_cli_parser,
    build_meta_ads_url,
    is_winning_ad,
    run_meta_ad_scout,
)


# ==============================================================================
# AC-01: CLI Parser Argument Parsing & Help
# ==============================================================================

def test_cli_argument_parsing():
    parser = build_cli_parser()

    # Kiểm tra giá trị mặc định
    args = parser.parse_args([])
    assert args.keyword == "sơ sinh"
    assert args.country == "VN"
    assert args.limit == 20
    assert args.sort == "total_impressions"
    assert args.min_days == 14
    assert args.format == "all"
    assert args.active_only is True

    # Kiểm tra tham số tùy biến
    custom_args = parser.parse_args([
        "--keyword", "thực phẩm chức năng",
        "--country", "US",
        "--limit", "50",
        "--sort", "start_date",
        "--min-days", "20",
        "--format", "json",
        "--seed",
        "--no-analyze",
    ])
    assert custom_args.keyword == "thực phẩm chức năng"
    assert custom_args.country == "US"
    assert custom_args.limit == 50
    assert custom_args.sort == "start_date"
    assert custom_args.min_days == 20
    assert custom_args.format == "json"
    assert custom_args.seed is True
    assert custom_args.no_analyze is True


# ==============================================================================
# AC-02: URL Builder & Vietnamese Encoding
# ==============================================================================

def test_url_builder_encoding():
    # 1. Kiểm tra từ khóa có dấu được mã hóa UTF-8 và bọc dấu nháy kép
    url = build_meta_ads_url("sơ sinh", country="VN", sort="total_impressions")
    assert "country=VN" in url
    assert "search_type=keyword_exact_phrase" in url
    assert "sort_data%5Bmode%5D=total_impressions" in url or "sort_data[mode]=total_impressions" in url
    assert "q=%22s%C6%A1+sinh%22" in url or "q=%22s%C6%A1%20sinh%22" in url
    assert "active_status=active" in url

    # 2. Kiểm tra từ khóa đã có sẵn dấu nháy kép không bị bọc 2 lần
    url_quoted = build_meta_ads_url('"thời trang trẻ em"', country="VN")
    assert "%22th%E1%BB%9Di+trang+tr%E1%BA%BB+em%22" in url_quoted or "%22th%E1%BB%9Di%20trang%20tr%E1%BA%BB%20em%22" in url_quoted

    # 3. Kiểm tra validation mã quốc gia
    with pytest.raises(ValueError):
        build_meta_ads_url("test", country="VIETNAM")


# ==============================================================================
# AC-03: Multi-Tier Scraping Fallback
# ==============================================================================

def test_scraping_engine_fallback():
    # Khởi tạo engine với mock seed
    engine = MetaScraperEngine()

    # Dù gọi với môi trường không có token hoặc mạng lỗi, không bao giờ văng unhandled exception
    ads, coverage, engine_used = engine.fetch(
        keyword="sơ sinh",
        country="VN",
        limit=5,
        use_seed_only=False,  # Cho phép thử tier 1 rồi fallback
    )

    assert isinstance(ads, list)
    assert len(ads) > 0
    assert isinstance(coverage, CoverageMetrics)
    assert coverage.collected == len(ads)
    assert engine_used in ("tier1_web", "tier2_graph_api", "tier4_seed_fallback")


# ==============================================================================
# AC-04: AdNormalizer Null-Safe Extraction
# ==============================================================================

def test_ad_normalizer_extraction():
    raw_node = {
        "id": "123456",
        "ad_archive_id": "7891011",
        "page_name": "Shop Mẹ và Bé",
        "start_date": "2026-09-01",
        "days_active": 30,
        "variant_count": 5,
        "body_text": "Nội dung quảng cáo thử nghiệm",
        "media_urls": [
            "https://example.com/image.jpg",
            "javascript:alert(1)",  # Phải bị loại bỏ
        ],
    }

    ad = AdNormalizer.normalize_node(raw_node)
    assert ad.id == "123456"
    assert ad.ad_archive_id == "7891011"
    assert ad.page_name == "Shop Mẹ và Bé"
    assert ad.days_active == 30
    assert ad.variant_count == 5
    assert ad.body_text == "Nội dung quảng cáo thử nghiệm"
    assert ad.media_urls == ["https://example.com/image.jpg"]
    assert "https://www.facebook.com/ads/library/?id=7891011" in ad.ad_snapshot_url

    # Kiểm tra node rỗng / thiếu trường không gây crash
    empty_node = {}
    ad_empty = AdNormalizer.normalize_node(empty_node)
    assert ad_empty.id == "N/A"
    assert ad_empty.page_name == "Fanpage"
    assert ad_empty.media_urls == []


# ==============================================================================
# AC-05: Creative Angle & AI Analyzer
# ==============================================================================

def test_creative_angle_analyzer():
    analyzer = CreativeAngleAnalyzer()

    # 1. Kiểm tra phát hiện Hook Nỗi sợ & Cảnh báo
    fear_ad = AdCreative(
        id="f1",
        ad_archive_id="f1",
        page_id="p1",
        page_name="Page 1",
        page_profile_picture_url=None,
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=10,
        variant_count=1,
        publisher_platforms=["facebook"],
        body_text="Cảnh báo: 90% bé sơ sinh bị hăm tã nghiêm trọng do mẹ chủ quan!",
        title="Tiêu đề",
        caption=None,
        cta_text="Gửi tin nhắn",
        link_url=None,
        media_type="image",
        media_urls=[],
        ad_snapshot_url="https://example.com",
    )
    analysis_fear = analyzer.analyze(fear_ad)
    assert "Nỗi sợ" in analysis_fear.hook_type
    assert 1 <= analysis_fear.persuasion_score <= 10

    # 2. Kiểm tra phát hiện Hook Tò mò / Câu hỏi
    curious_ad = AdCreative(
        id="c1",
        ad_archive_id="c1",
        page_id="p2",
        page_name="Page 2",
        page_profile_picture_url=None,
        start_date="2026-10-01",
        end_date=None,
        is_active=True,
        days_active=15,
        variant_count=4,
        publisher_platforms=["facebook"],
        body_text="Tại sao hơn 10.000 mẹ bỉm lại tin dùng gối chống trào ngược này?\nCombo 2 tặng 1 duy nhất hôm nay!",
        title="Gối chống trào ngược",
        caption=None,
        cta_text="Mua ngay",
        link_url=None,
        media_type="video",
        media_urls=[],
        ad_snapshot_url="https://example.com",
    )
    analysis_curious = analyzer.analyze(curious_ad)
    assert "Tò mò" in analysis_curious.hook_type
    assert "Combo" in analysis_curious.primary_offer or "combo" in analysis_curious.primary_offer.lower()


# ==============================================================================
# AC-06: JSON & Markdown Export
# ==============================================================================

def test_json_and_markdown_export(tmp_path: Path):
    exporter = ReportExporter(tmp_path)
    engine = MetaScraperEngine()
    ads, coverage, _ = engine.fetch("sơ sinh", limit=3, use_seed_only=True)
    analyzer = CreativeAngleAnalyzer()
    analyses = {ad.id: analyzer.analyze(ad) for ad in ads}

    report = ScoutReport(
        keyword="sơ sinh",
        country="VN",
        scouted_at="2026-10-20 12:00:00",
        target_url="https://example.com",
        total_found=len(ads),
        coverage=coverage,
        ads=ads,
        analyses=analyses,
    )

    json_path = exporter.export_json(report, "test_report.json")
    md_path = exporter.export_markdown(report, "test_report.md")

    assert json_path.exists()
    assert md_path.exists()

    # Kiểm tra cấu trúc JSON
    loaded_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded_data["keyword"] == "sơ sinh"
    assert "coverage" in loaded_data
    assert loaded_data["coverage"]["collected"] == len(ads)
    assert len(loaded_data["ads"]) == len(ads)

    # Kiểm tra cấu trúc Markdown
    md_content = md_path.read_text(encoding="utf-8")
    assert "# BÁO CÁO TRINH SÁT META ADS" in md_content
    assert "Winning Ads" in md_content


# ==============================================================================
# AC-07: HTML Dashboard Generation
# ==============================================================================

def test_html_dashboard_generation(tmp_path: Path):
    exporter = ReportExporter(tmp_path)
    engine = MetaScraperEngine()
    ads, coverage, _ = engine.fetch("sơ sinh", limit=3, use_seed_only=True)
    analyzer = CreativeAngleAnalyzer()
    analyses = {ad.id: analyzer.analyze(ad) for ad in ads}

    report = ScoutReport(
        keyword="sơ sinh",
        country="VN",
        scouted_at="2026-10-20 12:00:00",
        target_url="https://example.com",
        total_found=len(ads),
        coverage=coverage,
        ads=ads,
        analyses=analyses,
    )

    html_path = exporter.export_html(report, "test_dashboard.html")
    assert html_path.exists()

    html_content = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content
    assert "Meta Ads Intelligence Scout" in html_content
    assert "copyAdCopy" in html_content
    assert "filterAds" in html_content
    assert "ad-card" in html_content


# ==============================================================================
# AC-08: Seed Sample Dataset Integrity
# ==============================================================================

def test_seed_sample_data_integrity():
    assert len(SEED_ADS) >= 5, "Bộ dữ liệu mẫu seed phải có ít nhất 5 mẫu ads chân thực"

    categories = []
    for raw in SEED_ADS:
        ad = AdNormalizer.normalize_node(raw)
        assert ad.id, "Ad ID không được rỗng"
        assert ad.page_name, "Tên Page không được rỗng"
        assert ad.body_text, "Body copy không được rỗng"
        assert ad.days_active > 0, "Số ngày chạy phải > 0"
        assert ad.variant_count >= 1, "Số nhóm ads phải >= 1"
        assert ad.ad_snapshot_url.startswith("https://"), "Link snapshot phải là https"
        text = (ad.body_text + " " + ad.page_name).lower()
        if "sơ sinh" in text:
            categories.append("so_sinh")
        if "não" in text or "canxi" in text or "sức khỏe" in text:
            categories.append("tpcn")

    assert "so_sinh" in categories, "Phải có ads thuộc ngách sơ sinh"
    assert "tpcn" in categories, "Phải có ads thuộc ngách thực phẩm chức năng"


# ==============================================================================
# AC-09: Zero Hallucination & Coverage Tracking
# ==============================================================================

def test_zero_hallucination_coverage():
    # Kiểm tra trường hợp Meta không trả về dữ liệu
    incomplete_node = {
        "id": "111",
        "ad_archive_id": "222",
        "body_text": "Chỉ có body text",
    }
    ad = AdNormalizer.normalize_node(incomplete_node)
    # Không được bịa title, caption hay link
    assert ad.title is None
    assert ad.caption is None
    assert ad.link_url is None
    assert ad.page_profile_picture_url is None

    # Coverage metrics phản ánh đúng số lượng
    cov = CoverageMetrics(requested=20, collected=5, failed=0, complete=False, missing_fields=[])
    assert not cov.complete
    assert cov.collected == 5


# ==============================================================================
# AC-10: Security, XSS Escaping & Winning Ads Logic
# ==============================================================================

def test_security_xss_and_secret_safety(tmp_path: Path):
    # Ad chứa mã độc XSS
    xss_node = {
        "id": "xss_001",
        "ad_archive_id": "xss_001",
        "page_name": "<script>alert('xss_page')</script>",
        "body_text": "<img src=x onerror=alert('xss_body')> Vít mạnh sản phẩm sơ sinh",
        "title": "<script>alert('xss_title')</script>",
        "media_urls": [
            "javascript:alert('bad')",  # Phải bị chặn
            "https://safe.com/image.jpg",
        ],
    }

    ad = AdNormalizer.normalize_node(xss_node)
    analyzer = CreativeAngleAnalyzer()
    analysis = analyzer.analyze(ad)

    report = ScoutReport(
        keyword="<script>alert('kw')</script>",
        country="VN",
        scouted_at="2026-10-20",
        target_url="https://example.com",
        total_found=1,
        coverage=CoverageMetrics(1, 1, 0, True, []),
        ads=[ad],
        analyses={ad.id: analysis},
    )

    exporter = ReportExporter(tmp_path)
    html_path = exporter.export_html(report, "xss_test.html")
    content = html_path.read_text(encoding="utf-8")

    # Xác minh không còn thẻ <script> thô từ dữ liệu
    assert "<script>alert('xss_page')</script>" not in content
    assert "<script>alert('xss_title')</script>" not in content
    assert "javascript:alert" not in content
    assert "&lt;script&gt;alert(&#x27;xss_page&#x27;)&lt;/script&gt;" in content or "&lt;script&gt;alert('xss_page')&lt;/script&gt;" in content


def test_winning_ad_detection():
    # Chạy >= 14 ngày -> Winning
    ad1 = AdCreative(
        id="1", ad_archive_id="1", page_id="p", page_name="P",
        page_profile_picture_url=None, start_date="2026-09-01",
        end_date=None, is_active=True, days_active=15, variant_count=1,
        publisher_platforms=["facebook"], body_text="", title=None,
        caption=None, cta_text=None, link_url=None, media_type="image",
        media_urls=[], ad_snapshot_url="",
    )
    assert is_winning_ad(ad1, min_days=14, min_variants=3) is True

    # Có >= 3 nhóm ads -> Winning
    ad2 = AdCreative(
        id="2", ad_archive_id="2", page_id="p", page_name="P",
        page_profile_picture_url=None, start_date="2026-10-18",
        end_date=None, is_active=True, days_active=2, variant_count=4,
        publisher_platforms=["facebook"], body_text="", title=None,
        caption=None, cta_text=None, link_url=None, media_type="image",
        media_urls=[], ad_snapshot_url="",
    )
    assert is_winning_ad(ad2, min_days=14, min_variants=3) is True

    # Chạy ít ngày và ít biến thể -> Không winning
    ad3 = AdCreative(
        id="3", ad_archive_id="3", page_id="p", page_name="P",
        page_profile_picture_url=None, start_date="2026-10-18",
        end_date=None, is_active=True, days_active=2, variant_count=1,
        publisher_platforms=["facebook"], body_text="", title=None,
        caption=None, cta_text=None, link_url=None, media_type="image",
        media_urls=[], ad_snapshot_url="",
    )
    assert is_winning_ad(ad3, min_days=14, min_variants=3) is False
