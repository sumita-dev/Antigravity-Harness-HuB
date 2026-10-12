---
name: subagent-driven-development
description: Thực thi kế hoạch bằng cách chia nhỏ thành các task độc lập, mỗi task một subagent kèm review và Progress Ledger.
---

# Phát Triển Theo Tác Tử Con (Subagent-Driven Development - SDD)

## Tổng Quan (Overview)

Thực thi kế hoạch kiến trúc bằng cách bẻ nhỏ công việc thành các nhiệm vụ độc lập (independent tasks). Mỗi nhiệm vụ được bàn giao cho một tác tử con (subagent implementer) sở hữu ngữ cảnh cô lập (fresh context), tiếp nối bằng một vòng review độc lập và ghi nhận tiến độ liên tục vào Progress Ledger.

**Nguyên tắc cốt lõi:**
- Fresh subagent trên từng task: Không làm ô nhiễm ngữ cảnh (context pollution).
- Kiểm soát tiến độ qua sổ cái (Progress Ledger): Phục hồi hoàn hảo sau context compaction.
- Vòng lặp sửa lỗi có kiểm soát (Fix-Loop cap): Tối đa 5 vòng với cơ chế nâng cấp model (model escalation).
- Đánh giá toàn nhánh ở cuối chu trình (Whole-branch final review).

## Cơ Chế Sổ Cái Tiến Độ (Progress Ledger)

Ngữ cảnh hội thoại của AI có thể bị nén (compaction) hoặc mất dấu khi tác vụ kéo dài. Do đó, toàn bộ trạng thái thực thi SDD phải được lưu bền vững vào file sổ cái:

- Đường dẫn file: `.harness/sdd/progress.md` (hoặc thư mục workspace riêng biệt của kế hoạch).
- Dòng định danh đầu tiên: `# SDD Ledger — plan: <đường dẫn plan>`
- Định dạng ghi nhận:
  + Bắt đầu task: `Task <N>: started (<mô tả ngắn>)`
  + Vòng sửa lỗi: `Task <N>: fix round <R>/5 (<X> addressed, <Y> open; commits <base>..<head>)`
  + Hoàn thành task: `Task <N>: complete (commits <base>..<head>, review clean)`
  + Phán quyết hoãn/park: `Task <N>: parked — <vấn đề> — Ruling: <lý do chấp nhận>`

Khi khôi phục phiên sau compaction: Đọc trực tiếp sổ cái `progress.md` và `git log` để xác định task tiếp theo cần chạy, tuyệt đối không re-dispatch lại các task đã có trạng thái `complete`.

## Quy Trình Vận Hành Từng Task (The Task Loop)

1. **Bẻ nhỏ & Đóng gói Task Brief:**
   - Trích xuất yêu cầu cụ thể, giá trị hằng số, chữ ký hàm và ca kiểm thử cho từng task.
   - Giao việc cho Implementer kèm đường dẫn brief và file báo cáo (report path).
   - Implementer không tự ý spawn subagent khác.

2. **Thực thi & Tự kiểm thử (Implementation & Self-Testing):**
   - Implementer viết mã nguồn, viết test tương ứng, chạy test chứng minh xanh và commit.
   - Trả về báo cáo gồm: trạng thái (`DONE` hoặc `DONE_WITH_CONCERNS`), commit hash và kết quả test.

3. **Thẩm định nhiệm vụ (Task-Scoped Review):**
   - Khởi chạy Reviewer độc lập thẩm định 2 chiều bắt buộc: Tuân thủ Spec (Spec Compliance) VÀ Chất lượng mã nguồn (Task Quality).
   - Reviewer đối soát trực tiếp diff commit với brief và các ràng buộc toàn cục.

4. **Vòng lặp sửa lỗi (Fix-Loop tối đa 5 vòng):**
   - Nếu phát hiện lỗi Spec ❌ hoặc lỗi nghiêm trọng (Critical/Important), kích hoạt vòng lặp sửa lỗi.
   - **Vòng 1 - 3:** Tiếp tục giao cho implementer ban đầu sửa (tận dụng ngữ cảnh đã hiểu rõ code).
   - **Vòng 4 - 5 (Model Escalation):** Nếu sau 3 vòng vẫn chưa giải quyết dứt điểm, khởi chạy Implementer mới với model mạnh hơn một bậc (ví dụ nâng từ Flash lên Pro) để phá vỡ bế tắc tư duy.
   - Mỗi vòng sửa đều chạy re-review kiểm chứng.
   - Nếu chạm mốc vòng 5 mà vẫn còn điểm chưa giải quyết: Trọng tài (Quản đốc/Architect) phân xử (adjudicate), ghi rõ `Ruling:` vào sổ cái và chỉ dừng lại nếu toàn bộ các hướng tiếp theo đều là phỏng đoán.

5. **Nghiệm Thu Toàn Nhánh (Whole-Branch Final Review):**
   - Khi tất cả các task đã `complete`, kích hoạt đợt review toàn diện trên toàn bộ nhánh so với base branch bằng model mạnh nhất.
   - Nếu có phát hiện lỗi, gom thành MỘT đợt sửa duy nhất (single fix wave) để tối ưu chi phí.
