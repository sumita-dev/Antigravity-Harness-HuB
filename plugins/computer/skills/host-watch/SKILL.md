---
name: host-watch
description: Giám sát Disk I/O 3 tầng, điều phối concurrency slot theo pool và bảo vệ SSD/RAM trên Windows & POSIX qua Host Watch và scripts/host_gate.py. Kích hoạt khi cần xử lý nghẽn disk, quá tải I/O, bọc lệnh build/test/install/worktree, cài PATH shims hoặc tỉa cache Go/pytest có giới hạn.
---

# Host Watch & Disk I/O Protection

Kỹ năng vận hành hệ thống bảo vệ Disk I/O 3 tầng (`harness/host_watch.py` và `scripts/host_gate.py`) giúp ngăn chặn tình trạng storm I/O làm treo máy hoặc nghẽn SSD khi chạy đa tác tử / worktree song song.

---

## 1. Kiến Trúc 3 Tầng (Balanced Defaults)

1. **Tầng OS Priority (`apply_low_io_priority`):**
   - Tự động hạ mức ưu tiên Disk I/O (`IOPRIO_VERYLOW` trên Windows, `IOPRIO_CLASS_IDLE` / `IOPRIO_CLASS_BE` trên Linux) và CPU (`BELOW_NORMAL_PRIORITY_CLASS` / `nice(10)`) cho các tiến trình build/test/install nền để giữ UI phản hồi mượt.
2. **Tầng Concurrency Gate (`scripts/host_gate.py`):**
   - **`io_heavy` (cap = `1`):** `install`, `worktree` (`pnpm/npm/yarn/pip install`, `git worktree`).
   - **`compute_io` (cap = `2`):** `build`, `test` (`go test/build`, `pytest`, `run_pytest_windows.py`, `cargo build/test`, `tsc`, `vitest`, `jest`).
   - **Fail-Fast Backpressure:** Chờ tối đa `45s` (`--wait-timeout`), quá hạn trả mã thoát `75` (`[HOST-GATE-BUSY]`) và tự thu hồi lock của PID đã chết hoặc quá `max_lease_sec=600s`.
3. **Tầng Telemetry & Admission Control:**
   - Theo dõi `psutil.disk_io_counters()` delta + EMA (`bytes_per_sec`, `iops`, `avg_latency_ms`) với 3 mức `GREEN` / `YELLOW` / `RED`.
   - `ChiefOrchestrator.fan_out_tasks` tự hãm concurrency (`GREEN -> requested`, `YELLOW -> min(requested, 2)`, `RED -> 1`).
   - Hook `PreInvocation` chèn cảnh báo `host_io=` tối đa 1 lần mỗi 5 phút (`cooldown=300s`, trừ khi leo thang `YELLOW -> RED`).

---

## 2. Lệnh Thực Thi & PATH Shims

### Kiểm tra trạng thái & bọc lệnh
```bash
python scripts/host_gate.py --status --json
python scripts/host_gate.py --category auto --wait-timeout 45 -- pytest -q
python scripts/host_gate.py --category io_heavy -- pnpm install
```

### Cài đặt PATH Shims chống đệ quy
Tạo wrapper trong thư mục riêng (ví dụ thư mục tạm hoặc bin cá nhân bên ngoài repo) và thêm lên đầu `PATH`:
```bash
python scripts/host_gate.py --install-shims "$HOME/.local/antigravity-shims"
python scripts/host_gate.py --install-shims "$HOME/.local/antigravity-shims" --shim npm --shim pytest
```
- Shim luôn đặt `ANTIGRAVITY_SHIM_ACTIVE=1`, loại bỏ chính thư mục shim khỏi `PATH` và phân giải binary thật qua `shutil.which` nên không bao giờ đệ quy vô hạn hoặc deadlock slot lồng nhau.

---

## 3. Kỷ Luật Multi-Agent Worktree & Package Stores

Khi mở nhiều worktree hoặc subagent song song:
1. **Tắt auto-gc trên worktree:** Chạy `git -c gc.auto=0 worktree add ...` và thiết lập `git config gc.auto 0` tại worktree để tránh nhiều tiến trình chạy `git gc` nền cùng lúc.
2. **Dùng chung package store (read-mostly):** Tái sử dụng `GOMODCACHE` và `pnpm` store / `npm` cache dùng chung thay vì nhân bản cache riêng cho từng worktree.
3. **Bọc lệnh nặng qua Host Gate:** Mọi lệnh `install`, `worktree`, `build`, `test` của subagent đi qua `scripts/host_gate.py` hoặc `scripts/safe_task_runner.py --host-gate`.

---

## 4. Tỉa Cache Có Giới Hạn & Tư Vấn Lưu Trữ Windows

- **Kiểm tra trước khi xóa (Dry-Run):**
  ```bash
  python scripts/host_gate.py --prune-caches --dry-run
  python scripts/host_gate.py --prune-caches
  ```
- **Chính sách tỉa an toàn:**
  - `GOCACHE`: Chỉ tỉa các tệp truy cập/sửa đổi cũ nhất theo LRU khi vượt trần `30 GB` hoặc cũ hơn `7 ngày`; tuyệt đối không chạm `.git` hay mã nguồn.
  - `antigravity-pytest-*`: Dọn các thư mục temp sót lại quá `1 giờ` (hoặc chạy `python run_harness.py --doctor-fix`).
- **Tư vấn Windows Storage (Read-Only):**
  - Khi workspace nằm trên phân vùng `NTFS` và chạy tải multi-worktree nặng, cân nhắc đặt repo/cache trên **Windows Dev Drive (`ReFS`)** và bổ sung **Windows Defender Folder Exclusion** cho thư mục workspace cùng `GOCACHE`, `GOMODCACHE`, `pnpm` store.
