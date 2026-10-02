# Sổ Tay Rủi Ro Bản Quyền Theo Nền Tảng Công Nghệ (Tech Stack Vulnerability Handbook)

Tài liệu này cung cấp hướng dẫn chuyên sâu theo từng stack công nghệ: cách kẻ gian khai thác đặc thù của ngôn ngữ/framework, và các biện pháp phòng thủ cụ thể phù hợp với từng nền tảng.

---

## C# / .NET Framework & .NET Core

### Điểm yếu đặc thù
- Biên dịch ra **IL (Intermediate Language)** bytecode, không phải mã máy native. IL giữ nguyên tên namespace, class, method, field.
- Công cụ dịch ngược như **dnSpy**, **ILSpy**, **dotPeek** có thể phục hồi gần như 100% mã C# gốc (kể cả LINQ, async/await, lambda).
- **dnSpy** không chỉ đọc mà còn có thể **biên dịch lại và thay thế method** trực tiếp trong file DLL/EXE mà không cần có mã nguồn gốc.
- Reflection API của .NET cho phép kẻ gian enumerate và gọi bất kỳ method `private` nào lúc runtime.

### Kịch bản tấn công phổ biến
```
dnSpy → mở App.exe → tìm class "LicenseValidator" → 
sửa hàm "CheckActivation()" return true → File → Save Module
```

### Biện pháp phòng thủ đặc thù
1. **Obfuscation .NET chuyên dụng:** ConfuserEx (free), Dotfuscator (commercial), Eazfuscator. Không chỉ đổi tên mà cần bật: String Encryption, Control Flow Obfuscation, Anti-Tamper, Anti-Debug mode.
2. **Native AOT (.NET 7+):** Biên dịch trực tiếp ra mã máy native (như C++), loại bỏ hoàn toàn IL bytecode và khả năng dịch ngược dễ dàng.
3. **Tách hàm nhạy cảm ra DLL riêng viết bằng C++/Rust:** Mix native code với managed code. Phần kiểm tra bản quyền viết bằng C++ native, gọi từ C# qua P/Invoke.

---

## Electron / NW.js (JavaScript Desktop Apps)

### Điểm yếu đặc thù
- **Toàn bộ mã nguồn JavaScript/HTML/CSS** được đóng gói trong file `resources/app.asar` — thực chất là file ZIP/TAR đặc biệt.
- Một lệnh duy nhất để giải nén toàn bộ:
  ```bash
  npx asar extract resources/app.asar ./app_source/
  ```
- Sau khi giải nén, kẻ gian có thể đọc, sửa `main.js`, `renderer.js`, các file logic bản quyền... rồi đóng gói lại:
  ```bash
  npx asar pack ./app_source/ resources/app.asar
  ```
- Không cần bất kỳ kỹ năng dịch ngược nào — chỉ cần biết đọc JavaScript.

### Biện pháp phòng thủ đặc thù
1. **Bật tính năng tích hợp ASAR Integrity trong Electron Forge/Fuses:** Electron 12+ hỗ trợ ASAR Integrity (checksums). Nếu file `.asar` bị sửa, app từ chối khởi chạy.
2. **JavaScript Obfuscation:** Dùng **javascript-obfuscator** (mạnh hơn UglifyJS nhiều) để mã hóa string, đổi tên biến, làm rối control flow.
3. **Tách logic nhạy cảm ra Node.js Addon native (`.node` file):** Viết module bản quyền bằng C++ dạng Node Addon. Kẻ gian không thể đọc được bằng cách mở text editor.
4. **Không bao giờ đặt Secret, API Key, Private Key trong code JS phía Renderer Process.**

---

## Python (PyInstaller, Py2exe, Nuitka)

### Điểm yếu đặc thù
- **PyInstaller/Py2exe:** Về cơ bản chỉ là bộ giải nén tự động kèm Python interpreter. Cấu trúc thực sự:
  - `app.exe` → khi chạy, giải nén vào thư mục `%TEMP%\_MEIxxxxxx/`
  - Bên trong có các file `.pyc` (Python bytecode)
- Công cụ tấn công:
  ```bash
  # Bước 1: Bung ngược PyInstaller bundle
  python pyinstxtractor.py app.exe
  # Bước 2: Dịch .pyc về .py
  uncompyle6 app.cpython-311.pyc > app.py
  # hoặc: decompyle3, decompyle++
  ```
- Kết quả: Mã Python gần như nguyên bản, rõ ràng từng dòng logic kiểm tra bản quyền.

### Ngoại lệ
- **Nuitka:** Biên dịch Python ra C rồi compile sang native binary. Kết quả khó dịch ngược hơn đáng kể (giống C++).

### Biện pháp phòng thủ đặc thù
1. **Dùng Nuitka thay PyInstaller** cho phần code bản quyền nhạy cảm.
2. **Cython + biên dịch C extension:** Viết module bản quyền bằng Cython, biên dịch ra file `.pyd` (native DLL). Khó dịch ngược như C++.
3. **Không lưu secret hardcode trong .py file.** Mọi secret phải đến từ Server call có xác thực.

---

## C / C++ Native (Win32, Qt, MFC)

### Điểm yếu đặc thù
- Biên dịch ra mã máy (x86/x64 Assembly) — không còn tên hàm/biến nếu đã stripped symbols.
- Khó dịch ngược hơn managed code, nhưng **không phải không thể** can thiệp:
  - Instruction Patching vẫn áp dụng hoàn toàn (xem Threat Matrix Nhóm 1)
  - Memory Patching/In-Memory Loader vẫn hiệu quả (xem Threat Matrix Nhóm 2)
  - Nếu **không strip symbols**, Ghidra/IDA Pro dịch ngược rất hiệu quả

### Điểm mạnh tự nhiên
- String ít lộ hơn (không có Reflection)
- Khó re-compile lại sau khi sửa
- Phù hợp nhất để tích hợp các giải pháp Anti-Debug và Code Virtualization

### Biện pháp phòng thủ đặc thù
1. **Luôn bật strip symbols** khi build Release (`/PDBSTRIPPED` hoặc `-s` flag).
2. Bật tối ưu hóa trình biên dịch (`/O2`, `-O3`) kết hợp với **Link-Time Optimization (LTO)** để làm khó việc nhận diện ranh giới hàm.
3. **VMProtect / Themida** ảo hóa mã hiệu quả nhất với binary native C/C++.

---

## Rust / Go

### Điểm mạnh tự nhiên
- Rust: Ownership model, không có garbage collector, không có runtime riêng → binary rất gần với C++.
- Go: Binary tự chứa toàn bộ runtime, symbol names thường vẫn còn trong binary (nếu không strip).

### Điểm yếu cần chú ý
- **Go binary mặc định GIỮ nguyên symbol names** (package path, function names). Ghidra phục hồi tên hàm Go rất tốt. Cần build với: `go build -ldflags="-s -w"` để strip.
- Cả Rust và Go đều vẫn bị **Memory Patching** (Nhóm 2) nếu không có Anti-Tamper runtime.
