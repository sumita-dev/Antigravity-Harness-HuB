# Hướng Dẫn: Quy Trình Khảo Sát Hiện Trạng & Khởi Tạo Lệnh Tắt Một Chạm (Quick Audit & One-Touch Onboarding)

Tài liệu này đặc tả quy trình khảo sát sơ bộ hệ thống siêu tốc (~800ms) không phá hủy, nhận diện Workload sử dụng thực tế của máy tính và tự động thiết lập lệnh tắt một chạm (`care.cmd` / `care.ps1`) tại thư mục làm việc của người dùng.

---

## 1. CHỐT CHẶN BẢO VỆ: KHẢO SÁT HIỆN TRẠNG SIÊU TỐC (NON-DESTRUCTIVE QUICK AUDIT)

### Input:
- Yêu cầu ban đầu từ người dùng ("dọn dẹp máy", "máy bị chậm", "/cham-soc-may-tinh").
- Script kiểm tra tổng hợp: `diagnose_all.ps1`.

### Process:
- Bước 1: Thực thi ngầm kịch bản `diagnose_all.ps1` trong chế độ chỉ đọc (Read-only), tuyệt đối không xóa file, không ghi registry, không tắt tiến trình.
- Bước 2: Thu thập 10 nhóm thông số:
  1. Dung lượng tệp tạm (Windows Temp, User Temp, Crash Dumps).
  2. Dung lượng bản cập nhật Windows Update cũ trong WinSxS.
  3. Mức chiếm dụng RAM và danh sách tiến trình nền nhàn rỗi.
  4. Trạng thái phân mảnh 243+ cơ sở dữ liệu SQLite nội bộ.
  5. Dung lượng trống phân vùng C: và trạng thái TRIM ổ SSD NVMe.
  6. Phân loại máy tính: PC Desktop (bỏ qua pin) vs Laptop (đo độ chai pin).
  7. Trạng thái hàng đợi máy in (Print Spooler).
  8. Độ trễ mạng DNS và cấu hình mạng TCP.
  9. Mã lỗi phần cứng ngoại vi PnP (USB, Audio).
  10. Trạng thái an toàn khởi động (Secure Boot, Driver Signing WHQL).
- Bước 3: Xuất kết quả ra tệp máy đọc `HealthReport.json`.

### Output:
- **Nội dung:** Báo cáo hiện trạng kỹ thuật số liệu thực tế.
- **Hình thức:** Tệp JSON và bảng tóm tắt ngắn gọn trên màn hình.
- **Vị trí:** Context làm việc của Agent.

---

## 2. XUẤT PHIẾU KHẢO SÁT & THIẾT LẬP LỆNH TẮT TẠI WORKSPACE

### Input:
- Dữ liệu từ `HealthReport.json`.
- Thư mục làm việc hiện tại của người dùng (`$PWD` / workspace root).

### Process:
- Bước 1: Trình bày **Phiếu Kiểm Tra Sơ Bộ** với ngôn ngữ kỹ thuật đời thường, rõ ràng, nêu bật các điểm nghẽn (ví dụ: ổ C còn trống bao nhiêu GB, có bao nhiêu MB rác có thể thu hồi).
- Bước 2: Tự động kiểm tra và khởi tạo file lệnh tắt một chạm ngay tại thư mục hiện hành:
  - `care.cmd` (dành cho CMD)
  - `care.ps1` (dành cho PowerShell)
- Bước 3: Hướng dẫn người dùng 2 phương thức theo dõi:
  - **Phương thức A (AI Tự Hành):** Người dùng đồng ý, AI tự chạy ngầm và mở file hồ sơ Markdown trực tiếp trên editor.
  - **Phương thức B (Terminal Tương Tác):** Người dùng chuyển sang tab Terminal bên dưới và gõ lệnh ngắn:
    ```powershell
    .\care
    ```

### Output:
- **Nội dung:** 2 file lệnh tắt sẵn sàng sử dụng và giao diện hướng dẫn người dùng trực quan.
- **Hình thức:** Tệp tin vật lý tại workspace và tin nhắn dẫn đường trong chat.
- **Vị trí:** `$PWD\care.cmd` và `$PWD\care.ps1`.
