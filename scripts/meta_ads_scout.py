#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Meta Ads Library Competitor Intelligence & Creative Angle Scout.

Trinh sát đối thủ Meta Ads Library theo từ khóa chủ đề, bóc tách creative vít mạnh,
phân tích Hook/Offer/Angle bằng AI/Heuristics và xuất Dashboard HTML / JSON / Markdown.
"""

from __future__ import annotations

import argparse
import dataclasses
from dataclasses import dataclass, field
import datetime
import html
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional
import urllib.parse

# Cấu hình logging
logger = logging.getLogger("meta_ads_scout")


# ==============================================================================
# 1. DATA MODELS & SCHEMAS
# ==============================================================================

@dataclass
class AdCreative:
    """Mô hình dữ liệu mẫu quảng cáo Meta Ads."""
    id: str
    ad_archive_id: str
    page_id: str
    page_name: str
    page_profile_picture_url: Optional[str]
    start_date: str
    end_date: Optional[str]
    is_active: bool
    days_active: int
    variant_count: int
    publisher_platforms: List[str]
    body_text: str
    title: Optional[str]
    caption: Optional[str]
    cta_text: Optional[str]
    link_url: Optional[str]
    media_type: str  # 'image' | 'video' | 'carousel' | 'text_only'
    media_urls: List[str]
    ad_snapshot_url: str
    landing_page_data: Optional[Dict[str, Any]] = None
    local_media_paths: List[str] = field(default_factory=list)


@dataclass
class CreativeAnalysis:
    """Phân tích góc tiếp cận và tâm lý của mẫu quảng cáo."""
    hook_type: str
    hook_text: str
    primary_offer: str
    marketing_angle: str
    target_audience: str
    pain_points: List[str]
    persuasion_score: int  # Thang điểm 1 - 10
    recommendations: List[str]


@dataclass
class CoverageMetrics:
    """Chỉ số bao phủ và tính trung thực của việc cào dữ liệu."""
    requested: int
    collected: int
    failed: int
    complete: bool
    missing_fields: List[str]


@dataclass
class ScoutReport:
    """Báo cáo tổng hợp trinh sát Meta Ads."""
    keyword: str
    country: str
    scouted_at: str
    target_url: str
    total_found: int
    coverage: CoverageMetrics
    ads: List[AdCreative]
    analyses: Dict[str, CreativeAnalysis]


# ==============================================================================
# 2. URL BUILDER & ENCODING
# ==============================================================================

def build_meta_ads_url(
    keyword: str,
    country: str = "VN",
    sort: str = "total_impressions",
    active_only: bool = True,
    media_type: str = "all",
    loose: bool = False,
) -> str:
    """Tạo URL truy vấn Meta Ads Library chính xác 100%.

    Mã hóa UTF-8 từ khóa có dấu, kèm dấu nháy kép \"\" để kích hoạt
    chế độ tìm kiếm chính xác keyword_exact_phrase (trừ khi bật loose).
    """
    cleaned_country = country.strip().upper()
    if not re.match(r"^[A-Z]{2}$", cleaned_country):
        raise ValueError(f"Mã quốc gia không hợp lệ (phải là 2 ký tự ISO Alpha-2): {country}")

    raw_kw = keyword.strip()
    if loose:
        exact_kw = raw_kw.replace('"', '')
        search_type = "keyword_unordered"
    else:
        # Bọc từ khóa trong dấu nháy kép cho tìm kiếm chính xác
        if not (raw_kw.startswith('"') and raw_kw.endswith('"')):
            exact_kw = f'"{raw_kw}"'
        else:
            exact_kw = raw_kw
        search_type = "keyword_exact_phrase"

    quoted_query = urllib.parse.quote_plus(exact_kw)
    active_val = "active" if active_only else "all"

    # Chuẩn hóa sort mode
    if sort in ("new", "relevance"):
        sort_mode = "relevancy_monthly_grouped"
    else:
        sort_mode = sort

    # Xây dựng URL đúng chuẩn Meta Ads Library
    base_url = "https://www.facebook.com/ads/library/"
    params = [
        f"active_status={active_val}",
        "ad_type=all",
        f"country={cleaned_country}",
        "is_targeted_country=false",
        f"media_type={media_type}",
        f"q={quoted_query}",
        f"search_type={search_type}",
        "sort_data[direction]=desc",
        f"sort_data[mode]={sort_mode}",
    ]
    return f"{base_url}?{'&'.join(params)}"


# ==============================================================================
# 3. WINNING ADS LOGIC
# ==============================================================================

def is_winning_ad(ad: AdCreative, min_days: int = 14, min_variants: int = 3) -> bool:
    """Phát hiện winning ad (chạy liên tục >= min_days hoặc có >= min_variants nhóm ads)."""
    return ad.days_active >= min_days or ad.variant_count >= min_variants


# ==============================================================================
# 4. RICH SEED SAMPLE DATA (AC-08 & OFFLINE FALLBACK)
# ==============================================================================

SEED_ADS: List[Dict[str, Any]] = [
    {
        "id": "ad_seed_001",
        "ad_archive_id": "892019283019201",
        "page_id": "104928192019",
        "page_name": "Moony Baby Việt Nam",
        "page_profile_picture_url": "https://images.unsplash.com/photo-1555252333-9f8e92e65df9?w=100&auto=format&fit=crop&q=80",
        "start_date": "2026-09-12",
        "end_date": None,
        "is_active": True,
        "days_active": 38,
        "variant_count": 6,
        "publisher_platforms": ["facebook", "instagram", "messenger"],
        "body_text": (
            "🚨 Mẹ có biết 90% bé sơ sinh bị hăm tã là do chọn sai chất liệu tã trong tháng đầu?\n\n"
            "Làn da của con non nớt mỏng manh, chỉ một vết hằn đỏ cũng khiến con quấy khóc cả đêm.\n"
            "Tã dán Moony Natural bông hữu cơ Nhật Bản với sợi bông Plant-based siêu mềm mại, "
            "thấm hút tức thì gấp 3 lần, giúp mông bé luôn khô thoáng tới 12 giờ.\n\n"
            "🎁 ƯU ĐÃI ĐẶC BIỆT THÁNG NÀY:\n"
            "- Combo 3 bịch tặng ngay 1 chăn ủ xô Muslin cao cấp trị giá 180k.\n"
            "- Freeship toàn quốc khi đặt mua trực tiếp hôm nay!\n"
            "👉 Nhấp [Gửi Tin Nhắn] để nhận tư vấn size chuẩn cho bé yêu!"
        ),
        "title": "Moony Natural Bông Hữu Cơ - Êm Ái Cho Làn Da Sơ Sinh",
        "caption": "moony.vn/khuyen-mai-so-sinh",
        "cta_text": "Gửi tin nhắn",
        "link_url": "https://moony.vn/khuyen-mai-so-sinh",
        "media_type": "image",
        "media_urls": [
            "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=800&auto=format&fit=crop&q=80"
        ],
        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=892019283019201",
    },
    {
        "id": "ad_seed_002",
        "ad_archive_id": "918201928310928",
        "page_id": "201928102931",
        "page_name": "Babymoov Vietnam Official",
        "page_profile_picture_url": "https://images.unsplash.com/photo-1544717305-2782549b5136?w=100&auto=format&fit=crop&q=80",
        "start_date": "2026-09-28",
        "end_date": None,
        "is_active": True,
        "days_active": 22,
        "variant_count": 4,
        "publisher_platforms": ["facebook", "instagram"],
        "body_text": (
            "❓ Con hay ọc sữa, nôn trớ sau bú khiến mẹ thức trắng đêm lo lắng?\n\n"
            "Trào ngược dạ dày thực quản là nỗi ám ảnh lớn nhất của các mẹ bỉm giai đoạn sơ sinh 0-6 tháng. "
            "Gối chống trào ngược Babymoov chuẩn công thái học với góc nghiêng lý tưởng 15 độ được các chuyên gia "
            "nhi khoa Pháp khuyến nghị, giúp định hình cột sống và giảm ngay 85% hiện tượng ọc sữa.\n\n"
            "🔥 FLASH SALE TUẦN LỄ VÀNG:\n"
            "- Giảm 35% duy nhất 50 suất đầu tiên trong tuần.\n"
            "- Tặng kèm 01 vỏ gối cotton organic kháng khuẩn thay thế.\n"
            "Nhấn [Mua ngay] để bảo vệ giấc ngủ ngon trọn vẹn của con!"
        ),
        "title": "Gối Chống Trào Ngược Babymoov - Góc Nghiêng 15 Độ Y Khoa",
        "caption": "babymoov.vn/goi-chong-trao-nguoc",
        "cta_text": "Mua ngay",
        "link_url": "https://babymoov.vn/goi-chong-trao-nguoc",
        "media_type": "video",
        "media_urls": [
            "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800&auto=format&fit=crop&q=80"
        ],
        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=918201928310928",
    },
    {
        "id": "ad_seed_003",
        "ad_archive_id": "781920192830112",
        "page_id": "319201928102",
        "page_name": "D-nee Baby Care Official",
        "page_profile_picture_url": "https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?w=100&auto=format&fit=crop&q=80",
        "start_date": "2026-10-04",
        "end_date": None,
        "is_active": True,
        "days_active": 16,
        "variant_count": 3,
        "publisher_platforms": ["facebook", "messenger"],
        "body_text": (
            "⚠️ Cảnh báo: Da trẻ sơ sinh mỏng gấp 5 lần người lớn - Đừng giặt đồ con bằng xà phòng thông thường!\n\n"
            "Hóa chất tẩy rửa công nghiệp là nguyên nhân âm thầm gây viêm da cơ địa và ngứa ngáy cho trẻ.\n"
            "Nước giặt xả D-nee Organic chiết xuất từ hoa cúc thiên nhiên, độ pH trung tính đạt chứng nhận Dermatologically Tested, "
            "vừa làm sạch vết sữa ố vàng vừa giữ sợi vải mềm mịn như vòng tay mẹ.\n\n"
            "💥 MUA CAN 3000ML TẶNG TÚI 600ML TIẾT KIỆM:\n"
            "- Miễn phí vận chuyển tận nhà.\n"
            "- Cam kết 100% hàng nhập khẩu chính ngạch Thái Lan, đền gấp 10 nếu phát hiện hàng giả.\n"
            "Bấm [Tìm hiểu thêm] để nhận mã giảm 50k ngay hôm nay!"
        ),
        "title": "Nước Giặt Xả Sơ Sinh D-nee Organic - An Toàn Tuyệt Đối",
        "caption": "dnee.vn/chinh-hang",
        "cta_text": "Tìm hiểu thêm",
        "link_url": "https://dnee.vn/chinh-hang",
        "media_type": "image",
        "media_urls": [
            "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800&auto=format&fit=crop&q=80"
        ],
        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=781920192830112",
    },
    {
        "id": "ad_seed_004",
        "ad_archive_id": "671928192019283",
        "page_id": "491820192819",
        "page_name": "Healthy Care Australia Store",
        "page_profile_picture_url": "https://images.unsplash.com/photo-1584017911766-d451b3d0e843?w=100&auto=format&fit=crop&q=80",
        "start_date": "2026-09-05",
        "end_date": None,
        "is_active": True,
        "days_active": 45,
        "variant_count": 8,
        "publisher_platforms": ["facebook", "instagram", "messenger"],
        "body_text": (
            "🧠 Bạn hay quên trước quên sau, đau nửa đầu, mất ngủ triền miên ở tuổi 35+?\n\n"
            "Áp lực công việc và tuổi tác khiến tuần hoàn máu não suy giảm nghiêm trọng. "
            "Hơn 10.000 khách hàng đã lấy lại giấc ngủ sâu và sự minh mẫn nhờ Viên uống bổ não Ginkgo Biloba 2000mg Chuẩn Úc.\n"
            "Chiết xuất cao bạch quả tinh khiết giúp tăng lưu thông máu lên não, giảm đau đầu tiền đình, tăng cường trí nhớ rõ rệt sau 14 ngày.\n\n"
            "🌿 ƯU ĐÃI SỨC KHỎE ĐỘC QUYỀN:\n"
            "- Mua combo 2 lọ tặng 1 hộp Trà thảo mộc an thần cao cấp.\n"
            "- Bác sĩ dinh dưỡng gọi điện tư vấn phác đồ 1-1 miễn phí.\n"
            "- Freeship toàn quốc + Kiểm tra hàng trước khi thanh toán.\n"
            "👉 Bấm [Gửi tin nhắn] nhận tư vấn từ dược sĩ chuyên môn!"
        ),
        "title": "Ginkgo Biloba Úc 2000mg - Tạm Biệt Đau Đầu, Mất Ngủ",
        "caption": "healthycare.vn/ginkgo-biloba",
        "cta_text": "Gửi tin nhắn",
        "link_url": "https://healthycare.vn/ginkgo-biloba",
        "media_type": "video",
        "media_urls": [
            "https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=800&auto=format&fit=crop&q=80"
        ],
        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=671928192019283",
    },
    {
        "id": "ad_seed_005",
        "ad_archive_id": "581920192830192",
        "page_id": "591820192830",
        "page_name": "Bestical Vietnam - Canxi Sinh Học",
        "page_profile_picture_url": "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=100&auto=format&fit=crop&q=80",
        "start_date": "2026-10-01",
        "end_date": None,
        "is_active": True,
        "days_active": 19,
        "variant_count": 5,
        "publisher_platforms": ["facebook", "instagram"],
        "body_text": (
            "⚠️ Bé ngủ trằn trọc, đổ mồ hôi trộm, rụng tóc vành khăn? Dấu hiệu thiếu canxi mẹ chớ coi thường!\n\n"
            "Giai đoạn 1000 ngày đầu đời quyết định 60% chiều cao trưởng thành của trẻ. "
            "Canxi sinh học Bestical thế hệ mới ứng dụng công nghệ Lipocal siêu mịn từ Châu Âu, "
            "hấp thu gấp đôi canxi thông thường, không nóng trong, không táo bón, vị dâu thơm ngọt bé nào cũng thích.\n\n"
            "🎁 KHUYẾN MÃI ĐỒNG HÀNH CÙNG MẸ:\n"
            "- Ưu đãi 20% khi mua liệu trình 2 lọ Bestical.\n"
            "- Tặng kèm Ebook 'Cẩm nang ăn dặm khoa học và phát triển chiều cao' do bác sĩ nhi biên soạn.\n"
            "Nhấn [Tìm hiểu thêm] để được chuyên gia đo lường biểu đồ tăng trưởng của bé!"
        ),
        "title": "Canxi Sinh Học Bestical - Hấp Thu Tối Đa, Không Táo Bón",
        "caption": "bestical.vn/canxi-sinh-hoc",
        "cta_text": "Tìm hiểu thêm",
        "link_url": "https://bestical.vn/canxi-sinh-hoc",
        "media_type": "image",
        "media_urls": [
            "https://images.unsplash.com/photo-1584362917165-526a968579e8?w=800&auto=format&fit=crop&q=80"
        ],
        "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=581920192830192",
    },
]


# ==============================================================================
# 5. CREATIVE ANGLE & AI ANALYZER
# ==============================================================================

class CreativeAngleAnalyzer:
    """Bộ phân tích góc tiếp cận quảng cáo sử dụng Heuristics & Quy tắc NLP."""

    FEAR_KEYWORDS = [
        "sợ", "nguy hiểm", "cảnh báo", "sai lầm", "đừng", "hỏng", "hăm",
        "lo lắng", "thức trắng", "nôn trớ", "đau", "mất ngủ", "thiếu canxi",
        "rụng tóc", "ốm vặt", "coi thường", "ảnh hưởng", "tác hại",
    ]
    CURIOSITY_KEYWORDS = [
        "tại sao", "có biết", "bí mật", "sự thật", "lý do", "liệu", "bất ngờ",
        "chưa từng", "ai cũng nghĩ", "đố bạn",
    ]
    PROMO_KEYWORDS = [
        "ưu đãi", "giảm", "sale", "tặng", "combo", "miễn phí", "freeship",
        "voucher", "flash sale", "quà tặng", "tiết kiệm", "%",
    ]
    SOCIAL_PROOF_KEYWORDS = [
        "hàng ngàn", "10.000", "bác sĩ", "chuyên gia", "tin dùng", "feedback",
        "đánh giá", "review", "chứng nhận", "khuyến nghị", "lâm sàng",
    ]

    def analyze(self, ad: AdCreative) -> CreativeAnalysis:
        body = ad.body_text or ""
        lines = [line.strip() for line in body.splitlines() if line.strip()]

        # 1. Trích xuất Hook Text (1-3 dòng đầu)
        if lines:
            hook_text = " ".join(lines[:2])
            if len(hook_text) > 160:
                hook_text = hook_text[:157] + "..."
        else:
            hook_text = ad.title or "N/A"

        hook_lower = hook_text.lower()
        body_lower = body.lower()

        # 2. Phân loại Hook Type
        if any(kw in hook_lower for kw in self.FEAR_KEYWORDS):
            hook_type = "Nỗi sợ & Cảnh báo (Fear / Problem-Agitate)"
        elif "?" in hook_text or any(kw in hook_lower for kw in self.CURIOSITY_KEYWORDS):
            hook_type = "Tò mò & Đặt câu hỏi (Curiosity / Question)"
        elif any(kw in hook_lower for kw in self.PROMO_KEYWORDS):
            hook_type = "Khuyến mãi & Ưu đãi (Promotion / Offer-driven)"
        elif any(kw in hook_lower for kw in self.SOCIAL_PROOF_KEYWORDS):
            hook_type = "Bằng chứng xã hội (Social Proof / Authority)"
        else:
            hook_type = "Lợi ích vượt trội (Benefit-driven)"

        # 3. Trích xuất Primary Offer
        offer_match = re.search(
            r"(combo \d+[^.\n]+|giảm \d+[%kK]|mua \d+ tặng \d+[^.\n]*|tặng ngay [^.\n]+|ưu đãi \d+[%kK][^.\n]*|freeship toàn quốc)",
            body,
            re.IGNORECASE,
        )
        if offer_match:
            primary_offer = offer_match.group(0).strip()
        elif "freeship" in body_lower or "miễn phí vận chuyển" in body_lower:
            primary_offer = "Miễn phí vận chuyển (Freeship)"
        elif any(k in body_lower for k in ["giảm giá", "ưu đãi", "sale"]):
            primary_offer = "Ưu đãi giá đặc biệt theo chiến dịch"
        else:
            primary_offer = "Chưa công bố ưu đãi cụ thể (Direct Value)"

        # 4. Xác định Marketing Angle
        if any(w in body_lower for w in ["sơ sinh", "bé", "con", "trẻ nhỏ", "mẹ bỉm"]):
            if "hăm" in body_lower or "trào ngược" in body_lower or "an toàn" in body_lower:
                marketing_angle = "Bảo vệ con yêu & An tâm cha mẹ (Protection & Peace of mind)"
            else:
                marketing_angle = "Chăm sóc dịu lành & Tiện lợi cho mẹ (Gentle Care & Convenience)"
        elif any(w in body_lower for w in ["não", "ginkgo", "mất ngủ", "đau đầu", "canxi", "sức khỏe"]):
            marketing_angle = "Phục hồi sức khỏe & Nâng cao thể trạng (Health Restoration)"
        elif "combo" in primary_offer.lower() or "giảm" in primary_offer.lower():
            marketing_angle = "Tiết kiệm chi phí & Quà tặng giá trị (Value Stack & Savings)"
        else:
            marketing_angle = "Giải pháp chuyên sâu & Tiện ích tiêu dùng (Specialized Solution)"

        # 5. Xác định Target Audience
        if any(w in body_lower for w in ["sơ sinh", "bé", "con", "mẹ bỉm", "ọc sữa"]):
            target_audience = "Mẹ bỉm sữa, phụ nữ mang thai hoặc phụ huynh có con nhỏ 0-2 tuổi"
        elif any(w in body_lower for w in ["não", "mất ngủ", "đau nửa đầu", "35+"]):
            target_audience = "Người trưởng thành, trung niên (35+) & người lao động trí óc chịu stress cao"
        elif any(w in body_lower for w in ["thực phẩm chức năng", "bổ sung", "uống"]):
            target_audience = "Người tiêu dùng quan tâm sức khỏe chủ động và dinh dưỡng bổ sung"
        else:
            target_audience = "Khách hàng mua sắm trực tuyến đại chúng quan tâm sản phẩm"

        # 6. Trích xuất Pain Points
        pain_points = []
        pain_patterns = [
            (r"hăm tã|hăm đỏ|hăm loét|hăm", "Bé bị hăm tã, ngứa ngáy khó chịu"),
            (r"nôn trớ|ọc sữa|trào ngược", "Con hay trào ngược, ọc sữa sau bú khiến mẹ lo lắng"),
            (r"hóa chất|kích ứng|mỏng gấp 5 lần", "Lo sợ da bé bị dị ứng bởi hóa chất độc hại"),
            (r"đau nửa đầu|mất ngủ|hay quên", "Đau đầu, hay quên, mất ngủ kéo dài làm suy giảm chất lượng sống"),
            (r"đổ mồ hôi trộm|rụng tóc vành khăn|thiếu canxi", "Bé trằn trọc, còi xương, thiếu hụt vi chất"),
        ]
        for pattern, desc in pain_patterns:
            if re.search(pattern, body_lower):
                pain_points.append(desc)
        if not pain_points:
            pain_points.append("Nhu cầu tìm kiếm sản phẩm chất lượng, nguồn gốc minh bạch")

        # 7. Tính Persuasion Score (1-10)
        score = 5
        if hook_type != "Lợi ích vượt trội (Benefit-driven)":
            score += 1
        if primary_offer != "Chưa công bố ưu đãi cụ thể (Direct Value)":
            score += 1
        if any(kw in body_lower for kw in self.SOCIAL_PROOF_KEYWORDS):
            score += 1
        if ad.cta_text:
            score += 1
        if is_winning_ad(ad):
            score += 1
        score = min(score, 10)

        # 8. Đề xuất cải tiến / Phản đòn (Recommendations)
        recommendations = []
        if "video" not in ad.media_type:
            recommendations.append("Thử nghiệm biến thể Video UGC ngắn (Reels format 9:16) để tăng giữ chân người xem.")
        else:
            recommendations.append("Khai thác thêm format ảnh tĩnh Side-by-Side (Trước vs Sau) để giảm chi phí CPM.")

        if "freeship" not in body_lower:
            recommendations.append("Bổ sung cam kết Freeship vào ngay Hook hoặc Headline để hạ rào cản chuyển đổi.")
        else:
            recommendations.append("Đẩy mạnh chính sách bảo hành/hoàn tiền 100% nếu không hài lòng để triệt tiêu rủi ro mua hàng.")

        return CreativeAnalysis(
            hook_type=hook_type,
            hook_text=hook_text,
            primary_offer=primary_offer,
            marketing_angle=marketing_angle,
            target_audience=target_audience,
            pain_points=pain_points,
            persuasion_score=score,
            recommendations=recommendations,
        )


# ==============================================================================
# 6. AD NORMALIZER
# ==============================================================================

def compute_coverage(ads: List[AdCreative], requested: int) -> CoverageMetrics:
    """Tính toán chỉ số bao phủ và phát hiện các trường dữ liệu bị thiếu."""
    collected = len(ads)
    missing = set()
    fields_to_check = [
        ("body_text", lambda a: not a.body_text),
        ("title", lambda a: not a.title),
        ("caption", lambda a: not a.caption),
        ("cta_text", lambda a: not a.cta_text),
        ("link_url", lambda a: not a.link_url),
        ("media_urls", lambda a: not a.media_urls),
        ("page_profile_picture_url", lambda a: not a.page_profile_picture_url),
        ("start_date", lambda a: a.start_date in (None, "", "N/A")),
    ]
    for ad in ads:
        for fname, check_fn in fields_to_check:
            if check_fn(ad):
                missing.add(fname)
    missing_fields = sorted(list(missing))
    return CoverageMetrics(
        requested=requested,
        collected=collected,
        failed=max(0, requested - collected),
        complete=(collected >= requested),
        missing_fields=missing_fields,
    )


class AdNormalizer:
    """Chuẩn hóa dữ liệu thô từ Meta sang Data Model AdCreative an toàn."""

    @staticmethod
    def normalize_node(node: Dict[str, Any]) -> AdCreative:
        today = datetime.date.today()
        raw_start = node.get("start_date")
        if raw_start and isinstance(raw_start, str) and raw_start.strip():
            start_date_str = raw_start.strip()
            days_active = node.get("days_active")
            if days_active is None:
                try:
                    start_dt = datetime.date.fromisoformat(start_date_str[:10])
                    days_active = max(0, (today - start_dt).days)
                except Exception:
                    days_active = 0
        else:
            start_date_str = "N/A"
            days_active = 0

        ad_id = str(node.get("id") or node.get("ad_archive_id") or "N/A")
        archive_id = str(node.get("ad_archive_id") or ad_id)
        raw_snapshot = node.get("ad_snapshot_url")
        if raw_snapshot and isinstance(raw_snapshot, str) and (raw_snapshot.startswith("http://") or raw_snapshot.startswith("https://")):
            snapshot_url = raw_snapshot
        else:
            snapshot_url = f"https://www.facebook.com/ads/library/?id={archive_id}"

        # Trích xuất platforms
        platforms = node.get("publisher_platforms") or ["facebook"]
        if isinstance(platforms, str):
            platforms = [platforms]

        # Trích xuất media_urls null-safe
        raw_media = node.get("media_urls") or []
        media_urls = []
        for m in raw_media:
            if isinstance(m, str) and (m.startswith("http://") or m.startswith("https://")):
                media_urls.append(m)

        raw_avatar = node.get("page_profile_picture_url")
        avatar_url = (
            str(raw_avatar)
            if raw_avatar and isinstance(raw_avatar, str) and (raw_avatar.startswith("http://") or raw_avatar.startswith("https://"))
            else None
        )

        return AdCreative(
            id=ad_id,
            ad_archive_id=archive_id,
            page_id=str(node.get("page_id") or "N/A"),
            page_name=str(node.get("page_name") or "Fanpage"),
            page_profile_picture_url=avatar_url,
            start_date=start_date_str,
            end_date=node.get("end_date"),
            is_active=bool(node.get("is_active", True)),
            days_active=int(days_active),
            variant_count=int(node.get("variant_count") or 1),
            publisher_platforms=[str(p) for p in platforms],
            body_text=str(node.get("body_text") or ""),
            title=node.get("title"),
            caption=node.get("caption"),
            cta_text=node.get("cta_text"),
            link_url=node.get("link_url"),
            media_type=str(node.get("media_type") or "image"),
            media_urls=media_urls,
            ad_snapshot_url=snapshot_url,
        )

    @staticmethod
    def normalize_scrape_js_item(item: Dict[str, Any]) -> AdCreative:
        """Chuẩn hóa một item từ scrape.js (Node.js engine) sang AdCreative."""
        return map_scrape_js_item_to_ad_creative(item)

    normalize_raw_ad = normalize_node


def normalize_raw_ad(node: Dict[str, Any]) -> AdCreative:
    """Wrapper cho AdNormalizer.normalize_node."""
    return AdNormalizer.normalize_node(node)


def _parse_ad_start_date(text: str) -> str:
    """Bóc tách ngày bắt đầu chạy quảng cáo từ text node của Meta Ads Library sang YYYY-MM-DD hoặc N/A."""
    # Tiếng Việt: 'Ngày bắt đầu chạy: 16 Tháng 4, 2026' hoặc '16 thg 4, 2026'
    m_vn = re.search(
        r'(?:Ngày bắt đầu chạy|Bắt đầu chạy vào):\s*(\d{1,2})\s+(?:Tháng|thg)\s+(\d{1,2}),?\s+(\d{4})',
        text,
        re.IGNORECASE,
    )
    if m_vn:
        day, month, year = int(m_vn.group(1)), int(m_vn.group(2)), int(m_vn.group(3))
        try:
            return datetime.date(year, month, day).isoformat()
        except Exception:
            pass

    # Tiếng Anh
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    m_en1 = re.search(r'Started running on\s*([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})', text, re.IGNORECASE)
    if m_en1:
        mon_str, day, year = m_en1.group(1).lower(), int(m_en1.group(2)), int(m_en1.group(3))
        if mon_str in months:
            try:
                return datetime.date(year, months[mon_str], day).isoformat()
            except Exception:
                pass

    m_en2 = re.search(r'Started running on\s*(\d{1,2})\s+([a-zA-Z]+),?\s+(\d{4})', text, re.IGNORECASE)
    if m_en2:
        day, mon_str, year = int(m_en2.group(1)), m_en2.group(2).lower(), int(m_en2.group(3))
        if mon_str in months:
            try:
                return datetime.date(year, months[mon_str], day).isoformat()
            except Exception:
                pass

    m_dmy = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m_dmy:
        day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        try:
            return datetime.date(year, month, day).isoformat()
        except Exception:
            pass

    return "N/A"


def map_scrape_js_item_to_ad_creative(item: Dict[str, Any]) -> AdCreative:
    """Chuyển đổi dữ liệu từ output của scrape.js sang mô hình chuẩn AdCreative."""
    raw_id = str(item.get("ad_id") or item.get("id") or "N/A")
    raw_start = item.get("start_date")
    start_date_str = str(raw_start).strip() if raw_start and str(raw_start).strip() else "N/A"

    days_running = item.get("days_running")
    if days_running is not None:
        try:
            days_active = max(0, int(days_running))
        except (ValueError, TypeError):
            days_active = 0
    elif start_date_str != "N/A":
        try:
            start_dt = datetime.date.fromisoformat(start_date_str[:10])
            days_active = max(0, (datetime.date.today() - start_dt).days)
        except Exception:
            days_active = 0
    else:
        days_active = 0

    variants = item.get("variants") or 1
    try:
        variant_count = max(1, int(variants))
    except (ValueError, TypeError):
        variant_count = 1

    platforms = item.get("platforms") or item.get("publisher_platforms") or ["facebook"]
    if isinstance(platforms, str):
        platforms = [platforms]
    publisher_platforms = [str(p).lower() for p in platforms]

    raw_format = str(item.get("format") or "").upper()
    videos = [v for v in (item.get("videos") or []) if isinstance(v, str) and (v.startswith("http://") or v.startswith("https://"))]
    images = [img for img in (item.get("images") or []) if isinstance(img, str) and (img.startswith("http://") or img.startswith("https://"))]
    card_count = int(item.get("card_count") or 0)

    if "VIDEO" in raw_format or len(videos) > 0:
        media_type = "video"
    elif "MULTI" in raw_format or "CAROUSEL" in raw_format or card_count > 1 or len(images) > 1:
        media_type = "carousel"
    elif "IMAGE" in raw_format or len(images) > 0:
        media_type = "image"
    elif not images and not videos:
        media_type = "text_only"
    else:
        media_type = "image"

    media_urls: List[str] = []
    for u in videos + images:
        if u not in media_urls:
            media_urls.append(u)

    video_prev = item.get("video_preview")
    if video_prev and isinstance(video_prev, str) and (video_prev.startswith("http://") or video_prev.startswith("https://")):
        if video_prev not in media_urls:
            media_urls.append(video_prev)

    lib_url = item.get("library_url")
    if lib_url and isinstance(lib_url, str) and (lib_url.startswith("http://") or lib_url.startswith("https://")):
        snapshot_url = lib_url
    else:
        snapshot_url = f"https://www.facebook.com/ads/library/?id={raw_id}"

    return AdCreative(
        id=raw_id,
        ad_archive_id=raw_id,
        page_id=str(item.get("page_id") or "N/A"),
        page_name=str(item.get("page_name") or "Fanpage"),
        page_profile_picture_url=None,
        start_date=start_date_str,
        end_date=item.get("end_date"),
        is_active=bool(item.get("is_active", True)),
        days_active=days_active,
        variant_count=variant_count,
        publisher_platforms=publisher_platforms,
        body_text=str(item.get("body") or ""),
        title=item.get("title") or None,
        caption=item.get("link_caption") or None,
        cta_text=item.get("cta") or None,
        link_url=item.get("link_url") or None,
        media_type=media_type,
        media_urls=media_urls,
        ad_snapshot_url=snapshot_url,
    )


def kill_process_tree(pid: int) -> None:
    """Triệt tiêu toàn bộ cây tiến trình (process tree) tránh sót node.exe hoặc chrome.exe mồ côi trên Windows."""
    try:
        import psutil
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
    except Exception:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass


def run_node_scrape_subprocess(
    keyword: str,
    country: str = "VN",
    limit: int = 20,
    active_only: bool = True,
    media_type: str = "all",
    cdp_port: Optional[int] = None,
    timeout: int = 120,
    scrape_script_path: Optional[Path] = None,
    sort: str = "total_impressions",
    loose: bool = False,
) -> List[AdCreative]:
    """Khởi chạy node scrape.js qua subprocess an toàn với STDIN DevNull Guard và Process Hygiene."""
    node_bin = shutil.which("node")
    if not node_bin:
        raise RuntimeError("Môi trường không tìm thấy lệnh 'node' trong PATH.")

    if scrape_script_path is None:
        project_root = Path(__file__).resolve().parent.parent
        scrape_script_path = project_root / "plugins" / "marketing" / "tools" / "ad-library" / "scrape.js"

    if not scrape_script_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy tệp script scrape.js tại: {scrape_script_path}")

    temp_dir = Path(tempfile.gettempdir())
    temp_out = temp_dir / f"meta_scout_{uuid.uuid4().hex[:10]}.json"

    cmd = [
        node_bin,
        str(scrape_script_path),
        "--q", keyword,
        "--country", country,
        "--max", str(limit),
        "--out", str(temp_out),
    ]

    status_val = "active" if active_only else "all"
    cmd.extend(["--status", status_val])

    sort_mode = "top" if sort in ("top", "total_impressions") else ("new" if sort == "new" else "relevance")
    cmd.extend(["--sort", sort_mode])

    if loose:
        cmd.append("--loose")

    if media_type in ("image", "video"):
        cmd.extend(["--media", media_type])
    else:
        cmd.extend(["--media", "all"])

    if cdp_port is not None:
        cmd.extend(["--cdp-port", str(cdp_port)])

    logger.info(f"Khởi chạy Node Scraper Adapter: {' '.join(cmd[:4])} ...")

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        if proc.returncode != 0:
            logger.warning(f"Node scraper exit code {proc.returncode}. Stderr: {stderr[:300]}")
            raise RuntimeError(f"Node scraper thất bại (exit code {proc.returncode}): {stderr.strip()[:200]}")

        if not temp_out.exists():
            raise RuntimeError(f"Node scraper hoàn tất nhưng không tạo tệp kết quả tại {temp_out}")

        with open(temp_out, "r", encoding="utf-8") as f:
            payload = json.load(f)

        raw_ads = payload.get("ads", [])
        if not raw_ads:
            logger.warning("Node scraper trả về 0 kết quả.")
            return []

        ads = [map_scrape_js_item_to_ad_creative(item) for item in raw_ads]
        return ads[:limit]

    except subprocess.TimeoutExpired:
        logger.warning(f"Node scraper timed out sau {timeout}s. Đang dọn dẹp tiến trình mồ côi...")
        if proc:
            kill_process_tree(proc.pid)
        raise TimeoutError(f"Node scraper bị timeout sau {timeout} giây.")
    except Exception as e:
        if proc and proc.poll() is None:
            kill_process_tree(proc.pid)
        raise e
    finally:
        if temp_out.exists():
            try:
                temp_out.unlink()
            except OSError:
                pass


def run_node_lp_subprocess(
    ads: List[AdCreative],
    top: int = 5,
    timeout: int = 60,
    lp_script_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Chạy node lp.js để trích xuất thông tin landing page an toàn với STDIN DevNull Guard."""
    node_bin = shutil.which("node")
    if not node_bin:
        logger.warning("Không tìm thấy Node.js để chạy lp.js.")
        return {}

    if lp_script_path is None:
        project_root = Path(__file__).resolve().parent.parent
        lp_script_path = project_root / "plugins" / "marketing" / "tools" / "ad-library" / "lp.js"

    if not lp_script_path.is_file():
        logger.warning(f"Không tìm thấy script lp.js tại {lp_script_path}")
        return {}

    eligible_ads = [ad for ad in ads if ad.link_url and ad.link_url.startswith("http")]
    if not eligible_ads:
        return {}

    temp_dir = Path(tempfile.gettempdir())
    input_file = temp_dir / f"meta_lp_in_{uuid.uuid4().hex[:8]}.json"
    output_file = temp_dir / f"meta_lp_out_{uuid.uuid4().hex[:8]}.json"

    proc = None
    try:
        raw_payload = {
            "ads": [
                {
                    "ad_id": a.id,
                    "page_name": a.page_name,
                    "link_url": a.link_url,
                }
                for a in eligible_ads
            ]
        }
        input_file.write_text(json.dumps(raw_payload, ensure_ascii=False), encoding="utf-8")

        cmd = [
            node_bin,
            str(lp_script_path),
            str(input_file),
            "--top", str(top),
            "--out", str(output_file),
        ]

        logger.info(f"Bắt đầu soi Landing Page ({len(eligible_ads)} ads)...")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc.pid)
            logger.warning(f"lp.js bị timeout sau {timeout}s.")
            return {}

        if proc.returncode != 0:
            logger.warning(f"lp.js exit code {proc.returncode}: {stderr[:200]}")
            return {}

        if not output_file.exists():
            return {}

        lp_results = json.loads(output_file.read_text(encoding="utf-8"))
        res_map = {}
        for r in lp_results:
            ad_id = str(r.get("ad_id") or "")
            req_url = str(r.get("requested_url") or "")
            if ad_id and ad_id != "manual":
                res_map[ad_id] = r
            elif req_url:
                res_map[req_url] = r
        return res_map
    except Exception as e:
        logger.warning(f"Lỗi khi chạy lp.js: {e}")
        return {}
    finally:
        if proc and proc.poll() is None:
            kill_process_tree(proc.pid)
        for f in (input_file, output_file):
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass


def run_node_download_subprocess(
    ads: List[AdCreative],
    output_dir: Path,
    top: int = 5,
    timeout: int = 120,
    download_script_path: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Chạy node download.js để tải media cục bộ an toàn với STDIN DevNull Guard."""
    node_bin = shutil.which("node")
    if not node_bin:
        logger.warning("Không tìm thấy Node.js để chạy download.js.")
        return {}

    if download_script_path is None:
        project_root = Path(__file__).resolve().parent.parent
        download_script_path = project_root / "plugins" / "marketing" / "tools" / "ad-library" / "download.js"

    if not download_script_path.is_file():
        logger.warning(f"Không tìm thấy script download.js tại {download_script_path}")
        return {}

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    target_dl_dir = output_dir / "creative" / today

    temp_dir = Path(tempfile.gettempdir())
    input_file = temp_dir / f"meta_dl_in_{uuid.uuid4().hex[:8]}.json"

    proc = None
    try:
        raw_payload = {
            "ads": [
                {
                    "ad_id": a.id,
                    "page_name": a.page_name,
                    "page_id": a.page_id,
                    "library_url": a.ad_snapshot_url,
                    "link_url": a.link_url,
                    "cta": a.cta_text,
                    "format": a.media_type,
                    "start_date": a.start_date,
                    "days_running": a.days_active,
                    "variants": a.variant_count,
                    "platforms": a.publisher_platforms,
                    "title": a.title,
                    "link_caption": a.caption,
                    "body": a.body_text,
                    "images": [u for u in a.media_urls if not any(ext in u.lower() for ext in (".mp4", ".webm"))],
                    "videos": [u for u in a.media_urls if any(ext in u.lower() for ext in (".mp4", ".webm"))],
                    "video_preview": next((u for u in a.media_urls if any(ext in u.lower() for ext in (".jpg", ".jpeg", ".png"))), None),
                }
                for a in ads
            ]
        }
        input_file.write_text(json.dumps(raw_payload, ensure_ascii=False), encoding="utf-8")

        cmd = [
            node_bin,
            str(download_script_path),
            str(input_file),
            "--top", str(top),
            "--out-dir", str(target_dl_dir),
            "--json",
        ]

        logger.info(f"Bắt đầu tải media offline (Top {top} ads)...")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc.pid)
            logger.warning(f"download.js bị timeout sau {timeout}s.")
            return {}

        if proc.returncode != 0:
            logger.warning(f"download.js exit code {proc.returncode}: {stderr[:200]}")
            return {}

        res_map = {}
        try:
            dl_reports = json.loads(stdout)
            for item in dl_reports:
                ad_id = str(item.get("ad_id") or "")
                files = item.get("files") or []
                if ad_id:
                    res_map[ad_id] = files
        except Exception:
            if target_dl_dir.exists():
                for subfolder in target_dl_dir.iterdir():
                    if subfolder.is_dir():
                        parts = subfolder.name.split("-")
                        if len(parts) >= 3:
                            folder_ad_id = parts[-1]
                            files = [str(f.resolve()) for f in subfolder.iterdir() if f.is_file() and f.name != "info.txt"]
                            res_map[folder_ad_id] = files
        return res_map
    except Exception as e:
        logger.warning(f"Lỗi khi chạy download.js: {e}")
        return {}
    finally:
        if proc and proc.poll() is None:
            kill_process_tree(proc.pid)
        if input_file.exists():
            try:
                input_file.unlink()
            except OSError:
                pass


# ==============================================================================
# 7. MULTI-TIER SCRAPING ENGINE
# ==============================================================================

class MetaScraperEngine:
    """Engine cào dữ liệu Meta Ads Library đa tầng với cơ chế Graceful Fallback."""

    def __init__(self, seed_data: Optional[List[Dict[str, Any]]] = None):
        self.seed_data = seed_data or SEED_ADS

    def _fetch_tier1_node(
        self,
        keyword: str,
        country: str,
        limit: int,
        active_only: bool,
        media_type: str,
        cdp_port: Optional[int] = None,
        sort: str = "total_impressions",
        loose: bool = False,
    ) -> List[AdCreative]:
        """Cào qua Node.js Scraper Adapter."""
        return run_node_scrape_subprocess(
            keyword=keyword,
            country=country,
            limit=limit,
            active_only=active_only,
            media_type=media_type,
            cdp_port=cdp_port,
            sort=sort,
            loose=loose,
        )

    def fetch(
        self,
        keyword: str,
        country: str = "VN",
        limit: int = 20,
        sort: str = "total_impressions",
        active_only: bool = True,
        media_type: str = "all",
        use_seed_only: bool = False,
        cdp_port: Optional[int] = None,
        loose: bool = False,
    ) -> tuple[List[AdCreative], CoverageMetrics, str]:
        target_url = build_meta_ads_url(keyword, country, sort, active_only, media_type, loose=loose)

        if use_seed_only:
            logger.info("Chế độ --seed / --seed-only được kích hoạt. Nạp bộ dữ liệu mẫu tức thì.")
            return self._load_seed(keyword, limit)

        # Tier 1: Thử Node.js Scraper Adapter (Playwright Node / CDP)
        try:
            logger.info("Tier 1: Đang khởi chạy Node.js Scraper Adapter (scrape.js)...")
            ads = self._fetch_tier1_node(
                keyword=keyword,
                country=country,
                limit=limit,
                active_only=active_only,
                media_type=media_type,
                cdp_port=cdp_port,
                sort=sort,
                loose=loose,
            )
            if ads:
                coverage = compute_coverage(ads, requested=limit)
                return ads, coverage, "tier1_node_scraper"
        except Exception as e:
            logger.warning(f"Tier 1 (Node Scraper Adapter) thất bại hoặc không khả dụng ({e}). Graceful fallback sang Tier 2 (Playwright Python)...")

        # Tier 2: Cào dữ liệu thực tế và realtime từ Meta Ads Library bằng Playwright Chromium
        try:
            logger.info("Tier 2: Đang khởi chạy Playwright Chromium Python cào dữ liệu thực tế từ Meta Ads Library...")
            ads = self._fetch_tier1_playwright(target_url, limit)
            if ads:
                coverage = compute_coverage(ads, requested=limit)
                return ads, coverage, "tier1_playwright_live"
        except Exception as e:
            logger.warning(f"Tier 2 (Playwright Python) thất bại ({e}). Chuyển sang kiểm tra Tier 3...")

        # Tier 3: Thử Graph API nếu có META_ACCESS_TOKEN
        token = os.getenv("META_ACCESS_TOKEN")
        if token:
            try:
                logger.info("Tier 2: Đang thử Meta Graph API (/ads_archive)...")
                ads = self._fetch_tier2_graph_api(keyword, country, limit, token)
                if ads:
                    coverage = compute_coverage(ads, requested=limit)
                    return ads, coverage, "tier2_graph_api"
            except Exception as e:
                logger.warning(f"Tier 2 (Graph API) thất bại ({e}).")

        # TUYỆT ĐỐI CẤM TỰ Ý FALLBACK VỀ SEED_ADS KHI KHÔNG CÓ CỜ --seed
        raise RuntimeError(
            f"Không thể cào dữ liệu trực tiếp từ Meta Ads Library cho từ khóa '{keyword}'. "
            f"Vui lòng kiểm tra kết nối mạng hoặc thử lại. Nếu muốn xem dữ liệu mẫu thẩm định, hãy thêm cờ --seed."
        )

    def _load_seed(self, keyword: str, limit: int) -> tuple[List[AdCreative], CoverageMetrics, str]:
        """Lọc và chuẩn hóa dữ liệu mẫu seed."""
        kw_norm = keyword.lower().strip('"\' ')
        matching = []
        for raw in self.seed_data:
            text = (raw.get("body_text", "") + " " + raw.get("title", "") + " " + raw.get("page_name", "")).lower()
            if not kw_norm or kw_norm in text:
                matching.append(raw)

        # Nếu từ khóa không khớp ad nào trong seed, trả về toàn bộ seed để không rỗng
        if not matching:
            matching = list(self.seed_data)

        selected = matching[:limit]
        ads = [AdNormalizer.normalize_node(n) for n in selected]
        coverage = compute_coverage(ads, requested=limit)
        return ads, coverage, "tier4_seed_fallback"

    def _fetch_tier1_playwright(self, target_url: str, limit: int) -> List[AdCreative]:
        """Cào dữ liệu thực tế 100% từ Meta Ads Library bằng Playwright Chromium."""
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup

        ads: List[AdCreative] = []
        seen_ids: set[str] = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
                page = browser.new_page(user_agent=user_agent)
                page.set_extra_http_headers({
                    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                })
                page.goto(target_url, timeout=35000, wait_until="networkidle")
                page.wait_for_timeout(4000)

                # Cuộn trang nhẹ để kích hoạt tải thêm bài quảng cáo
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                page.wait_for_timeout(2000)

                html_content = page.content()
                browser.close()
        except Exception as e:
            logger.error(f"Lỗi kết nối Playwright Chromium: {e}")
            raise RuntimeError(f"Playwright Chromium không thể truy cập Meta Ads Library: {e}") from e

        soup = BeautifulSoup(html_content, "html.parser")
        id_nodes = soup.find_all(string=re.compile(r'ID thư viện:\s*\d+|Library ID:\s*\d+'))
        if not id_nodes:
            raise RuntimeError("Meta Ads Library không trả về thẻ quảng cáo nào (trang rỗng hoặc bị checkpoint).")

        for node in id_nodes:
            if len(ads) >= limit:
                break
            text = str(node).strip()
            ad_id_match = re.search(r'\d+', text)
            if not ad_id_match:
                continue
            ad_id = ad_id_match.group(0)
            if ad_id in seen_ids:
                continue

            # Tìm thẻ div card bao bọc (chứa đúng 1 node ID thư viện)
            curr = node.parent
            card = None
            for _ in range(16):
                if not curr or curr.name in ('body', 'html'):
                    break
                ids_inside = curr.find_all(string=re.compile(r'ID thư viện:\s*\d+|Library ID:\s*\d+'))
                if len(ids_inside) > 1:
                    break
                if len(ids_inside) == 1:
                    card = curr
                    curr_text = curr.get_text(" ", strip=True)
                    has_sponsored = bool(re.search(r'Được tài trợ|Sponsored', curr_text, re.IGNORECASE))
                    if has_sponsored:
                        # Đã chạm ranh giới card hoàn chỉnh chứa Fanpage & nội dung bài viết, dừng lại ngay tránh trôi lên body
                        break
                curr = curr.parent

            if not card:
                continue

            seen_ids.add(ad_id)
            card_text = card.get_text("\n", strip=True)
            lines = [line.strip() for line in card_text.split("\n") if line.strip()]

            start_date = _parse_ad_start_date(card_text)

            # Bóc tách tên Fanpage và nội dung bài viết quảng cáo thực tế
            page_name = "Meta Advertiser"
            body_text = ""
            cta_text = None

            sponsored_idx = -1
            for idx, line in enumerate(lines):
                if re.search(r'^(Được tài trợ|Sponsored)', line, re.IGNORECASE):
                    sponsored_idx = idx
                    if idx > 0:
                        page_name = lines[idx - 1]
                    elif idx + 1 < len(lines):
                        page_name = lines[idx + 1]
                    break

            content_lines = []
            if sponsored_idx != -1:
                raw_body = lines[sponsored_idx + 1:]
                cta_candidates = {
                    'gửi tin nhắn', 'send message', 'tìm hiểu thêm', 'learn more',
                    'mua ngay', 'shop now', 'đăng ký', 'sign up',
                    'liên hệ với chúng tôi', 'contact us', 'nhận báo giá', 'get quote',
                    'gọi ngay', 'call now', 'cài đặt ngay', 'install now',
                    'sử dụng ứng dụng', 'use app'
                }
                for bl in raw_body:
                    if bl.lower() in cta_candidates:
                        cta_text = bl
                        break
                    content_lines.append(bl)
                body_text = "\n".join(content_lines).strip()
            else:
                body_text = card_text.strip()

            # Bóc tách tiêu đề / headline nổi bật
            title = None
            heading_node = card.find(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4', 'strong'] and tag.get_text(strip=True))
            if heading_node:
                h_text = heading_node.get_text(strip=True)
                if (
                    h_text
                    and h_text.lower() not in [page_name.lower(), 'được tài trợ', 'sponsored']
                    and not re.search(r'ID thư viện|Library ID', h_text, re.I)
                ):
                    title = h_text

            if not title:
                if content_lines:
                    first_line = content_lines[0].strip()
                    if first_line and len(first_line) > 5:
                        title = first_line[:120]
                elif body_text:
                    first_line = body_text.split("\n")[0].strip()
                    if first_line and len(first_line) > 5:
                        title = first_line[:120]

            # Bóc tách domain / caption nếu có
            caption = None
            link_url = None
            for line in lines:
                if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$', line):
                    caption = line
                    link_url = f"https://{line}" if not line.startswith("http") else line
                    break

            # Bóc tách số lượng nhóm quảng cáo sử dụng chung creative
            variants = 1
            var_match = re.search(
                r'(\d+)\s+quảng cáo sử dụng nội dung|(\d+)\s+ads use this creative',
                card_text,
                re.IGNORECASE,
            )
            if var_match:
                try:
                    variants = int(var_match.group(1) or var_match.group(2))
                except Exception:
                    variants = 1

            # Bóc tách media URLs (ảnh thật) và avatar nếu có
            all_imgs = [
                img.get("src")
                for img in card.find_all("img")
                if img.get("src") and (img.get("src").startswith("http://") or img.get("src").startswith("https://"))
            ]
            avatar_url = all_imgs[0] if all_imgs else None
            media_imgs = all_imgs[1:] if len(all_imgs) > 1 else all_imgs
            has_video = bool(card.find("video"))
            media_type = "video" if has_video else ("image" if media_imgs else "all")
            snapshot_url = f"https://www.facebook.com/ads/library/?id={ad_id}"

            raw_node = {
                "id": ad_id,
                "ad_archive_id": ad_id,
                "page_name": page_name,
                "page_profile_picture_url": avatar_url,
                "start_date": start_date,
                "body_text": body_text,
                "title": title,
                "caption": caption,
                "link_url": link_url,
                "variant_count": variants,
                "media_type": media_type,
                "media_urls": media_imgs,
                "ad_snapshot_url": snapshot_url,
                "cta_text": cta_text,
                "publisher_platforms": ["facebook", "instagram"],
            }
            ads.append(AdNormalizer.normalize_node(raw_node))

        return ads

    # Alias tương thích ngược
    _fetch_tier1 = _fetch_tier1_playwright

    def _fetch_tier2_graph_api(self, keyword: str, country: str, limit: int, token: str) -> List[AdCreative]:
        """Truy vấn Meta Graph API ads_archive."""
        import urllib.request
        api_url = (
            f"https://graph.facebook.com/v19.0/ads_archive"
            f"?fields=id,ad_creation_time,ad_delivery_start_time,page_id,page_name,ad_creative_bodies,ad_snapshot_url"
            f"&search_terms={urllib.parse.quote(keyword)}"
            f"&ad_reached_countries=['{country}']"
            f"&limit={limit}&access_token={token}"
        )
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", [])
            nodes = []
            for it in items:
                bodies = it.get("ad_creative_bodies") or [""]
                nodes.append({
                    "id": it.get("id"),
                    "page_id": it.get("page_id"),
                    "page_name": it.get("page_name"),
                    "start_date": it.get("ad_delivery_start_time", "")[:10],
                    "body_text": bodies[0] if bodies else "",
                    "ad_snapshot_url": it.get("ad_snapshot_url"),
                })
            return [AdNormalizer.normalize_node(n) for n in nodes]


# ==============================================================================
# 8. REPORT EXPORTERS (JSON, MARKDOWN, HTML DASHBOARD)
# ==============================================================================

def autolink_urls(text: str) -> str:
    """Tự động chuyển đổi các URL trong văn bản thành hyperlink an toàn chống XSS.
    
    Nhận diện URL có scheme (http://, https://), bắt đầu bằng www., hoặc các tên miền
    thương mại điện tử/mạng xã hội phổ biến (shopee.vn, lazada.vn, tiktok.com, fb.me, zalo.me...).
    Tất cả các phần văn bản khác đều được escape qua html.escape để đảm bảo an toàn tuyệt đối.
    """
    if not text:
        return ""

    url_pattern = re.compile(
        r"(https?://[^\s<>\"']+|www\.[a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)+(?:/[^\s<>\"']*)?|\b(?:[a-zA-Z0-9\-]+\.)+(?:com\.vn|edu\.vn|gov\.vn|vn|com|net|org|io|me|ly|cc|store|shop|site|online|biz)(?:/[^\s<>\"']*)?)",
        re.IGNORECASE,
    )

    result = []
    last_idx = 0
    for match in url_pattern.finditer(text):
        start, end = match.span()
        result.append(html.escape(text[last_idx:start]))

        raw_url = match.group(0)
        trailing = ""
        while raw_url and raw_url[-1] in ".,;:!?)'\"":
            trailing = raw_url[-1] + trailing
            raw_url = raw_url[:-1]

        if not raw_url or ("." not in raw_url and not raw_url.startswith(("http://", "https://"))):
            result.append(html.escape(raw_url + trailing))
            last_idx = end
            continue

        href = raw_url
        if not href.startswith(("http://", "https://")):
            href = "https://" + href

        if not (href.startswith("http://") or href.startswith("https://")):
            result.append(html.escape(raw_url + trailing))
            last_idx = end
            continue

        safe_href = html.escape(href, quote=True)
        safe_display = html.escape(raw_url)
        result.append(
            f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer" class="post-url-link">{safe_display}</a>'
            f"{html.escape(trailing)}"
        )
        last_idx = end

    result.append(html.escape(text[last_idx:]))
    return "".join(result)


class ReportExporter:
    """Xuất báo cáo đa định dạng: JSON, Markdown và Dashboard HTML bespoke."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, report: ScoutReport, filename: str = "scout_report.json") -> Path:
        out_path = self.output_dir / filename
        data = dataclasses.asdict(report)
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Đã xuất file JSON: {out_path}")
        return out_path

    def export_markdown(self, report: ScoutReport, filename: str = "scout_report.md", min_days: int = 14) -> Path:
        out_path = self.output_dir / filename
        lines = [
            f"# BÁO CÁO TRINH SÁT META ADS — TỪ KHÓA: \"{report.keyword}\"",
            f"**Thời gian trinh sát:** {report.scouted_at} | **Quốc gia:** {report.country} | **Tổng mẫu quét được:** {report.total_found}",
            f"**Đường dẫn truy vấn:** [Meta Ads Library]({report.target_url})",
            "",
            "## 1. Tóm Tắt Độ Bao Phủ Dữ Liệu (Coverage)",
            f"- Yêu cầu: **{report.coverage.requested}** mẫu quảng cáo",
            f"- Thực tế thu thập: **{report.coverage.collected}** mẫu",
            f"- Trạng thái: **{'Hoàn tất đầy đủ 100%' if report.coverage.complete else 'Thu thập một phần'}**",
            "",
            "## 2. Bảng Xếp Hạng Các Mẫu Quảng Cáo Đang Vít Mạnh (Winning Ads)",
            "| STT | Fanpage | Ngày Chạy | Số Nhóm | Hook & Angle | Ưu Đãi (Offer) | Snapshot |",
            "| :---: | :--- | :---: | :---: | :--- | :--- | :---: |",
        ]

        for idx, ad in enumerate(report.ads, 1):
            analysis = report.analyses.get(ad.id)
            hook_str = analysis.hook_type.split("(")[0].strip() if analysis else "N/A"
            angle_str = analysis.marketing_angle.split("(")[0].strip() if analysis else "N/A"
            offer_str = analysis.primary_offer if analysis else "N/A"
            winning_tag = "🔥 " if is_winning_ad(ad, min_days=min_days) else ""

            lines.append(
                f"| {idx} | **{ad.page_name}** | {ad.days_active} ngày | {ad.variant_count} nhóm | "
                f"{winning_tag}{hook_str} / {angle_str} | {offer_str} | [Xem Ads]({ad.ad_snapshot_url}) |"
            )

        lines.extend([
            "",
            "## 3. Đúc Kết Góc Tiếp Cận & Đề Xuất Chiến Lược (Actionable Takeaways)",
        ])

        for ad in report.ads[:3]:
            analysis = report.analyses.get(ad.id)
            if not analysis:
                continue
            lines.append(f"### Mẫu từ **{ad.page_name}** ({ad.days_active} ngày vít liên tục):")
            lines.append(f"- **Hook:** \"{analysis.hook_text}\"")
            lines.append(f"- **Góc tiếp cận:** {analysis.marketing_angle}")
            lines.append(f"- **Nỗi đau khách hàng:** {', '.join(analysis.pain_points)}")
            if ad.landing_page_data:
                lpd = ad.landing_page_data
                prices = ", ".join(lpd.get("prices", []))
                offers = " | ".join(lpd.get("offers", []))
                lines.append(f"- **Landing Page Spy:** {lpd.get('final_url') or ad.link_url}")
                if prices:
                    lines.append(f"  + Giá trích xuất: {prices}")
                if offers:
                    lines.append(f"  + Ưu đãi: {offers}")
                if lpd.get("has_phone_form"):
                    lines.append("  + Phương thức chốt đơn: Form số điện thoại")
            if ad.local_media_paths:
                lines.append(f"- **Media offline:** {len(ad.local_media_paths)} tệp đã lưu cục bộ")
            lines.append(f"- **Đề xuất phản đòn:** {analysis.recommendations[0] if analysis.recommendations else 'Tối ưu lại Hook video'}")
            lines.append("")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Đã xuất file Markdown: {out_path}")
        return out_path

    def export_html(self, report: ScoutReport, filename: str = "scout_dashboard.html", min_days: int = 14) -> Path:
        """Xuất Dashboard visual độc lập với phong cách Apple Dark Glassmorphism và Media Player tương tác."""
        out_path = self.output_dir / filename

        winning_ads = [ad for ad in report.ads if is_winning_ad(ad, min_days=min_days)]
        winning_count = len(winning_ads)
        report_json_safe = (
            json.dumps(dataclasses.asdict(report), ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
        )

        cards_html = []
        for ad in report.ads:
            analysis = report.analyses.get(ad.id)
            is_vip = is_winning_ad(ad, min_days=min_days)

            # XSS escaping cho các trường dữ liệu text
            safe_page = html.escape(ad.page_name)
            linked_body = autolink_urls(ad.body_text)
            safe_title = html.escape(ad.title or "Xem chi tiết quảng cáo")
            safe_caption = html.escape(ad.caption or "")
            safe_cta = html.escape(ad.cta_text or "Tìm hiểu thêm")

            # URL scheme check cho snapshot
            if ad.ad_snapshot_url and (ad.ad_snapshot_url.startswith("http://") or ad.ad_snapshot_url.startswith("https://")):
                safe_snapshot = html.escape(ad.ad_snapshot_url, quote=True)
            else:
                safe_snapshot = "#"

            safe_avatar = None
            if ad.page_profile_picture_url and (ad.page_profile_picture_url.startswith("http://") or ad.page_profile_picture_url.startswith("https://")):
                safe_avatar = html.escape(ad.page_profile_picture_url, quote=True)

            safe_hook_type = html.escape(analysis.hook_type if analysis else "Chưa phân tích")
            safe_angle = html.escape(analysis.marketing_angle if analysis else "N/A")
            safe_offer = html.escape(analysis.primary_offer if analysis else "N/A")
            safe_score = analysis.persuasion_score if analysis else 5

            # Xử lý Link đích nổi bật (ad.link_url)
            safe_link_url = ""
            destination_html = ""
            if ad.link_url and (ad.link_url.startswith("http://") or ad.link_url.startswith("https://")):
                safe_link_url = html.escape(ad.link_url, quote=True)
                display_link = ad.link_url
                if len(display_link) > 52:
                    display_link = display_link[:49] + "..."
                safe_display_link = html.escape(display_link)
                destination_html = f"""
                <div class="ad-destination-row">
                    <span class="dest-badge">🔗 Link đích:</span>
                    <a href="{safe_link_url}" target="_blank" rel="noopener noreferrer" class="dest-link" title="{safe_link_url}">{safe_display_link}</a>
                </div>
                """

            safe_cta_target = safe_link_url if safe_link_url else safe_snapshot

            # Ưu tiên sử dụng local media đã tải về nếu có
            local_video = None
            local_images = []
            if ad.local_media_paths:
                for lp in ad.local_media_paths:
                    p = Path(lp)
                    try:
                        rel_p = os.path.relpath(p, self.output_dir).replace("\\", "/")
                    except Exception:
                        rel_p = str(p).replace("\\", "/")
                    if p.suffix.lower() in (".mp4", ".webm"):
                        local_video = rel_p
                    elif p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                        local_images.append(rel_p)

            # Làm sạch và loại bỏ trùng lặp danh sách media URLs
            clean_media = []
            seen_m = set()
            for li in local_images:
                if li not in seen_m:
                    seen_m.add(li)
                    clean_media.append(li)
            for u in ad.media_urls:
                if u and u.strip() and u.strip() not in seen_m:
                    if u.startswith("http://") or u.startswith("https://") or "/" in u or "\\" in u:
                        seen_m.add(u.strip())
                        clean_media.append(u.strip())

            # Xử lý Media Player & Gallery
            media_html = ""
            if ad.media_type == "video":
                video_url = local_video or next((u for u in clean_media if ".mp4" in u.lower() or "video" in u.lower()), None)
                poster_url = next((u for u in clean_media if u != video_url and any(ext in u.lower() for ext in (".jpg", ".jpeg", ".png", ".webp"))), None)

                if video_url:
                    safe_v_url = html.escape(video_url, quote=True)
                    poster_attr = f' poster="{html.escape(poster_url, quote=True)}"' if poster_url else ""
                    offline_badge = '<span class="local-badge">💾 Offline MP4</span>' if local_video else ""
                    media_html = f"""
                    <div class="ad-media-box video-box">
                        <video controls playsinline preload="metadata" referrerpolicy="no-referrer" class="ad-media-player"{poster_attr}>
                            <source src="{safe_v_url}" type="video/mp4">
                            Trình duyệt không hỗ trợ thẻ video HTML5.
                        </video>
                        <div class="video-action-strip">
                            <a href="{safe_v_url}" target="_blank" rel="noopener noreferrer" class="btn-video-tab">▶ Mở Video tab mới ↗</a>
                            {offline_badge}
                            <button type="button" class="btn-zoom-video" onclick="openMediaLightbox('{safe_v_url}', 'video', '{safe_page}')">🔍 Phóng to video</button>
                        </div>
                    </div>
                    """
                elif clean_media:
                    safe_preview = html.escape(clean_media[0], quote=True)
                    media_html = f"""
                    <div class="ad-media-wrapper">
                        <div class="ad-media-box image-box" onclick="openLightboxFromCard(this)">
                            <img src="{safe_preview}" alt="Video Preview" loading="lazy" referrerpolicy="no-referrer" class="ad-media-img main-carousel-img" onerror="handleMediaError(this, '{safe_snapshot}')">
                            <div class="video-play-badge">▶ Xem Video trên Meta Library ↗</div>
                            <div class="media-fallback" style="display:none;">
                                <span class="fallback-icon">⚠️</span>
                                <span>Video xem trực tiếp trên Meta Ads</span>
                                <a href="{safe_snapshot}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm">Mở Meta Ads Library ↗</a>
                            </div>
                        </div>
                        <div class="video-action-strip">
                            <a href="{safe_snapshot}" target="_blank" rel="noopener noreferrer" class="btn-video-tab">Mở Meta Ads Library ↗</a>
                        </div>
                    </div>
                    """
                else:
                    media_html = f"""
                    <div class="ad-media-box placeholder">
                        <span>🎬 Video quảng cáo (Xem trực tiếp trên Meta Library)</span>
                    </div>
                    """
            elif clean_media:
                main_img = clean_media[0]
                safe_main_img = html.escape(main_img, quote=True)

                thumbnails_strip = ""
                if len(clean_media) > 1:
                    thumbs_html = []
                    for t_idx, t_url in enumerate(clean_media[:16]):
                        safe_t = html.escape(t_url, quote=True)
                        active_cls = " active" if t_idx == 0 else ""
                        thumbs_html.append(
                            f'<div class="carousel-thumb{active_cls}" onclick="switchCarouselImage(this, \'{safe_t}\')">'
                            f'<img src="{safe_t}" alt="Thumbnail {t_idx+1}" loading="lazy" referrerpolicy="no-referrer" class="thumb-img" onerror="this.parentElement.style.display=\'none\'">'
                            f'</div>'
                        )
                    thumbnails_strip = f"""
                    <div class="carousel-strip-container">
                        <div class="carousel-strip-header">
                            <span class="carousel-label">📸 Album Carousel ({len(clean_media)} ảnh)</span>
                            <span class="carousel-hint">Click đổi ảnh</span>
                        </div>
                        <div class="carousel-thumbnails-strip">
                            {''.join(thumbs_html)}
                        </div>
                    </div>
                    """

                media_html = f"""
                <div class="ad-media-wrapper">
                    <div class="ad-media-box image-box" onclick="openLightboxFromCard(this)">
                        <img src="{safe_main_img}" alt="Ad Preview" loading="lazy" referrerpolicy="no-referrer" class="ad-media-img main-carousel-img" onerror="handleMediaError(this, '{safe_snapshot}')">
                        <div class="zoom-hint-badge">🔍 Click phóng to</div>
                        <div class="media-fallback" style="display:none;">
                            <span class="fallback-icon">⚠️</span>
                            <span>Ảnh không tải được hoặc đã hết hạn trên CDN Facebook</span>
                            <a href="{safe_snapshot}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm">Mở Meta Ads Library ↗</a>
                        </div>
                    </div>
                    {thumbnails_strip}
                </div>
                """
            else:
                media_html = """
                <div class="ad-media-box placeholder">
                    <span>📝 Quảng cáo bài viết định dạng văn bản</span>
                </div>
                """

            # Xử lý Landing Page Spy Insights nếu có
            lp_html = ""
            if ad.landing_page_data:
                lpd = ad.landing_page_data
                prices = lpd.get("prices") or []
                offers = lpd.get("offers") or []
                has_form = lpd.get("has_phone_form") or False
                buttons = lpd.get("buttons") or []
                lp_title = html.escape(lpd.get("title") or "")

                prices_str = html.escape(", ".join(prices[:5])) if prices else ""
                offers_str = html.escape(" | ".join(offers[:4])) if offers else ""
                buttons_str = html.escape(" | ".join(buttons[:4])) if buttons else ""

                form_badge = '<span class="lp-tag form-tag">📋 Chốt đơn Form SĐT</span>' if has_form else ''
                price_badge = f'<div class="lp-info-row"><strong>💰 Giá:</strong> <span class="lp-price-val">{prices_str}</span></div>' if prices_str else ''
                offer_badge = f'<div class="lp-info-row"><strong>🎁 Ưu đãi:</strong> <span>{offers_str}</span></div>' if offers_str else ''
                cta_badge = f'<div class="lp-info-row"><strong>⚡ Nút CTA:</strong> <span>{buttons_str}</span></div>' if buttons_str else ''

                lp_html = f"""
                <div class="ad-lp-box">
                    <div class="lp-box-title">
                        <span>🎯 Landing Page Spy Insights</span>
                        {form_badge}
                    </div>
                    {f'<div class="lp-page-title">{lp_title}</div>' if lp_title else ''}
                    {price_badge}
                    {offer_badge}
                    {cta_badge}
                </div>
                """

            vip_badge = ""
            card_class = "ad-card"
            if is_vip:
                card_class += " winning-card"
                vip_badge = """<span class="badge badge-vip">🔥 ĐANG VÍT KHỦNG</span>"""

            if safe_avatar:
                avatar_html = f"""<img src="{safe_avatar}" class="page-avatar" alt="Avatar" referrerpolicy="no-referrer">"""
            else:
                initial = safe_page[0].upper() if safe_page else "F"
                avatar_html = f"""<div class="page-avatar-placeholder">{initial}</div>"""

            cards_html.append(f"""
            <div class="{card_class}" data-media="{html.escape(ad.media_type)}" data-winning="{'true' if is_vip else 'false'}">
                <div class="card-header">
                    <div class="page-info">
                        {avatar_html}
                        <div>
                            <div class="page-name-row">
                                <span class="page-title">{safe_page}</span>
                                {vip_badge}
                            </div>
                            <div class="ad-meta-sub">Được tài trợ • Bắt đầu {html.escape(ad.start_date)} ({ad.days_active} ngày) • {ad.variant_count} nhóm ads</div>
                        </div>
                    </div>
                </div>

                <div class="card-body-text">
                    <p class="body-content">{linked_body}</p>
                </div>

                {media_html}

                {destination_html}

                {lp_html}

                <div class="ad-action-bar">
                    <div class="ad-action-info">
                        <div class="ad-caption-text">{safe_caption}</div>
                        <div class="ad-headline-text">{safe_title}</div>
                    </div>
                    <a href="{safe_cta_target}" target="_blank" rel="noopener noreferrer" class="btn btn-cta">{safe_cta}</a>
                </div>

                <div class="ai-analysis-drawer">
                    <div class="analysis-tag-grid">
                        <div class="tag-item"><span class="tag-label">🎯 Hook:</span> <span class="tag-val">{safe_hook_type}</span></div>
                        <div class="tag-item"><span class="tag-label">💡 Angle:</span> <span class="tag-val">{safe_angle}</span></div>
                        <div class="tag-item"><span class="tag-label">🎁 Offer:</span> <span class="tag-val">{safe_offer}</span></div>
                        <div class="tag-item"><span class="tag-label">⭐ Điểm:</span> <span class="tag-val score">{safe_score}/10</span></div>
                    </div>
                </div>

                <div class="card-footer-buttons">
                    <button class="btn btn-secondary copy-btn" onclick="copyCardContent(this)">📋 Sao Chép Copy-Ads</button>
                    <a href="{safe_snapshot}" target="_blank" rel="noopener noreferrer" class="btn btn-outline">Mở Meta Ads Library ↗</a>
                </div>
            </div>
            """)

        safe_target_url = (
            html.escape(report.target_url)
            if report.target_url and (report.target_url.startswith("http://") or report.target_url.startswith("https://"))
            else "#"
        )

        html_template = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <title>Meta Ads Scout Dashboard — {html.escape(report.keyword)}</title>
    <style>
        :root {{
            --bg-color: #0b0c10;
            --surface: #13151b;
            --surface-card: #181b24;
            --surface-card-hover: #1f232e;
            --border: rgba(255, 255, 255, 0.08);
            --border-vip: rgba(255, 107, 0, 0.4);
            --primary: #0071e3;
            --primary-glow: rgba(0, 113, 227, 0.3);
            --accent-vip: #ff6b00;
            --text-main: #f5f5f7;
            --text-sub: #86868b;
            --success: #30d158;
            --font-stack: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-stack);
            line-height: 1.5;
            padding: 24px;
            -webkit-font-smoothing: antialiased;
        }}

        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* Header Gradient */
        .dash-header {{
            background: linear-gradient(135deg, rgba(24, 27, 36, 0.8) 0%, rgba(11, 12, 16, 0.95) 100%);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 28px 32px;
            backdrop-filter: blur(20px);
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .header-title-group h1 {{
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .keyword-pill {{
            background: var(--primary-glow);
            color: #60a5fa;
            font-size: 14px;
            font-weight: 500;
            padding: 4px 12px;
            border-radius: 12px;
            border: 1px solid rgba(96, 165, 250, 0.3);
        }}

        .header-subtitle {{
            color: var(--text-sub);
            font-size: 13px;
            margin-top: 6px;
        }}

        /* Metric Cards */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .metric-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }}

        .metric-label {{
            font-size: 13px;
            color: var(--text-sub);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            margin-top: 6px;
            color: var(--text-main);
        }}

        .metric-value.highlight {{
            color: var(--accent-vip);
        }}

        .metric-value.success {{
            color: var(--success);
        }}

        /* Control & Filter Bar */
        .control-bar {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 12px 18px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .filter-group {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            color: var(--text-sub);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .filter-btn:hover, .filter-btn.active {{
            background: var(--primary);
            color: #fff;
            border-color: var(--primary);
        }}

        .search-box {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 6px 16px;
            color: #fff;
            font-size: 13px;
            min-width: 240px;
            outline: none;
        }}

        .search-box:focus {{
            border-color: var(--primary);
        }}

        /* Ads Feed Grid */
        .ads-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 24px;
        }}

        @media (max-width: 768px) {{
            .ads-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Facebook Mock Feed Card */
        .ad-card {{
            background: var(--surface-card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            transition: transform 0.2s ease, border-color 0.2s ease;
            position: relative;
        }}

        .ad-card:hover {{
            border-color: rgba(255, 255, 255, 0.18);
            transform: translateY(-2px);
        }}

        .ad-card.winning-card {{
            border-color: var(--border-vip);
            box-shadow: 0 4px 20px rgba(255, 107, 0, 0.08);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .page-info {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .page-avatar {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            object-fit: cover;
            border: 1px solid var(--border);
        }}

        .page-avatar-placeholder {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: var(--primary);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }}

        .page-name-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .page-title {{
            font-weight: 600;
            font-size: 15px;
            color: #fff;
        }}

        .badge {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 10px;
        }}

        .badge-vip {{
            background: rgba(255, 107, 0, 0.2);
            color: #ff9248;
            border: 1px solid rgba(255, 107, 0, 0.4);
        }}

        .ad-meta-sub {{
            font-size: 12px;
            color: var(--text-sub);
            margin-top: 2px;
        }}

        .card-body-text {{
            font-size: 14px;
            color: #e5e5e7;
            white-space: pre-line;
            max-height: 140px;
            overflow-y: auto;
            padding-right: 6px;
        }}

        .card-body-text::-webkit-scrollbar {{
            width: 4px;
        }}
        .card-body-text::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
        }}

        /* Hyperlinks in body text */
        .post-url-link {{
            color: #60a5fa;
            text-decoration: underline;
            text-underline-offset: 3px;
            word-break: break-all;
            transition: color 0.15s ease;
        }}
        .post-url-link:hover {{
            color: #93c5fd;
        }}

        /* Destination Link Row */
        .ad-destination-row {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
        }}

        .dest-badge {{
            color: #93c5fd;
            font-weight: 600;
            white-space: nowrap;
        }}

        .dest-link {{
            color: #60a5fa;
            text-decoration: none;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            transition: color 0.15s ease;
        }}
        .dest-link:hover {{
            color: #bfdbfe;
            text-decoration: underline;
        }}

        /* Landing Page Spy Box */
        .ad-lp-box {{
            background: rgba(0, 113, 227, 0.08);
            border: 1px solid rgba(0, 113, 227, 0.25);
            border-radius: 8px;
            padding: 10px 12px;
            margin: 6px 16px;
            font-size: 13px;
        }}
        .lp-box-title {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: 600;
            color: #5ac8fa;
            margin-bottom: 4px;
        }}
        .lp-page-title {{
            font-size: 12px;
            color: var(--text-sub);
            margin-bottom: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .lp-info-row {{
            margin-top: 3px;
            line-height: 1.4;
            color: #d1d1d6;
        }}
        .lp-price-val {{
            color: #ff9f0a;
            font-weight: 600;
        }}
        .lp-tag.form-tag {{
            background: rgba(48, 209, 88, 0.2);
            color: #30d158;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .local-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: rgba(48, 209, 88, 0.15);
            border: 1px solid rgba(48, 209, 88, 0.3);
            color: #30d158;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}

        /* Media Box & Player */
        .ad-media-wrapper {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            width: 100%;
        }}

        .ad-media-box {{
            width: 100%;
            min-height: 240px;
            border-radius: 12px;
            overflow: hidden;
            background: #000;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid var(--border);
        }}

        .ad-media-box.image-box {{
            cursor: zoom-in;
            max-height: 380px;
        }}

        .ad-media-img {{
            width: 100%;
            height: 100%;
            max-height: 380px;
            object-fit: cover;
            transition: transform 0.25s ease;
        }}

        .ad-media-box.image-box:hover .ad-media-img {{
            transform: scale(1.02);
        }}

        .zoom-hint-badge {{
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: #fff;
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 11px;
            backdrop-filter: blur(8px);
            font-weight: 500;
            border: 1px solid rgba(255, 255, 255, 0.15);
            pointer-events: none;
            transition: all 0.2s ease;
        }}

        .ad-media-box.image-box:hover .zoom-hint-badge {{
            background: rgba(0, 113, 227, 0.85);
            border-color: rgba(255, 255, 255, 0.3);
        }}

        .ad-media-box.video-box {{
            height: auto;
            flex-direction: column;
            background: #000;
        }}

        .ad-media-player {{
            width: 100%;
            max-height: 320px;
            object-fit: contain;
            background: #000;
            display: block;
        }}

        .video-action-strip {{
            width: 100%;
            background: rgba(19, 21, 27, 0.95);
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            border-top: 1px solid var(--border);
        }}

        .btn-video-tab, .btn-zoom-video {{
            background: rgba(255, 255, 255, 0.08);
            color: #e5e5e7;
            border: 1px solid var(--border);
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}

        .btn-video-tab:hover, .btn-zoom-video:hover {{
            background: var(--primary);
            color: #fff;
            border-color: var(--primary);
        }}

        .video-play-badge {{
            position: absolute;
            background: rgba(0, 0, 0, 0.75);
            color: #fff;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            backdrop-filter: blur(8px);
            font-weight: 600;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}

        /* Carousel Strip */
        .carousel-strip-container {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 8px 10px;
        }}

        .carousel-strip-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: var(--text-sub);
            margin-bottom: 6px;
        }}

        .carousel-label {{
            font-weight: 600;
            color: #93c5fd;
        }}

        .carousel-hint {{
            font-size: 10px;
            color: var(--text-sub);
        }}

        .carousel-thumbnails-strip {{
            display: flex;
            gap: 6px;
            overflow-x: auto;
            padding-bottom: 4px;
        }}

        .carousel-thumbnails-strip::-webkit-scrollbar {{
            height: 4px;
        }}

        .carousel-thumbnails-strip::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
        }}

        .carousel-thumb {{
            flex: 0 0 52px;
            height: 52px;
            border-radius: 8px;
            overflow: hidden;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s ease;
            background: #000;
        }}

        .carousel-thumb:hover {{
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.3);
        }}

        .carousel-thumb.active {{
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }}

        .thumb-img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        /* Fallback on error */
        .media-fallback {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px 16px;
            text-align: center;
            gap: 8px;
            color: var(--text-sub);
            font-size: 12px;
            background: rgba(255, 255, 255, 0.02);
            width: 100%;
            height: 100%;
        }}

        .fallback-icon {{
            font-size: 26px;
        }}

        .ad-media-box.has-error {{
            cursor: default;
        }}

        .ad-media-box.placeholder {{
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-sub);
            font-size: 13px;
            padding: 20px;
            text-align: center;
        }}

        /* Action Bar */
        .ad-action-bar {{
            background: rgba(255, 255, 255, 0.03);
            border-radius: 10px;
            padding: 10px 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }}

        .ad-caption-text {{
            font-size: 11px;
            color: var(--text-sub);
            text-transform: uppercase;
        }}

        .ad-headline-text {{
            font-size: 13px;
            font-weight: 600;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 240px;
        }}

        /* AI Analysis Box */
        .ai-analysis-drawer {{
            background: rgba(0, 113, 227, 0.06);
            border: 1px solid rgba(0, 113, 227, 0.2);
            border-radius: 12px;
            padding: 12px;
        }}

        .analysis-tag-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 6px;
            font-size: 12px;
        }}

        .tag-item {{
            display: flex;
            align-items: baseline;
            gap: 6px;
        }}

        .tag-label {{
            color: #93c5fd;
            font-weight: 600;
            min-width: 60px;
        }}

        .tag-val {{
            color: #e2e8f0;
        }}

        .tag-val.score {{
            color: #facc15;
            font-weight: 700;
        }}

        /* Buttons */
        .card-footer-buttons {{
            display: flex;
            gap: 10px;
            margin-top: 4px;
        }}

        .btn {{
            font-family: inherit;
            font-size: 12px;
            font-weight: 600;
            padding: 8px 14px;
            border-radius: 10px;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: all 0.2s ease;
            border: none;
        }}

        .btn-cta {{
            background: var(--primary);
            color: #fff;
            padding: 6px 14px;
        }}

        .btn-cta:hover {{
            background: #0077ed;
        }}

        .btn-secondary {{
            background: rgba(255, 255, 255, 0.08);
            color: #fff;
            flex: 1;
        }}

        .btn-secondary:hover {{
            background: rgba(255, 255, 255, 0.15);
        }}

        .btn-outline {{
            background: transparent;
            color: var(--text-sub);
            border: 1px solid var(--border);
        }}

        .btn-outline:hover {{
            color: #fff;
            border-color: rgba(255, 255, 255, 0.3);
        }}

        .btn-sm {{
            padding: 4px 10px;
            font-size: 11px;
        }}

        /* Lightbox Modal */
        .media-lightbox {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.88);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            z-index: 9999;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 24px;
            opacity: 0;
            transition: opacity 0.25s ease;
        }}

        .media-lightbox.active {{
            display: flex;
            opacity: 1;
        }}

        .lightbox-dialog {{
            position: relative;
            max-width: 90vw;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: rgba(24, 27, 36, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 20px;
            padding: 16px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.7);
        }}

        .lightbox-close {{
            position: absolute;
            top: -14px;
            right: -14px;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: #1f232e;
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.2);
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            z-index: 10;
        }}

        .lightbox-close:hover {{
            background: #ff453a;
            border-color: #ff453a;
            transform: scale(1.1);
        }}

        .lightbox-content {{
            display: flex;
            align-items: center;
            justify-content: center;
            max-width: 85vw;
            max-height: 80vh;
            overflow: hidden;
        }}

        .lightbox-media-img {{
            max-width: 100%;
            max-height: 80vh;
            object-fit: contain;
            border-radius: 12px;
        }}

        .lightbox-media-video {{
            max-width: 100%;
            max-height: 80vh;
            border-radius: 12px;
            outline: none;
        }}

        .lightbox-caption {{
            margin-top: 10px;
            color: var(--text-main);
            font-size: 13px;
            text-align: center;
        }}

        /* Toast notification */
        #toast {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #30d158;
            color: #000;
            font-weight: 700;
            padding: 12px 24px;
            border-radius: 30px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
            z-index: 1000;
        }}

        #toast.show {{
            opacity: 1;
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- Header -->
        <header class="dash-header">
            <div class="header-title-group">
                <h1>Meta Ads Intelligence Scout <span class="keyword-pill">"{html.escape(report.keyword)}"</span></h1>
                <div class="header-subtitle">
                    Quốc gia: <strong>{html.escape(report.country)}</strong> • Trinh sát lúc: <strong>{html.escape(report.scouted_at)}</strong>
                </div>
            </div>
            <div>
                <a href="{safe_target_url}" target="_blank" rel="noopener noreferrer" class="btn btn-cta">Mở Trực Tiếp Meta Ads Library ↗</a>
            </div>
        </header>

        <!-- Metric Summary Cards -->
        <section class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Tổng Mẫu Quảng Cáo</div>
                <div class="metric-value">{report.total_found}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Quảng Cáo Đang Vít Khủng</div>
                <div class="metric-value highlight">{winning_count}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Tỷ Lệ Hoàn Tất (Coverage)</div>
                <div class="metric-value success">{'100%' if report.coverage.complete else f"{report.coverage.collected}/{report.coverage.requested}"}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Nền Tảng Phổ Biến</div>
                <div class="metric-value">Facebook / Instagram</div>
            </div>
        </section>

        <!-- Filter & Search Bar -->
        <nav class="control-bar">
            <div class="filter-group">
                <button class="filter-btn active" onclick="filterAds('all', this)">Tất cả ({report.total_found})</button>
                <button class="filter-btn" onclick="filterAds('winning', this)">🔥 Đang Vít Khủng ({winning_count})</button>
                <button class="filter-btn" onclick="filterAds('video', this)">🎬 Video Ads</button>
                <button class="filter-btn" onclick="filterAds('image', this)">🖼️ Ảnh & Carousel</button>
            </div>
            <input type="text" class="search-box" id="searchInput" placeholder="Tìm Fanpage, Hook, Offer..." oninput="searchAds(this.value)">
        </nav>

        <!-- Ads Grid -->
        <main class="ads-grid" id="adsGrid">
            {"".join(cards_html)}
        </main>
    </div>

    <!-- Lightbox Modal -->
    <div id="mediaLightbox" class="media-lightbox" onclick="closeMediaLightbox(event)">
        <div class="lightbox-dialog" onclick="event.stopPropagation()">
            <button type="button" class="lightbox-close" onclick="closeMediaLightbox()" title="Đóng (Phím ESC)">✕</button>
            <div id="lightboxContent" class="lightbox-content"></div>
            <div id="lightboxCaption" class="lightbox-caption"></div>
        </div>
    </div>

    <div id="toast">✅ Đã sao chép nội dung quảng cáo!</div>

    <script>
        // Lưu trữ dữ liệu thô an toàn
        const rawReport = {report_json_safe};

        function copyCardContent(btn) {{
            const card = btn.closest('.ad-card');
            const textElem = card ? card.querySelector('.body-content') : null;
            if (!textElem) return;
            const text = textElem.innerText || textElem.textContent;
            navigator.clipboard.writeText(text).then(() => {{
                const toast = document.getElementById('toast');
                if (toast) toast.classList.add('show');
                const originalText = btn.innerHTML;
                btn.innerHTML = '✅ Đã Sao Chép!';
                setTimeout(() => {{
                    if (toast) toast.classList.remove('show');
                    btn.innerHTML = originalText;
                }}, 2000);
            }}).catch(() => {{
                alert('Không thể truy cập clipboard của trình duyệt.');
            }});
        }}

        function filterAds(type, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const cards = document.querySelectorAll('.ad-card');
            cards.forEach(card => {{
                const isWinning = card.getAttribute('data-winning') === 'true';
                const media = card.getAttribute('data-media');

                if (type === 'all') {{
                    card.style.display = 'flex';
                }} else if (type === 'winning') {{
                    card.style.display = isWinning ? 'flex' : 'none';
                }} else if (type === 'video') {{
                    card.style.display = (media === 'video') ? 'flex' : 'none';
                }} else if (type === 'image') {{
                    card.style.display = (media === 'image' || media === 'carousel') ? 'flex' : 'none';
                }}
            }});
        }}

        function searchAds(query) {{
            const q = query.toLowerCase().trim();
            const cards = document.querySelectorAll('.ad-card');
            cards.forEach(card => {{
                const text = card.innerText.toLowerCase();
                card.style.display = text.includes(q) ? 'flex' : 'none';
            }});
        }}

        // Đổi ảnh chính Carousel khi click thumbnail
        function switchCarouselImage(thumbElem, imgUrl) {{
            const card = thumbElem.closest('.ad-card');
            if (!card) return;
            const mainImg = card.querySelector('.main-carousel-img');
            if (mainImg) {{
                mainImg.src = imgUrl;
                mainImg.style.display = 'block';
                const fallback = card.querySelector('.media-fallback');
                if (fallback) fallback.style.display = 'none';
            }}
            const strip = thumbElem.closest('.carousel-thumbnails-strip');
            if (strip) {{
                strip.querySelectorAll('.carousel-thumb').forEach(t => t.classList.remove('active'));
            }}
            thumbElem.classList.add('active');
        }}

        // Lightbox phóng to ảnh / video
        function openMediaLightbox(url, type, title) {{
            const lightbox = document.getElementById('mediaLightbox');
            const container = document.getElementById('lightboxContent');
            const caption = document.getElementById('lightboxCaption');
            if (!lightbox || !container) return;

            container.innerHTML = '';
            if (type === 'video') {{
                const video = document.createElement('video');
                video.src = url;
                video.controls = true;
                video.autoplay = true;
                video.playsInline = true;
                video.setAttribute('referrerpolicy', 'no-referrer');
                video.className = 'lightbox-media-video';
                container.appendChild(video);
            }} else {{
                const img = document.createElement('img');
                img.src = url;
                img.alt = 'Enlarged Preview';
                img.setAttribute('referrerpolicy', 'no-referrer');
                img.className = 'lightbox-media-img';
                container.appendChild(img);
            }}

            if (caption) {{
                caption.innerHTML = title ? `<strong>${{title}}</strong>` : '';
            }}

            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden';
        }}

        function openLightboxFromCard(mediaBox) {{
            if (mediaBox.classList.contains('has-error')) return;
            const img = mediaBox.querySelector('.main-carousel-img');
            if (!img || !img.src) return;
            const card = mediaBox.closest('.ad-card');
            const pageTitle = card ? (card.querySelector('.page-title')?.innerText || '') : '';
            openMediaLightbox(img.src, 'image', pageTitle);
        }}

        function closeMediaLightbox(e) {{
            const lightbox = document.getElementById('mediaLightbox');
            if (!lightbox) return;
            const container = document.getElementById('lightboxContent');
            if (container) {{
                const video = container.querySelector('video');
                if (video) video.pause();
                container.innerHTML = '';
            }}
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        }}

        // Phím ESC đóng Lightbox
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeMediaLightbox();
            }}
        }});

        // Xử lý lỗi tải ảnh từ CDN Facebook
        function handleMediaError(imgElem, snapshotUrl) {{
            imgElem.style.display = 'none';
            const parentBox = imgElem.closest('.ad-media-box');
            if (parentBox) {{
                parentBox.classList.add('has-error');
                const fallback = parentBox.querySelector('.media-fallback');
                if (fallback) fallback.style.display = 'flex';
                const zoomBadge = parentBox.querySelector('.zoom-hint-badge');
                if (zoomBadge) zoomBadge.style.display = 'none';
            }}
        }}
    </script>
