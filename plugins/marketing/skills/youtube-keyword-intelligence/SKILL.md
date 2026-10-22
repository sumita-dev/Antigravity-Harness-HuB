---
name: youtube-keyword-intelligence
description: "Nghiên cứu, phân cụm ý định và thẩm định sâu trang kết quả tìm kiếm (SERP Audit) trên YouTube cho video dài, áp dụng thuật toán chấm điểm VKOS v3.0 (View, Evergreen, Displacement, Policy Safety) để chọn ra từ khóa số 1 cho từng nhóm nội dung."
---

# YouTube Keyword Intelligence & SERP Audit Engine (VKOS v3.0)

Hệ thống nghiên cứu từ khóa chuyên sâu, phân cụm ý định tìm kiếm và thẩm định trang kết quả tìm kiếm (SERP) trên YouTube dành riêng cho định dạng **Video Dài (Long-form Video >= 10 phút)**. Công cụ vận hành tự động bằng Python Standard Library (không phụ thuộc bên ngoài), tích hợp bộ lọc an toàn kiếm tiền (Yellow Dollar Guard) và thuật toán chấm điểm đa biến **VKOS v3.0**.

---

## 1. Quy Trình Vận Hành 4 Giai Đoạn

```
[Seed Keyword] 
      │
      ▼
┌────────────────────────────────────────────────────────┐
│ Giai đoạn 1: Thu thập & Mở rộng (Harvesting)           │
│ Google Suggest API (yt client) + Modifiers + Alphabet  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Giai đoạn 2: Phân cụm ý định (5 Intent Clusters)       │
│ Phân loại Regex ngữ nghĩa & Mẫu hình truy vấn          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Giai đoạn 3: Thẩm định sâu SERP (Deep SERP Audit)     │
│ ytInitialData, Views, Tuổi thọ video, Kệ Shorts, Ads   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Giai đoạn 4: Bộ lọc Chính sách & Chấm điểm VKOS v3.0   │
│ Rà soát Vàng nút kiếm tiền -> Chọn Top 1 kèm Briefing  │
└────────────────────────────────────────────────────────┘
```

### Giai đoạn 1: Thu thập & Mở rộng (Keyword Harvesting & Expansion)
- Truy vấn trực tiếp endpoint Google Suggest dành riêng cho YouTube client:
  `https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={query}&hl={lang}&gl={geo}`
- Kết hợp tiền tố (Prefix modifiers: cách, hướng dẫn, kinh nghiệm, review, so sánh, tự học...) và hậu tố (Suffix modifiers: là gì, cho người mới, lừa đảo, uy tín, kiếm tiền, rủi ro, chiến lược, bài học...).
- Mở rộng qua bảng chữ cái (Alphabet expansion: seed + a..z) nhằm khai thác triệt để từ khóa đuôi dài (long-tail keywords).

### Giai đoạn 2: Phân cụm ý định tìm kiếm (5 Semantic Intent Clusters)
Mọi từ khóa mở rộng được tự động phân loại vào 5 nhóm nội dung cốt lõi:
1. **1. Định nghĩa / Khái niệm (`Dinh_Nghia_Khai_Niem`):** Tìm hiểu bản chất, thuật ngữ, cơ chế hoạt động cho người mới bắt đầu (vd: *forex là gì*, *broker là gì*).
2. **2. Hướng dẫn / Thực hành (`Huong_Dan_Thuc_Hanh`):** Quy trình thao tác, cài đặt phần mềm, đăng ký tài khoản, nạp rút tiền (vd: *cách chơi forex*, *hướng dẫn mở tài khoản exness*).
3. **3. Hoài nghi / Rủi ro / Pháp lý (`Hoai_Nghi_Rui_Ro_Phap_Ly`):** Tâm lý phòng vệ, lo ngại lừa đảo, rủi ro cháy tài khoản, quy định pháp luật (vd: *forex có lừa đảo không*, *dấu hiệu sàn lừa đảo*).
4. **4. Đánh giá / Chọn sàn / So sánh (`Danh_Gia_Chon_San`):** So sánh các nền tảng, phí giao dịch, xếp hạng sàn uy tín (vd: *chọn sàn forex uy tín*, *review sàn exness vs icmarkets*).
5. **5. Chiến thuật / Kinh nghiệm (`Chien_Thuat_Kinh_Nghiem`):** Bí quyết giao dịch, phương pháp quản lý vốn, kiểm soát tâm lý, bài học thực chiến (vd: *kinh nghiệm chơi forex*, *chiến lược scalping*).

