# Hướng Dẫn Giao Việc Chuẩn Khung Giới Hạn (3-Stage Task Protocol)

> **Mục đích:** Triệt tiêu hoàn toàn hiện tượng AI tự ý thu nhỏ scope (Scope Reduction) hoặc tạo mockup sơ sài rồi tuyên bố hoàn thành sớm (Reward Hacking).

---

## 1. Bản Chất Rủi Ro Khi Giao Việc Quá Mở

❌ **Cách giao việc dễ khiến AI trượt dốc:**
> *"Em rebuild lại extension/hệ thống này từ đầu với đầy đủ 100% chức năng nhé."*

- **Hậu quả:** Prompt quá rộng vượt quá dung lượng working memory. AI không thể giữ hàng chục file cùng lúc, dẫn đến việc tự động tạo một prototype nhỏ 4-5 file rồi vội vã báo cáo "xong 100%".

---

## 2. Mô Hình Giao Việc 3 Chặng Tối Ưu (The 3-Stage Protocol)

### Chặng 1: Rà Soát & Lập Danh Mục Đối Soát 1:1 (Audit & Inventory Matrix)
Khi bắt đầu dự án lớn (>20 files, clone, rebuild, reverse):
> *"CẤM viết code ngay lập tức. Hãy dùng subagent research rà soát toàn bộ thư mục gốc, lập bảng Feature Parity Inventory đối chiếu 1:1: từng trang UI có những nút nào, background có những event listener nào, manifest/config có permissions/scripts nào. Xuất ra file markdown để anh duyệt trước."*

- **Mục tiêu:** Khóa chặt phạm vi (Scope Freeze), không cho AI cơ hội cắt xén tính năng.

### Chặng 2: Khóa Chặt Từng Module (One Module per Prompt / Milestone Lock)
Sau khi đã chốt bảng kiểm kê ở Chặng 1:
> *"Bây giờ chúng ta chỉ làm duy nhất Module 1: [Tên Module, ví dụ: Quản lý Storage & Bắt Event Khởi Động]. Chưa cần làm UI hay các phân hệ khác. Hãy viết code và chứng minh bằng log runtime: (1) Storage đã lưu dữ liệu thật, (2) Background listener đã bắt được event và log ra màn hình."*

- **Mục tiêu:** Tập trung 100% Context Window vào một bài toán hẹp, giải quyết dứt điểm và kiểm chứng sâu.

### Chặng 3: Nghiệm Thu Thực Chứng 2 Tầng & Phản Biện Đối Kháng (2-Tier DoD & Adversarial Review)
Trước khi chuyển sang module kế tiếp:
> *"Hãy đóng vai một QA Auditor/Critic khó tính nhất:
> 1. Trích xuất bằng chứng 2 Tầng: Tầng 1 (Dữ liệu thật trong storage/db) và Tầng 2 (Event listener runtime log).
> 2. Tìm ra 3 điểm mà code của em đang khác biệt hoặc thiếu sót so với logic chạy ngầm của bản gốc."*

- **Mục tiêu:** Ép AI tự rà soát regression và chống ngụy tạo bằng chứng.

---

## 3. Rào Chắn Tự Động Trong Hệ Thống (Built-in Invariants)
- **Anti-Scope-Reduction Guard:** Quy định tại `GEMINI.md` (Mục 14).
- **2-Tier Definition of Done:** Bắt buộc Tầng State & Tầng Lifecycle (`verification-before-completion`).
- **Feature Parity Inventory:** Bắt buộc đối soát AST và sự kiện (`anti-hallucination-guard`).

---

## 4. Quy chuẩn Giao Việc Chống Thẩm Định Hình Thức (Anti-Cosmetic Triad & Adversarial Grounding)

> **Mục tiêu:** Cấm tuyệt đối hiện tượng "thẩm định hình thức" (Cosmetic Review), nơi các tác tử trong Triad (Architect, Builder, Critic, QA) chỉ đối chiếu lý thuyết, kiểm tra cú pháp AST tĩnh hoặc suy đoán về routing/network mà không có bằng chứng thực chứng từ thế giới thực.

### 4.1. Lệnh Cấm Thẩm Định Hình Thức (Cosmetic Triad Ban)
- **Cấm suy diễn ranh giới mạng:** Mọi kết luận về lỗi mạng, chuyển hướng URL (redirect), fallback trang chủ, rewrite, hoặc HTTP 404/500 CẤM TUYỆT ĐỐI dựa trên suy đoán logic hay chỉ đọc file mã nguồn.
- **Bắt buộc raw HTTP evidence:** Bắt kỳ tuyên bố nào về hành vi chuyển hướng hoặc lỗi trang đều bị rào chắn `enforce_anti_hallucination_hook.py` chặn lại nếu thiếu raw HTTP status code từ lệnh probe thực tế.

