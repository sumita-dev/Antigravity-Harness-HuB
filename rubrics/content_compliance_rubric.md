# Rubric Thẩm Định Marketing và Nghiên Cứu

Áp dụng content và research-only. Critic độc lập đối soát dossier, bytes artifacts và baseline đã khóa lúc init, không sửa draft/source.

| Required ID | Tiêu chí |
| --- | --- |
| source_accuracy | Nguồn gốc, ngày công bố/truy xuất, claim/source IDs, units/timeframe, số liệu và trích dẫn đúng evidence |
| policy | Đối soát chính sách liên quan bằng nguồn hiện hành; quyền sử dụng media; báo rủi ro và giới hạn, không bảo đảm nền tảng duyệt |
| integrity | Hash dossier/artifact/baseline/report/evidence hiện tại; đủ claim coverage, actor độc lập, không bịa số liệu/chứng cứ |
| task_quality | Đúng brief/skill, logic rõ và sản phẩm thực sự giúp quyết định của người dùng |

Bốn ID bắt buộc không được Creator chọn/bỏ; checklist và claim_checks phải phủ mọi ID đúng một lần. APPROVE yêu cầu PASS có evidence. Fact có status verified và nguồn kiểm được; unverified không được viết thành factual. Assumption phải hiện rõ `Giả định:` hoặc `Assumption:` ngay excerpt bản thảo; excluded claim không còn literal statement trong artifact. Hash chứng minh bytes không đổi, không tự chứng minh nguồn đúng hoặc paraphrase đúng.

Với Meta Ads/analyzer/money models/research-only: kiểm công thức CPA = spend / conversions, ROAS = revenue / spend, CPM = spend / impressions * 1000; mẫu số 0 và unavailable không giả thành 0. Kiểm tiền tệ, kỳ dữ liệu, timezone, date range, attribution, currency conversion source/date, coverage/truncation/errors. Phân biệt tương quan/nhân quả và tiếng nói mẫu nhỏ/đại diện thị trường. Dossier ghi chất lượng nguồn, hạn chế, số chưa kiểm được.

Hook/CTA và framework AIDA/PAS/Hormozi chỉ chấm khi brief yêu cầu nội dung chuyển đổi. Research-only, phân tích hiệu suất và bảng số liệu không bắt có Hook/CTA; task_quality chấm tính đúng, khả năng tái tính và tính hữu ích của phân tích.

Quét heuristic chỉ phát hiện pattern đáng rà lại; không xác nhận YPP, bản quyền hay an toàn tuyệt đối. Critic dẫn nguồn chính sách cụ thể và thời điểm kiểm, không dùng quy tắc số giây cố định như bảo đảm tuân thủ. Giọng văn rõ, tránh sáo rỗng, không thêm hứa hẹn thiếu căn cứ.

Report file nằm trong configured brain root, được hash bind; marketing payload `report` là PATH absolute tới report thật (khác app report TEXT). Findings có excerpt/location, claim ID, nguồn, tác động và cách sửa. REJECT thứ hai audit → ESCALATED ngay, counter tồn tại qua revise/resubmit/restart. Kết thúc report bằng `VERDICT: APPROVE|REJECT|ESCALATE` theo một phán quyết cụ thể.
