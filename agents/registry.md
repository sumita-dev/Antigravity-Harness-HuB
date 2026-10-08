# Agent Registry — Hợp đồng dispatch native

Bảng này là metadata và hợp đồng prompt, không phải schema API Antigravity. Quản đốc kiểm inventory thực tế rồi dùng công cụ subagent mà runtime cung cấp; không suy ra công cụ hoặc tham số từ ví dụ của repo. Exporter chỉ xuất prompt/frontmatter, không chạy agent.

| Agent | Branch | Stage | Role file | Quyền theo prompt |
| --- | --- | --- | --- | --- |
| `Architect` | app | DESIGN | agents/app/architect.md | Đọc source; ghi Spec/artifacts |
| `Design_Reviewer` | app | DESIGN_REVIEW | agents/app/design_reviewer.md | Đọc Spec/source; ghi report |
| `Builder` | app | IMPLEMENTATION | agents/app/builder.md | Sửa source/tests theo Spec đã duyệt |
| `QA_Auditor` | app | AUDIT | agents/app/qa_auditor.md | Đọc source; terminal test/browser; ghi evidence/report |
| `Web_Researcher` | marketing | RESEARCH | agents/marketing/web_researcher.md | Đọc/search; ghi dossier/evidence |
| `Creator` | marketing | CREATION | agents/marketing/creator.md | Đọc dossier; ghi draft/artifacts |
| `Compliance_Critic` | marketing | AUDIT | agents/marketing/compliance_critic.md | Đọc artifacts; ghi report/evidence, không sửa draft/source |
| `Synthesizer` | cross | Sau task | agents/synthesizer.md | Chưng cất skill theo phạm vi được giao |

## Routing và ràng buộc

Luôn đọc checkpoint `stage`/`next_agent` trước keyword; keyword chỉ chọn skill khi chưa có workflow hoặc bổ sung chuyên môn. App: Architect → Design Reviewer độc lập → Sếp duyệt đúng Spec SHA256 → Builder → QA độc lập. Marketing content: Researcher → Creator → Critic; `research-only`: Researcher → Critic. APPROVED/ESCALATED không dispatch Maker mới tự động.

REJECT lần đầu quay Maker của pha; REJECT thứ hai trong cùng pha chuyển ESCALATED ngay. Counters design/code của app và audit marketing tồn tại qua restart/resubmit/revise; không tạo task ID mới để bỏ gate.

Builder và QA phải dùng cùng checkout chứa source/test/config hiện tại, gồm staged, unstaged, untracked. Bản `git diff main...HEAD` chỉ là dữ liệu phụ, không đủ làm snapshot hoặc handoff. Nếu runtime tạo branch/worktree riêng, ghi absolute checkout và bàn giao thư mục đó cho QA; kiểm manifest bytes hiện tại trước audit.

Architect khác Reviewer; Builder khác QA; Researcher/Creator khác Critic. Actor ID là provenance khai báo, không chứng thực identity hay context isolation. Runtime phải tạo context độc lập và quan sát isolation thực tế.

## Tools và sandbox

Frontmatter `enable_write_tools`, `enable_mcp_tools`, `workspace`, `model` là cấu hình khai báo. File-write, terminal execution và MCP/browser là các capability khác nhau; quyền ghi file không tự cấp quyền terminal. Cho phép ghi artifact không cho phép sửa source. Khi runtime không có sandbox theo đường dẫn, hạn chế này chỉ được nhắc bằng prompt và kiểm bằng diff/manifest, không được claim đã cưỡng chế.

Kiểm từng capability theo trạng thái OBSERVED / DECLARED / UNAVAILABLE / NOT_VERIFIED trong `docs/native-readiness.md`. Thiếu browser không cho phép tự nhận UI PASS; QA hợp lệ có thể nộp PARTIAL_APPROVE và giữ AUDIT_PENDING_BROWSER theo hợp đồng app.

Model tiers trong `configs/harness_config.json` giữ lựa chọn hiện hữu; chưa có adapter resolve/gọi model và không đảm bảo model khả dụng.

Hướng dẫn payload: `docs/app-workflow-guide.md`, `docs/marketing-workflow-guide.md`. Product gates áp dụng job native Antigravity; bảo trì/audit chính harness đã được Sếp giao không cần tạo product task/signoff giả.
