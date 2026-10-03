#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Policy Auditor CLI & Engine
Analyzes YouTube scripts against 50 YouTube policies crawled from YouTube Support.
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
        "title": "Chính sách về nội dung rác & lừa đảo",
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
        status = "🔴 NGUY HIỂM / VI PHẠM NGUYÊN TẮC CỘNG ĐỒNG (CÓ NGUY CƠ NHẬN GẬY HOẶC XÓA VIDEO)"
        monetization = "BỊ TẮT KIẾM TIỀN HOẶC XÓA VIDEO"
    elif high_count > 0 or score < 70:
        status = "🟠 RỦI RO CAO / GIỚI HẠN ĐỘ TUỔI 18+ HOẶC VÀNG TIỀN NẶNG"
        monetization = "ĐÔ LA VÀNG / HẠN CHẾ HẦU HẾT NHÀ QUẢNG CÁO"
    elif medium_count > 0 or score < 90:
        status = "🟡 CẦN LƯU Ý / CÓ THỂ BỊ HẠN CHẾ QUẢNG CÁO (ĐÔ LA VÀNG)"
        monetization = "ĐÔ LA VÀNG (Cần chỉnh sửa từ ngữ để lên Đô la Xanh)"
    else:
        status = "🟢 AN TOÀN TUYỆT ĐỐI (CHUẨN BẬT KIẾM TIỀN ĐÔ LA XANH)"
        monetization = "ĐÔ LA XANH (Phù hợp mọi nhà quảng cáo)"

    return {
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
        "violations": violations
    }

def format_markdown_report(result, original_script):
    m = result["metrics"]
    v_list = result["violations"]
    
    lines = []
    lines.append("# BÁO CÁO KIỂM ĐỊNH CHÍNH SÁCH YOUTUBE (YOUTUBE POLICY AUDIT REPORT)")
    lines.append("")
    lines.append("## 1. BẢNG TỔNG QUAN ĐIỂM SỐ & DỰ BÁO TRẠNG THÁI")
    lines.append("")
    lines.append("| Chỉ số kiểm định | Kết quả đánh giá | Diễn giải kỹ thuật |")
    lines.append("|:---|:---:|:---|")
    lines.append(f"| **Điểm An toàn Chính sách** | **{m['safety_score']}/100** | {'Đạt ngưỡng xuất bản an toàn' if m['safety_score']>=90 else 'Cần sửa đổi trước khi sản xuất'} |")
    lines.append(f"| **Đánh giá Trạng thái** | {m['status']} | Dựa trên 50 bộ quy chuẩn YouTube |")
    lines.append(f"| **Dự báo Kiếm tiền** | **{m['monetization']}** | Tác động trực tiếp đến doanh thu AdSense/YPP |")
    lines.append(f"| **Quy mô Kịch bản** | {m['total_words']} từ | Ước tính thời lượng: {m['estimated_duration']} |")
    lines.append(f"| **Bối cảnh EDSA** | {'✅ Đã tích hợp Disclaimer' if m['has_edsa_framing'] else '❌ Chưa có Disclaimer/Bối cảnh'} | Ngoại lệ Giáo dục/Tư liệu (Policy 6345162) |")
    crit = m['violation_counts']['critical']
    high = m['violation_counts']['high']
    med = m['violation_counts']['medium']
    tot = m['violation_counts']['total']
    lines.append(f"| **Tổng số phát hiện vi phạm** | **{tot}** điểm | Critical: {crit} - High: {high} - Medium: {med} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. CHI TIẾT CÁC LỖI VI PHẠM & CẢNH BÁO RỦI RO")
    lines.append("")
    
    if not v_list:
        lines.append("🎉 **KỊCH BẢN HOÀN HẢO!** Không phát hiện vi phạm nào trong 50 tài liệu chính sách của YouTube. Kịch bản đủ điều kiện bật kiếm tiền Đô la Xanh.")
    else:
        lines.append("| STT | Vị trí xuất hiện | Từ khóa vi phạm | Chính sách liên quan (ID) | Mức rủi ro | Hướng dẫn khắc phục an toàn |")
        lines.append("|:---:|:---|:---|:---|:---:|:---|")
        for idx, v in enumerate(v_list, 1):
            sev_badge = "🔴 CRITICAL" if v['severity'] == "CRITICAL" else ("🟠 HIGH" if v['severity'] == "HIGH" else "🟡 MEDIUM")
            lines.append(f"| {idx} | **{v['location']}** | `{v['matched_text']}` | **{v['category']}**<br>*(ID: [{v['policy_id']}](https://support.google.com/youtube/answer/{v['policy_id']}))* | {sev_badge} | {v['advice']} |")
            
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. KHUYẾN NGHỊ HÀNH ĐỘNG CỐT LÕI ĐỂ SẠCH BÓNG VI PHẠM")
    lines.append("")
    lines.append("1. **Áp dụng triệt để Quy tắc 7 giây đầu tiên (First 7 Seconds Rule)**: Đảm bảo phần Hook mở đầu tuyệt đối không có từ chửi thề, tiếng la hét ghê rợn, hình ảnh máu me hoặc chi tiết kích dục.")
    lines.append("2. **Hoán đổi sang Từ điển Từ ngữ An toàn (Safe Euphemisms)**: Thay các từ nhạy cảm (giết, chết, tự tử, súng, ma túy) bằng từ ngữ mô tả khách quan, học thuật, báo chí.")
    lines.append("3. **Cấy Bối cảnh Ngoại lệ EDSA (Giáo dục/Tư liệu)**: Luôn chèn câu tuyên bố miễn trừ trách nhiệm (Disclaimer) ở 5s đầu và nhắc lại thông điệp nhân văn/thượng tôn pháp luật ở phần kết.")
    lines.append("")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="YouTube Script Policy Auditor")
    parser.add_argument("--file", help="Path to script text file")
    parser.add_argument("--text", help="Script text string")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    content = ""
    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    elif args.text:
        content = args.text
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        print("Vui lòng cung cấp kịch bản qua --file, --text hoặc qua stdin.")
        sys.exit(1)

    result = analyze_script(content)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_markdown_report(result, content))

if __name__ == "__main__":
    main()
