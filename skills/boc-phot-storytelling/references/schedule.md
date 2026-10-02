# Lịch format

Năm format có mặt trên lịch phát và trên playlist. Tên người xem thấy:

| Slug | Tên playlist |
|---|---|
| `mo-so` | Mổ sổ |
| `lat-to-roi` | Lật tờ rơi |
| `mot-dem` | Một đêm |
| `hai-mat-nhin` | Hai mắt nhìn |
| `ba-nga` | Ba ngã |

Chu kỳ, lặp lại:

1. `mo-so`
2. `lat-to-roi`
3. `mot-dem`
4. `hai-mat-nhin`
5. `ba-nga`

`dem-nguoc-thang` (playlist **Đếm ngược tháng**) đứng ngoài chu kỳ.

## Chọn slot

1. Lấy bài `da-chot` mới nhất trong `ledger.md`.
2. Slot đến hạn là `slot_den_han_ke_tiep` của bài đó. Bài đó chưa có khóa này thì lấy format kế tiếp sau `slot_lich` của nó trong chu kỳ. `slot_lich: ngoai-chu-ky` mà thiếu khóa kế tiếp thì slot đến hạn là `mo-so`.
3. Lắp các trục còn lại theo `cards.md` để bài mới lệch bài liền trước ít nhất ba trục.
4. Được đổi khỏi slot đến hạn khi brief chỉ sống trong một format khác, hoặc khi slot đến hạn không lệch đủ ba trục. Ghi lý do trên thẻ. Format bị nhảy lượt thành `slot_den_han_ke_tiep`, trừ `dem-nguoc-thang`.
5. `dem-nguoc-thang` chỉ được thay vào slot khi cả ba điều sau đúng: brief là một quyết định sụp trong nhiều tháng; năm bài `da-chot` gần nhất không dùng engine này; thẻ ghi lý do đổi slot. Không dùng nó để “kể cho có chuyện”.

Sau khi anh chốt, ghi `slot_den_han_ke_tiep` bằng format bị nhảy lượt nếu có, không thì bằng phần tử kế tiếp của `slot_lich` trong chu kỳ. Bài `ngoai-chu-ky` không làm chu kỳ nhảy bước.
