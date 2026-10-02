---
name: kahneman-creative-ads
description: Use when the user asks for creative strategy, content angles, ad territories, hooks for ads, soft-sell content strategy, chien luoc sang tao, goc noi dung, canvas quang cao, or runs /kahneman-creative-ads; builds a 1-page Creative Strategy Canvas plus 8 creative territories mapped to Kahneman cognitive mechanisms.
---

# Kahneman Creative Ads

Dùng **Thinking, Fast and Slow** làm hệ điều hành cho chiến lược sáng tạo quảng cáo.
Skill này **không** thay research thị trường / media plan. Nó sinh **2 deliverable bắt buộc**:

1. **Creative Strategy Canvas (1 trang)** — đã điền cho sản phẩm cụ thể  
2. **Bộ 8 creative territories** — góc nội dung + hook mẫu + map 1 cơ chế Kahneman / territory  

Giao tiếp với user bằng **tiếng Việt** (trừ khi họ yêu cầu khác). Gọi user là **"Sếp"**, xưng **"em"** nếu workspace/AGENTS yêu cầu.

## Khi nào chạy

- User muốn góc content / hook / canvas chiến lược ads  
- User đưa brief sản phẩm + persona + mục tiêu ads  
- `/kahneman-creative-ads`

## Bước 0 — Đủ brief chưa?

Nếu thiếu input quan trọng → **hỏi ngay**, không đoán bừa. Checklist:

| # | Field | Bắt buộc? |
|---|--------|-----------|
| 1 | Sản phẩm / category | Có |
| 2 | 1–3 điểm khác biệt / truth (spec, chứng nhận, form…) | Có |
| 3 | Persona (ai, giai đoạn đời) | Có |
| 4 | Thu nhập / segment (nếu có) | Nên có |
| 5 | Giá | Nên có |
| 6 | Mục tiêu ads (bán / awareness / lead) | Có |
| 7 | Ràng buộc giọng (vd. hạn chế từ bán hàng) | Nếu user có |
| 8 | Thị trường / ngôn ngữ (mặc định: Việt Nam, tiếng Việt) | Mặc định OK |
| 9 | SKU variants (màu, size, ngắn/dài…) | Nếu có |

Chỉ khi đủ (1)(2)(3)(6) mới viết full 2 deliverable. Có thể đọc thêm:

- `references/kahneman-mechanisms.md` — glossary cơ chế  
- `references/canvas-template.md` — khung Canvas trống  
- `references/example-baby-body.md` — case mẫu (body sơ sinh)  

## Nguyên tắc cốt lõi (không bỏ)

1. **System 1 trước, System 2 sau** — ads thắng impression; trang SP lo lý lẽ/giá/giỏ.  
2. **Substitution** — xác định *câu hỏi S1* mẹ/khách thực sự trả lời (dễ), không chỉ câu marketing (khó).  
3. **WYSIATI** — mọi claim quan trọng phải *thấy được* trên frame (vải, da, thao tác, kết).  
4. **Cognitive ease** — 1 ý / spot; câu ngắn; tránh jargon lab trừ khi dịch ra cảm giác.  
5. **Prospect theory** — chọn frame: gain / loss nhẹ / certainty / possibility; loss aversion ~2:1 nhưng **không hù dọa**.  
6. **Peak–end** — cấu trúc nội dung: peak sớm → coherence → end cảm xúc + CTA mềm.  
7. **Soft-sell (nếu user yêu cầu hạn chế từ bán)** — tránh: mua ngay, sale, chốt đơn, lastest, giảm sốc. Ưu tiên: khoảnh khắc, an tâm, chăm, xem chất liệu/size, lưu gợi ý.  
8. **Trung thực** — claim đúng phạm vi (vd. chứng nhận *vải*, không hứa “không bao giờ dị ứng”).  
9. **Phân tích, không tóm tắt sách** — dùng cơ chế để *quyết định creative*, không giảng lại Kahneman dài.

## Deliverable 1 — Creative Strategy Canvas (1 trang)

Xuất **một bảng / các ô gọn**, đã điền. Không để placeholder suông.

### Template bắt buộc (điền hết)

