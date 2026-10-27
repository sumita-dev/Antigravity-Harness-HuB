---
name: interview-me
description: "Trích xuất ý định thực tế qua phỏng vấn 1 câu/lượt kèm giả thuyết, đạt >=95% độ tin cậy trước khi lập spec/code."
metadata:
  origin: Addy Osmani (agent-skills)
---

# Kỹ Năng: Interview Me (Trích Xuất Ý Định Thực Tế)

## Tổng Quan (Overview)

Những gì người dùng yêu cầu ban đầu và những gì họ thực sự mong muốn thường có khoảng cách rất lớn. Họ thường nói "làm cho tôi một dashboard" vì đó là thuật ngữ thông thường nảy ra trong đầu, không phải vì dashboard giải quyết đúng nút thắt của họ. Họ nói "làm cho nó nhanh hơn" mà không có một con số cụ thể để đo lường.

Thời điểm rẻ nhất để tìm ra khoảng cách này là **trước khi bất kỳ spec, kế hoạch hay dòng code nào xuất hiện**. Một khi đã bắt tay vào code, chi phí chuyển đổi (switching costs) sẽ tăng vọt, và người dùng sẽ có xu hướng hợp lý hóa thứ đang làm dở thành "thế này cũng tạm ổn". Sự sai lệch lúc đó sẽ bị khóa chặt vào hệ thống.

Kỹ năng này thu hẹp khoảng cách ngay từ đầu với chi phí bằng 0. Trong khi các kỹ năng khác giả định bạn đã biết mình muốn gì, `interview-me` là bước đi trước: phỏng vấn từng câu một, gắn kèm giả thuyết tốt nhất của bạn, cho đến khi bạn có thể đoán trước được phản ứng của người dùng trước khi họ trả lời.

---

## Khi Nào Sử Dụng (When to Use)

Kích hoạt kỹ năng này khi:
- Yêu cầu còn thiếu ít nhất một trong các yếu tố: **ai** sử dụng (Who), **tại sao** cần (Why), định nghĩa **thành công** là gì (Success), **ràng buộc** then chốt là gì (Constraint).
- Yêu cầu mang tính quy ước chung chung ("làm cho tôi cái X", "tối ưu hệ thống") mà bạn không thể phân rã nếu không đoán mò.
- Bạn cảm thấy bị cám dỗ muốn tự động điền các giả định ngầm chưa được người dùng xác nhận.
- Hai giá trị kỹ thuật hợp lý đang xung đột nhưng người dùng chưa chỉ định rõ ưu tiên (đơn giản vs linh hoạt, chi phí vs tốc độ).
- Người dùng gõ lệnh hoặc nói rõ: `/interview-me`, "interview me", "grill me", "chất vấn tôi đi", "kiểm tra lại tư duy".

**Khi KHÔNG sử dụng:**
- Yêu cầu đã rõ ràng, khép kín và tự định nghĩa ("đổi tên biến này", "sửa lỗi chính tả").
- Người dùng yêu cầu tốc độ thay vì kiểm chứng kỹ lưỡng ("cứ làm nhanh đi").
- Các câu hỏi thuần tra cứu thông tin ("X hoạt động thế nào?", "code này làm gì?").
- Thao tác cơ học (format code, đổi tên file, di chuyển thư mục).
- Bạn đã có độ tin cậy $\ge 95\%$ (kiểm tra lại điều kiện dừng trước khi hỏi).

---

## Ràng Buộc Tải & Môi Trường (Loading Constraints)

Kỹ năng này đòi hỏi một người dùng tương tác trực tiếp:
- **Tuyệt đối không kích hoạt trong ngữ cảnh phi tương tác** như CI pipelines, cron schedules, hoặc vòng lặp tự trị đóng kín. Nếu gặp yêu cầu mơ hồ trong môi trường tự động, hãy gắn cờ chặn (blocker) thay vì đoán mò.
- Trong Antigravity 2.0, Quản đốc (Chief Orchestrator) sử dụng công cụ `ask_question` để điều phối phỏng vấn trực tiếp với Sếp.

---

## Tích Hợp Antigravity 2.0 & Dynamic Triad

1. **Cổng Xác Nhận Ý Định (Intent Alignment Gate):**
   - Vận hành tại tầng Pre-Spec. Trước khi bàn giao cho SubAgent Architect lập Spec 5 mục, Quản đốc kích hoạt `/interview-me` nếu yêu cầu có dấu hiệu mơ hồ.
