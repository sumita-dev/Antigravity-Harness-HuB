---
name: finishing-a-development-branch
description: Quy trình hoàn tất và nghiệm thu nhánh phát triển (chạy test, menu 3 lựa chọn, dọn dẹp worktree an toàn).
---

# Hoàn Tất Nhánh Phát Triển (Finishing a Development Branch)

## Tổng Quan (Overview)

Quy trình chuẩn hóa để tích hợp và nghiệm thu kết quả công việc sau khi hoàn tất giai đoạn lập trình.

**Nguyên tắc cốt lõi:** Chạy kiểm thử xác minh baseline → Nhận diện môi trường → Trình menu 3 lựa chọn → Thực thi theo chỉ đạo → Dọn dẹp an toàn.

## Bước 1: Kiểm Tra Toàn Bộ Test Suite (Verify Tests Baseline)

Trước khi đề xuất bất kỳ hành động nghiệm thu nào, bắt buộc phải chạy toàn bộ test suite của dự án (ví dụ: `pytest -q`, `npm test`, `cargo test`).

- **Nếu có test fail:** Dừng lại ngay lập tức, báo cáo danh sách test hỏng. Không trình menu tích hợp cho đến khi toàn bộ test xanh 100%.
- **Nếu test xanh toàn bộ:** Chuyển sang Bước 2.

## Bước 2: Nhận Diện Môi Trường Git (Detect Environment)

Kiểm tra trạng thái worktree và vị trí nhánh:
- Xác định `git rev-parse --git-dir` và `git rev-parse --git-common-dir`.
- Xác định nhánh gốc (base branch, ví dụ `main` hoặc `master`).
- Kiểm tra xem đang chạy trên repository thông thường hay worktree độc lập.

## Bước 3: Trình Menu 3 Lựa Chọn Tích Hợp (Present Options)

Trình bày rõ ràng menu 3 lựa chọn cho người dùng/Sếp quyết định:

```
Triển khai và kiểm thử đã hoàn tất thành công. Bạn muốn xử lý nhánh phát triển như thế nào?

1. Merge trực tiếp vào nhánh gốc (<base-branch>) tại local
2. Push lên remote và tạo Pull Request (PR)
3. Giữ nguyên nhánh hiện tại (sẽ xử lý sau)

Xin vui lòng chọn phương án?
```

Tuyệt đối không tự ý quyết định merge hay push lên remote khi chưa có phản hồi rõ ràng.

## Bước 4: Thực Thi Lựa Chọn Được Duyệt (Execute Choice)

### Lựa chọn 1: Merge Local
1. Chuyển về nhánh gốc (`git checkout <base-branch>`).
2. Kéo cập nhật mới nhất (`git pull`).
3. Thực hiện merge (`git merge <feature-branch>`).
4. Chạy lại toàn bộ test suite trên kết quả sau merge.
5. Nếu test xanh: Xóa nhánh tính năng (`git branch -d <feature-branch>`) và dọn dẹp worktree liên quan.

### Lựa chọn 2: Push & Tạo Pull Request
1. Đẩy nhánh lên remote (`git push -u origin <feature-branch>`).
2. Cung cấp đường dẫn tạo PR hoặc gọi CLI hỗ trợ tạo PR.
3. Giữ nguyên worktree để sẵn sàng chỉnh sửa khi có review phản biện từ PR.

### Lựa chọn 3: Giữ Nguyên Nhánh
1. Báo cáo xác nhận: Đã bảo lưu toàn bộ commit và nhánh phát triển an toàn.

## Cơ Chế Bảo Vệ Chống Xóa Nhầm (Discard Protection Gate)

Nếu người dùng yêu cầu hủy bỏ hoặc vứt bỏ (discard) nhánh làm việc:
- **Cơ chế xác nhận nghiêm ngặt:** Bắt buộc người dùng phải gõ chính xác từ `discard` để xác nhận.
- Cảnh báo rõ ràng các thành phần sẽ bị xóa vĩnh viễn: Tên nhánh, danh sách commit liên quan và thư mục worktree.
- Khi nhận được từ xác nhận `discard`: Thực hiện dọn dẹp worktree và force-delete nhánh (`git branch -D <feature-branch>`).

## Bước 5: Dọn Dẹp Worktree An Toàn (Cleanup Worktree)

- Chỉ thực hiện gỡ worktree (`git worktree remove`) từ bên ngoài thư mục worktree đó.
- Nếu lệnh remove bị từ chối do có file chưa commit hoặc untracked: Dừng lại và liệt kê các file đó cho người dùng quyết định (commit, di chuyển sang thư mục chính, hoặc xóa). Cấm tự ý dùng cờ ép buộc (`--force`) gây mất mát dữ liệu.
- Chạy `git worktree prune` để làm sạch đăng ký worktree rác.