</body>
</html>"""

        out_path.write_text(html_template, encoding="utf-8")
        logger.info(f"Đã xuất Dashboard HTML: {out_path}")
        return out_path


# ==============================================================================
# 9. SCOUT ORCHESTRATOR & CLI INTERFACE
# ==============================================================================

def run_meta_ad_scout(
    keyword: str,
    country: str = "VN",
    limit: int = 20,
    sort: str = "total_impressions",
    active_only: bool = True,
    media_type: str = "all",
    output_dir: str | Path = "./output",
    export_format: str = "all",
    seed_mode: bool = False,
    no_analyze: bool = False,
    min_days: int = 14,
    cdp_port: Optional[int] = None,
    loose: bool = False,
    scrape_lp: bool = False,
    download_media: bool = False,
) -> ScoutReport:
    """Điều phối toàn bộ quy trình trinh sát Meta Ads Library."""
    if not (1 <= limit <= 100):
        raise ValueError(f"Tham số --limit phải nằm trong khoảng từ 1 đến 100 (nhận được: {limit}).")

    target_url = build_meta_ads_url(keyword, country, sort, active_only, media_type, loose=loose)
    engine = MetaScraperEngine()
    ads, coverage, engine_used = engine.fetch(
        keyword=keyword,
        country=country,
        limit=limit,
        sort=sort,
        active_only=active_only,
        media_type=media_type,
        use_seed_only=seed_mode,
        cdp_port=cdp_port,
        loose=loose,
    )

    # 1. Soi Landing Page nếu bật cờ --scrape-lp
    if scrape_lp and ads:
        lp_data_map = run_node_lp_subprocess(ads, top=min(limit, 10))
        for ad in ads:
            if ad.id in lp_data_map:
                ad.landing_page_data = lp_data_map[ad.id]
            elif ad.link_url and ad.link_url in lp_data_map:
                ad.landing_page_data = lp_data_map[ad.link_url]

    # 2. Tải media offline nếu bật cờ --download-media
    if download_media and ads:
        dl_map = run_node_download_subprocess(ads, output_dir=Path(output_dir), top=min(limit, 10))
        for ad in ads:
            if ad.id in dl_map:
                ad.local_media_paths = dl_map[ad.id]

    analyses = {}
    if not no_analyze:
        analyzer = CreativeAngleAnalyzer()
        for ad in ads:
            analyses[ad.id] = analyzer.analyze(ad)

    report = ScoutReport(
        keyword=keyword,
        country=country.upper(),
        scouted_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target_url=target_url,
        total_found=len(ads),
        coverage=coverage,
        ads=ads,
        analyses=analyses,
    )

    exporter = ReportExporter(output_dir)
    if export_format in ("json", "all"):
        exporter.export_json(report)
    if export_format in ("md", "all"):
        exporter.export_markdown(report, min_days=min_days)
    if export_format in ("html", "all"):
        exporter.export_html(report, min_days=min_days)

    return report


def build_cli_parser() -> argparse.ArgumentParser:
    """Xây dựng CLI ArgumentParser tuân thủ đặc tả kỹ thuật AC-01."""
    parser = argparse.ArgumentParser(
        prog="meta_ads_scout.py",
        description="Meta Ads Library Competitor Intelligence & Creative Angle Scout CLI.",
    )
    parser.add_argument(
        "--keyword", "-k",
        type=str,
        default="sơ sinh",
        help="Từ khóa tìm kiếm trên Meta Ads Library (ví dụ: 'sơ sinh', 'thực phẩm chức năng').",
    )
    parser.add_argument(
        "--country", "-c",
        type=str,
        default="VN",
        help="Mã quốc gia ISO Alpha-2 (mặc định: VN).",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Số lượng mẫu quảng cáo tối đa cần thu thập (mặc định: 20).",
    )
    parser.add_argument(
        "--sort",
        type=str,
        default="total_impressions",
        choices=["total_impressions", "new", "relevance", "start_date"],
        help="Tiêu chí sắp xếp Meta Ads Library (mặc định: total_impressions).",
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=14,
        help="Số ngày chạy tối thiểu để đánh giá Winning Ad (mặc định: 14 ngày).",
    )
    parser.add_argument(
        "--media-type",
        type=str,
        default="all",
        choices=["all", "image", "video", "meme"],
        help="Bộ lọc định dạng media (mặc định: all).",
    )
    parser.add_argument(
        "--active-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Chỉ lấy quảng cáo đang hoạt động (mặc định: True, dùng --no-active-only để tắt).",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="all",
        choices=["json", "md", "html", "all"],
        help="Định dạng báo cáo xuất ra (mặc định: all).",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./output",
        help="Thư mục lưu trữ kết quả đầu ra (mặc định: ./output).",
    )
    parser.add_argument(
        "--seed", "--seed-only",
        dest="seed",
        action="store_true",
        default=False,
        help="Chạy ở chế độ Demo Seed tức thì không cần kết nối mạng.",
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        default=False,
        help="Tắt module phân tích AI Hook / Offer / Angle.",
    )
    parser.add_argument(
        "--cdp-port",
        type=int,
        default=None,
        help="Cổng Chrome DevTools Protocol (ví dụ: 9222) để gắn vào Chrome đang chạy sẵn với --remote-debugging-port.",
    )
    parser.add_argument(
        "--loose",
        action="store_true",
        default=False,
        help="Tìm kiếm mở rộng không ép cụm từ chính xác (keyword_unordered).",
    )
    parser.add_argument(
        "--scrape-lp",
        action="store_true",
        default=False,
        help="Bật tính năng tự động soi Landing Page bằng Playwright Mobile.",
    )
    parser.add_argument(
        "--download-media",
        action="store_true",
        default=False,
        help="Tự động tải toàn bộ hình ảnh và video về ổ cứng để xem offline tránh link CDN chết.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="In kết quả dạng JSON ra standard output.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_cli_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    fmt = "json" if args.json else args.format
    try:
        report = run_meta_ad_scout(
            keyword=args.keyword,
            country=args.country,
            limit=args.limit,
            sort=args.sort,
            active_only=args.active_only,
            media_type=args.media_type,
            output_dir=args.output_dir,
            export_format=fmt,
            seed_mode=args.seed,
            no_analyze=args.no_analyze,
            min_days=args.min_days,
            cdp_port=args.cdp_port,
            loose=args.loose,
            scrape_lp=args.scrape_lp,
            download_media=args.download_media,
        )
    except ValueError as e:
        logger.error(f"Lỗi tham số đầu vào: {e}")
        print(f"[ERROR] Tham số không hợp lệ: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error(f"Lỗi thực thi Meta Ads Scout: {e}")
        print(f"[ERROR] Không thể hoàn thành trinh sát: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2))
    else:
        print("\n========================================================")
        print(f"[OK] THANH CONG: Da trinh sat xong tu khoa '{report.keyword}'")
        print(f"- Tong so mau tim thay: {report.total_found}")
        print(f"- Thu muc bao cao: {args.output_dir}")
        print(f"- URL Meta Ads Library: {report.target_url}")
        print("========================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
