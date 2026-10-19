# AI, LLM, and Agent Hunting Reference

Tài liệu tham chiếu chuyên sâu dành cho tác tử khi mục tiêu có mô hình ngôn ngữ (LLM) tham gia vào các quyết định nhạy cảm về tin cậy (trust-sensitive decisions): Chatbots, AI Assistants, RAG pipelines, bộ nhớ tác tử (persistent memory), vòng lặp gọi công cụ (tool-calling loops), MCP servers và clients, mã nguồn dựng prompt từ input của người dùng, hoặc mã nguồn tiêu thụ output của model để kích hoạt hành động.

Luồng dữ liệu cốt lõi: **untrusted content → model or memory → capability, authority, or sink**.

---

## 1. Kỷ Luật Cốt Lõi (Core Discipline)

- **Prompt injection đơn thuần KHÔNG PHẢI là một lỗ hổng bảo mật.** Bắt buộc phải có lỗi phá vỡ ranh giới ở cấp mã nguồn (code-level boundary failure): nội dung lọt vào ngữ cảnh của chủ thể khác (cross-principal context), kích hoạt thẩm quyền mà requester không có, làm lộ dữ liệu requester không được phép đọc, hoặc kích hoạt một sink mà requester không thể chạm tới trực tiếp.
- **Model output, bộ nhớ (memory), mô tả công cụ (tool descriptions), và phản hồi MCP (MCP responses) đều là UNTRUSTED INPUTS.** Luôn chỉ rõ dòng code nào đã trao quyền, tin tưởng output một cách mù quáng, ghi nhận trạng thái bền vững, hoặc cấp dữ liệu cho sink nhạy cảm.
- **Guardrail prompt KHÔNG PHẢI là một ranh giới bảo mật.** Chỉ công nhận các kiểm tra tất định (deterministic checks), ủy quyền theo phạm vi tài nguyên (resource-scoped authorization), cô lập (isolation), ràng buộc hành động (action-binding), và thông tin xác thực bị giới hạn (constrained credentials).
- **Mô tả cụ thể danh tính và tác động:** Kẻ tấn công (attacker), chủ thể bị ảnh hưởng (affected principal), danh tính thực thi hiệu dụng (effective execution identity), tài nguyên (resource), hành động chính xác (exact action), thẩm quyền sử dụng (authority used), và tác động quan sát được (observable impact). Yêu cầu trực tiếp có chủ ý sử dụng quyền hạn hiện có của requester không phải lỗi ủy quyền chỉ vì có model thực thi.
- **Phân định Authorization và Action-Binding:** Nội dung do attacker kiểm soát gây ra hành động dưới quyền hạn hợp lệ của nạn nhân là lỗi action-binding khi nạn nhân KHÔNG chủ ý yêu cầu hoặc phê duyệt hành động chính xác đó.
- **Phân loại phán quyết:**
  - `confirmed`: Chỉ khi có bằng chứng mã nguồn (source evidence) VÀ kiểm chứng cục bộ có giới hạn (bounded local validation) xác lập ranh giới bị phá vỡ và kết quả thực tế.
  - `needs_validation`: Khi hành vi phụ thuộc vào nhà cung cấp bên ngoài (provider), hạ tầng triển khai (deployment), mô hình (model), trình dựng giao diện (renderer), hoặc cấu hình danh tính chưa thể quan sát được trên môi trường cục bộ.

---

## 2. Các Lớp Tấn Công Ngữ Cảnh, Truy Xuất và Bộ Nhớ (Context, Retrieval & Memory)

### 2.1 Indirect Injection Through Retrieved or Ingested Content
Kẻ tấn công có thể ghi nội dung vào tài liệu RAG, trang web được lập chỉ mục, tệp, email, issue body, phản hồi công cụ (tool response), hoặc metadata lọt vào context của model thuộc về chủ thể khác.
- **Cách rà soát:** Truy vết ai có quyền ghi vào từng nguồn, cách bộ truy xuất (retrieval) giới hạn phạm vi, phiên (session) của ai tiêu thụ nó, và capability nào được kích hoạt ở đó. Kiểm tra riêng biệt tính cô lập, ủy quyền tài nguyên, và ràng buộc ý định của chủ thể tiêu thụ. Lỗi nằm ở việc thiếu kiểm soát tất định, không phải bản thân văn bản mang tính thuyết phục.

### 2.2 Cross-Session hoặc Cross-Tenant Context Bleed
Lịch sử hội thoại, vector embeddings, kết quả tìm kiếm/truy xuất, hoặc bộ nhớ đệm prompt (prompt cache) được đánh key quá rộng hoặc dùng chung.
- **Cách rà soát:** Xác minh bộ lọc tenant và ACL ngay trong câu truy vấn cơ sở dữ liệu và từng cache key. Trường tenant lưu trong object không có giá trị bảo vệ nếu một truy vấn thay thế, shared cache, hoặc luồng xử lý hàng loạt (batch) bỏ qua nó.

