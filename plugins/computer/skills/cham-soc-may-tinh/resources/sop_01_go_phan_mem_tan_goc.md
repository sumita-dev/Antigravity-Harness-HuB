# Hướng Dẫn: Quy Trình Gỡ Bỏ Phần Mềm Sạch Qua 6 Trạm (Deep Clean Uninstallation)

Tài liệu này đặc tả quy trình kỹ thuật 6 trạm nhằm gỡ bỏ tận gốc các ứng dụng cứng đầu, xóa sạch tàn dư trong AppData, ProgramData, Registry và giải phóng tài nguyên hệ thống bị chiếm dụng ngầm.

---

## 1. CHỐT CHẶN BẢO VỆ: QUÉT TÀN DƯ VÀ XÁC THỰC PHẠM VI

### Input:
- Tên phần mềm người dùng yêu cầu gỡ bỏ — Vị trí: Context hội thoại hoặc lệnh `gophanmem <tên>`.
- Danh mục ứng dụng cài đặt trong Registry — Vị trí: `HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall` và `HKCU:\Software\...`.

### Process:
- Bước 1: Quét tìm toàn bộ chuỗi đường dẫn tệp tin liên quan đến phần mềm trên các ổ đĩa bằng công cụ tìm kiếm nhanh Everything CLI (`es.exe`):
  ```powershell
  es.exe -r "\b<TenPhanMem>\b"
  ```
- Bước 2: Liệt kê các tiến trình nền, dịch vụ (Services), tác vụ lịch trình (Scheduled Tasks) và khóa Registry đang gắn với phần mềm.
- Bước 3: Trình bày danh mục tệp tàn dư dự kiến xóa cho người dùng xác nhận trước khi can thiệp.

### Output:
- **Nội dung:** Danh mục tệp tin, khóa cấu hình và tiến trình liên quan sẵn sàng xử lý.
- **Hình thức:** Bảng kê chi tiết trên màn hình.
- **Vị trí:** Context làm việc của Agent.

---

## 2. THI CÔNG GỠ BỎ TẬN GỐC QUA 6 TRẠM

### Input:
- Danh mục thành phần đã được xác thực từ Chốt chặn 1.

### Process:
- **Trạm 1: Dừng toàn bộ tiến trình liên quan trong bộ nhớ RAM:**
  Chấm dứt các tiến trình đang khóa tệp hoặc chạy ngầm để tránh lỗi tệp đang bận (`File in use`):
  ```powershell
  Get-Process -Name "*<TenPhanMem>*" | Stop-Process -Force
  ```
- **Trạm 2: Kích hoạt lệnh gỡ cài đặt chính thức (Official Uninstaller):**
  Tìm chuỗi `UninstallString` hoặc `QuietUninstallString` trong Registry và thực thi ở chế độ im lặng (`/S`, `/quiet`, hoặc `msiexec.exe /x {GUID} /qn`).
- **Trạm 3: Dọn sạch tệp và thư mục tàn dư mồ côi:**
  Xóa các thư mục còn sót lại không tự hủy sau khi gỡ:
  - `%LOCALAPPDATA%\<TenPhanMem>`
  - `%APPDATA%\<TenPhanMem>`
  - `%PROGRAMDATA%\<TenPhanMem>`
  - `C:\Program Files\<TenPhanMem>` và `C:\Program Files (x86)\<TenPhanMem>`
- **Trạm 4: Làm sạch các khóa Registry cấu hình:**
  Xóa các khóa mồ côi trong:
  - `HKCU:\Software\<TenPhanMem>`
  - `HKLM:\Software\<TenPhanMem>`
  - `HKLM:\Software\WOW6432Node\<TenPhanMem>`
- **Trạm 5: Dỡ bỏ dịch vụ chạy ngầm và tác vụ lịch trình:**
  Xóa dịch vụ tự cập nhật hoặc giám sát chạy nền:
  ```powershell
  sc.exe delete "<TenDichVu>"
  Unregister-ScheduledTask -TaskName "<TenTacVu>" -Confirm:$false
  ```
- **Trạm 6: Xóa luật tường lửa và mở khóa tệp kẹt:**
  - Xóa các quy tắc mạng mồ côi: `Remove-NetFirewallRule -DisplayName "*<TenPhanMem>*"`.
  - Nếu có tệp đơn lẻ bị khóa cứng, sử dụng tiện ích mở khóa tay cầm (Handle Unlocker) để giải phóng trước khi xóa.

### Output:
- **Nội dung:** Kết quả giải phóng ổ đĩa, số lượng khóa Registry và dịch vụ đã được dỡ bỏ.
- **Hình thức:** Biên bản nghiệm thu gỡ bỏ sạch.
- **Vị trí:** Cập nhật vào hồ sơ bảo trì hệ thống.
