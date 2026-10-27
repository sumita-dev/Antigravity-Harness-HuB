---
name: doubt-driven-development
description: "Phản biện đối kháng với ngữ cảnh cô lập (Fresh-Context Adversarial Review) cho quyết định quan trọng."
metadata:
  origin: Addy Osmani (agent-skills)
---

# Kỹ Năng: Doubt-Driven Development (Phản Biện Đối Kháng Ngữ Cảnh Cô Lập)

## Tổng Quan (Overview)

Một câu trả lời tự tin không đồng nghĩa với một câu trả lời chính xác. Trong các phiên làm việc kéo dài, ngữ cảnh tích lũy dần biến các giả định mơ hồ ban đầu thành "sự thật hiển nhiên" mà không ai nhận ra.

`Doubt-Driven Development` (Phát triển dựa trên sự hoài nghi) là kỷ luật triệu tập một **Reviewer độc lập với ngữ cảnh tươi mới (Fresh-Context Reviewer)**, được thiết lập thiên kiến mặc định là **phản bác và tìm lỗi (Disprove, not approve)**, trước khi bất kỳ quyết định quan trọng nào được chốt hạ.

Đây không phải là bước review tổng kết cuối cùng (`/gitnexus-review` hay hoàn tất PR). Đây là tư thế phản biện ngay trong lúc thực thi: thẩm vấn đối kháng các quyết định phi tầm thường ngay khi chi phí thay đổi còn rẻ nhất.

---

## Khi Nào Sử Dụng (When to Use)

Một quyết định được coi là **phi tầm thường (non-trivial)** khi thỏa mãn ít nhất một trong các điều kiện sau:
1. Tạo mới hoặc thay đổi logic rẽ nhánh cốt lõi (branching logic).
2. Tác động xuyên ranh giới giữa các module, service hoặc gói thư viện.
3. Khẳng định một thuộc tính mà hệ thống kiểu dữ liệu (type system) hoặc compiler không thể tự kiểm tra (tính an toàn đa luồng/thread safety, tính lũy thừa/idempotence, thứ tự thực thi, tính toàn vẹn dữ liệu).
4. Tính đúng đắn phụ thuộc vào ngữ cảnh ngầm mà người đọc trong tương lai không thể thấy trực tiếp trong code.
5. Bán kính ảnh hưởng (blast radius) không thể đảo ngược (triển khai production, migration dữ liệu lớn, thay đổi public API).

**Khi KHÔNG sử dụng:**
- Thao tác cơ học thuần túy (đổi tên biến, format code, di chuyển tệp).
- Làm theo chỉ thị trực tiếp, tường minh, không có rủi ro từ người dùng.
- Thao tác công cụ đơn thuần (chạy test suite, liệt kê danh sách tệp).
- Mã nguồn ngắn, hiển nhiên đúng, không có rẽ nhánh logic phức tạp.

*Nguyên tắc:* Nếu hoài nghi từng phím gõ, bạn sẽ không bao giờ xuất xưởng được sản phẩm. Kỹ năng chỉ áp dụng cho quyết định phi tầm thường.

---

## Ràng Buộc Tải & Môi Trường (Loading Constraints)

- Kỹ năng này dành riêng cho **Quản đốc Hệ thống (Chief Orchestrator)**. Quản đốc có quyền triệu tập tác tử con với ngữ cảnh độc lập.
- **Cấm gọi lồng nhau (No Nested Persona Spawn):** Tác tử con không được tự ý spawn tác tử phản biện khác. Mọi sự điều phối phản biện đều phải thông qua Quản đốc.

---

## Tích Hợp Antigravity 2.0 & Dynamic Triad

1. **Triệu Tập SubAgent Code Critic Độc Lập:**
   - Quản đốc ủy quyền phản biện cho `SubAgent Code Critic` bằng `invoke_subagent`.
   - **Ép phân tầng Model tường minh:** Bắt buộc dùng `Model: "flash"` cho Critic, cấm dùng `inherit` để tối ưu chi phí và tăng tính khách quan của kiến trúc mô hình khác biệt.
   - **Cô lập không gian làm việc:** Sử dụng `Workspace: 'branch'` hoặc `Workspace: 'share'` để tránh xung đột tài nguyên.
2. **Quy Tắc Cách Ly Ngữ Cảnh Tuyệt Đối (Zero Prior Bias Invariant):**
   - Khi chuyển giao cho Critic, Quản đốc **CHỈ TRUYỀN** `ARTIFACT` (mã nguồn/thiết kế) và `CONTRACT` (ràng buộc kỹ thuật).
   - **CẤM TUYỆT ĐỐI** truyền các lập luận, lý do biện hộ hoặc khẳng định chủ quan của tác giả ban đầu (`CLAIM`). Việc truyền lập luận của tác giả sẽ làm tha hóa tính khách quan của Critic.
3. **Cầu Dao Ngắt Mạch (Decoupled Circuit Breakers):**
   - Hạn ngạch: `critic_rounds <= 2`, `total_cycles <= 3`. Nếu sau 2 lượt mà Maker và Critic không đồng thuận, kích hoạt trạng thái `ESCALATED`, dừng vòng lặp và trình bằng chứng cho Sếp phân xử.

---

## Quy Trình 5 Bước Chuẩn Mực (The 5-Step Process)

