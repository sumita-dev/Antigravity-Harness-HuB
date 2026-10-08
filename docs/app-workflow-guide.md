# Gemini native app workflow

Antigravity gọi tác tử thật; CLI chỉ lưu/kiểm checkpoint/hash, không gọi LLM, chạy test hay browser. Simulation không có `--workflow` không chứng minh app đạt. Các gate này áp dụng app native; bảo trì harness đã được Sếp giao không tạo thêm product task hoặc human signoff giả.

## Smoke local trong Antigravity

1. Cài Python dependencies bằng `py -3.12 -m pip install -r requirements.txt`. Mở workspace harness trong Antigravity, kiểm tool inventory và ghi OBSERVED/DECLARED/UNAVAILABLE/NOT_VERIFIED theo `docs/native-readiness.md`.
2. Gửi brief có project directory riêng: “/app Xây Task Board local, thêm/sửa/xóa, title bắt buộc, todo/doing/done, filter, lưu localStorage, desktop/mobile. Dùng Architect → Design Reviewer → trình anh duyệt đúng Spec → Builder → QA test và browser thật. Không deploy.” Đây là benchmark tùy chọn, chưa phải app được triển khai.
3. Gemini quản lý checkpoint/artifacts, gọi Architect và Reviewer độc lập. Sếp đọc Spec và chỉ duyệt đúng bản đã review; Gemini giữ nguyên raw human_message/spec_sha256, không giả approval.
4. Builder sửa đúng Spec trong checkout thật, chạy test/build và preview. QA nhận cùng checkout, tự rerun commands và kiểm từng AC qua browser. Bàn giao URL còn chạy, evidence, defects/limitations. Thiếu browser giữ NOT_VERIFIED; không suy từ trang đầu rằng luồng chính đã đúng.
5. Resume cùng task ID bằng status; route stage/next_agent trước keyword. REJECT đầu trả Maker, REJECT thứ hai cùng pha design/code ESCALATED ngay. Counters tồn tại qua replacement/restart/revise.

## CLI

Chạy từ harness checkout. `--project-root` phải là app directory thật; payload là JSON file do agent tạo. Các lệnh dưới là recipes cho runtime, không tự chứng minh có subagent hoặc UI execution.

```powershell
py -3.12 run_harness.py --workflow init --task-id app-smoke --project-root ./app-smoke --task "Local app smoke" --json
py -3.12 run_harness.py --workflow status --task-id app-smoke --json
py -3.12 run_harness.py --workflow spec --task-id app-smoke --actor architect-1 --payload .brain/artifacts/app-smoke/spec.json --json
py -3.12 run_harness.py --workflow design-review --task-id app-smoke --actor reviewer-1 --payload .brain/artifacts/app-smoke/design-review.json --json
py -3.12 run_harness.py --workflow sign-off --task-id app-smoke --payload .brain/artifacts/app-smoke/sign-off.json --json
py -3.12 run_harness.py --workflow implementation --task-id app-smoke --actor builder-1 --payload .brain/artifacts/app-smoke/implementation.json --json
py -3.12 run_harness.py --workflow audit --task-id app-smoke --actor qa-1 --payload .brain/artifacts/app-smoke/audit.json --json
```

Architect/Reviewer/QA không sửa source. Frontmatter tool permissions chỉ DECLARED; file-write không tự cấp terminal/browser hoặc enforced sandbox. Runtime phải tạo context độc lập; actor IDs là provenance tự khai báo.

## Spec và payload

Spec năm mục `scope/design/contracts/acceptance_criteria/risks`; scope/design/contracts/risks là nonempty strings. AC có id/description/ui, `applicable` default true; false cần `na_reason`. Mọi applicable AC kể cả non-UI phải PASS có evidence. N/A chỉ khi Spec đánh dấu false, reason khớp signed na_reason.

