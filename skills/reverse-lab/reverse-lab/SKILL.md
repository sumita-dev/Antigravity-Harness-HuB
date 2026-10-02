---
name: reverse-lab
description: >
  Runs the Reverse-Engineer lab pipeline on Antigravity 2.0: reverse-skill
  routing, compiled-language playbook (skill co rack), mitmproxy capture, and
  Frida hooks. Use when the user invokes /reverse-lab, asks to reverse a binary
  or APK, capture TLS, hook a process, or analyze Go/Rust/Swift/.NET/C++ samples
  in this workspace.
  TRIGGERS: 'reverse-lab', 'dịch ngược', 'reverse engineer', 'phân tích APK', 'phân tích binary', 'bắt gói tin TLS', 'mitmproxy', 'hook hàm', 'Frida hook'.
---

# Reverse-lab (Antigravity 2.0)

Execute the numbered steps **in order**. Do not skip to analysis. Do not only acknowledge. User-visible language: Vietnamese unless the user writes another language.

**Lab root:** workspace of this skill (`D:\AntiGravity\Reverse-Engineer` when opened as the project).

| Role | Path |
|------|------|
| Router | `reverse-skill-main/` |
| Frida source | `frida-main/` |
| mitmproxy source | `mitmproxy-main/` |
| Language playbook | `skill co rack.md` |
| Lab scripts | `lab/` |
| Case artifacts | `work/<case>/` |
| Antigravity MCP | `.agents/mcp_config.json` |

Load extra detail only when needed: `references/phase-commands.md`.

## ACTION REQUIRED

After reading this file, collect inputs then start at Step 1.

Sếp chỉ cần cung cấp tối thiểu **sample** và **hint** (mục tiêu). Các thông số khác tự động áp dụng giá trị mặc định tiện dụng.

Required inputs (chỉ hỏi nếu thiếu `sample` hoặc `hint`):

- **sample**: absolute path to the authorized local file (exe/dll/apk/elf), or `none` for docs-only (bắt buộc cung cấp)
- **hint**: one-line task (ví dụ: `offline golang binary reverse pclntab`, bắt buộc cung cấp)
- **auth**: mặc định luôn là `offline-sample` cho mọi sample cục bộ / CTF trong workspace này (tự động áp dụng, không cần hỏi lại Sếp; chỉ yêu cầu quyền khi thao tác trên remote/production target)
- **case_name**: mặc định tự động trích xuất từ tên file sample nếu không chỉ định (ví dụ: `sample.exe` -> `sample-exe`)
- **capture**: mặc định là `auto` (hoặc `yes`/`no` nếu Sếp chỉ định rõ). Khi là `auto`, AI sẽ tự động soi network indicators ở Step 5 (Imports table: `net/http`, `ws2_32`, `wininet`, `winhttp`, `HttpClient`, `okhttp`... hoặc strings URL/domain/IP). Nếu phát hiện network stack/outbound intent thì tự động bật capture ở Step 6; nếu là offline/standalone binary không có network activity thì tự động bỏ qua Step 6 mà không cần hỏi lại Sếp.

Stop if the user has no authorization. Mọi sample offline cục bộ tự động dùng preset `offline-sample`.

---

## Step 1 — Bootstrap lab

Run (PowerShell, from lab root):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\start-pipeline.ps1
```

Expect `PIPELINE_READY`. Record FRIDA / MITM / GORESYM / RUSTFILT / GHIDRA lines.

If any of `FRIDA_MISSING`, `GORESYM_MISSING`, `GHIDRA_MISSING`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\install-core.ps1
```

That installs `frida-tools==14.10.4`, GoReSym, bootstraps Ghidra, and tries `cargo install rustfilt`.

Read `reverse-skill-main/skills/tool-index.md` for real tool paths. Do not guess paths.

**GhidraMCP (Antigravity):** `.agents/mcp_config.json` registers `ghidra` at `http://127.0.0.1:8765/mcp`. Server is live only after Ghidra has the GhidraMCP extension and a project is open. Refresh MCP in Customizations. Use MCP decompile/xref in Step 5 when the server is up; otherwise `analyzeHeadless` from tool-index.

## Step 2 — Identify runtime (if sample exists)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\identify-runtime.ps1 -Sample "<sample>"
```

Map `LANG` to the rack section in `skill co rack.md`:

| LANG | Next |
|------|------|
| `go` / `rust` | PRIMARY will be R33 `go-rust-reverse/` then rack |
| `dotnet` | `dotnet-reverse/` (R5), not R33 |
| `swift` | iOS/IPA → `mobile-reverse/`; else rack Swift + Ghidra |
| `kotlin-native` | rack + Ghidra; APK/JVM → `apk-reverse/` |
| `unknown` | continue; master-route decides (often R0) |

## Step 3 — Route

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\route.ps1 -Hint "<hint>"
```

Read the printed `PRIMARY -> skills/.../SKILL.md`. Open that file under `reverse-skill-main/` and execute its ACTION REQUIRED.

## Step 4 — Scope gate (MUST before any ACT on the sample)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File reverse-skill-main\skills\scripts\case-init.ps1 -Hint "<hint>" -CaseName "<case_name>" -ProjectRoot "<lab-root>" -Preset offline-sample -Sample "<sample>"
```

If not offline, omit `-Preset` / `-Sample` and set auth in `work/<case>/scope.md` until `auth.status=granted` and `ready_for_act=true`.

Then:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File reverse-skill-main\skills\scripts\case-guard.ps1 -CaseRoot "work\<case_name>"
```

Exit 2 → stop. Do not hook, proxy, or unpack until the gate is green.

## Step 5 — Static (language playbook)

