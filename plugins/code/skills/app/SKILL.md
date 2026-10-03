---
name: app
description: >
  🏭 Unified App Loop: Từ ý tưởng sơ bộ hoặc brief chi tiết tới bản MVP chạy thử. Phỏng vấn/thẩm định đặc tả, duyệt 1 lần duy nhất, sau đó tự động code và kiểm thử tới khi có preview URL.
  TRIGGERS: 'build app', 'làm app', 'tạo ứng dụng', 'xây dựng web tool', 'làm MVP', 'phát triển app từ brief', 'app loop'.
---
> ⚠️ **TRẠNG THÁI SKILL (đã kiểm chứng):** các tài liệu tham chiếu dưới đây
> (`AI_CODE_WORKFLOW.md`, `references/coding-taste.md`, `references/engineering-standards.md`,
> `templates/app-spec.md`, `docs/superpowers/specs/...`) **KHÔNG có trong repo này**.
> Agent phải bám theo nội dung ngay trong SKILL.md và không được viện dẫn các file không tồn tại.


# WORKFLOW: /app - Unified App Loop (v1.28.0)

**Role:** Controller. Do not write app code in this chat.  
**Source of truth:** `docs/superpowers/specs/2026-09-30-mvp-app-loop-design.md` and `AI_CODE_WORKFLOW.md`.  
**Reasoning Protocol:** Tích hợp kỷ luật tư duy từ skill `fable-thinking` xuyên suốt toàn bộ quy trình.

`/app` là Unified App Loop (Vòng lặp ứng dụng hợp nhất), thống nhất xử lý cả ý tưởng sơ bộ lẫn bản brief có sẵn tới bản chạy thử (runnable preview).

Python does not call `invoke_subagent`. Each turn runs `python scripts/app-loop.py next` and does only the printed block, then stops.

## Phase 1 — Specification & Intake (Fable-Grounded Intake)

Hỗ trợ 2 luồng tiếp nhận đầu vào:
1. **Raw idea / Vibe input (Ý tưởng sơ bộ):** Tiến hành phỏng vấn tương tác (interactive interview) để làm rõ mục tiêu, tác nhân, giao diện, dữ liệu và tiêu chí nghiệm thu từ `templates/app-spec.md` cho tới khi:
   ```bash
   python scripts/spec-gate.py --spec apps/<slug>/docs/spec.md --allow-draft
   ```
   thoát mã 0. Stack là một trong các starter: `nextjs-tailwind-sqlite`, `fastapi-sqlite`, `vanilla-tools`, `python-cli`.
2. **Existing brief input (Brief chi tiết có sẵn):** Nạp trực tiếp bản mô tả vào `apps/<slug>/docs/spec.md` và thẩm định nhanh bằng `python scripts/spec-gate.py --spec apps/<slug>/docs/spec.md`. Nếu thiếu tiêu chí bắt buộc hoặc chưa cụ thể (vague expected), bổ sung hoàn thiện trước khi trình duyệt.

### Chốt chặn The Floor & Kỷ luật Đặc tả (Fable Intake Discipline)
Trước khi chốt `apps/<slug>/docs/spec.md`, bắt buộc vượt qua chốt chặn **The Floor** với 3 bước nghiêm ngặt:
1. **Goal:** Định nghĩa chính xác trạng thái đích (end-state) của hệ thống trong thế giới thực ("*đối tượng* đã được *xử lý xong*"), tuyệt đối không nhầm lẫn với các mốc trung gian (milestones như "đã gửi request", "đã hiển thị form", "chọn phương án A").
2. **Follow-through:** Chạy mô phỏng (run the movie) toàn bộ hành trình trải nghiệm người dùng đến khung hình cuối cùng (final frame) nơi trạng thái đích được kiểm chứng thực tế. Kiểm kê toàn bộ đối tượng, công cụ và kênh phụ thuộc xem có thực sự hiện diện và hoạt động liền mạch hay không.
3. **Leftovers:** Rà soát triệt để mọi chi tiết trong brief ban đầu. Không bỏ sót bất kỳ ràng buộc hay chi tiết nào; nếu có chi tiết không dùng tới, phải lý giải rõ ràng lý do. Coi trọng các danh từ chỉ đối tượng nghiệp vụ hơn các con số gây xao nhãng.

### Kỷ luật khẳng định (Claim Discipline) trong Spec
Toàn bộ dữ liệu và tiêu chí nghiệm thu (Acceptance Criteria - AC) trong bản đặc tả phải tuân thủ phân định minh bạch theo **Claim Discipline**:
- **OBSERVED:** Dữ liệu, hành vi đã trực tiếp đo đạc, kiểm chứng từ codebase/starter.
- **DERIVED:** Suy luận logic từ các thực tế đã quan sát kèm cơ chế rõ ràng.
- **PRIOR:** Kiến thức huấn luyện hoặc quy ước sẵn có — phải kiểm tra lại nếu là yếu tố chịu tải (load-bearing).
- **ASSUMED:** Giả định chưa kiểm chứng bắt buộc phải nêu rõ rủi ro nếu sai. Cấm để giả định núp bóng câu khẳng định quan sát.

