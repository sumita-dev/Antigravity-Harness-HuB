---
name: verify-ui
description: Tự động kiểm chứng giao diện (Verification Loop) thông qua Chrome DevTools MCP, đo đạc Core Web Vitals, thu thập logs và bàn giao bằng chứng cho tác tử thẩm định thứ hai (Second Agent Review).
triggers:
  - after_ui_changes
  - before_commit_ui
---

# Quy trình tự kiểm chứng giao diện (UI Verification Loop)

Kỹ năng này thực thi vòng lặp xác minh giao diện không thiên kiến thông qua các bằng chứng thực nghiệm (Visual Evidence & DevTools Logs), theo triết lý Second Agent Review.

## Bước 1: Khởi động Dev Server
- Khởi động hoặc kiểm tra trạng thái dev server đang hoạt động trên localhost hoặc dev port tương ứng.
- Đảm bảo ứng dụng có thể truy cập qua HTTP/HTTPS.

## Bước 2: Kết nối Chrome DevTools
- Tự động kết nối thông qua Chrome DevTools MCP (hoặc headless browser).
- Điều hướng (navigate) đến trang/component vừa được sửa đổi.

## Bước 3: Thu thập Errors
- Lắng nghe Console errors và Network errors.
- Chặn đứng mọi uncaught exception hoặc các request HTTP có status code >= 400.

## Bước 4: Kiểm tra Core Web Vitals & Bố cục
- Đo lường chỉ số CLS (Cumulative Layout Shift) để phát hiện vỡ giao diện hoặc giật lag.
- Đo lường chỉ số LCP (Largest Contentful Paint).
- Chụp ảnh màn hình (screenshot) hiện trạng UI.
- Lưu trữ toàn bộ dữ liệu vào `.brain/evidence/` làm bằng chứng thực nghiệm (Visual Evidence).

## Bước 5: Bàn giao Thẩm định
- Bàn giao bằng chứng (Visual Evidence, DevTools logs) sang cho tác tử thẩm định độc lập như `code-reviewer` hoặc `ui-finish-gate-reviewer`.
- Việc nghiệm thu phải được thực hiện hoàn toàn dựa trên bằng chứng thu thập được, đảm bảo quá trình không thiên kiến.
