# QUY CHUẨN ĐIỀU PHỐI TÁC TỬ CON TRA CỨU TRI THỨC (AGENTIC RAG RESEARCH PROTOCOL)

Tài liệu này quy chuẩn hóa cách thức Quản đốc Hệ thống (Chief Orchestrator) ủy quyền các tác vụ tra cứu phức tạp, diện rộng trong Second Brain hoặc Codebase cho Subagent `research` theo mô hình **Google Agentic RAG**.

---

## 1. Mối Quan Hệ Giữa `query-wiki` Và Subagent `research`

- **`query-wiki` (Kỹ năng / Skill):** Bộ não phương pháp luận (Mental Model & Invariants). Quy định logic 5 bước của Agentic RAG (Decomposition $\rightarrow$ Multi-hop $\rightarrow$ Evidence Grading $\rightarrow$ Grounded Synthesis $\rightarrow$ Compounding).
- **Subagent `research` (Công nhân thực thi / Worker):** Không gian ngữ cảnh cô lập (Fresh Context) sở hữu các công cụ chỉ đọc (read-only tools). Đảm bảo việc "bơi trong hàng trăm file" diễn ra bên ngoài, không làm ô nhiễm và phình to Context Window của luồng hội thoại chính.

---

## 2. Tiêu Chí Kích Hoạt Subagent `research`

Quản đốc **tự tra cứu trực tiếp** nếu:
- Chỉ cần đọc 1–2 trang wiki cụ thể hoặc tra nhanh 1 khái niệm.
- Cần phản hồi tức thì và khối lượng tài liệu ngắn (< 500 dòng).

Quản đốc **BẮT BUỘC ủy thác sang Subagent `research`** nếu:
- Yêu cầu tổng hợp đa chiều, so sánh nhiều trường phái / framework trong Vault.
- Tra cứu liên trang xuyên suốt nhiều thư mục (`wiki/`, `sources/`, `memory/facts/`).
- Dự kiến số file cần đọc $\ge 3$ file hoặc tài liệu thô $> 1.000$ dòng.

---

## 3. Mẫu Đóng Gói Lệnh Giao Việc (Prompt Dispatch Template)

Khi gọi `invoke_subagent`, Quản đốc bắt buộc truyền Prompt theo đúng cấu trúc 4 phần của Google Agentic RAG:

```markdown
Role: "Second Brain Knowledge Researcher"
TypeName: "research"
Model: "flash"

Prompt:
## 1. Mục Tiêu & Phân Rã Truy Vấn (Decomposed Queries)
- Câu hỏi chính: [Yêu cầu của Sếp]
- Sub-query 1: Định vị các thực thể cốt lõi trong `F:\Obsidian\wiki\_index.md` hoặc `wiki/index.md`.
- Sub-query 2: Lần theo các [[wikilink]] và backlinks liên quan trực tiếp đến [Chủ đề].
- Sub-query 3: Kiểm tra nguồn thô trong `F:\Obsidian\sources\` nếu trang wiki chưa đủ thông tin.

## 2. Ranh Giới Khảo Sát & Cầu Dao (Boundaries & Hop Budget)
- Công cụ sử dụng: `mcp_obsidian-vault_*` (read_file, search_files).
- Ngân sách chặng: Tối đa 3 hops (`max_hops <= 3`). Tuyệt đối không đọc lan man ngoài chủ đề.
- Chế độ: Chỉ đọc (Read-Only), cấm ghi/sửa file.

## 3. Kiểm Chứng & Chống Ảo Giác (Grounding Checklist)
- Mọi kết luận phải gắn với đường dẫn file cụ thể hoặc liên kết `[[Tên_Trang#Heading]]`.
- Nếu phát hiện mâu thuẫn giữa 2 tài liệu -> ghi rõ cả 2 quan điểm, không tự ý chọn 1 bên.
- Nếu không tìm thấy thông tin -> ghi rõ "Chưa có dữ liệu trong vault", cấm tự suy diễn.

## 4. Biên Bản Giao Nhận Tinh Gọn (Lean Handoff Payload)
- Trả về tin nhắn kết quả cô đọng < 100 từ tóm tắt câu trả lời cốt lõi.
- Ghi toàn bộ báo cáo chi tiết có trích dẫn đầy đủ ra file artifact tại:
  `<appDataDir>\brain\<conversation-id>/scratch/wiki_research_<topic>.md`
```

---

## 4. Quy Trình Tiếp Nhận & Nghiệm Thu Handoff Từ Subagent

1. **Reactive Wakeup:** Quản đốc dừng turn, không gọi polling loop, chờ hệ thống tự đánh thức khi subagent hoàn tất.
2. **Đối soát biên bản:** Quản đốc kiểm tra tin nhắn digest và đọc lướt artifact tại `scratch/`.
3. **Phản hồi cho Sếp:** Tổng hợp báo cáo tinh gọn, dẫn link file artifact và trích dẫn `[[wikilink]]` nguồn.
4. **Compounding:** Nếu kết quả nghiên cứu có giá trị lũy tiến cao, Quản đốc đề xuất với Sếp tạo trang wiki chính thức mới trong `F:\Obsidian\wiki\`.
