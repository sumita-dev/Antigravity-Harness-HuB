---
name: karpathy-second-brain
description: "Xây dựng và vận hành Bộ não thứ 2 (Second Brain bằng Obsidian) theo đúng kiến trúc LLM Wiki của Andrej Karpathy."
group: Second Brain
---

# KỸ NĂNG VẬN HÀNH BỘ NÃO THỨ HAI (KARPATHY SECOND BRAIN & LLM WIKI)

Tài liệu này chuẩn hóa toàn bộ phương pháp luận và quy trình thực chiến để xây dựng, vận hành và bảo trì một **Bộ não thứ hai (Second Brain)** trên nền tảng **Obsidian** kết hợp với **AI Coding Agent** theo đúng kiến trúc **LLM Wiki** do **Andrej Karpathy** công bố (Tháng 04/2026).

---

## I. TỔNG QUAN TRIẾT LÝ & 4 TRỤ CỘT BẤT BIẾN

### 1. Ẩn Dụ Cốt Lõi: IDE — Programmer — Codebase
> *"Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."* — Andrej Karpathy

- **Obsidian = IDE (Integrated Development Environment):** Môi trường hiển thị trực quan, duyệt mã nguồn tri thức bằng Graph View, Canvas, Bases, Hotkeys và Backlinks.
- **LLM Agent = Programmer:** Kỹ sư lập trình tri thức chịu trách nhiệm đọc tài liệu, biên dịch nội dung, sửa lỗi, tạo liên kết chéo và tái cấu trúc (refactor) các ghi chú.
- **Wiki = Codebase:** Kho tệp Markdown văn bản thuần (plain-text `.md`) đại diện cho cơ sở tri thức đã biên dịch và liên tục tích lũy lũy tiến (compounding artifact).

### 2. Bốn Trụ Cột Bất Biến Của Kiến Trúc Karpathy

1. **Write-Time Compilation (Biên dịch trước thay vì chắp vá khi hỏi):**
   - **Vector RAG truyền thống:** Cắt vụn tài liệu thành chunk, chỉ tìm kiếm rời rạc khi người dùng đặt câu hỏi (*Query-time retrieval*). Tri thức không bao giờ được đắp bồi.
   - **LLM Wiki:** Đọc tài liệu thô một lần, trích xuất thực thể, đối chiếu mâu thuẫn và **biên dịch sẵn** vào hệ thống trang wiki liên kết (*Write-time compilation*).
2. **Compounding Artifact (Tạo phẩm tích lũy lũy tiến):**
   - Mỗi nguồn tài liệu mới được đưa vào làm giàu thêm mạng lưới wiki.
   - Mỗi câu trả lời truy vấn có giá trị sâu sắc được lưu ngược trở lại thành trang wiki mới. Cơ sở tri thức ngày càng thông minh theo thời gian ($O(N)$ tăng trưởng giá trị).
3. **Liberation from Bookkeeping (Giải phóng gánh nặng sổ sách):**
   - Con người từ bỏ Zettelkasten hay PARA vì chi phí bảo trì liên kết chéo, dọn broken link và cập nhật index tăng nhanh hơn giá trị nhận được.
   - LLM đưa chi phí bảo trì sổ sách (bookkeeping burden) về **tiệm cận số 0** vì AI có thể sửa 15-20 file cùng lúc một cách chính xác mà không bao giờ chán nản.
4. **Kiến Trúc LLM OS (Hệ điều hành LLM):**
   - **Kernel/CPU:** AI Agent (Claude Code, Gemini, Cursor).
   - **RAM (Working Memory):** Cửa sổ ngữ cảnh (Context Window) nạp các trang wiki liên quan.
   - **Disk (Long-term Storage):** Hệ thống tệp Markdown cục bộ trên ổ đĩa.
   - **System Schema (`CLAUDE.md`):** Tệp quy chuẩn cấu hình hệ điều hành tri thức.

---

## II. CẤU TRÚC THƯ MỤC CHUẨN CỦA VAULT (LOCAL-FIRST)

Một Vault tuân thủ chuẩn Karpathy LLM Wiki phải tổ chức phân tầng nghiêm ngặt:

