---
name: query-wiki
description: "Tra cứu và tổng hợp tri thức trong Second Brain (F:\\Obsidian) có trích dẫn nguồn bằng mô hình Agentic RAG đa chặng."
group: Second Brain
---
# QUERY - Tra cứu tri thức đa chặng (Agentic RAG Engine) từ Obsidian Wiki (F:\Obsidian)

Khai thác tri thức trong Second Brain tại `F:\Obsidian` bằng mô hình **Agentic RAG đa chặng (Multi-Hop Graph Traversal)**: tự động phân rã câu hỏi, lần theo đồ thị liên kết, tự đánh giá độ phủ và tổng hợp câu trả lời có trích dẫn nguồn gốc xác thực.

## Vault Root & Cấu trúc mặc định
- **Vault Root**: `F:\Obsidian`
- **Bản đồ tri thức chính**: `F:\Obsidian\wiki\_index.md` & `F:\Obsidian\wiki\index.md`
- **Thư mục Wiki (Evergreen Notes)**: `F:\Obsidian\wiki\`
- **Nguồn thô (Raw Sources)**: `F:\Obsidian\sources\` (hoặc `F:\Obsidian\Raw\`)
- **Câu hỏi tồn đọng**: `F:\Obsidian\wiki\_open-questions.md`

## Khi nào dùng
Kích hoạt khi người dùng hỏi hoặc cần khai thác tri thức trong Second Brain:
- "Tổng hợp các framework về X trong wiki"
- "So sánh quan điểm A vs B trong kho tri thức"
- "Tra cứu các bài học kinh nghiệm về lỗi Y"
- "Wiki có gì về chủ đề Z và còn thiếu mảng nào?"

---

## Cơ Chế Phân Quyền & Ủy Thác Subagent `research`
Theo nguyên tắc **Context Budget Economics**:
- **Tra cứu nhanh (Targeted Lookup - 1-2 trang, < 500 dòng):** Quản đốc tự đọc trực tiếp bằng công cụ Obsidian MCP để phản hồi tức thì.
- **Tra cứu sâu & diện rộng (Broad Synthesis - $\ge 3$ trang hoặc tài liệu thô $> 1.000$ dòng):** BẮT BUỘC ủy thác sang Subagent chuyên trách `TypeName: "research"` với `Model: "flash"` theo quy chuẩn [AGENTIC_RESEARCH_PROTOCOL.md](./references/AGENTIC_RESEARCH_PROTOCOL.md). Subagent sẽ tự "bơi trong tài liệu" ở một context riêng và chỉ trả về digest < 100 từ kèm artifact dẫn chứng, giữ luồng chính luôn sạch và nhanh.

---

## Quy trình 5 bước Google Agentic RAG trên Obsidian Vault

### Bước 1: Query Decomposition (Phân rã truy vấn)
Không tìm kiếm từ khóa thô trực tiếp. Tác tử phân tích câu hỏi thành:
1. **Thực thể cốt lõi (Core Entities):** Danh từ, framework, tác giả, dự án.
2. **Quan hệ cần đối soát (Relationships):** So sánh, nguyên nhân - kết quả, tiến trình thời gian.
3. **Mục tiêu trích xuất (Target Output):** Khái niệm, bảng đối sánh, checklist hay bài học kinh nghiệm.

### Bước 2: Multi-Hop Traversal (Duyệt đồ thị liên kết đa chặng)
Sử dụng công cụ Obsidian MCP (`mcp_obsidian-vault_read_file`, `mcp_obsidian-vault_search_files`):
- **Hop 1 (Chỉ mục & Bản đồ):** Đọc `wiki/index.md` hoặc `wiki/_index.md` để định vị cụm chủ đề và trang thực thể trung tâm.
- **Hop 2 (Trang thực thể & Liên kết ngang):** Đọc trang mục tiêu; bóc tách các liên kết `[[wikilink]]` và backlinks có liên quan trực tiếp đến câu hỏi.
- **Hop 3 (Liên kết sâu & Đối chứng):** Đi tiếp sang tối đa 2-3 trang liên kết phụ trợ để thu thập góc nhìn đa chiều hoặc số liệu cụ thể.
> *Cầu dao an toàn:* `max_hops <= 3` để chống sa đà vòng lặp. Nếu cần đọc vượt quá 3 hops, chuyển ngay sang Subagent `research`.

### Bước 3: Self-Reflection & Evidence Grading (Tự phản biện độ phủ)
Tác tử tự rà soát:
- *Thông tin đã đủ để trả lời câu hỏi của Sếp chưa?*
- Nếu thông tin trong `wiki/` chưa đủ: Truy xuất ngược về nguồn thô tương ứng tại `sources/` (dựa trên frontmatter `source: "[[...]]"`).
- Nếu cả `sources/` cũng không có: Ghi nhận câu hỏi mở vào `_open-questions.md`, nêu rõ ranh giới kiến thức thay vì tự suy diễn (Strict Anti-Hallucination).

### Bước 4: Grounded Synthesis (Tổng hợp có dẫn chứng cứng)
- Mọi nhận định, số liệu hay framework phải đi kèm trích dẫn nguồn `[[Tên_Trang#Heading]]` hoặc `[[Nguồn_Thô]]`.
- Tách bạch rõ ràng: `(theo wiki)` vs `(phân tích suy luận của tác tử)` vs `(cần xác minh thêm)`.

### Bước 5: Compounding (Đề xuất bồi đắp tri thức)
- Nếu câu trả lời mang lại giá trị tái sử dụng cao (bảng tổng hợp mới, so sánh hệ thống):
  - Đề xuất tạo một trang wiki mới trong `F:\Obsidian\wiki\`.
  - Cập nhật liên kết vào `wiki/index.md` và ghi nhận nhật ký vào `wiki/log.md`.
