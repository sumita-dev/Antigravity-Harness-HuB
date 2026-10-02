---
name: advisor
description: Quản lý chế độ cố vấn độc lập và Advisor Checkpoint Protocol
---

# Kỹ năng `/advisor`

Kỹ năng này quản lý chế độ cố vấn độc lập với các lệnh:
- `on`: Bật chế độ cố vấn
- `off`: Tắt chế độ cố vấn
- `status`: Xem trạng thái cố vấn
- `ask <question>`: Hỏi cố vấn

Trạng thái được lưu tại `.brain/advisor/state.json`.

Hướng dẫn soạn Briefing và nhận định từ cố vấn:
- Trình bày bối cảnh rõ ràng.
- Báo cáo phản hồi của Advisor sẽ theo định dạng: `Verdict / Why / Recommendations / Risks / Confidence`.
