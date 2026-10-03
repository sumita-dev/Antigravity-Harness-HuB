# Báo Cáo Thẩm Định Độ An Toàn Bản Quyền — Reverse Lab Audit Report
**Phiên bản template:** v1.0 | Được sử dụng bởi skill `/reverse-lab`

---

## THÔNG TIN PHẦN MỀM ĐƯỢC THẨM ĐỊNH

| Mục | Chi tiết |
|:---|:---|
| **Tên ứng dụng** | `[Tên app]` |
| **Nền tảng / Tech Stack** | `[C# .NET / Electron / Python / C++ / ...]` |
| **Cơ chế kích hoạt hiện tại** | `[Online / Offline / Hybrid]` |
| **Ngày thẩm định** | `[Ngày]` |
| **Người thực hiện** | Skill `/reverse-lab` — Antigravity AI |

---

## PHẦN 1: PHÂN TÍCH NỀN TẢNG (Tech-Stack Risk Profile)

**Nền tảng được phát hiện:** `[C# .NET 6 / Electron 28 / Python 3.11 / ...]`

**Mức độ rủi ro nền tảng vốn có:** `[🔴 Rất Cao / 🟠 Cao / 🟡 Trung bình / 🟢 Thấp]`

**Lý do:**
> `[Phân tích lý do dựa trên đặc thù của nền tảng — tham chiếu stack-vulnerabilities.md]`

**Công cụ tấn công phù hợp nhất với nền tảng này:**
- `[Công cụ 1]`: `[Mô tả ngắn]`
- `[Công cụ 2]`: `[Mô tả ngắn]`

---

## PHẦN 2: MA TRẬN RỦI RO (Threat Modeling Scorecard)

Đánh giá khả năng bị tấn công theo từng nhóm phương thức. Điểm từ `0` (Không thể tấn công được) đến `10` (Cực kỳ dễ bị tấn công).

| Nhóm tấn công | Điểm rủi ro (0–10) | Mức độ | Phát hiện điểm yếu |
|:---|:---:|:---:|:---|
| **Nhóm 1:** Disk Patching (Patch file tĩnh) | `X` | 🔴/🟠/🟡/🟢 | `[Mô tả điểm yếu cụ thể]` |
| **Nhóm 2:** Memory Patching (Can thiệp RAM) | `X` | 🔴/🟠/🟡/🟢 | `[Mô tả điểm yếu cụ thể]` |
| **Nhóm 3:** Network Bypass | `X` | 🔴/🟠/🟡/🟢 | `[Mô tả điểm yếu cụ thể]` |
| **Nhóm 4:** Environment Manipulation | `X` | 🔴/🟠/🟡/🟢 | `[Mô tả điểm yếu cụ thể]` |
| **Nhóm 5:** Tech Stack Specific Risk | `X` | 🔴/🟠/🟡/🟢 | `[Mô tả điểm yếu cụ thể]` |

---

## PHẦN 3: ĐÁNH GIÁ KHẢ NĂNG CHỊU ĐỰNG (Attacker Resilience Matrix)

| Cấp độ kẻ tấn công | Mô tả | Có thể bẻ khóa không? | Ước tính thời gian |
|:---|:---|:---:|:---|
| 🟢 **Script Kiddie** | Người dùng phổ thông, chỉ dùng tool có sẵn (dnSpy, Cheat Engine crack tool) | `[Có / Không]` | `[< 30 phút / ...]` |
| 🟠 **Intermediate Reverser** | Biết dùng dnSpy, x64dbg, Ghidra cơ bản; hiểu Assembly | `[Có / Không]` | `[X giờ / X ngày]` |
| 🔴 **Advanced Cracker** | Chuyên nghiệp: tự viết Loader, Frida script, patch Memory | `[Có / Không]` | `[X ngày / Rất khó]` |

---

## PHẦN 4: ĐIỂM SỐ TỔNG THỂ (Overall Resilience Score)

