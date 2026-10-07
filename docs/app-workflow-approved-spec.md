# Đặc tả triển khai đã duyệt

Sếp đã xác nhận: “trước mắt hãy hoàn thiện theo đề xuất của em”, mục tiêu app chạy local có preview. Design Checker độc lập đã APPROVE với các điều kiện dưới đây.

1. Phạm vi: thêm AppWorkflowStore và checkpoint CLI; giữ CLI mô phỏng tương thích và phân biệt rõ kết quả mô phỏng. Không triển khai LLM API hoặc runtime tác tử riêng.
2. Thiết kế: INIT → DESIGN → DESIGN_REVIEW → SIGN_OFF → IMPLEMENTATION → AUDIT → APPROVED; REJECT quay lại Maker tương ứng, hai lần REJECT trong mỗi pha thì ESCALATED. Snapshot JSON chứa events và evidence được thay nguyên tử dưới task lock.
3. Hợp đồng: task ID an toàn; spec gồm năm mục và AC; review gắn SHA256 spec; approval ghi nguyên văn xác nhận con người; implementation có manifest bytes toàn source/test/config kể cả untracked; QA gắn manifest/spec hiện tại, command/cwd/exit/log hash và preview kiểm đủ AC.
4. Nghiệm thu: không bỏ qua gate, không Maker tự duyệt, phát hiện artifact đổi, counters tồn tại qua resubmit/restart, validation lỗi tường minh, full pytest xanh; có guide build task board thật trong Antigravity.
5. Rủi ro: actor ID và evidence là khai báo từ runtime, không xác thực danh tính hoặc sandbox quyền. CLI không tự gọi agent và không tự kiểm trình duyệt. Native runtime phải tạo agent độc lập và kiểm preview thực tế. Bảo toàn thay đổi sẵn có trong AGENTS.md, .claude và CLAUDE.md.

## Tám điều kiện của Design Checker

1. Design review/human approval gắn SHA256 Spec; audit gắn hash manifest. Spec hoặc source đổi làm quyết định cũ stale, không được APPROVED bằng evidence cũ.
2. Reviewer khác Architect, QA khác Builder; identity metadata là provenance do caller khai báo, không chứng minh native isolation.
3. Design REJECT về DESIGN, QA REJECT về IMPLEMENTATION; REJECT thứ hai mỗi pha chuyển ESCALATED. Counter không reset qua sửa bản thảo/resubmit/restart.
4. Manifest hash bytes source/test/config gồm untracked liên quan; loại trừ .git/.brain/dependencies/cache/artifact logs, không chỉ HEAD/git diff.
5. State/events/evidence references lưu cùng transaction dưới task lock; atomic replace không dùng một mình để chống lost updates.
6. Validate schema/actor/verdict/stage/task ID/path; evidence tồn tại/hash khớp; test log ghi command/cwd/exit/output. Exit 0 không tự suy ra QA APPROVE.
7. UI có local preview/browser evidence theo toàn bộ AC; non-UI có N/A reason phù hợp Spec. CLI không tự kiểm browser.
8. Simulator breaker dùng >=2 và tests/docs nhất quán. Giữ nội dung người dùng trong AGENTS/.claude/CLAUDE; nếu cập nhật AGENTS theo quyền bổ sung, chỉ surgical app section và bảo toàn GitNexus block, sync GEMINI. Task Board chỉ là benchmark guide, không triển khai benchmark trong thay đổi này.

### Điều chỉnh nghiệm thu sau review

`revise` có lý do rõ được mở lại task APPROVED về DESIGN, vô hiệu toàn bộ Spec/review/signoff/manifest/evidence downstream và giữ reject counters. Muốn hoàn tất phải qua toàn bộ thiết kế, reviewer, human signoff, implementation và audit mới; ESCALATED vẫn terminal. Approval được ghi nguyên văn chỉ khi khớp câu xác nhận rõ được CLI chấp nhận; câu không rõ bị từ chối và phải hỏi Sếp xác nhận rõ, không tự suy ra ý định.