Spec mới có yêu cầu test/build phải kê khai `verification_commands`: nonempty list {id,command,cwd,ac_ids}, cwd exact root-relative (bao gồm ".") resolve theo project_root. QA commands là {id,command,cwd,ac_ids,exit_code,log}; cwd ABSOLUTE nằm trong project, exit_code integer 0, command và AC IDs khớp Spec. Legacy Spec chưa có command list vẫn phải có command/log hợp lệ và evidence mỗi applicable AC.

Ví dụ schema dưới chỉ minh họa; thay command/AC theo stack thật và paths bằng file evidence đã quan sát, không nộp placeholder:

```json
{"scope":"Python CLI source/tests","design":"Existing parser and pure command handler","contracts":"Invalid input exits nonzero","acceptance_criteria":[{"id":"AC1","description":"Valid and invalid input regression tests pass","ui":false}],"risks":"No external writes","verification_commands":[{"id":"tests","command":"python -m pytest -q","cwd":".","ac_ids":["AC1"]}],"snapshot_exclusions":["coverage"]}
```

Review {verdict APPROVE|REJECT|ESCALATE,spec_sha256,report TEXT}; design PARTIAL_APPROVE forbidden. Signoff {spec_sha256,human_message raw}. CLI accepts whole phrase Duyệt / Duyệt Spec này / Duyệt bản đặc tả này / SIGN_OFF: approved / Bắt đầu code đi, case-insensitive, trim ngoài, optional prefix Sếp:. Không dấu câu cuối hoặc câu điều kiện; không sửa raw message để hợp grammar.

Implementation {report TEXT}; ghi checkout, diff và test/build/preview evidence. Audit {verdict,spec_sha256,manifest_sha256,report TEXT,commands,preview:{url,checks}}. `report` app là TEXT, không tự đọc path. Hash lấy từ checkpoint hiện tại.

```json
{"verdict":"APPROVE","spec_sha256":"FROM_CURRENT_CHECKPOINT","manifest_sha256":"FROM_CURRENT_CHECKPOINT","report":"QA independently reran commands and checked AC1","commands":[{"id":"tests","command":"python -m pytest -q","cwd":"ABSOLUTE_APP_DIRECTORY","ac_ids":["AC1"],"exit_code":0,"log":"ABSOLUTE_EVIDENCE_FILE"}],"preview":{"checks":[{"id":"AC1","status":"PASS","evidence":"ABSOLUTE_EVIDENCE_FILE"}]}}
```

`preview.checks` bao gồm mỗi AC đúng một lần cả UI/non-UI. UI applicable cần local URL hợp lệ (localhost/127.0.0.1/::1), PASS evidence. Non-UI không cần URL nhưng vẫn PASS có evidence. Optional `functional/http_smoke/browser` records có status và evidence/log khi PASS, reason khi NOT_VERIFIED. functional_status dựa commands và non-UI checks hợp lệ; explicit functional NOT_VERIFIED không bị tự nâng. HTTP thiếu evidence vẫn NOT_VERIFIED; browser_status theo applicable UI AC, không biến thiếu kiểm thành PASS.

## Partial audit và browser promotion

PARTIAL_APPROVE chỉ hợp lệ khi ít nhất một applicable UI AC NOT_VERIFIED có reason, mọi applicable non-UI PASS và command/log hợp lệ. Store chuyển AUDIT_PENDING_BROWSER, next_agent human_browser_verification. Không dùng audit-pending-browser hoặc verify-browser trực tiếp từ AUDIT để bỏ QA.

```powershell
py -3.12 run_harness.py --workflow audit-pending-browser --task-id app-smoke --actor qa-1 --payload .brain/artifacts/app-smoke/browser-request.json --json
py -3.12 run_harness.py --workflow verify-browser --task-id app-smoke --actor browser-checker-1 --payload .brain/artifacts/app-smoke/browser-result.json --json
```

