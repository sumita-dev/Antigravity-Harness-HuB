---
name: forensics
description: >
  Kỹ năng /forensics - Chẩn đoán chuyên sâu trước khi fix bug
  TRIGGERS: 'forensics', 'chẩn đoán lỗi sâu', 'bug quái đản', 'lỗi khó tái hiện', 'điều tra lỗi ngầm', 'truy tìm nguồn gốc bug', 'root-cause forensics', 'deep bug investigation'.
---
# Skill: /forensics

## Khái Niệm
Chẩn đoán chuyên sâu trước khi fix bug (phân tách thành 2 nhánh: Runtime Forensics & Trace Forensics).

## Hai Nhánh Chẩn Đoán
1. **Runtime Forensics (Chẩn đoán Runtime):**
   - Chẩn đoán các triệu chứng sống (leak bộ nhớ, idle CPU spin, socket leak, GC thrashing).
   - Thực hiện bằng phương pháp live instrumentation (đo đạc trực tiếp hệ thống đang chạy).

2. **Trace Forensics (Chẩn đoán Vết):**
   - Bóc tách file artifact profiling ngoại tuyến (như `.cpuprofile`, `.heapsnapshot`, Chrome trace JSON, Flamegraph, OTEL spans).
   - Trích xuất hot frames (các khung gọi thường xuyên) & retention paths (đường dẫn giữ bộ nhớ).
   - Nạp kết quả đã phân tích vào `debug-orchestrator` để đề xuất fix.
