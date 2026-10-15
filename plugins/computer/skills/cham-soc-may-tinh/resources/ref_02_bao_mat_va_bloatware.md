# Cẩm Nang: Bảo Mật Nhân, Tối Ưu Dịch Vụ Khởi Động & Xử Lý Phần Mềm Rác (Security, Startup & Bloatware Reference)

Tài liệu này cung cấp danh mục dịch vụ chạy ngầm làm chậm máy, giải thích bản chất rủi ro lỗ hổng Driver cấp nhân (Ring 0 BYOVD), danh sách ứng dụng rác (Bloatware) cài sẵn và các mẫu từ khóa tra cứu thông tin trực tuyến.

---

## 1. BẢN CHẤT TRANH CHẤP DỊCH VỤ KHỞI ĐỘNG (STARTUP CONTENTION)

### Hiện Tượng & Nguyên Nhân
Khi vừa bật máy, máy tính bị đơ chuột, quạt quay mạnh dù cấu hình cao. Nguyên nhân do 10-20 dịch vụ tự động đăng ký chạy cùng Windows tranh chấp đọc đĩa (Disk I/O) và chiếm dụng 1.5 - 3 GB RAM:
- **Dịch vụ tự động cập nhật:** `AdskAccessService.exe` (Autodesk), `AdobeARMservice.exe` (Adobe), `GoogleUpdate.exe`.
- **Dịch vụ thiết bị di động:** `mDNSResponder.exe` (Bonjour/Apple), `AppleMobileDeviceService.exe`.
- **Dịch vụ thu thập dữ liệu chẩn đoán (Telemetry):** Dell SupportAssist, HP Touchpoint Analytics, Lenovo Vantage Telemetry.
- **Trình khởi động game/chat:** Steam, Epic Games, Discord, Spotify, Zalo tự bật cửa sổ nền.

### Giải Pháp Tối Ưu Hóa An Toàn
- **Nguyên tắc:** Chuyển trạng thái khởi động từ `Automatic` sang `Manual` (Thủ công). Dịch vụ không tự chạy khi bật máy, nhưng khi người dùng mở ứng dụng chính (ví dụ mở Photoshop hay AutoCAD), Windows sẽ tự động kích hoạt dịch vụ mà không bị gián đoạn tính năng.
- Lệnh PowerShell:
  ```powershell
  Set-Service -Name "<TenDichVu>" -StartupType Manual
  ```

---

## 2. RỦI RO LỖ HỔNG DRIVER CẤP NHÂN (RING 0 BYOVD)

### Khái Niệm Kỹ Thuật
Driver cấp nhân (Kernel Driver) chạy với đặc quyền cao nhất của hệ điều hành. Kỹ thuật tấn công **BYOVD (Bring Your Own Vulnerable Driver)** là hình thức mã độc cài cắm một file `.sys` hợp pháp của bên thứ ba nhưng đã cũ và chứa lỗ hổng bảo mật đã biết (CVE) nhằm vượt qua mặt Windows Defender và chiếm quyền kiểm soát hệ thống.

### Cách Nhận Diện & Xử Lý
1. **Kiểm tra trạng thái bảo vệ BCD:** Đảm bảo chế độ thực thi chữ ký số driver (WHQL Driver Signature Enforcement) luôn được kích hoạt (`nointegritychecks = No`, `testsigning = No`).
2. **Quét danh sách driver bên thứ ba:**
   ```powershell
   pnputil /enum-drivers
   ```
3. **Cách ly driver lạ:** Nếu phát hiện file `.sys` không rõ nguồn gốc nằm ngoài thư mục `System32\drivers`, tiến hành dừng dịch vụ (`sc.exe stop`), gán cờ `Deny Execute` và đưa vào thư mục cách ly `_Quarantine`.

---

## 3. DANH MỤC PHẦN MỀM RÁC CÀI SẴN (OEM BLOATWARE)

Các dòng laptop và máy bộ xuất xưởng thường bị cài kèm nhiều phần mềm quảng cáo hoặc tiện ích thừa làm nặng máy:

| Hãng Sản Xuất | Tên Phần Mềm Rác Điển Hình | Tác Động Tiêu Cực | Khuyến Nghị Xử Lý |
| :--- | :--- | :--- | :--- |
| **Dell / Alienware** | Dell SupportAssist, Dell Customer Connect, Alienware Command Center (bản cũ) | Chiếm dụng RAM liên tục, tạo tiến trình quét đĩa ngầm ngẫu nhiên. | Gỡ bỏ nếu không sử dụng bảo hành tự động; thay bằng cập nhật driver thủ công. |
| **HP** | HP Touchpoint Analytics, HP Support Assistant, HP JumpStarts | Gửi dữ liệu chẩn đoán về hãng, xung đột dịch vụ nền. | Gỡ bỏ hoàn toàn. |
| **Lenovo** | Lenovo Vantage Telemetry, Lenovo Now, Lenovo Welcome | Chiếm dụng dịch vụ nền, hiện thông báo quảng cáo phụ kiện. | Chuyển dịch vụ sang Manual hoặc dùng công cụ mã nguồn mở nhẹ hơn (Lenovo Legion Toolkit). |
| **ASUS** | Armoury Crate (bản đầy đủ), ASUS Giftbox, MyASUS | Rất nặng hệ thống, cài cắm hàng chục dịch vụ con cấp thấp. | Dùng công cụ gỡ chính thức (Armoury Crate Uninstall Tool); dùng giải pháp thay thế siêu nhẹ (G-Helper). |

---

## 4. MẪU TỪ KHÓA TRA CỨU WEB KHI GẶP SỰ CỐ

Khi gặp hiện tượng lạ trên phần cứng hoặc mã lỗi Windows, sử dụng cú pháp tìm kiếm chính xác:
- **Tra cứu nhiệt độ & trần công suất CPU:**
  `"<Ten_CPU>" "thermal throttling" "power limit" "undervolt" "reddit"`
- **Tra cứu độ ổn định của bản driver mới:**
  `"<Phien_Ban_Driver>" "known issues" "stability" "stutter" "reddit"`
- **Tra cứu mã lỗi bản cập nhật Windows Update:**
  `"<Ma_Loi_0x800...>" "Windows 11" "fix" "standalone update"`
- **Tra cứu độ tin cậy của tệp thực thi lạ:**
  `"<Ten_File.exe>" "process info" "legitimate or malware"`
