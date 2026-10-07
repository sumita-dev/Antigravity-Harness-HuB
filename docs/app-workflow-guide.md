# Gemini native workflow: local app có preview

Gemini thực hiện các lệnh checkpoint và gọi tác tử; Sếp chỉ cung cấp brief rồi duyệt Spec sau Design Reviewer. CLI không tự gọi Gemini, xác thực human identity hay kiểm browser. Python simulation là công cụ kiểm luồng riêng.

## Prompt dùng trong Antigravity

> /app Hãy xây Task Board chạy local: thêm/sửa/xóa công việc, tiêu đề bắt buộc, trạng thái todo/doing/done, lọc trạng thái và lưu localStorage. Có layout desktop/mobile. Dùng native Architect → Design Reviewer → trình anh duyệt Spec → Builder → QA kiểm test và preview thực tế. Em tự quản checkpoint, commands và artifacts; anh chỉ duyệt Spec một lần. Không deploy. Khi thiếu tool native/browser thì báo rõ giới hạn, không nhận đã kiểm. Bàn giao URL local còn chạy và evidence.

Benchmark này chỉ là đề bài/tiêu chí hướng dẫn, chưa phải app đã được chạy hoặc kiểm chứng trong repo.

## Các bước Sếp chạy thử

1. Mở workspace harness trong Antigravity, chọn Gemini và Python có dependencies: chạy `py -3.12 -m pip install -r requirements.txt` trong terminal harness (hoặc interpreter tương đương). Kiểm tool native subagent/browser có hoạt động.
2. Gửi prompt `/app` ở trên, chỉ định thư mục app thử riêng. Gemini tạo task, gọi Architect rồi Design Reviewer; chưa cho Builder sửa source trước hai bước này.
3. Đọc Spec và review report, sửa brief nếu cần. Khi đúng yêu cầu, xác nhận “Duyệt bản đặc tả này”; Gemini giữ nguyên human_message và đúng hash. Sếp không cần tự chạy từng checkpoint.
4. Theo dõi Builder/QA và mở URL local được bàn giao. Kiểm đủ tám AC, gồm viewport desktop 1280px và mobile 390px. Thử dữ liệu localStorage lỗi chỉ trong key của app thử; không xóa toàn bộ browser storage hay dữ liệu ứng dụng khác.
5. Lưu bảng đánh giá dưới đây cùng checkpoint/report/log/browser artifacts. Nếu thiếu evidence hoặc AC fail, trả QA/Builder xử lý theo counter; không tự ghi PASS vì app hiện được trang đầu.

## Phiếu đánh giá quan sát được

| Mục | Bằng chứng cần lưu | Kết quả |
| --- | --- | --- |
| Architect/Reviewer | Hai actor IDs khác nhau, Spec hash và report thiết kế trước source edits | PASS/FAIL + paths |
| Human signoff | Nguyên văn Sếp duyệt, timestamp, đúng Spec hash | PASS/FAIL |
| Builder | Branch/worktree thực tế, manifest source/test/config và test/build logs | PASS/FAIL |
| QA độc lập | Actor ID khác Builder, context do runtime tạo, command/cwd/exit/log tự rerun | PASS/FAIL |
| Preview | URL local hoạt động, browser evidence từng AC, viewport 1280/390, console/errors | PASS/FAIL |
| AC1–AC8 | Ghi riêng kết quả từng AC và defect/cách tái hiện | PASS/FAIL từng AC |
| Resume và revision | Checkpoint reload đúng, stale source bị chặn, reject counters giữ nguyên | PASS/FAIL |
| Chi phí thực tế | Thời gian bắt đầu/kết thúc, số defects, số vòng sửa từng pha, giới hạn tools | Số đo/ghi chú |

Nghiệm thu chỉ PASS khi mọi gate và toàn bộ AC bắt buộc đạt bằng evidence hiện tại. Nếu thiếu tool/bằng chứng, ghi chưa kiểm; không tính phần trăm trưởng thành tùy ý. Actor ID/log metadata tự khai báo vẫn cần quan sát runtime thực tế, không coi là chứng thực danh tính.

## Checkpoint CLI dành cho Gemini

Chạy từ repo harness; `--project-root` là thư mục app mục tiêu. Interpreter ví dụ Windows có thể thay bằng Python phù hợp đã cài dependencies. Payload/artifact là file thật do agent tạo, không phải log giả.

