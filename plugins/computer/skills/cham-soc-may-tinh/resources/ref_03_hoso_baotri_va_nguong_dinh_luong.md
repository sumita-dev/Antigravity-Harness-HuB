# Cẩm Nang: Quản Lý Hồ Sơ Bảo Trì, Ngưỡng Định Lượng & Từ Điển Non-Tech (Maintenance Records & Thresholds)

Tài liệu này quy chuẩn cấu trúc lưu trữ hồ sơ bảo trì dài hạn, xác lập bảng ngưỡng định lượng tài nguyên hệ thống và cung cấp từ điển chuyển đổi thuật ngữ kỹ thuật sang ngôn ngữ đời thường cho người dùng non-tech.

---

## 1. QUY CHUẨN QUẢN LÝ HỒ SƠ BẢO TRÌ DÀI HẠN (`HOSO_CSSK/`)

Toàn bộ quá trình kiểm tra, dọn dẹp và tối ưu hóa hệ thống được tự động lưu vết theo cấu trúc phân nhóm thời gian để người dùng dễ dàng theo dõi lịch sử và diễn biến hiệu năng và trạng thái phần cứng/phần mềm:

### Cấu Trúc Thư Mục
```text
HOSO_CSSK/
├── LATEST_CSSK.md                    # File con trỏ: Luôn phản ánh lần bảo trì mới nhất để mở xem trực tiếp
├── CSSK_INDEX.md                     # Bảng sổ cái tổng hợp: Tra cứu nhanh lịch sử bảo trì qua các năm
└── 2026-09/                          # Phân nhóm theo Năm-Tháng
    ├── CSSK_TOI_UU_DINH_KY_20260916_164833.md
    └── CSSK_KIEM_THU_AN_TOAN_20260916_164621.md
```

### Quy Tắc Đặt Tên Tệp
Cấu trúc: `CSSK_[LoaiHinh]_[YYYYMMDD_HHmmss].md`
- `[LoaiHinh]`:
  - `TOI_UU_DINH_KY`: Thi công dọn dẹp & tối ưu hóa thực tế.
  - `KIEM_THU_AN_TOAN`: Chạy chế độ kiểm thử (Dry-Run).
  - `KHAM_TONG_QUAT`: Báo cáo khảo sát toàn diện 10 phân hệ.
  - `CUU_HO_KHAN_CAP`: Xử lý sự cố kẹt in, giải phóng khẩn cấp ổ C bị đầy 100%.
- `[YYYYMMDD_HHmmss]`: Dấu thời gian tuyệt đối chống trùng lặp và hỗ trợ sắp xếp tự nhiên.

---

## 2. BẢNG NGƯỠNG ĐỊNH LƯỢNG TÀI NGUYÊN HỆ THỐNG

| Tài Nguyên | Chỉ Số Đo Đạc | Ngưỡng An Toàn (Bình thường) | Ngưỡng Cảnh Báo (Cần tối ưu) | Hành Động Can Thiệp |
| :--- | :--- | :--- | :--- | :--- |
| **Bộ nhớ RAM** | Dung lượng RAM khả dụng (Available Memory) | Trống > 25% tổng RAM | Trống < 15% tổng RAM | Thu hồi Working Set nhàn rỗi (`task_03_optimize_ram.ps1`). |
| **Phân vùng C:** | Tỷ lệ dung lượng đĩa trống | Trống > 20% dung lượng | Trống < 10% (hoặc < 25 GB) | Dọn tệp tạm, xóa bản cập nhật WinSxS cũ (`task_01`, `task_02`). |
| **SSD NVMe** | Trạng thái cờ TRIM OS | `DisableDeleteNotify = 0` (Active) | TRIM bị tắt hoặc chưa ReTrim > 30 ngày | Kích hoạt TRIM và gửi lệnh `Optimize-Volume -ReTrim` (`task_05`). |
| **Pin Laptop** | Tỷ lệ chai pin (Wear Level) | Độ chai < 20% | Độ chai > 35% | Cảnh báo người dùng cân nhắc bật chế độ bảo vệ pin (80% Battery Limit). |
| **Print Spooler** | Số lượng tệp kẹt trong hàng đợi | 0 tệp | Có >= 1 tệp kẹt quá 24h | Dừng dịch vụ, xóa tệp `.SPL`/`.SHD` kẹt và bật lại spooler (`task_06`). |
| **Cơ sở dữ liệu SQLite** | Số trang trống (Free Pages) nội bộ | < 5% dung lượng file | > 20% dung lượng file | Thực thi lệnh `PRAGMA vacuum` và `REINDEX` (`task_04`). |

---

## 3. BỘ TỪ ĐIỂN CHUYỂN ĐỔI THUẬT NGỮ CHO NGƯỜI NON-TECH

Khi giải thích hoặc trình bày báo cáo cho người dùng không rành kỹ thuật, Agent bắt buộc dùng ngôn ngữ phổ quát, dễ hiểu, kết hợp thuật ngữ chuẩn mực:

| Thuật Ngữ Kỹ Thuật Khô Khan | Ngôn Ngữ Đời Thường Dễ Hiểu | Ví Dụ Minh Họa Trong Giao Tiếp |
| :--- | :--- | :--- |
| **Memory Working Set Trim** | Thu hồi bộ nhớ RAM tạm thời không dùng | *"Hệ thống đã thu hồi lại bộ nhớ RAM nhàn rỗi, giúp máy chạy nhẹ nhàng hơn."* |
| **WinSxS Component Cleanup** | Dọn dẹp các bản cập nhật Windows cũ | *"Đã gỡ bỏ các bản vá cũ của Windows Update, giải phóng dung lượng vĩnh viễn cho ổ C."* |
| **NVMe SSD ReTrim** | Làm mới và phục hồi tốc độ ghi ổ cứng thể rắn | *"Đã kích hoạt tính năng dọn ô nhớ rác trên ổ cứng SSD, giúp duy trì tốc độ đọc ghi nhanh nhất."* |
| **SQLite Vacuum & Reindex** | Chống phân mảnh và sắp xếp lại chỉ mục dữ liệu | *"Đã dọn dẹp và sắp xếp lại 243 tệp dữ liệu nội bộ, giúp việc tìm kiếm dữ liệu diễn ra tức thì."* |
| **Print Spooler Stuck Queue** | Xóa lệnh in bị nghẽn trong máy in | *"Đã thông tắc hàng đợi máy in, ngăn chặn tiến trình in chạy ngầm gây nóng máy."* |
| **UAC Elevation Required** | Yêu cầu quyền quản trị viên cao nhất | *"Tác vụ này cần quyền Administrator để đảm bảo an toàn cho tệp hệ thống."* |
