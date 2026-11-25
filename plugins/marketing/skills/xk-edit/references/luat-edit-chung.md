# Luật edit chung cho mọi video

## Bảng số chuẩn (mọi file khác theo bảng này)
| Mục | Con số |
|---|---|
| Tiêu đề hiện bao lâu | 3–5 giây với video không lời / vlog; tối đa 10 giây với video nói |
| Tiêu đề dài bao nhiêu | 2–3 dòng, mỗi dòng ≤ 6–8 chữ |
| Phụ đề | 1 dòng 3–8 chữ; mỗi dòng hiện ≥ 0,8 giây; khoảng ≤ 15 ký tự/giây |
| Chữ chú thích | hiện đủ lâu để đọc 2 lần |
| Độ dài cảnh | cảnh không lời ≤ 5 giây (cảnh chuẩn bị 0,5–1 giây); cảnh có lời dài theo câu nói; chuỗi hành động 5–6 giây; ngoại lệ: khoảnh khắc 1 cảnh liền của nhóm gia đình |
| Vùng an toàn (khung 1080x1920) | cách mép trên 220 px, cách đáy ≥ 480 px (đăng cả Facebook Reels: ≥ 520 px), lề trái 60 px, lề phải 160 px |
| Âm lượng | khoảng -14 LUFS (độ to chuẩn chung của cả video), đây là mức tham khảo; đỉnh ≤ -1 dB |

## 1.0. Lệnh nói trong video: ưu tiên số 1
Người quay thường **nói luôn trong lúc quay để dặn Claude**: "Claude ơi cắt đoạn vừa rồi", "lấy lần nói này", "chỗ này chèn chữ 5 giờ sáng", "đoạn này cho chạy nhanh", "cái này để mở đầu", "che biển số đi". Đây là ý muốn của chủ kênh, **đứng trên mọi luật và khuôn mẫu khác** (trừ luật an toàn 1.4).

1. **Đọc lời nói trước tiên, lọc ra mọi câu là lệnh** (gọi Claude, "cắt", "bỏ", "giữ", "lấy lần này", "chèn chữ", "để ở đầu / cuối", "nhanh lên", "chậm lại", "zoom", "che", "thêm nhạc", "dừng ở đây"…). Lệnh không có câu gọi cũng tính, miễn rõ là nói với người edit chứ không nói với người xem.
2. **Lập bảng lệnh** trước khi dựng: giây nói lệnh → lệnh hiểu là gì → áp vào đoạn nào (thường là đoạn ngay trước hoặc ngay sau câu lệnh) → làm thế nào. Lệnh mơ hồ ("chỗ này làm đẹp chút") thì đề xuất cách hiểu cụ thể và hỏi lại trong cùng lượt duyệt.
3. **Làm đúng lệnh.** Lệnh trái khuôn nhóm (vd muốn giữ cảnh 10 giây) thì vẫn làm theo, chỉ ghi chú 1 dòng gợi ý nếu thấy ảnh hưởng nhịp. Lệnh trái luật an toàn (lộ địa chỉ nhà, mặt trẻ em ở cảnh tắm…) thì không làm và nói lý do.
4. **Cắt sạch câu lệnh khỏi bản cuối:** không để lọt tiếng, không để lọt vào phụ đề, kể cả chữ "Claude ơi" lửng ở đầu hoặc cuối đoạn.
5. **Báo lại** trong phần giao: danh sách lệnh đã làm, lệnh nào hiểu khác hoặc chưa làm và vì sao.

**Nghe lời nói ở đâu:** Claude không tự nghe chính xác giọng tiếng Việt ở mọi môi trường. Thứ tự ưu tiên:
- công cụ nhận giọng có sẵn trong môi trường đang chạy (nếu có), rồi đối chiếu lại với lời người dùng gửi;
- lời người dùng gõ lại, hoặc phụ đề tự động CapCut họ xuất ra / chụp màn hình;
- không có cả hai thì hỏi: "Trong video bạn có dặn mình chỉnh gì không? Gõ lại giúp mình các câu dặn, kèm khoảng giây."