### Giai đoạn 3: Thẩm định sâu SERP (Deep SERP Audit)
- Phân tích mã nguồn trang kết quả tìm kiếm YouTube (`ytInitialData`) không cần API key.
- Trích xuất định lượng cho Top 10 kết quả tự nhiên:
  - Lượng view trung bình (`avg_views`) và trung vị (`median_views`).
  - Tỷ lệ video thời lượng dài >= 10 phút (`pct_long_videos`).
  - Tỷ lệ video trường tồn xuất bản > 1 năm vẫn đứng top (`pct_evergreen_videos`).
  - Sự xuất hiện và vị trí của kệ video ngắn (`Shorts shelf`) gây phân tán lượt click.
  - Sự xuất hiện của quảng cáo tài trợ (`Sponsored Ads`) và khung cảnh báo chính sách chính thức (`Emergency / Health Onebox`).

### Giai đoạn 4: Bộ lọc Chính sách & Chấm điểm VKOS v3.0
- **Policy & Safety Guardrail:** Đánh giá nguy cơ hạn chế quảng cáo hoặc gán nút vàng (Yellow Dollar).
- **Thuật toán VKOS v3.0:** Tính toán cơ hội tổng hòa giữa nhu cầu người xem, độ bền thời gian, khoảng trống cạnh tranh và giá trị thương mại.
- **Top 1 Selection & Actionable Briefing:** Tự động chọn ra 01 từ khóa xuất sắc nhất của mỗi nhóm kèm bản định hướng sản xuất chi tiết.

---

## 2. Công Thức & Trọng Số VKOS v3.0

Thuật toán **VKOS v3.0 (Video Keyword Opportunity Score)** được tính toán theo thang điểm 100:

$$\text{VKOS} = 0.25 \times \text{VMS} + 0.20 \times \text{EDO} + 0.20 \times \text{CSG} + 0.15 \times \text{LRP} + 0.10 \times \text{PMS} + 0.10 \times \text{CCV}$$

| Chỉ số | Tên đầy đủ | Trọng số | Ý nghĩa & Cách tính |
| :--- | :--- | :---: | :--- |
| **VMS** | **View Momentum Score** | **25%** | Lượng người xem thực tế trên SERP. Tính toán theo thang logarit của trung vị lượt xem (Median Views). $10.000\text{ views} \approx 72\text{đ}$, $100.000\text{ views} \approx 90\text{đ}$, $\ge 500.000\text{ views} \approx 100\text{đ}$. |
| **EDO** | **Evergreen Demand Opportunity** | **20%** | Nhu cầu tìm kiếm trường tồn qua các năm. Đo lường tỷ lệ video cũ xuất bản > 1 năm vẫn trụ vững trong Top 10 (chứng minh chủ đề không lỗi thời). |
| **CSG** | **Competition & Shorts Gap** | **20%** | Cơ hội soán ngôi đối thủ. Điểm cộng cao khi đối thủ chỉ làm video ngắn dưới 10 phút (+20đ) và SERP không bị kệ Shorts chiếm sóng (+10đ). |
| **LRP** | **Long-form Retention Potential** | **15%** | Tiềm năng giữ chân người xem video dài (Average View Duration >= 45%). Các chủ đề hướng dẫn thực hành, case study, bóc phốt đạt điểm cao (85-98đ). |
| **PMS** | **Policy Monetization Safety** | **10%** | Độ an toàn kiếm tiền. Đạt 100đ cho Vùng Xanh (Green Dollar). Bị phạt xuống 60đ nếu cần disclaimer thận trọng, hoặc 20đ nếu vi phạm từ khóa đỏ. |
| **CCV** | **Commercial Conversion Value** | **10%** | Tiềm năng khai thác thương mại ngoài AdSense (Sponsorship, hoa hồng Affiliate sàn, bán khoá học/phần mềm). |

---

## 3. Chính Sách YouTube & An Toàn Kiếm Tiền

Hệ thống phân định 3 cấp độ an toàn kiếm tiền:

1. 🟢 **SAFE_GREEN (Vùng Xanh - Điểm PMS = 100):**
   - Chủ đề giáo dục, phân tích kỹ thuật, quản trị rủi ro, chia sẻ tư duy căn bản.
   - Thân thiện tuyệt đối với các nhà quảng cáo tài chính chính thống, đạt RPM cao nhất.
2. 🟡 **CAUTION_YELLOW (Vùng Cảnh Báo - Điểm PMS = 60):**
   - Dấu hiệu lời hứa làm giàu nhanh, copy trade, bắn tín hiệu VIP, review sàn có tranh chấp.
   - **Yêu cầu bắt buộc:** Phải áp dụng khung **EDSA (Educational, Documentary, Scientific, Artistic)**, chèn *Risk Disclaimer* (Tuyên bố từ chối trách nhiệm rủi ro tài chính) trong 5 giây đầu và phần mô tả.
