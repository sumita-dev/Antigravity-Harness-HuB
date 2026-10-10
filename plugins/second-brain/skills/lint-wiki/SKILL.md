---
name: lint-wiki
description: "Rà soát sức khoẻ Vault F:\\Obsidian\\ (broken links, orphans, missing pages, open questions, mâu thuẫn). Trả checklist, không tự sửa hàng loạt."
group: Second Brain
---

# LINT - Rà soát sức khoẻ Second Brain (F:\Obsidian)

Kiểm định toàn diện chất lượng liên kết, tính nhất quán và độ phủ tri thức trong Vault `F:\Obsidian\`.

## Vault Root & Phạm vi quét
- **Vault Root**: `F:\Obsidian`
- **Thư mục kiểm tra chính**: `F:\Obsidian\wiki\`
- **Tập tin chỉ mục**: `F:\Obsidian\wiki\index.md`
- **Tập tin câu hỏi mở**: `F:\Obsidian\wiki\_open-questions.md`

## Khi nào dùng
Kích hoạt khi người dùng yêu cầu:
- "Health check wiki"
- "Lint wiki / kiểm tra vault"
- "Wiki có lỗi gì không"
- "Rà soát các broken link hoặc orphan notes"

## 8 Nhóm vấn đề được rà soát
1. **Mâu thuẫn logic (Contradictions)**: Các section `## Mâu thuẫn` chưa được người dùng hợp nhất hoặc giải quyết.
2. **Khẳng định cũ/lỗi thời (Stale claims)**: Trang cũ chưa được cập nhật dữ liệu từ các source mới hơn.
3. **Trang mồ côi (Orphan notes)**: Các trang wiki không có liên kết ngược (`[[link]]`) từ bất kỳ trang nào khác.
4. **Trang còn thiếu (Missing concepts)**: Các khái niệm quan trọng được nhắc đến nhiều nơi nhưng chưa có trang riêng.
5. **Liên kết hỏng (Broken wikilinks)**: Các `[[wikilink]]` trỏ tới file không tồn tại.
6. **Trùng lặp (Duplicate notes)**: Hai hoặc nhiều trang có nội dung tương đồng cần đề xuất hợp nhất (merge).
7. **Lỗ hổng tri thức (Knowledge gaps)**: Vùng chủ đề mỏng cần nạp thêm tài liệu thô hoặc nghiên cứu bổ sung.
8. **Câu hỏi mở tồn đọng (Open questions)**: Các câu hỏi ghi nhận lâu ngày trong `F:\Obsidian\wiki\_open-questions.md`.

## Nguyên tắc vàng
- **CHỈ XUẤT CHECKLIST ĐÁNH SỐ**: Liệt kê rõ ràng vấn đề, file liên quan và mức độ ưu tiên.
- **TUYỆT ĐỐI KHÔNG TỰ Ý SỬA HÀNG LOẠT**: Chờ người dùng chỉ định mục cần xử lý để đảm bảo kiểm soát chất lượng và tính minh bạch.
