# Antigravity-Harness-Hub
> **Bộ Harness Đa Nhiệm & Phản Biện Tự Động 2.0**

`Antigravity-Harness-Hub` là khung điều phối (harness framework) tự hành chuẩn hóa quy trình phát triển đa lĩnh vực (Phần mềm & Tiếp thị/Nội dung). Hệ thống kết hợp cơ chế phân vai tác tử chuyên môn hóa, cỗ máy trạng thái (State Machine), và rào chắn kiểm định chất lượng đối nghịch (Adversarial Quality Gate) tích hợp cầu dao ngắt mạch (Circuit Breaker) chống kẹt vòng lặp sau tối đa 2 lượt phản biện.

> ### ⚠️ Ranh giới thực tế giữa 2 tầng (đọc trước khi dùng)
>
> | Tầng | Vai trò thật | Ai chạy |
> | :--- | :--- | :--- |
> | `GEMINI.md` / `AGENTS.md` + `agents/` + `rubrics/` + `plugins/*/skills/` | **Bộ luật vận hành thật** — quy định Quản đốc phân vai, gọi subagent, gọi skill theo slash command | Antigravity 2.0 (đọc trực tiếp trong IDE) |
> | `harness/orchestrator.py` + `harness/runners/` | **Mô phỏng state machine**, không gọi LLM hoặc tự sinh nội dung | CLI không có checkpoint flag (dev/CI) |
> | `harness/app_workflow.py` + `harness/marketing_workflow.py` | **Checkpoint stores thật**: khóa hash/evidence/gates, không chạy agents/browser hoặc publish | CLI `--workflow` / `--marketing-workflow` do native orchestrator gọi |
>
> Muốn agent *viết nội dung thật*, nó phải chạy trong Antigravity theo `GEMINI.md`. Checkpoint không thay thế dispatch native. Human Spec gate là behavior app sản phẩm; không tạo signoff giả hoặc gate mới cho bảo trì harness đã được Sếp giao.

