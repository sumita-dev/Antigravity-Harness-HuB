---
name: sdd-spec-kit
description: "Quy chuẩn Spec-Driven Development (SDD) từ GitHub Spec Kit: Specify -> Plan -> Tasks -> Implement kèm Hiến pháp dự án (Constitution) và Clarify trước khi lập trình."
---

# SDD Spec-Kit: Spec-Driven Development cho Antigravity 2.0

Kỹ năng này chuẩn hóa quy trình phát triển dựa trên đặc tả kỹ thuật (Spec-Driven Development) từ GitHub Spec Kit, lấp đầy khoảng trống ở giai đoạn tiền phát triển (Pre-development) cho vai trò Architect & Builder trong Antigravity Harness Hub.

---

## 1. Triết Lý Cốt Lõi: 4 Bước SDD Chuẩn

```
[Yêu cầu Người dùng] 
       │
       ▼
1. /specify ───► Sinh spec.md (User stories, Requirements, Constraints)
       │
       ▼
2. /plan    ───► Sinh plan.md (Architecture, Tech Stack, Verification Strategy)
       │
       ▼
3. /tasks   ───► Sinh tasks.md (Danh sách task độc lập, song song hoặc tuần tự)
       │
       ▼
4. /implement ─► Triển khai mã nguồn qua TDD (Red-Green-Refactor)
```

> [!IMPORTANT]
> **Nguyên tắc "Consult Before Mutate":**
> Nếu yêu cầu đầu vào chưa rõ ràng, BẮT BUỘC chạy pha **`clarify`** (phỏng vấn 1 câu/lượt, có giả thuyết và phương án lựa chọn) trước khi sinh `spec.md`.

---

## 2. Các Lệnh Điều Phối Chi Tiết

Tất cả các tài liệu chi tiết của từng lệnh được lưu trữ tại `references/`:

1. **`specify` ([references/specify.md](./references/specify.md)):**
   - Phân tích yêu cầu tự nhiên của người dùng.
   - Sử dụng template [specs/templates/spec-template.md](../../../../specs/templates/spec-template.md).
   - Xác định rõ User Scenarios, Functional Requirements, Non-Functional Requirements, Edge Cases.

2. **`clarify` ([references/clarify.md](./references/clarify.md)):**
   - Rà soát các điểm mơ hồ trong yêu cầu hoặc spec.
   - Đặt câu hỏi trắc nghiệm/ngắn gọn có kèm khuyến nghị để người dùng chốt phương án.

3. **`constitution` ([references/constitution.md](./references/constitution.md)):**
   - Thiết lập hoặc cập nhật Hiến pháp dự án theo [specs/templates/constitution-template.md](../../../../specs/templates/constitution-template.md).
   - Quy định các nguyên tắc bất di bất dịch (Non-negotiables): TDD, Versioning, Log format, Zero-poll, Security.

4. **`plan` ([references/plan.md](./references/plan.md)):**
   - Chuyển hóa `spec.md` thành `plan.md` theo [specs/templates/plan-template.md](../../../../specs/templates/plan-template.md).
   - Đối chiếu với Hiến pháp dự án và rào chắn kiến trúc (Architect Triad).

5. **`tasks` ([references/tasks.md](./references/tasks.md)):**
   - Phân rã `plan.md` thành các tác vụ thực thi cụ thể trong `tasks.md` theo [specs/templates/tasks-template.md](../../../../specs/templates/tasks-template.md).
   - Đánh dấu các tác vụ có thể chạy song song (Parallelizable: `[P]`) để phục vụ Fan-Out.

6. **`implement` ([references/implement.md](./references/implement.md)):**
   - Thực thi từng task trong `tasks.md` theo chu trình Red-Green-Refactor.

---

## 3. Tích Hợp Vào Triad Protocol

- **Vai trò Architect:** Chịu trách nhiệm thực hiện `specify`, `clarify`, `constitution`, và `plan`.
- **Vai trò Design Reviewer / Critic:** Chịu trách nhiệm review `spec.md` và `plan.md` trước khi bàn giao cho Builder.
- **Vai trò Builder:** Tiếp nhận `tasks.md` và chạy `implement`.
- **Vai trò QA Auditor:** Chạy verification test suite đối soát với acceptance criteria trong `spec.md`.
