"""Test chất lượng skill marketing: định tuyến, rào chắn sự thật, đường dẫn.

Bộ test này chặn hồi quy cho đợt audit logic/hiệu quả áp dụng:
- Định tuyến phải bắt được cách nói thường ngày của người Việt (không để rơi về None).
- Skill sinh nội dung phải có rào chắn chống bịa số liệu.
- Không được tồn tại câu cho phép agent tự suy diễn số liệu.
- Skill xuất số liệu phải có quy tắc xử lý lỗi/thiếu dữ liệu.
- Không còn đường dẫn cũ `skills/marketing/...`.
"""

import json
import re
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
    ("kênh nào đang làm rớt phễu chuyển đổi", "framework-marketing-da-kenh"),
    ("phễu marketing của tôi đang tắc ở đâu", "framework-marketing-da-kenh"),
    ("ma trận kênh marketing", "framework-marketing-da-kenh"),
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
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts or ".gitnexus" in path.parts or path.name == Path(__file__).name:
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


# ================= Phase B: tích hợp & hiệu quả áp dụng =================

def test_traffic_da_tach_reference_va_khong_tro_treo():
    """Skill lớn phải tách sang references/ (progressive disclosure) và con trỏ phải sống."""
    sk = MK / "traffic-secrets-playbook"
    text = (sk / "SKILL.md").read_text(encoding="utf-8")
    assert len(text) < 16000, f"SKILL.md còn quá lớn: {len(text)} ký tự"
    for name in ["frameworks.md", "templates.md", "channel-lookup.md"]:
        ref = sk / "references" / name
        assert ref.exists(), f"Thiếu references/{name}"
        assert name in text, f"SKILL.md không trỏ tới references/{name} (con trỏ treo)"
    # mọi file trong references/ phải được SKILL.md nhắc tới
    for ref in (sk / "references").iterdir():
        assert ref.name in text, f"references/{ref.name} không được SKILL.md tham chiếu"


CONTENT_SKILLS_RUBRIC = [
    "cong-thuc-viet-content-by-noti-v4",
    "kahneman-creative-ads",
    "viet-content-seo-geo-v5",
    "boc-phot-storytelling",
    "traffic-secrets-playbook",
    "check-youtube-policy",
    "framework-marketing-da-kenh",
]


