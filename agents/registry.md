# Agent Registry — Bộ Tổng Hợp Tác Tử Chuẩn

File này là tài liệu tham chiếu tập trung cho **Quản đốc (Chief Orchestrator)**.
Mọi lần dispatch agent mới đều bắt đầu bằng cách đọc bảng metadata dưới đây, sau đó
gọi `define_subagent` + `invoke_subagent` theo đúng template quy định.

> [!IMPORTANT]
> Quản đốc **CẤM** nhét toàn bộ spec vào `Prompt` của `invoke_subagent`.
> Thay vào đó: đọc frontmatter → `define_subagent` (system_prompt = nội dung spec) → `invoke_subagent`.

---

## 1. Bảng Tóm Tắt 6 Agent

| `agent_name`        | `display_name`                       | `branch`    | `role`      | `enable_write_tools` | `enable_mcp_tools` | `workspace` |
|---------------------|--------------------------------------|-------------|-------------|----------------------|--------------------|-------------|
| `Architect`         | System Architect                     | `app`       | `maker`     | `true`               | `true`             | `inherit`   |
| `Builder`           | Developer / Builder                  | `app`       | `maker`     | `true`               | `true`             | `branch`    |
| `QA_Auditor`        | QA Auditor                           | `app`       | `checker`   | `true`               | `true`             | `inherit`   |
| `Web_Researcher`    | Web & Social Media Intelligence      | `marketing` | `researcher`| `true`               | `true`             | `inherit`   |
| `Creator`           | Content Creator                      | `marketing` | `maker`     | `true`               | `true`             | `inherit`   |
| `Compliance_Critic` | Compliance Critic                    | `marketing` | `checker`   | `true`               | `true`             | `inherit`   |

---

## 2. Template Gọi Chuẩn Từng Agent

### 2.1 Architect

```python
# Bước 1 — Pre-define (đọc spec từ agents/app/architect.md)
define_subagent(
    name="Architect",
    description="Nhận yêu cầu nghiệp vụ, khảo sát blast radius và chốt kiến trúc, schema dữ liệu, hợp đồng API, tiêu chí nghiệm thu cho Builder. Không viết code — chỉ đặc tả.",
    system_prompt=<nội dung đầy đủ của agents/app/architect.md>,
    enable_write_tools=True,
    enable_mcp_tools=True,
    enable_subagent_tools=False,
)

# Bước 2 — Dispatch
invoke_subagent(
    TypeName="Architect",
    Role="System Architect",
    Prompt=f"""
    Thiết kế kỹ thuật cho task: <mô tả yêu cầu ngắn gọn>.
    Ràng buộc: <ngôn ngữ/framework/deadline>.
    Mã nguồn hiện có: <tóm tắt hoặc đường dẫn>.
    Lưu bản thiết kế 5-mục ra file `{artifact_dir}/architect_spec.md`.
    """,
    Workspace="inherit",
)
```

---

### 2.2 Builder

```python
# Bước 1 — Pre-define (đọc spec từ agents/app/builder.md)
define_subagent(
    name="Builder",
    description="Triển khai đúng hợp đồng API/schema do Architect đặc tả, viết kiểm thử và cung cấp bằng chứng chạy thật. Cần branch riêng để tránh đụng code nhánh chính.",
    system_prompt=<nội dung đầy đủ của agents/app/builder.md>,
    enable_write_tools=True,
    enable_mcp_tools=True,
    enable_subagent_tools=False,
)

# Bước 2 — Dispatch
invoke_subagent(
    TypeName="Builder",
    Role="Developer / Builder",
    Prompt=f"""
    Đọc spec tại `{artifact_dir}/architect_spec.md`. Triển khai code vào branch. TRƯỚC KHI KẾT THÚC, bắt buộc xuất patch toàn bộ thay đổi (bằng lệnh `git diff main...HEAD > {artifact_dir}/builder_diff.patch`).
    """,
    Workspace="branch",
)
```

---

### 2.3 QA_Auditor

```python
# Bước 1 — Pre-define (đọc spec từ agents/app/qa_auditor.md)
define_subagent(
    name="QA_Auditor",
    description="Thẩm định độc lập sản phẩm của Builder: đối chiếu với đặc tả Architect, chạy lại test, quét bảo mật tối thiểu và phán quyết APPROVE / REJECT / ESCALATE.",
    system_prompt=<nội dung đầy đủ của agents/app/qa_auditor.md>,
    enable_write_tools=True,
    enable_mcp_tools=True,
    enable_subagent_tools=False,
)

# Bước 2 — Dispatch
invoke_subagent(
    TypeName="QA_Auditor",
    Role="QA Auditor",
    Prompt=f"""
    Kiểm định mã nguồn dựa trên bản vá tại `{artifact_dir}/builder_diff.patch` đối chiếu với `{artifact_dir}/architect_spec.md`.
    """,
    Workspace="inherit",
)
```