### 4.2. Bắt Buộc Bước Ra Thực Tế (Adversarial Reality Grounding Invariant)
- **QA Auditor độc lập kích hoạt CLI probe:** Trước khi ký duyệt (`APPROVE` / signoff) bất kỳ báo cáo kỹ thuật nào liên quan đến routing, hạ tầng mạng, web pages hoặc API endpoints, QA Auditor BẮT BUỘC phải độc lập chạy lệnh probe thực nghiệm từ CLI (`curl -I`, `Invoke-WebRequest`, `Invoke-RestMethod` hoặc HTTP client script) trực tiếp đến host/endpoint mục tiêu.
- **Tiêu chuẩn nghiệm thu:** Chỉ chấp nhận signoff khi output ghi nhận rõ ràng raw HTTP status code (ví dụ `HTTP 200`, `HTTP 301`, `HTTP 302`, `HTTP 404`, `HTTP 500`) và URL chuyển hướng thực tế từ CLI probe log với `exit code == 0`.

### 4.3. Tiêu Chuẩn Prompting QA Đối Kháng (Adversarial QA Prompting Standard)
Khi điều phối SubAgent QA Auditor thẩm định bản vá lỗi, an ninh hoặc điều tra lỗi hệ thống, Quản đốc (Orchestrator) **BẮT BUỘC** phải đưa yêu cầu đối kháng tường minh vào prompt:
> *"Em là QA Auditor đóng vai trò Adversarial Attacker khó tính nhất:
> 1. Với bản vá bảo mật/logic: CẤM chỉ đọc diff mã nguồn; BẮT BUỘC tái hiện lại PoC exploit cũ và thử nghiệm thêm 1-2 payload bypass để kiểm chứng độ bền thực tế của bản vá.
> 2. Với tuyên bố lỗi mạng/routing/redirect/HTTP: CẤM suy đoán AST tĩnh; BẮT BUỘC chạy trực tiếp CLI probe (`curl -I`, `Invoke-WebRequest`) lấy raw HTTP status code.
> 3. Báo cáo nghiệm thu BẮT BUỘC đính kèm terminal output thực tế hoặc khối `### [EVIDENCE TUPLE]` hợp lệ."*

### 4.4. Cấu Trúc Khối Bằng Chứng Tinh Gọn (Lean Evidence Tuple Format)
Nhằm giữ Context Window tinh gọn nhưng vẫn vượt qua rào chắn thực chứng tự động, SubAgent và QA Auditor có thể trình bày bằng chứng kiểm định mạng/routing theo khối chuẩn:

```markdown
### [EVIDENCE TUPLE]
- Target URL: <URL hoặc endpoint được kiểm chứng, ví dụ: https://example.com/login>
- Probe Command: <Lệnh CLI thăm dò thực tế: curl -I, Invoke-WebRequest, Invoke-RestMethod, requests, urllib, fetch>
- Raw Status Code: <Raw HTTP output hoặc status code: ví dụ HTTP 200 OK, HTTP 301 Moved Permanently, HTTP 404 Not Found, HTTP 500>
```

Hoặc dưới dạng bảng Markdown tinh gọn:

```markdown
### [EVIDENCE TUPLE]
| Target URL | Probe Command | Raw Status Code |
| :--- | :--- | :--- |
| https://example.com/checkout | `curl -I https://example.com/checkout` | HTTP 301 Moved Permanently |
```

---

## 5. Quy Chuẩn Handoff & Xuất Artifact Theo Quyền Ghi SubAgent
- **SubAgent có quyền ghi (`TypeName="self"`):** BẮT BUỘC ghi báo cáo chi tiết ra `report_path` (non-empty, trong `scratch/` hoặc thư mục artifact) và trả về `digest <= 100 từ` theo Structured Envelope (`Verdict | Exit Code | Key Findings | report_path`).
- **SubAgent Read-Only (`TypeName="research"` — L1 Read-Only Sandbox):** Không có công cụ `write_file`; trả kết quả trực tiếp qua `[Message]` (kèm `send_message`). Quản đốc tự lưu nội dung đó ra `scratch/` nếu cần truyền tiếp cho tác tử downstream (`Creator`, `Builder`, `Critic`).
- **Trường hợp cần Researcher tự xuất `report_path`:** Quản đốc chủ động gọi `TypeName="self"` kèm chỉ dẫn tường minh chỉ được phép ghi duy nhất vào thư mục `scratch/` để giữ kỷ luật L1 Read-Only đối với mã nguồn chính.