## 1.1. Tiếng: không bị ngắt, không bị hụt chữ
- **Phụ đề theo lời người nói, không theo kịch bản.** Kịch bản chỉ để soát chính tả, tên riêng, con số.
- **Giọng địa phương, lời gõ không dấu:** giữ nguyên từ địa phương (răng, rứa, mô…), tự thêm dấu theo ngữ cảnh, chỉ hỏi lại chữ mình không chắc.
- **Nói lại hoặc vấp thì giữ lần trọn ý nhất**, thường là lần cuối. Câu nói dở thì cắt. Hai câu trùng ý thì giữ câu sau.
- **Không ăn chữ đầu, chữ cuối** ("hòa vốn" thành "hòa"). Cắt theo âm lượng thật. Cắt xong nghe lại từng chỗ nối.
- **Cắt hết khoảng lấy hơi** (0,4–0,6 giây). Nhịp nối cho video nói:
  - trong một câu: gần như liền (khoảng 0,03 giây);
  - giữa hai câu: khoảng 0,07 giây;
  - trước mục mới ("Thứ hai", ví dụ mới): khoảng 0,2 giây;
  - không chỗ nối nào quá 0,25 giây.
- **Video tâm sự, chuyện phiếm:** để nhịp tự nhiên, chỗ ngừng dưới 0,6 giây giữ nguyên.
- **Video bán hàng:** không có khoảng chờ, đoạn chốt nói liền.
- **Bỏ chữ đệm** "ok", "rồi", "ừm". Câu dặn người edit thì làm theo mục 1.0 rồi cắt bỏ.
- **Âm lượng:**
  - cả video khoảng -14 LUFS (mức tham khảo; trong CapCut: chuẩn hóa âm lượng), đỉnh không vượt -1 dB;
  - giọng phải to rõ; giọng quá nhỏ thì người xem lướt và phụ đề tự động cũng sai;
  - nhạc nền nhỏ dưới giọng, nghe thấy nhưng không lấn;
  - video không lời thì nhạc là chính, tiếng tại chỗ (xèo xèo, rót nước, mở hộp) để nhỏ làm nền;
  - tiếng tại chỗ đẹp (xèo, rót, cắt giòn) thì hạ nhạc xuống 1–2 giây cho tiếng đó nổi lên;
  - chỗ ồn (quạt, xe, gió) thì giảm ồn nhẹ (CapCut: chạm clip → Giảm tiếng ồn, nếu bản của bạn có), nghe lại không để giọng méo;
  - đến cảnh chèn có người khác nói thì tắt nhạc nền;
  - kiểm không có đoạn lặng dài bất thường trước khi xuất.

## 1.2. Chữ trên màn hình: đọc kịp, không đè nhau
- **Kiểu chữ (font, màu, viền) không cố định.** Học theo kênh hình mẫu của bạn. Luật dưới đây là luật đọc dễ, áp cho mọi kiểu chữ.
- **Font có sẵn trong CapCut, đã thử đủ dấu tiếng Việt (11/2026).** Không cần cài thêm font. Tìm theo tên trong Văn bản → Font, chọn dòng **không có biểu tượng tím** (biểu tượng tím là bản trả phí).

  | Dùng cho | Font đề xuất | Cảm giác |
  |---|---|---|
  | Tiêu đề, chữ chạy (mặc định) | **Montserrat-ExtraBold** | Đậm, rõ, hợp mọi nhóm |
  | Tiêu đề dài, cần nhiều chữ một dòng | **Anton** hoặc **Oswald-Bold** | Chữ cao, hẹp, mạnh |
  | Phụ đề | **Roboto-Blk** hoặc **Inter-Blk** | Dày, dễ đọc khi chạy nhanh |
  | Kênh gia đình, mẹ bỉm, quán dễ thương | **Nunito** | Tròn, mềm |
  | Tiêu đề kiểu áp phích, vui | **Lalezar** | Béo, nổi |

  - **Tránh:** Bebas Neue, Poppins, Rubik, DM Sans. Các font này thiếu dấu tiếng Việt nên CapCut tự thay một phần hoặc cả câu bằng font khác, chữ lệch kiểu, mảnh đi.
  - **Thử font mới:** gõ "Ậ Ư Ờ Ễ Ỹ ặ ữ ộ", chờ font tải xong (vài giây) rồi nhìn kỹ. Mọi chữ phải cùng độ đậm, cùng kiểu thì mới dùng.
  - Một video chỉ dùng 1–2 font. Ví dụ tiêu đề Montserrat-ExtraBold, phụ đề Roboto-Blk.
