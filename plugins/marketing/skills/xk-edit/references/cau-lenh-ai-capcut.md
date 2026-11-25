# Câu lệnh cho AI trong CapCut tự edit (chế độ 3)

Dành cho người **chỉ dùng chat Claude** (claude.ai trên web hoặc điện thoại). Mình không mở được CapCut của bạn, nên mình viết sẵn từng câu lệnh. Bạn chép dán vào ô chat AI trong CapCut, AI đó tự cắt, chỉnh tốc độ, thêm chữ. Vài việc AI CapCut làm hỏng thì bạn tự làm tay theo hướng dẫn bên dưới.

## Ô chat AI nằm ở đâu
- **CapCut máy tính:**
  - Mở dự án, góc dưới bên phải có nút **EditPilot**. Bấm vào thì hiện ô chat, trong ô ghi "Describe your edits, or @ clips…".
  - Ở trang chủ còn có ô **AI edit**.
- **CapCut điện thoại:** tên và chỗ có thể khác, hoặc chưa có. Không thấy ô chat AI thì dùng kế hoạch edit tay (chế độ 2).
- Đây là tính năng thử nghiệm (Beta). **Mỗi câu lệnh trừ điểm** (bản miễn phí có ít điểm). Tên nút có thể đổi theo bản CapCut.

## Đã chạy thử thật (11/2026): việc nào giao AI, việc nào tự làm
| Việc | AI CapCut | Cách làm |
|---|---|---|
| Cắt một clip, giữ từ giây A đến giây B | ✅ đúng | Giao AI |
| Tách một clip dài thành nhiều đoạn, xếp theo thứ tự mình đưa | ✅ đúng | Giao AI, tối đa 6 đoạn mỗi câu |
| Tăng tốc "4 lần", hoặc "tăng tốc để còn đúng 5 giây" | ✅ đúng | Giao AI |
| Chuyển một đoạn lên đầu, nối liền không khoảng trống | ✅ đúng | Giao AI |
| Nhạc đã có trên timeline: cắt bằng video, chỉnh âm lượng, tắt dần, tắt tiếng clip | ✅ đúng | Giao AI |
| Thêm chữ: nội dung, giây hiện, màu, vị trí | ✅ gần đúng | Giao AI, rồi tự kiểm vị trí |
| **Thêm file nhạc của bạn** | ❌ lấy bài khác trong thư viện mà vẫn báo là đã làm | **Tự kéo** file nhạc từ mục Media xuống timeline |
| **Đánh dấu nhịp, khớp cảnh theo nhịp** | ❌ tự báo không làm được, còn làm hỏng cả timeline (cảnh co còn 1 khung hình) | **Không bao giờ giao.** Tự làm: chạm nhạc → "Nhịp / Beat", rồi kéo mép cảnh |
| **Font chữ** | ❌ chọn font thiếu dấu tiếng Việt; gọi tên font cũng gắn sai, chữ tràn khung | **Tự chọn font**: Montserrat-ExtraBold (tiêu đề), Roboto-Blk (phụ đề), có sẵn trong CapCut |

**AI CapCut có thể báo "đã hoàn thành" dù làm sai.** Sau mỗi câu lệnh luôn nhìn timeline và phát thử 1 lần.

## Hỏi trước khi viết câu lệnh
1. Danh sách clip theo thứ tự quay. Mỗi clip ghi: tên file, dài bao lâu, quay cảnh gì.
2. Mỗi cảnh muốn lấy **từ giây nào đến giây nào**. Cách xem giây trong CapCut: kéo thanh trắng trên timeline, số giây hiện dưới khung xem.
   - AI CapCut cắt chính xác khi có số giây.
   - Bạn chưa xem được thì mô tả ("lúc tay đặt ấm xuống"). Khi đó mình viết thêm bước "bạn kéo thanh trắng tìm đúng lúc đó, báo mình số giây", rồi mới viết câu cắt.
3. Lời bạn nói trong video (nếu có), để soát phụ đề.
4. Nhạc: file bạn đã tải về, hoặc bài chọn trong thư viện CapCut. Bạn tự đưa bài nhạc xuống timeline.

## Luật viết câu lệnh
- **Mỗi câu lệnh một việc.** Dán một câu, chờ AI làm xong (dòng "All tasks done"), xem lại rồi mới dán câu tiếp theo.
- **Gọi clip bằng tên file đầy đủ** như CapCut hiện trên timeline (vd 20261122_123846). Không gõ đuôi .mp4 cũng được. Gõ **@** để chọn clip từ danh sách cũng được.
- **Ghi số cụ thể**: giây, tốc độ, âm lượng %, màu mã #, vị trí theo pixel trên khung 1080x1920. Không ghi "cho đẹp", "cho hay".
- **Câu nào có clip video nằm sẵn trên timeline thì thêm:** "Không di chuyển, không đổi độ dài, không đổi thứ tự các clip video." Câu thêm nhạc, chữ mà thiếu dòng này thì AI hay xếp lại cảnh.
- **Cuối mỗi câu lệnh luôn dán dòng giữ an toàn:**
  > Chỉ làm đúng việc này, không đổi phần khác. Không thêm bài nhạc khác. Không tạo hình ảnh, giọng nói hay người bằng AI. Không thêm chuyển cảnh, bộ lọc, hiệu ứng, nhãn dán.