2. **Kỷ Luật 1 Câu Hỏi/Lượt Qua `ask_question`:**
   - Cấm gom 3-4 câu hỏi vào một lúc. Quản đốc đặt 1 câu hỏi cụ thể kèm giả thuyết và các lựa chọn định hướng qua `ask_question`.
3. **Cầu Dao Dừng Cuối Phiên (Terminal Turn & Stop Rule):**
   - Khi Sếp xác nhận rõ ràng "Duyệt" hoặc "Yes" đối với Biên bản Ý định (Statement of Intent), Quản đốc **DỪNG TURN NGAY LẬP TỨC**. Cấm tự ý gọi tool can thiệp mã nguồn trong cùng lượt đó.

---

## Quy Trình 6 Bước Chuẩn Mực (The 6-Step Process)

### Bước 1: Thiết lập giả thuyết kèm chỉ số tin cậy (Hypothesize with confidence)

Trước khi hỏi, viết ra một câu tóm tắt nhận định hiện tại kèm % tin cậy trung thực (0–100%):

```text
HYPOTHESIS: Sếp muốn có cách trả lời "tiến độ thế nào?" trong buổi họp standup, và "dashboard" là từ quen thuộc nảy ra trong đầu.
CONFIDENCE: ~30% — thiếu: ai sẽ xem, các chỉ số cụ thể là gì, và tiêu chí thành công ra sao.
```

*Quy tắc:* Khi confidence $< 70\%$, bắt buộc ghi rõ lý do còn thiếu sót trên cùng dòng.

### Bước 2: Hỏi từng câu một, luôn đính kèm giả thuyết phán đoán (Ask one at a time + Guess)

Định dạng chuẩn:
```text
Q: Khi Sếp nói "theo dõi thí nghiệm", ai là người trực tiếp xem — một mình Sếp, cả đội kỹ thuật, hay báo cáo lên cấp quản lý?
GUESS: Dự đoán là một mình Sếp, vì quy mô hiện tại là thử nghiệm cá nhân. Nếu cho ban quản lý thì cấu trúc báo cáo sẽ hoàn toàn khác.
```

**Tại sao phải gắn kèm dự đoán (GUESS):**
- Con người phản ứng và sửa sai trước một phỏng đoán nhanh hơn rất nhiều so với việc phải tự suy nghĩ câu trả lời từ con số 0.
- Nó bộc lộ các giả định ngầm của AI để người dùng uốn nắn kịp thời.

### Bước 3: Lắng nghe và phân biệt "Muốn" vs "Nghĩ là nên muốn" (Want vs. Should Want)

Cảnh giác trước các câu trả lời mang tính khẩu hiệu hoặc quy ước mẫu sách giáo khoa:
- Dùng buzzwords: "phải thật scalable", "clean architecture chuẩn mực", "theo best practice".
- Trả lời bằng thói quen: "cách các ứng dụng khác hay làm".

Khi phát hiện dấu hiệu này, hãy dùng câu hỏi chốt chặn:
> *"Nếu không phải giải trình hay chứng minh phương pháp với bất kỳ ai, Sếp thực sự muốn kết quả cuối cùng như thế nào?"*

### Bước 4: Tuyên bố lại ý định bằng ngôn ngữ của người dùng (Restate Intent)

Khi độ tin cậy đã cao, đúc kết lại bức tranh thành 5-8 dòng súc tích:

```text
Biên bản xác nhận ý định (Statement of Intent):
- Outcome (Kết quả):       Một danh sách phẳng theo dõi 10 thử nghiệm đang chạy kèm trạng thái.
- User (Người dùng):        Một mình Sếp sử dụng hàng ngày.
- Why now (Lý do):          Các file note đang phân tán ở 5 nơi khác nhau gây sót việc.
- Success (Thành công):    Mở ra thấy ngay thử nghiệm nào đang chạy và kết quả sơ bộ trong 5 giây.
- Constraint (Ràng buộc):  Dùng file Markdown hoặc JSON đơn giản, không dựng database phức tạp.
- Out of scope (Ngoài lề): Phân quyền người dùng, biểu đồ đồ họa, thông báo qua email.

Sếp duyệt phương án này chưa / có cần tinh chỉnh điểm nào không?
```

