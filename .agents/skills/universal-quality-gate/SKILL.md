---
name: universal-quality-gate
description: >-
  Hướng dẫn vận hành Hệ thống Cổng Kiểm Soát Cứng Đa Nhiệm (Crawl Completeness,
  Code Syntax & JSON, Markdown & Local Link Integrity) được kích hoạt tự động
  qua .agents/hooks.json.
---

# Universal Quality Gate

Hệ thống gồm 3 cổng kiểm soát cứng tự động chạy qua `hooks.json` (`PostToolUse` tracker + `Stop` enforcer):

1. **Crawl Completeness Gate (`audit_crawl.py`):**
   - Kiểm tra mọi file `.md` trong thư mục `*_crawled/` phải `>= 300` ký tự sạch, không có stub chuyển trang/`404`, không trùng `SHA-256`.
   - Đối chiếu toàn bộ link tham chiếu chéo trong file đã cào; nếu còn sót URL mục tiêu -> Gate chặn `decision: "continue"` và liệt kê URL thiếu.
   - Có thể tạo file `audit_ignore.txt` trong thư mục crawl để khai báo các pattern URL cố tình bỏ qua (ví dụ `/en/`, `cookie`, `transparency`).

2. **Code Syntax Gate (`audit_code.py`):**
   - Chạy `py_compile` cho mọi file `.py` và `json.loads()` cho mọi file `.json` vừa tạo/sửa.

3. **Markdown & Link Integrity Gate (`audit_markdown.py`):**
   - Kiểm tra UTF-8 và xác minh mọi liên kết nội bộ (`file:///...` hoặc relative path) đều tồn tại trên đĩa.

4. **Circuit Breaker:**
   - Tối đa 2 lần chặn liên tiếp mỗi turn (`MAX_GATE_RETRIES = 2`) để tránh treo vòng lặp vô hạn.
