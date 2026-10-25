---
name: cham-soc-may-tinh
description: >-
  BẢO DƯỠNG VÀ TỐI ƯU HÓA MÁY TÍNH WINDOWS theo phương pháp đối soát thực nghiệm 2 chiều. Hỗ trợ bảo dưỡng định kỳ nhanh và điều tra chuyên sâu theo hiện tượng cụ thể, phân tích nguyên nhân qua bộ công cụ nội tại kết hợp tra cứu tài liệu bên ngoài, lập trước biên bản kỹ thuật LATEST_CSSK.md với 3 chốt chặn đọc lại bắt buộc. Hỗ trợ rà soát và giải phóng dung lượng ổ C chuyên sâu: cache công cụ lập trình (pip, npm, pnpm, docker), crash dumps / WER, thùng rác (recycle bin) và làm mới DNS Resolver. Kích hoạt khi người dùng nói 'máy tính chậm', 'dọn rác máy', 'tối ưu windows', 'bảo dưỡng pc', 'giải phóng ram', 'alt tab bị giật', 'chuyển ứng dụng khựng', 'máy đơ', 'computer-optimize', 'dọn dẹp và tối ưu máy tính', 'dọn cache pip npm pnpm', 'dọn docker'.
---

# Kỹ Năng: Chăm Sóc & Tối Ưu Hóa Máy Tính Windows (Targeted PC Care Engine)

> **TRIẾT LÝ LÕI:**
> - **Giao tiếp đời thường, kỹ thuật chuẩn xác:** Khi nói chuyện với người dùng, sử dụng ngôn ngữ bình dân, tự nhiên, dễ hiểu. Khi thực thi và lập biên bản kỹ thuật, ghi chép chuẩn xác từng byte RAM, ms phản hồi, đường dẫn Registry và lệnh PowerShell.
> - **Kỷ luật đối soát 2 chiều:** Kết hợp đo đạc nội tại trên máy để loại bỏ định kiến, kết hợp tra cứu tài liệu bên ngoài (`search_web`) để quét diện rộng nguyên nhân gốc rễ.
> - **Bộ đôi Markdown đồng bộ thời gian thực:** Mọi quy trình can thiệp bắt buộc duy trì song song File 1 (`LATEST_CSSK.md` - Checklist kế hoạch) và File 2 (`NHAT_KY_TIEN_TRINH_MOI_NHAT.md` - Log stream thời gian thực).

---

## 1. NGUYÊN TẮC VẬN HÀNH & PHÂN ĐỊNH TRÁCH NHIỆM

Kỹ năng tuân thủ kiến trúc phân tầng khám phá dần (Progressive Disclosure):
- **`SKILL.md` (Bộ Não Điều Phối Mỏng):** Chứa 3 Chốt Chặn Bắt Buộc (Gate 1, 2, 3), quy tắc IPO đệ quy và 3 trạm kiểm soát đọc lại `view_file`.
- **`scripts/` (Hệ Thống Thực Thi):** Chứa `diagnose_all.ps1`, `CSSK_LiveLogger.ps1`, `execute_selected.ps1` và các task chuyên biệt (kèm module dev caches: pip, npm, pnpm, docker, recycle bin, dns).
- **`resources/` (Tài Liệu Chuyên Sâu):** Chứa các SOP tra cứu mã lỗi, bloatware, ngưỡng định lượng và quy trình JIT.

---

## 2. CHỐT CHẶN 1 (GATE 1): KHÁM SƠ BỘ, XUẤT BÁO CÁO KHẢO SÁT & ĐỐI SOÁT VIEW_FILE

### Input:
- Đầu vào 1: Câu lệnh hoặc phản ánh hiện tượng từ người dùng — Vị trí: Context hội thoại.
- Đầu vào 2: Bộ công cụ khảo sát hiện trạng — Vị trí: [scripts/diagnose_all.ps1](scripts/diagnose_all.ps1).

### Process:
- Bước 1: Gọi `run_command` chạy `diagnose_all.ps1 -WorkspaceRoot <path> -UserPrompt <prompt>`.
- Bước 2: 🛑 **CHỐT CHẶN CƯỠNG BỨC ĐỌC LẠI 1:** BẮT BUỘC gọi `view_file` đọc lại tệp `HOSO_CSSK/BAO_CAO_KHAO_SAT.md` vừa sinh trên đĩa cứng. TUYỆT ĐỐI CẤM trả lời người dùng từ trí nhớ khi chưa gọi `view_file`.
- Bước 3: Xác định phân loại định tuyến được ghi nhận trong báo cáo khảo sát:
  - `[NHÁNH A] Yêu Cầu Xử Lý Mang Tính Lặp Lại Cơ Bản`: Người dùng yêu cầu dọn dẹp chung, bảo dưỡng định kỳ, làm nhẹ máy.
  - `[NHÁNH B] Yêu Cầu Xử Lý Vấn Đề Không Rõ Ràng / Sự Cố Đặc Thù`: Người dùng phản ánh giật lag Alt+Tab, lỗi font chữ, ứng dụng đơ khựng, phình đĩa C bất thường, xung đột tiến trình.