- **Phụ đề** (khi có lời nói):
  - 1 dòng 3–8 chữ, có viền hoặc nền để nổi trên mọi cảnh;
  - đặt ở khoảng 2/3 – 3/4 chiều cao, dưới tay làm việc, trên vùng nút bấm;
  - mỗi dòng hiện ít nhất 0,8 giây, khoảng ≤ 15 ký tự/giây; không để dòng chỉ còn 1–2 chữ, không ngắt vắt qua dấu chấm, không kết dòng bằng chữ nối (cái, là, thì, không…);
  - phụ đề tự động **phải đọc lại sửa lỗi** (chữ tách đôi, sai tên riêng).
- **Tiêu đề / câu móc:**
  - chỉ hiện ở đầu video: 3–5 giây với video không lời / vlog, tối đa 10 giây với video nói; không giữ suốt video;
  - 2–3 dòng, mỗi dòng không quá 6–8 chữ, có ít nhất 1 con số thật (tuổi, giờ, giá, ngày thứ mấy);
  - tô màu 1–2 từ khóa;
  - dài thì xuống dòng, không thu nhỏ chữ;
  - người dùng chưa có tiêu đề thì gợi ý 3–5 phương án, **luôn có ít nhất 1 phương án góc độ hiếm**: cánh cửa người ngoài không thấy ("hậu trường", "bếp sau", "bên trong") + điều đặc biệt chỉ họ có + con số thật làm tương phản. Vd "HẬU TRƯỜNG 1 MÌNH 1 PHÒNG / LIVE HƠN 5000 NGƯỜI XEM". Cách ghép và câu hỏi tìm độ hiếm ở `mo-dau.md`. Số liệu kênh trong tiêu đề (view, người xem, follow) phải có ảnh chụp làm bằng chứng chèn vào video.
- **Tra xu hướng trước khi viết chữ** (tiêu đề, chữ chạy, chữ chú thích): không chỉ lấy câu mẫu trong bộ skill. Tìm trên TikTok 5–10 video **cùng dạng, đăng trong 1–2 tháng gần đây, nhiều tim nhất** (từ khóa theo việc của bạn, vd "trước giờ lên live", "một ngày làm việc pov", "hậu trường một mình"). Xem đầu – giữa – cuối mỗi video, ghi 4 điều: câu mở viết thế nào, chữ giữa video kiểu gì (mốc giờ, nhãn bước, lời tự nói), giọng (xưng hô, dài ngắn), câu kết. Học **cách nói**, không chép nguyên câu; mọi giờ, số, sự việc phải là của bạn. Chỉ làm khi mình có công cụ xem web; không có thì dùng mục "Kiểu đang hot" ngay dưới và trong `mo-dau.md`, bạn muốn thì gửi ảnh chụp video bạn thích (không xin link, không bắt bạn đi tìm). Khi đưa chữ cho bạn duyệt, ghi kèm 1 dòng "học từ kiểu: …".
  - Kiểu đang hot (11/2026, kiểm lại mỗi 1–2 tháng) cho video hậu trường không lời: **mốc giờ thật + việc 2–4 chữ** ("17:30 Nấu nước lèo", "21:30 Làm video"); câu mở có **mốc đếm ngược** ("15 phút trước giờ lên sóng") hoặc **tuổi/nghề + con số** ("26 tuổi chạy xe, 14 tiếng một ngày"); câu kết là một câu thật lòng ngắn, không khẩu hiệu.