Hướng dẫn: [App local và schema 2](docs/app-workflow-guide.md), [Marketing content/research-only và publishing local](docs/marketing-workflow-guide.md), [Native readiness và portable smoke](docs/native-readiness.md). Antigravity E2E: NOT_VERIFIED cho đến khi có native evidence thật; model/tool metadata không chứng minh availability/sandbox/isolation.


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
│   │   ├── architect.md                    # System Architect (Thiết kế hệ thống & Spec 5 mục)
│   │   ├── design_reviewer.md              # Design Reviewer (Thẩm định độc lập Spec kiến trúc)
│   │   ├── builder.md                      # Developer (Lập trình mã nguồn & unit test)
│   │   ├── qa_auditor.md                   # QA Reviewer (Kiểm thử độc lập, bảo mật & browser evidence)
│   │   ├── e2e_engineer.md                 # E2E Automation Engineer (Kịch bản Playwright E2E)
│   │   └── e2e_critic.md                   # E2E Test Critic (Thẩm định kịch bản E2E độc lập)
│   ├── marketing/                          # Tác tử khối Tăng trưởng / Nội dung (Marketing)
│   │   ├── web_researcher.md               # Web & Market Intelligence Researcher
│   │   ├── creator.md                      # Content Creator (Soạn kịch bản & copy chuyển đổi cao)
│   │   └── compliance_critic.md            # Policy Reviewer (Rà soát chính sách, lọc AI slop)
│   ├── registry.md                         # Bảng đăng ký định danh & quyền hạn tác tử
│   └── synthesizer.md                      # Tác tử tổng hợp tri thức & giải pháp
├── docs/                                   # Tài liệu hướng dẫn & quy chuẩn vận hành
│   ├── app-workflow-guide.md               # Cẩm nang Gemini Native App Workflow & Checkpoint Guide
│   ├── intake-protocol.md                  # Giao thức phỏng vấn Intake 3 câu hỏi trước khi lập Spec
│   └── human-test-sheet-template.md        # Mẫu biểu kiểm thử UAT dành cho người dùng cuối
├── plugins/                                # Skills đóng gói theo plugin (Antigravity đọc trực tiếp)
│   ├── code/skills/                        # 22 skill kỹ thuật (SKILL.md + references/ + scripts/)
│   └── marketing/skills/                   # 12 skill marketing / nội dung
├── .agent/ , .agents/                      # Khai báo search path cho Antigravity (skills.json, plugins.json)
├── .brain/                                 # Dữ liệu runtime (trajectories, learnings) — KHÔNG commit
├── scripts/                                # Tiện ích tự động hóa & vận hành Production
│   ├── run_security_audit.py               # Quét bảo mật dependency vulnerabilities & secret leak
│   ├── generate_launcher.py                # 1-click launcher (start-app.bat) + cờ --docker (Dockerfile, docker-compose.yml, .github/workflows/ci.yml, ARCHITECTURE.md)
│   ├── run_dev_logger.py                   # Quản lý tiến trình nền dev server & Pre-flight check (port, health)
│   ├── session_manager.py                  # Đồng bộ session di động giữa các máy
│   └── apify_crawler.py                    # Thu thập dữ liệu mạng xã hội qua Apify
├── configs/                                # Tệp cấu hình phân tầng model và giới hạn vận hành
│   └── harness_config.json                 # Model tier, roles, max_rounds, skill_routing (34 skill)
├── harness/                                # Lõi thực thi (Harness Core Engine)
│   ├── app_workflow.py                     # Quản lý vòng đời checkpoint, evidence deduplication & consistency sweep
│   ├── orchestrator.py                     # ChiefOrchestrator: Bộ điều phối trung tâm
│   ├── quality_gate.py                     # AdversarialQualityGate & Verdict logic
│   ├── state_machine.py                    # Cỗ máy trạng thái (HarnessState & TaskContext)
│   ├── memory/                             # Vòng lặp tự học & bộ nhớ trajectory (harvester.py, distiller.py, trajectory.py)
│   ├── skills/                             # Quản lý vòng đời skill, staging, routing (curator.py, manager.py, router.py)
│   └── runners/                            # Các Runner thực thi theo phân nhánh
│       ├── app_runner.py                   # Luồng vận hành nhánh Build App
│       └── marketing_runner.py             # Luồng vận hành nhánh Marketing
├── rubrics/                                # Bộ tiêu chí đánh giá nghiệm thu chuẩn hóa
│   ├── design_review_rubric.md             # Tiêu chuẩn thẩm định thiết kế kiến trúc & Spec 5 mục
│   ├── code_quality_rubric.md              # Tiêu chuẩn chất lượng code, test, OWASP, UI verification
│   └── content_compliance_rubric.md        # Tiêu chuẩn chính sách nền tảng, chống AI slop
├── tests/                                  # Bộ kiểm thử tự động (24 files, 393 tests)
│   ├── test_app_workflow.py                # Checkpoint store, review gate, verify-browser & evidence deduplication
│   ├── test_generate_launcher_production.py # Kiểm thử sinh launcher mở rộng Docker, CI/CD, ARCHITECTURE.md
│   ├── test_harness_core.py                # Unit test: State machine, Quality gate, Routing
│   ├── test_harness_e2e.py                 # E2E test: Luồng phản biện 2 vòng, Escalate
│   ├── test_launcher_and_dev_logger.py     # Kiểm thử tiện ích dev logger & 1-click launcher generator
│   ├── test_marketing_skills.py            # Frontmatter & loader của skill
│   ├── test_run_security_audit.py          # Kiểm thử quét bảo mật dependencies & secret leak
│   ├── test_session_manager.py             # Portable session sync
│   ├── test_skill_router.py                # Keyword routing
│   └── test_repo_integrity.py              # Chặn lỗi: thư mục lồng, file rác, secret, path cá nhân, ref gãy
├── setup/                                  # Cài đặt cấu hình môi trường mới
│   ├── config.json                         # Cấu hình Antigravity plugins & userSettings chuẩn
│   └── setup.ps1                           # Merge defaults, hỗ trợ -TargetDirectory/-SkipSessionRestore
├── run_harness.py                          # Giao diện dòng lệnh CLI chính của hệ thống (Task & Workflow checkpoint)
└── README.md                               # Tài liệu hướng dẫn chi tiết
```

### Mô Tả Chi Tiết Các Tệp Tin

| Tệp tin / Thư mục | Trách nhiệm chính |
| :--- | :--- |
| `harness/app_workflow.py` | Quản lý vòng đời Checkpoint cho nhánh App (`WorkflowStore`): kiểm soát chuyển trạng thái, thẩm định chữ ký SHA256 Spec/Manifest, tự động khử trùng lặp bằng chứng (evidence deduplication) và quét sạch trạng thái cũ (consistency auto-sweep). |
| `docs/app-workflow-guide.md` | Hướng dẫn chi tiết luồng vận hành chuẩn Native Gemini App Workflow: hợp đồng vai trò, tiêu chuẩn nghiệm thu và quy trình tái tục nhiệm vụ (resume). |
| `docs/intake-protocol.md` | Giao thức phỏng vấn Intake 3 câu hỏi cốt lõi trước khi lập Spec kiến trúc, chống giả định ngầm. |
| `docs/human-test-sheet-template.md` | Mẫu bảng kiểm thử UAT chuẩn hóa (Human Test Sheet) dành cho người dùng nghiệm thu thủ công trong 3 phút. |
| `scripts/run_security_audit.py` | Quét bảo mật toàn diện: phát hiện hardcoded secrets (API keys, Tokens, Private Keys, DB URLs) và kiểm tra lỗ hổng dependency (`npm audit`, `pip-audit`). Hỗ trợ cờ `--fail-on-critical` và xuất báo cáo JSON/Markdown. |
| `scripts/run_dev_logger.py` | Quản lý tiến trình nền dev server, stream log ra file và thực hiện Pre-flight Check (port, health status 200). |
| `scripts/generate_launcher.py` | Tự động quét môi trường ứng dụng và sinh file khởi chạy 1-click `start-app.bat` kèm cẩm nang `HDSD-NHANH.md`. Hỗ trợ tùy chọn `--docker` để sinh trọn bộ Dockerfile, `docker-compose.yml`, `.github/workflows/ci.yml`, `.env.example` và `ARCHITECTURE.md`. |
| `agents/app/e2e_engineer.md` | Tác tử lập trình kịch bản Playwright E2E tự động hóa kiểm thử giao diện theo tiêu chuẩn Page Object Model. |
| `agents/app/e2e_critic.md` | Tác tử kiểm định độc lập kịch bản Playwright E2E (phát hiện hardcoded sleep, selector mong manh, thiếu assertion). |
| `harness/state_machine.py` | Định nghĩa các trạng thái (`INIT`, `INTAKE`, `DESIGN`, `IMPLEMENTATION`, `AUDIT`, `APPROVED`, `REJECTED`, `ESCALATED`) và quản lý bước chuyển trạng thái hợp lệ, ngăn chặn việc nhảy cóc quy trình. |
| `harness/quality_gate.py` | Kiểm tra định dạng phán quyết của Checker (`VERDICT: APPROVE`, `REJECT`, `ESCALATE`) và đếm số vòng lặp critique. |
| `harness/orchestrator.py` | Khởi tạo môi trường, tiếp nhận yêu cầu từ người dùng, nạp `TaskContext`, chuyển giao cho Runner thích hợp và gửi kết quả thẩm định. |
| `harness/runners/` | Đóng gói chu trình 3 bước cho từng nhánh: `app_runner.py` (Architect → Builder → QA Auditor) và `marketing_runner.py` (Researcher → Creator → Compliance Critic). Runner là nơi ghi trace từng bước. |
| `harness/memory/` | Vòng lặp tự học & bộ nhớ quỹ đạo (Trajectory): thu hoạch bài học kinh nghiệm (`harvester.py`), chưng cất kỹ năng mới (`distiller.py`) và lưu trữ lịch sử thực thi (`trajectory.py`). |
| `harness/skills/` | Quản lý vòng đời kỹ năng: định tuyến theo từ khóa (`router.py`), quản lý hàng đợi staging và phê duyệt (`manager.py`), đánh giá chất lượng và phát hiện trùng lặp (`curator.py`). |
| `configs/harness_config.json` | Khai báo model tier (`pro`/`flash`), `roles`, `limits` và `skill_routing` (34 skill → keyword). **Lưu ý:** chưa có code nào resolve/gọi model — đây là metadata cấu hình, cần adapter LLM mới dùng được. |
| `rubrics/` | Định nghĩa các checklist khắt khe độc lập mà Checker bắt buộc phải đối chiếu khi đánh giá (`design_review_rubric.md`, `code_quality_rubric.md`, `content_compliance_rubric.md`). |

---

## 2. Luồng Điều Phối Theo Phân Nhánh

Hệ thống hoạt động theo nguyên tắc tách biệt vai trò (Maker-Checker Invariant): Tác tử tạo nội dung/code không bao giờ tự duyệt sản phẩm của mình.

### 2.1. Nhánh 1: Phát Triển Phần Mềm (`app`) — Gemini Native App Workflow

Quy trình phát triển phần mềm tuân thủ nghiêm ngặt mô hình Gemini Native App Workflow toàn diện với cơ chế Maker-Checker 2 tầng (Kiến trúc & Mã nguồn), kiểm thử tự động E2E Playwright, rà soát an toàn bảo mật (Security Audit) và đóng gói Production Ops (1-Click Launcher, Docker, CI/CD):

```mermaid
flowchart TD
    A["PHA 0: INTAKE & SCOPE ALIGNMENT<br/><i>Phỏng vấn 3 câu hỏi cốt lõi</i>"] --> B["PHA 1: DESIGN<br/>(SubAgent: Architect)<br/><i>Spec 5 mục + AC-SEED dữ liệu mẫu</i>"]
    B --> C["PHA 2: DESIGN REVIEW<br/>(SubAgent: Design Reviewer)<br/><i>Đối soát design rubric độc lập</i>"]
    C -->|"VERDICT: APPROVE"| D["PHA 3: HUMAN SIGN-OFF<br/>(Sếp duyệt khóa SHA256 Spec)"]
    C -->|"VERDICT: REJECT lần 1"| B
    C -->|"VERDICT: REJECT lần 2"| ESC1["ESCALATED (Báo cáo Sếp)"]
    D --> E["PHA 4: IMPLEMENTATION<br/>(SubAgent: Builder)<br/><i>TDD + Nạp mockData.json + Snapshot manifest</i>"]
    E --> F["PHA 5: AUDIT & E2E TESTING<br/>(QA Auditor + E2E Playwright Engineer & Critic)<br/><i>Dev Logger + Port Check + Playwright E2E</i>"]
    F -->|"VERDICT: REJECT lần 1"| E
    F -->|"VERDICT: REJECT lần 2"| ESC2["ESCALATED (Báo cáo Sếp)"]
    F -->|"VERDICT: APPROVE"| SEC["PHA 5.5: SECURITY AUDIT<br/>(scripts/run_security_audit.py)<br/><i>Quét secret leak & lỗ hổng dependencies</i>"]
    SEC -->|"VERDICT: REJECT"| E
    SEC -->|"VERDICT: APPROVE"| G["PHA 6: PACKAGING & PRODUCTION OPS<br/>(1-Click Launcher + Docker + CI/CD + UAT)<br/><i>start-app.bat + Docker + CI/CD + ARCHITECTURE.md</i>"]
    G --> H["APPROVED / BÀN GIAO TOÀN DIỆN"]
