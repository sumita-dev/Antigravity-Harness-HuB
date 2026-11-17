---
name: video-normalizer
description: >-
  Chuẩn hóa video dọc 9:16: xóa watermark góc dưới bên phải bằng FFmpeg delogo
  linh hoạt (hỗ trợ preview khung vùng xóa và xử lý hàng loạt) và ghi đè toàn bộ
  metadata + thông số stream theo chuẩn thiết bị Google Pixel 4 XL.
---

# Video Normalizer (9:16 Watermark Removal + Google Pixel 4 XL Metadata)

Skill chuẩn hóa video dọc `9:16` phục vụ 2 tác vụ cốt lõi thông qua script tất định [`normalize_video.py`](./scripts/normalize_video.py) (chỉ yêu cầu `ffmpeg`, `ffprobe` và Python chuẩn, không cần cài thư viện ngoài):

1. **Xóa watermark góc dưới bên phải** bằng bộ lọc `delogo` của FFmpeg (giữ nguyên full khung hình `9:16`, tự động clamp biên an toàn tránh lỗi `delogo`).
2. **Chuẩn hóa Metadata & Stream theo chuẩn Google Pixel 4 XL**:
   - Xóa sạch toàn bộ metadata gốc (`-map_metadata -1`, bỏ tag AI/editor/Lavf).
   - Ghi bộ thẻ Android / QuickTime `mdta` chuẩn Google Pixel 4 XL (`com.android.manufacturer=Google`, `com.android.model=Pixel 4 XL`, `com.android.version=13`, `com.android.capture.fps`, `make`, `model`, `creation_time`, `handler_name=VideoHandle` / `SoundHandle`, brand `mp42`).
   - Ép chuẩn stream quay điện thoại Pixel 4 XL: `1080x1920`, H.264 High@L4.1 (`yuv420p`, `bt709`), `30fps` hoặc `60fps`, AAC `48kHz` stereo.

---

## Cách chạy nhanh

### 1. Xử lý 1 file đơn lẻ
```powershell
python "$env:USERPROFILE\.gemini\config\plugins\computer\skills\video-normalizer\scripts\normalize_video.py" `
  --input "D:\videos\raw.mp4" `
  --output "D:\videos\clean_pixel4xl.mp4"
```

### 2. Xử lý hàng loạt (Batch cả thư mục)
```powershell
python "$env:USERPROFILE\.gemini\config\plugins\computer\skills\video-normalizer\scripts\normalize_video.py" `
  --input "D:\videos\input_dir" `
  --output "D:\videos\output_dir"
```
*Ghi chú: Khi chạy batch, script tự động cộng lệch ngẫu nhiên vài phút cho `creation_time` của từng video (trừ khi truyền `--creation-time` cố định) để tránh trùng timestamp.*

### 3. Xem trước vùng `delogo` trước khi render hàng loạt
Nếu watermark có kích thước đặc thù, xuất 1 frame ảnh có khung đỏ đánh dấu vùng `delogo` để kiểm tra:
```powershell
python "$env:USERPROFILE\.gemini\config\plugins\computer\skills\video-normalizer\scripts\normalize_video.py" `
  --input "D:\videos\raw.mp4" `
  --preview-box "D:\videos\preview_box.jpg"
```
Sau đó tinh chỉnh bằng `--wm-rect x,y,w,h` (tọa độ trên khung `1080x1920`) hoặc theo tỷ lệ phần trăm (`--wm-w-pct`, `--wm-h-pct`, `--wm-mr-pct`, `--wm-mb-pct`).

---

## Tùy chọn tham số chính

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `--input`, `-i` | *(Bắt buộc)* | Đường dẫn file video (`.mp4`, `.mov`, `.mkv`, `.webm`) hoặc thư mục chứa video |
| `--output`, `-o` | `<input>_pixel4xl.mp4` / `normalized/` | Đường dẫn file xuất hoặc thư mục xuất |
| `--wm-rect` | *(Tự tính theo %)* | Tọa độ cố định `x,y,w,h` trên khung hình đích (ví dụ `780,1750,275,130`) |
| `--wm-w-pct` | `0.26` | Chiều rộng vùng xóa theo tỷ lệ chiều ngang (26% ~ 280px) |
| `--wm-h-pct` | `0.07` | Chiều cao vùng xóa theo tỷ lệ chiều dọc (7% ~ 134px) |
| `--wm-mr-pct` | `0.02` | Cách mép phải (2% ~ 22px) |
| `--wm-mb-pct` | `0.02` | Cách mép dưới (2% ~ 38px) |
| `--no-delogo` | `False` | Bỏ qua bước xóa watermark, chỉ chuẩn hóa stream + metadata Pixel 4 XL |
| `--fps` | `auto` (`30` hoặc `60`) | Ép FPS đầu ra (`30`, `60`, hoặc `auto` giữ 60 nếu nguồn >= 50fps) |
| `--crf` | `18` | Chất lượng H.264 (`16`-`23`, nhỏ hơn = nét hơn) |
| `--keep-resolution` | `False` | Giữ độ phân giải gốc thay vì chuẩn hóa về `1080x1920` |
| `--android-version` | `13` | Phiên bản Android ghi vào `com.android.version` |
| `--creation-time` | *(UTC hiện tại)* | Thời gian tạo chuẩn ISO 8601 (ví dụ `2026-11-17T09:15:00Z`) |
| `--location` | *(Không ghi)* | Tọa độ GPS chuẩn ISO 6709 (ví dụ `+10.7769+106.7009/`) |
| `--preview-box` | *(Không xuất)* | Xuất 1 frame `.jpg` vẽ khung đỏ vùng `delogo` để kiểm tra |

---

## Kiểm chứng sau khi chạy

Luôn kiểm tra lại file đầu ra bằng `ffprobe` để xác nhận sạch tag cũ và đủ metadata Pixel 4 XL:
```powershell
ffprobe -v quiet -print_format json -show_format -show_streams "D:\videos\clean_pixel4xl.mp4"
```
Các trường bắt buộc phải thấy:
- `format.tags.com.android.manufacturer`: `"Google"`
- `format.tags.com.android.model`: `"Pixel 4 XL"`
- `format.tags.com.android.version`: `"13"`
- `streams[0]`: `codec_name: "h264"`, `width: 1080`, `height: 1920`, `pix_fmt: "yuv420p"`, `tags.handler_name: "VideoHandle"`
- `streams[1]` (nếu có audio): `codec_name: "aac"`, `sample_rate: "48000"`, `channels: 2`, `tags.handler_name: "SoundHandle"`
