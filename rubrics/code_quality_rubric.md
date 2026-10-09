# Bộ Tiêu Chí Thẩm Định Chất Lượng Mã Nguồn (Code Quality Rubric)

> **Ai dùng:** QA Auditor (`agents/app/qa_auditor.md`) — Tác tử kiểm định chất lượng khách quan (Checker) của nhánh `app`.
> **Nguyên tắc:** QA Auditor tập trung vào kiểm định kỹ thuật khách quan và bằng chứng thực thi động (chạy lại test suite, quét bảo mật OWASP/Secret leak, kiểm tra endpoint /health, browser evidence và local preview). Không tin báo cáo của Builder; mọi phán quyết phải dựa trên bằng chứng tự chạy lại thật.

---

## 1. Năm Trụ Cột Thẩm Định Bắt Buộc

### Trụ cột 1: Bằng chứng thực thi (Evidence Integrity)
- Có lệnh cụ thể đã chạy (test/lint/build) kèm **kết quả thật**.
- QA Auditor phải **tự chạy lại** tối thiểu bộ test liên quan; kết quả phải khớp.
- Không chấp nhận: "đã test pass" mà không có output; output cắt xén không thấy tổng kết.
- **Không có bằng chứng = REJECT**, kể cả code nhìn có vẻ đúng.

### Trụ cột 2: Tuân thủ đặc tả (Spec Compliance)
- Đối chiếu từng mục trong hợp đồng API/schema của Architect.
- Kiểm cả **phần không được làm**: blast radius có bị vượt không?
- Lệch đặc tả mà không khai báo → REJECT. Lệch có khai báo + lý do hợp lý → ghi nhận, đánh giá riêng.

### Trụ cột 3: Chất lượng mã nguồn (Code Quality)
- **Surgical Diff:** Git diff phải sạch, không có thay đổi định dạng ngoài luồng, mọi dòng code thay đổi đều có thể truy vết về yêu cầu của task.
- Hàm/đơn vị mã có một trách nhiệm rõ ràng; tên nói rõ ý định.
- Không mã chết, không log rác, không code bị comment-out.
- Xử lý lỗi tường minh; **không silent failure** (bắt lỗi rồi bỏ qua).
- Không thêm dependency thừa; dependency mới phải có lý do.
- Không lặp logic ở mức phải tách hàm.
- **Kiểm định giao diện Frontend & Anti-patterns (Impeccable 59 Rules):** Đối với các thay đổi liên quan đến giao diện Web / Frontend (HTML, CSS, JSX/TSX), QA Auditor phải chạy bộ công cụ detector của Impeccable (`plugins/impeccable/skills/impeccable/scripts/detect.mjs` hoặc `scripts/detector/cli/main.mjs`) để rà soát bộ 59 detector rules. Đảm bảo Zero Primary Anti-Patterns (không vi phạm nghiêm trọng về typography, contrast, hierarchy, layout, motion). Các cảnh báo advisory được xem xét nhưng không tính là failure chặn.

### Trụ cột 4: Bảo mật & An toàn Vận hành (Security & Operational Baseline)
- **Zero Hardcoded Secrets:** Tuyệt đối không hardcode secret/token/mật khẩu/private keys trong mã nguồn (bắt buộc quét sạch qua `scripts/run_security_audit.py`).
- **Zero Critical Vulnerabilities:** Phụ thuộc (dependencies trong package.json / requirements.txt) không chứa lỗ hổng bảo mật mức Critical.
- **Health Check Readiness:** Hệ thống/ứng dụng phải có endpoint `/health` (tiêu chí AC-HEALTH) trả về trạng thái hoạt động, uptime và version phục vụ giám sát và container orchestration.
- Kiểm tra & làm sạch đầu vào ở ranh giới hệ thống (chống injection).
- Không nối chuỗi để tạo câu truy vấn/lệnh hệ thống.
- Lỗi trả về không rò rỉ thông tin nội bộ (stack trace, đường dẫn, phiên bản).
- Phân quyền: hành động nhạy cảm phải có kiểm tra quyền, không mặc định tin tưởng.

### Trụ cột 5: Kiểm thử (Test Adequacy)
- Có test cho luồng chính **và** ít nhất một luồng lỗi/biên.
- **Bugfix test:** Khi sửa bug, phải có test case tái hiện lỗi.
- Test phải thực sự kiểm hành vi (assert có ý nghĩa), không chỉ chạy cho có.
- Test không phụ thuộc trạng thái máy cá nhân (đường dẫn tuyệt đối, dữ liệu có sẵn).
- Test dùng thư mục tạm riêng; trong môi trường hạn chế dùng `.brain/qa-tmp-<unique>` và `-p no:cacheprovider`, không thay quyền toàn máy.

---

## 2. Checklist Chấm Điểm

