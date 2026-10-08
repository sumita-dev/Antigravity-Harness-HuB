# Human Test Sheet — Bảng Nghiệm Thu UAT Thực Tế

Tài liệu này được cung cấp cho Sếp để trực tiếp trải nghiệm và nghiệm thu ứng dụng (User Acceptance Testing - UAT) sau khi các giai đoạn Unit Test, Integration Test và E2E Test tự động đã hoàn thành.

---

## 1. Thông Tin Triển Khai & Trạng Thái Hệ Thống

- **Ứng dụng / Tính năng:** <!-- Tên ứng dụng hoặc module vừa hoàn thành -->
- **URL Local đang chạy:** `http://localhost:3000` <!-- Hoặc port thực tế của dev server -->
- **Commit / Spec SHA256:** `<!-- SHA256 tương ứng từ checkpoint -->`
- **Trạng thái E2E Test tự động (Playwright):** [x] 100% Pass <!-- Hoặc ghi chú số test pass/skip -->
  - Báo cáo Playwright Report: `<!-- đường dẫn tương đối tới playwright-report/index.html nếu có -->`
  - Trace / Video bằng chứng: `<!-- đường dẫn tới thư mục test-results -->`

---

## 2. Checklist Hành Trình Người Dùng (User Journey Checklist)

Sếp hãy mở trình duyệt (ưu tiên kiểm tra cả trên Desktop lẫn Mobile View / Inspect mode) và lần lượt kiểm tra các bước dưới đây:

| STT | Luồng kiểm tra (Hành trình người dùng) | Các bước thực hiện cụ thể | Kết quả mong đợi | Đánh giá | Ghi chú / Nhận xét |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **01** | Khởi động & Hiển thị trang chủ | Mở URL local trên trình duyệt Desktop (1280x720) | Trang tải nhanh (<1.5s), bố cục hiển thị đầy đủ, không vỡ layout, console không có lỗi đỏ. | [ ] Pass<br>[ ] Fail | |
| **02** | Luồng thao tác chính (Happy Path) | 1. Nhập liệu đầy đủ vào form<br>2. Nhấn nút hành động chính (Submit/Thực hiện) | Dữ liệu được lưu thành công, thông báo hiển thị rõ ràng, danh sách được cập nhật tức thì. | [ ] Pass<br>[ ] Fail | |
| **03** | Xác thực & Xử lý lỗi (Validation) | 1. Để trống các trường bắt buộc<br>2. Nhập ký tự không hợp lệ hoặc vượt độ dài | Hiển thị thông báo lỗi thân thiện ngay tại trường nhập liệu; hệ thống không bị crash hoặc đơ giao diện. | [ ] Pass<br>[ ] Fail | |
| **04** | Trải nghiệm trên Mobile (Responsive) | Thu nhỏ cửa sổ về kích thước Mobile (390x844) hoặc bật Responsive Mode (F12) | Menu điều hướng chuyển sang dạng gọn gàng, text/nút bấm dễ chạm bằng ngón tay, không xuất hiện thanh cuộn ngang (horizontal scroll). | [ ] Pass<br>[ ] Fail | |
| **05** | Lưu trữ & Duy trì trạng thái | Tải lại trang (F5 / Refresh) sau khi thêm/sửa dữ liệu | Dữ liệu và trạng thái phiên làm việc vẫn được giữ nguyên vẹn đúng như trước khi reload. | [ ] Pass<br>[ ] Fail | |

---

## 3. Hướng Dẫn Báo Cáo Bug (Nếu Phát Sinh Lỗi)

Nếu trong quá trình kiểm tra, Sếp phát hiện bất kỳ hành vi bất thường nào, xin vui lòng phản hồi lại cho em kèm theo các thông tin sau để đội ngũ Maker sửa chữa ngay lập tức:

1. **Bước gây lỗi (Steps to reproduce):** Mô tả ngắn gọn các bước Sếp đã bấm trước khi lỗi xuất hiện.
2. **Hiện tượng thực tế:** Giao diện bị đơ, hiển thị sai nội dung, hoặc không bấm được nút,...
3. **Ảnh chụp / Screenshot:** (Nếu có)
4. **Console Log:** Bấm phím `F12` trên trình duyệt → chuyển sang tab `Console` → sao chép các dòng chữ đỏ (nếu có).
5. **Runtime Crash Log:** Kiểm tra file `runtime-crash.log` trong thư mục dự án để lấy dấu vết lỗi backend.

---

## 4. Phán Quyết Nghiệm Thu Của Sếp

- [ ] **CHẤP THUẬN NGHIỆM THU (APPROVED):** Ứng dụng đáp ứng đầy đủ yêu cầu, chuyển sang giai đoạn bàn giao / đóng task.
- [ ] **YÊU CẦU ĐIỀU CHỈNH (REVISION NEEDED):** Cần xử lý các lỗi hoặc điều chỉnh chi tiết theo mục Ghi chú ở trên.
