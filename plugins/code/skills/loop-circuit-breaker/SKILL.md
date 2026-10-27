---
name: loop-circuit-breaker
description: "Cơ chế ngắt mạch tự động chống lặp vô hạn, chống cháy token và kẹt tiến độ."
user_invocable: false
---
# Loop Circuit Breaker & Safety Protocol

Skill này cung cấp các thuật toán bảo vệ cơ học dành riêng cho **Controller / Orchestrator (Agent Điều Phối)** trong suốt quá trình điều phối Subagent.

---

## 1. Cơ Chế Ngắt Mạch (Circuit Breakers)

### A. Quy tắc Chống Kẹt Lỗi (Stagnation Breaker - Ngưỡng 3 lần)
- **Định nghĩa:** Khi một subagent (`tdd-guide` hoặc `build-error-resolver`) thực hiện sửa đổi nhưng gặp lại **cùng một thông điệp lỗi hoặc mã lỗi compile/test** trong 3 lần liên tiếp.
- **Hành động bắt buộc:**
  1. **TRIP CIRCUIT BREAKER (NGẮT MẠCH NGAY LẬP TỨC):** Nghiêm cấm dispatch subagent thử lần thứ 4.
  2. **Cắt tỉa lỗi (Pruning):** Trích xuất tối đa 8 dòng quan trọng nhất của lỗi (bỏ các dòng log thừa và stack trace lặp).
  3. **Escalate to Human (Báo cáo Sếp):** Chuyển trạng thái sang `ESCALATE_HUMAN`, thông báo cho Sếp kèm phân tích nguyên nhân gốc rễ (Root Cause) và các phương án xử lý để Sếp ra quyết định.

### B. Quy tắc Bế Tắc Tiến Độ (No-Progress Breaker - Ngưỡng 5 lần)
- Sau 5 lần dispatch sửa đổi mà số lượng test pass không tăng lên hoặc xuất hiện thêm nhiều lỗi mới $\rightarrow$ Dừng ngay chu trình, đánh giá lại kiến trúc (Architect Review) thay vì tiếp tục code vá víu.

### C. Quy tắc Cầu Dao Thời Gian Nền & Dead-man's Switch Watchdog (Execution Time Breaker)

#### Scaffolding Script Kiểm Định AST Vòng Lặp & Đệ Quy (Dune Invariant)
Phân tích tĩnh AST phát hiện `while True` thiếu break/timeout và đệ quy thiếu base case:
```bash
python plugins/code/skills/loop-circuit-breaker/scripts/check_loop_thresholds.py [files...]
```
Script kiểm định: [check_loop_thresholds.py](./scripts/check_loop_thresholds.py).
- **Định nghĩa:** Khi một lệnh thực thi chuyển thành tiến trình chạy ngầm (`task-...` qua `run_command`) hoặc khi dispatch tác vụ nặng (>1 phút), Quản đốc rơi vào trạng thái ngủ đông chờ Reactive Wakeup. Nếu tiến trình con bị deadlock hoặc treo hộp thoại modal ngầm (như Word/Excel COM, crawler, compile vô hạn), runtime Antigravity sẽ không bao giờ phát tín hiệu wakeup nếu không có timeout.
- **Hành động bắt buộc (Dead-man's Switch Watchdog):**
  1. **Kích hoạt chuông đánh thức dự phòng:** Tác tử BẮT BUỘC gọi ngay công cụ `schedule(DurationSeconds=240)` (hoặc `45s` cho task nhanh) kèm Prompt rõ ràng làm Dead-man's Switch: `"[DEAD-MAN SWITCH] Kiểm tra tiến độ background task <task_id>. Nếu chưa xong hoặc kẹt thì ngắt mạch."`.
  2. **Xử lý khi được đánh thức:** Khi timer kích hoạt và đánh thức Quản đốc:
     - Gọi `manage_task(Action="list")` kiểm tra trạng thái task.
     - Nếu task vẫn `RUNNING` mà không có tiến độ mới hoặc chạm ngưỡng timeout: Lập tức gọi `manage_task(Action="kill", TaskId=...)`.
     - Quét và diệt triệt để tiến trình con treo: `taskkill /F /IM WINWORD.EXE` hoặc `Stop-Process -Name "WINWORD", "EXCEL" -Force`.
     - Kích hoạt trạng thái `TRIP CIRCUIT BREAKER (ESCALATED)`, báo cáo bằng chứng và nguyên nhân ngắt mạch ngay cho Sếp thay vì để tiến trình treo âm thầm.

---

## 2. Chuẩn Hóa Báo Cáo Kiểm Định Độc Lập (Adversarial Verifier)

Khi Controller gọi `code-reviewer` hoặc `security-reviewer`, kết quả trả về bắt buộc phải tuân theo mẫu đóng:

```markdown
## VERDICT: APPROVE | REJECT | ESCALATE_HUMAN

### 1. Test Evidence (Bằng chứng thực thi)
- Test Command: `npm test` / `pytest` (hoặc lệnh tương ứng của project)
- Kết quả: X passed, Y failed (BẮT BUỘC có snippet output thực tế)

### 2. Scope Audit (Phạm vi ảnh hưởng)
- Files Changed: N files (So sánh với yêu cầu spec ban đầu)
- Denylist Check: PASS (Không sửa đổi file nhạy cảm .env, auth, secrets)

### 3. Anti-Cheating Check (Chống gian lận test)
- Phát hiện test bị skip/disable/mock giả tạo: KHÔNG (PASS)

### 4. Lý do (Nếu REJECT / ESCALATE_HUMAN)
- Nêu rõ các điểm chưa đạt và gợi ý sửa đổi cụ thể cho implementer.
```

**Nguyên tắc vàng của Verifier:**
* Luôn giữ lập trường **REJECT** cho đến khi có bằng chứng thực nghiệm rõ ràng.
* Không tin vào lời khẳng định "Code đã chạy tốt" của Implementer nếu thiếu log kết quả test thật.

---

## 3. Quản Lý Trạng Thái Bền Vững (`STATE.md`)

Mỗi khi một Task hoặc Milestone được nghiệm thu `APPROVE`:
1. Controller tự động cập nhật file `STATE.md` tại root dự án.
2. Ghi nhận rõ: Task đã xong, commit liên quan, kết quả test hiện tại.
3. Giúp Sếp hoặc bất kỳ session nào sau này mở lên đều nắm được bức tranh tổng thể chỉ trong 1 giây mà không tốn token nạp lại toàn bộ lịch sử chat.