```
[Vault Root] (Ví dụ: $env:OBSIDIAN_VAULT_PATH hoặc ~/Obsidian)
├── CLAUDE.md                 # SCHEMA & ĐIỀU LỆ TỐI CAO (Invariants, rules, guardrails)
├── Raw/                      # TẦNG 1: TÀI LIỆU GỐC (BẤT BIẾN - READ ONLY)
│   ├── books/                # Sách điện tử, file PDF, epub
│   ├── web/                  # Ghi chú clip từ web qua Web Clipper / Defuddle
│   ├── transcripts/          # Bản ghi âm YouTube, Podcast, Meeting
│   └── assets/               # Hình ảnh, tài liệu đính kèm nguyên bản
├── wiki/                     # TẦNG 2: BÁCH KHOA TOÀN THƯ (BIẾN ĐỔI - COMPOUNDING)
│   ├── _index.md             # Bản đồ tri thức toàn diện & điều hướng chính
│   ├── index.md              # Catalog phụ trợ & điều hướng nhanh
│   ├── log.md                # Nhật ký cập nhật hệ thống (Append-only)
│   ├── _inbox.md             # Hòm thư tiếp nhận ghi chú thô chờ tiêu hóa
│   ├── _open-questions.md    # Danh mục câu hỏi mở & điểm mâu thuẫn cần đối chứng
│   └── [cac-trang-wiki].md   # Từng trang khái niệm, thực thể, quy trình (1 trang = 1 chủ đề)
├── templates/                # MẪU TRANG CHUẨN HÓA (Templates)
│   ├── wiki-page.md          # Template trang tri thức tiêu chuẩn
│   └── concept-page.md       # Template trang khái niệm / mô hình
└── ops/                      # CÔNG CỤ TỰ ĐỘNG HÓA & SCRIPTS
    └── wiki_ops.py           # Script bảo trì, thống kê, linting tự động
```

### Quy định quyền truy cập thư mục:
- `Raw/`: **Đóng băng tuyệt đối**. AI Agent và người dùng KHÔNG ĐƯỢC CHỈNH SỬA tệp gốc sau khi đã lưu, đảm bảo luôn có nguồn chân lý để đối soát.
- `wiki/`: Khu vực hoạt động chính của AI Agent. Mọi chỉnh sửa, cập nhật, tạo mới diễn ra tại đây.
- `CLAUDE.md`: Quy định cao nhất, ghi đè mọi cấu hình plugin khi có xung đột.

---

## III. 3 CHU TRÌNH VẬN HÀNH THỰC CHIẾN KÈM PROMPT MẪU

### 1. Chu trình Ingest (Tiêu Hóa Nguồn Thô Vào Wiki)

#### Mục tiêu:
Khi có tài liệu mới trong `Raw/`, AI đọc hiểu, trích xuất cấu trúc và cập nhật đồng loạt vào hệ sinh thái `wiki/`.

#### Các bước thực hiện của Agent:
1. Đọc tệp trong `Raw/` (nếu tệp dài trên 10.000 dòng, dùng chiến thuật 3-pass đọc từng phần).
2. Tra cứu `_index.md` và các trang wiki hiện có để tìm điểm giao thoa.
3. Tạo trang wiki mới hoặc cập nhật 5–15 trang liên quan (thêm liên kết hai chiều `[[...]]`).
4. Ghi rõ trích dẫn nguồn ở cuối trang: `[[Raw/tên-file.md]]`.
5. Cập nhật `_index.md` và ghi log vào `wiki/log.md`.

#### Prompt mẫu Ingest cho Người dùng:
```text
Tôi vừa thêm tài liệu mới vào thư mục Raw: [[Raw/ten-tai-lieu.md]].
Hãy thực hiện chu trình INGEST theo chuẩn Karpathy LLM Wiki:
1. Đọc kỹ tài liệu và chưng cất các luận điểm cốt lõi, mô hình hoặc quy trình thực chiến.
2. Kiểm tra _index.md để xác định những trang wiki nào cần tạo mới hoặc cập nhật.
3. Tạo trang mới theo đúng cấu trúc 6 mục chuẩn (YAML Frontmatter UTF-8, Tóm tắt, Nội dung chính, Liên kết, Nguồn [[Raw/...]], Cập nhật).
4. Cập nhật các liên kết chéo [[...]] vào các trang khái niệm liên quan.
5. Cập nhật _index.md và ghi nhận nhật ký vào log.md.
Lưu ý: Tuyệt đối không chỉnh sửa tệp trong thư mục Raw/.
```

