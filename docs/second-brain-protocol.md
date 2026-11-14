# Cơ Chế Tự Động Hoá Bộ Não Thứ 2 (Autonomous Second Brain — Obsidian Vault)

> Tài liệu tham chiếu on-demand được tách từ `GEMINI.md` theo nguyên tắc Progressive Disclosure.

1. **Chủ Động Tra Cứu (Auto-Query):** BẮT BUỘC tự tra cứu `$OBSIDIAN_VAULT_PATH/wiki/index.md` nạp bối cảnh, bài học cũ trước khi lập kế hoạch/giao việc.
2. **Chủ Động Tiêu Hoá (Auto-Ingest):** Dữ liệu mới trong `sources/` (hoặc `Raw/`) hoặc chat: tự điều phối tiêu hoá theo 3 kỷ luật (Citation cứng, Mục tiêu vs thực tế, Giữ mâu thuẫn) thành trang Evergreen trong `wiki/`, cập nhật `wiki/index.md` và `wiki/log.md`.
3. **Chủ Động Đúc Kết (Memory Reflection & Triad Lesson Schema):**
   - Lưu facts theo 2 tầng (`memory/facts/global/` hoặc `memory/facts/projects/<ten-du-an>/`), cập nhật mục lục `MEMORY.md`.
   - Append `wiki/projects/<ten-du-an>/log.md` (`## [YYYY-MM-DD] ...`).
   - Cập nhật `wiki/projects/<ten-du-an>/_session-handoff.md`.
   - Triad Lesson Schema 3 trường: `cue` (chỉ dấu/ngữ cảnh kích hoạt), `lesson` (hành động chuẩn cần làm), `evidence` (bằng chứng thực chứng: hash commit/spec, log lỗi thực tế hoặc exit code).
4. **Rà Soát Sức Khoẻ (Gap Detection):** Câu hỏi mở: tự append `wiki/_open-questions.md` và cảnh báo mâu thuẫn tri thức.
