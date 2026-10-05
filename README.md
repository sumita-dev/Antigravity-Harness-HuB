# Antigravity-Harness-Hub
> **Bộ Harness Đa Nhiệm & Phản Biện Tự Hành 2.0**

`Antigravity-Harness-Hub` là khung điều phối (harness framework) tự hành chuẩn hóa quy trình phát triển đa lĩnh vực (Phần mềm & Tiếp thị/Nội dung). Hệ thống kết hợp cơ chế phân vai tác tử chuyên môn hóa, cỗ máy trạng thái (State Machine), và rào chắn kiểm định chất lượng đối nghịch (Adversarial Quality Gate) tích hợp cầu dao ngắt mạch (Circuit Breaker) chống kẹt vòng lặp sau tối đa 2 lượt phản biện.

> ### ⚠️ Ranh giới thực tế giữa 2 tầng (đọc trước khi dùng)
>
> | Tầng | Vai trò thật | Ai chạy |
> | :--- | :--- | :--- |
> | `GEMINI.md` / `AGENTS.md` + `agents/` + `rubrics/` + `plugins/*/skills/` | **Bộ luật vận hành thật** — quy định Quản đốc phân vai, gọi subagent, gọi skill theo slash command | Antigravity 2.0 (đọc trực tiếp trong IDE) |
> | `harness/*.py` + `run_harness.py` | **Mô phỏng state machine** để kiểm thử luồng/quy tắc và trích xuất nội dung skill. **Không gọi LLM API**, không tự sinh nội dung | `python run_harness.py …` (dev/CI) |
>
> Muốn agent *viết nội dung thật*, nó phải chạy trong Antigravity theo `GEMINI.md`. `harness/` không thay thế được bước đó.


---

## MCP Server cho skill `framework-marketing-da-kenh`

Skill marketing đa kênh truy vấn MCP server của Noti. Cần thêm server vào ứng dụng AI trước khi dùng:

- URL endpoint (JSON-RPC, dán vào phần "thêm MCP server" của ứng dụng): `https://go.noti.vn/cong-cu/framework-marketing-da-kenh/mcp`
- Tên server gợi ý: `noti-framework-marketing` (đã khai trong `plugins/marketing/mcp_config.json`)
- Server cung cấp 8 tool `framework_*`; schema đã kiểm chứng lưu tại `plugins/marketing/skills/framework-marketing-da-kenh/references/mcp-tools-schema.json`
- Chưa cấu hình MCP vẫn dùng được skill ở **chế độ khung tĩnh** (6 pha + nhóm kênh + 6 loại liên kết), nhưng mất phần khối việc chi tiết và link sơ đồ.

## 1. Cấu Trúc Thư Mục Dự Án