- **Không bao giờ viết** "khớp nhịp", "theo beat", "chọn font", "chọn nhạc". Ba việc này bạn tự làm.
- **AI làm sai:** bấm **Ctrl+Z** (điện thoại: nút hoàn tác ↶) từng lần, sau mỗi lần nhìn lại timeline. Một câu lệnh có thể gồm nhiều bước nên có khi phải bấm 2–3 lần. AI tự thêm thứ không muốn thì chạm vào nó trên timeline, bấm Xóa.
- Con số theo Bảng số chuẩn ở đầu `luat-edit-chung.md`:
  - **vị trí chữ:** tiêu đề cách mép trên khoảng **300 px**; chữ chạy ở khoảng **1250 px** từ trên xuống; cách hai mép trái phải ít nhất 60 px (bên phải 160 px);
  - tiêu đề giữ 3–5 giây;
  - phụ đề mỗi dòng 3–8 chữ;
  - cảnh không lời không quá 5 giây.

## Thứ tự làm (mẫu)
Mình viết cho bạn đủ các bước dưới đây, thay số và chữ theo video của bạn. Bước có chữ **[AI]** là câu dán vào ô chat; **[Tay]** là bạn tự bấm.

1. **[Tay] Tạo dự án:** dự án mới → nhập hết clip → kéo xuống timeline theo thứ tự quay. Tỷ lệ 9:16: nút "Tỷ lệ" (máy tính: dưới khung xem).
2. **[AI] Cắt từng clip** (một câu cho mỗi clip; clip cần nhiều đoạn thì liệt kê đủ trong một câu)
   > Clip 20261122_123710: chỉ giữ 2 đoạn, từ giây 0 đến 1,3 và từ giây 11,3 đến 12,9, xóa phần còn lại. Giữ tốc độ gốc. + dòng giữ an toàn
3. **[AI] Tốc độ**
   > Clip 20261122_123846: chỉ giữ từ giây 1,5 đến 11,5, rồi tăng tốc đoạn đó lên 4 lần. + dòng giữ an toàn
   >
   > Clip dji_…: đoạn từ giây 22 đến 210 tăng tốc để chỉ còn đúng 5 giây. + dòng giữ an toàn
4. **[AI] Thứ tự**
   > Chuyển đoạn của clip 20261122_123846 lên đầu timeline, các đoạn khác giữ nguyên thứ tự và nối liền nhau, không có khoảng trống. + dòng giữ an toàn
5. **[Tay] Nhạc:**
   - kéo file nhạc (hoặc bài chọn trong Âm thanh) xuống dưới các clip, đầu bài trùng giây 0;
   - vlog không lời muốn cắt theo nhịp: chạm nhạc → "Nhịp / Beat" → bật đánh dấu, rồi kéo mép từng cảnh khớp dấu (mỗi cảnh 2–4 dấu). Ngại thì bỏ qua bước khớp nhịp, video vẫn ổn.
6. **[AI] Chỉnh nhạc đã có**
   > Bản nhạc <tên> đang có trên timeline: cắt bỏ phần thừa sau khi video kết thúc, đặt âm lượng 45%, tắt dần 1,5 giây cuối. Tắt tiếng gốc (âm lượng 0) của mọi clip video. Không di chuyển, không đổi độ dài, không đổi thứ tự các clip video. + dòng giữ an toàn
   - Video có lời nói thì thay bằng: nhạc 10–15%, giữ tiếng nói gốc 100%, giảm tiếng ồn cho tiếng nói.
7. **[AI] Chữ** (một câu cho tiêu đề, một câu cho mỗi 3–4 dòng chữ chạy)
   > Thêm chữ tiêu đề 2 dòng: dòng 1 "<…>", dòng 2 "<…>", hiện từ giây 0 đến giây 3. Chữ trắng viền đen, riêng dòng 2 màu #19D3C5. Đặt giữa theo chiều ngang, tâm chữ cách mép trên khoảng 300 px trên khung 1920. Chữ nằm gọn trong khung, cách hai mép ít nhất 60 px, tràn thì thu nhỏ cỡ chữ. Không di chuyển, không đổi độ dài, không đổi thứ tự các clip video. + dòng giữ an toàn
