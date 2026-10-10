---
name: second-brain-memory
description: "Tự động đồng bộ bài học kinh nghiệm, facts, quyết định và session handoff vào F:\\Obsidian\\memory\\ và F:\\Obsidian\\wiki\\log.md."
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
