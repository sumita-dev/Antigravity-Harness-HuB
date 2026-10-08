# Native Readiness

Antigravity E2E: NOT_VERIFIED. Repo tests và Codex execution chỉ chứng minh checkpoint/CLI/tool behavior được kiểm; chưa chứng minh Antigravity dispatch, context isolation, browser hay model availability.

| State | Nghĩa |
| --- | --- |
| OBSERVED | Đã gọi thành công capability thật trong runtime đích; có timestamp/input/result/evidence |
| DECLARED | Metadata/config/prompt nêu capability, chưa quan sát hoạt động |
| UNAVAILABLE | Inventory/runtime báo không có capability cần dùng |
| NOT_VERIFIED | Chưa kiểm hoặc chưa đủ bằng chứng, không tự suy thành PASS |

## Capability inventory cần điền lúc native smoke

| Capability | Baseline trong repo | Evidence cần quan sát |
| --- | --- | --- |
| Native subagent dispatch | DECLARED | Tool name/schema thật từ runtime, invocation và result; không invent define_subagent/invoke_subagent schema |
| Independent context/actor | NOT_VERIFIED | Runtime session/context separation giữa Architect/Reviewer và Builder/QA, Researcher/Creator/Critic |
| File read/artifact write/source write | DECLARED | Thử quyền riêng theo role và đúng paths; write metadata không chứng minh enforcement |
| Terminal/process | DECLARED | Command/cwd/exit/log thật, capability riêng file-write |
| Browser local preview | NOT_VERIFIED | URL, viewport/interactions/console/screenshots từng UI AC |
| Branch/worktree checkout | NOT_VERIFIED | Actual checkout/path, staged/unstaged/untracked manifest QA nhận |
| MCP/search/platform access | DECLARED | Inventory/connectivity/source evidence, ghi missing quota/token/coverage |
| Config model tiers | DECLARED | Lựa chọn hiện hữu pro/flash metadata, chưa có model-call adapter hay availability proof |
| Sandbox enforcement | NOT_VERIFIED | Kiểm runtime restrictions thực tế; prompt whitelist không cưỡng chế sandbox |
| Native app/marketing E2E | NOT_VERIFIED | Hai smoke recipes dưới chạy trọn gate với artifacts hiện tại |

Không gộp tool access và write_tools: terminal/MCP/browser có schema/quyền riêng. OBSERVED ở Codex không tự chuyển capability Antigravity thành OBSERVED.

## Recipes thực dụng

Portable package (fresh target, không sửa global profile/session):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File setup/setup.ps1 -TargetDirectory .brain/portable-smoke -SkipSessionRestore
py -3.12 .brain/portable-smoke/run_harness.py --help
py -3.12 -m pytest tests/test_setup.py tests/test_native_contracts.py -q --basetemp .brain/native-contract-smoke -p no:cacheprovider
```

Setup merges defaults vào config hiện có, giữ user choices; target không là repo/ancestor và không có symlink/junction ancestors/cleanup children. Không dùng default global install để test. Global khi chủ động chọn: `powershell -NoProfile -ExecutionPolicy Bypass -File setup/setup.ps1 -SkipSessionRestore`, default user profile .gemini/config; dependencies cần interpreter phù hợp. Copy run_harness.py/docs/runtime/tests hỗ trợ Stop hook smoke. Packaged Git-tracking test vẫn cần Git checkout, không tạo .git giả trong portable archive.

App: dùng prompt/CLI/payload trong `docs/app-workflow-guide.md`, Reviewer độc lập và Sếp duyệt đúng Spec, Builder/QA cùng current checkout, test/build/browser evidence mỗi applicable AC. CLI/backend không cần browser AC, vẫn cần PASS evidence. Optional Task Board profile chỉ với brief đó.

Marketing: dùng `docs/marketing-workflow-guide.md` content và research-only; Critic kiểm sources/claim coverage/hashes/required checks. Publishing preparation local không gửi; smoke không real publish/paid API/deploy. Mocked Facebook failures và malicious dashboard browser fixtures không thay native research E2E.

Ghi actual invocation/schema/actor/context/checkout/tool status/commands/exit/evidence/AC result/reject counters. Không ghi native-complete khi capability thiếu; không sử dụng URL, log template hoặc actor ID tự khai báo làm authenticated evidence.

## Maintenance scope

Cổng human Spec là behavior sản phẩm native Antigravity khi tạo app; không tự áp vào việc Codex sửa/audit harness đã được Sếp giao. Planning checkpoint harness-completion cũ được giữ nguyên trong `.brain/artifacts/harness-completion/maintenance-checkpoint-archive.json`, không còn product job active, không ghi signoff/APPROVED giả. Canonical design/spec/review artifacts vẫn giữ để đối chiếu, không sửa approval hashes hồi tố.

Runtime .brain/ hoàn toàn gitignored; integrity scanning source bỏ generated .brain fixtures, trong khi Git-tracking integrity tests vẫn kiểm runtime tracking và .env.example. Archive không có .git phải báo test_env_example_duoc_commit không chứng minh tracked state; không bỏ/skip test hay claim Git verification pass.
