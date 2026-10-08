# Gemini native marketing workflow

CLI checkpoint không chạy LLM/research/browser/publish. Content: RESEARCH → CREATION → AUDIT → APPROVED; research-only: RESEARCH → AUDIT → APPROVED. Researcher/Creator khác Critic; actor IDs là khai báo, không chứng thực identity.

## Smoke local trong Antigravity

Cài dependencies, kiểm inventory theo docs/native-readiness.md. Gửi brief rõ persona/task/skill/data range: “Nghiên cứu chủ đề anh chỉ định, xuất dossier có nguồn và limitations, mode research-only, Critic độc lập kiểm; không đăng bài.” Với content, thêm yêu cầu Creator dùng dossier và chuyển Critic trước bàn giao. Dữ liệu thật do Researcher thu; fixtures kiểm thử không được đưa thành claim thật.

```powershell
py -3.12 run_harness.py --marketing-workflow init --task-id marketing-smoke --marketing-mode content --task "Marketing brief" --json
py -3.12 run_harness.py --marketing-workflow status --task-id marketing-smoke --json
py -3.12 run_harness.py --marketing-workflow research --task-id marketing-smoke --actor researcher-1 --payload .brain/artifacts/marketing-smoke/dossier.json --json
py -3.12 run_harness.py --marketing-workflow content --task-id marketing-smoke --actor creator-1 --payload .brain/artifacts/marketing-smoke/content.json --json
py -3.12 run_harness.py --marketing-workflow audit --task-id marketing-smoke --actor critic-1 --payload .brain/artifacts/marketing-smoke/audit.json --json
```

Research-only dùng `--marketing-mode research-only`, bỏ bước content nhưng vẫn independent audit. Mỗi stage status/next_agent ưu tiên trước keyword; không ghép `--workflow` và `--marketing-workflow`. Resume task ID cũ, không tạo mới để reset counter. REJECT thứ hai audit ESCALATED; revise {reason} xóa downstream nhưng giữ counter, không reopen escalated.

## Brain root và bindings

MarketingWorkflowStore(root=None): root là brain directory, default HARNESS_BRAIN_DIR hoặc repo .brain; checkpoint root/marketing_workflows. Mọi source evidence/draft/report/check evidence/media phải nằm trong configured brain root, path ABSOLUTE, không traversal/symlink/junction kể cả ancestors. Đặt artifacts dưới root/artifacts/<task-id>. CLI payload file có thể resolve từ cwd; fields evidence/artifact không được relative. Các thao tác store không gọi mạng.

Init khóa task brief/mode, selected skill name/bytes hash, config bytes hash và bốn required IDs `source_accuracy/policy/integrity/task_quality`; baseline_sha256 bind chúng. Creator không chọn hoặc bỏ required checks.

Dossier schema:

```json
{"schema_version":1,"brief":"Marketing brief","sources":[{"id":"s1","reference":"SOURCE_REFERENCE","retrieved_at":"2026-10-08","evidence":"ABSOLUTE_SOURCE_EVIDENCE_FILE"}],"claims":[{"id":"c1","statement":"CLAIM_CHECKED_AGAINST_SOURCE","source_ids":["s1"],"status":"verified","units":"UNIT","timeframe":"PERIOD"}],"limitations":["KNOWN_LIMITATION"]}
```

Claim status verified|assumption|unverified, source_ids trỏ source IDs thật. Thay placeholder bằng source/evidence quan sát được; không nộp mock source như nghiên cứu thật. Dossier replacement vô hiệu draft/audit/publishing downstream, giữ history/counters.

Content schema:

```json
{"dossier_sha256":"FROM_CURRENT_CHECKPOINT","artifacts":[{"path":"ABSOLUTE_DRAFT_FILE"}],"claim_checks":[{"claim_id":"c1","artifact":"ABSOLUTE_DRAFT_FILE","location":"LITERAL_EXCERPT_IN_DRAFT","label":"factual"}]}
```

Mỗi claim ID đúng một lần, label factual|assumption|excluded. Location là literal excerpt hiện trong file. Factual phải verified; assumption visibly `Giả định:` hoặc `Assumption:` ngay excerpt. Excluded literal claim statement không được còn trong bất kỳ draft. Critic chịu trách nhiệm kiểm semantic/paraphrases; automated string/hash checks không tự biết nguồn đúng.

Audit schema:

```json
{"verdict":"APPROVE","report":"ABSOLUTE_AUDIT_REPORT_FILE","dossier_sha256":"FROM_CURRENT_CHECKPOINT","artifacts_sha256":"FROM_CURRENT_CHECKPOINT","baseline_sha256":"FROM_CURRENT_CHECKPOINT","claim_checks":[{"claim_id":"c1","status":"PASS","evidence":"ABSOLUTE_CHECK_EVIDENCE_FILE"}],"checklist":[{"id":"source_accuracy","status":"PASS","evidence":"ABSOLUTE_CHECK_EVIDENCE_FILE"},{"id":"policy","status":"PASS","evidence":"ABSOLUTE_CHECK_EVIDENCE_FILE"},{"id":"integrity","status":"PASS","evidence":"ABSOLUTE_CHECK_EVIDENCE_FILE"},{"id":"task_quality","status":"PASS","evidence":"ABSOLUTE_CHECK_EVIDENCE_FILE"}]}
```