```

1. **Pha 0 - INTAKE & SCOPE ALIGNMENT (Phỏng vấn 3 câu hỏi cốt lõi):**
   - **Tài liệu quy chuẩn:** `docs/intake-protocol.md`.
   - **Nhiệm vụ:** Trước khi viết một dòng Spec nào, Quản đốc bắt buộc dừng lại phỏng vấn Sếp 3 câu hỏi cốt lõi: (1) Mục tiêu & Người dùng chính, (2) Khung công nghệ & Phạm vi (Scope In/Out), (3) Ràng buộc kỹ thuật & Tiêu chí nghiệm thu (Acceptance Criteria). Tránh tuyệt đối bệnh "giả định ngầm" và lập trình sai hướng.
2. **Pha 1 - DESIGN (Architect + AC-SEED dữ liệu mẫu bắt buộc):**
   - **Tác tử:** `agents/app/architect.md` (System Architect).
   - **Nhiệm vụ:** Tiếp nhận Intake, phân tích ranh giới chức năng (blast radius), thiết kế kiến trúc phân lớp, Schema dữ liệu, hợp đồng API và danh sách Acceptance Criteria có ID rõ ràng. BẮT BUỘC thiết kế tối thiểu 1 tiêu chí `AC-SEED` chỉ định cấu trúc và nội dung dữ liệu mẫu phong phú ban đầu (`mockData.json` / seeds) để người dùng mở app lên là thấy dữ liệu sống ngay lập tức, không để màn hình trắng (empty state).
3. **Pha 2 - DESIGN REVIEW (Design Reviewer độc lập):**
   - **Tác tử:** `agents/app/design_reviewer.md` (Design Reviewer).
   - **Nhiệm vụ:** Thẩm định độc lập bản Spec đối chiếu với `rubrics/design_review_rubric.md`. Kiểm tra tính khả thi, độ hoàn thiện của AC (bao gồm kiểm tra AC-SEED), rủi ro bảo mật và hiệu năng. Phán quyết chuẩn `VERDICT: APPROVE` hoặc `VERDICT: REJECT`.
4. **Pha 3 - HUMAN SIGN-OFF (Sếp duyệt khóa SHA256 Spec):**
   - **Thao tác:** Khóa cố định mã băm `spec_sha256`. Chỉ khi Sếp xác nhận rõ ràng ("Duyệt", "Triển khai"), hệ thống mới ghi nhận sign-off và cho phép chuyển sang bước triển khai. Mọi sửa đổi vào Spec sau sign-off sẽ tự động vô hiệu hóa phê duyệt cũ.
5. **Pha 4 - IMPLEMENTATION (Builder TDD + Nạp dữ liệu mẫu mockData.json):**
   - **Tác tử:** `agents/app/builder.md` (Developer / Maker).
   - **Nhiệm vụ:** Triển khai theo quy trình TDD (Test-Driven Development) bám sát Spec đã khóa; nạp sẵn dữ liệu mẫu thực tế phong phú (`mockData.json` / seed script); ghi nhận snapshot bytes toàn bộ source/test/config vào manifest SHA256. Phải chạy tests xanh trước khi bàn giao.
6. **Pha 5 - AUDIT & E2E TESTING (QA Auditor + E2E Playwright Engineer & Critic + Dev Logger & Pre-flight Port/Health Check):**
   - **Tác tử:** `agents/app/qa_auditor.md` (QA Auditor / Checker), phối hợp cặp đôi Maker-Checker E2E: `agents/app/e2e_engineer.md` (viết kịch bản Playwright E2E) và `agents/app/e2e_critic.md` (thẩm định độc lập kịch bản test E2E).
   - **Hạ tầng kiểm thử & Ghi log:** Khởi chạy `scripts/run_dev_logger.py` để stream background dev server ra file log (`logs/dev-server.log`), thực hiện Pre-flight Check (kiểm tra port khả dụng, quét dọn tiến trình mồ côi, health-check HTTP 200 trước khi test). Chạy toàn bộ unit test, integration test và Playwright E2E test; thu thập screenshot/video/console log chứng minh từng UI AC.
7. **Pha 5.5 - SECURITY AUDIT (Quét an toàn bảo mật & Lỗ hổng phụ thuộc):**
   - **Công cụ & Tiện ích:** `scripts/run_security_audit.py` (hỗ trợ cờ `--fail-on-critical`, `--json`).
   - **Nhiệm vụ:** Kiểm tra an toàn bảo mật tự động trước khi đóng gói release:
     1. Quét rò rỉ secret nhạy cảm (API Keys, Tokens, Private Keys, Database credentials).
     2. Quét lỗ hổng bảo mật của dependencies (`npm audit` cho Node.js hoặc `pip-audit` cho Python).
     Nếu phát hiện lỗ hổng critical hoặc rò rỉ secret, trả về `VERDICT: REJECT` chuyển ngược Builder xử lý dứt điểm.
8. **Pha 6 - PACKAGING & PRODUCTION OPS (Đóng gói 1-Click Launcher, Docker, CI/CD & Nghiệm thu UAT):**
   - **Tài liệu & Kịch bản:** Sử dụng mẫu `docs/human-test-sheet-template.md` để lập bảng kiểm thử UAT rõ ràng (bước thực hiện, kết quả mong đợi, checkbox) cho Sếp nghiệm thu thực tế bằng tay trong 3 phút.
   - **Đóng gói Production Ops:** Chạy `scripts/generate_launcher.py --docker` để tự động dò tìm cấu hình dự án, kiểm tra port/process, tạo file khởi chạy 1-click `start-app.bat` và cẩm nang `HDSD-NHANH.md`. Đồng thời sinh trọn bộ artifact chuẩn Production: `Dockerfile`, `docker-compose.yml`, pipeline GitHub Actions `.github/workflows/ci.yml`, `.env.example` và tài liệu kiến trúc kỹ thuật `ARCHITECTURE.md`.
   - **Bàn giao:** Nhiệm vụ hoàn thành với đầy đủ bằng chứng thực chứng, checkpoint nhất quán, artifact Production hoàn chỉnh và báo cáo minh bạch cho Sếp.

#### Quy Trình Hotfix Fast-track (Khẩn Cấp)

Áp dụng khi cần khắc phục khẩn cấp sự cố nghiêm trọng (P0/P1), vá lỗi hồi quy hoặc xử lý lỗ hổng bảo mật zero-day trên môi trường Production mà không cần đi qua toàn bộ chu trình đầy đủ từ đầu:
- **Cắt giảm bước mở rộng:** Bỏ qua Pha 0 (Intake mở rộng) và Pha 1 (Spec nhiều trang).
- **Quy trình 4 bước tinh gọn:**
  1. **Hotfix Triage & Micro-Spec:** Quản đốc cô lập phạm vi sự cố (blast radius tối thiểu), Architect lập Micro-Spec tập trung duy nhất vào nguyên nhân gốc rễ và phương án vá lỗi.
  2. **Direct Sign-off:** Sếp duyệt trực tiếp Micro-Spec trong chat ("Duyệt hotfix").
  3. **Surgical Implementation & Regression Test:** Builder thực hiện sửa đổi cục bộ (Surgical Changes theo triết lý Karpathy Coder) và bổ sung test hồi quy chứng minh lỗi đã được khắc phục.
  4. **Strict QA & Security Gate:** QA Auditor chạy kiểm thử hồi quy và kích hoạt `scripts/run_security_audit.py` đảm bảo không phát sinh lỗ hổng mới trước khi bàn giao phát hành bản vá ngay lập tức.

---

### 2.2. Nhánh 2: Sáng Tạo Nội Dung & Tiếp Thị (`marketing`)

```mermaid
flowchart LR
    A["INTAKE"] --> B["RESEARCH<br/>(Researcher)"]
    B --> C["CREATION<br/>(Creator)"]
    C --> D["AUDIT<br/>(Compliance Critic)"]
    D -->|"VERDICT: APPROVE"| E["APPROVED"]
    D -->|"VERDICT: REJECT lần 1"| C
    D -->|"VERDICT: REJECT lần 2"| F["ESCALATED"]