1. Read PRIMARY `SKILL.md`.
2. If Go/Rust/compiled-language: read `skill co rack.md` for that language only.
3. Hash the sample (SHA256) into `work/<case>/evidence/`.
4. Recover symbols (paths from tool-index):
   - Go: `GoReSym.exe -d -p "<sample>" > work/<case>/evidence/goresym.json` then `go version -m` if present
   - Rust: `rustfilt` on `nm`/`strings` panic lines; if rustfilt missing, record and continue with raw `_ZN` names
   - Generic: GhidraMCP tools if `ghidra` MCP is connected; else `analyzeHeadless`; else strings + rack
5. Write Evidence notes: markers, imports/exports or `quality=unreadable`, key functions, và các dấu hiệu mạng (network indicators: APIs, URLs, IPs, domains) làm đầu vào cho Step 6.

Timebox static ~15 minutes with no key path → Step 6 or 7.

## Step 6 — Network (Adaptive Capture hoặc capture=yes)

**Logic Adaptive Capture:**
- **Nếu `capture=no`**: Luôn bỏ qua Step 6 (skip).
- **Nếu `capture=yes`**: Khởi động pipeline capture (nếu scope cho phép).
- **Nếu `capture=auto` (mặc định)**:
  - Kiểm tra kết quả Static Analysis ở Step 5:
    - Imports: `net/http`, `ws2_32.dll`, `wininet.dll`, `winhttp.dll`, `System.Net.Http`, `HttpClient`, `okhttp`, `URLSession`, socket APIs...
    - Strings: URL (`http://`, `https://`), domains, endpoints, API routes, raw IP addresses...
  - **Nếu có outbound/network traffic intent**: Tự động kích hoạt pipeline capture bên dưới.
  - **Nếu không có (offline / standalone binary thuần túy)**: Tự động skip Step 6, chuyển ngay sang Step 7 hoặc 8.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\start-pipeline.ps1 -Capture -ProxyPort 8082
```

Point the target at `127.0.0.1:8082`. Install mitmproxy CA if TLS. Flows: `work/pcap/session-*.mitm`. Addon: `lab/addons/save-flows.py`.

Do not scan hosts outside `scope.md`.

## Step 7 — Dynamic (Frida)

Need `FRIDA_OK` **and** `frida-ps` on PATH (CLI, not the `frida-main` source tree). Attach only to the in-scope process:

```powershell
frida-ps
frida -n "<process>" -l lab\hooks\trace-exports.js
```

Use PRIMARY skill scripts when they exist (example: `apk-reverse/scripts/frida-run.ps1`). Go stacks differ from native; follow rack + `go-rust-reverse`.

If Frida is blocked (anti-debug), record Evidence and return to static. Do not brute-force production.

## Step 8 — Synthesis

In `work/<case>/`:

- Evidence → Finding → Path (`reverse-skill-main/skills/ops/evidence-finding-path.md`)
- `timeline.md` / `workitems.md` (delta only)
- Report via `docs-generator` if the user wants a deliverable
- Optional: `python reverse-skill-main/skills/case-review/scripts/review_case.py work/<case> --verify-hashes --strict`

## Step 9 — Stop capture + journal

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\stop-pipeline.ps1
```

Write a short field-journal entry under `reverse-skill-main/skills/field-journal/` (no secrets, no PII).

## Step 10 — Clean-Room Specification & Architecture Extraction

- Trích xuất Schema dữ liệu: Structs, Enums, Models từ GoReSym / Ghidra decompile.
- Trích xuất Call Graph & Workflow logic: Các hàm nghiệp vụ cốt lõi, validation rules, encryption/decryption routines.
- Biên soạn tệp đặc tả: `work/<case>/REBUILD_SPEC.md` theo cấu trúc:
  1. Overview & Mục tiêu phần mềm mới.
  2. Data Structures & Schemas.
  3. Function Signatures & Business Rules (Logic nghiệp vụ).
  4. API & Network Endpoints (nếu có).
  5. Acceptance Criteria cho ứng dụng mới.

## Step 11 — Autonomous App Rebuild (TDD & Equivalence Verification)

- Triệu tập subagent lập trình chuyên trách (`tdd-guide` hoặc quy trình `/app-factory`) nạp `REBUILD_SPEC.md`.
- Khởi tạo dự án mới theo ngôn ngữ mục tiêu (Go / Rust / C# / Python / TypeScript).
- Triển khai mã nguồn theo chu trình TDD (Red-Green-Refactor).
- Viết Equivalence Test Suites: đối chiếu kết quả đầu ra (I/O, status, data) của app mới với sample gốc để đảm bảo độ chính xác 100%.
- Biên dịch ứng dụng (Build Artifact) và bàn giao cho Sếp.

## Completion checklist

- [ ] start-pipeline ran and tool-index exists
- [ ] PRIMARY skill opened and followed
- [ ] scope gate green before ACT
- [ ] rack read for compiled languages
- [ ] Evidence has hash + runtime markers
- [ ] capture stopped if it was started
- [ ] conclusions cite Evidence ids
- [ ] Go samples: GoReSym JSON in evidence (or recorded miss)
- [ ] Decompile via GhidraMCP or analyzeHeadless, or recorded miss
- [ ] REBUILD_SPEC.md generated (Step 10)
- [ ] Equivalence tests passed and artifact built (Step 11)

## Decision boundaries (offer a numbered menu only here)

1. Deep-decompile a named function
2. Frida-verify a hypothesis
3. Start or stop mitm capture
4. Export report
5. Generate REBUILD_SPEC.md (Step 10)
6. Autonomous App Rebuild (Step 11)
7. Switch tool (IDA ↔ Ghidra ↔ r2)
8. Pause

If the next action is uniquely determined by a gate, continue without a menu.
