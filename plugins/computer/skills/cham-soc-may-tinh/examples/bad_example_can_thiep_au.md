# Danh Mục Lỗi Cần Tránh: Các Sai Lầm Kỹ Thuật Khi Tối Ưu Hóa Hệ Thống (Anti-Patterns)

Tài liệu này liệt kê các hành vi can thiệp ẩu, vi phạm nguyên tắc bảo toàn dữ liệu và các anti-patterns mà AI Agent tuyệt đối không bao giờ được mắc phải.

---

## 1. CÁC HÀNH VI VI PHẠM NGUYÊN TẮC AN TOÀN

### ❌ Lỗi 1: Xóa tệp mù quáng không tạo điểm khôi phục (Blind Destruction)
- **Hành vi sai:** Tự ý chạy lệnh xóa sạch không kiểm tra hoặc không tạo System Restore Point trước khi can thiệp.
- **Hậu quả:** Nếu tệp bị xóa là thư viện của phần mềm chuyên dụng (ví dụ tệp tạm dự án Premiere/CapCut chưa lưu), người dùng sẽ mất dữ liệu vĩnh viễn và không có cách nào hoàn tác.
- **Quy chuẩn sửa:** Luôn chạy `task_00_restorepoint.ps1` tạo mốc VSS Snapshot trước bất kỳ thao tác xóa nào.

### ❌ Lỗi 2: Xâm phạm Vùng Đỏ nhân hệ điều hành
- **Hành vi sai:** Quét và cố tình xóa tệp trong `C:\Windows\System32` hoặc dọn Registry trong `HKLM:\SYSTEM\CurrentControlSet` vì nghĩ là tệp thừa.
- **Hậu quả:** Gây lỗi màn hình xanh (BSOD), phá hỏng chuỗi khởi động Windows và vô hiệu hóa các driver phần cứng.
- **Quy chuẩn sửa:** Tuyệt đối tuân thủ ranh giới trong `ref_01_vung_an_toan_va_xung_dot.md`. Vùng Đỏ là bất biến, không được chạm vào.

### ❌ Lỗi 3: Báo cáo mơ hồ, thiếu số liệu kỹ thuật đo đạc
- **Hành vi sai:** Báo cáo với người dùng kiểu chung chung: *"Hệ thống máy tính của bạn đã được tối ưu xong rồi nhé."* mà không có bất kỳ số liệu đo đạc nào.
- **Hậu quả:** Người dùng không biết máy mình đang gặp vấn đề gì cụ thể, không nắm được dung lượng đã giải phóng là bao nhiêu MB, thiếu độ tin cậy chuyên nghiệp.
- **Quy chuẩn sửa:** Dùng ngôn ngữ kỹ thuật đời thường, rõ ràng: thông báo chính xác số GB RAM trống, số MB tệp tạm đã dọn, tình trạng ổ đĩa SSD trước và sau khi xử lý.

### ❌ Lỗi 4: Mở cổng mạng tùy tiện (Rò rỉ tiến trình nền)
- **Hành vi sai:** Tự ý bật máy chủ HTTP nền (như `hud_server.py` cổng 8899) để hiển thị giao diện, nhưng quên tắt tiến trình, chiếm dụng cổng mạng và tạo lỗ hổng bảo mật.
- **Quy chuẩn sửa:** Vận hành theo cơ chế Dual-Stream phi máy chủ: Dùng Terminal tích hợp và file Live Markdown, tuyệt đối không mở cổng HTTP nội bộ.