3. 🔴 **HIGH_RISK_RED (Vùng Đỏ Nguy Hiểm - Điểm PMS = 20):**
   - Thuật ngữ liên quan đến cờ bạc trá hình, kéo tài xỉu, sập sàn, lừa tiền, ủy thác cam kết lãi 100%, hack/cheat tool.
   - Nguy cơ cực cao bị gán nút vàng (Yellow Dollar) hoặc gậy Nguyên tắc cộng đồng. Cần loại trừ khỏi kế hoạch hoặc chuyển hóa 100% thành phóng sự cảnh báo lừa đảo/pháp lý.

---

## 4. Hướng Dẫn Sử Dụng CLI

Script chính đặt tại: `scripts/keyword_intelligence.py`

### Lệnh Cơ Bản:
```bash
python scripts/keyword_intelligence.py -k "forex"
```

### Chế Độ Nhanh (Fast Mode) & Xuất Đủ Định Dạng (Markdown, CSV, JSON):
```bash
python scripts/keyword_intelligence.py -k "forex" --fast --format all -o "reports/forex_audit"
```

### Bảng Tham Số Lệnh:

| Tham số | Rút gọn | Bắt buộc | Mặc định | Mô tả |
| :--- | :---: | :---: | :---: | :--- |
| `--keyword` | `-k` | **Có** | - | Từ khóa hạt giống cần nghiên cứu (vd: "chứng khoán", "forex", "tiền ảo"). |
| `--output` | `-o` | Không | Thư mục hiện tại | Đường dẫn file hoặc thư mục lưu trữ kết quả. |
| `--fast` | - | Không | `False` | Bật chế độ nhanh: quét các modifier cốt lõi và audit top ứng viên để tiết kiệm thời gian. |
| `--format` | - | Không | `markdown` | Định dạng xuất báo cáo: `markdown` (hoặc `md`), `json`, `csv`, hoặc `all`. |
| `--lang` | - | Không | `vi` | Mã ngôn ngữ tìm kiếm (`vi` cho tiếng Việt, `en` cho tiếng Anh). |
| `--geo` | - | Không | `vn` | Mã quốc gia địa lý (`vn`, `us`...). |

---

## 5. Quy Cách Báo Cáo Xuất Ra

1. **Báo cáo Markdown (`.md`):**
   - Bảng tổng kết Top 1 từ khóa của 5 cụm ý định kèm điểm chi tiết VKOS v3.0 và trạng thái an toàn chính sách.
   - 5 bản **Actionable Briefing** sẵn sàng giao cho Biên kịch/Creator:
     - *Tại sao chọn (Why it wins)*
     - *Góc tiếp cận video dài (Content Angle)*
     - *Thời lượng đề xuất (>= 10 phút, tối ưu Mid-roll ads)*
     - *Chiến lược Thumbnail & Hook 30 giây đầu*
     - *Khuyến nghị an toàn chính sách & kiếm tiền*
2. **Bộ dữ liệu CSV (`.csv`):**
   - Mã hóa định dạng **`utf-8-sig`** để mở trực tiếp trên Microsoft Excel mà không bị lỗi font tiếng Việt.
   - Đầy đủ các trường: `cluster_id`, `cluster_name`, `keyword`, `vkos_score`, `vms`, `edo`, `csg`, `lrp`, `pms`, `ccv`, `avg_views`, `median_views`, `pct_long_videos`, `pct_evergreen`, `has_shorts_shelf`, `policy_status`, `is_top_1`.
3. **Dữ liệu JSON (`.json`):**
   - Cung cấp toàn bộ dữ liệu có cấu trúc cho các tác tử khác tiêu thụ hoặc tích hợp vào hệ thống tự động hóa.

---

## 6. Kiểm Thử & Nghiệm Thu (E2E Test)

Chạy test suite độc lập:
```bash
python tests/test_e2e.py
```
Test suite kiểm tra 5 hạng mục:
- ✅ Phân loại chính xác 5 cụm ý định tìm kiếm.
- ✅ Phân định chuẩn xác Vùng Xanh (Green) vs Nguy cơ Vàng nút (Yellow Dollar).
- ✅ Tính toán chuẩn xác công thức toán học và trọng số VKOS v3.0.
- ✅ Tạo lập đầy đủ các trường của Actionable Briefing.
- ✅ Thực thi CLI E2E và sinh đầy đủ 3 định dạng file báo cáo với `exit code == 0`.
