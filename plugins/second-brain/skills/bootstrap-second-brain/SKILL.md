---
name: bootstrap-second-brain
description: "Tạo mới trọn gói một Second Brain (Obsidian LLM Wiki) trên máy mới từ thư mục nguồn hỗn hợp (docx, pdf, xlsx, pptx, html, png, jpg, md, txt...): dựng cấu trúc Vault, dùng Microsoft MarkItDown convert tài liệu sang Markdown, dùng Vision trích xuất ảnh, ingest hàng loạt vào wiki/, kiểm định lint và thiết lập auto-sync."
group: Second Brain
---

# BOOTSTRAP SECOND BRAIN (END-TO-END FROM RAW SOURCES)

Quy trình 1-lệnh tạo mới hoàn chỉnh một **Second Brain** theo chuẩn Karpathy LLM Wiki từ bất kỳ thư mục nguồn hỗn hợp nào (đặc biệt khi thiết lập trên máy tính mới).

---

## 1. Khi nào kích hoạt
- Người dùng ở máy mới hoặc có một thư mục chứa tài liệu hỗn hợp (`.docx`, `.doc`, `.pdf`, `.xlsx`, `.pptx`, `.html`, `.csv`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.txt`, `.md`) và yêu cầu *"tạo Second Brain"*, *"xây dựng Second Brain từ thư mục X"*.

---

## 2. Quy trình 5 Pha Khép Kín

### Pha 1: Xác nhận & Khởi tạo Vault + Môi trường
1. Nếu chưa rõ đường dẫn **thư mục nguồn** hoặc **thư mục Vault đích**, hỏi xác nhận ngắn gọn qua `ask_question` hoặc text.
2. Chạy script khởi tạo & chuyển đổi:
   ```powershell
   python "<SKILL_DIR>/scripts/bootstrap_vault.py" --source "<SOURCE_DIR>" --vault "<VAULT_DIR>" --install-markitdown
   ```
3. Script tự động thực hiện:
   - Kiểm tra `markitdown`; nếu máy mới chưa có sẽ tự cài `pip install "markitdown[all]"` (nguồn Microsoft `microsoft/markitdown`).
   - Tạo cấu trúc Vault chuẩn 3 lớp nếu chưa có (`Raw/`, `wiki/`, `memory/`, `templates/`, `ops/`, `CLAUDE.md`, `AGENTS.md`, `<VAULT_DIR>/wiki/_index.md`, `<VAULT_DIR>/wiki/log.md`, `<VAULT_DIR>/wiki/_open-questions.md`, `<VAULT_DIR>/wiki/_session-handoff.md`, `<VAULT_DIR>/ops/wiki_ops.py`, `<VAULT_DIR>/ops/run-*.ps1` dùng `$PSScriptRoot`).
   - Sao chép an toàn toàn bộ tài liệu gốc từ `<SOURCE_DIR>` vào `<VAULT_DIR>/Raw/` (giữ nguyên bản gốc bất biến).

### Pha 2: Chuyển đổi sang Markdown (Microsoft MarkItDown + AI Vision)
1. **Tài liệu văn phòng & PDF/Web/Data:** Script `bootstrap_vault.py` tự động dùng **Microsoft MarkItDown** chuyển đổi hàng loạt `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.html`, `.htm`, `.csv`, `.tsv`, `.json`, `.xml`, `.zip`, `.epub` sang `.md` (UTF-8 No-BOM) đặt cùng vị trí tương đối trong `Raw/`. Các file `.txt` được chuyển sang `.md` giữ nguyên văn.
2. **Hình ảnh (`.png`, `.jpg`, `.jpeg`, `.webp`):**
   - Script trả về danh sách `pending_images` trong JSON output.
   - AI Agent dùng `read_file` đọc trực tiếp từng ảnh trong `pending_images`, trích xuất toàn bộ chữ (OCR), số liệu, bảng biểu và mô tả sơ đồ/insight thành file `<ten-anh>.md` đặt cạnh ảnh trong `Raw/` kèm liên kết nhúng `![[<ten-anh>.ext]]`.

### Pha 3: Chưng cất tri thức vào `wiki/` (Batch Ingest)
1. Áp dụng skill `ingest-source` (và `run_workflow` / subagent nếu có >= 5 tài liệu `.md` cần xử lý song song).
2. Tuân thủ **3 kỷ luật bắt buộc**:
   - Citation `[[Raw/...]]` trong thân bài.
   - Phân biệt rõ mục tiêu vs thực tế.
   - Giữ rõ mâu thuẫn (`## Mâu thuẫn` + ghi `<VAULT_DIR>/wiki/_open-questions.md`).
3. Mọi trang `wiki/` đều phải có frontmatter 4 key (`linh_vuc`, `do_uu_tien`, `trang_thai`, `ngay_cap_nhat`), cập nhật `<VAULT_DIR>/wiki/_index.md` và ghi nhật ký vào `<VAULT_DIR>/wiki/log.md`.

### Pha 4: Kiểm định chất lượng (Ops & Lint)
Chạy kiểm tra thực chứng tại `<VAULT_DIR>`:
```powershell
python "<VAULT_DIR>/ops/wiki_ops.py" weekly
```
Yêu cầu đạt: `broken_links == 0`, `orphan_pages == 0`, `files_missing_metadata == 0`, `raw_missing_in_wiki_count == 0`.

### Pha 5: Thiết lập Tự động hóa (Tùy chọn)
Hỏi người dùng có muốn bật đồng bộ Git & lịch kiểm tra định kỳ trên Windows không:
- Nếu đồng ý: khởi tạo `git init`, tạo `.gitignore`, `sync-vault.ps1` (dùng `$PSScriptRoot`), và đăng ký Windows Task Scheduler (`Daily`, `Weekly`, `Monthly`).

---

## 3. Ràng buộc An Toàn
- Tuyệt đối không sửa nội dung các file gốc trong `Raw/` (chỉ được tạo file `.md` chuyển đổi đi kèm và không ghi đè file `.md` đã tồn tại trừ khi truyền `--overwrite`).
- Mọi subprocess chạy từ Python phải khóa `stdin=subprocess.DEVNULL` và xuất UTF-8.
