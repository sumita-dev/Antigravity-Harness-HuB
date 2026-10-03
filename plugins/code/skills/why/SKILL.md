---
name: why
description: Kỹ năng /why - Khảo cổ học kiến trúc mã nguồn & Khung nhận thức Epistemics
---
# Skill: /why

## Khái Niệm
Khảo cổ học kiến trúc mã nguồn & Khung nhận thức Epistemics (hệ thống hóa sự hiểu biết về code trước khi thay đổi).

## 4 Bước Khảo Cổ
1. **Code anchor:** Bắt đầu bằng việc điều tra lịch sử mã thông qua `git blame`, `git log -p`, hoặc `gh pr view`.
2. **Scan & Classify:** Quét và phân loại 7 nhóm nguồn chứng cứ qua MCPs (Git/PRs, Issue tracker, Docs, Chat, Observability, Sentry, Analytics).
3. **Epistemic Confidence Framework:** Định mức độ tin cậy của phát hiện:
   - `CONFIRMED_FACT`: Sự thật đã được xác thực hoàn toàn bằng chứng cứ vững chắc.
   - `OBSERVED_BEHAVIOR`: Hành vi quan sát được nhưng chưa rõ nguyên nhân gốc rễ.
   - `INFERRED_HYPOTHESIS`: Giả thuyết suy luận cần được kiểm chứng thêm.
4. **Chesterton's Fence:** Chốt hạ nguyên tắc Chesterton's Fence ("Đừng phá hàng rào nếu bạn chưa biết vì sao nó được dựng lên") trước khi đưa ra bất kỳ đề xuất refactor hoặc xóa mã cũ nào.