```

1. **Bước 1 - RESEARCH (Researcher):**
   - **Tác tử:** `agents/marketing/web_researcher.md` (Web & Market Intelligence Researcher).
   - **Nhiệm vụ:** Nghiên cứu insight khách hàng mục tiêu, tìm kiếm từ khóa ngách, nắm bắt xu hướng thị trường và giải phẫu đối thủ cạnh tranh.
2. **Bước 2 - CREATION (Creator):**
   - **Tác tử:** `agents/marketing/creator.md` (Content Creator).
   - **Nhiệm vụ:** Soạn thảo kịch bản video, bài viết mạng xã hội hoặc sales copy chuyển đổi cao dựa trên insight từ Researcher.
3. **Bước 3 - AUDIT (Compliance Critic):**
   - **Tác tử:** `agents/marketing/compliance_critic.md` (Policy Reviewer).
   - **Nhiệm vụ:** Thẩm định nội dung đối soát với `rubrics/content_compliance_rubric.md`. Rà soát vi phạm chính sách nền tảng (Facebook Community Standards, YouTube Trust & Safety, TikTok Policy), loại bỏ sáo rỗng AI (AI slop) và ngụy biện logic.

Mode `research-only` bỏ CREATION, vẫn independent Critic audit. Bốn required IDs source_accuracy/policy/integrity/task_quality và đủ claim IDs được hash-bound; analytical task kiểm số liệu/công thức/tiền tệ/dates/source quality thay Hook/CTA bắt buộc. Hướng dẫn payload trong docs/marketing-workflow-guide.md.

### 2.3. Gọi Trực Tiếp Kỹ Năng Nhánh Marketing Trong Ô Chat (Slash Commands)

Toàn bộ 12 kỹ năng của nhánh Marketing đã được tích hợp đầy đủ và có thể gọi trực tiếp trong ô chat Antigravity bằng lệnh Slash `/<tên_lệnh>`:

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
| `/fb-admin` | Facebook Fanpage Manager | Quản lý Fanpage (đăng bài, đọc/trả lời comment) |
| `/framework-marketing-da-kenh` | Framework Marketing Đa Kênh | Sơ đồ hoá hành trình khách hàng 6 pha, kết nối ma trận kênh & 8 công cụ MCP Noti |

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
- REJECT lần đầu: Task quay Maker của pha để sửa theo phản hồi.
- REJECT thứ hai trong cùng pha: lập tức ESCALATED; app counters design/code riêng, marketing audit counter tồn tại qua restart/resubmit/revise.
- Khi đã ở trạng thái `ESCALATED`, hệ thống dừng lặp lại và bàn giao cho chuyên gia con người xử lý.

---

## 4. Hướng Dẫn Sử Dụng & Kiểm Thử

### 4.1. Cài Đặt Cấu Hình Môi Trường Khi Sang Máy Mới

Để áp dụng toàn bộ cấu hình plugin (`anti-workflows`, `chrome-devtools-plugin`, `gemini-api`, `google-antigravity-sdk`, `modern-web-guidance-plugin`) và `userSettings` chuẩn của hệ thống:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File setup\setup.ps1 -TargetDirectory .brain\portable-smoke -SkipSessionRestore
```
Script cài vào đích portable chỉ định, sao lưu/merge defaults và giữ lựa chọn config user; không restore global sessions khi có TargetDirectory. Bỏ TargetDirectory chỉ khi muốn cài user global `%USERPROFILE%\.gemini\config`.