- Bước 4: Trả lời người dùng bằng ngôn ngữ đời thường, tóm tắt các chỉ số đo đạc thực tế và định hướng phương án xử lý tiếp theo.

### Output:
- **Nội dung:** Báo cáo hiện trạng kỹ thuật và phân loại định tuyến chính xác bài toán thuộc Nhánh A hay Nhánh B.
- **Hình thức:** File Markdown `BAO_CAO_KHAO_SAT.md` tại thư mục hồ sơ.
- **Vị trí:** `HOSO_CSSK/BAO_CAO_KHAO_SAT.md`.

---

## 3. CHỐT CHẶN 2 (GATE 2): ĐỐI SOÁT NGUYÊN NHÂN 2 CHIỀU, LẬP KẾ HOẠCH & CHỜ PHÊ DUYỆT

### Input:
- Đầu vào 1: Báo cáo khảo sát và phân loại bài toán từ Gate 1 — Vị trí: `HOSO_CSSK/BAO_CAO_KHAO_SAT.md`.
- Đầu vào 2: Bộ kịch bản kiểm tra sâu — Vị trí: `scripts/checks/`.
- Đầu vào 3: Động cơ khởi tạo hồ sơ theo dõi — Vị trí: [scripts/CSSK_LiveLogger.ps1](scripts/CSSK_LiveLogger.ps1).

### Process:
- Bước 1: Lựa chọn phương thức đối soát theo kết quả phân loại từ Gate 1:
  - **Nếu thuộc Nhánh A (Lặp lại cơ bản):** Đối soát nội tại các thông số kỹ thuật (RAM trống, tệp tạm, SSD) để chọn Gói tác vụ phù hợp (`FullCare`, `DevClean`, `DiskClean`, `AppSwitch`, `DBVacuum`).
  - **Nếu thuộc Nhánh B (Vấn đề không rõ ràng):** BẮT BUỘC kích hoạt cơ chế Đối Soát 2 Chiều:
    * **Chiều 1 (Nội tại & Log Agentic RAG):** Áp dụng Two-Tier Event RAG:
      - Quét nhanh Windows Event Log (Application / System) và WER Crash Dumps trong 24-48h gần nhất qua `Get-WinEvent` theo FilterHashtable để bóc tách Event ID lỗi (Event 1000 App Crash, 1001 WER, 41 Kernel-Power, 7036 Service Hang), Exception Code (`0xc0000005`), và Faulting Module (`.dll`).
      - Dùng `run_command` chạy các script kiểm tra sâu trong `scripts/checks/` hoặc đo đạc Registry, tiến trình sống trên máy.
    * **Chiều 2 (Bên ngoài & Root Cause Grounding):** BẮT BUỘC dùng `search_web` tra cứu chính xác mã Event ID + Faulting Module trên Microsoft Learn và tài liệu hỗ trợ kỹ thuật chính thức để xác định cơ chế gốc rễ (xung đột driver, hỏng registry, lỗi bộ nhớ) trước khi lập kế hoạch can thiệp.
- Bước 2: Viết script gọi `New-CSSKSession` trong `CSSK_LiveLogger.ps1` để in kết quả đối soát vào cặp hồ sơ:
  - File 1: `HOSO_CSSK/LATEST_CSSK.md` (Biên bản checklist kế hoạch ở trạng thái `[ ]`).
  - File 2: `HOSO_CSSK/NHAT_KY_TIEN_TRINH_MOI_NHAT.md` (Nhật ký tiến trình thời gian thực).
- Bước 3: 🛑 **CHỐT CHẶN CƯỠNG BỨC ĐỌC LẠI 2:** BẮT BUỘC gọi `view_file` đọc lại `HOSO_CSSK/LATEST_CSSK.md` trên đĩa cứng để kiểm tra tính toàn vẹn của danh mục checklist trước khi trình bày.
- Bước 4: Trình bày kế hoạch xử lý cho người dùng bằng ngôn ngữ đời thường, giải thích rõ nguyên nhân vì sao bị, dự kiến làm gì và cam kết an toàn.
- Bước 5: ⛔ **ĐIỂM DỪNG BÁO CÁO 2 (CHỜ PHÊ DUYỆT):** DỪNG LẠI TUYỆT ĐỐI. Không tự ý chạy bất kỳ lệnh can thiệp nào khi chưa có sự xác nhận đồng ý của người dùng.

