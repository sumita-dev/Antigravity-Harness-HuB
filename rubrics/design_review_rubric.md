# Rubric thẩm định thiết kế

Design Reviewer độc lập kiểm Spec trước cổng Sếp duyệt. Không chấm bằng lời cam kết của Architect.

1. Đủ năm mục: phạm vi/blast radius, thiết kế, API/schema, acceptance criteria, rủi ro/giả định. Mỗi thay đổi source có lý do và phạm vi cụ thể.
2. Đối chiếu kiến trúc/code hiện tại, callers và execution flows; có impact evidence trước thay đổi symbol. Khi công cụ không khả dụng phải nêu giới hạn, không nhận đã kiểm.
3. API/schema có inputs, outputs, lỗi và validation. Không thêm LLM runtime cho workflow Gemini native.
4. AC có ID ổn định và cách kiểm; source/test/config liên quan được kê khai, gồm untracked. Với UI có local preview và browser checks; không UI có lý do `N/A`.
5. Có phương án test luồng chính, lỗi/biên, stale spec/source, approval và resume. Preview/log không thay cho kiểm tra hành vi.
6. Spec SHA256 và actor IDs được ghi; reviewer khác Architect. Những metadata này không xác thực danh tính runtime. Human signoff chỉ được ghi khi Sếp xác nhận rõ đúng Spec hiện tại.

Report: hash Spec, từng mục PASS/FAIL kèm dẫn chứng, lỗi theo ưu tiên và phán quyết. Thiếu mục bắt buộc → REJECT; mâu thuẫn không giải quyết được trong scope → ESCALATE. APPROVE không thay human signoff.

Kết thúc bằng đúng một dòng `VERDICT: APPROVE`, `VERDICT: REJECT` hoặc `VERDICT: ESCALATE`. Không sửa Spec/source. REJECT thứ hai trong pha design ngắt mạch.