---

### 4.2. Chạy Kiểm Thử Tự Động (Automated Testing)

Toàn bộ logic máy trạng thái, routing, vòng đời checkpoint workflow và kịch bản ngắt mạch đã được bao phủ bởi pytest. Để thực thi toàn bộ test suite:

```bash
# Chạy toàn bộ unit test và e2e test
pytest -v
```

Xem logs QA thực tế cho current revision. Archive không có `.git` khiến `test_env_example_duoc_commit` không chứng minh tracked state; giữ nguyên test và báo giới hạn, không tạo Git giả hoặc claim toàn bộ PASS.

Bộ test gồm 24 file (393 tests):
- `test_app_workflow.py` — Checkpoint store, review gate, verify-browser & evidence deduplication
- `test_app_workflow_hardening.py` — Gia cố các trường hợp biên của WorkflowStore
- `test_auto_harvest_global.py` — Harvest global learnings & trajectories
- `test_curator.py` — Đánh giá vòng đời skill, phát hiện trùng lặp & curation
- `test_distiller.py` — Chưng cất trajectory thành kỹ năng mới
- `test_dsh_patterns.py` — Kiểm tra mẫu thiết kế & phân rã nhiệm vụ (DSH)
- `test_generate_launcher_production.py` — Kiểm thử sinh cấu hình Production mở rộng (Docker, compose, CI/CD, ARCHITECTURE.md)
- `test_harness_core.py` — State machine, quality gate, circuit breaker
- `test_harness_e2e.py` — Luồng 2 nhánh, escalate sau 2 vòng REJECT
- `test_harness_learning.py` — Trajectory store + learning harvester
- `test_harness_live.py` — Kiểm thử live harness orchestration
- `test_launcher_and_dev_logger.py` — Kiểm thử tiện ích dev logger & trình sinh 1-click launcher
- `test_marketing_skill_quality.py` — Kiểm định chất lượng nội dung skill marketing
- `test_marketing_skills.py` — Frontmatter & loader của skill marketing
- `test_marketing_tools.py` — Kiểm thử công cụ marketing
- `test_marketing_workflow.py` — Workflow marketing checkpoint & audit
- `test_native_contracts.py` — Kiểm thử hợp đồng native agent & vai trò
- `test_repo_integrity.py` — Chặn hồi quy cấu trúc/secret/path cá nhân/ref gãy
- `test_run_security_audit.py` — Kiểm thử tiện ích rà soát bảo mật dependencies & secret leak
- `test_score_scripts.py` — Đối soát script chấm điểm SEO (Python vs Node.js)
- `test_session_manager.py` — Portable session sync
- `test_setup.py` — Kiểm thử setup script & config defaults
- `test_skill_manager.py` — Quản lý vòng đời skill và hàng đợi staging
- `test_skill_router.py` — Keyword routing (34 skill)

