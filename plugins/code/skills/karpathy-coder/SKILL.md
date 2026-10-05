---
name: karpathy-coder
description: "Áp dụng 4 nguyên lý lập trình thực dụng của Andrej Karpathy: Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution. Use when writing, refactoring, or debugging code to keep changes surgical and prevent over-engineering"
---

# Kỹ năng: Karpathy Coder

Kỹ năng này định hướng quá trình phát triển, tái cấu trúc (refactoring) và sửa lỗi (debugging) mã nguồn tuân thủ 4 nguyên lý thực dụng của Andrej Karpathy nhằm chống lại over-engineering và đảm bảo mã nguồn bền vững.

## 4 Nguyên lý cốt lõi

### 1. Think Before Coding (Nghĩ trước khi gõ)
- Không bắt đầu viết code ngay lập tức. Phải lập kế hoạch rõ ràng về luồng dữ liệu, kiến trúc và phạm vi tác động.
- Liệt kê các file bị ảnh hưởng và cách chúng tương tác trước khi thay đổi bất kỳ dòng code nào.

### 2. Simplicity First (Ưu tiên sự tối giản)
- Chọn giải pháp đơn giản nhất có thể giải quyết được vấn đề hiện tại.
- Tránh over-abstraction (trừu tượng hóa thái quá). Chỉ sử dụng tính năng có sẵn và cấu trúc dễ hiểu nhất thay vì đưa vào các pattern phức tạp không cần thiết.

### 3. Surgical Changes (Can thiệp cục bộ - "Phẫu thuật chính xác")
- Chỉ thay đổi chính xác những dòng code cần thiết cho tính năng hoặc lỗi đang giải quyết.
- Chống code lan man: KHÔNG TỰ Ý format lại toàn bộ file, KHÔNG sửa code style của các phần không liên quan.
- Kết quả Git diff phải sạch sẽ, dễ review, mọi dòng code thay đổi đều có thể truy vết về yêu cầu của task.

### 4. Goal-Driven Execution & Bugfix (Thực thi theo mục tiêu & sửa lỗi có cơ sở)
- Khi sửa bug, bắt buộc phải viết và chạy bài kiểm thử tự động (failing test case) tái hiện chính xác lỗi đó trước khi chạm vào mã nguồn chính (Goal-driven Bugfix).
- Mọi nỗ lực sửa lỗi đều phải dựa trên cơ sở là làm cho bài test chuyển từ FAILED sang PASSED.

## Hướng dẫn áp dụng

- **Trong lúc Code/Refactor**: Luôn tự hỏi "Giải pháp này có phải là đơn giản nhất chưa?". Nếu câu trả lời là chưa, hãy tìm cách tối giản nó.
- **Trong lúc Debug**: Đừng "đoán" lỗi và sửa mù. Hãy viết test tái hiện lỗi. Khi test fail, bạn đã xác định đúng vùng lỗi. Khi test pass, bạn biết mình đã sửa xong.
- **Trong lúc Commit**: Xem lại Git diff. Nếu thấy các dòng bị thay đổi chỉ vì format hoặc do tiện tay sửa những thứ không liên quan, hãy loại bỏ (revert) các thay đổi đó. Chỉ giữ lại đúng trọng tâm.