| # | Mục kiểm | Mức | Cách kiểm |
| :-: | :--- | :--- | :--- |
| 1 | Test liên quan chạy lại và pass | Bắt buộc | Tự chạy, so kết quả |
| 2 | Có bằng chứng output thật | Bắt buộc | Xem log/lệnh |
| 3 | Đúng hợp đồng API/schema | Bắt buộc | Đối chiếu đặc tả |
| 4 | Không vượt blast radius | Bắt buộc | So danh sách file thay đổi |
| 5 | Không secret hardcode (Zero Secrets) | Bắt buộc | Quét qua `scripts/run_security_audit.py` & grep diff |
| 6 | Zero critical vulnerabilities | Bắt buộc | Quét dependency audit (`run_security_audit.py`) |
| 7 | Đạt tiêu chuẩn kiểm tra sức khỏe (/health) | Bắt buộc | Kiểm tra endpoint `/health` (AC-HEALTH) |
| 8 | Không silent failure | Bắt buộc | Đọc đường xử lý lỗi |
| 9 | Không mã chết / code comment-out | Nên | Đọc diff |
| 10 | Đặt tên rõ, hàm một trách nhiệm | Nên | Đọc diff |
| 11 | Dependency mới có lý do | Nên | So requirements/manifest |
| 12 | Có test cho luồng lỗi/biên | Nên | Đọc test |
| 13 | Test không phụ thuộc máy cá nhân | Nên | Grep path tuyệt đối |
| 14 | Comment giải thích "vì sao" | Tùy | Đọc diff |
| 15 | Sạch anti-patterns frontend (Impeccable 59 rules) | Bắt buộc (nếu có UI) | Chạy detector Impeccable: `node plugins/impeccable/skills/impeccable/scripts/detect.mjs --json <targets>` |

---

## 3. Quy Định Định Dạng Đầu Ra Bắt Buộc Của QA Auditor

### [AUDIT REPORT] - BÁO CÁO THẨM ĐỊNH MÃ NGUỒN

```
1. BẰNG CHỨNG ĐÃ TỰ CHẠY LẠI
   - Lệnh: <lệnh> | Kết quả: <tóm tắt thật>

2. ĐỐI CHIẾU ĐẶC TẢ
   - Mục <n>: ĐẠT / KHÔNG ĐẠT — <dẫn chứng file:dòng>

3. CHECKLIST CHẤT LƯỢNG
   - [số] <mục>: PASS / FAIL — <dẫn chứng>

4. LỖI PHÁT HIỆN (theo thứ tự ưu tiên)
   - [Chặn] <mô tả> — <file:dòng> — cách tái hiện: <...>
   - [Nên sửa] <mô tả> — <file:dòng>

5. KẾT LUẬN
```

Kết thúc báo cáo bằng **đúng một** dòng, không thêm chữ nào khác ở cuối:

    VERDICT: APPROVE
    VERDICT: REJECT
    VERDICT: ESCALATE

---

## 4. Quy Tắc Chấm

- **REJECT** nếu bất kỳ mục **Bắt buộc** nào FAIL, hoặc thiếu bằng chứng thực thi.
- **ESCALATE** nếu: đặc tả gốc mâu thuẫn/thiếu tới mức không thể chấm, hoặc phát hiện
  vấn đề hệ thống vượt phạm vi task.
- **APPROVE** chỉ khi mọi mục Bắt buộc PASS và đã tự chạy lại bằng chứng.
- Native app workflow: Spec/human signoff và manifest source/test/config phải khớp snapshot hiện tại, kể cả thay đổi chưa commit. Actor QA khác Builder; identity khai báo không thay chứng minh context độc lập của runtime.
- Evidence gồm command ID, command, cwd absolute trong project, ac_ids, exit code, output file/hash; khớp signed verification_commands với cwd root-relative. Exit code 0 không tự suy ra APPROVE. Mọi applicable AC, kể cả non-UI, phải PASS có evidence; N/A chỉ cho Spec applicable false kèm na_reason. UI yêu cầu local preview và browser evidence từng AC.
- **Frontend UI & Anti-Patterns (Impeccable):** Với task có giao diện Web / Frontend, QA Auditor bắt buộc chạy detector của Impeccable (`node plugins/impeccable/skills/impeccable/scripts/detect.mjs --json <targets>`) để rà soát 59 detector rules. Bất kỳ vi phạm primary anti-pattern nào chưa được cấu hình miễn trừ hợp lệ đều phải bị đánh REJECT.
- PARTIAL_APPROVE chỉ khi có applicable UI AC NOT_VERIFIED và toàn bộ non-UI PASS/commands hợp lệ. AUDIT_PENDING_BROWSER không được tạo để bỏ QA; verify-browser đối soát pending IDs/URL cũ và cả logs/evidence/source hiện tại. Design không có partial verdict.
- Git diff chỉ hỗ trợ đọc; QA kiểm cùng checkout chứa staged/unstaged/untracked, không audit mỗi committed HEAD. Runtime/log/cache exclusion theo policy Spec; generated build/dist/.next chỉ loại khi kê khai, nested source collision vẫn included.
- REJECT thứ hai của pha audit chuyển ESCALATED; counters tồn tại qua resubmit/restart. CLI kiểm dữ liệu checkpoint, không tự xác thực hành động người dùng hay kiểm trình duyệt.
- Mỗi lỗi phải kèm **vị trí cụ thể** và **cách tái hiện**; REJECT chung chung là báo cáo lỗi.
- QA Auditor **không được sửa code** — chỉ nêu lỗi và yêu cầu Builder sửa.
