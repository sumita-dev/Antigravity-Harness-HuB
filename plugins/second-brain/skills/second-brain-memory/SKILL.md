---
name: second-brain-memory
description: "Đồng bộ bài học kinh nghiệm, facts và session handoff theo kiến trúc 2 tầng (Global Hub + Project Silos) vào Obsidian Vault."
group: Second Brain
---
# SECOND BRAIN MEMORY - Quản lý Ký ức & Đồng bộ Vault (Obsidian Vault)

Đồng bộ bộ nhớ dài hạn, ghi nhận sự kiện, quyết định kỹ thuật và trạng thái phiên làm việc trực tiếp vào Vault Obsidian tại `$env:OBSIDIAN_VAULT_PATH` (mặc định `~/Obsidian`) theo mô hình **1 Vault Hub + Project Silos (2 Tầng)**.

## Vault Root & Quy tắc Phân tầng Lưu trữ
- **Vault Root**: `$env:OBSIDIAN_VAULT_PATH` (mặc định `~/Obsidian`). Nếu dự án yêu cầu cô lập NDA/bàn giao riêng, override `$env:OBSIDIAN_VAULT_PATH` theo workspace đó.
- **Quy tắc `<ten-du-an>` (Deterministic Slug)**: Lấy cố định từ **tên thư mục gốc của workspace hiện tại**, chuẩn hóa chữ thường và thay khoảng trắng/ký tự đặc biệt bằng `-` (ví dụ: `Antigravity-Harness-HuB-main` -> `antigravity-harness-hub-main`). Tự động tạo thư mục dự án nếu chưa tồn tại (lazy-create).

### Tầng 1: Global (Dùng chung liên dự án)
- **Bộ nhớ cốt lõi & danh mục dự án**: `$OBSIDIAN_VAULT_PATH/memory/MEMORY.md` (chỉ lưu sở thích cá nhân, quy ước hệ thống chung và `[[wikilink]]` trỏ sang từng dự án).
- **Facts & Triad Lessons phổ quát**: `$OBSIDIAN_VAULT_PATH/memory/facts/global/<chủ_đề>.md`
- **Chỉ mục & Nhật ký chung**: `$OBSIDIAN_VAULT_PATH/wiki/index.md` và `$OBSIDIAN_VAULT_PATH/wiki/log.md`

### Tầng 2: Project Silos (Cô lập theo `<ten-du-an>`)
- **Lịch sử toàn bộ phiên chat dự án**: `$OBSIDIAN_VAULT_PATH/memory/conversations/<ten-du-an>-all-sessions.md`
- **Facts & Triad Lessons đặc thù dự án**: `$OBSIDIAN_VAULT_PATH/memory/facts/projects/<ten-du-an>/<chủ_đề>.md`
- **Nhật ký quyết định dự án**: `$OBSIDIAN_VAULT_PATH/wiki/projects/<ten-du-an>/log.md`
- **Bàn giao phiên dự án**: `$OBSIDIAN_VAULT_PATH/wiki/projects/<ten-du-an>/_session-handoff.md`

## Khi nào dùng
Kích hoạt khi:
- Người dùng gõ `savebrain` hoặc yêu cầu lưu nhớ thông tin cá nhân, sở thích, quy ước lâu dài ("nhớ rằng...", "lưu vào bộ nhớ", "ghi nhớ cấu hình này").
- Kết thúc một phiên làm việc lớn cần bàn giao trạng thái (`handoff`).
- Cần ghi nhận một quyết định kỹ thuật/kiến trúc quan trọng vào nhật ký dự án.
- Đồng bộ bài học kinh nghiệm (lessons learned) sau khi hoàn thành task.

## Quy trình đồng bộ