```powershell
py -3.12 run_harness.py --workflow init --task-id task-board --project-root ./task-board --task "Task Board local" --json
py -3.12 run_harness.py --workflow status --task-id task-board --json
py -3.12 run_harness.py --workflow revise --task-id task-board --payload ./.brain/artifacts/task-board/revise.json --json
py -3.12 run_harness.py --workflow spec --task-id task-board --actor architect-1 --payload ./.brain/artifacts/task-board/spec.json --json
py -3.12 run_harness.py --workflow design-review --task-id task-board --actor reviewer-1 --payload ./.brain/artifacts/task-board/design-review.json --json
py -3.12 run_harness.py --workflow sign-off --task-id task-board --payload ./.brain/artifacts/task-board/sign-off.json --json
py -3.12 run_harness.py --workflow implementation --task-id task-board --actor builder-1 --payload ./.brain/artifacts/task-board/implementation.json --json
py -3.12 run_harness.py --workflow audit --task-id task-board --actor qa-1 --payload ./.brain/artifacts/task-board/audit.json --json
```

Đặt payload/report/log/browser artifacts trong thư mục được manifest loại trừ (ví dụ `.brain/artifacts/`) để không tự làm source snapshot thay đổi. `--payload`, command cwd, log và browser evidence path tương đối resolve từ cwd của lệnh CLI (không tự neo theo project-root); ưu tiên absolute paths của môi trường hiện tại. `report` là nội dung báo cáo text, không phải path được tự đọc. Không ghi source khi làm Reviewer/QA. `status` trả `stage` và `next_agent`; Gemini route theo checkpoint trước keyword. Resume dùng cùng task ID, không suy ra approval từ ký ức và không reset review counter bằng tạo lại task.

`revise` chỉ dùng khi cần đổi thiết kế, với payload `{"reason":"architecture change"}` có lý do thực tế; lệnh vô hiệu Spec/signoff/manifest/evidence, quay DESIGN và giữ reject counters. Có thể mở lại task APPROVED; khi đó phải qua toàn bộ DESIGN → DESIGN_REVIEW → SIGN_OFF → IMPLEMENTATION → AUDIT lần nữa. Task ESCALATED không mở lại bằng revise. Đây không phải bước bắt buộc trong happy path; không chạy revise giữa init và spec khi thiết kế chưa cần đổi. Thiết kế sửa phải qua Reviewer và Sếp duyệt lại đúng bản mới.

Spec JSON có `scope`, `design`, `contracts`, `acceptance_criteria` (list ID/description/ui), `risks`. Review có `verdict`, `spec_sha256`, `report`; signoff có `spec_sha256`, `human_message` nguyên văn xác nhận Sếp. Implementation có `report`. Audit có `verdict`, `spec_sha256`, `manifest_sha256`, `report`, `commands` (command/cwd/exit_code/log), `preview` (url/checks với id/status/reason/evidence). Lấy hashes từ checkpoint, không tự đoán. Actor Reviewer khác Architect; QA khác Builder. Metadata này không xác thực identity runtime.

Human signoff chỉ chấp nhận nguyên câu `Duyệt`, `Duyệt Spec này`, `Duyệt bản đặc tả này`, `SIGN_OFF: approved` hoặc `Bắt đầu code đi`; không phân biệt hoa thường, cho phép khoảng trắng ngoài cùng và prefix `Sếp:`. Không thêm dấu câu cuối hoặc text khác. CLI giữ nguyên message gốc, không tự rút câu duyệt từ câu điều kiện/từ chối/yêu cầu hỏi lại. Câu không khớp bị từ chối: Gemini hỏi Sếp xác nhận bằng một câu rõ ở trên, không sửa thông điệp của Sếp thành approval.

### Payload JSON mẫu

Mẫu một AC dưới đây minh họa schema; benchmark thực tế phải dùng đủ AC1–AC8 và toàn bộ checks tương ứng. Gemini điền Spec đã review, hai hash lấy từ checkpoint và đường dẫn log/evidence thật; không nộp các chuỗi placeholder như bằng chứng.

