# Binary Safety, Native Memory, and Local IPC Reference

Tài liệu tham chiếu chuyên sâu dành cho tác tử khi mục tiêu xử lý byte không tin cậy trong ngữ cảnh native/nhị phân (C/C++, Rust `unsafe`, FFI, binary loaders) hoặc ứng dụng Desktop/Mobile với cơ chế IPC cục bộ (Unix sockets, Named Pipes, RPC, Deep-links, Webview native bridges, Privileged Helpers).

---

## Phần 1: An Toàn Bộ Nhớ & Native Binaries (Memory Safety & Binary)

### 1. Kỷ Luật Thực Chứng Cốt Lõi
- **Tính toán lại toàn bộ giới hạn và vòng đời (lifetimes)** từ dữ liệu đầu vào do attacker kiểm soát và mọi hàm gọi. Đánh giá dựa trên trường hợp xấu nhất được chấp nhận, không dựa trên test vector thông thường.
- **Panic, sanitizer finding hoặc crash** chỉ chứng minh lỗ hổng khi có đầu vào không tin cậy thực tế chạm tới được. Không suy diễn tự động việc hỏng bộ nhớ (memory corruption) hay thực thi mã từ nhãn cảnh báo đơn thuần.
- **Xác minh trong test harness cục bộ:** Sử dụng AddressSanitizer/ThreadSanitizer, test đồng thời tất định, fuzz targets có sẵn. Dừng lại ngay khi chứng minh được bất biến bị vi phạm và tác động quan sát được; tuyệt đối không phát triển kỹ thuật khai thác hậu hỏng hóc (post-corruption exploits).
- **Phân loại phán quyết:** `confirmed` khi có bằng chứng mã nguồn và kiểm chứng cục bộ; `needs_validation` khi phụ thuộc vào ABI, allocator, kiến trúc phần cứng, hoặc cờ biên dịch môi trường ngoài.

### 2. Các Lớp Tấn Công Bộ Nhớ Chính
- **Out-of-bounds Read/Write:** Độ dài, offset, chỉ mục vượt dung lượng bộ đệm. Tính toán khoảng trống còn lại sau tiền tố, căn lề (alignment), padding, và ký tự kết thúc chuỗi. Kiểm tra dung lượng nguồn và đích.
- **Integer Overflow, Underflow & Truncation:** Phép tính số học trước khi cấp phát bộ nhớ, sao chép hoặc lập chỉ mục. Chú ý các mẫu: `a - b` với `b > a`, `count * size`, chuyển đổi số âm sang không dấu, thu hẹp độ dài từ 64-bit xuống 32-bit, giá trị sentinel `-1` thành kích thước cực lớn.
- **Unit & Pointer-Depth Confusion:** Trộn lẫn đơn vị byte, phần tử (elements), đơn vị mã (code units), trang nhớ (pages), từ nhớ (words), hoặc kích thước con trỏ lồng nhau.
- **Use-After-Free, Double Free & Stale Views:** Giải phóng tài nguyên trong khi callback, hàng đợi, timer, iterator, hoặc con trỏ thô vẫn còn tham chiếu. Rà soát mọi nhánh lỗi, hủy (cancellation), và `realloc`.
- **Type Confusion & Invalid Downcast:** Thẻ (tag), vtable, union discriminator bị kiểm tra lệch so với biểu diễn thực tế khi đọc.
- **Concurrency & TOCTOU:** Race condition giữa các luồng đọc/ghi bộ đệm dùng chung, non-atomic retain/release, hoặc kiểm tra trước dùng sau mà không khóa.
- **FFI & ABI Contract Mismatch:** Bất đồng giữa bên gọi và bên được gọi về người cấp phát/giải phóng bộ nhớ, độ dài con trỏ, căn lề cấu trúc (struct packing/alignment), ngoại lệ/panic vượt ranh giới FFI không cho phép unwind.

---

