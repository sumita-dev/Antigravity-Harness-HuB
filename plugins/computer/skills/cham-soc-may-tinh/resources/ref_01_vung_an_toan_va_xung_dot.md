# Cẩm Nang: Ma Trận 3 Vùng An Toàn & Xung Đột Hệ Thống 5 Tầng (Safety Boundaries & System Conflict Matrix)

Tài liệu này xác định ranh giới can thiệp an toàn tuyệt đối của hệ điều hành Windows và cung cấp bảng ma trận nhận diện 5 tầng xung đột giữa phần cứng, driver, dịch vụ và ứng dụng.

---

## 1. PHÂN ĐỊNH 3 VÙNG CAN THIỆP AN TOÀN

### VÙNG ĐỎ (BẤT BIẾN — TUYỆT ĐỐI CẤM ĐỤNG CHẠM)
Chỉ bao gồm các thành phần nhân sống còn của Windows. Bất kỳ sự can thiệp nào vào vùng này đều có nguy cơ gây lỗi màn hình xanh (BSOD) hoặc hỏng hệ điều hành:
- **Thư mục nhân Windows:** `C:\Windows\System32`, `SysWOW64`, `WinSxS`, `Boot`, `Recovery`.
- **Tệp hệ thống cốt lõi:** `pagefile.sys`, `swapfile.sys`, `dumpstack.log.tmp`.
- **Khóa Registry nhân:** `HKLM:\SAM`, `SECURITY`, `SYSTEM\CurrentControlSet\Control`, `HARDWARE`.
- **Dịch vụ hệ điều hành tối quan trọng:** RPCSS, DcomLaunch, EventLog, PlugPlay, SamSs.

---

### VÙNG VÀNG (BẮT BUỘC HỎI Ý KIẾN NGƯỜI DÙNG TRƯỚC KHI CAN THIỆP)
Dữ liệu công việc hoặc tệp cấu hình có giá trị tái sử dụng cao. Bắt buộc người dùng phê duyệt trước khi dọn dẹp hoặc gỡ bỏ:
1. **Môi trường lập trình & Trí tuệ nhân tạo:** Thư mục `.conda`, `miniconda3`, các thư viện `torch`, `cuda`, ổ đĩa ảo `.vhdx` của Docker/WSL2, khóa bảo mật `.ssh`.
2. **Tài sản sáng tạo:** Cọ vẽ và bảng màu Adobe Presets, tệp cấu hình dự án dựng phim CapCut/Premiere (`.json`).
3. **Bộ nhớ đệm phần mềm đang làm việc:** Cache render dựng phim CapCut hoặc Premiere (sẽ phải render lại nếu mở dự án cũ), tệp tải về cập nhật Windows (`SoftwareDistribution\Download`).
4. **Dịch vụ khởi động của hãng:** Các phần mềm tự khởi động cùng Windows (OneDrive, Google Drive Sync, Zalo, Discord, Steam).

---

### VÙNG XANH (AN TOÀN XỬ LÝ TỰ HÀNH)
Dữ liệu rác vô giá trị và lịch sử tạm thời, tự động giải phóng trong quy trình bảo dưỡng thường quy:
1. **Thư mục tạm:** `%LOCALAPPDATA%\Temp`, `C:\Windows\Temp`.
2. **Nhật ký lỗi crash:** `%LOCALAPPDATA%\CrashDumps`, `C:\Windows\WER\ReportQueue`.
3. **Bộ nhớ đệm hình ảnh thu nhỏ:** Windows Thumbnail Cache (`thumbcache_*.db`).
4. **Lịch sử tệp gần đây (Recent Items & JumpLists):** `%APPDATA%\Microsoft\Windows\Recent`, `AutomaticDestinations`, `CustomDestinations`, `RunMRU`, `TypedPaths`.
5. **Hàng đợi máy in bị kẹt:** Tệp spooler `.SPL` và `.SHD` trong `System32\spool\PRINTERS`.
6. **Bộ nhớ RAM nhàn rỗi:** Vùng Working Set dư thừa của các dịch vụ nền không phát sinh I/O > 15 phút.

---

## 2. MA TRẬN XUNG ĐỘT HỆ THỐNG 5 TẦNG

| Tầng Xung Đột | Hiện Tượng Kỹ Thuật | Nguyên Nhân Gốc Rễ | Phương Án Xử Lý An Toàn |
| :--- | :--- | :--- | :--- |
| **Tầng 1: Phần cứng & BIOS/UEFI** | Màn hình xanh ngẫu nhiên `MEMORY_MANAGEMENT`, crash game/render đột ngột. | Cấu hình ép xung RAM (XMP/EXPO) vượt quá khả năng chịu tải của bộ điều khiển bộ nhớ (IMC) trên CPU. | Giữ nguyên mức xung ổn định theo danh sách tương thích (QVL) của bo mạch chủ; kiểm tra trần công suất PL1/PL2. |
| **Tầng 2: Driver phần cứng** | Sụt giảm khung hình (drop FPS), âm thanh bị rè, màn hình chớp nháy. | Cài đặt đè nhiều phiên bản driver GPU khác nhau hoặc driver âm thanh Realtek bị xung đột với phần mềm bên thứ ba (Nahimic, Sonic Studio). | Gỡ sạch driver cũ bằng Display Driver Uninstaller (DDU); cài bản driver WHQL ổn định nhất từ nhà sản xuất. |
| **Tầng 3: Dịch vụ & Tranh chấp I/O** | Máy tính khởi động chậm mất 1-2 phút, CPU và ổ đĩa 100% trong thời gian đầu mở máy. | Đồng thời chạy nhiều dịch vụ cập nhật ngầm (Autodesk Access, Adobe CC, Apple Mobile Device, OEM Telemetry). | Chuyển trạng thái khởi động của các dịch vụ cập nhật sang `Manual` (chỉ chạy khi người dùng bật phần mềm chính). |
| **Tầng 4: Ảo hóa vs Game Anti-cheat** | Game bảo vệ cấp nhân (Vanguard, Easy Anti-Cheat, BattlEye) từ chối khởi động hoặc báo lỗi driver. | Xung đột giữa tính năng ảo hóa Windows (Hyper-V, WSL2, Sandbox) với cơ chế bảo vệ nhân của game. | Tách biệt hồ sơ cấu hình: Bật Hyper-V khi lập trình và tạm tắt khi chơi game nặng. |
| **Tầng 5: Ứng dụng kép trùng lặp** | Tràn bộ nhớ RAM, chuột bị giật khựng, máy bị đứng hình vài giây. | Chạy song song 2 phần mềm diệt virus bên thứ ba, hoặc mở cùng lúc nhiều trình đồng bộ đám mây quét liên tục ổ đĩa. | Giữ lại 1 giải pháp bảo mật chính quy (Windows Defender kết hợp kiểm tra định kỳ); tắt tự đồng bộ nền cho các thư mục code nặng (`node_modules`, `venv`). |
