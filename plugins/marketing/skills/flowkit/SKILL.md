---
name: flowkit
description: "Sản xuất video AI hoàn chỉnh từ Storyboard trực quan sử dụng động cơ Flowkit (Veo 3 / Google Flow)."
when-to-use: >
  Tạo video marketing, TVC quảng cáo, phân cảnh storyboard, video TikTok/Reels/Shorts, video giới thiệu sản phẩm từ kịch bản phân cảnh.
argument-hint: create "<chủ đề>" | render [video_id] [--outdir <path>]
metadata:
  short-description: AI Video Production Studio (Google Flow / Veo 3)
---

# Kỹ Năng: flowkit (AI Video Production Studio)

Kỹ năng điều phối sản xuất video AI hoàn chỉnh từ kịch bản Storyboard trực quan, tích hợp động cơ **Flowkit** (Google Flow / Veo 3). Hỗ trợ vận hành cross-project từ bất kỳ workspace nào sang căn cứ động cơ Flowkit vật lý.

---

## 1. Cấu Hình Căn Cứ Động Cơ (Engine Base Configuration)

Hệ thống kết nối với căn cứ động cơ Flowkit qua biến môi trường hoặc tham số đường dẫn:

- **Biến môi trường căn cứ:** `FLOWKIT_ROOT`
  ```bash
  # Linux / macOS
  export FLOWKIT_ROOT="/path/to/flowkit"

  # Windows PowerShell
  $env:FLOWKIT_ROOT = "<flowkit-repo-path>"
  ```
  *Trong code / script:* `FLOWKIT_ROOT = os.getenv("FLOWKIT_ROOT", "<flowkit-repo-path>")`
- **Base URL API Flowkit:** `http://127.0.0.1:8100`
- **Review Board URL:** `http://localhost:8200`
- **Quy tắc thực thi script vật lý:** Mọi công cụ chạy script helper (`<flowkit-root>/tools/remove_watermark.py`, `<flowkit-root>/tools/review_server.py`) phải dùng đường dẫn căn cứ `$FLOWKIT_ROOT` hoặc chỉ định `Cwd: $FLOWKIT_ROOT`.
- **Thư mục đầu ra mặc định:** `<flowkit-root>/output/<slug>/`
- **Quy tắc xuất chéo dự án:** Khi chạy từ thư mục khác hoặc có tham số `--outdir <path>`, tự động copy video thành phẩm về thư mục chỉ định của người dùng.

---

## 2. Cú Pháp Lệnh (Sub-commands)

### 2.1 Phân cảnh & Tạo Storyboard trực quan:
```bash
/flowkit create "<chủ đề/tiêu đề>" [--scenes 8|12] [--lang vi|en] [--orientation HORIZONTAL|VERTICAL] [--material realistic|3d_pixar|anime]
```

### 2.2 Render Video & Ghép hoàn thiện:
```bash
/flowkit render [video_id] [--outdir <path>]
```

---

## 3. Chi Tiết Luồng: `/flowkit create`

Quy trình tạo Visual Storyboard Stills và mở Review Board trực quan để người dùng nghiệm thu trước khi render video tốn tài nguyên.

### Bước 0: Pre-flight Health Check
Kiểm tra kết nối tới Flowkit API:
```bash
curl -s http://127.0.0.1:8100/health
```
- Kết quả mong đợi: `{"extension_connected": true}` (hoặc provider status `OK` nếu dùng Assistant mode).
- **Nếu server chưa bật hoặc không phản hồi:**
  - Hướng dẫn hoặc kích hoạt server nền:
    ```bash
    # Chạy tại thư mục căn cứ FLOWKIT_ROOT
    cd "$FLOWKIT_ROOT"
    python -m agent.main
    ```
  - Kiểm tra Chrome Extension trên tab Google Flow đã đăng nhập và hiển thị trạng thái kết nối màu xanh.