| Ô | Nội dung cần có |
|---|-----------------|
| **Sản phẩm** | Tên/category + truth 1 dòng (spec cốt lõi) |
| **Giá & segment** | Giá; persona thu nhập/đời sống nếu có |
| **Persona** | Ai; giai đoạn; nỗi/mong S1 |
| **Câu hỏi S1 cần thắng** | 1 câu substitution (không phải USP feature) |
| **Không bán / Đang “bán”** | Feature không lead vs trạng thái cảm xúc/identity lead |
| **Big idea** | 1 câu chiến lược (có thể 2 biến thể ngắn) |
| **Frame prospect** | Gain / loss nhẹ / certainty / possibility + vì sao |
| **WYSIATI must-show** | 3–6 thứ *phải thấy* trên ads |
| **Ease package** | Message 1 ý; ngôn ngữ cấm/ưu tiên |
| **Peak → End** | Peak 0–3s; end frame; CTA mềm |
| **Giá trên ads** | Cách neo (anchor) hoặc *không* nói giá trên ads |
| **Ads vs Landing** | Ads = S1; landing = S2 (spec %, chứng nhận đủ chữ, size, giá) |
| **KPI “bán gián tiếp”** | Hold 3s/50%, save, comment hỏi size, ATC từ landing… |
| **Rủi ro** | 3–5 cấm (fear porn, overclaim, hard-sell, visual sai…) |

Thêm **2–4 dòng “chiến lược một câu cho team”** ở cuối Canvas.

Chi tiết ô: `references/canvas-template.md`.

## Deliverable 2 — 8 Creative Territories

Đúng **8** territory. Mỗi cái **map đúng 1 cơ chế chính** từ sách (có thể ghi cơ chế phụ 1 dòng).

### Format mỗi territory (bắt buộc)

```markdown
### T[n] — [Tên góc]
- **Cơ chế Kahneman (chính):** [tên] — [1 câu giải thích áp dụng]
- **Cơ chế phụ (nếu có):** …
- **Persona / lúc dùng:** …
- **Góc nội dung:** 2–4 câu chiến lược
- **Hook mẫu (3–5 câu):** 
  1. "…"
  2. "…"
- **Must-show (WYSIATI):** …
- **CTA mềm:** …
- **Tránh:** …
```

### Bộ 8 cơ chế — phân bổ gợi ý (đổi tên góc theo product, **giữ đủ 8 lớp cơ chế**)

Dùng đủ các lớp sau (thứ tự territory có thể đổi):

| # | Lớp cơ chế bắt buộc cover | Gợi ý tên territory |
|---|---------------------------|---------------------|
| 1 | **Loss aversion / ma sát** (mất thời gian, bình tĩnh, kiểm soát) | Relief / “bớt một việc khó” |
| 2 | **Certainty / safety cues** (bình an, proof an toàn — không scare) | Gần da / tin cậy |
| 3 | **Endowment / chuẩn bị tương lai** (sở hữu tâm lý, “góc chờ”) | Ritual chuẩn bị / quà cho mình |
| 4 | **Peak–end / remembering self** | Khoảnh khắc đáng nhớ |
| 5 | **Representativeness / identity** (“người như mình”) | Persona mirror |
| 6 | **Availability** (nỗi/điều kiện sống *dễ nhớ*, concrete) | Bối cảnh đời thật |
| 7 | **Cognitive ease / load** (ai cũng làm được, bớt System 2) | Đơn giản hóa / người hỗ trợ |
| 8 | **Mere exposure / continuity** (lặp hành trình, size, season) | Hành trình dài / series |

Nếu product có **spec mạnh** (chứng nhận, chất liệu): gộp vào T2 (certainty) + WYSIATI; **dịch spec → cảm giác** trước, số lab để landing.

Nếu **hạn chế SKU** (1 màu, 2 form…): biến thành territory identity/ease (tinh gọn), không xin lỗi.

Hooks phải **nghe được trên ads** (thoại/caption), khớp ràng buộc soft-sell nếu có.

## Thứ tự output

1. Brief restated (5–8 dòng) — chứng minh đã hiểu  
2. **Deliverable 1 — Canvas**  
3. **Deliverable 2 — 8 territories**  
4. **Gợi ý 7–14 ngày content** (map T1…T8, optional nhưng nên có)  
5. **Câu hỏi mở** nếu cần truth thêm (ảnh, chứng chỉ logo, size chart…)  

## Chất lượng

- Không giảng lại cả cuốn sách.  
- Không generic “content value” thiếu map cơ chế.  
- Mỗi territory **một** cơ chế chính phân biệt — tránh 8 territory cùng “cảm xúc mẹ”.  
- Spec đúng: % vải, chứng nhận, variant.  
- Với case body sơ sinh mẫu: xem `references/example-baby-body.md` (tham chiếu, **không** copy nguyên nếu product khác).  

## Slash

`/kahneman-creative-ads`
