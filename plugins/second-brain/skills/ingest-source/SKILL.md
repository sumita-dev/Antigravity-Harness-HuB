---
name: ingest-source
description: "Tiêu hoá tài liệu thô từ F:\\Obsidian\\sources\\ vào F:\\Obsidian\\wiki\\, chưng cất thành tri thức tích luỹ theo 3 kỷ luật."
group: Second Brain
---

# INGEST - Tiêu hoá tài liệu thô vào Wiki (F:\Obsidian)

Chưng cất tài liệu thô trong `F:\Obsidian\sources\` thành các trang tri thức liên kết bền vững trong `F:\Obsidian\wiki\`.

## Vault Root & Cấu trúc mặc định
- **Vault Root**: `F:\Obsidian`
- **Nguồn thô**: `F:\Obsidian\sources\` (BẤT BIẾN với nội dung — chỉ đọc, chỉ sửa frontmatter)
- **Wiki**: `F:\Obsidian\wiki\` (1 trang = 1 ý, liên kết chéo)
- **Mục lục**: `F:\Obsidian\wiki\index.md`
- **Nhật ký**: `F:\Obsidian\wiki\log.md`
- **Câu hỏi mở**: `F:\Obsidian\wiki\_open-questions.md`

## Khi nào dùng
Kích hoạt khi người dùng yêu cầu:
- "Tiêu hoá source này vào wiki"
- "Xử lý bài viết/sách/tài liệu này vào Second Brain"
- "Đọc file trong sources/ rồi ghi lại kiến thức"
- Có tài liệu mới được đưa vào `F:\Obsidian\sources\`

## 3 Kỷ luật chống Wiki rỗng/sai (Bắt buộc)
1. **Citation trong thân bài**: Mọi khẳng định cụ thể (số liệu, quy trình, trích dẫn) phải kết bằng `[[Nguồn]]`.
2. **Phân biệt mục tiêu vs thực tế**: Gắn nhãn rõ ràng: `(mục tiêu)` / `(thực tế tính đến [thời điểm])` / `(cần xác minh)`.
3. **Mâu thuẫn giữ rõ, không ghi đè**: Source mới mâu thuẫn Wiki cũ -> giữ cả hai quan điểm trong section `## Mâu thuẫn`, append vào `_open-questions.md`, không xoá đè.

## Quy trình tiêu hoá
1. **Kiểm tra trạng thái**: Đọc frontmatter của source. Nếu `status: processed` -> Dừng lại và hỏi người dùng có muốn re-ingest không.
2. **Phân loại độ dài**:
   - Nếu source dài (>= 10.000 dòng hoặc sách lớn): Áp dụng 3-pass (Đọc lướt lập outline -> Đọc sâu từng đoạn 1.000-1.500 dòng và viết wiki ngay -> Đặt 5 câu hỏi kiểm tra độ phủ).
3. **Chưng cất tri thức**:
   - Tóm tắt 3-5 ý cốt lõi và rút ra insight/framework.
   - Đối chiếu `F:\Obsidian\wiki\index.md` để xác định trang cần tạo mới, cập nhật hoặc hợp nhất.
   - Viết trang wiki có ngữ cảnh tự thân (Contextual Retrieval), thêm frontmatter:
     ```yaml
     type: wiki
     status: active
     tags: [wiki, <chủ_đề>]
     aliases: [<tên_khác>, <tiếng_anh>]
     source: "[[Tên Source]]"
     ```
4. **Cập nhật chỉ mục & nhật ký**:
   - Thêm dòng tóm tắt vào `F:\Obsidian\wiki\index.md`.
   - Cập nhật frontmatter source: `status: processed`, `processed_at`, `wiki_links: [...]`.
   - Ghi nhật ký vào `F:\Obsidian\wiki\log.md`: `## [YYYY-MM-DD] ingest | <Tên Source>`.
5. **Báo cáo**: Tóm tắt ngắn gọn các trang đã tạo/sửa, insight chính và đề xuất task hành động (nếu có).