### Bước 1: Kịch bản Phân rã & Storyboard
1. **Thiết lập tham số:**
   - Số phân cảnh: `--scenes` (mặc định: `8`, tùy chọn: `12`).
   - Khung hình: `--orientation` (`VERTICAL` 9:16 cho TikTok/Reels/Shorts, `HORIZONTAL` 16:9 cho YouTube/TVC).
   - Chất liệu: `--material` (`realistic`, `3d_pixar`, `anime`, mặc định: `realistic`).
   - Ngôn ngữ: `--lang` (`vi` hoặc `en`, mặc định: `vi`).
2. **Kỷ luật cốt truyện & Cấu trúc phân cảnh:**
   - Mỗi cảnh gồm:
     - `camera_angle` & `shot_scale`: góc máy (Wide, Medium Close-up, Low-angle, Tracking shot...).
     - `action_prompt` (Prompt sinh ảnh tĩnh): chỉ mô tả hành động và bố cục cảnh; TUYỆT ĐỐI không lặp lại mô tả ngoại hình nhân vật (tính nhất quán do Reference Images qua `imageInputs` đảm nhiệm).
     - `video_prompt`: phân đoạn thời gian chuyển động chi tiết: `0-3s: [hành động]. 3-6s: [hành động]. 6-8s: [hành động].` (hoặc 4.0s native cho video ngắn).
     - `narrator_text`: lời thuyết minh vừa vặn với độ dài cảnh (tối đa 7.0s cho cảnh 8s; tối đa 3.5s cho cảnh 4s).
     - `dialogue`: lời thoại trong ngoặc kép ở sub-clip nếu có.
3. **Quy tắc bất biến Rule 15 (Real-people bypass):**
   - Khi kịch bản dựa trên nhân vật có thật hoặc người nổi tiếng (chính trị gia, tài phiệt, KOLs):
     - **CẤM TUYỆT ĐỐI** dùng tên thật làm entity `name` hoặc trong prompt (`image_prompt`, `prompt`, `video_prompt`).
     - Dùng **Role-based Alias** (ví dụ: "Tổng Tư Lệnh", "Vị Doanh Nhân Áo Đen", "Chuyên Gia Tài Chính").
     - Miêu tả diện mạo thuần túy bằng nhận dạng khách quan (vóc dáng, tóc, trang phục, phụ kiện).
     - Ghi nhận mapping nội bộ tại `<flowkit-root>/.omc/research/`.

### Bước 2: Khai báo Entities & Batch Sinh Reference Images
1. **Tạo Project:**
   ```bash
   curl -X POST http://127.0.0.1:8100/api/projects \
     -H "Content-Type: application/json" \
     -d '{
       "name": "<Tên_Dự_Án>",
       "material": "<realistic|3d_pixar|anime>",
       "story": "<Tóm_tắt_cốt_truyện>"
     }'
   ```
   Lấy `project_id` (`PID`).

2. **Khai báo Entities:**
   - Nhân vật (Characters): Khung dọc **PORTRAIT (9:16)**.
   - Bối cảnh (Locations): Khung ngang **LANDSCAPE (16:9)**.
   ```bash
   curl -X POST http://127.0.0.1:8100/api/characters \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": "<PID>",
       "name": "<Alias_Role>",
       "type": "CHARACTER",
       "description": "<Đặc_điểm_nhận_dạng>",
       "image_prompt": "<Prompt_chi_tiết>"
     }'
   ```

3. **Batch sinh Reference Images:**
   - **CẤM** viết script vòng lặp rời rạc. Dùng Batch API:
     ```bash
     curl -X POST http://127.0.0.1:8100/api/requests/batch \
       -H "Content-Type: application/json" \
       -d '{
         "requests": [
           {"type": "GENERATE_CHARACTER_IMAGE", "character_id": "<CID_1>", "project_id": "<PID>"},
           {"type": "GENERATE_CHARACTER_IMAGE", "character_id": "<CID_2>", "project_id": "<PID>"}
         ]
       }'
     ```
   - Polling trạng thái qua `GET /api/requests/batch-status?project_id=<PID>` cho đến khi `done: true` và `all_succeeded: true`.
   - Xác nhận 100% entities đã có `media_id` chuẩn UUID (format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, không dùng `CAMS...`).