```
Antigravity-Harness-Hub/
├── agents/                                 # Đặc tả vai trò và trách nhiệm của từng tác tử
│   ├── app/                                # Tác tử khối Kỹ thuật / Lập trình (App)
│   │   ├── architect.md                    # System Architect (Thiết kế hệ thống & API contract)
│   │   ├── builder.md                      # Developer (Lập trình mã nguồn phân lập)
│   │   └── qa_auditor.md                   # QA Reviewer (Kiểm thử, bảo mật OWASP, phát hiện lỗi)
│   └── marketing/                          # Tác tử khối Tăng trưởng / Nội dung (Marketing)
│       ├── web_researcher.md               # Web & Market Intelligence Researcher
│       ├── creator.md                      # Content Creator (Soạn kịch bản & copy chuyển đổi cao)
│       └── compliance_critic.md            # Policy Reviewer (Rà soát chính sách, lọc AI slop)
├── plugins/                                # Skills đóng gói theo plugin (Antigravity đọc trực tiếp)
│   ├── code/skills/                        # 21 skill kỹ thuật (SKILL.md + references/ + scripts/)
│   └── marketing/skills/                   # 11 skill marketing / nội dung
├── .agent/ , .agents/                      # Khai báo search path cho Antigravity (skills.json, plugins.json)
├── .brain/                                 # Dữ liệu runtime (trajectories, learnings) — KHÔNG commit
├── scripts/                                # Tiện ích: session_manager.py, apify_crawler.py
├── configs/                                # Tệp cấu hình phân tầng model và giới hạn vận hành
│   └── harness_config.json                 # Model tier, roles, max_rounds, skill_routing (32 skill)
├── harness/                                # Lõi thực thi (Harness Core Engine)
│   ├── orchestrator.py                     # ChiefOrchestrator: Bộ điều phối trung tâm
│   ├── quality_gate.py                     # AdversarialQualityGate & Verdict logic
│   ├── state_machine.py                    # Cỗ máy trạng thái (HarnessState & TaskContext)
│   └── runners/                            # Các Runner thực thi theo phân nhánh
│       ├── app_runner.py                   # Luồng vận hành nhánh Build App
│       └── marketing_runner.py             # Luồng vận hành nhánh Marketing
├── rubrics/                                # Bộ tiêu chí đánh giá nghiệm thu chuẩn hóa
│   ├── code_quality_rubric.md              # Tiêu chuẩn chất lượng code, test, OWASP
│   └── content_compliance_rubric.md        # Tiêu chuẩn chính sách nền tảng, chống AI slop
├── tests/                                  # Bộ kiểm thử tự động
│   ├── test_harness_core.py                # Unit test: State machine, Quality gate, Routing
│   ├── test_harness_e2e.py                 # E2E test: Luồng phản biện 2 vòng, Escalate
│   ├── test_harness_learning.py            # Trajectory + Learning Harvester
│   ├── test_marketing_skills.py            # Frontmatter & loader của skill
│   ├── test_session_manager.py             # Portable session sync
│   ├── test_skill_router.py                # Keyword routing
│   └── test_repo_integrity.py              # Chặn lỗi: thư mục lồng, file rác, secret, path cá nhân, ref gãy
├── setup/                                  # Cài đặt cấu hình môi trường mới
│   ├── config.json                         # Cấu hình Antigravity plugins & userSettings chuẩn
│   └── setup.ps1                           # Script tự động copy đè cấu hình vào %USERPROFILE%\.gemini\config
├── run_harness.py                          # Giao diện dòng lệnh CLI chính của hệ thống
└── README.md                               # Tài liệu hướng dẫn chi tiết
```

### Mô Tả Chi Tiết Các Tệp Tin

| Tệp tin / Thư mục | Trách nhiệm chính |
| :--- | :--- |
| `harness/state_machine.py` | Định nghĩa các trạng thái (`INIT`, `INTAKE`, `DESIGN`, `IMPLEMENTATION`, `AUDIT`, `APPROVED`, `REJECTED`, `ESCALATED`) và quản lý bước chuyển trạng thái hợp lệ, ngăn chặn việc nhảy cóc quy trình. |
| `harness/quality_gate.py` | Kiểm tra định dạng phán quyết của Checker (`VERDICT: APPROVE`, `REJECT`, `ESCALATE`) và đếm số vòng lặp critique. |
| `harness/orchestrator.py` | Khởi tạo môi trường, tiếp nhận yêu cầu từ người dùng, nạp `TaskContext`, chuyển giao cho Runner thích hợp và gửi kết quả thẩm định. |
| `harness/runners/` | Đóng gói chu trình 3 bước cho từng nhánh: `app_runner.py` (Architect → Builder → QA Auditor) và `marketing_runner.py` (Researcher → Creator → Compliance Critic). Runner là nơi ghi trace từng bước. |
| `configs/harness_config.json` | Khai báo model tier (`pro`/`flash`), `roles`, `limits` và `skill_routing` (32 skill → keyword). **Lưu ý:** chưa có code nào resolve/gọi model — đây là metadata cấu hình, cần adapter LLM mới dùng được. |
| `rubrics/` | Định nghĩa các checklist khắt khe độc lập mà Checker bắt buộc phải đối chiếu khi đánh giá. |

