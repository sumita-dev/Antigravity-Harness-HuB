# Apple-Inspired Design Skill v4.0

**Một Agent Skill độc lập** hỗ trợ thiết kế, xây dựng, đánh giá và cải thiện UI theo những nguyên tắc tham khảo từ Apple Human Interface Guidelines. Không liên kết, đại diện hay được Apple chứng nhận.

## Có gì trong v4.0?

- Giữ lại bộ React/TypeScript/Tailwind components, CSS tokens và Playwright + axe từ v2/v3.
- **Design Capture**: screenshot ở 390/768/1440px, thu thập metadata DOM/CSS hạn chế (không tự thu nội dung text).
- **Rubric + Scoring Engine**: 8 tiêu chí, 100 điểm, bằng chứng, confidence và coverage; tách điểm thẩm mỹ khỏi technical QA.
- **Native Vision SubAgent (`apple-design-critic`)**: Chấm điểm giao diện trực tiếp bằng năng lực thị giác native của Gemini trong Antigravity (dùng `view_file` xem ảnh PNG), 100% không cần `GEMINI_API_KEY`.
- **AI Design Critic CLI tùy chọn**: `critic-gemini.mjs` đóng vai trò fallback cho CI/CD ngoài khi cần gọi API trực tiếp.
- **Design Memory**: chỉ lưu những quyết định được duyệt, có ID, người duyệt, nguồn và thời điểm.
- **Controlled Improvement Loop**: tạo repair plan theo mặc định; có thể dùng coding-agent adapter opt-in để sửa theo đường dẫn cho phép, tối đa 3 vòng, dừng khi regression.
- **Node test suite**: chạy không cần mạng và không cần API key.

## Cài Agent Skill

Giải nén toàn bộ thư mục `apple-inspired-design` vào một trong các thư mục mà coding agent đang dùng hỗ trợ:

```text
.claude/skills/apple-inspired-design/        # Claude Code (project)
.agents/skills/apple-inspired-design/       # Codex (project)
.agent/skills/apple-inspired-design/        # Antigravity: kiểm tra phiên bản/cấu hình cụ thể
```

**Giữ nguyên** toàn bộ nội dung trong Skill. Với Antigravity, nếu phiên bản sử dụng không quét thư mục trên, làm theo tài liệu của phiên bản đó và truyền đường dẫn tới SKILL.md cho agent.

## 5 bước chạy thử trên dự án React / Next.js

1. Khởi chạy ứng dụng ở `http://127.0.0.1:3000` (hoặc đặt `UI_BASE_URL`).
2. Trong thư mục `qa`: `npm install && npx playwright install chromium`. Chạy `UI_ROUTES=/,/dashboard npm run qa:audit` rồi `npm run qa:design:capture`.
3. Chạy self-test của Skill: `node --test tests/*.test.mjs` ở root của Skill.
4. Đánh giá ảnh bằng AI **nếu được phép** theo `evaluation/README.md`, hoặc viết đánh giá có căn cứ bằng tay. Chạy scoring engine để xuất `score.json`, `issues.json`, `report.md`.
5. Dùng `improvement/guarded-loop.mjs` ở chế độ **plan-only**. Để agent sửa, đọc kỹ `improvement/README.md` và duyệt mọi thay đổi với Git diff.

### Demo chấm điểm offline, không cần app hay API

```bash
node evaluation/scoring-engine.mjs \
  --input evaluation/samples/sample-review.json \
  --out /tmp/apple-design-v4-demo
```

**Demo chứa dữ liệu giả định, không phải kết quả đánh giá sản phẩm của anh.** Điểm demo được đánh dấu provisional.

### 1. Luồng mặc định: SubAgent Native Vision (`apple-design-critic`) — Không cần API Key

Trong Antigravity, SubAgent `apple-design-critic` dùng `view_file` để mở và đánh giá trực tiếp ảnh PNG từ `qa/artifacts/design-capture/`:
1. **Chụp ảnh**: Tại thư mục `qa`, chạy `npm run qa:design:capture`.
2. **Khởi chạy SubAgent `apple-design-critic`**: Tác tử mở xem trực tiếp các file ảnh PNG bằng `view_file`, đọc `capture.json` và `audit.json`, rồi chấm điểm theo rubric.
3. **Xuất kết quả**: SubAgent ghi `qa/artifacts/design-quality/review.json` và chạy `scoring-engine.mjs` để xuất `score.json`, `issues.json`, `report.md`.
> **Hoàn toàn native**, không gửi dữ liệu ra ngoài, **100% không cần `GEMINI_API_KEY`**.

### 2. Luồng Fallback: External Gemini Vision API (`critic-gemini.mjs`) cho CI/CD ngoài

Nếu chạy trong môi trường CI/CD bên ngoài không có native SubAgent và muốn gọi trực tiếp Google Gemini API:
```bash
# 1. Capture, tại thư mục qa
npm run qa:design:capture

# 2. Tại root skill, cấu hình Gemini Vision API
export GEMINI_API_KEY='...'
export UI_CRITIC_MODEL='gemini-2.5-flash'  # hoặc gemini-2.5-pro
export UI_ALLOW_EXTERNAL_IMAGES=1
node evaluation/critic-gemini.mjs --capture qa/artifacts/design-capture/capture.json \
  --technical-audit qa/artifacts/visual-qa/audit.json \
  --out qa/artifacts/design-quality/ai-review.json
node evaluation/scoring-engine.mjs --input qa/artifacts/design-quality/ai-review.json \
  --out qa/artifacts/design-quality
```
Trong Windows PowerShell dùng `$env:KEY="value"` thay vì `export`.

## Tài liệu

- `evaluation/README.md`: rubric, điểm số và AI API.
- `improvement/README.md`: ranh giới tự động sửa và phê duyệt.
- `qa/README.md`: test, capture, screenshot baseline.
- `references/design-rubric.md`: tiêu chuẩn đánh giá thiết kế.
- `workflows/design-audit.md`, `workflows/design-improvement.md`: quy trình cho coding agent.
- `references/sources-and-rights.md`: nguồn chính thức và giới hạn bản quyền.

## Giới hạn

- Screenshot không đủ để đánh giá toàn bộ UX, chuyển động, trạng thái tương tác hoặc accessibility.
- Điểm AI có tính chủ quan, cần hiệu chỉnh bằng review thực tế và human approval.
- Playwright và React samples chỉ áp dụng cho website; đánh giá native yêu cầu môi trường riêng.
- `guarded-loop` kiểm tra sau khi fixer chạy, **không cách ly an toàn** một AI hoặc lệnh độc hại. Chỉ dùng command đáng tin cậy trong repository có backup/Git.
- Chưa được xác minh tích hợp E2E trên ứng dụng thực tế của anh trong gói này.

## CI notes

`.github/workflows/design-quality-skill-checks.yml` and `ui-qa.yml` are **templates**. A GitHub repository will only execute them after they are placed in that repository's root `.github/workflows/` and adjusted to its directory structure and application start commands. AI API calls and baseline updates are not enabled by default.