```text
$ pytest -q
393 passed in 33.03s
```

---

### 4.3. Hướng Dẫn Sử Dụng Lệnh CLI (`run_harness.py`)

Hệ thống cung cấp điểm vào CLI chuẩn xác qua `run_harness.py` hỗ trợ 2 chế độ: mô phỏng nhanh trạng thái nhiệm vụ và quản lý checkpoint vòng đời Native App Workflow.

#### 4.3.1. Chế Độ Mô Phỏng Nhiệm Vụ Nhanh (`--task`)

```bash
python run_harness.py --task "<mô tả nhiệm vụ>" --branch {app,marketing,auto}
```

**Ví dụ thực thi:**
```bash
# Khởi chạy luồng Kỹ thuật (App)
python run_harness.py --task "Xây dựng module xác thực phân quyền JWT" --branch app

# Khởi chạy luồng Tiếp thị (Marketing)
python run_harness.py --task "Soạn kịch bản video TikTok 60 giây phân tích tài chính" --branch marketing
```

**Tham số dòng lệnh nhiệm vụ:**
- `--task`: Mô tả nhiệm vụ.
- `--branch {app,marketing,auto}`: Chọn nhánh (mặc định `auto` = tự định tuyến theo `skill_routing`).
- `--checker-output "VERDICT: ..."`: Phán quyết Checker đưa vào (mặc định `VERDICT: APPROVE`). Dùng để kiểm thử luồng REJECT/ESCALATE.
- `--review-rounds N`: Mô phỏng N vòng review. Kích hoạt circuit breaker khi REJECT đến vòng 3 (`--review-rounds 3 --checker-output "VERDICT: REJECT"` → ESCALATED).
- `--task-id`: ID tùy chọn (mặc định sinh UUID mới).
- `--dump-skill`: In nội dung SKILL.md đã nạp ra stdout.
- `--json`: Xuất kết quả dạng JSON.
- `--auto-distill`: Tự động chưng cất kỹ năng vào staging khi task APPROVE.
- `--distill <TASK_ID>`: Chưng cất kỹ năng từ trajectory đã lưu.
- `--curate`: Đánh giá vòng đời kỹ năng và phát hiện trùng lặp.
- `--skills-pending`, `--skills-approve <ID>`, `--skills-reject <ID>`: Quản lý hàng đợi Staging.