---

## 2. Luồng Điều Phối 3 Bước Theo Phân Nhánh

Hệ thống hoạt động theo nguyên tắc tách biệt vai trò (Maker-Checker Invariant): Tác tử tạo nội dung/code không bao giờ tự duyệt sản phẩm của mình.

### 2.1. Nhánh 1: Phát Triển Phần Mềm (`app`)

```mermaid
flowchart LR
    A["INTAKE"] --> B["DESIGN<br/>(Architect)"]
    B --> C["IMPLEMENTATION<br/>(Builder)"]
    C --> D["AUDIT<br/>(QA Auditor)"]
    D -->|"VERDICT: APPROVE"| E["APPROVED"]
    D -->|"VERDICT: REJECT (vòng <= 2)"| C
    D -->|"VERDICT: REJECT (vòng > 2)"| F["ESCALATED"]
```

1. **Bước 1 - DESIGN (Architect):**
   - **Tác tử:** `agents/app/architect.md` (System Architect).
   - **Nhiệm vụ:** Tiếp nhận yêu cầu nghiệp vụ, phân tích ranh giới chức năng (blast radius), thiết kế kiến trúc phân lớp, Schema dữ liệu và hợp đồng API (API contract).
2. **Bước 2 - IMPLEMENTATION (Builder):**
   - **Tác tử:** `agents/app/builder.md` (Developer).
   - **Nhiệm vụ:** Viết mã nguồn phân lập bám sát thiết kế kiến trúc, tuân thủ các nguyên tắc thiết kế sạch (Clean Code), viết kèm kiểm thử tương ứng.
3. **Bước 3 - AUDIT (QA Auditor):**
   - **Tác tử:** `agents/app/qa_auditor.md` (QA Reviewer).
   - **Nhiệm vụ:** Khảo sát mã nguồn đối chiếu với `rubrics/code_quality_rubric.md`. Xác minh kiểm thử pass, quét lỗ hổng bảo mật OWASP, phát hiện mã thừa hoặc phụ thuộc không cần thiết.

---

### 2.2. Nhánh 2: Sáng Tạo Nội Dung & Tiếp Thị (`marketing`)

```mermaid
flowchart LR
    A["INTAKE"] --> B["DESIGN<br/>(Researcher)"]
    B --> C["IMPLEMENTATION<br/>(Creator)"]
    C --> D["AUDIT<br/>(Compliance Critic)"]
    D -->|"VERDICT: APPROVE"| E["APPROVED"]
    D -->|"VERDICT: REJECT (vòng <= 2)"| C
    D -->|"VERDICT: REJECT (vòng > 2)"| F["ESCALATED"]
```

1. **Bước 1 - DESIGN (Researcher):**
   - **Tác tử:** `agents/marketing/web_researcher.md` (Web & Market Intelligence Researcher).
   - **Nhiệm vụ:** Nghiên cứu insight khách hàng mục tiêu, tìm kiếm từ khóa ngách, nắm bắt xu hướng thị trường và giải phẫu đối thủ cạnh tranh.
2. **Bước 2 - IMPLEMENTATION (Creator):**
   - **Tác tử:** `agents/marketing/creator.md` (Content Creator).
   - **Nhiệm vụ:** Soạn thảo kịch bản video, bài viết mạng xã hội hoặc sales copy chuyển đổi cao dựa trên insight từ Researcher.
3. **Bước 3 - AUDIT (Compliance Critic):**
   - **Tác tử:** `agents/marketing/compliance_critic.md` (Policy Reviewer).
   - **Nhiệm vụ:** Thẩm định nội dung đối soát với `rubrics/content_compliance_rubric.md`. Rà soát vi phạm chính sách nền tảng (Facebook Community Standards, YouTube Trust & Safety, TikTok Policy), loại bỏ sáo rỗng AI (AI slop) và ngụy biện logic.