### 2.3 Persistent Memory Poisoning
Nội dung do attacker kiểm soát hoặc tóm tắt của model được ghi vào bộ nhớ bền vững (persistent memory) và sau đó định hình tác vụ, người dùng, hoặc phiên đặc quyền khác.
- **Cách rà soát:** Ai có quyền tạo, cập nhật, hợp nhất (merge), và xóa bộ nhớ; nguồn gốc (provenance) và phạm vi tenant; các quan sát có độ tin cậy thấp có bị biến thành hướng dẫn bền vững hoặc sự thật (facts) không; bộ truy xuất có phân biệt tùy chọn người dùng với chính sách công cụ không. Bộ nhớ do chính người dùng lưu có chủ ý và chỉ dùng cho các yêu cầu được phép của chính họ không phải là lỗi.

### 2.4 Prompt Role và Provenance Confusion
Việc ghép prompt cho phép văn bản không tin cậy mạo danh system message, lượt hội thoại trước (prior turn), kết quả công cụ (tool result), chính sách (policy), hoặc bản ghi bộ nhớ.
- **Cách rà soát:** Tìm kiếm việc nối chuỗi (string concatenation), lịch sử hội thoại không định kiểu (untyped history), trường role do caller kiểm soát, và các vòng tuần hoàn chuyển đổi dữ liệu (serialization round trips) làm mất nhãn nguồn. Xác nhận danh tính giả mạo có làm thay đổi quyết định tin cậy tất định hoặc kích hoạt capability có ý nghĩa không.

---

## 3. Các Lớp Tấn Công Công Cụ và Hành Động (Tool & Action)

### 3.1 Tool-Argument Injection into Downstream Sink
Đối số do model sinh ra được đưa thẳng vào SQL, shell, filesystem, URL-fetch, hoặc privileged APIs mà không có kiểm tra hợp lệ ở phía handler.
- **Cách rà soát:** Xem schema của công cụ chỉ như bộ phân tích cú pháp (input parsing), theo dõi từng trường từ khi giải mã đến sink. Cấu trúc output có thể thu hẹp kiểu dữ liệu nhưng không xác lập tính hợp quyền, đường dẫn an toàn, URL an toàn, hoặc ngữ nghĩa truy vấn an toàn.

### 3.2 Excessive Agency và Confused-Deputy Authority
Tác tử sử dụng danh tính dịch vụ (service identity) hoặc thông tin xác thực quá rộng (broad credential), trong khi handler của công cụ không kiểm tra lại quyền hạn của chủ thể yêu cầu trên tài nguyên được chỉ định.
- **Cách rà soát:** Xác minh cả danh tính thực thi hiệu dụng và liệu caller có thể thực hiện thao tác chính xác đó qua giao diện thông thường của sản phẩm hay không. Một credential dùng chung nhưng có bắt buộc phạm vi truy vấn cho từng user thì không phải là lỗi.

### 3.3 Action-Confirmation và Approval Binding
Người dùng phê duyệt một hành động được mô tả, nhưng quá trình thực thi lại sử dụng các đối số đã bị thay đổi, tài nguyên khác, chủ thể khác, hoặc lượt gọi model sau đó.
- **Action-Binding Invariant:** Một lỗi action-binding tồn tại khi nội dung do attacker kiểm soát gây ra tác dụng phụ (side-effect) dưới quyền hạn hợp lệ của nạn nhân mà nạn nhân không hề có chủ ý yêu cầu hoặc phê duyệt, ngay cả khi kiểm tra authorization chung cho phép nạn nhân thực hiện thao tác đó.
- **Cách rà soát:** Kiểm tra xem xác nhận ý định có ràng buộc chặt chẽ tên công cụ đã chuẩn hóa, toàn bộ object đối số, requester, đối tượng mục tiêu, số lượng/giá trị, hạn dùng (expiry), và batch membership hay không. Kiểm tra các cơ chế thử lại (retry) và khôi phục phiên (resumed session): một lần phê duyệt tuyệt đối không được cấp phép cho một thao tác bị biến đổi hoặc nhân bản tác dụng phụ.

### 3.4 Tool-Schema và Dispatcher Disagreement
Schema chấp nhận alias, trường thừa, duplicate keys, ép kiểu ngầm, object tự do lồng nhau, hoặc giá trị ngoài phạm vi mà dispatcher hoặc handler diễn giải theo cách khác.
- **Cách rà soát:** So sánh việc kiểm tra schema, canonicalization, generated bindings, và giá trị mặc định của handler. Kiểm định lại ở những nơi giá trị trở thành bộ chọn tài nguyên (resource selector) hoặc tùy chọn bảo mật.

