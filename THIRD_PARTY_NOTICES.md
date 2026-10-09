# Third-Party Notices

Repo này chứa skill được vendored (copy) từ các nguồn/plugin bên thứ ba. Những
phần đó **giữ nguyên bản quyền và giấy phép gốc của chúng**, không thuộc phạm vi
giấy phép MIT áp cho mã nguồn gốc của repo (xem `LICENSE`).

## Các nhóm cần Sếp rà giấy phép trước khi dùng thương mại

| Nhóm skill | Vị trí | Ghi chú |
| :--- | :--- | :--- |
| `impeccable` (+ `scripts/`, `reference/`) | `plugins/impeccable/skills/impeccable/` | Bộ công cụ thiết kế/UI lớn, có script JS và agent `.toml` — nhiều khả năng đến từ một bộ nguồn riêng |
| `gitnexus-plan`, `gitnexus-work`, `gitnexus-review` | `plugins/code/skills/gitnexus-*` | Kèm `scripts/evidence-provenance.mjs` |
| `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `condition-based-waiting*` | `plugins/code/skills/*` | Nhóm skill mang phong cách "superpowers"/obra |
| `traffic-secrets-playbook` | `plugins/marketing/skills/` | Nội dung trích từ sách của Russell Brunson — cần cân nhắc bản quyền nội dung |
| `alex-hormozi-*`, `kahneman-creative-ads` | `plugins/marketing/skills/` | Framework của tác giả khác, diễn giải lại |
| `boc-phot-storytelling` (kèm BRAND_GUIDELINE html) | `plugins/marketing/skills/` | Tài liệu thương hiệu riêng — kiểm tra có được phép công khai |

## Việc cần làm
1. Xác nhận giấy phép của từng nhóm ở trên (hoặc thay bằng skill tự viết).
2. Với nội dung diễn giải từ sách/khóa học: kiểm tra có vi phạm bản quyền nội dung khi phát hành công khai không.
3. Nếu repo chuyển sang private, các lo ngại trên giảm nhưng không biến mất hoàn toàn.