### Bước 3: Tạo Scenes & Batch Sinh Visual Storyboard Stills
1. **Tạo Video Container:**
   ```bash
   curl -X POST http://127.0.0.1:8100/api/videos \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": "<PID>",
       "name": "<Video_Title>",
       "orientation": "<ORIENTATION>"
     }'
   ```
   Lấy `video_id` (`VID`).

2. **Tạo Scenes trong DB & Cập nhật Narrator Text:**
   - Tạo Scene:
     ```bash
     curl -X POST http://127.0.0.1:8100/api/scenes \
     -H "Content-Type: application/json" \
     -d '{
       "video_id": "<VID>",
       "display_order": 1,
       "prompt": "<Scene_1_Visual_Action_Prompt>",
       "video_prompt": "<Scene_1_Veo3_Motion_Prompt>",
       "character_names": ["<Alias_Role_1>"]
     }'
     ```
   - **Bắt buộc gọi PATCH (Rule 13):** Endpoint POST bỏ qua `narrator_text`, phải patch ngay:
     ```bash
     curl -X PATCH http://127.0.0.1:8100/api/scenes/<SID_1> \
       -H "Content-Type: application/json" \
       -d '{"narrator_text": "<Lời_thuyết_minh_scene_1>"}'
     ```

3. **Batch sinh Scene Images (Visual Storyboard Stills):**
   ```bash
   curl -X POST http://127.0.0.1:8100/api/requests/batch \
     -H "Content-Type: application/json" \
     -d '{
       "requests": [
         {"type": "GENERATE_IMAGE", "scene_id": "<SID_1>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "<ORIENTATION>"},
         {"type": "GENERATE_IMAGE", "scene_id": "<SID_2>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "<ORIENTATION>"}
       ]
     }'
   ```
   - Polling `GET /api/requests/batch-status?video_id=<VID>&type=GENERATE_IMAGE` tới khi `done: true`.

### Bước 4: Xóa SynthID Watermark Tự Động
Chạy script xóa watermark bằng inpainting (Rule 19 & 20):
```bash
python "<flowkit-root>/tools/remove_watermark.py" "<flowkit-root>/output/<slug>/raw/*.jpg" "<flowkit-root>/output/<slug>/raw/*.png"
```
Đảm bảo tất cả các hình ảnh đã được xử lý sạch sẽ.

### Bước 5: Bật Review Board & Dừng Phiên Duyệt Trực Quan
1. **Khởi chạy Review Board trên port 8200:**
   ```bash
   # Chạy tại FLOWKIT_ROOT
   python "<flowkit-root>/tools/review_server.py"
   ```
2. **Cung cấp URL cho người dùng:**
   - Link Review Board: `http://localhost:8200?video_id=<VID>`
3. **Cổng Dừng Bàn Giao (Zero-Context-Bloat Gate):**
   - **DỪNG LẠI TẠI ĐÂY.** Không tự ý chạy tiếp sang bước render video.
   - Báo cáo tóm tắt: Project ID, Video ID, số lượng Scenes, Khung hình, Chất liệu, và liên kết Review Board.
   - Người dùng trực tiếp xem các khung hình storyboard tĩnh trên trình duyệt, gắn nhãn duyệt hoặc yêu cầu chỉnh sửa prompt/regen hình ảnh.

---

## 4. Chi Tiết Luồng: `/flowkit render`

Quy trình nhận diện feedback, render video Veo 3 chuyển động, kiểm định chất lượng AI Vision, lồng tiếng TTS và hoàn thiện video master.

### Bước 0: Pre-flight Health Check
```bash
curl -s http://127.0.0.1:8100/health
```

### Bước 1: Đồng bộ Feedback từ Review Board
1. Xác định `video_id` từ đối số lệnh hoặc truy vấn `GET /api/active-project`.
2. Kiểm tra `<flowkit-root>/tools/review_feedback.json` hoặc trạng thái scene trong DB:
   - Nếu cảnh có thay đổi prompt: gọi `PATCH /api/scenes/<SID>` cập nhật `prompt` / `video_prompt`.
   - Nếu cảnh được gắn tag `regen-img`: chạy `REGENERATE_IMAGE`, sau đó xóa lại watermark trước khi tạo video.

