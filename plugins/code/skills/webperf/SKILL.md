---
name: webperf
description: "Tối ưu Web Performance & Core Web Vitals (LCP, INP, CLS, long tasks, bundle size) chuẩn Google và DevTools MCP."
metadata:
  origin: Addy Osmani (agent-skills)
---

# Kỹ Năng: Web Performance & Core Web Vitals (WebPerf)

## Tổng Quan (Overview)

Đo lường trước khi tối ưu hóa. Tối ưu hóa hiệu năng mà không có số liệu thực nghiệm là đoán mò — và việc đoán mò dẫn đến tối ưu hóa sớm (premature optimization), làm tăng độ phức tạp mã nguồn mà không đem lại cải thiện thực tế nào cho người dùng.

Kỹ năng này chuẩn hóa quy trình audit, chẩn đoán và khắc phục hiệu năng ứng dụng Web theo các chỉ số **Core Web Vitals** chính thức của Google (LCP, INP, CLS), kết hợp giám sát các tác vụ chặn Main Thread (**Long Tasks > 50ms**) và kiểm soát dung lượng gói tải (**Bundle Size**). Được tích hợp năng lực của **Chrome DevTools MCP** giúp tác tử trực tiếp đo lường trên trình duyệt thực tế.

> **Ranh giới Hợp đồng (Contract Boundary):**
> - `webperf` chuyên trách độc quyền về: Đo đạc và tối ưu số liệu hiệu năng (Core Web Vitals: LCP, INP, CLS; long tasks; network telemetry; bundle size budgets). Hỗ trợ script tất định `scripts/check_bundle_budget.py`.
> - Kiểm tra hiển thị giao diện trực quan, render layout, micro-interactions và ảnh chụp screenshot do kỹ năng `/verify-ui` phụ trách.

---

## Chỉ Số Mục Tiêu Core Web Vitals (Google Targets)

| Chỉ số (Metric) | Đạt chuẩn (Good) | Cần cải thiện (Needs Work) | Kém (Poor) | Trọng tâm tối ưu |
|:---|:---:|:---:|:---:|:---|
| **LCP** (Largest Contentful Paint) | $\le 2.5\text{s}$ | $\le 4.0\text{s}$ | $> 4.0\text{s}$ | Hero image, text block chính, preload, fetchpriority |
| **INP** (Interaction to Next Paint) | $\le 200\text{ms}$ | $\le 500\text{ms}$ | $> 500\text{ms}$ | Long tasks, `scheduler.yield()`, LoAF, event delays |
| **CLS** (Cumulative Layout Shift) | $\le 0.1$ | $\le 0.25$ | $> 0.25$ | Khai báo width/height, aspect-ratio, font-display: swap |
| **Long Tasks** | $0\text{ task} > 50\text{ms}$ | $\le 100\text{ms}$ | $> 100\text{ms}$ | Giảm tải JS main thread, Web Workers, code splitting |
| **Bundle Size** | $\le 170\text{kB}$ (gzip) | $\le 300\text{kB}$ | $> 300\text{kB}$ | Dynamic import, tree-shaking, loại bỏ thư viện thừa |

---

## Quy Tắc Bất Biến Trung Thực Số Liệu (Metric-Honesty Rule)

> [!CAUTION]
> **TUYỆT ĐỐI CẤM BỊA ĐẶT HOẶC ĐOÁN MÒ SỐ LIỆU PERFORMANCE.**
> Một mô hình AI chỉ đọc mã nguồn tĩnh KHÔNG THỂ đo lường chính xác các chỉ số thời gian thực (LCP ms, INP ms, CLS). Vi phạm quy tắc này là vi phạm nghiêm trọng đạo đức kỹ thuật và rào chắn chống ảo giác.

Kỹ năng chia làm hai chế độ vận hành rạch ròi:

### 1. Chế độ Tĩnh (Quick / Static Mode — Khi chưa có công cụ đo đạc thực tế)
- Quét mã nguồn tĩnh để phát hiện các anti-pattern cấu trúc (ảnh thiếu width/height, import thư viện nặng ở top-level, vòng lặp đồng bộ lớn...).
- **Toàn bộ phát hiện chỉ được gắn nhãn là `potential impact`** (tác động tiềm năng), cấm ghi là số đo thực tế.
- Bảng Scorecard Core Web Vitals bắt buộc phải ghi rõ: `not measured` (chưa đo đạc).

### 2. Chế độ Đo đạc Thực tế (Deep Mode — Khi có công cụ DevTools / Lighthouse / CrUX)
- Đọc dữ liệu từ báo cáo thực tế:
  - **Lighthouse JSON report**: `npx lighthouse <url> --output json` hoặc qua Chrome DevTools MCP `lighthouse_audit`.
  - **Chrome DevTools MCP server**: Thu thập trực tiếp qua `performance_start_trace` / `performance_stop_trace` và `performance_analyze_insight`.
  - **CrUX API**: Dữ liệu thực tế người dùng (p75 trong 28 ngày qua).
- Mọi giá trị trên Scorecard đều phải đính kèm nhãn nguồn gốc: `Lab (Lighthouse)`, `Field (CrUX)`, hoặc `Trace (DevTools)`.

---

## Tích Hợp Antigravity 2.0 & Dynamic Triad

1. **Maker (SubAgent Builder):**
   - Không tối ưu mù quáng. Bắt đầu bằng việc ghi nhận baseline (báo cáo đo lường hiện tại).
   - Áp dụng các giải pháp phẫu thuật chính xác (Surgical Changes) theo [optimization-patterns.md](references/optimization-patterns.md).
   - Chạy script tất định `python plugins/code/skills/webperf/scripts/check_bundle_budget.py` để kiểm soát dung lượng gói tải.