*Lưu ý:* Mục `Out of scope` là bắt buộc. Một nửa sự sai lệch bắt nguồn từ việc không thống nhất những gì **không** làm.

### Bước 5: Xác nhận tường minh (Explicit Yes)

Chốt chặn chỉ mở khi người dùng nói "Có", "Duyệt", "Yes".
Các trường hợp sau **KHÔNG PHẢI** là đồng ý:
- "Tùy em thấy cái nào tốt thì làm." $\rightarrow$ Người dùng đang ủy quyền vì bản thân họ cũng chưa rõ. Hãy tách thành 2 lựa chọn cụ thể để họ chọn.
- "Trông cũng ổn đấy." $\rightarrow$ Mơ hồ. Hỏi lại: "Có điểm nào Sếp muốn gọt bớt không?".
- Im lặng rồi bảo "cứ code đi". $\rightarrow$ Dấu hiệu người dùng bị mệt. Cần dừng lại rà soát.

### Bước 6: Cầu dao dừng lượt (Terminal Turn & Stop Rule)

Khi nhận được sự xác nhận rõ ràng:
1. Trình bày lại bản **Statement of Intent** đã chốt.
2. Đề xuất các bước tiếp theo (Lưu vào `docs/intent/<tên>.md`, chuyển giao cho SubAgent Architect lập Spec).
3. **DỪNG LƯỢT NGAY LẬP TỨC.** Tuyệt đối không tự ý chạy tool hay bắt đầu code trong lượt này.

---

## Điều Kiện Dừng 95% Độ Tin Cậy (The 95% Confidence Stop)

Bạn hoàn thành phỏng vấn khi có thể tự tin trả lời "CÓ" cho câu hỏi:
> *"Mình có thể đoán trước được phản ứng của người dùng đối với 3 câu hỏi tiếp theo không?"*

Nếu có: Dừng phỏng vấn và xuất bản Restate.
Nếu không: Tiếp tục đào sâu câu hỏi tiếp theo.

---

## Bảng Đối Soát Chống Ngụy Biện (Anti-Rationalization Table)

| Ngụy biện thường gặp | Thực tế kiểm chứng |
|---|---|
| "Yêu cầu thế này là đủ rõ rồi" | Nếu bạn không thể viết ra kết quả mong muốn trong đúng 1 câu, nó chưa hề rõ. |
| "Hỏi nhiều làm mất thời gian của Sếp" | Mất 3 phút hỏi 4 câu còn hơn mất 3 ngày code sai hướng rồi đập đi làm lại. |
| "Cứ vừa làm vừa khám phá" | Chi phí sửa chữa khi code đã thành hình đắt gấp 10 lần lúc còn là ý niệm. |
| "Sếp bảo 'tùy em', nghĩa là mình tự quyết" | "Tùy em" là bỏ cuộc, không phải quyết định. Cần thu hẹp thành bài toán lựa chọn A/B. |

---

## Bảng Dấu Hiệu Cảnh Báo (Red Flags)

- Đặt từ 3 câu hỏi trở lên trong một tin nhắn (Hỏi dồn dập khiến người dùng trả lời lướt).
- Đặt câu hỏi mà không gắn kèm dự đoán (`GUESS`).
- Tự ý sinh Spec hoặc code trước khi người dùng xác nhận bản Restate.
- Chấp nhận câu trả lời sáo rỗng ("hiện đại", "chuẩn enterprise") mà không đào sâu bản chất.
- Không có mục "Out of scope" trong bản Restate.

---

## Checklist Kiểm Định (Verification Checklist)

- [ ] Đã nêu giả thuyết kèm % độ tin cậy ngay từ lượt đầu tiên.
- [ ] Mọi chỉ số tin cậy $< 70\%$ đều có lý do giải thích nguyên nhân chưa rõ.
- [ ] Phỏng vấn từng câu một, luôn đính kèm dự đoán (`GUESS`).
- [ ] Đã đào sâu ít nhất một lần để bóc tách giữa "muốn thực sự" và "nghĩ là nên muốn".
- [ ] Đã gửi bản Restate đầy đủ 6 thành phần (Outcome, User, Why now, Success, Constraint, Out of scope).
- [ ] Người dùng đã xác nhận rõ ràng bằng "Có" / "Duyệt" / "Yes".
- [ ] Dừng lượt ngay lập tức sau khi được xác nhận, không gọi tool hay sửa mã nguồn bừa bãi.