### 2.3. Gọi Trực Tiếp Kỹ Năng Nhánh Marketing Trong Ô Chat (Slash Commands)

Toàn bộ 11 kỹ năng của nhánh Marketing đã được tích hợp đầy đủ và có thể gọi trực tiếp trong ô chat Antigravity bằng lệnh Slash `/<tên_lệnh>`:

| Lệnh Slash trong Chat | Kỹ Năng | Trọng Tâm Xử Lý |
| :--- | :--- | :--- |
| `/boc-phot-storytelling` | Kịch bản Bóc Phốt Tài Chính | Soạn và chỉnh kịch bản theo 6 format kể chuyện đỉnh cao |
| `/check-youtube-policy` | YouTube Policy Auditor | Rà soát vi phạm 50 cụm chính sách YouTube & viết lại Safe Script |
| `/yt-competitor-analyzer` | YouTube Competitor Analyzer | Quét toàn bộ video đối thủ từ URL, xuất Dashboard HTML & CSV |
| `/alex-hormozi-offer-builder` | Grand Slam Offer Builder | Thiết kế Offer không thể chối từ theo framework $100M Offers |
| `/alex-hormozi-money-models` | $100M Money Models | Xây dựng chuỗi thang sản phẩm, upsell, downsell & mô hình dòng tiền |
| `/kahneman-creative-ads` | Kahneman Creative Strategy | Lập Canvas chiến lược sáng tạo quảng cáo dựa trên cơ chế nhận thức |
| `/traffic-secrets-playbook` | Traffic Secrets Playbook | Kế hoạch kéo và tối ưu traffic 14 bước của Russell Brunson |
| `/cong-thuc-viet-content-by-noti-v4` | 14 Công Thức Content Noti | Viết content/copy ads chuyển đổi cao theo 14 công thức tâm lý + NLP |
| `/viet-content-seo-geo-v5` | Content Chuẩn SEO + AEO + GEO | Tối ưu bài viết đạt chuẩn SEO, trích dẫn AEO/GEO cho AI Search |
| `/meta-ads-analyzer-mod-by-noti` | Meta Ads Analyzer Mod Noti | Chẩn đoán chuyên sâu hiệu suất quảng cáo Meta, CPA/ROAS/CPM |
| `/fb-admin` | Facebook Fanpage Manager | Quản lý Fanpage Doanh Nghiệp (đăng bài, đọc/trả lời comment) |

---

## 3. Cơ Chế Phản Biện Độc Lập & Cầu Dao Ngắt Mạch (Circuit Breaker)

### 3.1. Rào Chắn Kiểm Định Độc Lập (Adversarial Quality Gate)
- Checker (`qa_auditor` hoặc `compliance_critic`) hoạt động hoàn toàn khách quan theo chuẩn đóng.
- Phán quyết bắt buộc phải chứa một trong các nhãn định dạng chuẩn:
  - `VERDICT: APPROVE`: Công việc đạt chuẩn toàn bộ rubric.
  - `VERDICT: REJECT`: Công việc có lỗi, thiếu sót hoặc vi phạm chính sách.
  - `VERDICT: ESCALATE` (hoặc `ESCALATE_HUMAN`): Phát hiện lỗi hệ thống, bế tắc hoặc vi phạm nghiêm trọng cần con người can thiệp.

### 3.2. Cầu Dao Ngắt Mạch Sau 2 Vòng Phản Biện (Stagnation Breaker)
Để ngăn ngừa tình trạng tác tử sửa đổi luẩn quẩn, gây cháy token và suy thoái ngữ cảnh:
- Khi Checker đưa ra `VERDICT: REJECT`, biến đếm `critique_rounds` của task được tăng thêm 1 đơn vị.
- Nếu `critique_rounds <= 2`: Task context được chuyển ngược về trạng thái `IMPLEMENTATION` để Maker tiến hành sửa chữa theo phản hồi.
- Nếu `critique_rounds > 2`: Hệ thống tự động kích hoạt **Stagnation Circuit Breaker**, ngay lập tức chuyển trạng thái sang `HarnessState.ESCALATED` và trả về `Verdict.ESCALATE`.
- Khi đã ở trạng thái `ESCALATED`, hệ thống dừng lặp lại và bàn giao cho chuyên gia con người xử lý.

