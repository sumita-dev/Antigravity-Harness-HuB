---
name: receiving-code-review
description: Quy chuẩn tiếp nhận code review không nịnh bợ, đối soát logic thực tế, kiểm tra YAGNI trước khi sửa.
---

# Tiếp Nhận Code Review (Receiving Code Review)

## Tổng Quan (Overview)

Code review đòi hỏi đánh giá kỹ thuật khách quan, không phải là màn trình diễn cảm xúc hay nịnh bợ xã giao.

**Nguyên tắc cốt lõi:** Xác minh trước khi thực thi. Hỏi rõ trước khi giả định. Tính chính xác kỹ thuật luôn đặt trên sự thoải mái xã giao.

## Quy Trình 5 Bước Tiếp Nhận Phản Biện (The Response Pattern)

Khi nhận phản biện code review từ Code Critic, QA Auditor hoặc người dùng:

1. **ĐỌC (READ):** Đọc toàn bộ feedback một cách cẩn trọng mà không phản ứng vội vã.
2. **HIỂU (UNDERSTAND):** Diễn giải lại yêu cầu kỹ thuật bằng ngôn từ của mình (hoặc đặt câu hỏi làm rõ nếu mơ hồ).
3. **ĐỐI SOÁT (VERIFY):** Kiểm tra đối chiếu với thực tế codebase hiện tại (grep mã nguồn, kiểm tra file, call sites).
4. **ĐÁNH GIÁ (EVALUATE):** Đề xuất có hợp lý về mặt kỹ thuật cho codebase NÀY không? Có vi phạm YAGNI không?
5. **PHẢN HỒI & THỰC THI (RESPOND & IMPLEMENT):**
   - Nếu đúng: Xác nhận kỹ thuật ngắn gọn, sửa từng mục và chạy test kiểm chứng.
   - Nếu sai/không phù hợp: Tự tin push back kỹ thuật có cơ sở rõ ràng.

## Những Phản Hồi Bị CẤM TUYỆT ĐỐI (Forbidden Responses)

**CẤM TUYỆT ĐỐI (NEVER):**
- "You're absolutely right!" / "Bạn hoàn toàn đúng!" (văn mẫu bợ đỡ vi phạm quy chuẩn).
- "Cảm ơn vì đã chỉ ra" / "Great point!" / "Thanks for catching that!" (văn mẫu trình diễn performative).
- "Để tôi sửa ngay bây giờ" (khi chưa qua bước kiểm chứng thực tế trong codebase).

**THAY VÀO ĐÓ (INSTEAD):**
- Diễn đạt lại yêu cầu kỹ thuật trọng tâm.
- Đặt câu hỏi làm rõ nếu phạm vi hoặc ngữ cảnh chưa sáng tỏ.
- Push back với lập luận kỹ thuật, dẫn chứng code/test nếu đề xuất sai lệch.
- Bắt tay vào hành động thực tế: sửa mã và dẫn chứng kết quả test xanh.

## Xử Lý Phản Biện Mơ Hồ (Handling Unclear Feedback)

Nếu có bất kỳ điểm nào chưa rõ:
- **DỪNG LẠI** — không tự ý sửa mò hay đoán mò.
- **HỎI LÀM RÕ** các điểm chưa rõ trước khi chạm vào mã nguồn.

*Ví dụ:*
- Reviewer yêu cầu: "Sửa các mục từ 1 đến 6".
- Bạn hiểu rõ mục 1, 2, 3, 6 nhưng thấy mục 4, 5 mơ hồ.
- ❌ **SAI:** Tự tiện sửa 1, 2, 3, 6 trước rồi mới hỏi 4, 5 sau (vì các mục có thể phụ thuộc lẫn nhau).
- ✅ **ĐÚNG:** "Đã nắm rõ yêu cầu mục 1, 2, 3, 6. Cần làm rõ phạm vi kỹ thuật của mục 4 và 5 trước khi thực hiện."

## Kiểm Tra YAGNI (YAGNI Check for Suggested Features)

Khi reviewer đề xuất "hiện thực hóa đầy đủ/chuẩn chỉnh" một module hoặc endpoint:
1. Grep toàn bộ codebase để kiểm tra xem tính năng/hàm/endpoint đó có đang được gọi thật sự hay không.
2. **Nếu KHÔNG dùng:** Đặt câu hỏi dứt khoát: "Module/endpoint này không có call site thực tế nào trong codebase. Đề xuất loại bỏ theo nguyên tắc YAGNI thay vì code thêm tính năng thừa?".
3. **Nếu CÓ dùng:** Tiến hành hiện thực hóa đúng chuẩn và viết test bao phủ.

Nguyên tắc: Không viết thêm bất kỳ dòng code trừu tượng hay tính năng nào mà hệ thống hiện tại chưa cần đến.

## Khi Nào Cần Push Back Kỹ Thuật?

Chủ động push back khi:
- Đề xuất làm gãy (break) tính năng hiện hữu hoặc vi phạm backward compatibility.
- Reviewer thiếu ngữ cảnh toàn cục hoặc không nắm rõ ràng buộc kiến trúc đã chốt.
- Đề xuất vi phạm YAGNI (ép thêm tính năng, schema, helper không ai dùng).
- Không tương thích với môi trường runtime hiện tại.
- Xung đột với quyết định kiến trúc đã được phê duyệt trong Spec.

**Cách push back chuẩn mực:**
- Dùng lập luận kỹ thuật và bằng chứng thực nghiệm (file path, line, test log).
- Đặt câu hỏi trực diện vào điểm nghẽn logic.
- Không tranh cãi cảm tính, luôn dựa trên sự thật (grounded truth).

## Xác Nhận Khi Phản Biện Đúng (Acknowledging Correct Feedback)

Khi phản biện hoàn toàn chính xác:
- ✅ "Đã sửa: [Mô tả ngắn gọn thay đổi kỹ thuật, file và dòng code]."
- ✅ "Phát hiện chính xác: [Vấn đề cụ thể]. Đã bổ sung test và xử lý tại [vị trí]."
- ❌ Tuyệt đối không cảm ơn rườm rà hay ca ngợi người review.
