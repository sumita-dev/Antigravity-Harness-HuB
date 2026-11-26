---
name: social-publisher
description: "Đăng tải và lên lịch phát hành video lên Facebook Page (Graph Video API v21.0) và YouTube (Data API v3 Resumable Upload) thông qua các script Python stdlib thuần."
---

# Social Publisher (`social-publisher`)

Skill hỗ trợ thiết lập xác thực OAuth/Token và đăng hoặc hẹn lịch phát hành video lên **Facebook Page** và **YouTube** bằng Python chuẩn (`stdlib` thuần, không cần cài thư viện ngoài).

## 1. Cấu trúc tệp
- `.env.example`: Mẫu 7 biến môi trường cần thiết tại thư mục cấu hình (`--config-dir`, mặc định là thư mục làm việc hiện tại).
- `scripts/setup_fb_tokens.py`: Đổi `FB_SHORT_TOKEN` sang long-lived user token, lấy danh sách Page (`me/accounts`), lưu `fb_tokens.json` và tự điền `FB_PAGE_ID` / `FB_PAGE_ACCESS_TOKEN` vào `.env` nếu đang trống.
- `scripts/setup_youtube_oauth.py`: Chạy luồng OAuth 2.0 local callback (`http://127.0.0.1:8765/callback`), xác nhận kênh khớp `YOUTUBE_CHANNEL_ID`, lưu `youtube_token.json`.
- `scripts/publish_video.py`: Upload hoặc hẹn lịch video lên `fb`, `yt`, hoặc `all` (hỗ trợ `--dry-run`).

## 2. Quy trình vận hành chuẩn

### Bước 1: Chuẩn bị `.env` tại workspace
1. Sao chép `.env.example` thành `.env` tại thư mục cấu hình (`<config-dir>/.env`).
2. Điền các biến tương ứng với nền tảng cần dùng:
   - Facebook: `FB_APP_ID`, `FB_APP_SECRET` (và `FB_SHORT_TOKEN` khi chạy setup, hoặc `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN` nếu đã có).
   - YouTube: `YOUTUBE_CHANNEL_ID`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`.

### Bước 2: Thiết lập token / OAuth (chỉ cần làm lần đầu hoặc khi token hết hạn)
- **Facebook:**
  ```bash
  python "<SKILL_DIR>/scripts/setup_fb_tokens.py" --config-dir "<WORKSPACE>"
  ```
- **YouTube:**
  ```bash
  python "<SKILL_DIR>/scripts/setup_youtube_oauth.py" --config-dir "<WORKSPACE>"
  ```

### Bước 3: Kiểm tra trước bằng `--dry-run` (BẮT BUỘC)
Chạy `publish_video.py` với cờ `--dry-run` để kiểm tra file video tồn tại, cấu hình hợp lệ, payload dự kiến và ràng buộc thời gian hẹn đăng (Facebook yêu cầu từ **10 phút** đến **30 ngày** kể từ hiện tại):
```bash
python "<SKILL_DIR>/scripts/publish_video.py" \
  --platform all \
  --video "<PATH_TO_VIDEO>" \
  --title "Tiêu đề video" \
  --description "Mô tả / caption" \
  --tags "tag1,tag2" \
  --privacy private \
  --schedule "2026-12-01 20:00" \
  --config-dir "<WORKSPACE>" \
  --dry-run
```

### Bước 4: Xin xác nhận của người dùng (BẮT BUỘC)
Trước khi bỏ cờ `--dry-run` để đăng hoặc lên lịch thật:
- Trình bày rõ nền tảng (`fb` / `yt` / `all`), file video, tiêu đề, mô tả, quyền riêng tư (`privacy`), và thời gian hẹn đăng (nếu có).
- Chỉ chạy lệnh thật sau khi người dùng xác nhận đồng ý.

### Bước 5: Chạy `publish_video.py` thật
Chạy lại lệnh ở Bước 3 nhưng bỏ `--dry-run`. Script trả về JSON sạch gồm `video_id`, `url`, `scheduled_at` và `status` (`published` hoặc `scheduled`).

## 3. Quy tắc an toàn bắt buộc
- **Không hardcode** ID, secret, hoặc token vào skill, script hay prompt.
- **Không tự ý đăng/lên lịch thật** khi chưa có xác nhận rõ ràng của người dùng sau bước `--dry-run`.
- **Không in token/secret** ra chat, stdout, stderr hay log; không đọc hay dán nội dung `fb_tokens.json`, `youtube_token.json`, `.env` vào phản hồi.
- Khi có lỗi API/mạng, báo lại thông điệp đã che secret để người dùng xử lý, không lặp retry mù quáng tránh đăng trùng.

## 4. Bảng phân luồng (Route)

| Yêu cầu thực tế của người dùng | Dùng skill |
|---|---|
| Đăng bài text/ảnh hoặc đọc, trả lời bình luận Fanpage | `fb-admin` |
| Kiểm tra nội dung/kịch bản có vi phạm chính sách YouTube | `check-youtube-policy` |
| Viết caption bán hàng hoặc kịch bản video ngắn | `cong-thuc-viet-content-by-noti-v4` / `short-video-storytelling` |