---

### 2. Chu trình Query Tích Lũy (Compounding Query)

#### Mục tiêu:
Truy vấn tri thức đa nguồn, tạo ra câu trả lời chiều sâu và **lưu ngược câu trả lời trở lại wiki** để tri thức tiếp tục đắp bồi.

#### Các bước thực hiện của Agent:
1. Đọc `_index.md` để xác định các trang wiki liên quan đến câu hỏi.
2. Nạp nội dung các trang wiki vào Context Window.
3. Tổng hợp câu trả lời sâu sắc, phân tích so sánh, có viện dẫn citation rõ ràng.
4. Đề xuất hoặc tự động lưu bản tổng hợp thành một trang Evergreen mới trong `wiki/` (ví dụ: `so-sanh-a-va-b.md`) hoặc bổ sung vào mục liên quan.

#### Prompt mẫu Query Tích lũy cho Người dùng:
```text
Dựa trên toàn bộ tri thức hiện có trong thư mục wiki/:
Hãy phân tích và đối chiếu: [Chủ đề câu hỏi phức tạp, ví dụ: "So sánh chiến lược định giá của Hormozi và tâm lý học về tiền của Morgan Housel"].
Yêu cầu:
1. Tổng hợp đa chiều kèm trích dẫn rõ ràng từ các trang wiki.
2. Nêu bật các điểm tương đồng, điểm mâu thuẫn và bài học hành động thực chiến.
3. ĐÚC KẾT BỒI ĐẮP: Tạo một trang tổng hợp mới trong wiki/ lưu trữ câu trả lời này, đồng thời liên kết ngược vào _index.md và log.md.
```

---

### 3. Chu trình Lint Health Check (Rà Soát Sức Khỏe Wiki)

#### Mục tiêu:
Dọn dẹp "nợ kỹ thuật tri thức" (Knowledge Debt), phát hiện lỗi liên kết, trang mồ côi và mâu thuẫn quan điểm.

#### Các bước thực hiện của Agent:
1. Quét toàn bộ thư mục `wiki/` để kiểm tra tính toàn vẹn:
   - **Broken Links:** Các liên kết `[[...]]` trỏ đến trang không tồn tại.
   - **Orphan Pages:** Các trang không có bất kỳ trang nào khác trỏ tới và không có mặt trên `_index.md`.
   - **Missing Frontmatter:** Các trang thiếu YAML metadata hoặc sai chuẩn UTF-8.
   - **Missing Citations:** Các trang khẳng định số liệu/quy trình nhưng không có mục `## Nguồn` trỏ về `Raw/`.
   - **Knowledge Contradictions:** Phát hiện các điểm dữ liệu mâu thuẫn giữa các tài liệu.
2. Lập báo cáo Health Check chi tiết và tự động sửa các lỗi liên kết nếu được cho phép.

#### Prompt mẫu Lint cho Người dùng:
```text
Hãy thực hiện chu trình LINT HEALTH CHECK toàn diện cho Vault Obsidian theo chuẩn Karpathy:
1. Quét tìm toàn bộ Broken Links và Orphan Pages trong thư mục wiki/.
2. Kiểm tra tính hợp lệ của YAML Frontmatter (UTF-8, linh_vuc, do_uu_tien, trang_thai, ngay_cap_nhat).
3. Rà soát xem có trang nào khẳng định dữ kiện mà thiếu liên kết nguồn [[Raw/...]] không.
4. Phát hiện các điểm mâu thuẫn tri thức giữa tài liệu cũ và tài liệu mới.
5. Xuất báo cáo kết quả và đề xuất danh sách các liên kết cần khắc phục ngay.
```

---

