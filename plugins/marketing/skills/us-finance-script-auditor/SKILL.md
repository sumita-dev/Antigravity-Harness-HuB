---
name: us-finance-script-auditor
description: >-
  Kiểm định tính xác thực, toán học bảng lương Mỹ (US Payroll), thuế IRS/FICA,
  phúc lợi KFF và quy chuẩn thương hiệu cho kênh YouTube Broke and Building.
  Bắt buộc kích hoạt trước khi phê duyệt bất kỳ kịch bản tài chính nào.
---

# US Finance Script Auditor & Compliance Gatekeeper

Kỹ năng kiểm toán độc lập dành riêng cho các video phân tích tài chính cá nhân, bảng lương và chi phí sinh hoạt tại Mỹ của kênh **Broke and Building (@BrokeAndBuildingMoney)**.

---

## 1. Mục Đích & Sứ Mệnh
Triệt tiêu hoàn toàn:
1. Sai lệch toán học giữa Gross và Net, chuỗi khấu trừ (Taxes & Benefits) và chi phí sinh tồn.
2. Nhầm lẫn thuật ngữ bảng lương đặc thù của Mỹ (Bi-weekly vs Semi-monthly).
3. Ảo giác biểu thuế IRS và thổi phồng chi phí bảo hiểm vượt benchmark thực tế (KFF).
4. Vi phạm quy chuẩn Brand Voice: Bỏ lỡ từ điển thương hiệu (*The Latte Lie*, *Boomer Math*, *The Spreadsheet Defense*).

---

## 2. 6 Chốt Chặn Kiểm Định Bắt Buộc (The 6 Hard Invariants)

Mọi kịch bản tài chính trước khi được cấp trạng thái **PASS** phải thỏa mãn 100% các tiêu chí sau:

### Chốt Chặn 1: Chu Kỳ Lương Bất Biến (Payroll Schedule Invariant)
- **Semi-Monthly (24 kỳ/năm):** Lương về **ngày 1 và 15 hàng tháng**. Công thức: $\text{Annual Gross} / 24$.
- **Bi-Weekly (26 kỳ/năm):** Lương về **cách tuần (mỗi 2 tuần, thường là thứ Sáu)**. Công thức: $\text{Annual Gross} / 26$.
- **QUY TẮC CẤM:** CẤM TUYỆT ĐỐI gọi số tiền của 24 kỳ ($\$68,000 / 24 = \$2,833.33$) là "Bi-Weekly". Nếu nói ngày 1 và 15, bắt buộc dùng thuật ngữ *semi-monthly* hoặc *twice a month*.

### Chốt Chặn 2: Kiểm Định Thuế IRS & W-4 (Tax Withholding Grounding)
- Tính thuế liên bang phải trừ **Standard Deduction** ($15,000+ cho Single Filer) và các khoản **Pre-tax Deductions** (401k, Section 125 Healthcare).
- Nếu kịch bản dùng số thuế khấu trừ thô cao hơn thực tế (ví dụ $720/tháng thay vì $530/tháng), kịch bản **BẮT BUỘC** phải giải thích rõ: Đây là do **default W-4 withholding** bị giữ lố, dẫn đến việc cho chính phủ vay tiền không lãi suất chờ hoàn thuế vào tháng 4.

### Chốt Chặn 3: Chi Phí Bảo Hiểm Y Tế Chuẩn KFF (Healthcare Benchmark)
- Đối chiếu với báo cáo thường niên của **Kaiser Family Foundation (KFF)**:
  - Mức đóng trung bình của nhân viên cho gói cá nhân (Single Coverage): **~$120 - $130/tháng**.
  - Nha khoa & Thị lực (Dental & Vision): **~$30 - $45/tháng**.
- Nếu đưa con số trên **$250/tháng**, kịch bản bắt buộc phải bóc tách chi tiết: gồm tiền đóng vào quỹ HSA hoặc gói PPO cao cấp. Cấm đưa số $340-$400/tháng cho gói HDHP đơn lẻ mà không có breakdown.

### Chốt Chặn 4: Kỷ Luật Thống Kê NACE & BLS (Statistical Integrity)
- Phân định rõ ràng:
  - **Average Starting Salary (Lương trung bình):** Thường bị kéo lên bởi nhóm ngành Tech/Engineering/Wall Street.
  - **Median Starting Salary (Lương trung vị):** Phản ánh chính xác điểm giữa của toàn bộ sinh viên tốt nghiệp.
