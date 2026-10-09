# Bộ Tiêu Chí Phản Biện Mã Nguồn & Soi GAP (Code Critique Rubric)

> **Ai dùng:** Code Critic (`agents/app/code_critic.md`) — Tác tử phản biện độc lập chặng CRITIQUE của nhánh `app`.
> **Nguyên tắc:** Soi rọi sâu vào tính đúng đắn của logic, phát hiện lỗ hổng đặc tả (Spec GAP), các giả định ngầm, boundary conditions và ngụy biện test/mock trước khi code được nạp vào QA chạy test động.
> **Nguyên tắc Reality Checker (Chống Phê Duyệt Ảo):** Mặc định trạng thái `NEEDS WORK` cho đến khi có bằng chứng thực chứng áp đảo (overwhelming proof). Miễn dịch hoàn toàn với fantasy approval — coi các tuyên bố "zero issues found", điểm số hoàn hảo hoặc pass ảo từ các khâu trước là tín hiệu cảnh báo đỏ (red flag). CẤM TUYỆT ĐỐI phê duyệt khi thiếu bằng chứng thực chứng, phát hiện dirty mocks hoặc kết quả kiểm thử ngụy tạo.


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

### Trụ cột 3: Chống Mock Bẩn, Pass Ảo & Ngụy Biện Kiểm Thử (Anti-Pattern, Dirty Mock & Phantom Pass Audit)
- **Dirty Mocks:** Mock có thay thế toàn bộ logic cần test khiến test trở nên vô nghĩa không? Mock có che giấu lỗi runtime tiềm ẩn không?
- **Phantom Pass (Pass ảo):** Test có thực sự chạy và assert dữ liệu nghiệp vụ thật, hay chỉ là kiểm thử hình thức (chỉ kiểm tra hàm chạy không ném exception hoặc kiểm tra `assert True`)?
- **Assertion Validity:** Test có assert đúng hành vi và trạng thái kết quả đầu ra không?
- **Tautology Tests:** Test có kiểm tra xem `A == A` thay vì kiểm tra kết quả tính toán thực sự không?
- **Test coverage:** Kiểm thử có bao phủ đầy đủ các nhánh lỗi (unhappy path) và boundary conditions không?
- **Bằng chứng thực thi:** Tuyên bố tính năng đã chạy có đi kèm command và log output thực tế không, hay chỉ là suy diễn chủ quan?

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
| 3 | Chống mock bẩn & Pass ảo | Bắt buộc | Mock triệt tiêu giá trị kiểm thử, pass ảo không assert |
| 4 | Bằng chứng thực chứng (Reality Check) | Bắt buộc | Thiếu bằng chứng thực thi, tự phong 'zero issues' |
| 5 | Không nuốt lỗi (No Silent Fail) | Bắt buộc | try/catch rỗng, che giấu lỗi hệ thống |
| 6 | Không vượt Blast Radius | Bắt buộc | Sửa các module ngoài phạm vi Spec |
| 7 | Đặt tên & Cấu trúc mã | Nên | Tên biến tối nghĩa, hàm vi phạm Single Responsibility |
| 8 | Tách biệt logic và biểu diễn | Nên | Trộn lẫn logic nghiệp vụ vào tầng UI/Controller |

---

## 3. Định Dạng Báo Cáo Phản Biện Bắt Buộc

### [CODE CRITIQUE REPORT] - BÁO CÁO PHẢN BIỆN MÃ NGUỒN

```
1. PHÂN TÍCH SPEC GAP
   - [Đạt/Hổng] <mô tả chi tiết GAP so với Spec đã khóa>

2. ĐIỀU KIỆN BIÊN & EDGE CASES
   - [Phát hiện] <vị trí file:dòng> — rủi ro biên: <mô tả>

3. ĐÁNH GIÁ KIỂM THỬ, MOCKS & PASS ẢO
   - [Hợp lệ/Bẩn] <đánh giá chất lượng test case, mock và phát hiện pass ảo nếu có>

4. XÁC THỰC THỰC CHỨNG (REALITY CHECK EVIDENCE)
   - [Đạt/Thiếu] <đối soát claims với diff, lệnh chạy và bằng chứng thực tế>

5. KHUYẾN NGHỊ SỬA ĐỔI (REFACTORING)
   - [Ưu tiên cao] <vấn đề cần sửa> — <file:dòng>
   - [Khuyến nghị] <gợi ý cải thiện cấu trúc>

6. KẾT LUẬN & TRẠNG THÁI (Mặc định NEEDS WORK trừ khi có bằng chứng áp đảo)
```

Kết thúc báo cáo bằng **đúng một** dòng phán quyết chuẩn:

    VERDICT: APPROVE
    VERDICT: REJECT
    VERDICT: ESCALATE

---

## 4. Quy Tắc Phán Quyết

- **Mặc định:** Mọi lượt nộp luôn ở trạng thái `NEEDS WORK`.
- **REJECT:** Nếu vi phạm bất kỳ mục nào thuộc mức **Bắt buộc** (có Spec GAP, bỏ sót biên, mock bẩn, pass ảo, thiếu bằng chứng thực chứng, nuốt lỗi). Yêu cầu Builder sửa đổi và nộp lại cho Code Critic duyệt lại.
- **APPROVE:** CHỈ KHI có bằng chứng thực chứng áp đảo (overwhelming proof), mã nguồn sạch, bao phủ đầy đủ Spec, xử lý đầy đủ biên, loại trừ hoàn toàn dirty mocks/pass ảo. Cho phép chuyển sang chặng AUDIT (QA Auditor).
- **ESCALATE:** Khi phát hiện mâu thuẫn kiến trúc gốc hoặc yêu cầu Spec bất khả thi.

