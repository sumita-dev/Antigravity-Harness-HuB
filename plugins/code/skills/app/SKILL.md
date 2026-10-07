---
name: app
dependencies: ["test-driven-development", "karpathy-coder"]
description: >
  Gemini native app workflow: Architect, Design Reviewer, human signoff, Builder,
  QA và local preview, có checkpoint/evidence để resume. Triggers: build app, làm app, MVP.
---

# /app — Gemini native app workflow

Gemini trong Antigravity điều phối tác tử native qua công cụ thực tế runtime cung cấp. Quản đốc không tự sửa source/test. Workflow CLI lưu và kiểm checkpoint, không gọi LLM, viết app hay kiểm browser thay QA. CLI không có `--workflow` vẫn là mô phỏng; không dùng làm bằng chứng app hoàn tất.

## Bootstrap và routing

Đọc `docs/app-workflow-guide.md`. Kiểm runtime có tool gọi subagent, đọc/ghi/terminal và browser; thiếu thì báo đúng giới hạn. Không suy ra sandbox/identity isolation từ frontmatter. Dùng Python đã cài dependencies.

Tạo task checkpoint cho project mục tiêu, giữ task ID. Mỗi lượt gọi `--workflow status`; route theo `next_agent` và `stage` trước keyword. Checkpoint corrupt thì dừng, không tạo task mới để bỏ gate/counter. Sau đó chọn skill chuyên môn bổ sung: DESIGN kiến trúc, DESIGN_REVIEW advisor, IMPLEMENTATION TDD/Karpathy, AUDIT verification-before-completion/verify-ui/security-review khi cần.

## DESIGN → DESIGN_REVIEW

Gọi Architect theo `agents/app/architect.md`: Spec năm mục scope/design/contracts/acceptance_criteria có ID/description/ui/risks. Kê khai source/test/config, preview và cách kiểm AC. Lưu JSON và nộp `--workflow spec` với actor Architect.

Gọi Design Reviewer context độc lập theo `agents/app/design_reviewer.md` và `rubrics/design_review_rubric.md`; actor khác Architect. Reviewer kiểm tra 8 Trụ cột bằng chứng (StatusIntegrity, Error Contract Testability, Responsive Parity, DOM-Free Core, Anti-XSS, ID Integrity, Strict Schema Guard, MutationResult) và lập Bảng Evidence 10 mục. Ghi report tại `.brain/artifacts/<task-id>/design-review.md`, verdict gắn `spec_sha256`, nộp `--workflow design-review`. REJECT trả Architect; REJECT thứ hai ESCALATED. Không sửa source trước reviewer APPROVE.

## SIGN_OFF

Trình đúng Spec đã reviewer duyệt cho Sếp. Chờ xác nhận rõ, không coi im lặng là duyệt. Ghi nguyên văn thông điệp Sếp và `spec_sha256` qua `--workflow sign-off`. CLI record không xác thực ai gõ lệnh. Spec đổi vô hiệu design review/signoff cũ.

CLI nhận nguyên câu `Duyệt`, `Duyệt Spec này`, `Duyệt bản đặc tả này`, `SIGN_OFF: approved` hoặc `Bắt đầu code đi` (không phân biệt hoa thường; trim ngoài; prefix `Sếp:` tùy chọn). Không dấu câu cuối/text khác. Giữ raw message; unknown/conditional/refusal bị chặn, hỏi Sếp xác nhận rõ, không tự biến câu thành duyệt.

`--workflow revise` có reason được mở lại APPROVED về DESIGN, vô hiệu approvals/artifacts downstream và giữ counters; cần toàn bộ Reviewer/human signoff/Builder/QA mới. ESCALATED không mở lại bằng revise.

## IMPLEMENTATION

Gọi Builder theo `agents/app/builder.md`, TDD/Karpathy và branch/worktree thực tế; không vượt Spec. Chạy test/build thật, giữ command/cwd/exit/output artifact. Nộp `--workflow implementation`; store snapshot bytes source/test/config gồm untracked thuộc project, không chỉ HEAD. Runtime/log/dependency/cache không thuộc manifest.

Với UI chạy local preview theo Spec, giữ process và bàn giao URL/lệnh/session. Không deploy. Source đổi khi đang AUDIT: QA nộp REJECT gắn hashes checkpoint và report lý do, quay Builder rồi nộp implementation mới; counter tăng. Đổi kiến trúc dùng `--workflow revise` với reason để quay DESIGN, Reviewer và Sếp duyệt lại.

## AUDIT

Gọi QA context độc lập theo `agents/app/qa_auditor.md` và `rubrics/code_quality_rubric.md`; actor khác Builder. QA tự rerun test, đối soát diff/manifest/spec và kiểm local preview từng AC. Browser evidence là kết quả kiểm thực tế, không phải cờ auto-verified.

Nộp `--workflow audit`: verdict/spec hash/manifest hash/report/command-cwd-exit-log/preview checks theo AC ID. UI có local URL và bằng chứng; non-UI có N/A reason. CLI validate dữ liệu/hash, không tự xác thực browser/log. Test exit 0 không thay audit toàn bộ AC.

REJECT quay Builder; REJECT thứ hai pha audit ESCALATED, không reset sau resubmit/resume. APPROVE bàn giao URL còn hoạt động, cách chạy và evidence. Source đổi làm revision cũ stale. Không tuyên bố hoàn tất chỉ vì simulator APPROVE hoặc Stop hook pytest xanh.

## Quyền và resume

Architect/Reviewer/QA không sửa source. Runtime có thể gộp terminal/file-write cùng quyền; đây là prompt guardrail, không đảm bảo sandbox. Agent export chỉ mô tả vai trò; runtime phải tạo đúng context/branch/tools.

Resume task ID cũ qua `--workflow status`, kiểm file/hash trước tiếp tục. Stop hook kiểm harness không thay test/build/browser app mục tiêu. Task Board trong guide chỉ là benchmark hướng dẫn, chưa được triển khai trong repo.