2. **Critic (SubAgent Code Critic):**
   - Soi xét kiến trúc: Ngăn chặn over-engineering (tránh việc bọc `useMemo` / `useCallback` bừa bãi làm tăng rác bộ nhớ mà không cải thiện thời gian render).
   - Kiểm tra Metric-Honesty Rule: REJECT ngay nếu Maker tự tiện đưa ra số liệu thời gian vẽ màn hình mà không có log/bằng chứng từ công cụ đo.
3. **QA Auditor (Checker):**
   - Rerun độc lập bộ test kiểm thử hiệu năng và Chrome DevTools MCP.
   - Kiểm tra rò rỉ tiến trình qua kỹ năng `/browser-hygiene` sau khi hoàn tất phiên đo lường.

---

## Thiết Lập Chrome DevTools MCP (Isolated Testing)

Để tác tử có thể quan sát và phân tích trình duyệt thời gian thực, cấu hình MCP Server với cờ `--isolated`:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--isolated"]
    }
  }
}
```

*Quy chuẩn bảo mật:* Cờ `--isolated` đảm bảo Chrome chạy trên một profile tạm thời hoàn toàn tách biệt với trình duyệt cá nhân của người dùng, triệt tiêu nguy cơ rò rỉ cookies hoặc phiên đăng nhập nhạy cảm.

---

## Quy Trình 5 Bước Tối Ưu Hóa (The 5-Step Workflow)

```text
1. MEASURE   ──► Thiết lập baseline ban đầu bằng công cụ thực tế
2. IDENTIFY  ──► Định vị đúng nút thắt cổ chai (Bottleneck)
3. FIX       ──► Can thiệp phẫu thuật chính xác theo pattern chuẩn
4. VERIFY    ──► Đo lường lại độc lập; chứng minh hiệu quả hoặc rollback
5. GUARD     ──► Thiết lập ngân sách (budget) để chống hồi quy (regression)
```

### Bước 1: Đo lường (Measure)
- Nếu có live app/local preview: Chạy Lighthouse hoặc Chrome DevTools trace để ghi nhận chỉ số LCP, INP, CLS và Long Tasks.
- Nếu chỉ có mã nguồn tĩnh: Lập danh mục các điểm nghi vấn (potential bottlenecks) và phân loại theo mức độ rủi ro.

### Bước 2: Định vị nút thắt cổ chai (Identify)
- **LCP chậm:** Do tài nguyên ảnh quá nặng chưa nén, thiếu preload, hoặc bị chặn bởi CSS/JS đồng bộ.
- **INP kém:** Do Main thread bị chiếm dụng bởi các vòng lặp tính toán nặng, render cây DOM quá lớn, hoặc thiếu `scheduler.yield()`.
- **CLS giật:** Do thiếu thuộc tính kích thước trên media (`<img>`, `<iframe>`), font chữ nhảy layout (FOUT), hoặc render nội dung động không chừa chỗ trống.

### Bước 3: Sửa chữa theo mẫu chuẩn (Fix)
Tham khảo chi tiết tại [references/optimization-patterns.md](references/optimization-patterns.md):
- Thêm `fetchpriority="high"` và `loading="eager"` cho ảnh LCP.
- Chuyển logic nặng sang Web Worker hoặc bẻ nhỏ vòng lặp bằng `yieldToMain()`.
- Áp dụng `aspect-ratio` và skeleton loader cho các khối nội dung động.
- Tách code (code splitting) các thư viện nặng với `next/dynamic` hoặc `import()`.

### Bước 4: Kiểm chứng lại (Verify)
- Chạy lại bài kiểm tra trong cùng điều kiện mạng/CPU throttling (ví dụ: Slow 4G / 4x CPU Slowdown).
- Nếu chỉ số không cải thiện mà độ phức tạp code tăng lên $\rightarrow$ **Rollback ngay lập tức**.

### Bước 5: Thiết lập rào chắn (Guard)
- Thêm ngưỡng cảnh báo kích thước gói tải vào cấu hình build qua `python plugins/code/skills/webperf/scripts/check_bundle_budget.py`.

---

## Bảng Dấu Hiệu Cảnh Báo (Red Flags)

- Khẳng định "trang web đã nhanh hơn 40%" mà không có bất kỳ log so sánh trước/sau từ công cụ đo.
- Đặt `loading="lazy"` lên ảnh LCP ở đầu trang (khiến ảnh tải muộn hơn 1-2 giây).
- Đưa vào các abstraction phức tạp (như Web Worker tự chế) cho tác vụ chỉ mất 5ms.
- Sử dụng Chrome DevTools gắn vào profile cá nhân có thông tin thẻ thanh toán/email mà không có cờ `--isolated`.

---

## Checklist Kiểm Định (Verification Checklist)

- [ ] Đã xác định rõ framework và mô hình render (Next.js SSR/SSG/ISR, React SPA, Astro...).
- [ ] Tuân thủ nghiêm ngặt Metric-Honesty Rule (đánh dấu `not measured` nếu chỉ đọc code tĩnh).
- [ ] Ảnh LCP có kích thước rõ ràng, không bị lazy load, có `fetchpriority="high"`.
- [ ] Không có layout shift tự do (mọi container động đều có min-height hoặc aspect-ratio).
- [ ] Các tác vụ xử lý mảng lớn đều có cơ chế nhường Main Thread (`yieldToMain` hoặc tương đương).
- [ ] Đã tách nhỏ các component/thư viện nặng bằng dynamic import.
- [ ] Đã dọn dẹp tiến trình trình duyệt mồ côi (`/browser-hygiene`) sau khi kết thúc audit.