---

## 4. Hướng Dẫn Sử Dụng & Kiểm Thử

### 4.1. Cài Đặt Cấu Hình Môi Trường Khi Sang Máy Mới

Để áp dụng toàn bộ cấu hình plugin (`anti-workflows`, `chrome-devtools-plugin`, `gemini-api`, `google-antigravity-sdk`, `modern-web-guidance-plugin`) và `userSettings` chuẩn của hệ thống:

```powershell
powershell -ExecutionPolicy Bypass -File setup\setup.ps1
```
*Script sẽ tự động sao lưu cấu hình cũ (nếu có) và cài đè `config.json` vào `%USERPROFILE%\.gemini\config\config.json`.*

---

### 4.2. Chạy Kiểm Thử Tự Động (Automated Testing)

Toàn bộ logic máy trạng thái, routing và kịch bản ngắt mạch đã được bao phủ bởi pytest. Để thực thi toàn bộ test suite:

```bash
# Chạy toàn bộ unit test và e2e test
pytest -v
```

Kết quả hiện tại: toàn bộ test PASS.

Bộ test gồm 6 file:
- `test_harness_core.py` — state machine, quality gate, circuit breaker
- `test_harness_e2e.py` — luồng 2 nhánh, escalate sau 2 vòng REJECT
- `test_harness_learning.py` — trajectory store + learning harvester
- `test_skill_router.py` — keyword routing (32 skill)
- `test_marketing_skills.py` — frontmatter + loader của skill
- `test_session_manager.py` — portable session sync
- `test_repo_integrity.py` — chặn hồi quy cấu trúc/secret/path cá nhân

```text
$ pytest -q
44 passed
```
```

---

### 4.3. Hướng Dẫn Sử Dụng Lệnh CLI (`run_harness.py`)

Hệ thống cung cấp điểm vào CLI chuẩn xác qua `run_harness.py`:

```bash
python run_harness.py --task "<mô tả nhiệm vụ>" --branch {app,marketing}
```

#### Ví Dụ Thực Thi Cụ Thể

**1. Khởi chạy luồng Kỹ thuật (App):**
```bash
python run_harness.py --task "Xây dựng module xác thực phân quyền JWT" --branch app
```
*Kết quả mẫu:*
```text
Task processing finished. Status: HarnessState.APPROVED, Verdict: APPROVE
```

**2. Khởi chạy luồng Tiếp thị (Marketing):**
```bash
python run_harness.py --task "Soạn kịch bản video TikTok 60 giây phân tích tài chính" --branch marketing
```
*Kết quả mẫu:*
```text
Task processing finished. Status: HarnessState.APPROVED, Verdict: APPROVE
```

#### Tham Số Dòng Lệnh
- `--task` *(bắt buộc)*: Mô tả nhiệm vụ.
- `--branch {app,marketing,auto}`: Chọn nhánh. Mặc định `auto` = tự định tuyến theo `skill_routing`.
- `--checker-output "VERDICT: ..."`: Phán quyết Checker đưa vào (mặc định `VERDICT: APPROVE`). Dùng để kiểm thử luồng REJECT/ESCALATE.
- `--review-rounds N`: Mô phỏng N vòng review. **Đây là cách duy nhất kích hoạt circuit breaker từ CLI** (`--review-rounds 3 --checker-output "VERDICT: REJECT"` → ESCALATED).
- `--task-id`: ID tùy chọn (mặc định sinh UUID mới cho mỗi task).
- `--dump-skill`: In nội dung SKILL.md đã nạp ra stdout (để pipeline bên ngoài dùng).
- `--json`: Xuất kết quả dạng JSON (task_id, branch, state, verdict, critique_rounds, active_skill, skill_path).

**Ví dụ kiểm chứng circuit breaker:**
```bash
python run_harness.py --task "Build login" --branch app \
  --review-rounds 3 --checker-output "VERDICT: REJECT"