## Phần 2: Desktop, Mobile & Local IPC (Inter-Process Communication)

### 1. Kỷ Luật IPC & Ứng Dụng Cục Bộ
- **Xác lập năng lực ban đầu của attacker:** Kẻ tấn công cục bộ có thể là một ứng dụng khác cùng máy, người dùng hệ điều hành khác, tiến trình con bị sandbox, tài liệu không tin cậy tải về, hoặc web content từ xa. Việc tự gây hại trong cùng một tài khoản và quyền hạn không tính là lỗ hổng bảo mật.
- **Đường dẫn, tên tiến trình, Bundle/Package ID, trường người gửi tự khai KHÔNG PHẢI là xác thực định danh (peer authentication).** Bắt buộc sử dụng thông tin xác thực hệ điều hành (OS peer credentials: PID/UID/token), danh tính chữ ký số (code identity), handle năng lực, hoặc kênh truyền được bảo vệ.
- **Native bridge và Privileged Helper** phải tự kiểm tra thẩm quyền cho từng thao tác và tài nguyên cuối cùng sau khi phân tích cú pháp.

### 2. Các Lớp Tấn Công IPC & Nền Tảng Cục Bộ
- **Deep-link & Custom-Scheme Ambiguity:** Ứng dụng hoặc trang web khác gọi route để kích hoạt thay đổi trạng thái, hoàn tất xác thực hoặc đổi tài khoản mà không có ràng buộc phiên hiện tại và token một lần.
- **Webview & Native Bridge Escapes:** Nội dung web từ xa hoặc frame không tin cậy có thể truy cập vào JavaScript/native bridge vốn chỉ dành cho nội dung đóng gói sẵn. Cần kiểm tra nguồn gốc (origin) tại thời điểm gọi hàm và sau mọi chuyển hướng (navigation/redirect).
- **IPC Peer-Authentication Gaps:** Unix domain sockets, Named Pipes, RPC, D-Bus, Native Messaging, hoặc loopback sockets chấp nhận kết nối từ peer có đặc quyền thấp hơn mà không kiểm tra thông tin định danh hệ điều hành.
- **Claimed Principal vs Channel Identity:** Kênh truyền thuộc về một ứng dụng hoặc người dùng, nhưng trường trong payload lại chỉ định người dùng hoặc tenant khác. Phải ràng buộc dữ liệu với danh tính của kênh thay vì ID tự khai.
- **Privileged Helper as Confused Deputy:** Caller đặc quyền thấp yêu cầu privileged helper thực hiện lệnh hệ thống, ghi file nhạy cảm hoặc thay đổi cấu hình mà helper không tự kiểm tra quyền hạn của caller đối với tài nguyên đó.
- **Local File TOCTOU & Symlink Attacks:** Ứng dụng kiểm tra đường dẫn rồi thực hiện thao tác privileged mà bị tráo đổi file, symlink, hoặc mount point.
- **Credential-Store Mismatch:** Token, cấu hình bí mật được lưu trữ với quyền đọc quá rộng, cho phép người dùng hoặc ứng dụng khác cùng máy đọc được.

---

## 3. Quy Tắc Nghiệm Thu Báo Cáo (Validation Rules)

1. Nêu rõ năng lực khởi đầu của attacker, ranh giới tiến trình/bộ nhớ/hệ điều hành bị vượt qua, và thao tác trái phép quan sát được.
2. Với native memory: Dẫn chứng lệnh chạy, sanitizer report (AddressSanitizer, ThreadSanitizer), và input tối thiểu kích hoạt lỗi.
3. Với IPC / Helper: Xác minh cơ chế xác thực peer của kênh truyền và phân quyền trên tài nguyên.
4. Ghi nhận `needs_validation` khi cần chữ ký số, manifest hệ điều hành, phân quyền cài đặt (installer ACL), hoặc kiến trúc phần cứng thực tế mà môi trường cục bộ không kiểm chứng được.
