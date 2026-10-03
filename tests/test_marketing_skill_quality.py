"""Test chất lượng skill marketing: định tuyến, rào chắn sự thật, đường dẫn.

Bộ test này chặn hồi quy cho đợt audit logic/hiệu quả áp dụng:
- Định tuyến phải bắt được cách nói thường ngày của người Việt (không để rơi về None).
- Skill sinh nội dung phải có rào chắn chống bịa số liệu.
- Không được tồn tại câu cho phép agent tự suy diễn số liệu.
- Skill xuất số liệu phải có quy tắc xử lý lỗi/thiếu dữ liệu.
- Không còn đường dẫn cũ `skills/marketing/...`.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MK = REPO / "plugins" / "marketing" / "skills"
CONFIG = json.loads((REPO / "configs" / "harness_config.json").read_text(encoding="utf-8"))
ROUTING = CONFIG["skill_routing"]

# 16 yêu cầu thật (cách nói thường ngày), kèm skill phải định tuyến tới
REAL_REQUESTS = [
    ("viết content bán khóa học cho mẹ bỉm", "cong-thuc-viet-content-by-noti-v4"),
    ("viết caption facebook cho quán cà phê", "cong-thuc-viet-content-by-noti-v4"),
    ("viết content facebook cho shop mỹ phẩm", "cong-thuc-viet-content-by-noti-v4"),
    ("viết bài quảng cáo cho khóa học tiếng Anh", "cong-thuc-viet-content-by-noti-v4"),
    ("tối ưu SEO bài viết này", "viet-content-seo-geo-v5"),
    ("bài này có lên featured snippet không", "viet-content-seo-geo-v5"),
    ("phân tích tài khoản quảng cáo Meta của tôi", "meta-ads-analyzer-mod-by-noti"),
    ("CPM tăng mà CPA cũng tăng, xử lý sao", "meta-ads-analyzer-mod-by-noti"),
    ("nghĩ góc creative cho quảng cáo mỹ phẩm", "kahneman-creative-ads"),
    ("gợi ý ý tưởng quảng cáo cho app học tiếng Anh", "kahneman-creative-ads"),
    ("lên kế hoạch kéo traffic cho kênh mới", "traffic-secrets-playbook"),
    ("thiết kế offer bán khóa học", "alex-hormozi-offer-builder"),
    ("xây thang sản phẩm và upsell", "alex-hormozi-money-models"),
    ("viết kịch bản tập tiếp theo cho kênh bóc phốt", "boc-phot-storytelling"),
    ("soát kịch bản này có vi phạm chính sách YouTube không", "check-youtube-policy"),
    ("quét kênh đối thủ trên YouTube", "yt-competitor-analyzer"),
    ("đăng bài lên fanpage Doanh Nghiệp", "fb-admin"),
    ("trả lời comment fanpage giúp tôi", "fb-admin"),
]


@pytest.mark.parametrize("request_text,expected", REAL_REQUESTS)
def test_dinh_tuyen_bat_duoc_yeu_cau_that(request_text, expected):
    """Định tuyến phải trả về skill đúng, không được None."""
    from harness.skills.router import SkillRouter

    got = SkillRouter().route(request_text)[0]
    assert got == expected, f"{request_text!r} -> {got!r} (mong đợi {expected!r})"


def test_khong_co_keyword_trung_lap():
    all_kw = [k.lower() for d in ROUTING.values() for k in d.get("keywords", [])]
    dup = [k for k, c in Counter(all_kw).items() if c > 1]
    assert dup == [], f"Keyword trùng giữa các skill: {dup}"


# Skill sinh nội dung/số liệu => BẮT BUỘC có rào chắn chống bịa
CONTENT_SKILLS = [
    "cong-thuc-viet-content-by-noti-v4",
    "traffic-secrets-playbook",
    "kahneman-creative-ads",
    "alex-hormozi-offer-builder",
    "alex-hormozi-money-models",
]

BANNED_PHRASES = [
    "tự suy luận hợp lý từ ngữ cảnh, ghi chú giả định",  # F1: câu cho phép tự suy diễn
]


@pytest.mark.parametrize("skill", CONTENT_SKILLS)
def test_skill_noi_dung_co_rao_chan_bia(skill):
    text = (MK / skill / "SKILL.md").read_text(encoding="utf-8").lower()
    markers = ["placeholder", "không được tự", "số liệu thật", "giả định", "bịa"]
    hits = [m for m in markers if m in text]
    assert len(hits) >= 2, f"{skill} thiếu rào chắn chống bịa (chỉ thấy {hits})"


@pytest.mark.parametrize("skill", CONTENT_SKILLS)
def test_skill_noi_dung_khong_cho_phep_suy_dien_tu_do(skill):
    text = (MK / skill / "SKILL.md").read_text(encoding="utf-8")
    for phrase in BANNED_PHRASES:
        assert phrase not in text, f"{skill} vẫn còn câu bị cấm: {phrase!r}"


def test_skill_xuat_so_lieu_co_quy_tac_thieu_du_lieu():
    """Skill xuất bảng số liệu phải nói rõ phải làm gì khi lỗi/thiếu dữ liệu."""
    for skill in ["yt-competitor-analyzer", "meta-ads-analyzer-mod-by-noti"]:
        text = (MK / skill / "SKILL.md").read_text(encoding="utf-8").lower()
        assert ("n/a" in text or "không có dữ liệu" in text), f"{skill} thiếu quy tắc ghi N/A"
        assert ("lỗi" in text or "error" in text or "fail" in text), f"{skill} thiếu quy tắc xử lý lỗi"


def test_check_youtube_khong_phong_dai_nguon_tri_thuc():
    text = (MK / "check-youtube-policy" / "SKILL.md").read_text(encoding="utf-8")
    assert "50 tài liệu chính sách chính thức`, đóng gói" not in text, "Vẫn còn tuyên bố sai về nguồn"
    assert "KHÔNG được đóng gói trong repo" in text or "KHÔNG được đóng gói kèm" in text
    assert "KHÔNG tự sinh mã chính sách" in text, "Thiếu ràng buộc không tự sinh mã chính sách"


def test_khong_con_duong_dan_cu_skills_marketing():
    """Đường dẫn cũ `skills/marketing/...` phải được sửa hết (repo đã chuyển sang plugins/)."""
    bad = []
    for path in REPO.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.name == Path(__file__).name:
            continue
        if path.suffix not in {".md", ".py", ".js", ".json", ".mjs"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "skills/marketing/" in line:
                bad.append(f"{path.relative_to(REPO)}:{i}")
    assert bad == [], f"Còn đường dẫn cũ: {bad}"
