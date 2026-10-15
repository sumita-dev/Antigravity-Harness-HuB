# Mẫu Chuẩn: Phiếu Khảo Sát & Báo Cáo Bảo Trì Hệ Thống Đạt Chuẩn

Tài liệu này mô tả mẫu giao tiếp và báo cáo kết quả hoàn chỉnh giữa AI Agent và người dùng, tuân thủ nguyên tắc: ngôn ngữ đời thường kết hợp kỹ thuật chính xác, minh bạch số liệu trước/sau và bảo toàn dữ liệu.

---

## 1. MẪU KHẢO SÁT SƠ BỘ & HƯỚNG DẪN DẪN ĐƯỜNG (ONBOARDING)

**Người dùng:** *"Dạo này máy tính của mình hơi chậm và quạt quay to, kiểm tra giúp mình nhé."*

**AI Agent phản hồi:**
> Chào bạn, tôi đã kiểm tra nhanh hệ thống máy tính của bạn trong 800ms. Dưới đây là hiện trạng kỹ thuật:
>
> 📌 **Tóm tắt hiện trạng:**
> - **Ổ đĩa hệ thống (C:):** Còn trống **477.6 GB (50.1%)** — Dung lượng rất an toàn. Tuy nhiên có **~379 MB tệp tạm và cache cập nhật cũ** có thể dọn dẹp.
> - **Bộ nhớ RAM:** Đang dùng **45% (14.6 GB / 31.8 GB)** — Có 18 tiến trình chạy ngầm nhàn rỗi có thể thu hồi bộ nhớ.
> - **Ổ cứng thể rắn NVMe SSD:** Trạng thái tốt, hỗ trợ ReTrim để phục hồi tốc độ ghi.
> - **Dịch vụ máy in (Print Spooler):** Sạch sẽ, không bị kẹt lệnh in.
>
> 🚀 **Phương thức thực hiện:**
> Tôi đã chuẩn bị sẵn lệnh tắt một chạm tại thư mục làm việc của bạn:
> - **Cách 1 (Ủy quyền):** Bạn chỉ cần nhắn *"Tiến hành"*, tôi sẽ tự động dọn dẹp ngầm và mở bảng theo dõi trực tiếp cho bạn.
> - **Cách 2 (Trực quan trên Terminal):** Bạn click vào tab `Terminal` bên dưới và gõ lệnh:
>   ```powershell
>   .\care
>   ```

---

## 2. MẪU BÁO CÁO NGHIỆM THU SAU BẢO TRÌ (POST-AUDIT)

```markdown
# BIÊN BẢN NGHIỆM THU BẢO DƯỠNG MÁY TÍNH
- **Thời gian hoàn tất:** 2026-09-16 16:48:39
- **Hồ sơ lưu trữ:** `HOSO_CSSK/2026-09/CSSK_TOI_UU_DINH_KY_20260916_164833.md`
- **Chế độ thi công:** Tự hành 90/10 (Đã tạo điểm khôi phục bảo vệ trước khi làm)

### KẾT QUẢ ĐO ĐẠC THỰC TẾ:
1. **Dung lượng ổ đĩa C:** Giải phóng thành công **378.96 MB** tệp rác và cache Windows Update cũ.
2. **Bộ nhớ RAM:** Thu hồi thành công vùng nhớ nhàn rỗi, đưa RAM trống về mức **17.19 GB** ổn định.
3. **Ổ cứng SSD NVMe:** Đã gửi tín hiệu ReTrim dọn ô nhớ rác tới Flash Controller thành công.
4. **Cơ sở dữ liệu SQLite:** 243/243 tệp dữ liệu đã được tối ưu hóa chỉ mục B-Tree và chống phân mảnh.
5. **An toàn hệ thống:** Điểm khôi phục `Antigravity_SafeCheck_Live` đã sẵn sàng; cờ WHQL Driver Signing giữ nguyên vẹn.
```
