---
name: arena
description: >
  Kỹ năng /arena - Fan-out N candidates song song cho cùng 1 bài toán khó, chấm điểm chéo và lai ghép
  TRIGGERS: 'arena', 'so sánh nhiều phương án', 'thử nghiệm nhiều cách làm', 'fan-out candidates', 'chấm điểm giải pháp', 'thi đấu thuật toán', 'chọn phương án tối ưu'.
---
# Skill: /arena

## Khái Niệm
Fan-out N candidates song song cho cùng 1 bài toán khó, chấm điểm chéo (cross-judge) và lai ghép (grafting).

## 6 Pha Chi Tiết
1. **Frame:** Xây dựng rubric gồm 3-6 tiêu chí chấm điểm khách quan.
2. **Fan out:** Triển khai N phương án độc lập trong các worktree cách ly.
3. **Cross-judge:** Chấm điểm chéo (độc lập, khách quan) dựa trên rubric.
4. **Pick:** Chọn ra 1 Base candidate có tiềm năng cao nhất.
5. **Graft:** Trích xuất các tinh hoa/logic ưu việt từ các bản thua để ghép vào Base candidate.
6. **Verify:** Thực hiện kiểm thử nghiệm thu toàn diện (TDD, E2E).
