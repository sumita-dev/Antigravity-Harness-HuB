# Task Board Design Profile (optional)

Chỉ áp dụng khi brief chọn Task Board benchmark; không phải rubric cho mọi app. Các chi tiết bên dưới phải được chốt trong Spec, không phải proof benchmark đã chạy.

# Rubric Thẩm Định Thiết Kế (Design Review Rubric)

Design Reviewer độc lập kiểm tra Spec 5 mục trước cổng Sếp duyệt. Không chấm bằng lời cam kết suông của Architect.

---

## 1. Tiêu Chí Thẩm Định 8 Trụ Cột Bằng Chứng (8 Evidence Pillars)

1. **Status Integrity:** Spec cấm tự ghi `SIGN_OFF: approved`. Human approval không bị giả lập. Có checkpoint chờ Human Sign-off rõ ràng. Builder bị chặn chạy trước sign-off.
2. **Error Contract Testability:** Mọi API error code (`ERR_TITLE_REQUIRED`, `ERR_INVALID_STATUS`, `ERR_TASK_NOT_FOUND`, `ERR_STORAGE_FAIL`...) phải có ánh xạ trực tiếp sang AC ID và phương pháp test.
3. **Responsive Parity:** Mô tả cụ thể sự khác biệt giữa Desktop (1280px, layout 3 cột, Modal) và Mobile (390px, Group list, Full-screen/Bottom sheet, Touch-safe dialog). Spec ghi chung chung "responsive" mà không phân định rõ $\rightarrow$ **REJECT**.
4. **DOM-Free Core:** Core module không import `window`/`document`, có thể chạy Node.js thuần (`node_import_check: PASS`). Storage adapter hỗ trợ mock injection.
5. **Anti-XSS:** Cấm `innerHTML` thô với dữ liệu user. Title & Description có AC test XSS với payload cụ thể (`<script>alert(1)</script>`, `<img src=x onerror=alert(1)>`, `<svg onload=alert(1)>`). Render bằng phương thức an toàn (`textContent`/`createElement`).
6. **ID Integrity:** Thuật toán sinh ID cụ thể (`crypto.randomUUID` + collision guard), có test sinh 10,000 IDs. Không tuyên bố "tuyệt đối" nếu dùng random thuần.
7. **Strict Schema Guard:** Lập bảng Schema fields (`id`, `title`, `description`, `status`, `createdAt`, `updatedAt`). Phải có test cases cho JSON hỏng, JSON không phải array, id/title sai kiểu, status sai enum, timestamp sai định dạng, phần tử null.
8. **MutationResult Contract:** Tách biệt rõ `success: true, persisted: true` vs `success: true, persisted: false, warning: "ERR_STORAGE_UNAVAILABLE"` vs `success: false, persisted: false, code: "ERR_INVALID_STATUS"`. CẤM trả `success: true` cho lỗi nghiệp vụ.

---

## 2. Bảng Evidence Bắt Buộc 10 Mục (10-Item Evidence Manifest)

Report bắt buộc phải chứa bảng evidence 10 mục với dẫn chứng `file:section`, `AC ID`, hoặc `artifact path`:
1. **Scope / Blast Radius:** Spec §1, file list.
2. **Architecture:** Spec §2, data-flow diagram.
3. **API / Schema:** Spec §3, contract table.
4. **Error Contracts:** AC mapping table.
5. **Testability:** Node import & storage mock plan.
6. **Security:** XSS / storage / input validation rules.
7. **Responsive Behavior:** Desktop / mobile layout & interaction matrix.
8. **Preview Plan:** Server start & browser verification commands.
9. **Risks:** Mitigation plan & verification steps.
10. **Human Gate:** Checkpoint stage, SHA256 spec hash, sign-off state.

*Lưu ý:* Mục không thể kiểm tra phải ghi `status: NOT_VERIFIED` và lý do. Không được tự động chuyển `NOT_VERIFIED` thành `PASS`.

---

## 3. Cấu Trúc Finding & Quy Tắc Verdict

- **Finding Format:** Mỗi lỗi phải có `Finding ID`, `Severity` (`BLOCKER` | `HIGH` | `MEDIUM` | `LOW`), `Location`, `Problem`, `Impact`, `Evidence`, `Required fix`, `Status`. Không dùng câu nhận xét mơ hồ.
- **VERDICT: APPROVE:** Chỉ khi không có finding `BLOCKER`/`HIGH`, mọi error code có AC, mọi UI AC có kế hoạch browser check, Spec SHA256 khớp, Reviewer độc lập với Architect, không có mục bắt buộc nào bị `NOT_VERIFIED`.
- **VERDICT: REJECT:** Thiếu 1 trong 5 mục Spec, error contract không test được, UI không phân biệt Desktop/Mobile, rủi ro XSS/storage không có mitigation, AC không kiểm chứng được, thay đổi ngoài blast radius, hoặc mục bắt buộc chưa xác minh.
- **VERDICT: ESCALATE:** Yêu cầu Sếp mâu thuẫn, phạm vi không rõ ràng, Spec hash bị đổi trong khi review, runtime thiếu công cụ kiểm chứng, hoặc có dấu hiệu tác tử khác sửa Spec.

Report phải lưu tại `.brain/artifacts/<task-id>/design-review.md` và kết thúc bằng đúng một dòng:
```text
VERDICT: APPROVE
```
hoặc `VERDICT: REJECT` / `VERDICT: ESCALATE`.
