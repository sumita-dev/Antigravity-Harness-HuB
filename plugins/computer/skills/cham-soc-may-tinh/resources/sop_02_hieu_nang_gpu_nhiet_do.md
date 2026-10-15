# Hướng Dẫn: Kiểm Soát Nhiệt Độ Phần Cứng & Cấu Hình Card Đồ Họa (GPU Performance & Thermal Tuning)

Tài liệu này đặc tả quy trình kỹ thuật đo đạc nhiệt độ phần cứng, phát hiện hạ xung do quá nhiệt (Thermal Throttling), cân bằng trần công suất điện năng và ghim card đồ họa rời hiệu năng cao cho các ứng dụng nặng.

---

## 1. CHỐT CHẶN BẢO VỆ: ĐO ĐẠC VÀ ĐIỀU PHỐI NĂNG LƯỢNG CPU

### Input:
- Thông tin bộ vi xử lý và cảm biến nhiệt độ — Vị trí: `Win32_Processor`, `MSAcpi_ThermalZoneTemperature`.

### Process:
- Bước 1: Đo độ lệch nhiệt độ (Delta T):
  - Chạy tải nhẹ trong 2 giây. Nếu nhiệt độ tăng vọt > 35°C trong < 1.5 giây: Tản nhiệt kém hoặc keo khô. Đề xuất giới hạn trần công suất PL1 (ví dụ 175W cho Core i9, 105W cho Ryzen 9).
  - Nếu nhiệt độ tăng chậm < 15°C: Tản nhiệt tốt, giữ nguyên trần công suất tối đa.
- Bước 2: Cấu hình chế độ quản lý điện năng cân bằng (Balanced Power Plan):
  ```powershell
  powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e
  ```
- Bước 3: Đảm bảo mức xung nhịp tối thiểu `PROCTHROTTLEMIN = 5%` để CPU tự hạ xung về ~800MHz khi nhàn rỗi, và `PROCTHROTTLEMAX = 100%` để bứt tốc tối đa khi có tác vụ nặng.

### Output:
- **Nội dung:** Thông số nhiệt độ và cấu hình trần công suất CPU ổn định.
- **Hình thức:** Bảng chỉ số kiểm tra nhiệt năng.
- **Vị trí:** Context làm việc của Agent.

---

## 2. QUÉT VÀ GHIM CARD ĐỒ HỌA RỜI HIỆU NĂNG CAO (DIRECTX DYNAMIC GPU PINNING)

### Input:
- Danh mục phần mềm đồ họa, dựng phim, kiến trúc và game launchers trên toàn bộ các phân vùng ổ đĩa.

### Process:
- Bước 1: Rà soát tự động danh sách các ứng dụng nặng qua 3 tầng:
  1. *Phần mềm dựng phim & kỹ xảo:* Adobe Premiere, After Effects, CapCut, DaVinci Resolve, Sony Vegas, Camtasia, OBS Studio...
  2. *Phần mềm đồ họa 2D/3D & CAD:* Photoshop, Lightroom, Illustrator, Blender, 3ds Max, Maya, AutoCAD, SketchUp, Revit...
  3. *Thư viện Game Launchers:* Steam (`steamapps\common`), Epic Games, Riot Games, Battle.net, EA Desktop...
- Bước 2: Ghim card đồ họa rời hiệu năng cao (`GpuPreference=2;`) vào Registry DirectX cho toàn bộ file thực thi tìm được:
  ```powershell
  Set-ItemProperty -Path "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences" -Name "$AppExePath" -Value "GpuPreference=2;"
  ```
- Bước 3: Chạy script kiểm tra đối soát (`check_gpu_profile.ps1`) đảm bảo 100% ứng dụng nặng đã được nhận diện card rời.

### Output:
- **Nội dung:** Danh sách ứng dụng đã được gán cờ card đồ họa rời thành công.
- **Hình thức:** Bảng danh mục GPU Assignment.
- **Vị trí:** Cập nhật vào hồ sơ bảo trì hệ thống.