8. **[Tay] Font và hiệu ứng chữ:**
   - chạm từng chữ → Văn bản → Font → gõ tên vào ô tìm → chọn dòng không có biểu tượng tím. Mặc định: tiêu đề và chữ chạy **Montserrat-ExtraBold**, phụ đề **Roboto-Blk**. Font khác xem bảng font trong mục 1.2 của `luat-edit-chung.md`. Tránh Bebas Neue, Poppins, Rubik vì thiếu dấu;
   - Viền / Nét (Stroke): đen, dày;
   - muốn chữ hiện dần: Hoạt ảnh → Vào → "Đánh chữ".
9. **[AI] Phụ đề** (video có nói)
   > Tạo phụ đề tự động tiếng Việt. Mỗi dòng tối đa 8 chữ, chữ trắng viền đen, đặt ở khoảng 1250 px từ trên xuống, không đè tiêu đề. + dòng giữ an toàn
   - Sau đó bạn tự đọc lại từng dòng phụ đề, sửa chữ sai; đổi font như bước 8.
10. **[AI] Che thông tin**
    > Ở đoạn từ giây <A> đến <B>, làm mờ vùng <biển số / màn hình điện thoại / giấy tờ>. + dòng giữ an toàn
    - Tự xem lại: chỗ che có bám đúng suốt đoạn không.
11. **[Tay] Kiểm cuối:** phát cả video 1 lần có tiếng, 1 lần tắt tiếng. Đối chiếu bảng dàn dựng mình gửi.
12. **[Tay] Xuất:** nút Xuất (Export) góc trên phải → 1080p, 30 khung hình/giây.

## Khi giao cho người dùng
- Gửi **bảng dàn dựng** (cảnh, giây, chữ, nhạc) trước để bạn duyệt. Duyệt xong mới gửi các bước.
- Mỗi câu [AI] để trong một khung riêng, đã ghép sẵn dòng giữ an toàn, để bạn bấm chép nguyên câu.
- Dặn 4 điều:
  - dán từng câu, xem xong mới dán câu tiếp;
  - AI báo xong chưa chắc đã đúng, luôn nhìn lại timeline;
  - sai thì hoàn tác rồi dán lại;
  - mỗi câu trừ điểm, nên dán đúng câu đã viết, đừng hỏi AI CapCut những câu thừa.
- Sau khi làm xong, nhờ bạn chụp màn hình timeline và 2–3 khung hình có chữ gửi lại. Mình soát theo mục Tự kiểm của `ke-hoach-capcut.md`.

## Ví dụ: video hậu trường phòng live (vlog không lời, 34 giây)
Đã chạy thử nguyên bộ này. Các câu cắt, tốc độ, thứ tự đều đúng ngay lần đầu.
1. [Tay] Kéo 5 clip xuống timeline theo thứ tự quay.
2. [AI]
   > Clip 20261122_123846: chỉ giữ từ giây 1,5 đến giây 11,5, xóa phần còn lại của clip này, rồi tăng tốc độ đoạn đó lên 4 lần. + dòng giữ an toàn
3. [AI]
   > Clip 20261122_123710: chỉ giữ 2 đoạn, từ giây 0 đến 1,3 và từ giây 11,3 đến 12,9. Clip 20261122_123833: chỉ giữ từ giây 0,8 đến 2,7. Giữ tốc độ gốc. + dòng giữ an toàn
4. [AI]
   > Clip 20261122_123933: chỉ giữ 6 đoạn sau và xếp liền nhau đúng thứ tự này: (1) giây 17,5 đến 20,0; (2) 21,6 đến 23,6; (3) 32,7 đến 35,8; (4) 70,5 đến 73,0; (5) 88,5 đến 90,5; (6) 65,0 đến 67,5. Giữ tốc độ gốc. + dòng giữ an toàn
5. [AI]
   > Clip dji_…: chỉ giữ 3 đoạn theo thứ tự: (1) giây 5 đến 9, tốc độ gốc; (2) giây 22 đến 210, tăng tốc để đoạn này chỉ còn đúng 5 giây; (3) giây 217 đến 221, tốc độ gốc. + dòng giữ an toàn
6. [AI]
   > Chuyển đoạn của clip 20261122_123846 (đoạn đã tăng tốc 4 lần) lên đầu timeline, các đoạn khác giữ nguyên thứ tự và nối liền nhau, không có khoảng trống. + dòng giữ an toàn
7. [Tay] Kéo file nhạc xuống timeline. Tùy chọn: khớp nhịp bằng tay.
8. [AI] Chỉnh nhạc (bước 6 mẫu) → [AI] tiêu đề, chữ mốc giờ (bước 7 mẫu) → [Tay] font, viền, "Đánh chữ" → [Tay] xem lại, xuất.
