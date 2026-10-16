---
name: doc-to-markdown
description: Chuyển đổi tài liệu đa định dạng (PDF, Word .docx/.doc, Excel .xlsx/.xls, PowerPoint .pptx, HTML, CSV, JSON, XML) sang định dạng Markdown (.md) chuẩn bằng MarkItDown, hỗ trợ xử lý file đơn lẻ và hàng loạt (batch).
---

# Kỹ Năng: Chuyển Đổi Tài Liệu Sang Markdown (Document to Markdown Converter)

Kỹ năng này cho phép tự động chuyển đổi các định dạng tài liệu văn phòng, tài liệu kỹ thuật và sách điện tử sang định dạng Markdown (`.md`) chuẩn, bảo toàn cấu trúc bảng, tiêu đề, danh sách và font tiếng Việt có dấu.

---

## 1. Các Định Dạng Được Hỗ Trợ

- **Tài liệu PDF:** `.pdf` (bao gồm sách, báo cáo, tài liệu có chữ Hán/Nôm, tiếng Việt)
- **Văn bản Word:** `.docx`, `.doc`
- **Bảng tính Excel:** `.xlsx`, `.xls` (tự động chuyển thành bảng Markdown)
- **Bản trình chiếu PowerPoint:** `.pptx` (chuyển đổi từng slide thành các mục)
- **Trang Web & Mã nguồn:** `.html`, `.htm`
- **Dữ liệu cấu trúc:** `.csv`, `.tsv`, `.json`, `.xml`
- **Tập tin nén:** `.zip` (tự bung và chuyển đổi các file bên trong)

---

## 2. Quy Trình Vận Hành

### Chế Độ 1: Chuyển Đổi File Đơn Lẻ (Single File)

Khi người dùng cung cấp đường dẫn một file tài liệu cụ thể:
1. Xác định đường dẫn file đầu vào.
2. Mặc định file đầu ra sẽ cùng thư mục với tên mở rộng đổi thành `.md` (hoặc lưu theo đường dẫn đích người dùng yêu cầu).
3. Chạy script chuyển đổi tích hợp:
   ```bash
   python scripts/convert.py "<input_file>"
   ```
   *Tùy chọn chỉ định file đích:*
   ```bash
   python scripts/convert.py "<input_file>" -o "<output_file.md>"
   ```

### Chế Độ 2: Chuyển Đổi Hàng Loạt Trong Thư Mục (Batch Conversion)

Khi người dùng yêu cầu chuyển đổi toàn bộ file trong một thư mục (ví dụ: kho sách hoặc bộ hồ sơ tài liệu):
1. Chạy script quét thư mục:
   ```bash
   python scripts/convert.py "<source_dir>"
   ```
2. Nếu muốn quét đệ quy cả các thư mục con, thêm cờ `-r`:
   ```bash
   python scripts/convert.py "<source_dir>" -r
   ```
3. Nếu muốn xuất toàn bộ file `.md` sang một thư mục đầu ra riêng biệt:
   ```bash
   python scripts/convert.py "<source_dir>" -o "<output_dir>" -r
   ```

---

## 3. Lệnh CLI Trực Tiếp Nhanh (MarkItDown Native)

Nếu chỉ cần chạy lệnh CLI đơn giản mà không qua script:
```bash
markitdown "<input_file>" -o "<output_file.md>"
```

---

## 4. Kiểm Tra & Nghiệm Thu Kết Quả

Sau khi chuyển đổi thành công:
1. Kiểm tra kích thước file `.md` sinh ra.
2. Kiểm tra font tiếng Việt và cấu trúc tiêu đề.
3. Báo cáo đường dẫn file kết quả cho người dùng.