@pytest.mark.parametrize("skill", CONTENT_SKILLS_RUBRIC)
def test_skill_noi_dung_noi_voi_rubric_tuan_thu(skill):
    """Skill sinh nội dung phải tự đối chiếu rubric compliance trước khi trả bản final."""
    text = (MK / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "content_compliance_rubric" in text, f"{skill} chưa nối với rubric tuân thủ"


SKILL_SIBLINGS = {
    "cong-thuc-viet-content-by-noti-v4": ["viet-content-seo-geo-v5", "kahneman-creative-ads"],
    "kahneman-creative-ads": ["cong-thuc-viet-content-by-noti-v4", "meta-ads-analyzer-mod-by-noti"],
    "viet-content-seo-geo-v5": ["cong-thuc-viet-content-by-noti-v4", "traffic-secrets-playbook"],
    "boc-phot-storytelling": ["check-youtube-policy", "yt-competitor-analyzer"],
}


@pytest.mark.parametrize("skill,siblings", SKILL_SIBLINGS.items())
def test_skill_co_muc_route_truoc(skill, siblings):
    """Skill chồng chéo chức năng phải nói rõ khi nào dùng skill khác thay thế."""
    text = (MK / skill / "SKILL.md").read_text(encoding="utf-8")
    assert "## Route trước" in text, f"{skill} thiếu mục Route trước"
    for sib in siblings:
        assert sib in text, f"{skill} không nhắc tới skill thay thế {sib}"


def test_fb_admin_co_hop_dong_output_va_xu_ly_loi():
    text = (MK / "fb-admin" / "SKILL.md").read_text(encoding="utf-8")
    assert "Output Contract" in text, "fb-admin thiếu hợp đồng đầu ra"
    assert "post_id" in text, "fb-admin thiếu yêu cầu chứng cứ post_id"
    for code in ["190", "200", "613"]:
        assert code in text, f"fb-admin thiếu mã lỗi Graph API {code}"
    assert "đăng lại" in text, "fb-admin thiếu quy tắc chống đăng trùng"


# ================= Skill MCP (framework-marketing-da-kenh) =================

MCP_SKILL = "framework-marketing-da-kenh"
MCP_SCHEMA = MK / MCP_SKILL / "references" / "mcp-tools-schema.json"


def test_mcp_schema_da_duoc_chup_va_du_8_tool():
    """Schema phải là bản chụp thật từ server: đủ 8 tool + có bằng chứng gọi thử."""
    assert MCP_SCHEMA.exists(), "Thiếu references/mcp-tools-schema.json"
    d = json.loads(MCP_SCHEMA.read_text(encoding="utf-8"))
    names = [x["name"] for x in d["tools"]]
    assert len(names) == 8, f"Schema ghi {len(names)} tool, mong đợi 8"
    assert all(n.startswith("framework_") for n in names)
    assert d["_da_goi_that"] and all(v["ok"] for v in d["_da_goi_that"].values()), "Chưa gọi thử thành công đủ tool"


def test_tai_lieu_mcp_khop_schema_that():
    """SKILL.md phải mô tả đúng tên tham số của server — sai tên là gọi lỗi ngay."""
    text = (MK / MCP_SKILL / "SKILL.md").read_text(encoding="utf-8")
    d = json.loads(MCP_SCHEMA.read_text(encoding="utf-8"))
    # mọi tool trong schema phải được tài liệu nhắc tới
    for tool in d["tools"]:
        assert tool["name"] in text, f"SKILL.md thiếu tool {tool['name']}"
    # Tên tham số sai đã gặp thực tế (server trả "Tham số không hợp lệ") -> không được quay lại.
    # Cho phép duy nhất một ngoại lệ: câu cảnh báo phủ định ("không có tham số X") để người đọc
    # biết mà tránh; mọi chỗ khác đều là lỗi.
    for wrong in ["phase_id", "channel_id", "channel_name", "block_id", "from_block", "to_block", "business_type"]:
        for m in re.finditer(re.escape(wrong), text):
            ctx = text[max(0, m.start() - 45):m.end() + 5].lower()
            assert ("không có" in ctx) or ("không dùng" in ctx), (
                f"SKILL.md dùng tham số sai {wrong!r} ngoài ngữ cảnh cảnh báo: …{ctx.strip()[-60:]}")
    # tên đúng + tham số tuỳ chọn phải có
    for right in ["`phase`", "`channel`", "`block`", "`limit`", "`maxSteps`", "`topic`"]:
        assert right in text, f"SKILL.md thiếu tham số đúng {right}"


def test_mcp_skill_co_quy_tac_loi_va_du_phong():
    text = (MK / MCP_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "Không mô phỏng kết quả tool" in text, "Thiếu lệnh cấm mô phỏng kết quả khi chưa có MCP"
    assert "khung tĩnh" in text, "Thiếu mô tả chế độ dự phòng bằng khung tĩnh"
    assert "nguyên văn" in text.lower(), "Thiếu yêu cầu dán nguyên văn lỗi"


def test_mcp_skill_co_hop_dong_output_va_cam_ghep_url():
    text = (MK / MCP_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "cấm tự ghép URL" in text, "Thiếu lệnh cấm tự ghép URL sơ đồ"
    assert "Hợp Đồng Đầu Ra" in text
    assert "`counts`" in text, "Thiếu yêu cầu lấy số liệu từ counts của server"


def test_mcp_skill_co_route_va_rubric():
    text = (MK / MCP_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "## 8. Route Trước Khi Làm" in text
    for sib in ["traffic-secrets-playbook", "kahneman-creative-ads", "meta-ads-analyzer-mod-by-noti"]:
        assert sib in text, f"Thiếu skill anh em {sib} trong mục Route"
    assert "content_compliance_rubric" in text
