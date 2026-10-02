# Threat Matrix: Ma Trận 5 Nhóm Phương Thức Tấn Công Bản Quyền Ứng Dụng Desktop

Tài liệu này là nguồn tham chiếu kỹ thuật chuyên sâu, được sử dụng bởi skill `/reverse-lab` trong Bước 2 (Phân tích Điểm yếu & Threat Modeling). Đọc tài liệu này khi cần tra cứu chi tiết kỹ thuật của từng vector tấn công.

---

## NHÓM 1: Can Thiệp Tệp Tĩnh Trên Đĩa (Static Binary Patching)

**Điều kiện áp dụng:** Kẻ gian có quyền truy cập trực tiếp vào tệp `.exe`, `.dll`, `.jar`, `.pyc` trên ổ đĩa.

### 1.1 Instruction Patching (Sửa lệnh nhảy điều kiện)
- **Công cụ:** Ghidra, IDA Pro, x64dbg, dnSpy (cho .NET), JADX (cho Java/Android)
- **Cơ chế:** Logic `if (is_valid == true)` ở cấp cao được biên dịch thành lệnh nhảy máy `JZ`/`JNZ`/`JE`/`JNE`. Kẻ gian tìm chuỗi nhạy cảm (`"Trial Expired"`, `"Invalid License"`) trong disassembler để định vị địa chỉ lệnh nhảy, sau đó dùng Hex Editor ghi đè:
  - `JZ` → `JMP` (luôn nhảy vào nhánh thành công)
  - Toàn bộ đoạn mã kiểm tra → chuỗi `NOP` (byte `0x90` - bỏ qua hoàn toàn)
- **Dấu hiệu nhận biết trong code:** Logic kiểm tra nằm hoàn toàn ở Client, không có xác thực Server-side độc lập.

### 1.2 Function Prologue Hooking / NOPing
- **Cơ chế:** Kẻ gian nhắm vào điểm đầu hàm (Function Prologue). Ghi đè bằng:
  - `MOV EAX, 1` + `RET` (trên x86): ép hàm luôn trả về `true`
  - `XOR EAX, EAX` + `INC EAX` + `RET`: biến thể tương đương
- **Mục tiêu thường gặp:** Hàm `bool CheckLicenseFromServer()`, `bool ValidateKey(string key)`, `bool IsActivated()`, `int GetRemainingDays()`

### 1.3 DLL Hijacking & Proxying
- **DLL Replacement:** Kẻ gian tự viết DLL giả có cùng tên và danh sách Exported Functions, nhưng mỗi hàm bản quyền chỉ `return true;`. Copy đè lên DLL gốc.
- **DLL Proxying:** Đổi tên DLL gốc thành `license_manager_real.dll`. DLL giả trung gian forward tất cả các hàm phụ về DLL gốc, nhưng sửa kết quả trả về của hàm bản quyền thành thành công. Ứng dụng không bị crash, khó phát hiện hơn.
- **Điều kiện áp dụng:** App tách module xác thực bản quyền ra file DLL riêng, tải động bằng `LoadLibrary`.

---

## NHÓM 2: Can Thiệp Bộ Nhớ Khi Chạy (Dynamic Runtime / Memory Patching)

**NGUY HIỂM NHẤT:** Kẻ gian **không chạm vào tệp trên đĩa**. Mọi cơ chế kiểm tra Hash SHA-256 tĩnh đều **vô tác dụng**.

### 2.1 In-Memory Loader / Process Hollowing
- **Công cụ tự viết bằng:** C/C++/C# sử dụng Win32 API
- **Cơ chế kỹ thuật (tuần tự):**
  1. `CreateProcess(target.exe, ..., CREATE_SUSPENDED)` — khởi chạy tiến trình ứng dụng ở trạng thái đóng băng
  2. `VirtualQueryEx` — quét bản đồ bộ nhớ của tiến trình để tìm địa chỉ phân vùng `.text` (code section)
  3. `VirtualProtectEx(hProcess, addr, PAGE_EXECUTE_READWRITE)` — mở quyền ghi vào vùng code
  4. `WriteProcessMemory(hProcess, addr, patch_bytes, ...)` — ghi đè các byte cần patch
  5. `ResumeThread(hThread)` — đánh thức tiến trình chạy bình thường với code đã bị sửa trong RAM
- **Hệ quả:** Tệp `.exe` trên đĩa **nguyên vẹn 100%**, Hash SHA-256 luôn khớp.

### 2.2 Dynamic Instrumentation (Frida, Cheat Engine, x64dbg Attach)
- **Frida:** Framework injection mã JavaScript/Python vào tiến trình đang chạy. Kẻ gian viết script hook hàm bản quyền, sửa giá trị trả về:
  ```javascript
  // Frida script mẫu
  Interceptor.attach(Module.findExportByName(null, "CheckLicense"), {
    onLeave: function(retval) { retval.replace(1); } // ép trả về true
  });
  ```
- **Cheat Engine:** Quét bộ nhớ tìm biến lưu trạng thái (`is_licensed = 0`), đổi thành `1`, bật chế độ freeze để giữ nguyên giá trị.

### 2.3 OS-Level API Hooking (Thời gian & Registry)
- **Mục tiêu:** Hàm `GetSystemTimeAsFileTime`, `GetLocalTime`, `RegQueryValueExW`
- **Cơ chế:** Sử dụng kỹ thuật Detour (ghi đè 5 byte đầu hàm API trong `kernel32.dll` / `ntdll.dll` bằng lệnh `JMP` tới hàm hook của kẻ gian). Hàm hook luôn trả về:
  - Ngày/giờ giả mạo (trong thời hạn trial)
  - Giá trị Registry giả (ngày cài đặt giả, key hợp lệ giả)