```
┌─────────────────────────────────────────────────────────┐
│  RESILIENCE SCORE                                       │
│                                                         │
│  [ XX / 100 ]                                           │
│                                                         │
│  0────────────────────────────────────────────100       │
│  ←── Nguy hiểm ──── Trung bình ──── An toàn ──→        │
│                  ▲                                      │
│              Hiện tại                                   │
│                                                         │
│  Mức độ đánh giá:                                       │
│  0–30:   🔴 NGUY HIỂM NGHIÊM TRỌNG                    │
│  31–55:  🟠 CẦN CẢI THIỆN KHẨN CẤP                   │
│  56–75:  🟡 ĐẠT MỨC CƠ BẢN - Cần tăng cường          │
│  76–90:  🟢 TƯƠNG ĐỐI AN TOÀN                         │
│  91–100: ✅ MỨC THƯƠNG MẠI                            │
└─────────────────────────────────────────────────────────┘
```

**Nhận định tổng quan:**
> `[Nhận định 2-3 câu về tình trạng bảo mật tổng thể của ứng dụng]`

---

## PHẦN 5: LỘ TRÌNH GIA CỐ (Hardening Roadmap)

### Ưu tiên Khẩn cấp (Tuần 1–2)
> Các biện pháp phải triển khai ngay — đây là những điểm yếu nghiêm trọng nhất có thể bị khai thác bởi Script Kiddie.

| # | Biện pháp | Trụ cột | Độ phức tạp | Tác động |
|:---:|:---|:---:|:---:|:---:|
| 1 | `[Mô tả biện pháp]` | `[1–5]` | `[Thấp/Vừa/Cao]` | `[🔴 Cao]` |
| 2 | `[Mô tả biện pháp]` | `[1–5]` | `[Thấp/Vừa/Cao]` | `[🔴 Cao]` |

### Ưu tiên Quan trọng (Tháng 1)
> Cần làm để chống Intermediate Reverser.

| # | Biện pháp | Trụ cột | Độ phức tạp | Tác động |
|:---:|:---|:---:|:---:|:---:|
| 3 | `[Mô tả biện pháp]` | `[1–5]` | `[Thấp/Vừa/Cao]` | `[🟠 Vừa]` |
| 4 | `[Mô tả biện pháp]` | `[1–5]` | `[Thấp/Vừa/Cao]` | `[🟠 Vừa]` |

### Ưu tiên Nâng cao (Quý 1)
> Để đạt mức bảo vệ thương mại chống Advanced Cracker.

| # | Biện pháp | Trụ cột | Độ phức tạp | Tác động |
|:---:|:---|:---:|:---:|:---:|
| 5 | `[Mô tả biện pháp]` | `[1–5]` | `[Thấp/Vừa/Cao]` | `[🟡 Dài hạn]` |

---

## PHẦN 6: CHI TIẾT KỸ THUẬT TỪNG BIỆN PHÁP ĐỀ XUẤT

### [Tên biện pháp 1]
**Trụ cột:** `[Số]` | **Ngôn ngữ/Framework:** `[...]`

**Vấn đề hiện tại:**
> `[Mô tả cụ thể điểm yếu đang tồn tại]`

**Giải pháp:**
```[ngôn_ngữ]
// Code example cụ thể cho stack của anh
```

**Bước triển khai:**
1. `[Bước 1]`
2. `[Bước 2]`
3. `[Bước 3]`

**Xác nhận thành công:**
- `[Cách kiểm tra xem biện pháp đã hoạt động chưa]`

---

## PHỤ LỤC: TÀI LIỆU THAM KHẢO

- [Ma trận mối đe dọa đầy đủ](../references/threat-matrix.md)
- [Sổ tay rủi ro theo Tech Stack](../references/stack-vulnerabilities.md)
- [Cẩm nang 5 Trụ cột Phòng thủ](../references/defense-playbook.md)
- OWASP MASVS — Mobile/Desktop Application Security Verification Standard
- Microsoft Windows Internals — Pavel Yosifovich et al.