#### 4.3.2. Quản Lý Vòng Đời Native App Workflow Checkpoint (`--workflow`)

Điểm vào chuyên biệt quản lý và đối soát tiến trình phát triển ứng dụng thông qua máy trạng thái checkpoint (`harness/app_workflow.py`):

```bash
python run_harness.py --workflow <action> --task-id <TASK_ID> [--actor <ACTOR>] [--payload <JSON>] [--payload-file <PATH>]
```

**Các hành động `--workflow` được hỗ trợ:**
| Hành động (`--workflow`) | Giai đoạn áp dụng | Mô tả & Chức năng |
| :--- | :--- | :--- |
| `init` | Khởi tạo | Tạo checkpoint mới cho task ID với các thông tin scope ban đầu. |
| `status` | Bất kỳ | Đọc và hiển thị toàn bộ trạng thái hiện tại, lịch sử revision và kết quả audit của task. |
| `spec` | `INIT` / Sửa đổi | Architect nạp bản thiết kế Spec 5 mục, sinh mã băm `spec_sha256`. |
| `design-review` | `DESIGN` | Design Reviewer độc lập ghi nhận phán quyết (`APPROVE` / `REJECT`). |
| `sign-off` | `DESIGN` | Sếp (Human) phê duyệt Spec, khóa cứng `spec_sha256` trước khi viết mã. |
| `implementation` | `DESIGN` | Builder bàn giao mã nguồn kèm `manifest_sha256` và kết quả kiểm thử. |
| `audit` | `IMPLEMENTATION` | QA Auditor độc lập đối soát mã nguồn và kiểm thử. |
| `audit-pending-browser` | `AUDIT` | QA Auditor tạm dừng thẩm định mã để chờ kiểm chứng giao diện thực tế. |
| `verify-browser` | `AUDIT_PENDING_BROWSER` | QA Auditor nạp bằng chứng UI thực tế (DevTools MCP), tự động khử trùng lặp evidence và kích hoạt Consistency Auto-Sweep để hoàn tất nghiệm thu (`APPROVED`). |
| `revise` | `AUDIT` (khi REJECT) | Ghi nhận yêu cầu chỉnh sửa và chuyển ngược task về cho Builder. |

