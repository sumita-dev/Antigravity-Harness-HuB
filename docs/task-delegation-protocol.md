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
