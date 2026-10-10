---
name: app
dependencies: ["test-driven-development", "karpathy-coder"]
description: >
  Gemini native app workflow: Architect, Design Reviewer, human signoff, Builder,
  QA và local preview, có checkpoint/evidence để resume. Triggers: build app, làm app, MVP.
---

# /app — Gemini native app workflow

Gemini trong Antigravity điều phối tác tử native qua công cụ thực tế runtime cung cấp. Quản đốc không tự sửa source/test. Workflow CLI lưu và kiểm checkpoint, không gọi LLM, viết app hay kiểm browser thay QA. CLI không có `--workflow` vẫn là mô phỏng; không dùng làm bằng chứng app hoàn tất.

## Quy trình các pha phát triển toàn diện

Quy trình phát triển ứng dụng native khép kín gồm các pha:

1. **Pha 0 - INTAKE:** Phỏng vấn làm rõ 3 tham số cốt lõi (Tech Stack, Nơi lưu trữ, Top 3-5 MVP Stories) theo `docs/intake-protocol.md`. Cấm tự ý code khi chưa rõ ý Sếp.
2. **Pha 1 - DESIGN:** Architect lập Spec 5 mục, bắt buộc có tiêu chí dữ liệu mẫu `AC-SEED`.
3. **Pha 2 - DESIGN_REVIEW:** Reviewer độc lập thẩm định Spec theo rubric chung.
4. **Pha 3 - SIGN_OFF:** Trình đúng Spec SHA256 cho Sếp duyệt.
5. **Pha 3.5 - UI_CONCEPT (Nếu có UI):** Quản đốc sinh 2–4 ảnh concept bằng `generate_image`, Sếp chốt concept qua `ask_question`, lưu visual guideline cho Builder (bypass với non-UI/CLI).
6. **Pha 4 - IMPLEMENTATION:** Builder viết code theo TDD & Karpathy, bám sát visual concept đã duyệt, bắt buộc tạo seed data (mockData.json/seed script), cấm app trắng trơn.
7. **Pha 5 - AUDIT & E2E & UAT:** QA Auditor kiểm thử AC, E2E Playwright, giám sát dev server qua `scripts/run_dev_logger.py` (port check & HTTP health check), xuất bảng UAT `docs/human-test-sheet-template.md`.
8. **Pha 6 - PACKAGING:** Tự động sinh launcher 1-click `start-app.bat` và `HDSD-NHANH.md` qua `scripts/generate_launcher.py`.

## Bootstrap và routing

Đọc `docs/app-workflow-guide.md` và `docs/intake-protocol.md`. Kiểm runtime có tool gọi subagent, đọc/ghi/terminal và browser; thiếu thì báo đúng giới hạn. Không suy ra sandbox/identity isolation từ frontmatter. Dùng Python đã cài dependencies.

Tạo task checkpoint cho project mục tiêu, giữ task ID. Mỗi lượt gọi `--workflow status`; route theo `next_agent` và `stage` trước keyword. Checkpoint corrupt thì dừng, không tạo task mới để bỏ gate/counter. Sau đó chọn skill chuyên môn bổ sung: DESIGN kiến trúc, DESIGN_REVIEW advisor, IMPLEMENTATION TDD/Karpathy, AUDIT verification-before-completion/verify-ui/security-review khi cần.

## Pha 0: INTAKE (Intent Alignment Gate)

Trước khi khởi động Architect, Quản đốc bắt buộc thực hiện phỏng vấn làm rõ theo quy chuẩn `docs/intake-protocol.md`:
- Chốt 3 tham số: (1) Tech Stack, (2) Nơi lưu trữ dữ liệu, (3) Top 3-5 User Stories cốt lõi.
- Tuyệt đối không tự suy đoán hoặc bắt đầu code bừa bãi.
- Chỉ chuyển sang Pha 1 khi Sếp đã xác nhận rõ ràng phương án.

## Pha 1 & 2: DESIGN & DESIGN_REVIEW

Gọi Architect theo `agents/app/architect.md`: Spec năm mục scope/design/contracts/acceptance_criteria có ID/description/ui/risks. **Bắt buộc có ít nhất 1 Acceptance Criteria về dữ liệu mẫu (AC-SEED)** cung cấp sẵn dữ liệu mẫu phong phú để demo ngay khi khởi động. Kê khai source/test/config, preview và cách kiểm AC. Lưu JSON và nộp `--workflow spec` với actor Architect.