### Output:
- **Nội dung:** Kế hoạch can thiệp chi tiết kèm danh mục checklist vi tác vụ và giải mã nguyên nhân 2 chiều.
- **Hình thức:** Cặp file Markdown `LATEST_CSSK.md` và `NHAT_KY_TIEN_TRINH_MOI_NHAT.md`.
- **Vị trí:** Thư mục `HOSO_CSSK/`.

---

## 4. CHỐT CHẶN 3 (GATE 3): KIỂM TRA PHÊ DUYỆT, THI CÔNG REALTIME & NGHIỆM THU NGẮT NHỊP

### Input:
- Đầu vào 1: Phản hồi đồng ý / điều chỉnh từ người dùng — Vị trí: Context hội thoại.
- Đầu vào 2: Hồ sơ checklist đã phê duyệt — Vị trí: `HOSO_CSSK/LATEST_CSSK.md`.
- Đầu vào 3: Động cơ điều phối thực thi — Vị trí: [scripts/execute_selected.ps1](scripts/execute_selected.ps1).

### Process:
- Bước 1: 🛑 **CHỐT CHẶN CƯỠNG BỨC ĐỌC LẠI 3A:** BẮT BUỘC gọi `view_file` đọc lại `HOSO_CSSK/LATEST_CSSK.md` để đối soát danh mục nhiệm vụ người dùng đã phê duyệt trước khi kích hoạt kịch bản.
- Bước 2: Gọi `run_command` chạy kịch bản thực thi (gọi `execute_selected.ps1` hoặc custom action). Trong quá trình chạy, hệ thống stream log thời gian thực từng giây vào File 2 và tự động tick trạng thái vi tác vụ vào File 1 (`[ ]` ➔ `[..]` ➔ `[x]`).
- Bước 3: 🛑 **CHỐT CHẶN CƯỠNG BỨC ĐỌC LẠI 3B:** Sau khi kịch bản chạy xong (ExitCode 0), BẮT BUỘC gọi `view_file` đọc lại cả hai tệp `HOSO_CSSK/NHAT_KY_TIEN_TRINH_MOI_NHAT.md` và `HOSO_CSSK/LATEST_CSSK.md` để nghiệm thu số liệu đo đạc Trước vs Sau. CẤM báo cáo kết quả từ suy đoán.
- Bước 4: Bàn giao kết quả cho người dùng bằng bảng đối chiếu định lượng (RAM giải phóng, ổ C trống thêm, phản hồi tiêu điểm, trạng thái dịch vụ) kèm link clickable tới hồ sơ kỹ thuật.

### Output:
- **Nội dung:** Biên bản nghiệm thu hoàn tất 100% checklist kèm nhật ký tiến trình đóng dấu thành công.
- **Hình thức:** Cặp file Markdown đã đóng dấu nghiệm thu và một dòng ghi sổ cái `HOSO_CSSK/CSSK_INDEX.md`.
- **Vị trí:** Thư mục `HOSO_CSSK/`.

---

## 5. CÁC GÓI BẢO DƯỠNG ĐỊNH SẴN & NGUYÊN TẮC AN TOÀN

### Danh Mục Gói Tác Vụ Định Sẵn:
- `FullCare`: Bảo dưỡng toàn diện định kỳ (10 phân hệ tiêu chuẩn: OS Temp, WinSxS, RAM, SQLite, SSD ReTrim, Spooler, Dev Caches, Recycle Bin, DNS, Docker).
- `DevClean`: Dọn dẹp chuyên sâu môi trường lập trình (Pip, Npm, pnpm, Docker caches, CrashDumps, Recycle Bin & Flush DNS).
- `DiskClean`: Dọn dẹp ổ đĩa chuyên sâu (tệp tạm, cập nhật cũ, dev caches, Recycle Bin, ReTrim SSD).
- `AppSwitch`: Tối ưu chuyển đổi cửa sổ Alt+Tab và thu hồi RAM nhàn rỗi.
- `DBVacuum`: Bảo trì và nén cơ sở dữ liệu SQLite nội bộ.

### Cam Kết An Toàn Bắt Buộc:
1. **System Restore Point:** Luôn tạo điểm khôi phục bảo hiểm hệ thống trước mọi can thiệp cấu hình.
2. **Nguyên Tắc Zero-Destruction:** Tuyệt đối không xóa file cá nhân hay mã nguồn dự án; file dọn dẹp hoặc phiên bản cũ phải chuyển vào `_Delete` hoặc `_Archive`.
3. **Module Tham Khảo JIT:** Khi cần xử lý sâu, tham khảo [resources/ref_01_vung_an_toan_va_xung_dot.md](resources/ref_01_vung_an_toan_va_xung_dot.md) và [resources/sop_01_go_phan_mem_tan_goc.md](resources/sop_01_go_phan_mem_tan_goc.md).