# -> Task processing finished. Status: HarnessState.ESCALATED, Verdict: ESCALATE
```

**Ví dụ lấy nội dung skill cho pipeline ngoài:**
```bash
python run_harness.py --task "viết content cho facebook" --dump-skill
```

---

## 5. Bảo Mật & Vận Hành An Toàn

- **Không hardcode secret.** Page token / API key chỉ đọc từ biến môi trường hoặc `.env` (đã gitignore). Mẫu: `.env.example`.
- **⚠️ Cảnh báo lịch sử:** repo từng commit **Page Access Token Facebook thật** (`fb-admin/scripts/fb_api.py`) và **YouTube API key** (`yt-competitor-analyzer/scripts/analyze.js`) ở nhiều commit trước bản vá. Nếu các token đó từng được dùng: **thu hồi và cấp lại token mới** (Meta Business Suite / Google Cloud Console). Xoá file ở HEAD **không** xoá secret khỏi lịch sử git.
- Script cần cấu hình: `fb-admin` → `FB_PAGE_ID` + `FB_PAGE_ACCESS_TOKEN`; `yt-competitor-analyzer` → `YOUTUBE_API_KEY`; `scripts/apify_crawler.py` → `APIFY_API_TOKEN`.
- Trước khi bật `setup/config.json` cho agent: rà lại `globalPermissionGrants` (bản mặc định cấp quyền rộng: `command(*)`, `write_file(*)`, `mcp(*)`, `escalate_admin(...)`) và `enableTerminalSandbox: false`. Chỉ cấp quyền tối thiểu cần dùng.
- Scrape dữ liệu mạng xã hội phải tuân thủ điều khoản nền tảng và quy định về dữ liệu cá nhân.

---

## 6. Ghi Chú Trạng Thái (đã kiểm chứng, không phải suy đoán)

- `harness/*.py` là **mô phỏng state machine**: không gọi LLM API. Circuit breaker chỉ hoạt động khi vòng lặp review được gọi qua `submit_for_review`; một lần chạy CLI đơn lẻ không lặp nên không thể escalate.
- File phụ trợ và tham chiếu cũ:
  - `plugins/code/skills/app`: Toàn bộ các tham chiếu phụ trợ cũ (`AI_CODE_WORKFLOW.md`, `references/coding-taste.md`, `references/engineering-standards.md`, `templates/app-spec.md`) đã được dọn sạch hoàn toàn, chuyển đổi 100% sang mô hình Native Multi-Agent Orchestration (Architect -> Builder -> QA Auditor).
  - `plugins/marketing/skills/viet-content-seo-geo-v5`: `scripts/score.mjs`, `scripts/score.py` — nay **đã có** trong repo, đã kiểm chứng parity (JSON trùng nhau trên nhiều bài thử).
  Mỗi SKILL.md tương ứng đã có ghi chú **TRẠNG THÁI SKILL**; `tests/test_repo_integrity.py` giữ danh sách trong `KNOWN_GAPS` để không phát sinh con trỏ gãy mới.
- `setup.ps1` dùng `Copy-Item -Recurse` — chạy lại nhiều lần lên thư mục đã tồn tại có thể tạo tầng lồng `plugins/<tên>/<tên>`. Kiểm tra sau mỗi lần chạy.
- `configs/harness_config.json` khai báo model `Gemini 3.1 Pro` / `Gemini 3.8 Flash` — **chưa xác minh** 2 ID này tồn tại, và không code nào resolve chúng. Cần Sếp xác nhận hoặc thay bằng ID thật khi viết adapter LLM.