Sao chép checklist này khi áp dụng:
```text
Chu trình Hoài Nghi (Doubt Cycle):
- [ ] Bước 1: CLAIM — Nêu rõ khẳng định kỹ thuật & lý do tại sao nó quan trọng.
- [ ] Bước 2: EXTRACT — Cô lập đối tượng kiểm định (Artifact + Contract), gọt sạch lý lẽ biện hộ.
- [ ] Bước 3: DOUBT — Triệu tập Critic độc lập với prompt đối kháng sắc bén.
- [ ] Bước 4: RECONCILE — Đối soát từng phát hiện của Critic trực tiếp trên văn bản Artifact.
- [ ] Bước 5: STOP — Đạt điều kiện dừng (hết lỗi nghiêm trọng, chạm trần 2 rounds, hoặc Sếp can thiệp).
```

### Bước 1: Khẳng định kỹ thuật (CLAIM)

Định nghĩa quyết định kỹ thuật trong 2-3 dòng:
```text
CLAIM: "Lớp bộ đệm Redis mới an toàn đa luồng (thread-safe) dưới tải đọc cao được mô tả trong spec."
WHY THIS MATTERS: Lỗi tranh chấp tài nguyên (race condition) ở đây sẽ làm hỏng dữ liệu người dùng và cực kỳ khó bắt trong bài test đơn vị.
```

### Bước 2: Tách biệt đối tượng kiểm tra (EXTRACT)

Reviewer độc lập chỉ cần **sản phẩm** và **hợp đồng ràng buộc**, không cần nghe giải thích hành trình:
- Mã nguồn: Chỉ trích xuất Git diff hoặc hàm cần xét — không gửi toàn bộ tệp 1000 dòng.
- Quyết định kiến trúc: Bản đề xuất 3-5 câu kèm các ràng buộc hệ thống.
- **Loại bỏ hoàn toàn lập luận cá nhân của Maker.**

### Bước 3: Thẩm vấn đối kháng (DOUBT)

Prompt gửi cho SubAgent Critic **bắt buộc phải có tính đối kháng (Adversarial)**:

```text
Thẩm định đối kháng (Adversarial Review). Nhiệm vụ của bạn là tìm ra mọi lỗ hổng và rủi ro trong tài liệu/mã nguồn này.
Giả định rằng tác giả đang quá tự tin và chủ quan. Hãy đặc biệt soi xét:
- Các giả định ngầm chưa được chứng minh.
- Các trường hợp biên (edge cases) chưa được xử lý.
- Trạng thái dùng chung tiềm ẩn hoặc phụ thuộc ngầm (hidden coupling / shared state).
- Các nguy cơ vi phạm hợp đồng kỹ thuật (contract violations).
- Khả năng phá vỡ quy ước hiện có của dự án.
- Nguy cơ sập hệ thống khi gặp dữ liệu đầu vào bất thường.

TUYỆT ĐỐI KHÔNG KHEN NGỢI. KHÔNG TÓM TẮT DÀI DÒNG.
Chỉ liệt kê các lỗi/rủi ro cụ thể, hoặc tuyên bố rõ ràng rằng bạn không tìm thấy bất kỳ lỗi nào sau khi đã rà soát toàn diện.

ARTIFACT: <nội dung code/thiết kế>
CONTRACT: <ràng buộc kỹ thuật & tiêu chí chấp nhận>
```

#### Nâng Cấp Phản Biện Đa Mô Hình (Cross-Model Escalation)

Khi giải quyết các vấn đề tối quan trọng (mã hóa mật khẩu, migration database hàng triệu bản ghi), có thể đề xuất Sếp chạy kiểm chứng chéo qua mô hình/CLI khác (Gemini CLI, Codex CLI) bằng chế độ Sandbox chỉ đọc (`--sandbox read-only` hoặc piped qua stdin an toàn).

### Bước 4: Hòa giải và phân loại phát hiện (RECONCILE)

Maker và Quản đốc đối soát các điểm chỉ trích của Critic:
1. **Lỗi thật sự (Valid Issue):** Maker sửa ngay mã nguồn.
2. **Hiểu nhầm do Spec chưa rõ:** Bổ sung ràng buộc vào Contract và làm rõ tài liệu.
3. **Cảnh báo không đúng (False Positive):** Chỉ ra bằng chứng vật lý từ code để phản hồi khách quan.

### Bước 5: Điều kiện dừng (STOP)

- Dừng khi tất cả các phát hiện nghiêm trọng của Critic đã được khắc phục và bài test đạt `exit code == 0`.
- Kích hoạt `ESCALATED` nếu vượt quá 2 vòng lặp mà không tìm được tiếng nói chung.

---

## Bảng Dấu Hiệu Cảnh Báo (Red Flags)

- Truyền cả lập luận của Maker vào prompt của Critic (gây thiên kiến đồng tình).
- Critic trả về văn bản khen ngợi xã giao thay vì vạch ra các rủi ro kỹ thuật.
- Bỏ qua các cảnh báo về race condition hoặc rò rỉ bộ nhớ với lý do "chắc là không sao đâu" (`probably`, `should work`).
- Vòng lặp phản biện chạy quá 3 lần mà không có tiến triển.

---

## Checklist Kiểm Định (Verification Checklist)

- [ ] Đã tách biệt rõ ràng giữa Artifact, Contract và Claim.
- [ ] Đã invoke Critic trong ngữ cảnh cô lập với prompt đối kháng không thiên vị.
- [ ] Sử dụng đúng `Model: "flash"` cho Critic để tạo góc nhìn độc lập.
- [ ] Không có lập luận chủ quan của tác giả bị lọt vào prompt của Critic.
- [ ] Mọi lỗ hổng chỉ ra đều được sửa đổi trực tiếp trên mã nguồn vật lý.
- [ ] Tuân thủ nghiêm ngặt cầu dao ngắt mạch $\le 2$ vòng phản biện.