## IV. CẤU HÌNH OBSIDIAN TỐI ƯU CHO SECOND BRAIN

Để biến Obsidian thành một **IDE hoàn hảo** cho LLM Wiki, áp dụng các thiết lập sau:

### 1. Graph View (Đồ Thị Tri Thức)
- **Filters:** Loại bỏ thư mục `Raw/` và `templates/` khỏi Global Graph để chỉ tập trung quan sát mạng lưới tri thức tinh gọn trong `wiki/`.
- **Color Groups (Nhóm màu theo Lĩnh vực Frontmatter):**
  - `linh_vuc: ops` $\rightarrow$ Màu Đỏ / Cam.
  - `linh_vuc: content` $\rightarrow$ Màu Xanh dương.
  - `linh_vuc: business` $\rightarrow$ Màu Xanh lá.
  - `linh_vuc: psychology` $\rightarrow$ Màu Tím.
- **Local Graph:** Mở Local Graph ở thanh bên phải (Right Sidebar) với `Depth = 2` để quan sát ngay lập tức các liên kết lân cận của trang đang mở.

### 2. Thu Thập Dữ Liệu: Web Clipper & Defuddle
- Cài đặt tiện ích **Obsidian Web Clipper** trên Chrome/Brave hoặc dùng CLI `defuddle`.
- **Quy tắc vàng:** Mọi nội dung clip từ web **bắt buộc lưu vào `Raw/web/`**, tuyệt đối không ghi thẳng vào `wiki/`. Sau đó kích hoạt chu trình Ingest để AI xử lý.

### 3. Obsidian Bases & Canvas
- **Obsidian Bases (`.base`):** Dùng để tạo các bảng quản trị động (Dynamic Views) lọc theo các trường Frontmatter (`linh_vuc`, `do_uu_tien`, `trang_thai`, `ngay_cap_nhat`).
- **JSON Canvas (`.canvas`):** Dùng để vẽ sơ đồ tư duy, visual pipeline kết nối các file wiki dạng thẻ bài trực quan. Canvas là công cụ trình chiếu tư duy, không thay thế mã nguồn Markdown trong `wiki/`.

### 4. Hotkeys Thiết Yếu Khuyên Dùng
- `Ctrl + O`: Mở Quick Switcher (tìm kiếm file siêu tốc).
- `Ctrl + Shift + F`: Tìm kiếm toàn văn bản trong Vault.
- `Ctrl + G`: Mở Graph View toàn cục.
- `Alt + D`: Mở Local Graph của trang hiện tại.

---

## V. CÁC LƯU Ý BẢO MẬT & BẪY CẦN TRÁNH (GUARDRAILS)

1. **Bẫy "RAG Rời Rạc" (Chat-and-Forget):**
   - Đừng chat với AI rồi đóng tab. Mọi tri thức sinh ra từ câu hỏi hay phải được chưng cất thành file Markdown cố định trong `wiki/`.
2. **Bẫy "Sửa Nguồn Thô" (Modifying Raw):**
   - Thư mục `Raw/` là bằng chứng lịch sử. Nếu AI tự ý sửa tệp thô, hệ thống mất đi khả năng kiểm chứng ngược (fact-checking).
3. **Bẫy "AI Slop" (Rác ngôn từ sáo rỗng):**
   - AI thường có xu hướng viết dài dòng, dùng từ đệm vô nghĩa. Quy tắc kiểm soát: Mỗi câu trong wiki phải chứa thông tin thực chứng, số liệu hoặc luận điểm rõ ràng.
4. **Giới Hạn Context Window & Quy Mô Index:**
   - Khi Vault vượt quá 200–300 tài liệu, tệp `_index.md` có thể quá dài. Hãy phân chia theo các Sub-Index chuyên đề (MOC - Map of Content) hoặc sử dụng công cụ tìm kiếm cục bộ lai (Hybrid search như `qmd` / `ripgrep`) trước khi nạp vào AI.
5. **Kỷ Luật Mã Hóa UTF-8 Trên Windows:**
   - Luôn kiểm tra file được lưu ở định dạng UTF-8 không BOM để bảo toàn 100% tiếng Việt có dấu.
