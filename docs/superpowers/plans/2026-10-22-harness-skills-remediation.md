# Antigravity Harness & Skills Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục các rủi ro cài đặt, nạp skill, định tuyến và kiểm thử đã phát hiện trong audit, rồi xác minh bằng chứng thật trên Antigravity 2.0.

**Architecture:** Chia việc thành các phần độc lập: bảo vệ cấu hình cài đặt trước; sửa danh mục skill và đường dẫn; hoàn thiện kiểm tra tự động; cuối cùng chạy smoke test native trên đúng surface Antigravity. Các kiểm tra cục bộ không được coi là bằng chứng thay cho native E2E.

**Tech Stack:** PowerShell, Python 3.12, pytest, JSON/YAML, Antigravity 2.0 Customizations.

**Spec:** `reports/harness-skills-audit-2026-10-22.md`; quy ước runtime tại `GEMINI.md` và `docs/native-readiness.md`.

## Global Constraints

- Giữ nguyên lựa chọn người dùng trong `~/.gemini/config/config.json` khi cài/cập nhật.
- Không xóa plugin, skill, hook hoặc agent không thuộc harness.
- Native capability chỉ được ghi `OBSERVED` khi đã kiểm tra trong Antigravity 2.0 và có bằng chứng lưu lại.
- `GEMINI.md` không vượt trần `always_on_max` 24,000 bytes.
- QA độc lập với Maker theo quy chuẩn repo; không tạo signoff hoặc bằng chứng giả.
- Không dùng approval của product workflow để chặn bảo trì harness đã được giao.

## Review Focus

1. Plugin có sẵn của người dùng không bị xóa/ghi đè trong lần cài mới hoặc nâng cấp; kiểm bằng profile giả lập có plugin ngoài harness.
2. Cài dở giữa chừng không làm mất bản đang hoạt động; kiểm bằng lỗi mô phỏng ở bước copy và xác minh rollback.
3. Hai plugin không xuất cùng tên skill; kiểm registry trên toàn bộ plugin tree và thử nạp slash command.
4. Link/reference còn dùng được sau khi plugin được copy sang thư mục profile khác; kiểm với đường dẫn cài đặt tạm.
5. Router không gán nhầm task vào app/marketing; kiểm từng câu yêu cầu thực tế cho các skill đang thiếu route và các cặp skill dễ chồng lấn.

---

## Thứ tự triển khai

**P1:** Cài đặt an toàn → khôi phục được vòng test cục bộ → smoke test plugin/skill native.  
**P2:** Tên skill và link portable → routing → lint/CI.  
**P3:** Tách các skill dài theo progressive disclosure.

### Task 1: Cài đặt/cập nhật an toàn, không thay thế profile người dùng

**Files:**
- Modify: `setup/setup.ps1`
- Test: `tests/test_setup.py`
- Review: `docs/native-readiness.md`

**Contract:** Script chỉ được cập nhật file do harness quản lý. Plugin cùng tên nhưng không có dấu sở hữu harness phải được giữ nguyên và gây conflict rõ ràng, không bị ghi đè. Thư mục `.agents` hiện có phải được merge theo file sở hữu, không bị thay toàn bộ.

- [x] **Step 1: Viết test đỏ cho profile đã có plugin ngoài harness.** Tạo target giả lập có `plugins/user-plugin/plugin.json`; chạy setup và xác nhận plugin vẫn tồn tại nguyên byte, harness plugins được cài.
- [x] **Step 2: Viết test đỏ cho xung đột tên plugin không thuộc harness.** Tạo plugin `code` không có marker ownership; setup phải dừng với mã lỗi khác 0 và không thay đổi file đích.
- [x] **Step 3: Viết test đỏ cho cập nhật plugin do harness quản lý.** Chạy setup hai lần; config tuỳ chỉnh và plugin ngoài harness giữ nguyên, file harness cập nhật, file harness cũ được gỡ chỉ khi có trong manifest sở hữu.
- [x] **Step 4: Viết test rollback cho lỗi copy.** Mô phỏng lỗi sau staging; xác nhận bản cũ vẫn hoạt động và backup/rollback có thể phục hồi.
- [x] **Step 5: Sửa `setup/setup.ps1` theo luồng preflight → stage → backup → commit → rollback.** Lưu ownership manifest của harness; không chạy `Remove-Item -Recurse` lên thư mục dùng chung.
- [x] **Step 6: Chạy `pytest tests/test_setup.py -q` trong runner có quyền ghi/xóa thư mục temp.** Kỳ vọng toàn bộ test setup pass; kiểm tra thêm target có đường dẫn Unicode và target lồng/symlink theo test hiện hành.