**Ví dụ quy trình checkpoint thực tế:**
```bash
# 1. Khởi tạo task
python run_harness.py --workflow init --task-id task-board-01 --actor "User" --payload '{"title": "Task Board App"}'

# 2. Architect nạp Spec
python run_harness.py --workflow spec --task-id task-board-01 --actor "Architect" --payload-file spec.json

# 3. Design Reviewer thẩm định
python run_harness.py --workflow design-review --task-id task-board-01 --actor "Design Reviewer" --payload '{"verdict": "APPROVE", "notes": "Spec đạt chuẩn 5 mục"}'

# 4. Sếp duyệt khóa Spec
python run_harness.py --workflow sign-off --task-id task-board-01 --actor "User" --payload '{"approved": true}'

# 5. Builder bàn giao source code
python run_harness.py --workflow implementation --task-id task-board-01 --actor "Builder" --payload-file implementation.json

# 6. QA Auditor kiểm chứng giao diện thực tế & hoàn tất phê duyệt
python run_harness.py --workflow verify-browser --task-id task-board-01 --actor "QA Auditor" --payload-file browser_evidence.json

# 7. Kiểm tra trạng thái cuối
python run_harness.py --workflow status --task-id task-board-01
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
- `harness/app_workflow.py` đóng vai trò là **lớp quản lý checkpoint và kiểm chứng trạng thái độc lập** (`WorkflowStore`), bảo vệ tính toàn vẹn của mã băm SHA256 (Spec & Manifest), kiểm soát chặt chẽ thẩm quyền Actor và tự động dọn sạch trạng thái mâu thuẫn (Consistency Auto-Sweep). Nó không gọi trực tiếp LLM API hay chạy browser; việc tương tác LLM và kiểm thử trình duyệt do runtime tác tử native của Gemini trong Antigravity thực thi.
- File phụ trợ và tham chiếu cũ:
  - `plugins/code/skills/app`: Toàn bộ các tham chiếu phụ trợ cũ (`AI_CODE_WORKFLOW.md`, `references/coding-taste.md`, `references/engineering-standards.md`, `templates/app-spec.md`) đã được dọn sạch hoàn toàn, chuyển đổi 100% sang mô hình Native Multi-Agent Orchestration (Architect -> Design Reviewer -> Builder -> QA Auditor).
  - `plugins/marketing/skills/viet-content-seo-geo-v5`: `scripts/score.mjs`, `scripts/score.py` — nay **đã có** trong repo, đã kiểm chứng parity (JSON trùng nhau trên nhiều bài thử).
  Mỗi SKILL.md tương ứng đã có ghi chú **TRẠNG THÁI SKILL**; `tests/test_repo_integrity.py` giữ danh sách trong `KNOWN_GAPS` để không phát sinh con trỏ gãy mới.
- `setup.ps1` hỗ trợ đích portable, merges defaults giữ config user, kiểm resolved paths/symlink/junction và cấm repo/ancestor hoặc đích nằm trong packaged source dirs trước cleanup; repeat copy không tạo nesting. Không chạy default global install trong tests.
- `configs/harness_config.json` khai báo model `Gemini 3.1 Pro` / `Gemini 3.8 Flash` — **chưa xác minh** 2 ID này tồn tại, và không code nào resolve chúng. Cần Sếp xác nhận hoặc thay bằng ID thật khi viết adapter LLM.

---

## 7. Tối Ưu Hóa Ngân Sách Token (Customization Token Budget Optimization cho Antigravity 2.0)

Để đảm bảo hiệu năng vận hành mượt mà và tránh cạn kiệt cửa sổ ngữ cảnh (context window), hệ thống áp dụng cơ chế tối ưu hóa ngân sách token nghiêm ngặt theo đặc tả kiến trúc Antigravity 2.0:

### 7.1. Cơ Chế Ngân Sách Kép (Dual 20,000 Token Budget Invariant)
Antigravity 2.0 quản lý context prompt thông qua hai ngân sách độc lập:
1. **Rules Budget (20,000 tokens):** Dành riêng cho các quy tắc điều phối cốt lõi (`GEMINI.md`, `AGENTS.md`, các quy chuẩn vận hành hệ thống). Nếu vượt quá 20,000 tokens, các quy tắc dài sẽ bị hạ cấp (demoted), chỉ được nạp qua con trỏ file gián tiếp khiến tác tử mất đi các chỉ dẫn quan trọng.
2. **Customizations / Skills Budget (20,000 tokens):** Dành cho metadata của toàn bộ danh mục kỹ năng (skills metadata & system triggers). Khi danh mục phình to vượt ngưỡng, hệ thống sẽ cảnh báo tràn ngân sách và làm chậm quá trình lập luận của tác tử.

### 7.2. Khử Trùng Lặp 34 Kỹ Năng Kép (Plugins vs Standalone Skills)
- Hệ thống phát hiện và dọn sạch tình trạng phân mảnh định nghĩa khi 34 skills vừa tồn tại trong `plugins/code/skills/` hoặc `plugins/marketing/skills/`, vừa bị sao chép trùng lặp ở thư mục kỹ năng rời `skills/`.
- Chuẩn hóa toàn bộ: kỹ năng đóng gói theo plugin chính quy được ưu tiên, loại bỏ toàn bộ bản sao dư thừa tại thư mục rời, triệt tiêu xung đột định tuyến và tiết kiệm token metadata.

### 7.3. Dọn Dẹp Kỹ Năng Cũ (Nhóm 3 Cleanup) & Rút Gọn Danh Mục Kỹ Năng
- Rà soát và loại bỏ 14 kỹ năng thuộc Nhóm 3 gồm các AWF sessions cũ và các kỹ năng trùng lặp/thực nghiệm không cần thiết: `fable-thinking`, `doubt-driven`, `lazy-senior-dev`, `codebase-design`, `taste`, `canary-watch`, `liquid-glass`...
- Kết quả: Danh mục kỹ năng được tinh gọn từ **134 skills xuống còn 86 skills** chuẩn mực, giải phóng xấp xỉ **40% dung lượng context window**, giúp tác tử phản hồi nhanh và chuẩn xác hơn.

### 7.4. Khử Trùng Lặp Rules & Xóa Sạch Cảnh Báo Demoted
- Tinh gọn mối liên kết giữa `GEMINI.md` và `AGENTS.md`: Chuyển `AGENTS.md` thành con trỏ tham chiếu ngắn gọn về `GEMINI.md`, tập trung toàn bộ quy chuẩn điều phối tối cao tại một nguồn duy nhất.
- Đưa tổng dung lượng Rules về an toàn dưới ngưỡng 20,000 tokens, xóa sạch hoàn toàn cảnh báo `Rules token budget exceeded / demoted`, bảo toàn 100% chỉ dẫn điều phối của Quản đốc trong mọi phiên tương tác.