### 3.5 Unbounded Delegated Action Loops
Một yêu cầu có giới hạn có thể kích hoạt vòng lặp chi tiêu lặp lại, gửi tin nhắn, sửa đổi dữ liệu, hoặc gọi API bên ngoài mà không có ngân sách trên mỗi request, authorization trên từng hành động, cơ chế hủy (cancellation), hoặc kiểm soát tính lũy thừa (idempotency).
- **Cách rà soát:** Đánh giá tác động đến chi phí chung, hạn ngạch (quotas), người dùng khác, hoặc trạng thái bền vững. Không kiểm thử bằng cách làm cạn kiệt dịch vụ; dùng hạch toán ở cấp mã nguồn và vòng lặp có giới hạn cục bộ.

---

## 4. Ranh Giới Tin Cậy MCP và Tác Tử Con (MCP & Sub-Agent Trust)

### 4.1 Sub-Agent và MCP Trust Inheritance
Một tác vụ được ủy quyền nhận toàn bộ phiên làm việc, credentials, bộ nhớ, hoặc capabilities thay vì quyền tối thiểu (least privilege).
- **Cách rà soát:** Kiểm tra principal và tenant được truyền vào từng lệnh gọi, khả năng thu hẹp capability, phạm vi đối tượng credential (audience), và kết quả ủy quyền có được xử lý như untrusted khi nhận lại hay không.

### 4.2 MCP Server và Tool Identity Confusion
Lệnh gọi hoặc kết quả được định tuyến dựa trên tên server, tên công cụ, request ID, resource URI, hoặc alias do model lựa chọn mà kẻ tấn công có thể tác động, thay vì dựa trên kết nối đã xác thực và yêu cầu đang chờ xử lý.
- **Cách rà soát:** Liệu hai servers có thể tự nhận cùng một danh tính công cụ hoặc tài nguyên; việc kết nối lại (reconnect) có làm thay đổi liên kết; và phản hồi từ server này có thể thỏa mãn request đang chờ của server khác hay không.

### 4.3 MCP Metadata và Schema as Policy
Mô tả công cụ, metadata tài nguyên, prompts, gợi ý hoàn thành, hoặc schema do MCP peer cung cấp được tin tưởng như chính sách bảo mật hoặc ủy quyền.
- **Cách rà soát:** Các trường này chỉ dùng để định hướng cho model nhưng KHÔNG THỂ cấp capability. Tìm kiếm allowlist tất định, kiểm tra danh tính server, và cơ chế ủy quyền của handler để đảm bảo luôn giữ quyền quyết định tối cao khi metadata xung đột.

---

## 5. Ranh Giới Đầu Ra và Tiết Lộ Dữ Liệu (Output & Disclosure)

### 5.1 Insecure Output Rendering
Output của model được đưa thẳng vào HTML, Markdown, template engine, URL redirection, hoặc command sink mà không qua bộ mã hóa (encoding) và chính sách bắt buộc của sink đó.
- **Cách rà soát:** Kiểm tra tài nguyên tự động tải (auto-loaded resources), CSP headers, và cơ chế làm sạch (sanitization). Nếu hành vi renderer nằm ngoài repository, đánh dấu finding là `needs_validation`.

### 5.2 Sensitive Context Extraction
Context được lắp ráp chứa credentials, dữ liệu của người dùng khác, mã nguồn riêng tư, hoặc các giá trị chính sách tự cấp quyền truy cập, và output do người dùng tác động làm lộ chúng.
- **Cách rà soát:** Đọc kỹ mã nguồn lắp ráp prompt và lấy dữ liệu. Việc tiết lộ hướng dẫn chung chung không vi phạm ranh giới dữ liệu thì không tính là lỗ hổng.

---

## 6. Quy Tắc Nghiệm Thu Báo Cáo (Validation Rules)

1. Nêu rõ ranh giới bị vượt qua và kết quả quan sát được: Kẻ tấn công, chủ thể bị ảnh hưởng hoặc tài nguyên chung, danh tính thực thi, mục tiêu, và hành động hoặc sự tiết lộ trái phép/không mong muốn.
2. Với lỗi confused-deputy: Chứng minh tool thiếu cơ chế kiểm tra quyền hạn kết hợp giữa requester và resource, và attacker không thể thực hiện hành động đó một cách thông thường.
3. Với lỗi action-binding: Chứng minh nội dung do attacker kiểm soát gây ra hành động dưới quyền hạn nạn nhân mà nạn nhân không chủ ý yêu cầu.
4. Với lỗi memory/retrieval: Chỉ ra cả vị trí ghi do attacker kiểm soát và vị trí đọc chéo chủ thể (cross-principal read) hoặc quyết định đặc quyền về sau.
5. Với lỗi MCP identity: Xác minh kết nối xác thực, tương quan request, namespace của tool, và credential hiệu dụng. Ghi nhận `needs_validation` nếu cần hạ tầng định tuyến triển khai bên ngoài.