### Task 2: Bỏ trùng tên `karpathy-second-brain` và sửa link security-review

**Files:**
- Modify: `plugins/computer/skills/karpathy-second-brain/` hoặc registry plugin theo quyết định giữ một bản canonical tại `plugins/second-brain/skills/karpathy-second-brain/`
- Modify: `plugins/code/skills/security-review/SKILL.md`
- Test: `tests/test_repo_integrity.py` hoặc test skill-integrity mới

**Contract:** Mỗi `name` trong frontmatter chỉ xuất hiện một lần trên toàn bộ plugin bundle. Tài liệu skill chỉ dùng liên kết tương đối hoặc URL web; không giữ đường dẫn checkout máy phát triển.

- [x] **Step 1: Thêm test đỏ phát hiện duplicate frontmatter names trên toàn bộ `plugins/**/SKILL.md`.** Assertion phải báo cả hai path khi trùng.
- [x] **Step 2: Chuyển nội dung dùng chung sang skill canonical trong plugin `second-brain`; bỏ skill trùng ở plugin `computer` hoặc đổi tên nếu cần giữ hành vi độc lập.** Cập nhật mọi registry/config tham chiếu theo lựa chọn.
- [x] **Step 3: Thêm test đỏ cấm link `file:///` hoặc absolute checkout path trong `SKILL.md`.**
- [x] **Step 4: Thay các link ở `security-review` thành `references/ai-and-llm-security.md` và `references/binary-and-ipc.md`.**
- [x] **Step 5: Chạy test integrity và nạp thử skill từ plugin đã copy sang temp profile.** Kỳ vọng tên chỉ còn một và mọi reference resolve được.

### Task 3: Bổ sung route cho skill đang bị bỏ sót

**Files:**
- Modify: `configs/harness_config.json`
- Test: `tests/test_skill_router.py`
- Test: `tests/test_marketing_skills.py` nếu route thuộc marketing

**Contract:** Mỗi skill được phép tự động định tuyến phải có keyword kiểm thử; skill chỉ gọi trực tiếp phải được đánh dấu rõ trong catalog để không tạo kỳ vọng auto-route.

- [x] **Step 1: Thêm test đỏ cho các câu yêu cầu thực tế:** browser/process hygiene, chăm sóc Windows, chuyển tài liệu Markdown, tạo video Flow/Veo, audit paid media, test database bằng Testcontainers, và YouTube autocomplete.
- [x] **Step 2: Thêm route song ngữ hoặc tiếng Việt phù hợp cho `browser-hygiene`, `cham-soc-may-tinh`, `doc-to-markdown`, `flowkit`, `paid-media-auditor`, `testcontainers`, `youtube-suggest`.** Tránh keyword quá chung làm lấn skill khác.
- [x] **Step 3: Thêm test xung đột keyword và longest-match cho các nhóm gần nhau.** Ví dụ: viết bài SEO vs viết caption; kiểm tra trình duyệt mồ côi vs kiểm tra UI.
- [x] **Step 4: Chạy `pytest tests/test_skill_router.py tests/test_marketing_skills.py -q`.** Kỳ vọng mọi câu mẫu định tuyến đến đúng skill/branch.

### Task 4: Tách các skill dài theo progressive disclosure

**Files:**
- Modify: `plugins/second-brain/skills/setup-second-brain/SKILL.md`
- Create/update: `plugins/second-brain/skills/setup-second-brain/references/`
- Modify: `plugins/code/skills/gitnexus-plan/SKILL.md` và references liên quan
- Modify: `plugins/code/skills/security-review/SKILL.md` và references liên quan
- Test: skill integrity test

- [x] **Step 1: Thêm test xác nhận các tài liệu tham chiếu được liên kết từ `SKILL.md` và tồn tại vật lý.**
- [x] **Step 2: Chuyển checklist, ví dụ dài và bảng tra cứu sang `references/`; giữ quy trình chọn nhánh, điều kiện an toàn, lệnh chính và output contract trong `SKILL.md`.**
- [x] **Step 3: Rà lại mô tả frontmatter để mỗi skill nêu rõ mục đích và tình huống kích hoạt; không đổi tên skill ngoài Task 2.**
- [ ] **Step 4: Chạy test skill loader/curator và kiểm thử kích hoạt từng skill bằng slash command trong Antigravity.** Không áp một giới hạn byte cứng mới nếu chưa đo tác động context thực tế.