- **Phát hiện:** Rất khó nếu không có Anti-Hooking kiểm tra byte đầu các system API.

---

## NHÓM 3: Thao Túng Mạng (Network-Based Bypass)

**Điều kiện áp dụng:** App dùng Online Activation qua HTTP/HTTPS.

### 3.1 Local Server Emulation + Hosts File Redirect
- **Cơ chế:**
  1. Thêm vào `C:\Windows\System32\drivers\etc\hosts`: `127.0.0.1 api.license-server.com`
  2. Dựng server mini trên localhost (Node.js/Python/Flask) lắng nghe cổng 80/443
  3. Server giả trả về JSON/XML cấu trúc báo thành công dựa trên kết quả thám thính Mitmproxy trước đó
- **Dấu hiệu điểm yếu:** Response kích hoạt không có thành phần động (Nonce, Timestamp), không ký số.

### 3.2 Replay Attack (Tấn công Phát lại)
- **Công cụ:** Mitmproxy, Fiddler, Charles Proxy, Burp Suite
- **Điều kiện:** Response từ Server không có Nonce (chuỗi dùng 1 lần), không có Timestamp gắn chặt, không có Session Token ngắn hạn.
- **Cơ chế:** Bắt Response hợp lệ từ một máy đã mua key thật → lưu lại → phát lại mãi mãi cho các máy khác.

### 3.3 SSL/TLS Pinning Bypass
- **Bước 1 — Nếu không có Pinning:** Cài chứng chỉ Root CA giả vào Windows Certificate Store → Mitmproxy tự động giải mã toàn bộ HTTPS.
- **Bước 2 — Nếu có SSL Pinning:** Dịch ngược tìm hàm so sánh fingerprint chứng chỉ, patch thành `return true` (tương tự Nhóm 1). Frida cũng có thể hook `SSL_CTX_set_verify` hoặc `.NET`'s `ServicePointManager.ServerCertificateValidationCallback`.

---

## NHÓM 4: Thao Túng Môi Trường & Thiết Bị (Environment Manipulation)

### 4.1 Registry / File Tampering (Đóng băng Trial)
- **Công cụ:** Process Monitor (ProcMon) — Microsoft Sysinternals Suite
- **Quy trình:** Lọc hành vi Read/Write của process khi khởi động → xác định file/key Registry lưu ngày cài đặt → viết script tự động xóa/reset giá trị đó sau mỗi lần tắt app.
- **Biến thể:** Sửa giá trị `ExpiryDate` trong Registry thành `2099-12-31`.

### 4.2 Keygen (Tạo khóa giả mạo)
- **Điều kiện:** App kiểm tra license hoàn toàn Offline bằng thuật toán toán học cố định (Checksum, Luhn, mã hóa đối xứng nhúng key bí mật cứng trong code).
- **Cơ chế:** Dịch ngược hàm `ValidateKey(string key)`, phân tích logic toán học, viết phần mềm Keygen đảo ngược công thức để sinh key tùy ý.
- **Biến thể nguy hiểm:** Universal Keygen nếu thuật toán kiểm tra giống nhau trên nhiều phiên bản.

### 4.3 HWID Spoofing & VM Manipulation
- **HWID Spoofer:** Can thiệp driver mức Kernel (hoặc WMI) để trả về CPU ID, MAC Address, Disk Serial giả mạo giống hệt máy đã đăng ký bản quyền hợp lệ.
- **VM Cloning:** Kích hoạt bản quyền trong VMware/VirtualBox → export OVA file → phân phối cho nhiều người dùng. Tất cả cùng chạy trên một HWID giống hệt nhau.
- **VM Snapshot Rollback:** Chụp Snapshot lúc vừa cài phần mềm → sau 29 ngày trial khôi phục Snapshot → dùng thử vô hạn mà không cần bẻ khóa.

---

## NHÓM 5: Rủi Ro Đặc Thù Theo Nền Tảng Công Nghệ (Tech Stack Risks)

| Nền tảng | Mức độ dễ dịch ngược | Công cụ tấn công | Đặc điểm khai thác |
|:---|:---:|:---|:---|
| **C# / .NET / VB.NET** | ⚠️ Rất Cao | dnSpy, ILSpy, dotPeek | IL bytecode giữ nguyên tên hàm/biến. Dịch ngược về code C# gần như 90-95% nguyên bản. Dễ sửa code, recompile. |
| **Java / Kotlin (Desktop)** | ⚠️ Rất Cao | JADX, JD-GUI, Bytecode Viewer | .class/.jar bytecode tương tự .NET IL. Dịch ngược rất sạch. |
| **Electron / NW.js** | ⚠️ Rất Cao | `npx asar extract` (1 lệnh) | Toàn bộ JS source trong `app.asar`. Kẻ gian chỉ cần unpack, sửa file .js và repack lại. |
| **Python (PyInstaller, Py2exe)** | ⚠️ Cao | pyinstxtractor, uncompyle6, decompyle++ | Unpack → `.pyc` bytecode → dịch ngược ra `.py`. Mã nguồn Python lộ hoàn toàn. |
| **C / C++ Native** | ✅ Trung bình | Ghidra, IDA Pro, Binary Ninja | Không còn tên biến/hàm (đã stripped). Đòi hỏi kiến thức Assembly sâu nhưng vẫn bị Instruction Patching nếu thiếu Anti-Debug. |
| **Rust / Go** | ✅ Khá thấp | Ghidra + plugin | Bộ nhớ an toàn, panic mechanism. Tuy nhiên vẫn bị Memory Patching nếu không có Anti-Tamper runtime. |