- **Chữ chú thích** (thay lời kể khi không nói): mốc giờ to ("5:03", "21h") + 1 dòng 5–10 chữ; nhãn 2–5 chữ cạnh đồ vật (tên món, định lượng, giá, kích thước). Hiện đủ lâu để đọc 2 lần. Nhãn thông tin có thể **cộng dồn** thành danh sách trên đầu để người xem chụp lại.
- **Từ khóa tìm kiếm:** chọn 1 cụm người ta hay gõ tìm (vd "cơm hộp đi làm"), cho cụm đó có trong lời nói, trong chữ vài giây đầu và ở đầu mô tả.
- **Series:** "Ngày 33", "Phần 12", "Khách 20/100" ở một góc cố định, cùng vị trí mọi tập.
- **Hộp chữ trên đầu** chỉ cho câu vàng, công thức, các bước. Ít chữ ở đầu video, hộp tổng hợp các bước để cuối cho người xem chụp màn hình. Hộp chữ đứng ít nhất (số tiếng × 0,25 + 0,5) giây, tối thiểu 1,2 giây.
- **Không chữ đè chữ.** Cảnh có chữ sẵn thì tắt hộp chữ.
- **Vùng an toàn TikTok:** theo Bảng số chuẩn đầu file (cách mép trên 220 px, cách đáy ≥ 480 px, lề trái 60 px, lề phải 160 px; đăng cả Facebook Reels thì đáy ≥ 520 px). Đáy và cột phải bị nút bấm che.
- **Thử đọc ở cỡ điện thoại** trước khi đăng. **Tắt tiếng xem** vẫn phải hiểu ý chính.

## 1.3. Hình: 3 giây đầu, nhịp, cảnh chèn
- **3 giây đầu là hình mạnh nhất**, không phải cảnh đầu theo thời gian: kết quả đã xong, cảnh đầy/đẹp ("đã mắt"), mặt cảm xúc, khoảnh khắc buồn cười lấy từ giữa video, hoặc mặt người nói câu móc. Sáng rõ, có chuyển động. Không mở bằng màn hình đen, logo, cảnh đang chỉnh máy.
- **Nhịp:**
  - 6 giây đầu cắt 3–5 lần (khoảng 1 giây/cảnh);
  - thân video 2–3 giây/cảnh khi kể bằng chữ + nhạc; cảnh có lời dài theo câu nói (thường 3–4 giây);
  - cảnh không lời dài nhất 5 giây (cảnh chuẩn bị 0,5–1 giây); đoạn chờ (đun, trộn) cắt còn 3–4 giây hoặc tua;
  - không để một cảnh nói chuyện kéo quá 15 giây mà không chèn hình, chữ hoặc cắt nhảy;
  - mỗi động tác một cảnh, bỏ lúc chờ.
