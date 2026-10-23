#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Policy Auditor CLI & Engine
Screens text using local keyword heuristics; does not issue a platform verdict.
Includes comprehensive YouTube Community Guidelines, Advertiser Guidelines,
and the latest YouTube AI Policies & Likeness Protection standards.
"""

import sys
import os
import re
import argparse
import json

# Force UTF-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Policy Rules Definition
POLICIES = {
    # 01_Kiem_Tien_Va_YPP & 04_Noi_Dung_Nhay_Cam_Va_Bao_Luc
    "PROFANITY_STRONG": {
        "id": "10072685",
        "title": "Chính sách về ngôn từ thô tục & 6162278 (Nhà quảng cáo)",
        "category": "Ngôn từ thô tục nặng (Severe Profanity)",
        "regex": r"\b(đ[ụịịt]\s*(mẹ|m|mày)?|đm|đ[éẹ]o|vãi\s*l[ồôò]n|vkl|vl|clgt|c[ặa]c|l[ồôò]n|buồi|fuck|shit|motherfucker|bitch|cunt)\b",
        "severity": "HIGH",
        "penalty_7s": "CRITICAL",
        "advice": "Loại bỏ hoàn toàn hoặc thay bằng từ biểu cảm nhẹ nhàng, chèn hiệu ứng BEEP và đẩy ra sau 7 giây đầu."
    },
    "PROFANITY_MODERATE": {
        "id": "10072685",
        "title": "Chính sách về ngôn từ thô tục",
        "category": "Ngôn từ thô tục vừa (Moderate Profanity)",
        "regex": r"\b(chết\s*tiệt|mẹ\s*kiếp|đồ\s*khốn|đồ\s*chó|thằng\s*chó|con\s*đĩ|đồ\s*súc\s*vật|đồ\s*ngu|đồ\s*rác\s*rưởi|asshole|bastard)\b",
        "severity": "MEDIUM",
        "penalty_7s": "HIGH",
        "advice": "Tránh lặp lại quá nhiều lần; tuyệt đối không đặt trong tiêu đề hoặc 7 giây đầu."
    },
    "VIOLENCE_GORE": {
        "id": "2802008",
        "title": "Chính sách về nội dung bạo lực hoặc phản cảm",
        "category": "Bạo lực máu me & Phản cảm (Violence & Gore)",
        "regex": r"\b(thảm\s*sát|chặt\s*xác|phanh\s*thây|chém\s*đứt\s*(đầu|cổ|tay|chân)|máu\s*me\s*be\s*bét|máu\s*chảy\s*lênh\s*láng|ruột\s*gan|nội\s*tạng|xác\s*chết\s*thối\s*rữa|tra\s*tấn\s*dã\s*man|chém\s*chết|đâm\s*chết|bắn\s*nát\s*đầu)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Thay thế bằng thuật ngữ pháp y/hình sự trung lập: 'tước đoạt mạng sống', 'thương tích nghiêm trọng', 'phi tang dấu vết'."
    },
    "SUICIDE_SELF_HARM": {
        "id": "2802245",
        "title": "Chính sách về hành vi tự tử, tự huỷ hoại bản thân & rối loạn ăn uống",
        "category": "Tự tử & Tự hại (Suicide & Self-Harm)",
        "regex": r"\b(tự\s*tử|tự\s*sát|cắt\s*cổ\s*tay|uống\s*thuốc\s*ngủ\s*tự\s*tử|treo\s*cổ\s*tự\s*tử|nhảy\s*cầu\s*tự\s*tử|ép\s*nôn|nhịn\s*ăn\s*ép\s*cân)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Không miêu tả phương thức tự hại. Chuyển sang 'hành vi tiêu cực', 'sự cố đáng tiếc' và BẮT BUỘC chèn Hotline hỗ trợ tâm lý."
    },
    "FIREARMS_WEAPONS": {
        "id": "7667605",
        "title": "Chính sách về súng cầm tay & vũ khí nguy hiểm",
        "category": "Vũ khí nóng & Súng cầm tay (Firearms)",
        "regex": r"\b(chế\s*tạo\s*súng|in\s*3d\s*súng|độ\s*súng\s*liên\s*thanh|bán\s*súng|súng\s*lục|súng\s*tự\s*chế|chế\s*bom|chế\s*chất\s*nổ|chế\s*pháo|mua\s*súng\s*lậu)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Chuyển sang 'vũ khí nóng', 'công cụ tác chiến', 'vật liệu nguy hiểm' trong bối cảnh phân tích điều tra pháp luật."
    },
    "HATE_SPEECH": {
        "id": "2801939",
        "title": "Chính sách về lời nói hận thù (Hate Speech)",
        "category": "Kích động thù hận & Miệt thị (Hate Speech)",
        "regex": r"\b(bọn\s*(bắc\s*kỳ|nam\s*kỳ|trung\s*kỳ)|đồ\s*mọi\s*rợ|bọn\s*hạ\s*đẳng|bọn\s*bê\s*đê|bọn\s*xăng\s*pha\s*nhớt|xóa\s*sổ\s*chủng\s*tộc)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Xóa bỏ 100%. YouTube có chính sách không khoan nhượng (Zero-tolerance) đối với thù hận và miệt thị vùng miền/chủng tộc."
    },
    "SEXUAL_CONTENT": {
        "id": "2802002",
        "title": "Chính sách về ảnh khoả thân và nội dung tình dục",
        "category": "Nội dung người lớn & Tình dục (Adult Content)",
        "regex": r"\b(hiếp\s*dâm|cưỡng\s*hiếp|làm\s*tình|giao\s*cấu|thủ\s*dâm|khiêu\s*dâm|lộ\s*clip\s*nóng|audio\s*truyện\s*sex|gạ\s*tình|bán\s*dâm|mại\s*dâm)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Thay bằng 'hành vi xâm hại thân thể', 'tiếp xúc thân mật', 'dịch vụ biến tướng'. Cần bổ sung bối cảnh pháp luật rõ ràng."
    },
    "CHILD_SAFETY": {
        "id": "2801999",
        "title": "Chính sách an toàn cho trẻ em (Child Safety)",
        "category": "An toàn cho trẻ em (CSAE & Child Danger)",
        "regex": r"\b(ấu\s*dâm|xâm\s*hại\s*trẻ\s*em|bóc\s*lột\s*trẻ\s*em|đánh\s*đập\s*trẻ\s*em|ngược\s*đãi\s*trẻ\s*em)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Chủ đề cực kỳ nhạy cảm. Phải dùng ngôn ngữ học thuật/pháp lý cao nhất và phải có bối cảnh EDSA lên án tội phạm."
    },
    "MEDICAL_MISINFO": {
        "id": "13813322",
        "title": "Chính sách về thông tin y tế sai lệch",
        "category": "Thông tin y tế sai lệch (Medical Misinformation)",
        "regex": r"\b(chữa\s*khỏi\s*(ung\s*thư|hiv|tiểu\s*đường|covid)\s*(100%|dứt\s*điểm|thần\s*tốc)|thần\s*dược|uống\s*(nước\s*tiểu|kiềm|thuốc\s*tẩy)\s*chữa\s*bệnh|vắc\s*xin\s*(giết\s*người|gây\s*vô\s*sinh|gắn\s*chip))\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Thay bằng 'hỗ trợ cải thiện thể trạng', 'kinh nghiệm dân gian tham khảo', bắt buộc dẫn nguồn y khoa chính thống và khuyên người xem đi khám bác sĩ."
    },
    "SCAM_FINANCIAL": {
        "id": "2801973",
        "title": "Chính sách về nội dung rác & lừa đảo tài chính",
        "category": "Lừa đảo tài chính & Cờ bạc (Scams & Gambling)",
        "regex": r"\b(làm\s*giàu\s*không\s*khó|kiếm\s*\d+\s*(triệu|củ)\s*mỗi\s*ngày|đánh\s*bạc\s*online|tài\s*xỉu\s*online|cá\s*độ\s*bóng\s*đá|kéo\s*tài\s*xỉu|bao\s*thắng\s*100%|nhận\s*tiền\s*miễn\s*phí|tặng\s*iphone\s*miễn\s*phí)\b",
        "severity": "HIGH",
        "penalty_7s": "HIGH",
        "advice": "Cảnh báo rủi ro tài chính, sử dụng từ 'dự án mạo hiểm', 'trò chơi may rủi', 'nguy cơ lừa đảo chiếm đoạt tài sản'."
    },
    "DISHONEST_HACKING": {
        "id": "6162278",
        "title": "Nội dung tạo điều kiện cho hành vi bất chính",
        "category": "Hành vi bất chính & Bẻ khóa (Hacking/Cracking)",
        "regex": r"\b(crack\s*(phần\s*mềm|win|windows)|bẻ\s*khóa\s*(phần\s*mềm|mật\s*khẩu)|hack\s*(tài\s*khoản|facebook|game)|tải\s*lậu|xem\s*phim\s*lậu|tool\s*hack)\b",
        "severity": "HIGH",
        "penalty_7s": "HIGH",
        "advice": "Thay bằng 'kiểm thử an ninh mạng', 'kích hoạt thông qua công cụ bên thứ ba', 'sử dụng phần mềm mã nguồn mở thay thế'."
    },
    "ILLEGAL_DRUGS": {
        "id": "9229611",
        "title": "Chính sách về hàng hoá hoặc dịch vụ bất hợp pháp hoặc thuộc diện quản lý",
        "category": "Ma túy & Chất cấm (Recreational Drugs)",
        "regex": r"\b(ma\s*túy|heroin|hút\s*cần|cỏ\s*mỹ|hít\s*ke|chơi\s*kẹo|bay\s*lắc|đập\s*đá|mua\s*bán\s*chất\s*cấm|bóng\s*cười)\b",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Thay bằng 'chất cấm', 'chất gây nghiện', 'hợp chất nguy hại' trong bối cảnh điều tra tội phạm."
    },
    # CỤM 09 & QUY CHUẨN MỚI
    "AI_SYNTHETIC_REALISTIC": {
        "id": "14328491",
        "title": "Chính sách công bố nội dung tạo bằng AI & Bảo vệ Danh tính (Likeness Protection 16440338)",
        "category": "Nội dung AI Chân thực & Rủi ro Danh tính (Realistic AI & Likeness)",
        "regex": r"\b(deepfake|face\s*swap|hoán\s*đổi\s*khuôn\s*mặt|nhân\s*bản\s*giọng\s*(nói)?|clone\s*giọng|giả\s*giọng\s*(\w+)?|giọng\s*(đọc\s*)?ai|ai\s*voice|mô\s*phỏng\s*(thảm\s*họa|tai\s*nạn|chiến\s*tranh|cháy\s*nhà|động\s*đất|sập\s*cầu)|sự\s*kiện\s*giả\s*lập)\b",
        "severity": "HIGH",
        "penalty_7s": "CRITICAL",
        "advice": "BẮT BUỘC tick chọn 'Có' tại mục 'Nội dung đã qua chỉnh sửa' (Altered content) trong YouTube Studio. Cảnh báo nguy cơ Likeness Claim (SLA 48h) nếu mô phỏng người thật trái phép."
    },
    "AI_PROGRAMMATIC_MASS": {
        "id": "1311392",
        "title": "Chính sách kiếm tiền YPP: Cấm AI sản xuất hàng loạt & Avatar AI tư vấn nhạy cảm",
        "category": "AI sản xuất hàng loạt & Avatar AI nhạy cảm (AI Mass-Produced & Personas)",
        "regex": r"\b(chào\s*mừng\s*(các\s*bạn\s*)?đã\s*quay\s*trở\s*lại\s*với\s*kênh|trong\s*video\s*ngày\s*hôm\s*nay\s*chúng\s*ta\s*sẽ\s*cùng|hãy\s*nhấn\s*(nút\s*)?(like|đăng\s*ký|subscribe)\s*để\s*không\s*bỏ\s*lỡ|kịch\s*bản\s*(tự\s*động|chatgpt|mẫu)|tóm\s*tắt\s*sách\s*tự\s*động|bác\s*sĩ\s*ai|chuyên\s*gia\s*tài\s*chính\s*ai|luật\s*sư\s*ai|avatar\s*ai\s*khuyên|chuyên\s*gia\s*ảo)\b",
        "severity": "HIGH",
        "penalty_7s": "HIGH",
        "advice": "Nguy cơ bị từ chối/hủy kiếm tiền YPP do lỗi Repetitious Content hoặc cấm Avatar AI tư vấn nhạy cảm. Cần bổ sung phân tích độc bản của con người (Transformative Value)."
    },
    "EXTERNAL_LINKS_RISK": {
        "id": "9054257",
        "title": "Chính sách về đường liên kết ngoài (External Links)",
        "category": "Liên kết ngoài rủi ro & Kéo nhóm kín (External Links / Group Funneling)",
        "regex": r"(https?://\S+|t\.me/\S+|telegram\s*:\s*@?\S+|zalo\.me/\S+|bit\.ly/\S+|tinyurl\.com/\S+|link\s*(ở\s*phần\s*)?mô\s*tả|nhóm\s*kín\s*(telegram|zalo)|kéo\s*về\s*bờ|vào\s*nhóm\s*vip|link\s*đăng\s*ký\s*nhận\s*tiền)",
        "severity": "CRITICAL",
        "penalty_7s": "CRITICAL",
        "advice": "Liên kết trỏ đến Telegram kéo nhóm tài chính/cờ bạc hoặc link rút gọn mờ ám sẽ bị ăn GẬY CỘNG ĐỒNG TRỰC TIẾP theo chính sách 9054257. Chỉ dẫn link nguồn uy tín, chính thống."
    },
    "CLICKBAIT_MISLEADING": {
        "id": "2801973",
        "title": "Chính sách về thông tin sai lệch, giật tít & lừa đảo",
        "category": "Giật tít lừa đảo & Hứa hẹn phi thực tế (Clickbait & Misleading Metadata)",
        "regex": r"\b(bí\s*mật\s*động\s*trời\s*(chưa\s*từng\s*tiết\s*lộ)?|xem\s*ngay\s*kẻo\s*(bị\s*)?xóa|cam\s*kết\s*100%\s*(ăn\s*chắc|thắng|lãi)|kiếm\s*tiền\s*trong\s*lúc\s*ngủ|không\s*cần\s*vốn|bảo\s*đảm\s*giàu\s*ngay|sự\s*thật\s*kinh\s*hoàng\s*bị\s*giấu\s*kín|tiết\s*lộ\s*chấn\s*động)\b",
        "severity": "HIGH",
        "penalty_7s": "HIGH",
        "advice": "Tránh giật tít phóng đại sai sự thật. Tiêu đề và hook phải phản ánh đúng nội dung thực tế để tránh vi phạm chính sách Spam & Misleading Metadata."
    }
}

EDSA_KEYWORDS = [
    r"cảnh\s*báo", r"disclaimer", r"tuyên\s*bố\s*miễn\s*trừ", r"mục\s*đích\s*giáo\s*dục",
    r"phim\s*tài\s*liệu", r"tư\s*liệu\s*lịch\s*sử", r"hồ\s*sơ\s*vụ\s*án", r"theo\s*cơ\s*quan\s*điều\s*tra",
    r"lên\s*án", r"phòng\s*ngừa", r"bài\s*học\s*cảnh\s*giác", r"nghiên\s*cứu\s*khoa\s*học"
]

def analyze_script(script_text):
    words = script_text.split()
    total_words = len(words)
    estimated_seconds = round(total_words / 2.67, 1) # ~160 words per minute
    
    # 7-second cutoff = ~20 words
    hook_words = words[:20]
    hook_text = " ".join(hook_words)
    body_text = " ".join(words[20:]) if len(words) > 20 else ""
    
    violations = []
    
    # Check EDSA framing
    has_edsa = any(re.search(pat, script_text, re.IGNORECASE) for pat in EDSA_KEYWORDS)
    
    # Scan policies
    for p_key, p_info in POLICIES.items():
        pattern = p_info["regex"]
        
        # Check in Hook (0-7s)
        hook_matches = list(re.finditer(pattern, hook_text, re.IGNORECASE))
        for m in hook_matches:
            violations.append({
                "rule_key": p_key,
                "policy_id": p_info["id"],
                "policy_title": p_info["title"],
                "category": p_info["category"],
                "severity": p_info["penalty_7s"],
                "location": "Trong 7 giây đầu tiên (Hook/Intro)",
                "matched_text": m.group(0),
                "context": hook_text[max(0, m.start()-20):min(len(hook_text), m.end()+20)],
                "advice": f"CỰC KỲ NGUY HIỂM Ở 7S ĐẦU: {p_info['advice']}"
            })
            
        # Check in Body (after 7s)
        if body_text:
            body_matches = list(re.finditer(pattern, body_text, re.IGNORECASE))
            for m in body_matches:
                violations.append({
                    "rule_key": p_key,
                    "policy_id": p_info["id"],
                    "policy_title": p_info["title"],
                    "category": p_info["category"],
                    "severity": p_info["severity"],
                    "location": "Phần thân kịch bản (Sau 7 giây đầu)",
                    "matched_text": m.group(0),
                    "context": body_text[max(0, m.start()-30):min(len(body_text), m.end()+30)],
                    "advice": p_info["advice"]
                })

    # Sensitive themes without EDSA warning
    sensitive_theme_detected = any(v["severity"] in ["CRITICAL", "HIGH"] for v in violations)
    if sensitive_theme_detected and not has_edsa:
        violations.append({
            "rule_key": "MISSING_EDSA_DISCLAIMER",
            "policy_id": "6345162",
            "policy_title": "Cách YouTube đánh giá nội dung EDSA (Giáo dục/Tư liệu/Khoa học)",
            "category": "Thiếu bối cảnh ngoại lệ EDSA",
            "severity": "HIGH",
            "location": "Toàn bộ kịch bản (Thiếu Disclaimer đầu video)",
            "matched_text": "[Không tìm thấy Disclaimer/Bối cảnh]",
            "context": "Kịch bản có yếu tố gai góc/nhạy cảm nhưng không có câu mở đầu tuyên bố mục đích giáo dục hoặc cảnh báo người xem.",
            "advice": "Bắt buộc chèn Disclaimer tuyên bố mục đích giáo dục/phòng ngừa tội phạm ở 5 giây đầu tiên."
        })

    # Studio Checkbox Determination
    has_ai_realistic = any(v["rule_key"] == "AI_SYNTHETIC_REALISTIC" for v in violations)
    has_violence_drugs_sex = any(v["rule_key"] in ["VIOLENCE_GORE", "ILLEGAL_DRUGS", "SEXUAL_CONTENT", "PROFANITY_STRONG"] for v in violations)

    studio_checklist = {
        "altered_or_synthetic_content": {
            "required": has_ai_realistic,
            "status": "BẮT BUỘC TICK 'CÓ'" if has_ai_realistic else "TÙY CHỌN (TICK 'KHÔNG' NẾU CHỈ DÙNG AI HỖ TRỢ/PHI THỰC TẾ)",
            "guidance": "Video có chứa yếu tố AI mô phỏng người thật, giọng nói thật hoặc sự kiện giả lập chân thực (Policy 14328491)." if has_ai_realistic else "Không phát hiện yếu tố AI chân thực vi phạm ranh giới công bố."
        },
        "age_restriction_18_plus": {
            "required": has_violence_drugs_sex,
            "status": "KHUYẾN NGHỊ BẬT 18+" if has_violence_drugs_sex else "KHÔNG CẦN GIỚI HẠN 18+",
            "guidance": "Kịch bản có yếu tố nhạy cảm (bạo lực, chất cấm, ngôn từ thô tục). Bật 18+ để bảo vệ kênh khỏi án phạt gậy." if has_violence_drugs_sex else "Nội dung phù hợp với người xem đại chúng."
        },
        "made_for_kids": {
            "required": False,
            "status": "CHỌN 'KHÔNG, ĐÂY KHÔNG PHẢI NỘI DUNG DÀNH CHO TRẺ EM'",
            "guidance": "Nội dung người lớn/phân tích xã hội; tuyệt đối không gắn nhãn Made for Kids (COPPA 9528076)."
        },
        "likeness_protection_risk": {
            "has_risk": has_ai_realistic,
            "status": "CẢNH BÁO NGUY CƠ LIKENESS CLAIM (48H SLA)" if has_ai_realistic else "AN TOÀN",
            "guidance": "Nếu sử dụng giọng nói hoặc khuôn mặt mô phỏng của người thật mà chưa có văn bản đồng ý, chủ thể có quyền khiếu nại yêu cầu gỡ bỏ trong 48 giờ (Policy 16440338 / 17133929)." if has_ai_realistic else "Không có rủi ro xâm phạm đặc điểm nhận dạng sinh trắc học."
        }
    }

    # Calculate Score
    score = 100
    critical_count = sum(1 for v in violations if v["severity"] == "CRITICAL")
    high_count = sum(1 for v in violations if v["severity"] == "HIGH")
    medium_count = sum(1 for v in violations if v["severity"] == "MEDIUM")
    
    score -= (critical_count * 35)
    score -= (high_count * 20)
    score -= (medium_count * 8)
    score = max(0, min(100, score))
    
    # Status Determination
    if critical_count > 0:
        status = "Tín hiệu rủi ro CRITICAL cần thẩm định ngữ cảnh"
    elif high_count > 0 or score < 70:
        status = "Tín hiệu rủi ro HIGH cần thẩm định ngữ cảnh"
    elif medium_count > 0 or score < 90:
        status = "Tín hiệu rủi ro MEDIUM cần thẩm định ngữ cảnh"
    else:
        status = "Chưa phát hiện từ khóa trong bộ quy tắc hiện có"
    monetization = "NOT_VERIFIED: cần YouTube đánh giá video và kênh thực tế"

    return {
        "screening_method": "regex_heuristic",
        "limitations": [
            "Chỉ sàng lọc từ khóa văn bản; có thể bỏ sót hoặc báo nhầm do ngữ cảnh.",
            "Không xác minh hình ảnh, âm thanh, quyền sử dụng tài sản, bản quyền hoặc Content ID.",
            "Không chứng nhận tuân thủ chính sách, điều kiện YPP hoặc kết quả kiếm tiền.",
            "20 từ đầu chỉ ước tính thời gian; có disclaimer không tự tạo ngoại lệ EDSA.",
            "Quy tắc cục bộ không tự cập nhật chính sách; cần kiểm tra tài liệu hiện hành.",
        ],
        "metrics": {
            "total_words": total_words,
            "estimated_duration": f"{estimated_seconds} giây (~{round(estimated_seconds/60, 1)} phút)",
            "safety_score": score,
            "status": status,
            "monetization": monetization,
            "has_edsa_framing": has_edsa,
            "violation_counts": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "total": len(violations)
            }
        },
        "studio_checklist": studio_checklist,
        "violations": violations
    }

def format_markdown_report(result, original_script):
    m = result["metrics"]
    v_list = result["violations"]
    chk = result["studio_checklist"]
    
    lines = []
    lines.append("# BÁO CÁO KIỂM ĐỊNH CHÍNH SÁCH YOUTUBE (YOUTUBE POLICY AUDIT REPORT)")
    lines.append("")
    lines.append("## 1. BẢNG TỔNG QUAN ĐIỂM SỐ & DỰ BÁO TRẠNG THÁI")
    lines.append("")
    lines.append("| Chỉ số kiểm định | Kết quả đánh giá | Diễn giải kỹ thuật |")
    lines.append("|:---|:---:|:---|")
    lines.append(f"| **Điểm sàng lọc heuristic** | **{m['safety_score']}/100** | Điểm quy ước từ regex, không phải xác suất an toàn |")
    lines.append(f"| **Đánh giá Trạng thái** | {m['status']} | Bộ từ khóa cục bộ; cần Checker đánh giá ngữ cảnh |")
    lines.append(f"| **Kiếm tiền** | **{m['monetization']}** | Không chứng nhận YPP |")
    lines.append(f"| **Quy mô Kịch bản** | {m['total_words']} từ | Ước tính thời lượng: {m['estimated_duration']} |")
    lines.append(f"| **Từ khóa EDSA** | {'Có từ khóa' if m['has_edsa_framing'] else 'Không thấy từ khóa'} | Không xác nhận ngoại lệ EDSA |")
    crit = m['violation_counts']['critical']
    high = m['violation_counts']['high']
    med = m['violation_counts']['medium']
    tot = m['violation_counts']['total']
    lines.append(f"| **Tổng số phát hiện vi phạm** | **{tot}** điểm | Critical: {crit} - High: {high} - Medium: {med} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. CHECKBOX THIẾT LẬP YOUTUBE STUDIO KHI TẢI LÊN")
    lines.append("")
    lines.append("| Mục thiết lập trong YouTube Studio | Quyết định đề xuất | Hướng dẫn & Căn cứ chính sách |")
    lines.append("|:---|:---:|:---|")
    ai_item = chk["altered_or_synthetic_content"]
    lines.append(f"| **Nội dung đã qua chỉnh sửa (AI)** | **{ai_item['status']}** | {ai_item['guidance']} |")
    age_item = chk["age_restriction_18_plus"]
    lines.append(f"| **Giới hạn độ tuổi (18+)** | **{age_item['status']}** | {age_item['guidance']} |")
    kid_item = chk["made_for_kids"]
    lines.append(f"| **Dành cho trẻ em (COPPA)** | **{kid_item['status']}** | {kid_item['guidance']} |")
    like_item = chk["likeness_protection_risk"]
    lines.append(f"| **Rủi ro Quyền riêng tư & Likeness** | **{like_item['status']}** | {like_item['guidance']} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. CHI TIẾT CÁC LỖI VI PHẠM & CẢNH BÁO RỦI RO")
    lines.append("")
    
    if not v_list:
        lines.append("Không tìm thấy từ khóa trong bộ regex hiện có. Kết quả này không xác nhận kịch bản tuân thủ chính sách.")
    else:
        lines.append("| STT | Vị trí xuất hiện | Từ khóa vi phạm | Chính sách liên quan (ID) | Mức rủi ro | Hướng dẫn khắc phục an toàn |")
        lines.append("|:---:|:---|:---|:---|:---:|:---|")
        for idx, v in enumerate(v_list, 1):
            sev_badge = "🔴 CRITICAL" if v['severity'] == "CRITICAL" else ("🟠 HIGH" if v['severity'] == "HIGH" else "🟡 MEDIUM")
            lines.append(f"| {idx} | **{v['location']}** | `{v['matched_text']}` | **{v['category']}**<br>*(ID: [{v['policy_id']}](https://support.google.com/youtube/answer/{v['policy_id']}))* | {sev_badge} | {v['advice']} |")
            
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. GIỚI HẠN & THẨM ĐỊNH TIẾP THEO")
    lines.append("")
    lines.extend(f"- {item}" for item in result["limitations"])
    lines.append("Checker cần xem bản dựng thực tế, ngữ cảnh, nguồn dữ liệu và hồ sơ cấp phép tài sản. Đổi từ hoặc thêm disclaimer không bảo đảm tuân thủ.")
    lines.append("")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="YouTube Script Policy Auditor Engine")
    parser.add_argument("--file", help="Path to script text file (.txt, .md)")
    parser.add_argument("--text", help="Script text string")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data structure")
    args = parser.parse_args()

    content = ""
    if args.file:
        if not os.path.exists(args.file):
            print(f"Lỗi: Không tìm thấy tệp kịch bản tại đường dẫn '{args.file}'.", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Lỗi khi đọc tệp '{args.file}': {str(e)}", file=sys.stderr)
            sys.exit(1)
    elif args.text:
        content = args.text
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        parser.print_help()
        print("\nVui lòng cung cấp kịch bản qua --file, --text hoặc qua pipe/stdin.", file=sys.stderr)
        sys.exit(1)

    result = analyze_script(content)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_markdown_report(result, content))

if __name__ == "__main__":
    main()
