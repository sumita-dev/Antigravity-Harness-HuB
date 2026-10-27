---
name: ingest-source
description: "Tiêu hoá tài liệu thô từ sources/ vào wiki/ theo mô hình Ingestion Agentic RAG và 3 kỷ luật chưng cất tri thức."
group: Second Brain
---
# INGEST - Tiêu hoá tài liệu thô vào Wiki bằng Ingestion Agentic RAG (Obsidian Vault)

Chưng cất tài liệu thô trong `sources/` thành các trang tri thức liên kết bền vững trong `wiki/` bằng mô hình **Ingestion Agentic RAG**: tự động phân rã luận điểm, đối chiếu ngữ nghĩa đa chiều với kho tri thức sẵn có, phát hiện và lưu giữ mâu thuẫn tri thức theo đúng chuẩn Karpathy LLM Wiki.

## Vault Root & Cấu trúc mặc định
- **Vault Root**: `$env:OBSIDIAN_VAULT_PATH` (hoặc `~/Obsidian`)
- **Nguồn thô**: `sources/` (BẤT BIẾN với nội dung — chỉ đọc, chỉ sửa frontmatter)
- **Wiki (Evergreen Notes)**: `wiki/` (1 trang = 1 ý, liên kết chéo)
- **Mục lục**: `wiki/index.md` & `wiki/_index.md`
- **Nhật ký**: `wiki/log.md`
- **Câu hỏi mở & Mâu thuẫn**: `wiki/_open-questions.md`

## Khi nào dùng
Kích hoạt khi người dùng yêu cầu:
- "Tiêu hoá source này vào wiki"
- "Xử lý bài viết/sách/tài liệu này vào Second Brain"
- "Đọc file trong sources/ rồi ghi lại kiến thức"
- Có tài liệu mới được đưa vào `sources/`

## 3 Kỷ luật chống Wiki rỗng/sai (Bắt buộc)
1. **Citation trong thân bài**: Mọi khẳng định cụ thể (số liệu, quy trình, trích dẫn) phải kết bằng `[[Nguồn]]`.
2. **Phân biệt mục tiêu vs thực tế**: Gắn nhãn rõ ràng: `(mục tiêu)` / `(thực tế tính đến [thời điểm])` / `(cần xác minh)`.
3. **Mâu thuẫn giữ rõ, không ghi đè**: Source mới mâu thuẫn Wiki cũ -> giữ cả hai quan điểm trong section `## Mâu thuẫn & Tranh luận`, append vào `_open-questions.md`, tuyệt đối không xoá đè.

---

## Quy trình Tiêu hoá bằng Ingestion Agentic RAG

### Bước 1: Inspect & Partition (Kiểm tra & Phân loại)
1. **Kiểm tra trạng thái**: Đọc frontmatter của source. Nếu `status: processed` -> Dừng lại và hỏi người dùng có muốn re-ingest không.
2. **Phân loại độ dài & Ngân sách context**:
   - Nếu source dài (>= 10.000 dòng hoặc sách lớn): Áp dụng 3-pass (Đọc lướt lập outline -> Đọc sâu từng đoạn 1.000-1.500 dòng và viết wiki ngay -> Đặt 5 câu hỏi kiểm tra độ phủ).
   - Đẩy tác vụ đọc nặng sang Subagent chuyên trách (`Model: "flash"`) nếu tài liệu thô > 2.000 dòng.

### Bước 2: Extraction & Decomposition (Bóc tách luận điểm & thực thể)
Trích xuất từ tài liệu thô:
- **Thực thể mới (New Entities):** Khái niệm, công cụ, mô hình, tác giả.
- **Khẳng định cốt lõi (Core Assertions):** Các luận điểm, số liệu, quy tắc thực hành.
- **Quan hệ logic:** Đối kháng (vs), bổ trợ, phụ thuộc.

### Bước 3: Cross-Vault Agentic Retrieval (Đối chiếu đa chiều với Vault)
Trước khi tạo trang mới, tác tử kích hoạt truy xuất Agentic RAG trên Obsidian Vault:
1. Tra cứu `wiki/index.md` và dùng Obsidian MCP (`mcp_obsidian-vault_search_files`) để tìm các trang liên quan đến thực thể mới.
2. **Đối chiếu mâu thuẫn (Contradiction Check):**
   - *Luận điểm mới này có mâu thuẫn với nhận định trong trang wiki cũ nào không?*
   - *Số liệu/kết quả thực nghiệm mới có lật ngược tài liệu trước đó không?*
3. **Xử lý mâu thuẫn:** Nếu có sự khác biệt quan điểm:
   - Thêm section `## Mâu thuẫn & Tranh luận` vào trang wiki (ghi rõ quan điểm A của `[[Nguồn 1]]` vs quan điểm B của `[[Nguồn 2]]`).
   - Tự động ghi 1 dòng đối chứng vào `wiki/_open-questions.md`.

### Bước 4: Compilation & Contextual Retrieval (Biên dịch trang Wiki)
Biên dịch thành các ghi chú nguyên tử có ngữ cảnh tự thân (Contextual Retrieval), thêm frontmatter chuẩn:
```yaml
type: wiki
status: active
tags: [wiki, <chủ_đề>]
aliases: [<tên_khác>, <tiếng_anh>]
source: "[[Tên Source]]"
```
Đảm bảo mỗi trang có đủ:
- Tóm tắt 1 câu định nghĩa (TL;DR).
- Nội dung chi tiết có dẫn chứng `[[Nguồn]]`.
- Các liên kết hai chiều `[[wikilink]]` đến các trang cha / trang anh em.

### Bước 5: Indexing & Nhật ký bàn giao
1. Thêm dòng tóm tắt vào `wiki/index.md` và `wiki/_index.md`.
2. Cập nhật frontmatter source: `status: processed`, `processed_at: YYYY-MM-DD`, `wiki_links: [...]`.
3. Ghi nhật ký vào `wiki/log.md`: `## [YYYY-MM-DD] ingest | [[Tên Source]] -> [[Trang Wiki]]`.
4. Báo cáo ngắn gọn cho Sếp: danh sách các trang đã tạo/sửa, các điểm mâu thuẫn được phát hiện (nếu có) và trích dẫn kiểm chứng.