```json
{"scope":"Task Board local; source/test/config trong project mục tiêu", "design":"UI form/list/filter, trạng thái todo/doing/done và localStorage", "contracts":"title trimmed nonempty; status enum; lỗi storage có fallback theo thiết kế", "acceptance_criteria":[{"id":"AC1","description":"Thêm hợp lệ và từ chối title rỗng","ui":true}], "risks":"Chốt stack và commands; test storage lỗi chỉ key của app"}
```

```json
{"verdict":"APPROVE","spec_sha256":"COPY_FROM_CHECKPOINT","report":"Reviewer đã đối chiếu năm mục và AC; dẫn chứng cụ thể ở đây"}
```

```json
{"spec_sha256":"COPY_FROM_CHECKPOINT","human_message":"Duyệt bản đặc tả này"}
```

```json
{"report":"Builder ghi branch/worktree, source diff, RED/GREEN/build commands và kết quả thật ở đây"}
```

```json
{"verdict":"APPROVE","spec_sha256":"COPY_FROM_CHECKPOINT","manifest_sha256":"COPY_FROM_CHECKPOINT","report":"QA độc lập đã kiểm đúng revision và toàn bộ AC; dẫn chứng ở đây","commands":[{"command":"npm test -- --run","cwd":"./task-board","exit_code":0,"log":"./.brain/artifacts/task-board/qa-tests.log"}],"preview":{"url":"http://localhost:5173","checks":[{"id":"AC1","status":"PASS","evidence":"./.brain/artifacts/task-board/AC1-browser.png"}]}}
```

Command mẫu là minh họa, phải thay bằng command stack thực tế và output thật. Non-UI check dùng `{"id":"AC7","status":"N/A","reason":"Lý do phù hợp Spec"}` nếu hợp đồng cho phép; kiểm thử cần PASS thì QA vẫn phải kiểm, không dùng N/A để tránh AC bắt buộc.

Với UI, `preview.checks` kiểm từng AC và trỏ evidence thật; non-UI dùng N/A có lý do hợp Spec. Một URL hoặc test exit 0 không đủ APPROVE. Source/test/config kể cả untracked thay đổi sau snapshot khiến evidence stale. Nếu đang AUDIT, QA nộp REJECT với hashes của checkpoint và report giải thích source đổi, quay Builder rồi nộp implementation mới; counter code tăng. Nếu phải đổi kiến trúc, dùng revise về DESIGN và review/signoff lại. REJECT thứ hai mỗi pha chuyển ESCALATED; counters giữ qua restart/resubmit.

## Acceptance criteria cho benchmark

| ID | Hành vi cần tự kiểm |
| --- | --- |
| AC1 | Thêm công việc hợp lệ; title rỗng/whitespace hiển thị lỗi và không thêm record. |
| AC2 | Sửa title/status; hủy sửa giữ dữ liệu cũ. |
| AC3 | Xóa đúng công việc; các công việc khác giữ nguyên. |
| AC4 | Filter todo/doing/done/all hiển thị đúng, có empty state. |
| AC5 | Reload giữ dữ liệu localStorage; dữ liệu lỗi được xử lý theo Spec, không làm app trắng. |
| AC6 | Desktop và mobile dùng được; không tràn ngang, nút/form dễ thao tác. |
| AC7 | Chạy test/build thành công; QA tự rerun với command/cwd/exit/log. |
| AC8 | QA mở local preview, thực hiện AC1–AC6, kiểm console và lưu evidence từng AC. |

Architect chốt AC và stack/build/preview commands trước duyệt. Builder viết regression test luồng chính và lỗi, chạy test thật. QA kiểm form/filter/reload ở browser thật; không thay bằng screenshot trang ban đầu.

## Probe độ bền workflow

Trong task thử riêng: thử triển khai trước approval (phải bị chặn); reviewer trùng Architect (bị chặn); sửa source sau snapshot rồi audit bằng manifest cũ (bị chặn); reload checkpoint vẫn có signoff/counter; hai REJECT cùng pha phải ESCALATED. Không dùng probe để thay browser acceptance của app.

Stop hooks chỉ kiểm harness/thu hoạch transcript. Quyền write/terminal trong metadata không tạo sandbox; runtime phải tạo context độc lập và branch thực tế. Bàn giao cuối nêu URL, cách khởi chạy, tests/browser đã kiểm và hạn chế còn lại; không ghi benchmark PASS khi chưa thực hiện.
