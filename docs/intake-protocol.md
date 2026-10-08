# Intake Protocol — Quy Chuẩn Phỏng Vấn Làm Rõ Yêu Cầu (Pha 0)

Quy chuẩn này là cổng bắt buộc (**Intent Alignment Gate**) trong quy trình phát triển ứng dụng (App Workflow). Quản đốc Hệ thống (Chief Orchestrator) **CẤM TUYỆT ĐỐI** tự ý kích hoạt Architect hoặc gọi công cụ sửa mã khi chưa làm rõ và chốt 3 tham số nền tảng với Sếp.

---

## 1. Triết Lý & Nguyên Tắc Cốt Lõi

1. **Chống Tự Tiện Phỏng Đoán (No Hallucinated Assumptions):** Khi nhận ý tưởng hoặc yêu cầu chung chung từ Sếp (ví dụ: *"Làm cho anh cái app quản lý chi tiêu"*), Quản đốc không được tự chọn bừa stack hay tự bịa scope.
2. **Consult Before Mutate:** Chỉ tư vấn, hỏi ngắn gọn và đề xuất giải pháp khả thi. Không chạm vào file hay terminal trước khi Sếp xác nhận.
3. **Chuẩn Bị Sẵn Dữ Liệu Mẫu (Seed Data Invariant):** Mọi ứng dụng tạo ra phải có sẵn dữ liệu mẫu thực tế, phong phú (AC-SEED) để demo được ngay sau khi chạy 1-click launcher, cấm bàn giao app trắng trơn.

---

## 2. Ba Tham Số Bắt Buộc Cần Thu Thập (3 Core Parameters)

Mọi phiên phỏng vấn Intake bắt buộc phải chốt được 3 tham số sau:

| Tham số | Ý nghĩa & Lựa chọn | Khuyến nghị mặc định (Default Recommendation) |
| :--- | :--- | :--- |
| **1. Tech Stack** | Công nghệ xây dựng giao diện / xử lý:<br>- Web: React + Vite, Next.js, HTML/Tailwind/JS thuần.<br>- Desktop / CLI: Python, Node.js CLI. | - Web SPA nhẹ: **React + Vite** (hoặc HTML/Tailwind nếu siêu nhẹ).<br>- CLI / Automation: **Python 3.12**. |
| **2. Nơi Lưu Trữ Dữ Liệu** | Cơ chế lưu trữ dữ liệu ứng dụng:<br>- Trình duyệt: LocalStorage, IndexedDB.<br>- File cục bộ: SQLite file, JSON file. | - Web Local: **LocalStorage** (kèm seed data).<br>- Backend/Desktop: **SQLite file** hoặc **JSON file**. |
| **3. Phạm Vi MVP (Core Scope)** | Giới hạn tính năng cho bản thử nghiệm đầu tiên:<br>- Danh sách **Top 3 - 5 User Stories cốt lõi nhất**.<br>- Ranh giới rõ ràng: Cái gì LÀM và cái gì CHƯA LÀM (Out of scope). | Tập trung vào 1 luồng chính (Happy Path) hoàn chỉnh thay vì nhiều tính năng dở dang. |

---

## 3. Hướng Dẫn Quản Đốc Phỏng Vấn Sếp

Quản đốc sử dụng công cụ `ask_question` hoặc định dạng câu hỏi súc tích trong khung chat theo mẫu sau:

```markdown
Chào Sếp, để triển khai ứng dụng chính xác và tối ưu nhất, em xin xác nhận 3 thông số kỹ thuật cốt lõi:

1. **Tech Stack mong muốn:** (Khuyến nghị: React + Vite cho Web mượt mà, hoặc Python nếu là tool xử lý dữ liệu)
2. **Nơi lưu trữ dữ liệu:** (Khuyến nghị: LocalStorage cho Web chạy ngay không cần cài DB, hoặc SQLite file)
3. **3 - 5 tính năng cốt lõi (User Stories) của bản MVP:** (Các tính năng nâng cao sẽ dành cho giai đoạn sau)

Sếp duyệt phương án khuyến nghị trên hay có điều chỉnh gì không ạ?
```

---

## 4. Tiêu Chí Chuyển Giao Sang Pha 1 (Hand-off Gate sang Architect)

Quản đốc chỉ được chuyển sang **Pha 1 (DESIGN - Architect)** khi:
1. Sếp đã phản hồi xác nhận rõ ràng 3 tham số trên (hoặc đồng ý với phương án khuyến nghị).
2. Brief bàn giao cho Architect chứa đủ:
   - Tech stack đã chọn.
   - Cơ chế lưu trữ dữ liệu.
   - Top 3 - 5 User Stories rõ ràng.
   - Yêu cầu bắt buộc về tiêu chí **AC-SEED** (file dữ liệu mẫu thực tế).
