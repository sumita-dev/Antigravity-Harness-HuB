---
name: browser-hygiene
description: Rà soát và dọn dẹp an toàn các trình duyệt tự động (Chrome, Chromium, Edge headless, test-shell) và server dev/tiến trình mồ côi (node, python) do agent/tool bỏ quên. Kích hoạt khi người dùng gõ /browser-hygiene hoặc yêu cầu kiểm tra tiến trình/trình duyệt chạy ngầm.
---

# Kỹ Năng: Rà Soát & Dọn Dẹp Trình Duyệt / Tiến Trình Mồ Côi (Browser & Process Hygiene)

Kỹ năng này cung cấp quy trình 3 bước chuẩn mực để phát hiện và xử lý an toàn các tiến trình tự động hóa bị bỏ quên, bảo vệ tuyệt đối trình duyệt và dữ liệu cá nhân của người dùng.

---

## BƯỚC 1: KHẢO SÁT THỰC CHỨNG (CHỈ ĐỌC — CHƯA TẮT GÌ)

Khi được kích hoạt, Quản đốc chạy script kiểm tra tích hợp:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/scan_orphans.ps1"
```

### Nguyên tắc đối soát:
1. **Phân biệt rạch ròi trình duyệt cá nhân vs tự động hoá:**
   - **Bảo vệ tuyệt đối:** Các tiến trình Chrome/Edge chạy tương tác thông thường, sử dụng Profile mặc định (`AppData\Local\Google\Chrome\User Data` hoặc `AppData\Local\Microsoft\Edge\User Data`).
   - **Đưa vào diện rà soát:** Tiến trình có cờ `--headless`, `--remote-debugging-port`, `chrome-headless-shell`, hoặc `--user-data-dir` trỏ vào thư mục tạm (`Temp`, `scoped_dir`, `playwright`, `.agent`).
2. **Kiểm tra tiến trình cha (Parent Process Alive Check):**
   - Rà soát các tiến trình `node.exe`, `python.exe`, `uvicorn.exe`, `vite`, `next`.
   - Xác định rõ tiến trình cha còn sống hay đã biến mất (Orphaned / Mồ côi).
3. **Lập bảng báo cáo đầy đủ thông số:**
   - Bắt buộc ghi nhận: `PID`, `Tên tiến trình`, `Thời điểm khởi chạy`, `CPU / RAM (MB)`, `Tiến trình cha (Parent PID & Trạng thái)`, `Dòng lệnh thực thi / Thư mục Profile`.

---

## BƯỚC 2: ĐỀ XUẤT PHƯƠNG ÁN & CHỜ PHÊ DUYỆT (INTENT ALIGNMENT GATE)

Sau khi có dữ liệu từ Bước 1:
1. **Phân loại danh sách:**
   - **Nhóm đề xuất dừng:** Chỉ gồm các PID mồ côi đã xác thực (tiến trình cha đã chết) hoặc server test bị bỏ quên.
   - **Nhóm giữ nguyên:** Tiến trình MCP servers đang hoạt động, trình duyệt cá nhân của người dùng, hoặc tiến trình hệ thống.
2. ⛔ **ĐIỂM DỪNG BẮT BUỘC (Chờ duyệt):**
   - Trình bày danh sách đề xuất rõ ràng cho người dùng.
   - **DỪNG LẠI TUYỆT ĐỐI** và chờ người dùng xác nhận đồng ý ("OK", "Duyệt") trước khi thực hiện bất kỳ lệnh can thiệp nào.

---

## BƯỚC 3: THI CÔNG DỌN DẸP AN TOÀN

Khi người dùng đã phê duyệt danh sách PID:
1. **Chạy kịch bản dọn dẹp đích danh PID:**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/clean_orphans.ps1" -TargetPids @(<danh_sách_PID>)
   ```
2. **Kỷ luật dọn dẹp bất biến:**
   - **Tuyệt đối cấm kill hàng loạt theo tên:** Không bao giờ dùng `taskkill /F /IM chrome.exe` hay `Stop-Process -Name node` làm sập các ứng dụng đang làm việc của người dùng.
   - **Ưu tiên đóng đúng cách:** Nếu có server cha, tắt tiến trình cha để các tiến trình con tự giải phóng tài nguyên.
   - **Dọn dẹp thư mục profile tạm:** Chỉ xoá thư mục profile tạm sau khi đã xác minh không còn tiến trình nào đang chiếm dụng (Handle lock = 0).
3. **Nghiệm thu thực chứng:** Kiểm tra lại danh sách tiến trình sau khi tắt để đảm bảo tài nguyên RAM và cổng mạng đã được giải phóng hoàn toàn.

---

## QUY TẮC PHÒNG NGỪA DÀNH CHO CODE TỰ ĐỘNG HÓA CỦA AGENT

Mọi mã nguồn hoặc script do tác tử viết liên quan đến trình duyệt và server dev bắt buộc tuân thủ:
1. **Dùng trình duyệt riêng biệt:** Chỉ dùng **Chrome for Testing** hoặc browser binary do Playwright/Puppeteer tự quản lý trong cache riêng.
2. **Graceful Exit trong finally:**
   ```python
   # Python ví dụ:
   try:
       browser = await playwright.chromium.launch()
       # Thực hiện tác vụ
   finally:
       await browser.close()
   ```
3. **Tắt server preview:** Ngay khi hoàn tất kiểm định (UI test, local preview), bắt buộc gửi tín hiệu tắt dev server, không để chạy nền ngầm vô thời hạn.