---

### 2.4 Web_Researcher

```python
# Bước 1 — Pre-define (đọc spec từ agents/marketing/web_researcher.md)
define_subagent(
    name="Web_Researcher",
    description="Thu thập dữ liệu thực địa từ Google, Facebook, Instagram và X/Twitter qua kiến trúc lai đa tầng (Dorking + Meta Graph API + Apify fallback). Xuất Research Dossier đầy đủ.",
    system_prompt=<nội dung đầy đủ của agents/marketing/web_researcher.md>,
    enable_write_tools=True,
    enable_mcp_tools=True,
    enable_subagent_tools=False,
)

# Bước 2 — Dispatch
invoke_subagent(
    TypeName="Web_Researcher",
    Role="Web & Market Intelligence Researcher",
    Prompt=f"""
    Trinh sát dữ liệu cho chủ đề: <chủ đề / ngành / sản phẩm>.
    Mục tiêu nội dung: <kịch bản YouTube | copy quảng cáo | bài SEO | offer stack>.
    Đối tượng mục tiêu: <mô tả persona>.
    Lưu Research Dossier ra file `{artifact_dir}/research_dossier.md`.
    """,
    Workspace="inherit",
)
```

---

### 2.5 Creator

```python
# Bước 1 — Pre-define (đọc spec từ agents/marketing/creator.md)
define_subagent(
    name="Creator",
    description="Soạn thảo kịch bản video, copy quảng cáo, bài SEO/GEO và offer stack dựa trên Research Dossier. Áp dụng framework AIDA, PAS, Hormozi, Kahneman. Không tự phê duyệt.",
    system_prompt=<nội dung đầy đủ của agents/marketing/creator.md>,
    enable_write_tools=True,
    enable_mcp_tools=True,
    enable_subagent_tools=False,
)

# Bước 2 — Dispatch
invoke_subagent(
    TypeName="Creator",
    Role="Content Creator",
    Prompt=f"""
    Soạn <loại nội dung: kịch bản YouTube | copy quảng cáo | bài SEO | offer stack>
    cho chủ đề: <chủ đề>.
    Framework áp dụng: <AIDA | PAS | Hormozi | Kahneman | Bóc phốt format X>.
    Đọc Dossier tại `{artifact_dir}/research_dossier.md`. Lưu bản thảo hoàn chỉnh ra file `{artifact_dir}/creator_draft.md`.
    """,
    Workspace="inherit",
)
```

---

### 2.6 Compliance_Critic

```python
# Bước 1 — Pre-define (đọc spec từ agents/marketing/compliance_critic.md)
define_subagent(
    name="Compliance_Critic",
    description="Thẩm định độc lập bản thảo nội dung theo 4 trụ cột: chính sách nền tảng, lọc AI Slop, logic & bằng chứng, và độ sắc Hook/CTA. Phán quyết VERDICT: APPROVE / REJECT.",
    system_prompt=<nội dung đầy đủ của agents/marketing/compliance_critic.md>,
    enable_write_tools=True,
    enable_mcp_tools=True,
    enable_subagent_tools=False,
)

# Bước 2 — Dispatch
invoke_subagent(
    TypeName="Compliance_Critic",
    Role="Compliance Critic",
    Prompt=f"""
    Đọc bản thảo tại `{artifact_dir}/creator_draft.md` và đối chiếu với `{artifact_dir}/research_dossier.md`.
    """,
    Workspace="inherit",
)
```

---

## 3. Quy Tắc Tiền Đăng Ký (Pre-Registration Rules)

### Khi nào cần `define_subagent` trước `invoke_subagent`?

| Tình huống | Hành động đúng |
|---|---|
| Agent chưa được define trong session hiện tại | **Bắt buộc** `define_subagent` trước |
| Agent đã được define trong cùng session | Gọi thẳng `invoke_subagent(TypeName=<name>)` |
| Task nhỏ, bối cảnh đơn giản, không cần spec đầy đủ | Dùng `TypeName="self"` hoặc `TypeName="research"` |
| Task marketing đơn giản (tra thông vị, không sản xuất nội dung) | Dùng `TypeName="research"` thay vì define `Web_Researcher` |