- **Cắt theo nhịp nhạc** (vlog, trước – sau không lời): đặt mốc phách (nhịp gõ của bài nhạc), mỗi cảnh dài 2–4 phách hoặc đúng 1 ô nhịp, đoạn cao trào 1–2 phách. CapCut: chọn nhạc → tính năng Nhịp / Beat tự đánh dấu phách, kéo mép cảnh khớp dấu. Dựng bằng lệnh: đo nhịp bài, tính mốc phách cộng dồn trên lưới khung hình rồi làm tròn độ dài cảnh theo đó (không làm tròn từng cảnh riêng, kẻo trôi lệch dần).
- **Tua nhanh, quay chậm:** đoạn chờ tua 2–4 lần; khoảnh khắc đẹp (rót, nhấc món, lật bánh) chậm 0,5 lần, không quá 2 giây. Cảnh có lời nói thì không đổi tốc độ.
- **Cắt thẳng là chính.** Video tốt của người thường hầu như không dùng chuyển cảnh, hiệu ứng. Chỉ dùng chuyển cảnh làm ngay lúc quay (tay che ống kính, vẩy máy) hoặc đặt đúng phách nhạc. Zoom nhảy nhẹ (100% ↔ 110%) chỉ dùng cho video nói trước camera để che vết cắt.
- **Chỉ lấy cảnh sạch, dứt khoát.**
  - **Máy đứng yên:** cảnh rung lắc, lia vội, máy đang bị cầm lên / dời chỗ thì không dùng, kể cả khi nội dung hay. Video thiếu cảnh thì ngắn lại, không lấy cảnh rung bù vào. **Ngoại lệ nhóm D (gia đình):** được cầm máy đi theo người (cảnh đời thường trong nhà), nhưng vẫn bỏ cảnh giật, lia vội.
  - **Động tác trọn và gọn:** mỗi cảnh một động tác làm đến xong (bấm → đèn sáng, đặt ấm → đứng yên). Cắt vào ngay khi động tác bắt đầu, cắt ra ngay khi xong. Bỏ đoạn lóng ngóng: tay quờ quạng, chỉnh đi chỉnh lại, tay che kín khung, đồ vật nhòe vì tay lướt sát máy.
  - **Không lấy cảnh hậu trường của việc quay:** tay cầm điện thoại / máy quay, người quay lọt khung, lúc đang dựng máy.
  - **Tìm đúng khoảnh khắc của một việc** (vd "pha trà" = lúc ấm trà được đặt xuống, không phải cả đoạn loay hoay ở bàn trà):
    1. Gọi tên việc bằng **1 động tác + 1 đồ vật** ("đặt ấm xuống", "ấn nút nâng bàn", "màn máy sáng"). Chữ trên cảnh đó phải khớp đúng động tác ấy.
    2. Tìm mọi đoạn có đồ vật đó (cả cảnh rộng lẫn cảnh cận), xem **4 khung/giây** quanh lúc động tác xảy ra, không xem lướt 1 khung/giây (dễ chọn nhầm cảnh có đồ vật khác).
    3. Ghi 3 mốc: **vào** (đồ vật / tay bắt đầu vào khung), **xong** (đồ vật đứng yên), **ra** (tay rời khỏi khung). Cắt từ "vào" đến ngay sau "ra", thường 1–2 giây.
    4. Cắt ra **trước khi có thứ khác chen vào khung** (đồ vật khác, tay khác, máy bắt đầu dịch).
    5. Ưu tiên cảnh cận có máy đứng yên; cảnh rộng chỉ dùng khi động tác thấy rõ và không có việc khác xen vào.
    6. Bạn chê cảnh nào ("lóng ngóng", "cho nhầm", "hỏng") thì làm lại đúng 5 bước trên cho việc đó, ghi lại mốc vào – xong – ra đã chọn để bạn kiểm.
  - Cách soát khi dựng bằng lệnh: đo độ dịch khung giữa các khung liền nhau (rung thì khung dịch liên tục), xem bảng ảnh 2 khung/giây của từng cảnh trước khi chọn. Ghi vào bảng tư liệu cột "sạch / rung / lóng ngóng" cho từng đoạn.
- **Không có cảnh mấp máy mồm mà không có tiếng.** Video có lời thoại thì cảnh nào tắt tiếng gốc (chỉ nhạc / chữ) phải là lúc bạn **không nói**: đang làm, đang cười, đang nhịn cười, mặt không quay vào máy. Cảnh bạn đang nói thì **chỉ đưa vào kèm đúng lời thoại của cảnh đó**. Cách soát: so mốc lời nói (phụ đề, nhận giọng) với từng cảnh tắt tiếng; cảnh nào trùng lúc đang nói mà thấy mặt thì lùi / dời sang đoạn im, không được thì bỏ. Cảnh không thấy mặt (tay, đồ vật) thì không sao.
- **Cảnh chèn:** câu nói có danh từ cụ thể (món, đồ vật, chỗ, con số) thì chèn đúng hình đó 2–3 giây; chuỗi hành động 5–6 giây. Video nói không quá 15 giây không có hình mới. Cảnh chèn đúng hành động trong câu nói, đúng ngành; có người đang làm việc; đủ sáng; không ghép hai khúc của cùng một video liền nhau (bị giật).
- **Trước – sau:** chèn lại "trước" 1 giây rồi mới mở "sau", đặt ở khoảng 75–90% video. Video trước–sau không lời có thể cắt theo nhịp nhạc.
- **Kết:** cảnh đẹp nhất giữ 2–3 giây rồi dừng, hoặc câu trả lời cho câu hỏi ở tiêu đề, hoặc lời hẹn tập sau. Không kéo dài sau cao trào.
- **Màu, ánh sáng:** cả video một tông màu, series giữ tông giống nhau. Mịn da nhẹ, màu tươi nhẹ, không dùng bộ lọc làm đổi màu da hay màu món ăn. Quay chỗ tối thì bật hết đèn hoặc quay gần cửa sổ; đèn chiếu từ phía trước người / món, không quay ngược sáng.
- **Xuất** 1080x1920, không xuất độ phân giải thấp.
- Có nói số liệu kênh (view, follow) thì chèn ảnh chụp trang kênh, khoanh đỏ đúng con số đó.