### Bước 2: Batch Sinh Video Veo 3
1. **Gửi batch tạo video:**
   ```bash
   curl -X POST http://127.0.0.1:8100/api/requests/batch \
     -H "Content-Type: application/json" \
     -d '{
       "requests": [
         {"type": "GENERATE_VIDEO", "scene_id": "<SID_1>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "<ORIENTATION>"},
         {"type": "GENERATE_VIDEO", "scene_id": "<SID_2>", "project_id": "<PID>", "video_id": "<VID>", "orientation": "<ORIENTATION>"}
       ]
     }'
   ```
   *Lưu ý:* Video duration 8.0s chuẩn (hoặc 4.0s native cho Shorts/TikTok theo Rule 18; cấm crop video 8s xuống 4s).
2. **Polling trạng thái:**
   - Poll `GET /api/requests/batch-status?video_id=<VID>&type=GENERATE_VIDEO` (khoảng 2-5 phút mỗi video) cho đến khi `all_succeeded: true`.

### Bước 3: AI Vision Quality Review
1. **Chạy kiểm định chất lượng video tự động:**
   ```bash
   curl -X POST "http://127.0.0.1:8100/api/videos/<VID>/review?mode=light&orientation=<ORIENTATION>"
   ```
2. **Review Gate (Ngưỡng điểm >= 7.5):**
   - **Score >= 7.5:** Đạt chuẩn (PASS).
   - **Score < 7.5:**
     - Đọc lỗi và hướng dẫn khắc phục từ review report.
     - Patch điều chỉnh `video_prompt` qua `PATCH /api/scenes/<SID>`.
     - Kích hoạt regen video cảnh lỗi (`GENERATE_VIDEO`).
     - Tối đa 2 chu trình sửa & regen (Circuit breaker).

### Bước 4: TTS Narration & Tinh Chỉnh Thời Lượng
1. **Chọn Voice Template:**
   ```bash
   curl -s http://127.0.0.1:8100/api/tts/templates
   ```
2. **Batch sinh âm thanh thuyết minh:**
   ```bash
   curl -X POST http://127.0.0.1:8100/api/videos/<VID>/narrate \
     -H "Content-Type: application/json" \
     -d '{"template": "<template_name>"}'
   ```
   Đảm bảo các file âm thanh được sinh trong `<flowkit-root>/output/<slug>/tts/` với thời lượng <= 7.0s mỗi cảnh.

### Bước 5: Ghép Nối Hoàn Thiện & Xuất Video Cross-Project
1. **Thực thi ghép nối video bằng ffmpeg:**
   Chạy quy trình fit narrator và concat hoàn thiện:
   - Lấy từng video scene (`<flowkit-root>/output/<slug>/4k/scene_*.mp4` hoặc video gốc) và audio TTS (`<flowkit-root>/output/<slug>/tts/scene_*.wav`).
   - Cắt video vừa khít thời lượng giọng đọc: `CUT_DUR = min(TTS_DUR + 0.5s, VIDEO_DUR)`.
   - Trộn âm thanh TTS và render video master tại `<flowkit-root>/output/<slug>/final/<slug>_fitted.mp4`.

2. **Tự động sao chép video cross-project:**
   - Nếu có cờ `--outdir <path>` hoặc người dùng đang thực thi từ một thư mục dự án bên ngoài:
     ```bash
     # Copy video thành phẩm sang thư mục đích
     cp "<flowkit-root>/output/<slug>/final/<slug>_fitted.mp4" "<target_path>"
     ```
   - Đảm bảo video thành phẩm có mặt ngay tại thư mục làm việc của người dùng.

---

## 5. Báo Cáo Nghiệm Thu Hoàn Tất (Handoff Summary)
- **Tên dự án:** `<project_name>`
- **Video ID:** `<VID>`
- **Định dạng & Khung hình:** `<ORIENTATION>` (`1080x1920` hoặc `1920x1080`)
- **Số phân cảnh hoàn tất:** `<N>/<N>` scenes
- **Điểm đánh giá AI Vision:** `<Score>/10`
- **Đường dẫn tệp video master:** `<local_or_outdir_path>`