### Khi nào dùng thẳng `type=self`?

- Phân tích nhanh codebase không cần Maker-Checker.
- Debug / tìm hiểu cấu trúc file.
- Bất kỳ task nào không yêu cầu chuyên môn sâu của spec agent.

> [!TIP]
> Một lần `define_subagent` trong session là đủ. Sau khi đã define, gọi `invoke_subagent`
> nhiều lần với cùng `TypeName` mà không cần define lại.

---

## 4. Thứ Tự Dispatch Đúng

### Nhánh App (App Pipeline)

```
Quản đốc nhận yêu cầu
        │
        ▼
[BƯỚC 1] invoke_subagent(Architect)
   → Trả về: .brain/artifacts/architect_spec.md
        │
        ▼
[BƯỚC 1.5] CỔNG XÁC NHẬN Ý ĐỊNH
   → Quản đốc dùng tool `ask_question` trình Sếp duyệt nội dung trong file artifacts. CHỈ KHI Sếp duyệt, mới chuyển sang Bước 2 (Khởi chạy Maker 2).
        │
        ▼
[BƯỚC 2] invoke_subagent(Builder)   ← Nhận: .brain/artifacts/architect_spec.md
   → Trả về: .brain/artifacts/builder_diff.patch
        │
        ▼
[BƯỚC 3] invoke_subagent(QA_Auditor) ← Nhận: .brain/artifacts/builder_diff.patch + .brain/artifacts/architect_spec.md
   → Trả về: VERDICT: APPROVE | REJECT | ESCALATE
        │
   ┌────┴────┐
APPROVE   REJECT (≤ 2 vòng) → Quay lại Builder
              REJECT (> 2 vòng) → Circuit Breaker → Báo Sếp
```

**Quy tắc cứng:**
- Không được skip Architect và đưa yêu cầu thô thẳng cho Builder.
- Builder chỉ được khởi chạy sau khi có Output 5-mục đầy đủ từ Architect.
- QA_Auditor không được nhận task từ Architect — chỉ nhận sản phẩm từ Builder.

---

### Nhánh Marketing (Marketing Pipeline)

```
Quản đốc nhận topic / brief
        │
        ▼
[BƯỚC 1] invoke_subagent(Web_Researcher)
   → Trả về: .brain/artifacts/research_dossier.md
        │
        ▼
[BƯỚC 1.5] CỔNG XÁC NHẬN Ý ĐỊNH
   → Quản đốc dùng tool `ask_question` trình Sếp duyệt nội dung trong file artifacts. CHỈ KHI Sếp duyệt, mới chuyển sang Bước 2 (Khởi chạy Maker 2).
        │
        ▼
[BƯỚC 2] invoke_subagent(Creator)   ← Nhận: .brain/artifacts/research_dossier.md
   → Trả về: .brain/artifacts/creator_draft.md
        │
        ▼
[BƯỚC 3] invoke_subagent(Compliance_Critic) ← Nhận: .brain/artifacts/creator_draft.md + .brain/artifacts/research_dossier.md
   → Trả về: Audit Report + VERDICT: APPROVE | REJECT
        │
   ┌────┴────┐
APPROVE   REJECT (≤ 2 vòng) → Quay lại Creator
              REJECT (> 2 vòng) → Circuit Breaker → Báo Sếp
```

**Quy tắc cứng:**
- Creator phải nhận Research Dossier — không được viết nội dung khi chưa có dữ liệu thực địa.
- Compliance_Critic không được biết về quá trình sáng tác của Creator (context độc lập).
- Maker (Creator) và Checker (Compliance_Critic) **tuyệt đối không chạy trong cùng một SubAgent**.

---

## 5. Vị Trí File Spec

| `agent_name`        | Đường dẫn file spec                                   |
|---------------------|-------------------------------------------------------|
| `Architect`         | `agents/app/architect.md`                             |
| `Builder`           | `agents/app/builder.md`                               |
| `QA_Auditor`        | `agents/app/qa_auditor.md`                            |
| `Web_Researcher`    | `agents/marketing/web_researcher.md`                  |
| `Creator`           | `agents/marketing/creator.md`                         |
| `Compliance_Critic` | `agents/marketing/compliance_critic.md`               |
| Rubric App          | `rubrics/code_quality_rubric.md`                      |
| Rubric Marketing    | `rubrics/content_compliance_rubric.md`                |
