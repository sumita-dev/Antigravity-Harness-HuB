# Bộ Tiêu Chí Phản Biện Mã Nguồn & Soi GAP (Code Critique Rubric)

> **Ai dùng:** Code Critic (`agents/app/code_critic.md`) — Tác tử phản biện độc lập chặng CRITIQUE của nhánh `app`.
> **Nguyên tắc:** Soi rọi sâu vào tính đúng đắn của logic, phát hiện lỗ hổng đặc tả (Spec GAP), các giả định ngầm, boundary conditions và ngụy biện test/mock trước khi code được nạp vào QA chạy test động.

---

## 1. Bốn Trụ Cột Phản Biện (Critique Pillars)

### Trụ cột 1: Soi GAP Đặc tả (Spec GAP Detection)
- Builder có bỏ sót bất kỳ Acceptance Criteria nào trong Spec đã duyệt không?
- Có chức năng nào được viết nửa vời (placeholder, TODO, mock cứng giá trị trong code sản phẩm)?
- Có sự ngụy tạo dữ liệu hay hardcode kết quả để "lừa" test case không?
- Sự thay đổi có vượt ra ngoài phạm vi (blast radius) cho phép của Spec không?

### Trụ cột 2: Logic & Điều Kiện Biên (Boundary & Edge Case Integrity)
- Xử lý các giá trị cực trị/rỗng: `None`, `null`, `undefined`, chuỗi rỗng `""`, danh sách rỗng `[]`, số âm, số 0, số cực lớn.
- Xử lý lỗi phân trang (off-by-one errors): chỉ số đầu tiên/cuối cùng của mảng, trang vượt quá tổng số trang.
- Xử lý bất đồng bộ & đồng thời (Concurrency & Async): race conditions, deadlocks, unhandled promise rejections.
- Xử lý timeout, network drop, hoặc database reconnection.

### Trụ cột 3: Chống Mock Bẩn & Ngụy Biện Kiểm Thử (Anti-Pattern & Dirty Mock Audit)
- **Dirty Mocks:** Mock có thay thế toàn bộ logic cần test khiến test trở nên vô nghĩa không?
- **Assertion Validity:** Test có assert đúng hành vi và trạng thái hay chỉ assert hàm chạy không bắn exception?
- **Tautology Tests:** Test có kiểm tra xem `A == A` thay vì kiểm tra kết quả tính toán thực sự không?
- Test coverage có bao phủ các nhánh rẽ nhánh lỗi (unhappy path) chưa?

### Trụ cột 4: Khả Năng Bảo Trì & Kiến Trúc Sạch (Maintainability & Clean Design)
- **Surgical Diff:** Mã nguồn có tuân thủ 4 nguyên lý Karpathy (thay đổi tối thiểu, giải quyết đúng mục tiêu)?
- Có code rác (dead code), code comment-out hoặc console.log/print thừa trong luồng xử lý không?
- Xử lý ngoại lệ: Có hiện tượng "nuốt lỗi" (catch generic Exception rồi bỏ qua âm thầm) không?
- Tách biệt trách nhiệm: Hàm có quá dài (>50 dòng) hoặc xử lý quá nhiều việc không?

---

## 2. Checklist Chấm Điểm Phản Biện (Critique Checklist)

| # | Mục kiểm | Mức độ | Tiêu chí vi phạm |
| :-: | :--- | :--- | :--- |
| 1 | Độ phủ Spec & AC | Bắt buộc | Bỏ sót AC, hardcode kết quả giả lập |
| 2 | Điều kiện biên & Rỗng | Bắt buộc | Không kiểm tra null/empty, gây crash runtime |
| 3 | Chống mock bẩn | Bắt buộc | Mock triệt tiêu giá trị kiểm thử |
| 4 | Không nuốt lỗi (No Silent Fail) | Bắt buộc | try/catch rỗng, che giấu lỗi hệ thống |
| 5 | Không vượt Blast Radius | Bắt buộc | Sửa các module ngoài phạm vi Spec |
| 6 | Đặt tên & Cấu trúc mã | Nên | Tên biến tối nghĩa, hàm vi phạm Single Responsibility |
| 7 | Tách biệt logic và biểu diễn | Nên | Trộn lẫn logic nghiệp vụ vào tầng UI/Controller |

---

## 3. Định Dạng Báo Cáo Phản Biện Bắt Buộc

### [CODE CRITIQUE REPORT] - BÁO CÁO PHẢN BIỆN MÃ NGUỒN

```
1. PHÂN TÍCH SPEC GAP
   - [Đạt/Hổng] <mô tả chi tiết GAP so với Spec đã khóa>

2. ĐIỀU KIỆN BIÊN & EDGE CASES
   - [Phát hiện] <vị trí file:dòng> — rủi ro biên: <mô tả>

3. ĐÁNH GIÁ KIỂM THỬ & MOCKS
   - [Hợp lệ/Bẩn] <đánh giá chất lượng test case và mock>

4. KHUYẾN NGHỊ SỬA ĐỔI (REFACTORING)
   - [Ưu tiên cao] <vấn đề cần sửa> — <file:dòng>
   - [Khuyến nghị] <gợi ý cải thiện cấu trúc>

5. KẾT LUẬN
```

Kết thúc báo cáo bằng **đúng một** dòng phán quyết chuẩn:

    VERDICT: APPROVE
    VERDICT: REJECT
    VERDICT: ESCALATE

---

## 4. Quy Tắc Phán Quyết

- **REJECT:** Nếu vi phạm bất kỳ mục nào thuộc mức **Bắt buộc** (có Spec GAP, bỏ sót biên, mock bẩn, nuốt lỗi). Yêu cầu Builder sửa đổi và nộp lại cho Code Critic duyệt lại.
- **APPROVE:** Khi mã nguồn sạch, bao phủ đầy đủ Spec, xử lý đầy đủ biên và test trung thực. Cho phép chuyển sang chặng AUDIT (QA Auditor).
- **ESCALATE:** Khi phát hiện mâu thuẫn kiến trúc gốc hoặc yêu cầu Spec bất khả thi.