Gọi Design Reviewer context độc lập theo `agents/app/design_reviewer.md` và rubric chung `rubrics/design_review_rubric.md`; actor khác Architect. Kiểm hợp đồng, lỗi, AC (bao gồm AC-SEED), testability/security/snapshot/gates phù hợp CLI/backend/UI. Task Board profile `rubrics/task-board-design-profile.md` chỉ khi brief chọn benchmark. Ghi report thật, app payload report TEXT gắn `spec_sha256`; REJECT thứ hai pha design ESCALATED. Design PARTIAL_APPROVE không hợp lệ.

## Pha 3: SIGN_OFF

Trình đúng Spec đã reviewer duyệt cho Sếp. Chờ xác nhận rõ, không coi im lặng là duyệt. Ghi nguyên văn thông điệp Sếp và `spec_sha256` qua `--workflow sign-off`. CLI record không xác thực ai gõ lệnh. Spec đổi vô hiệu design review/signoff cũ.

CLI nhận nguyên câu `Duyệt`, `Duyệt Spec này`, `Duyệt bản đặc tả này`, `SIGN_OFF: approved` hoặc `Bắt đầu code đi` (không phân biệt hoa thường; trim ngoài; prefix `Sếp:` tùy chọn). Không dấu câu cuối/text khác. Giữ raw message; unknown/conditional/refusal bị chặn, hỏi Sếp xác nhận rõ, không tự biến câu thành duyệt.

`--workflow revise` có reason được mở lại APPROVED về DESIGN, vô hiệu approvals/artifacts downstream và giữ counters; cần toàn bộ Reviewer/human signoff/Builder/QA mới. ESCALATED không mở lại bằng revise.

## Pha 3.5: UI_CONCEPT (Concept Giao diện & Visual Signoff)

Kích hoạt tự động sau Pha 3 (SIGN_OFF) khi Sếp đã duyệt Spec, áp dụng cho mọi ứng dụng có giao diện UI (với ứng dụng Non-UI / backend thuần túy / CLI thì tự động bypass chuyển thẳng sang Pha 4).

1. **Sinh 2–4 ảnh concept bằng `generate_image`:**
   - Quản đốc trực tiếp sử dụng công cụ `generate_image` để tạo 2–4 ảnh mockup/concept giao diện thực tế dựa trên User Stories và Design Specs.
   - Các ảnh concept thể hiện các phong cách trực quan khác nhau (ví dụ: Modern Minimalist / Apple-inspired, Data-dense Dashboard / Linear-style, Vibrant & Friendly, hoặc Dark Mode Neo-brutalist).
   - Prompt tạo ảnh tập trung vào UI màn hình chính, bố cục phân cấp (layout hierarchy), màu sắc chủ đạo, component states, không viền thiết bị ngoài trừ khi được yêu cầu.

2. **Trình chiếu và khảo sát ý kiến Sếp bằng `ask_question`:**
   - Trình chiếu các ảnh concept dưới dạng Markdown image links hoặc Carousel.
   - Sử dụng công cụ `ask_question` để Sếp lựa chọn phong cách thiết kế ưng ý nhất (hoặc yêu cầu tinh chỉnh).

3. **Chốt Visual Guideline bàn giao cho Builder:**
   - Sau khi Sếp chốt concept, lưu đường dẫn ảnh vào Spec (`visual_guideline` / Design Memory).
   - Concept ảnh đã duyệt là visual guideline bắt buộc cho Builder trước khi khởi động Pha 4 (IMPLEMENTATION).

## Pha 4: IMPLEMENTATION

Gọi Builder theo `agents/app/builder.md`, TDD/Karpathy và branch/worktree thực tế; không vượt Spec. **Nếu ứng dụng có UI, Builder bắt buộc phải đối soát mã nguồn frontend (layout, màu sắc, typography, components) bám sát đúng concept ảnh đã được Sếp phê duyệt trong Pha UI_CONCEPT.** **Bắt buộc phải tạo file seed data (mockData.json, seed.json hoặc seed script tương ứng)** đáp ứng tiêu chí AC-SEED, cấm bàn giao app trắng trơn không có dữ liệu.

