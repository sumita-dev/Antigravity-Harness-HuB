---
name: diagnosing-harness
description: Chẩn đoán và kiểm toán phiên làm việc của tác tử (đọc transcript, phát hiện lặp, cháy token, lệch kế hoạch).
---

# Kiểm Toán Phiên Làm Việc Tác Tử (Diagnosing Harness)

## Tổng Quan (Overview)

Chẩn đoán và kiểm toán chi tiết những gì đã diễn ra trong một phiên làm việc của tác tử (session audit): phát hiện lặp lại công việc vô ích, cháy token, chệch hướng kế hoạch, kẹt vòng lặp hoặc thất bại không rõ nguyên nhân.

**Nguyên tắc cốt lõi:**
- Mọi phát hiện đều phải trích dẫn chính xác `path:line` từ log transcript thực tế. Không có trích dẫn `path:line` thì không công nhận kết luận.
- Mọi con số thống kê (token, thời gian, số turn) phải lấy trực tiếp từ transcript hoặc lệnh phân tích, không ước lượng cảm tính.
- Tuyệt đối chỉ đọc transcript ở chế độ Read-Only, không sửa đổi hay xóa file log của hệ thống.

## Vị Trí Transcript Hệ Thống

Trong môi trường Antigravity, log hội thoại được lưu tại đường dẫn thư mục AppData:
- Thư mục session: `.gemini/antigravity/brain/<session-id>/.system_generated/logs/`
- File transcript cô đọng: `transcript.jsonl`
- File transcript đầy đủ: `transcript_full.jsonl`

Cấu trúc mỗi dòng trong transcript gồm các trường metadata chuẩn: `step_index`, `source`, `type`, `status`, `created_at`, `content`, `thinking`, `tool_calls`.

## Phân Tích 7 Chiều Toàn Diện (The 7 Audit Dimensions)

Khi kiểm toán phiên làm việc, tiến hành rà soát theo 7 chiều kỹ thuật:

1. **Dòng Thời Gian Kỹ Năng (Skill Timeline):**
   - Theo dõi thứ tự kích hoạt các skill và subagent theo thời gian.
   - Kiểm tra kỹ năng mong đợi có được kích hoạt đúng lúc không hay bị bỏ qua.

2. **Lặp Lại Công Việc (Repeated Work):**
   - Rà soát các lệnh gọi công cụ trùng lặp (ví dụ: view_file cùng một file nhiều lần mà không có thay đổi mã nguồn, lặp lại các lệnh grep/search vô ích).
   - Phát hiện các đoạn vòng lặp thử-sai không tiến triển.

3. **Bám Sát Kế Hoạch (Plan Adherence):**
   - Đối chiếu từng bước thực tế tác tử đã làm so với bản kế hoạch hoặc Spec ban đầu.
   - Phát hiện hiện tượng chệch hướng sau sự kiện nén ngữ cảnh (context compaction).

4. **Chi Phí & Thời Gian (Cost & Time):**
   - Thống kê thời gian thực thi (wall-clock duration) giữa các bước.
   - Xác định các bước làm bùng nổ token hoặc gây nghẽn tốc độ phản hồi.

5. **Trở Ngại & Vấp Ngã (Stumbles):**
   - Thu thập các lỗi tool failure, command exit code khác 0, và ngoại lệ hệ thống.
   - Phân tích nguyên nhân tác tử bị kẹt hoặc phải thử lại nhiều lần.

6. **Bằng Chứng Chất Lượng (Quality Evidence):**
   - Đối soát xem các kết luận hoàn thành có đi kèm bằng chứng chạy test thực tế hay chỉ là tuyên bố suông.
   - Kiểm tra xem output có bị cắt cụt (truncated) hoặc thiếu sót tiêu chí nghiệm thu không.

7. **Xung Đột Yêu Cầu (Request Conflicts):**
   - Phát hiện các mâu thuẫn giữa chỉ đạo của người dùng và các quy tắc hệ thống, hoặc giữa các yêu cầu được đưa ra trong các turn khác nhau.

## Báo Cáo Kiểm Toán & Đề Xuất Khắc Phục

Báo cáo kiểm toán phải tổng hợp ngắn gọn:
- Mã định danh phiên (Session ID) và phạm vi bước phân tích.
- Bảng tổng kết 7 chiều kèm trích dẫn chứng minh `transcript.jsonl:<dòng>`.
- Khuyến nghị tối ưu luồng điều phối và điều chỉnh prompt để tránh lặp lại sự cố.