## 1.4. An toàn và luật nền tảng (bắt buộc)
- **Thông tin cá nhân:** che SĐT, Zalo, email cá nhân, địa chỉ nhà riêng, mã QR chuyển khoản, biển số, mã đơn, tên khách trên phiếu / thùng hàng, tên người khác (riêng ảnh bình luận công khai trong video trả lời bình luận thì giữ tên + ảnh đại diện, chỉ che khi tên nhạy cảm). Soi cả tiếng, phụ đề, đồ vật lọt khung (giấy tờ, màn hình, hóa đơn). **Địa chỉ, số điện thoại, Zalo của cửa hàng** thì được để (nên ở cảnh kết và mô tả); địa chỉ nhà riêng thì không bao giờ.
- **Trẻ em:** không dùng tên thật của trẻ; không lộ tên trường, đồng phục có tên, vở / sổ có tên trường lớp, đường về nhà; không cảnh ngủ, tắm, thay đồ, khóc, ăn mặc hở; không để trẻ một mình trong video (luôn có người lớn trong cảnh hoặc rõ là đang có người lớn trông). Trẻ em lên hình phải được bố mẹ đồng ý.
- **Khách hàng trong hình:** dán giấy báo "quán có quay video" ở chỗ dễ thấy; ưu tiên quay tay, tô, lưng khách. Khách lộ rõ mặt thì xin phép bằng miệng; không đồng ý thì che mặt. Mặt người đang chuyển động khó che → bỏ cảnh, hoặc dùng che có theo dõi chuyển động trong CapCut (lớp che tự chạy theo mặt).
- **Cảnh cấm:** lửa nguy hiểm, cháy nổ, đổ vỡ, tai nạn, hút thuốc, bạo lực, hở hang. Áo hai dây, trễ vai thì được, miễn không trông như cởi trần. Quay khách ở góc ngang mặt, không góc cao cận ngực.
- **Không hứa hẹn:** không "chắc chắn", "đảm bảo", "ngon nhất"; không bịa số liệu, lời khen; video có kết quả khách hàng thì thêm dòng "kết quả mỗi người khác nhau".
- **Dùng video người khác làm cảnh chèn** thì ghi nhãn "NGUỒN: TIKTOK @tên kênh" ở góc trên trái. Bình luận người xem dùng làm tiêu đề thì giữ tên và avatar, chỉ che khi tên nhạy cảm.
- **Nhạc:** nhạc bản quyền ghép sẵn có thể bị tắt tiếng; luôn giao thêm bản không nhạc. Tài khoản doanh nghiệp chỉ dùng thư viện nhạc thương mại.

## 1.5. Tự kiểm trước khi giao
- Xem bảng ảnh 24 khung đều cả video: phụ đề đúng nghĩa, chữ không đè chữ, cảnh chèn đúng chỗ, không lộ thông tin, không cảnh nào đang mấp máy mồm mà tắt tiếng, không cảnh rung / lóng ngóng / thấy tay cầm máy.
- Tự chấm 1–10:
  - 2 giây đầu có giữ được người xem không;
  - chữ có đọc kịp không;
  - nhịp có đoạn chết không;
  - tắt tiếng xem vẫn hiểu không;
  - kết có dừng đúng lúc không.
- Ghi 3 lỗi tệ nhất, sửa xong mới giao.