### Task 5: Thêm cổng CI cho tính nhất quán của harness và skill

**Files:**
- Create: `scripts/lint_harness_skills.py` (hoặc đặt vào validator hiện có sau khi kiểm tra trách nhiệm)
- Test: `tests/test_skill_integrity.py`
- Modify: `.github/workflows/` workflow kiểm tra hiện có
- Modify: `docs/native-readiness.md` khi có evidence mới

**Contract:** Linter báo lỗi duplicate names, frontmatter thiếu `name`/`description`, link nội bộ hỏng, absolute local `file:///`, route trỏ skill không tồn tại và route thiếu phân loại. Mọi cảnh báo cần ghi tên skill và path.

- [x] **Step 1: Thêm test đỏ cho từng lỗi metadata/reference/route và một fixture hợp lệ.**
- [x] **Step 2: Viết linter deterministic, không gọi mạng hoặc Antigravity.** Cho phép danh sách route-direct-only tường minh nếu cần.
- [x] **Step 3: Tích hợp linter vào CI trước pytest.** Lệnh CI trả nonzero khi gặp lỗi; thông báo có thể copy/paste để sửa.
- [x] **Step 4: Chạy linter trên toàn bộ 58 skill và pytest subset liên quan.** Kỳ vọng 0 lỗi metadata/link/duplicate; full pytest cũng đã chạy xanh.

### Task 6: Xác minh pytest suite trong môi trường Windows có temp ACL phù hợp

**Files:**
- Chỉ sửa: `pytest.ini` hoặc `tests/conftest.py` nếu nguyên nhân được tái hiện như lỗi cấu hình repo; nếu không thì không thay code.
- Evidence: `reports/` hoặc artifact CI

- [x] **Step 1: Chạy một test dùng `tmp_path` với `--basetemp` nằm trong thư mục Windows user-writable đã xác minh.** Ghi lại path, quyền tạo/xóa và exit code.
- [x] **Step 2: Chạy `pytest -q` toàn bộ suite trong cùng runner.** Lưu summary đầy đủ thay vì output bị cắt.
- [x] **Step 3: Nếu vẫn lỗi, phân loại từng failure thành lỗi assertion, lỗi filesystem ACL, dependency/env hoặc test flake; tạo regression test cho lỗi assertion sản phẩm.** Không sửa test để né failure.
- [x] **Step 4: Chỉ chốt test suite xanh khi exit code 0; cập nhật audit status cùng log thật.**

### Task 7: Smoke test native Antigravity 2.0

**Files:**
- Update: `docs/native-readiness.md`
- Create: `reports/native-smoke-2026-10-22.md` hoặc tên theo ngày chạy thực tế

**Dependencies:** Task 1–6 đã hoàn tất; profile test sạch hoặc đã backup; plugin visibility đã kiểm tra trước khi chạy.

- [ ] **Step 1: Kiểm tra Customizations trong Antigravity 2.0.** Ghi app/IDE/CLI surface, plugin names, skill names, phiên bản, global/workspace scope và plugin conflict.
- [ ] **Step 2: Gọi tường minh một skill kỹ thuật, một skill marketing và một skill second-brain.** Ghi skill thực sự được nạp, không chỉ dựa vào câu trả lời của model.
- [ ] **Step 3: Chạy app workflow smoke tối thiểu qua Architect → Reviewer → signoff → Builder → Critic → QA.** Ghi native tool schema/result thật, actor/context, current checkout, test command/exit, và UI/browser evidence nếu có UI.
- [ ] **Step 4: Chạy marketing research-only smoke qua Researcher → Critic.** Ghi source dossier, hashes và kết quả kiểm định; không publish hoặc gọi paid API.
- [ ] **Step 5: Cập nhật từng capability thành `OBSERVED`, `UNAVAILABLE` hoặc `NOT_VERIFIED` theo bằng chứng.** Không suy trạng thái của capability khác từ một smoke pass.

## Cổng nghiệm thu tổng

- Cài đặt chạy hai lần không mất plugin/user setting ngoài harness.
- Test setup, skill integrity, routing và toàn bộ pytest đều exit code 0 trong runner hợp lệ.
- Tên skill duy nhất; link tham chiếu resolve được sau khi copy plugin.
- Antigravity 2.0 Customizations hiển thị đúng plugin/skill; ít nhất hai đường workflow native có evidence thật.
- `docs/native-readiness.md` chỉ ghi `OBSERVED` cho capability đã được quan sát; phần còn lại tiếp tục `NOT_VERIFIED`.