### 0. Quy tắc Gom Toàn Bộ Phiên Chat Trong Dự Án (`savebrain`)
- Khi người dùng kích hoạt `savebrain` trong một thư mục dự án, **KHÔNG chỉ lưu riêng phiên chat hiện tại**.
- Nếu trong workspace tồn tại `.sessions/sessions_index.json` (hoặc thư mục `.sessions/`), **BẮT BUỘC quét toàn bộ các phiên chat gốc (`nesting_depth === 0` / có `title`) trong cùng thư mục dự án** để tổng hợp đầy đủ lịch sử quyết định kỹ thuật, kiến trúc, bài học kinh nghiệm và tài liệu liên quan vào `$OBSIDIAN_VAULT_PATH/memory/conversations/<ten-du-an>-all-sessions.md` (hoặc `memory/facts/projects/<ten-du-an>/`), đồng thời gắn liên kết từ `memory/MEMORY.md` và `wiki/projects/<ten-du-an>/log.md`.

### 1. Đồng bộ Facts & Sở thích (`memory/`)
1. Đọc `$OBSIDIAN_VAULT_PATH/memory/MEMORY.md`.
2. Phân loại thông tin:
   - **Global** (sở thích người dùng, quy ước hệ thống chung, bài học dùng cho mọi repo): cập nhật vào `$OBSIDIAN_VAULT_PATH/memory/MEMORY.md` hoặc tạo tệp trong `$OBSIDIAN_VAULT_PATH/memory/facts/global/<chủ_đề>.md`.
   - **Project** (kiến trúc, đường dẫn, cấu hình đặc thù của dự án): tạo/cập nhật trong `$OBSIDIAN_VAULT_PATH/memory/facts/projects/<ten-du-an>/<chủ_đề>.md` và chỉ gắn `[[wikilink]]` tóm tắt trong `MEMORY.md` để giữ `MEMORY.md` gọn nhẹ.

### 2. Ghi nhận Nhật ký thời gian (`wiki/projects/<ten-du-an>/log.md`)
Append một mục mới vào `$OBSIDIAN_VAULT_PATH/wiki/projects/<ten-du-an>/log.md` (nếu là sự kiện liên dự án/toàn cục thì ghi vào `$OBSIDIAN_VAULT_PATH/wiki/log.md`) theo định dạng chuẩn:
```markdown
## [YYYY-MM-DD] decision | <Tiêu đề ngắn gọn>
- **Bối cảnh**: <Mô tả ngắn>
- **Quyết định**: <Nội dung quyết định>
- **Liên quan**: [[Tên Trang Wiki hoặc Nguồn]]
```

### 3. Bàn giao phiên (`wiki/projects/<ten-du-an>/_session-handoff.md`)
Khi chuyển giao phiên hoặc kết thúc đợt làm việc lớn, ghi vào `$OBSIDIAN_VAULT_PATH/wiki/projects/<ten-du-an>/_session-handoff.md` để không ghi đè trạng thái của các dự án khác:
```markdown
# Session Handoff [YYYY-MM-DD] — <ten-du-an>
- **Mục tiêu**: ...
- **Đã hoàn thành**: ...
- **Đang xử lý**: ...
- **Quyết định đã chốt**: ...
- **Các bước tiếp theo**: ...
- **File liên quan**: ...
- **Status**: active | clear
```

### 4. Đúc kết Bài học Kinh nghiệm (Triad Lesson Schema)
Mọi bài học kinh nghiệm (lessons learned) được đúc kết vào Tầng Global (`memory/facts/global/` hoặc `wiki/log.md`) hoặc Tầng Project (`memory/facts/projects/<ten-du-an>/` hoặc `wiki/projects/<ten-du-an>/log.md`) bắt buộc phải tuân theo cấu trúc Triad Lesson Schema gồm 3 trường:
- **cue**: Chỉ dấu / ngữ cảnh kích hoạt (tình huống, triệu chứng lỗi hoặc tín hiệu nhận diện).
- **lesson**: Hành động chuẩn / bài học rút ra (quy tắc xử lý, kiến trúc chuẩn, giải pháp khắc phục).
- **evidence**: Bằng chứng thực chứng xác thực (commit hash, Spec SHA256, log lỗi thực tế hoặc lệnh kiểm chứng có `exit code == 0`).

Định dạng mẫu:
```markdown
- **cue**: <Chỉ dấu kích hoạt hoặc triệu chứng lỗi>
- **lesson**: <Hành động chuẩn / giải pháp rút ra>
- **evidence**: <Bằng chứng: hash, log lỗi hoặc exit code == 0>
```
