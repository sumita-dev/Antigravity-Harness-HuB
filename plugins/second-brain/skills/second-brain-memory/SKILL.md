---
name: second-brain-memory
description: "Đồng bộ bài học kinh nghiệm, facts và session handoff vào memory/ và wiki/log.md."
group: Second Brain
---
# SECOND BRAIN MEMORY - Quản lý Ký ức & Đồng bộ Vault (F:\Obsidian)

Đồng bộ bộ nhớ dài hạn, ghi nhận sự kiện, quyết định kỹ thuật và trạng thái phiên làm việc trực tiếp vào Vault Obsidian tại `F:\Obsidian`.

## Vault Root & Cấu trúc lưu trữ
- **Vault Root**: `F:\Obsidian`
- **Bộ nhớ người dùng & facts**: `F:\Obsidian\memory\MEMORY.md`
- **Chi tiết facts**: `F:\Obsidian\memory\facts\`
- **Lịch sử hội thoại quan trọng**: `F:\Obsidian\memory\conversations\`
- **Nhật ký thời gian**: `F:\Obsidian\wiki\log.md`
- **Bàn giao phiên làm việc**: `F:\Obsidian\wiki\_session-handoff.md`

## Khi nào dùng
Kích hoạt khi:
- Người dùng yêu cầu lưu nhớ thông tin cá nhân, sở thích, quy ước lâu dài: "nhớ rằng...", "lưu vào bộ nhớ", "ghi nhớ cấu hình này".
- Kết thúc một phiên làm việc lớn cần bàn giao trạng thái (`handoff`).
- Cần ghi nhận một quyết định kỹ thuật/kiến trúc quan trọng vào nhật ký vault.
- Đồng bộ bài học kinh nghiệm (lessons learned) sau khi hoàn thành task.

## Quy trình đồng bộ

### 1. Đồng bộ Facts & Sở thích (`memory/`)
1. Đọc file `F:\Obsidian\memory\MEMORY.md`.
2. Phân loại thông tin: Sở thích người dùng, quy ước hệ thống, đường dẫn cố định, thông tin dự án.
3. Cập nhật có cấu trúc vào `F:\Obsidian\memory\MEMORY.md` hoặc tạo file chi tiết trong `F:\Obsidian\memory\facts\<chủ_đề>.md` kèm liên kết ngược.

### 2. Ghi nhận Nhật ký thời gian (`wiki/log.md`)
Append một mục mới theo định dạng chuẩn:
```markdown
## [YYYY-MM-DD] decision | <Tiêu đề ngắn gọn>
- **Bối cảnh**: <Mô tả ngắn>
- **Quyết định**: <Nội dung quyết định>
- **Liên quan**: [[Tên Trang Wiki hoặc Nguồn]]
```

### 3. Bàn giao phiên (`wiki/_session-handoff.md`)
Khi chuyển giao phiên hoặc kết thúc đợt làm việc lớn:
```markdown
# Session Handoff [YYYY-MM-DD]
- **Mục tiêu**: ...
- **Đã hoàn thành**: ...
- **Đang xử lý**: ...
- **Quyết định đã chốt**: ...
- **Các bước tiếp theo**: ...
- **File liên quan**: ...
- **Status**: active | clear
```

### 4. Đúc kết Bài học Kinh nghiệm (Triad Lesson Schema)
Mọi bài học kinh nghiệm (lessons learned) được đúc kết vào Vault Obsidian (`F:\Obsidian\memory\facts/` hoặc `F:\Obsidian\wiki\log.md`) bắt buộc phải tuân theo cấu trúc Triad Lesson Schema gồm 3 trường:
- **cue**: Chỉ dấu / ngữ cảnh kích hoạt (tình huống, triệu chứng lỗi hoặc tín hiệu nhận diện).
- **lesson**: Hành động chuẩn / bài học rút ra (quy tắc xử lý, kiến trúc chuẩn, giải pháp khắc phục).
- **evidence**: Bằng chứng thực chứng xác thực (commit hash, Spec SHA256, log lỗi thực tế hoặc lệnh kiểm chứng có `exit code == 0`).

Định dạng mẫu:
```markdown
- **cue**: <Chỉ dấu kích hoạt hoặc triệu chứng lỗi>
- **lesson**: <Hành động chuẩn / giải pháp rút ra>
- **evidence**: <Bằng chứng: hash, log lỗi hoặc exit code == 0>
```