**Duyệt đặc tả duy nhất 1 lần:** Dừng lại hỏi người dùng DUY NHẤT một lần để xác nhận đặc tả (`SIGN_OFF: approved`). Sau khi được duyệt:

```bash
python scripts/app-loop.py approve-spec --root . --slug <slug>
```

## Phase 2 — Autonomous Build & Verification (Fable-Disciplined Pair Pod)

Sau khi `SIGN_OFF: approved`, vòng lặp tự động hóa hoàn toàn — không đặt thêm câu hỏi hay làm phiền người dùng.

```bash
python scripts/app-loop.py next --root . --slug <slug>
```

Follow `DO` / `THEN`. Dispatch with:

```text
python scripts/dispatch-brief.py --root . --app apps/<slug> --task-id <id> --role <role> --kind <kind>
python scripts/subagents-loader.py --export-schema <role>
define_subagent(<JSON>)
invoke_subagent(TypeName="<role>", Workspace="inherit", ...)
```

Maker is `tdd-guide`. Checker is `code-reviewer`. Workspace is `inherit` on `feature/app-<slug>`. Do not open a second worktree.

### Tiêu chuẩn Kỹ thuật Pair Pod (`fable-thinking`)
Chỉ thị Pair Pod áp dụng nghiêm ngặt các tiêu chuẩn kỹ thuật từ `fable-thinking` (tham chiếu `references/coding-taste.md` và `references/engineering-standards.md`):
- **Maker (`tdd-guide`):**
  - Viết bài test phân định (**Discriminating Tests**): Thiết kế các ca kiểm thử nhằm phân biệt rạch ròi giữa các giả thuyết lỗi và kiểm tra trường hợp biên (boundary, empty, typical, malformed, concurrent), loại bỏ hoàn toàn thiên kiến tìm kiếm sự xác nhận (confirmation seeking).
  - Cấm phán đoán theo khuôn mẫu quen thuộc (**Template Hijack**): Không áp dụng máy móc các giải pháp theo thói quen mà phải bám sát ràng buộc cơ học cụ thể của bài toán.
  - Sửa đổi phẫu thuật (surgical edits), duy trì sổ cái bất biến (*invariant ledger*: preserves, breaks, risks).
- **Checker (`code-reviewer`):**
  - Kiểm chứng chẩn đoán lỗi bằng chứng cứ thực nghiệm Terminal (**Claim Discipline**): Mọi nhận định review và kết luận phải dựa trên log Terminal, kết quả chạy lệnh test thực tế, không chấp nhận suy đoán lý thuyết.
  - Chống thiên kiến hình thức (**Surface Blindness**): Không đánh giá code qua cảm tính hay đọc lướt token; bắt buộc kiểm chứng cơ học (mechanical verification) từng đơn vị cấu trúc và ràng buộc cứng.

Submission includes `PRODUCT_SPEC`, `PRODUCT_SPEC_SHA256`, `ACCEPTANCE`, and `SCOPE`. Review includes `SPEC_CHECK: AC-00N met|missing|extra` for every accepted id. `missing` and `extra` block `APPROVE`. Cap is tối đa 2 vòng via `python scripts/pair-pod.py`.

## Phase 3 — Preview & Handoff (Receipt-Backed Delivery)

Trước khi đóng dấu `MVP_READY`, bắt buộc kích hoạt 2 chốt chặn chất lượng:
1. **Self-Review Gate:** Trả lời dứt khoát bảng câu hỏi tự kiểm tra:
   - Sản phẩm có thực sự tạo ra trạng thái đích (Goal end-state) qua mô phỏng follow-through hoàn chỉnh không?
   - Mọi tuyên bố chất lượng có căn cứ thực tế (OBSERVED/DERIVED) hay không?
   - Đã chạy các bài kill-test để thử đánh sập mã nguồn/tính năng chưa?
   - Sự tự tin có vượt quá bằng chứng thực nghiệm thu thập được không?
2. **Constraint Loop:** Cơ học kiểm chứng toàn bộ các ràng buộc cứng (hard output constraints): định dạng route, kiểu dữ liệu, các tiêu chuẩn loại trừ bằng công cụ/script kiểm tra tự động trước khi đóng gói.

### Nghiệm thu bàn giao (Receipt-Backed Handoff)
- Áp dụng cơ chế **Receipt-backed Handoff**: Chỉ cung cấp URL preview khi có đầy đủ biên bản kiểm chứng thực tế (**Receipt**):
  - Log HTTP 200 cho toàn bộ các route `SCR-` từ `python scripts/preview-check.py` mà không gặp bất kỳ gián đoạn nào.
  - Standard output (stdout) của các lệnh route test và health-check thực tế từ Terminal.
- Bàn giao cho người dùng URL và danh sách màn hình đã kiểm thử thành công. Tuyệt đối không tự ý deploy.

## Stop and ask only when

`next` prints `PHASE: escalate`, the spec hash changed, a secret or data deletion appears, the user asks to deploy, the same test command fails twice, or round 2 is `REJECT`.
