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
1. **Kiểm tra trạng thái & Bất biến Raw:** Đọc thông tin nguồn. Tuân thủ nghiêm ngặt quy tắc `Raw/` là **Read-only** nếu `AI_RULES.md` của Vault quy định nguồn thô bất biến.
2. **Phân loại quy mô nguồn & Chọn luồng thực thi:**
   - **Nguồn nhỏ (`<= 15` tệp và `< 150 KB`, `< 2.000` dòng):** Đọc trực tiếp hoặc giao 1 subagent (`Model: "flash"`).
   - **Nguồn lớn (`> 15` tệp hoặc `>= 150 KB`):** Bắt buộc kích hoạt **Luồng Hybrid (Deterministic Script + `run_workflow`)** để chống quá tải ngữ cảnh, chống sót số liệu và chống lệch đường dẫn:
     1. Chạy tiền xử lý (0 token LLM) bằng `scripts/ingest_ops.py` trong thư mục skill `ingest-source`:
        ```bash
        python "<skill_dir>/scripts/ingest_ops.py" prepare --source "<Vault>/Raw/<ThuMuc>" --vault "<Vault>" --out "<Scratch>/ingest_manifest.json"
        ```
        *(Tự động khử trùng lặp SHA-256, quét secret, tách file stub, chia shard cân bằng `<= 15 tệp` và `<= 150 KB / shard`, và sinh sẵn script workflow từ `scripts/ingest_workflow.tmpl` tại trường `workflow_script` trong JSON output.)*
     2. Chạy `run_workflow` với `ScriptPath` là giá trị `workflow_script` từ bước 1 và `Args: {"manifest_path": "<Scratch>/ingest_manifest.json", "vault_path": "<Vault>", "topic_hint": "<Chủ đề>"}` để Map song song từng shard ra JSON cấu trúc và Reduce đối soát chéo với `wiki/_index.md`.

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

### Bước 5: Verification, Indexing & Nhật ký bàn giao
1. **Hậu kiểm cứng (Bắt buộc với nguồn lớn hoặc nhiều trang):** Chạy script kiểm chứng để đảm bảo 0% trích dẫn ma (`Missing Raw refs`), 0% liên kết gãy, đúng YAML frontmatter UTF-8 No-BOM và kiểm tra độ phủ:
   ```bash
   python "<skill_dir>/scripts/ingest_ops.py" verify --vault "<Vault>" --files "wiki/<prefix>-*.md" --manifest "<Scratch>/ingest_manifest.json"
   ```
2. Thêm dòng tóm tắt vào `wiki/_index.md` (và `wiki/index.md` nếu cần).
3. Ghi nhật ký vào `wiki/log.md`: `## [YYYY-MM-DD] ingest | <Tiêu đề> -> [[Trang Wiki]]`.
4. Nếu phát hiện khoảng trống dữ liệu hoặc mâu thuẫn, ghi vào `wiki/_open-questions.md`.
5. Báo cáo ngắn gọn cho Sếp: danh sách trang đã tạo/sửa, kết quả `verify` (`PASS/FAIL`, tỷ lệ phủ) và các điểm mâu thuẫn/khoảng trống (nếu có).
