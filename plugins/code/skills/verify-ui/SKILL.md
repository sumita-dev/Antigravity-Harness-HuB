---
name: verify-ui
description: "Kiểm chứng giao diện thực tế (Visual Proof, DOM, Screenshot, Chrome DevTools MCP) - Không đo telemetry/CWV chuyên sâu (thuộc webperf)."
triggers:
  - after_ui_changes
  - before_commit_ui
---
# Quy trình tự kiểm chứng giao diện (UI Verification Loop)

Kỹ năng này thực thi vòng lặp xác minh giao diện không thiên kiến thông qua các bằng chứng trực quan (Visual Evidence & DevTools Logs), theo triết lý Second Agent Review.

> **Ranh giới Hợp đồng (Contract Boundary):**
> - `verify-ui` chuyên trách: Khởi động dev server, snapshot UI thực tế, kiểm tra DOM elements, render layout, micro-interactions, và chụp ảnh màn hình (Screenshot).
> - Đo đạc số liệu hiệu năng, đo Core Web Vitals (LCP, INP, CLS, long tasks) và bundle size thuộc thẩm quyền chuyên trách của kỹ năng `/webperf`.

## Bước 1: Khởi động Dev Server
- Khởi động hoặc kiểm tra trạng thái dev server đang hoạt động trên localhost hoặc dev port tương ứng.
- Đảm bảo ứng dụng có thể truy cập qua HTTP/HTTPS.

## Bước 2: Kết nối Chrome DevTools MCP
- Tự động kết nối thông qua Chrome DevTools MCP (hoặc headless browser).
- Điều hướng (navigate) đến trang/component vừa được sửa đổi.

## Bước 3: Thu thập Lỗi Giao diện & Console
- Lắng nghe Console errors và Network errors.
- Chặn đứng mọi uncaught exception hoặc các request HTTP có status code >= 400.

## Bước 4: Kiểm tra Bố cục Trực quan & Bằng chứng Snapshot (Visual Proof)
- Chụp ảnh màn hình (screenshot) hiện trạng UI sau khi render đầy đủ.
- Kiểm tra tính toàn vẹn của layout, container bounds và responsive elements.
- Lưu trữ toàn bộ dữ liệu vào `.brain/evidence/` làm bằng chứng thực nghiệm (Visual Evidence).

## Bước 5: Bàn giao Thẩm định
- Bàn giao bằng chứng (Visual Evidence, DevTools logs, Screenshots) sang cho tác tử thẩm định độc lập như `code-reviewer` hoặc `qa-auditor`.
- Việc nghiệm thu phải được thực hiện hoàn toàn dựa trên bằng chứng thu thập được, đảm bảo quá trình không thiên kiến.
