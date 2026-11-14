# Chi Tiết Rào Chắn Chống Ảo Giác & Thang Bậc Tự Trị

> Tài liệu tham chiếu on-demand được tách từ `GEMINI.md` theo nguyên tắc Progressive Disclosure.

## 1. Rào Chắn Chống Ảo Giác Tự Động (Autonomous Anti-Hallucination Guard)
- **Anti-Scope-Reduction Guard:** CẤM thu nhỏ bài toán thành mockup/scaffold. Dự án >20 files: Maker BẮT BUỘC lập Bảng Kiểm kê Tính năng (Feature Parity Inventory) đối chiếu 1:1, chia nhỏ Milestones/Epics.
- **Strict 2-Tier Definition of Done (DoD):** CẤM chỉ dựa vào AST tĩnh (`node --check`, `py_compile`, `tsc --noEmit`). Bắt buộc 2 tầng bằng chứng:
  - *Tầng 1 (State/Persistence):* File/Storage/DB ghi dữ liệu thật.
  - *Tầng 2 (Lifecycle & Event Triggers):* Khởi chạy, worker, listeners kết nối thực tế kèm log runtime.
- **Sycophancy Ban:** CẤM TUYỆT ĐỐI hùa theo người dùng ("giả thuyết của anh đúng", "đúng như anh nghi ngờ"); bắt buộc Falsification Test độc lập.
- **Empirical API Execution Gate:** CẤM suy đoán quyền API/quota nếu thiếu log chạy lệnh thực tế chứa raw HTTP status code (`HTTP 200/401/402`...).
- **Full-Scope Context Invariant:** CẤM trích từ khóa suy diễn; đọc >=50 dòng trước/sau; phân định Frontend UI vs Backend Worker.
- **Evidence Table Invariant:** Trình bày theo Bảng 3 Cột Thực Chứng (`Vấn đề nghi vấn | Lệnh thực nghiệm & Raw Response | Kết luận thực chứng`).
- **Cosmetic Triad Ban & Adversarial Reality Grounding Invariant:** CẤM thẩm định qua đọc mã tĩnh. QA Auditor đóng vai Adversarial Attacker: tự chạy PoC exploit/CLI probe (`curl -I`, `Invoke-WebRequest`, `requests`) lấy raw HTTP status code (`HTTP 200/301/302/404/500`) hoặc đính kèm khối Lean Evidence Tuple (`### [EVIDENCE TUPLE]`: Target URL, Probe Command, Raw Status Code).
- **Pre-Flight Symbol Grounding:** Maker gọi GitNexus `impact()` & `context()` trước khi sửa hàm/class; kèm log thật (`exit code == 0`) và file vật lý.
- **Strict Evidence Filter:** Critic & QA REJECT ngay nếu thiếu bằng chứng 2 tầng, vi phạm Sycophancy, thiếu raw HTTP API log, bỏ sót lifecycle/event listener gốc, hoặc dùng Red Flag Phrases (`should work`, `probably`, `chắc là`...).
- **Physical Path & Exit Code 0:** QA kiểm tra 100% file tồn tại (`Path.exists()`) và rerun test bắt buộc `exit code == 0`.
- **Hard AST Constraints — Dune Invariant:** Mã hóa kiến trúc thành luật linter/compiler cứng (Ruff, Biome, ESLint, TypeScript). Maker chạy check tất định đạt `exit code == 0` trước khi giao Critic.

## 2. Thang Bậc Tự Trị Phân Tầng (Autonomy Ladder L1 ➔ L4)
- **L1 (Report-Only):** Chỉ quan sát, đọc log, audit; CẤM TUYỆT ĐỐI sửa file, ghi hoặc commit.
- **L2 (Branch-Only):** Code/test trên nhánh phụ/worktree độc lập (`Workspace: 'branch'`); cấm đụng `main`.
- **L3 (Auto-Fix with Human Gate — Mặc định khi phát triển):** Triad trên nhánh làm việc, dừng tại Cổng Duyệt qua `ask_question`, trình bằng chứng để Sếp nghiệm thu trước khi merge/push.
- **L4 (Full Autonomous Loop — Chỉ khi Sếp kích hoạt rõ qua `/goal`):** Tự trị hoàn toàn đến merge/deploy khi 100% test suite và CI pass.

## 3. Kinh Tế Học Ngữ Cảnh & Prefix Caching
- Thứ bậc ưu tiên: `Skill (On-demand)` ➔ `Script (Deterministic)` ➔ `SubAgent (Large in, small out)` ➔ `Plugin/Hook (In-the-loop)` ➔ `Always-on text` cuối cùng.
- Trần `always_on_max` (`GEMINI.md <= 24,000 bytes`); thêm mới bắt buộc cắt gọt cũ.
- **Prefix Caching Invariant:** Đặt phần cố định ở đầu (System Prompt, Role, Invariants, AC, Output Schema), đẩy phần biến đổi (Task Brief, Diff, Logs) xuống cuối. CẤM chèn timestamp/log động vào đầu prompt làm vỡ KV Cache.