- Khi trích dẫn NACE $68,000, bắt buộc gọi đúng là **Average**.

### Chốt Chặn 5: Đối Soát Ngược Quy Tắc Nhà Ở (Housing Rule Back-Calculation)
- **Quy tắc 30% Gross:** $\text{Salary Needed} = (\text{Monthly Rent} \times 12) / 0.30$.
- **Quy tắc 3x Rent của chủ nhà:** $\text{Salary Needed} = \text{Monthly Rent} \times 3 \times 12$.
- CẤM bịa ra các con số giật gân (ví dụ nói thuê nhà $1,590 cần lương $85,000) mà không có bước tính toán đối soát đi kèm.

### Chốt Chặn 6: Kích Hoạt Bộ Từ Vựng Thương Hiệu (Brand Lexicon Injection)
Kịch bản tài chính phải lồng ghép tự nhiên ít nhất 2 trong số các thuật ngữ độc quyền từ `BRAND_TONE_OF_VOICE_GUIDELINES.md`:
1. **The Latte Lie:** Khi đập tan ngụy biện đổ lỗi cho cà phê/avocado toast.
2. **Boomer Math:** Khi bóc trần những lời khuyên lỗi thời thập niên 80.
3. **Adulting Tax / Grinder:** Khi nói về các chi phí phát sinh bất ngờ.
4. **The Spreadsheet Defense:** Khi hướng dẫn khán giả mở file Excel để phòng thủ.
5. **The Paycheck Mirage:** Khi nói về ảo ảnh lương Gross biến mất thành lương Net.

### Chốt Chặn 7: Chuẩn Hóa Âm Học KOKORO TTS (Kokoro Prosody Invariant v2.0)
Khi nhận yêu cầu *"viết kịch bản chuẩn hóa KOKORO"*, kịch bản BẮT BUỘC tuân thủ:
1. **Khai tử 85% `[↘]`:** Chỉ giữ tối đa 8–10 ký hiệu `[↘]` trong toàn bộ video cho các punchline định đoạt (kết Act/kết video).
2. **Quyền năng dấu `?` và `,`:** Câu hỏi tu từ/mỉa mai kết thúc bằng dấu `?` nguyên bản (CẤM kèm `[↘]`). Dấu phẩy `,` giữ hơi lơ lửng (+1 to +2 semitones, 150–220ms).
3. **Kiểm soát bọc `**`:** Không bọc nguyên cụm dài; chỉ nhấn từ hạt nhân hoặc để chữ thường tự nhiên.
4. **Gạch ngang dài ` — `:** Có khoảng trắng 2 đầu (280–320ms pause, giữ nguyên cao độ).
5. **Dấu ba chấm `...`:** Dừng dài 600–900ms trước cú twist hoặc số liệu quan trọng.
6. **Phiên âm sạch:** `A-M`, `P-M`, `M-B-A`, `U-S-A`, `H-R`, `D-Ms`, `I-R-S`, `H-Y-S-A`, `W-four`, `Section one-twenty-five`, `four-oh-one-k`.



---

## 3. Công Cụ Đối Soát Kỹ Thuật (Deterministic Engine)

Trước khi duyệt kịch bản, chạy script đối soát tại thư mục dự án:
```powershell
python scripts\verify_paycheck_math.py --salary <annual_gross> --schedule <semi-monthly|bi-weekly> --rent <monthly_rent>
```
Script sẽ xuất ra JSON và biên bản kiểm toán đối soát chính xác từng cent. Mọi số liệu trong kịch bản phải khớp 100% với output của script này.

---

## 4. Mẫu Biên Bản Kiểm Toán Kịch Bản (Audit Verdict Format)

```markdown
### BIÊN BẢN KIỂM TOÁN TÀI CHÍNH & KỊCH BẢN
- **Tập phim:** [Tên tập]
- **Trạng thái:** [PASS / REJECT]
- **Chi tiết đối soát 6 chốt chặn:**
  1. Payroll Schedule: [PASS/FAIL + dẫn chứng]
  2. IRS Tax & W-4: [PASS/FAIL + dẫn chứng]
  3. KFF Healthcare: [PASS/FAIL + dẫn chứng]
  4. NACE/BLS Terms: [PASS/FAIL + dẫn chứng]
  5. Housing Math: [PASS/FAIL + dẫn chứng]
  6. Brand Lexicon: [PASS/FAIL + dẫn chứng]
- **Sai lệch cần sửa (nếu REJECT):** [Liệt kê chính xác dòng và câu thoại]
```
