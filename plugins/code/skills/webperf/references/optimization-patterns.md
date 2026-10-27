# Optimization Patterns Reference

Cẩm nang tổng hợp các mẫu mã nguồn tối ưu hóa hiệu năng cao cho ứng dụng Web hiện đại (Next.js, React, Node.js, Web APIs) theo chuẩn kỹ thuật của Addy Osmani và Google Web Standards.

---

## 1. Interaction to Next Paint (INP) & Main Thread Yielding

### Kỹ thuật bẻ nhỏ Long Tasks (> 50ms) bằng `scheduler.yield()`

Khi xử lý danh sách lớn hoặc tính toán nặng, việc chạy vòng lặp đồng bộ sẽ chiếm dụng Main Thread làm đơ trình duyệt. Sử dụng `scheduler.yield()` (với fallback) để nhường quyền ưu tiên cho sự kiện người dùng:

```typescript
// Tiện ích nhường quyền Main Thread chuẩn hiện đại
async function yieldToMain(): Promise<void> {
  // @ts-expect-error - scheduler API đang dần chuẩn hóa
  if ('scheduler' in globalThis && 'yield' in globalThis.scheduler) {
    // @ts-expect-error
    return await globalThis.scheduler.yield();
  }
  // Fallback cho trình duyệt cũ
  return new Promise(resolve => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}

// Áp dụng trong xử lý dữ liệu hàng loạt:
export async function processBatchItems<T>(items: T[], processFn: (item: T) => void): Promise<void> {
  const BATCH_SIZE = 50;
  for (let i = 0; i < items.length; i++) {
    processFn(items[i]);
    if (i % BATCH_SIZE === 0) {
      await yieldToMain(); // Nhường main thread để xử lý click / gõ phím
    }
  }
}
```

### Sử dụng Long Animation Frames API (LoAF) để đo đạc thực tế

```javascript
if ('PerformanceObserver' in window && PerformanceObserver.supportedEntryTypes.includes('long-animation-frame')) {
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (entry.duration > 100) { // Frame bị trễ nghiêm trọng
        console.warn('Phát hiện LoAF trễ:', {
          duration: entry.duration,
          blockingDuration: entry.blockingDuration,
          scripts: entry.scripts.map(s => ({
            invoker: s.invoker,
            duration: s.duration,
            sourceURL: s.sourceURL
          }))
        });
      }
    }
  });
  observer.observe({ type: 'long-animation-frame', buffered: true });
}
```

---

## 2. Largest Contentful Paint (LCP) Optimization

### Image Preloading & High Fetch Priority

Ảnh LCP (Hero Banner / Ảnh đại diện sản phẩm) bắt buộc phải được tải sớm nhất có thể:

```html
<!-- Trong thẻ <head> của HTML hoặc Next.js Metadata -->
<link 
  rel="preload" 
  as="image" 
  href="/images/hero-banner.webp" 
  type="image/webp" 
  fetchpriority="high"
/>

<!-- Thẻ <img> hiển thị LCP -->
<img 
  src="/images/hero-banner.webp" 
  alt="Sản phẩm nổi bật" 
  width="1200" 
  height="630" 
  fetchpriority="high" 
  loading="eager" 
  decoding="async"
/>
```

*Quy tắc bất biến LCP:*
- **CẤM** đặt `loading="lazy"` cho phần tử LCP.
- Luôn khai báo tường minh `width` và `height` (hoặc `aspect-ratio` trong CSS) để loại bỏ CLS.
- Ưu tiên định dạng WebP hoặc AVIF thay vì PNG/JPEG thô.

---

## 3. Cumulative Layout Shift (CLS) Prevention

### Đặt chỗ kích thước (Aspect Ratio & Min-Height Sizing)

Tránh giật layout khi tải ảnh, video, banner quảng cáo hoặc dữ liệu bất đồng bộ:

```css
/* Bảo toàn không gian hiển thị trước khi media nạp xong */
.responsive-media-container {
  aspect-ratio: 16 / 9;
  width: 100%;
  background-color: #f1f5f9; /* Skeleton background */
}

/* Khung quảng cáo hoặc Dynamic Banner */
.dynamic-slot {
  min-height: 250px;
  contain-intrinsic-size: 300px 250px;
  content-visibility: auto;
}
```

### Chống FOUT / FOIT với Web Fonts

```css
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter.woff2') format('woff2');
  font-display: swap; /* Tránh text bị tàng hình khi tải font */
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6;
}
```

---

## 4. Bundle Size & Code Splitting

### Dynamic Import & Lazy Loading Component nặng

Chỉ nạp các thư viện nặng (biểu đồ, trình soạn thảo WYSIWYG, map) khi người dùng kích hoạt:

```typescript
import dynamic from 'next/dynamic';

// Next.js Dynamic Component
const HeavyChart = dynamic(() => import('@/components/HeavyChart'), {
  loading: () => <div className="h-64 animate-pulse bg-gray-100 rounded-lg" />,
  ssr: false // Tắt SSR nếu thư viện phụ thuộc trực tiếp vào window/canvas
});

// React Native / Standard Web Dynamic Import
const handleExportPDF = async () => {
  const { generatePDF } = await import('@/lib/pdf-generator');
  await generatePDF(data);
};
```

---

## 5. N+1 Query & Database Bottlenecks

### Dataloader / Batching Pattern

Tránh thực hiện N câu truy vấn đơn lẻ trong vòng lặp:

```typescript
import DataLoader from 'dataloader';

// Thay vì: items.map(i => db.user.findUnique({ where: { id: i.userId } }))
// Sử dụng DataLoader gom nhóm thành 1 câu truy vấn IN:
const userLoader = new DataLoader(async (userIds: readonly string[]) => {
  const users = await prisma.user.findMany({
    where: { id: { in: [...userIds] } }
  });
  const userMap = new Map(users.map(u => [u.id, u]));
  return userIds.map(id => userMap.get(id) || null);
});
```
