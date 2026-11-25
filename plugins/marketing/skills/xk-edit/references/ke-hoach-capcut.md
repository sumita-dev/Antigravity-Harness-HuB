# Mẫu kế hoạch edit cho CapCut (chế độ 2)

Viết cho người mới chưa từng mở CapCut, mỗi bước một dòng. **Tên nút có thể khác theo bản CapCut**, nên ghi kèm vị trí ("thanh công cụ dưới đáy", "chạm vào clip rồi xem hàng nút hiện ra"). Con số theo Bảng số chuẩn ở đầu `luat-edit-chung.md`.

## Hỏi trước khi viết kế hoạch
1. Danh sách clip: tên file, mỗi clip dài bao nhiêu giây, 1 ảnh chụp mỗi clip, lời bạn nói trong clip (gõ lại, kèm khoảng giây nếu nhớ). Vd "IMG_0123, 25 giây, cảnh pha trà, không nói".
2. Bạn dùng CapCut trên **điện thoại** hay **máy tính**? (vị trí nút khác nhau)

**Chưa xem được clip thì không ghi số giây.** Ghi bằng mô tả: "đoạn tay đặt ấm xuống, khoảng 2 giây", "từ lúc bạn nói «hôm nay…» đến hết câu". Chỉ ghi giây khi mình đã xem được clip hoặc bạn đã báo giây.

```markdown
# Kế hoạch edit: <tên video> (<kiểu A–G>, nhóm <A–D>)
Độ dài đích: <x> giây · Tỷ lệ 9:16 · Xuất 1080p, 30 khung hình/giây · CapCut trên <điện thoại / máy tính>
(Tên nút có thể khác theo bản CapCut của bạn, mình mô tả kèm vị trí.)

## 0. Lệnh bạn nói trong video
| Khoảng giây bạn báo | Bạn dặn | Mình hiểu là | Đã đưa vào bước |
|---|---|---|---|
| khoảng 0:40 | "Claude ơi cắt đoạn vừa rồi" | Bỏ lần nói vấp ngay trước câu dặn | Bảng 1, cảnh 6 |
| … | | | |
Nhớ cắt luôn các câu dặn này khỏi video (và xóa khỏi phụ đề).

## 1. Thứ tự cảnh
| # | File | Lấy đoạn nào (mô tả, khoảng bao lâu) | Ghi chú |
|---|---|---|---|
| 1 | IMG_0123 | Đoạn tay đặt ấm xuống, khoảng 2 giây | Cảnh mạnh nhất, để mở đầu |
| … | | | |

## 2. Chữ trên màn hình
| Trên cảnh # | Loại | Nội dung | Vị trí | Bao lâu / kiểu |
|---|---|---|---|---|
| 1–2 | Tiêu đề | "<dòng 1> / <dòng 2>" | trên giữa, trong vùng an toàn | 3–5 giây (video nói: tối đa 10); theo kênh hình mẫu, tô màu "<từ khóa>" |
| 3 | Mốc giờ | "21:05" | giữa | to, đủ lâu đọc 2 lần |
| … | Phụ đề | lời bạn nói, sửa các chữ: … | khoảng 2/3 – 3/4 chiều cao | 1 dòng 3–8 chữ |

## 3. Âm thanh
- Nhạc: <gợi ý 2–3 kiểu / tên trong thư viện CapCut>, âm lượng <x>%, bắt đầu từ đoạn beat (đoạn nhạc có nhịp rõ).
- Tiếng gốc: giữ ở cảnh <…>, âm lượng <x>%. Tiếng đẹp (xèo, rót) thì hạ nhạc 1–2 giây.
- Tắt nhạc ở cảnh <…> (cảnh có người khác nói).
- Cuối: bật "Chuẩn hóa âm lượng".

## 4. Che thông tin
- Cảnh <#>: che <phiếu / màn hình / biển số / mặt người không đồng ý>.

## 5. Các bước trong CapCut
1. Dự án mới → chọn các clip theo thứ tự bảng 1 → Thêm.
2. **Tỷ lệ 9:16:** nút "Tỷ lệ" ở thanh công cụ dưới đáy (máy tính: góc trên khung xem) → 9:16.
3. **Clip quay ngang:** chạm clip → "Nền" / "Canvas" → chọn "Làm mờ" để hai bên không bị đen.
4. Cắt từng clip theo mô tả bảng 1: kéo thanh trắng đến đúng lúc động tác bắt đầu → chạm clip → "Tách" → xóa phần thừa.
5. **Vlog không lời, cắt theo nhịp:** chạm nhạc → "Nhịp" / "Beat" → bật tự đánh dấu, kéo mép mỗi cảnh khớp dấu (mỗi cảnh 2–4 dấu).
6. **Giảm tiếng ồn** (chỗ có quạt, xe, gió): chạm clip → "Giảm tiếng ồn", nếu bản của bạn có.
7. Văn bản → Thêm văn bản → gõ tiêu đề; Font: gõ tên vào ô tìm, chọn dòng không có biểu tượng tím. Mặc định tiêu đề **Montserrat-ExtraBold**, phụ đề **Roboto-Blk**; muốn khác thì xem bảng font ở mục 1.2 của `luat-edit-chung.md`, tránh Bebas Neue, Poppins, Rubik vì thiếu dấu. Màu, viền theo kênh hình mẫu; kéo dài theo bảng 2.
8. **Phụ đề:** Văn bản → "Phụ đề tự động" nếu bản của bạn có (có thể cần trả phí) → đọc lại, sửa các chữ ở mục 2. Không có thì gõ tay từng câu theo lời bạn nói.
9. Âm thanh → chọn nhạc; chạm nhạc → Âm lượng <x>.
10. **Che thông tin** (mục 4): Hiệu ứng → "Khảm" / "Làm mờ" đặt lên chỗ cần che, hoặc dán nhãn dán (sticker) lên trên; kéo dài đúng cảnh đó.
11. Xem lại toàn bộ 1 lần có tiếng, 1 lần tắt tiếng.
12. **Xuất:** nút xuất ở góc trên phải → độ phân giải 1080p, tốc độ khung hình 30.
13. **Bản không nhạc:** tắt tiếng kênh nhạc (chạm nhạc → Âm lượng 0, hoặc nút loa ở đầu kênh nhạc) → xuất thêm 1 bản, để thêm nhạc trong app TikTok nếu nhạc bị tắt tiếng.

## 6. Tự kiểm
- [ ] Đã làm hết lệnh bạn nói trong video, không còn câu dặn nào lọt tiếng / phụ đề
- [ ] 2 giây đầu là cảnh mạnh nhất
- [ ] Chữ đọc kịp, không đè chữ, nằm trong vùng an toàn
- [ ] Không có cảnh không lời quá 5 giây mà không có gì mới
- [ ] Tắt tiếng vẫn hiểu
- [ ] Đã che thông tin cá nhân
```