Marketing `report` là PATH tới file thật, hash-bound (khác app report TEXT). Research-only artifacts_sha256 null. APPROVE yêu cầu đúng current dossier/artifact/baseline hashes, mỗi required ID và claim ID đúng một lần PASS/evidence. REJECT/ESCALATE vẫn có bindings/report nhưng không cần PASS checklist. Status APPROVED kiểm lại source/draft/report/evidence bytes; changed file fail closed. Hash attests unchanged bytes, không chứng thực fact truth.

Rubric `rubrics/content_compliance_rubric.md`: analytical task kiểm CPA/ROAS/CPM, units/currency/dates/coverage và source quality; Hook/CTA chỉ khi brief yêu cầu chuyển đổi. Policy scan heuristic không bảo đảm YPP/copyright/platform approval.

## Publishing local preparation

Publish chỉ khi Sếp đã yêu cầu rõ action/destination/content/media/schedule. Approval content không tự là authorization gửi. Trong maintenance/smoke này không real publish, paid API hoặc deploy.

```powershell
py -3.12 run_harness.py --marketing-workflow publish-prepare --task-id marketing-smoke --actor publisher-1 --payload .brain/artifacts/marketing-smoke/publish-request.json --json
py -3.12 run_harness.py --marketing-workflow publish-authorize --task-id marketing-smoke --payload .brain/artifacts/marketing-smoke/publish-authorization.json --json
py -3.12 run_harness.py --marketing-workflow publish-reconcile --task-id marketing-smoke --actor reconciler-1 --payload .brain/artifacts/marketing-smoke/publish-reconciliation.json --json
```

Prepare payload {action,destination,content,media:[absolute files],schedule:null|string}; content phải bằng toàn bộ UTF-8 text của một approved artifact, kể cả newline, media bytes hiện tại. Store trả local `publish_id` (khác external Facebook post ID), PREPARED/request_sha256/binding_sha256 gắn approved audit/dossier/artifacts/baseline/exact request/media/schedule.

Authorize payload {publish_id,raw_authorization}; chỉ nhận nguyên câu `Duyệt đăng bài này` hoặc `PUBLISH: approved`, case-insensitive, trim ngoài và optional prefix `Sếp:`. Không nhận generic yes/APPROVE, câu điều kiện/từ chối, embedded phrase hoặc text thêm. Ghi đúng raw xác nhận thật của Sếp, không bịa duyệt hay claim authenticated human. Chỉ PREPARED được authorize; validate_publish kiểm lại grammar của stored raw để chặn checkpoint cũ không affirmative. CLI ba action trên chỉ record local, không gửi.

Facebook script `plugins/marketing/skills/fb-admin/scripts/fb_api.py` write commands nhận `--task-id TASK --publish-id LOCAL_ID --brain ABSOLUTE_BRAIN_ROOT`; dùng cùng root với CLI/HARNESS_BRAIN_DIR. Request phải khớp action: post destination FB_PAGE_ID/media []/schedule null; reply_comment destination COMMENT_ID; schedule destination FB_PAGE_ID/media [absolute image]/schedule unix timestamp STRING. Content chính xác approved artifact. Credentials từ env/.env, không log token.

Sau real user authorization (ngoài smoke), command dạng:

```powershell
py -3.12 plugins/marketing/skills/fb-admin/scripts/fb_api.py post "EXACT_APPROVED_CONTENT" --task-id TASK --publish-id LOCAL_ID --brain ABSOLUTE_BRAIN_ROOT
```

Trước network, validate_publish kiểm current approved hashes/request/media/auth và ghi UNKNOWN atomically; mọi UNKNOWN task-wide chặn prepare/send mới. SUCCEEDED chỉ sau API response có external ID; FAILED có evidence lỗi chắc chắn; timeout/network/JSON uncertainty để UNKNOWN, không auto retry. Reconcile {publish_id,status:"SUCCEEDED"|"FAILED",evidence:absolute file,external_id?}; chỉ confirmed success có external_id. Reconciliation không tự gọi API, người kiểm phải có evidence thật.

Dossier/content revision archive publishing ở publish_history, unresolved UNKNOWN vẫn chặn và reconcile qua old ID được. Reconciled FAILED cho phép preparation/authorization mới; PREPARED invalidated chưa gửi có thể thay. Không đảm bảo exactly-once external side effects.

Facebook exit 0 API success (hoặc help), 1 runtime/API/network/JSON/upload/gate failure, 2 invalid usage. Redaction recursive không thay việc giữ secrets trong env. Read-only list_posts/list_comments không cần publishing gate.

## Verification và handoff

Critic kiểm current evidence và đủ claims/required IDs; probe task riêng: same Maker/Checker, stale dossier/draft/report, factual unverified, hidden assumption, missing/duplicate claim IDs, second REJECT và stale publish authorization phải bị chặn. Các probe dùng local fixtures/mocked HTTP, không cần token hoặc paid API.

Bàn giao dossier/draft/report/evidence paths, hashes, date/units/limitations và verdict. Native smoke chưa quan sát phải NOT_VERIFIED, không lấy simulator APPROVE hoặc unit tests làm Antigravity E2E.
