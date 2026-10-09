# Rubric Thẩm Định Thiết Kế

Áp dụng cho Python CLI, backend, thư viện và UI. Design Reviewer độc lập đọc Spec năm mục scope/design/contracts/acceptance_criteria/risks; mọi kết luận có section/AC ID/artifact làm evidence.

1. Scope: files/symbols và blast radius rõ; không thêm tính năng ngoài brief.
2. Design: kiến trúc phù hợp hệ thống hiện hữu; không bắt mọi stack dùng DOM, Node hoặc storage browser.
3. Contracts: input/output/schema, lỗi và side effects có cách kiểm; command/cwd/dependencies khả thi.
4. Acceptance: ID duy nhất, description kiểm được, ui boolean; applicable false phải có na_reason. AC bắt buộc không được né bằng N/A. Bắt buộc có ít nhất 1 Acceptance Criteria về dữ liệu mẫu (AC-SEED: cung cấp sẵn dữ liệu mẫu thực tế, phong phú để demo ngay khi khởi động, cấm bàn giao app trắng trơn không có dữ liệu).
5. Verification: test/build commands có ID, command, cwd root-relative và ac_ids. UI có kế hoạch browser/local preview, viewport và interactions phù hợp sản phẩm. CLI/backend có terminal/API evidence.
6. Security/data: input validation, secret handling, authorization, integrity/race risks theo bề mặt thật.
7. Snapshot: project checkout chính xác; staged/unstaged/untracked source được giữ; snapshot_exclusions chỉ path root-relative đã kê khai, evidence_root nếu cần là absolute directory.
8. Gates: Reviewer khác Architect, review gắn đúng Spec SHA256 trước Sếp duyệt; Spec đổi vô hiệu approval; REJECT thứ hai pha design → ESCALATED, counters giữ nguyên.
9. UI Finish-Gate & Anti-Generic Contract (Áp dụng cho sản phẩm có UI):
   - **Bài trừ Generic UI:** Loại bỏ triệt để các thiết kế dùng chung vô hồn (interchangeable UI: dashboard 4 thẻ số generic, gradient/glassmorphism trang trí rỗng tuếch, card grid thiếu phân cấp, fake density, empty state hời hợt).
   - **Bắt buộc có Design Contract cụ thể cho sản phẩm:** Spec UI phải xác lập rõ: User + Job cần hoàn thành, First-read object (thứ đập vào mắt đầu tiên), Primary action (1 hành động chính quan sát được), Density decision (compact/balanced/spacious và lý do), Phân cấp thị giác (Hierarchy), Interaction model, Responsive priority (ưu tiên khi thu nhỏ), và **Forbidden defaults** (danh sách pattern mặc định bị cấm cho sản phẩm này).
   - **Tính độc bản của Components (Bespoke Components):** Thành phần giao diện phải phục vụ trực tiếp cho workflow và domain của sản phẩm, không dùng thư viện mặc định một cách máy móc; phải thẩm định đủ các trạng thái loading, empty, error, selection, focus, disabled và giao diện hẹp (mobile/narrow viewports).
   - **Tiêu chuẩn Finish Gate:** Chỉ PASS/APPROVE khi màn hình thể hiện rõ bản sắc sản phẩm và luồng công việc chính mà không có nội dung đệm generic hay quyết định thị giác thiếu căn cứ.

Task Board có profile riêng tại `rubrics/task-board-design-profile.md`; chỉ áp dụng khi brief chọn benchmark đó. Không ép các điều kiện của profile lên CLI/backend.

Report ghi finding ID/severity/location/problem/impact/evidence/required fix/status. Mục không kiểm được ghi NOT_VERIFIED và lý do; không đổi thành PASS mặc định. APPROVE chỉ khi Spec đầy đủ, kiểm được, đáp ứng tiêu chuẩn UI Finish-Gate (với UI) và không còn blocker; REJECT nêu lỗi cụ thể; ESCALATE khi yêu cầu mâu thuẫn hoặc thiếu capability thiết yếu. Design không có PARTIAL_APPROVE.

Report lưu dưới brain artifact root của task; app payload `report` nhận TEXT (nội dung report), không tự đọc path. Kết thúc bằng đúng một dòng `VERDICT: APPROVE`, `VERDICT: REJECT` hoặc `VERDICT: ESCALATE`.
