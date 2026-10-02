---
name: hillclimb
description: >
  Kỹ năng /hillclimb - Vòng lặp tối ưu hóa hiệu năng thực nghiệm có kiểm soát khoa học
  TRIGGERS: 'hillclimb', 'tối ưu hiệu năng', 'tối ưu tốc độ', 'tăng throughput', 'giảm latency', 'benchmark hiệu năng', 'tối ưu thực nghiệm', 'optimize performance'.
---
# Skill: /hillclimb

## Khái Niệm
Vòng lặp tối ưu hóa hiệu năng thực nghiệm có kiểm soát khoa học.

## Các Nguyên Tắc Bất Biến
1. **1 metric:** Tập trung vào một chỉ số duy nhất tại một thời điểm (ví dụ: memory, execution time).
2. **1 giả thuyết/commit:** Mỗi thay đổi chỉ xoay quanh một giả thuyết duy nhất.
3. **Frozen benchmark harness:** Chứng minh độ nhạy của bài test trước khi khóa (frozen) và tiến hành vòng lặp.
4. **Stop predicate kép:** Dừng lại khi đạt được mục tiêu cải thiện hoặc đạt sàn số lần lặp tối thiểu.
5. **Decision log:** Bắt buộc ghi nhận mọi kết quả vào `.brain/decision.tsv` với định dạng `id, hypothesis, change, before, after, delta, tests, verdict: kept/reverted`.
6. **Tự động revert:** Lập tức revert ngay nếu delta <= 0 (không mang lại giá trị hoặc làm mọi thứ tệ hơn).