Browser request {report TEXT}; chỉ sau valid partial audit. Browser result {spec_sha256,manifest_sha256,url,checks:[{id,status:"PASS",evidence:absolute file}]} chỉ có đúng pending UI IDs, không duplicate/extra, URL chính xác như audit. Có thể dùng preview:{url,checks}; screenshots/logs optional lists paths. Promotion kiểm lại cả source, signed review/signoff, old logs/evidence và giữ QA actor hiện hữu; source hoặc old logs đổi phải bị chặn.

## Snapshot, evidence và revision

Manifest bytes gồm mọi source/test/config trong project, staged/unstaged/untracked, .htm, *_files, .log, ORCHESTRATION_/ANTIGRAVITY_ prefixes và nested build/dist. Mặc định chỉ loại exact root .git/.gitnexus/.brain/node_modules/.venv/venv/.pytest_cache/.cache; __pycache__ và .pyc compiled caches loại ở mọi cấp. Generated .next/dist/build/coverage/test-results/playwright-report chỉ loại khi Spec top-level `snapshot_exclusions` kê khai exact root-relative paths, không glob/traversal.

Evidence/log paths ABSOLUTE, không traversal/symlink/junction; nằm trong project, configured brain artifacts hoặc signed top-level `evidence_root` ABSOLUTE directory. Payload JSON path resolve từ cwd CLI; evidence/QA cwd không nhận relative. Lưu logs/evidence ở brain artifacts nằm ngoài manifest để không tự đổi snapshot. Hash attest unchanged bytes, không chứng thực ai chạy test/browser.

QA kiểm cùng checkout thật; git diff main...HEAD bỏ sót staged/unstaged/untracked nên chỉ phụ trợ. status ở AUDIT_PENDING_BROWSER/APPROVED kiểm lại current bindings. Source/evidence đổi làm authority stale. Trong AUDIT, QA có thể REJECT với checkpoint hashes và report, trả Builder nộp implementation mới. Thiết kế đổi dùng revise {reason}; về DESIGN và phải review/signoff lại. Revise/resubmit xóa aggregate/browser requests/verification/approval nhưng giữ counters; ESCALATED không tự reopen.

```powershell
py -3.12 run_harness.py --workflow revise --task-id app-smoke --payload .brain/artifacts/app-smoke/revise.json --json
py -3.12 run_harness.py --workflow migrate-legacy --task-id legacy-app --payload .brain/artifacts/legacy-app/revalidation.json --json
```

Schema 2 hardened. Pristine v1 DESIGN/DESIGN_REVIEW/SIGN_OFF/IMPLEMENTATION tự migration khi không có prior implementation/audit/manifest/browser history, giữ task ID/counters/events/raw signoff và kiểm hash/actors. v1 AUDIT/AUDIT_PENDING_BROWSER/APPROVED fail closed; migrate-legacy {reason} archive old authority trong legacy_revalidation, giữ identity/history/counters/actors, về DESIGN cần review/human signoff/implementation/QA mới. Corrupt state không được đoán sửa; không grandfather approval hoặc tạo task mới để xóa counter.

## Benchmark và handoff

Task Board tùy chọn dùng `rubrics/task-board-design-profile.md`: CRUD/filter/error/storage/responsive, desktop 1280 và mobile 390, browser tương tác và console evidence từng AC. Architect chốt stack/AC/commands trước review; không áp profile này lên backend/CLI.

Probe local task riêng: Builder trước signoff, cùng actor Maker/Checker, source/untracked/log đổi, duplicate/unknown AC và hai REJECT đều phải bị chặn theo hợp đồng. Probe không thay browser acceptance.

Stop hook pytest chỉ kiểm harness, không thay app test/build/browser. Bàn giao nêu URL/cách chạy, hashes, command logs, AC results và giới hạn. Antigravity E2E chưa được quan sát phải ghi NOT_VERIFIED. Xem smoke marketing tại `docs/marketing-workflow-guide.md`.
