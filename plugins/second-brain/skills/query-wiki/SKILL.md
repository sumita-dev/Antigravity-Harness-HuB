---
name: query-wiki
description: "Khai thác tri thức trong Second Brain (F:\\Obsidian): tổng hợp, so sánh, giả thuyết từ wiki/ và wiki/index.md. Trả lời có trích dẫn."
group: Second Brain
---

# QUERY - Tra cứu tri thức từ Obsidian Wiki (F:\Obsidian)

Khai thác tri thức trong Second Brain tại `F:\Obsidian`: tổng hợp, so sánh, phân tích giả thuyết và truy xuất thông tin từ mạng lưới ghi chú liên kết.

## Vault Root & Cấu trúc mặc định
- **Vault Root**: `F:\Obsidian`
- **Mục lục tri thức**: `F:\Obsidian\wiki\index.md`
- **Thư mục Wiki**: `F:\Obsidian\wiki\`
- **Nguồn thô**: `F:\Obsidian\sources\`
- **Câu hỏi tồn đọng**: `F:\Obsidian\wiki\_open-questions.md`

## Khi nào dùng
Kích hoạt khi người dùng hỏi hoặc muốn khai thác tri thức trong Second Brain:
- "Tổng hợp các framework về X"
- "So sánh A vs B vs C trong wiki"
- "Wiki có gì về Y"
- "Tra cứu tri thức trong vault"

## Quy trình thực hiện
1. **Đọc mục lục**: Đọc `F:\Obsidian\wiki\index.md` TRƯỚC để nắm toàn bộ danh mục và các trang hiện có.
2. **Đọc trang chi tiết**: Đọc các trang wiki liên quan trong `F:\Obsidian\wiki\`; theo dõi các liên kết `[[wikilink]]` để có đầy đủ ngữ cảnh.
3. **Tra cứu nguồn thô (nếu thiếu)**: Nếu wiki chưa đủ thông tin, đọc tiếp file nguồn tương ứng trong `F:\Obsidian\sources\`. Nếu vẫn thiếu, append 1 dòng vào `F:\Obsidian\wiki\_open-questions.md`.
4. **Trả lời có trích dẫn**: Ghi rõ `[[citation]]` cho mọi khẳng định cụ thể. Nêu rõ ranh giới kiến thức (phần nào wiki chưa đề cập) thay vì tự suy diễn.
5. **Đề xuất tích luỹ (Compounding)**: Nếu câu trả lời có giá trị tái sử dụng cao (bảng so sánh mới, phân tích tổng hợp mới) -> Đề xuất lưu thành 1 trang wiki mới trong `F:\Obsidian\wiki\` và cập nhật vào `F:\Obsidian\wiki\index.md`.