Chạy test/build thật; Spec verification_commands có ID/command/root-relative cwd/ac_ids, QA command cwd absolute trong project. Nộp implementation report TEXT; snapshot includes staged/unstaged/untracked source/test/config, không chỉ HEAD. Mặc định chỉ loại exact root runtime/dependency/cache theo store; build/dist/.next và generated outputs khác chỉ loại khi signed snapshot_exclusions kê khai. Không blanket loại suffix .log hoặc nested source collisions.

Với UI chạy local preview theo Spec, giữ process và bàn giao URL/lệnh/session. Không deploy. Source đổi khi đang AUDIT: QA nộp REJECT gắn hashes checkpoint và report lý do, quay Builder rồi nộp implementation mới; counter tăng. Đổi kiến trúc dùng `--workflow revise` với reason để quay DESIGN, Reviewer và Sếp duyệt lại.

## Pha 5: AUDIT, E2E & UAT

Gọi QA context độc lập theo `agents/app/qa_auditor.md` và `rubrics/code_quality_rubric.md`; actor khác Builder. QA tự rerun test, đối soát diff/manifest/spec và kiểm local preview từng AC (bao gồm kiểm chứng AC-SEED). Browser evidence là kết quả kiểm thực tế, không phải cờ auto-verified.

Nộp audit verdict/spec hash/manifest hash/report TEXT/commands/preview checks đúng mỗi AC ID một lần. Mọi applicable AC kể cả non-UI cần PASS evidence; N/A chỉ khi signed applicable false có na_reason. Evidence/log paths absolute trong project/brain artifacts/signed evidence_root, cấm traversal/symlink/junction. UI có local URL/browser evidence. CLI validate hash không xác thực browser/log execution. Test exit 0 không thay toàn bộ AC.

PARTIAL_APPROVE yêu cầu >=1 applicable UI AC NOT_VERIFIED, mọi non-UI PASS và command/log hợp lệ; giữ AUDIT_PENDING_BROWSER. Request/promotion chỉ từ valid partial audit, kiểm cùng local URL, đúng pending UI IDs và old source/log/evidence hashes. Không tự biến NOT_VERIFIED thành PASS. Xem payload/migrate-legacy/schema 2 trong `docs/app-workflow-guide.md`.

Với ứng dụng UI, sau khi vượt qua Unit/Integration test:
1. Gọi `E2E_Engineer` theo `agents/app/e2e_engineer.md`: kịch bản Playwright POM, kiểm thử responsive Desktop (1280x720) và Mobile (390x844), chạy headless/headed, chụp screenshots và traces.
2. Gọi `E2E_Critic` theo `agents/app/e2e_critic.md`: đối soát 100% AC, phát hiện flaky tests, kiểm tra console log.
3. Khi khởi động dev server, sử dụng `scripts/run_dev_logger.py` để tự động kiểm tra cổng (Pre-flight port check), thăm dò HTTP health check (`wait_for_http_ok`), và bắt lỗi runtime vào `runtime-crash.log`.
4. Xuất bảng nghiệm thu thực tế theo `docs/human-test-sheet-template.md` để Sếp trực tiếp trải nghiệm UAT.

## Pha 6: PACKAGING (1-Click Launcher & Handoff)

Sau khi AUDIT và E2E được thông qua, kích hoạt script `scripts/generate_launcher.py`:
- Tự động sinh file `start-app.bat` trong thư mục ứng dụng: kiểm tra môi trường Node/Python, khởi chạy dev server ở background, tự động mở trình duyệt `http://localhost:<port>`.
- Tự động sinh file `HDSD-NHANH.md`: hướng dẫn 1-click run, cách tắt server và vị trí file dữ liệu seed data.
- Bàn giao trọn gói sản phẩm cho Sếp.

## Quyền và resume

Architect/Reviewer/QA không sửa source. Runtime có thể gộp terminal/file-write cùng quyền; đây là prompt guardrail, không đảm bảo sandbox. Agent export chỉ mô tả vai trò; runtime phải tạo đúng context/branch/tools.

Resume task ID cũ qua `--workflow status`, kiểm file/hash trước tiếp tục. Stop hook kiểm harness không thay test/build/browser app mục tiêu. Task Board trong guide chỉ là benchmark hướng dẫn, chưa được triển khai trong repo.
