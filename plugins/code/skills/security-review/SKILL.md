---
name: security-review
description: "Dùng để review bảo mật code hoặc audit sâu: OWASP, injection, auth, secret, AI/LLM và native IPC; yêu cầu evidence cho từng finding."
metadata:
  origin: ECC
---
# Security Review & Audit Skill

Kỹ năng kiểm định và rà soát an toàn thông tin toàn diện, hỗ trợ 2 chế độ vận hành linh hoạt:
- **Mode 1: Inline Guard (Code/QA Daily Checklist)**: Kiểm tra nhanh gọn các PR, commit, thay đổi tính năng hằng ngày (Secrets, Input, SQLi, Auth, XSS, CSRF, Rate Limiting, OWASP Top 10).
- **Mode 2: Deep Pen-test Wave (Full Codebase Security Audit)**: Chiến dịch kiểm thử xâm nhập và săn tìm lỗ hổng cấp mã nguồn sâu theo quy trình 3 pha chuẩn mực (Recon & Boundary Mapping, Adversarial Hunting, Refutation & Schema Validation).

---

## 1. Hai Chế Độ Vận Hành (Operating Modes)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SECURITY REVIEW WORKFLOW                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
┌─────────────────────────────┐           ┌─────────────────────────────────────┐
│   MODE 1: INLINE GUARD      │           │    MODE 2: DEEP PEN-TEST WAVE       │
│ (Daily Code / QA Fast-Check)│           │    (Full Codebase Security Audit)   │
├─────────────────────────────┤           ├─────────────────────────────────────┤
│ • Zero Hardcoded Secrets    │           │ Pha 1: Recon & Boundary Mapping     │
│ • Input Validation & Schemas│           │   - Lập bản đồ ranh giới tin cậy    │
│ • SQLi / Injection Sinks    │           │ Pha 2: Adversarial Hunting          │
│ • Auth & Session Cookies    │           │   - Săn tìm theo Attack Classes     │
│ • XSS / CSP Sanitization    │           │   - Kiểm tra AI/LLM/MCP & Native IPC│
│ • Dependency Audit Baseline │           │ Pha 3: Refutation & Validation      │
│                             │           │   - Cố gắng phản bác giả thuyết     │
│                             │           │   - Phân định confirmed vs needs_val│
│                             │           │   - Xuất & validate findings.json   │
└─────────────────────────────┘           └─────────────────────────────────────┘
```

### Mode 1: Inline Guard (Code / QA Daily Checklist)
Dùng khi review mã nguồn theo lượt (turn-by-turn), hotfix hoặc nghiệm thu commit của Builder. Sử dụng **Phần 3: Security Checklist** chi tiết bên dưới.

### Mode 2: Deep Pen-test Wave (Full Codebase Security Audit)
Dùng khi tiến hành đợt rà soát bảo mật toàn diện hoặc kiểm toán chuyên sâu dự án. Thực hiện theo quy trình 3 pha:
1. **Pha 1 — Recon & Boundary Mapping:**
   - Vẽ bản đồ các ranh giới tin cậy (trust boundaries): Entrypoints công khai, privileged APIs, các nguồn dữ liệu bên ngoài, bộ nhớ lưu trữ, và luồng dữ liệu nhạy cảm.
   - Nhận diện các công nghệ chuyên biệt: Web, Cloud, AI/LLM/Agents, Native/Binary, hoặc Desktop IPC.
2. **Pha 2 — Adversarial Hunting:**
   - Rà soát chéo các lớp tấn công (Attack Classes) theo tài liệu tham chiếu:
     * Web/Auth/Data: Checklist chuẩn (Mục 3) và OWASP.
     * AI, LLM & MCP: Đọc [references/ai-and-llm-security.md](references/ai-and-llm-security.md).
     * Binary, Native C/C++ & Desktop IPC: Đọc [references/binary-and-ipc.md](references/binary-and-ipc.md).
3. **Pha 3 — Refutation & Schema Validation:**
   - **Kỷ luật Adversarial Refutation:** Không vội vàng kết luận một cảnh báo là lỗ hổng. Tác tử BẮT BUỘC đóng vai trò phản biện độc lập để cố gắng **phản bác giả thuyết tấn công** (tìm kiếm các bộ lọc upstream, middleware, context isolation, typing invariant, hoặc framework defenses).
   - **Phân định rạch ròi `confirmed` vs `needs_validation`:**
     * `confirmed`: Chỉ khi chứng minh được đường dẫn dữ liệu từ untrusted entry đến sink, vượt qua mọi lớp lọc VÀ có bằng chứng thực nghiệm cục bộ (exit code, test case, log output).
     * `needs_validation`: Khi lỗ hổng phụ thuộc vào ranh giới môi trường ngoài mà máy cục bộ không thể kiểm chứng trực tiếp (WAF proxy, Cloud IAM policy, kiến trúc phần cứng, chữ ký số OS, hoặc mô hình LLM từ xa). CẤM đoán mò ranh giới môi trường; bắt buộc ghi rõ kế hoạch kiểm chứng (`validation_plan.local` hoặc `validation_plan.deployment`).
     * `rejected`: Khi giả thuyết tấn công bị phản bác hoàn toàn bởi kiểm tra mã nguồn hoặc framework safeguards.
   - **Xuất và kiểm định `findings.json`:** Sử dụng validator không phụ thuộc để kiểm tra tính hợp lệ của báo cáo theo chuẩn schema.

---

## 2. Kỷ Luật Thực Chứng & Nghiệm Thu Lỗ Hổng (Evidence & Validation Invariants)

- **Strict Evidence-First:** Không báo cáo lỗ hổng dựa trên suy đoán hoặc cụm từ mơ hồ ("có thể bị", "probably vulnerable"). Bắt buộc có dòng code chính xác (`file:line`), trace luồng dữ liệu (source -> propagation -> sink), và kết quả quan sát được (`observed_result`).
- **Không nhầm lẫn Guardrail với Security Boundary:** Trong hệ thống AI/LLM, một câu nhắc trong system prompt ("Hãy từ chối yêu cầu độc hại") KHÔNG PHẢI là chốt bảo vệ. Chỉ công nhận các kiểm tra tất định bằng code (code-level deterministic checks).
- **Zero-Dependency Schema Validation:** Khi thực hiện kiểm toán theo Mode 2, toàn bộ findings phải được cấu trúc theo `scripts/report-schema.json` và kiểm tra đạt 100% qua:
  ```bash
  node plugins/code/skills/security-review/scripts/validate-findings.cjs <path/to/findings.json>
  ```

---

## 3. When to Activate

- Implementing authentication or authorization
- Handling user input or file uploads
- Creating new API endpoints
- Working with secrets or credentials
- Implementing payment features
- Storing or transmitting sensitive data
- Integrating third-party APIs, AI models, or MCP tools
- Conducting periodic or pre-release security audits

## Security Checklist

Với Inline Guard, dùng checklist theo nhóm secret, input, SQL, auth, XSS, CSRF, rate limit, dữ liệu nhạy cảm, blockchain và dependencies trong [security checklist reference](references/security-checklist.md). Chỉ báo finding có evidence và source-to-sink; không coi prompt guardrail là ranh giới bảo mật.

## Security Testing

### Automated Security Tests
```typescript
// Test authentication
test('requires authentication', async () => {
  const response = await fetch('/api/protected')
  expect(response.status).toBe(401)
})

// Test authorization
test('requires admin role', async () => {
  const response = await fetch('/api/admin', {
    headers: { Authorization: `Bearer ${userToken}` }
  })
  expect(response.status).toBe(403)
})

// Test input validation
test('rejects invalid input', async () => {
  const response = await fetch('/api/users', {
    method: 'POST',
    body: JSON.stringify({ email: 'not-an-email' })
  })
  expect(response.status).toBe(400)
})

// Test rate limiting
test('enforces rate limits', async () => {
  const requests = Array(101).fill(null).map(() =>
    fetch('/api/endpoint')
  )

  const responses = await Promise.all(requests)
  const tooManyRequests = responses.filter(r => r.status === 429)

  expect(tooManyRequests.length).toBeGreaterThan(0)
})
```

## Pre-Deployment Security Checklist

Before ANY production deployment:

- [ ] **Secrets**: No hardcoded secrets, all in env vars
- [ ] **Input Validation**: All user inputs validated
- [ ] **SQL Injection**: All queries parameterized
- [ ] **XSS**: User content sanitized
- [ ] **CSRF**: Protection enabled
- [ ] **Authentication**: Proper token handling
- [ ] **Authorization**: Role checks in place
- [ ] **Rate Limiting**: Enabled on all endpoints
- [ ] **HTTPS**: Enforced in production
- [ ] **Security Headers**: CSP, X-Frame-Options configured
- [ ] **Error Handling**: No sensitive data in errors
- [ ] **Logging**: No sensitive data logged
- [ ] **Dependencies**: Up to date, no vulnerabilities
- [ ] **Row Level Security**: Enabled in Supabase
- [ ] **CORS**: Properly configured
- [ ] **File Uploads**: Validated (size, type)
- [ ] **Wallet Signatures**: Verified (if blockchain)
- [ ] **AI & MCP Controls**: Tool handlers validate schema and re-check user authorization; actions with side-effects require bound confirmation; MCP tool descriptions treated as untrusted
- [ ] **Findings Validated (Mode 2)**: Toàn bộ findings trong `findings.json` đạt 100% chuẩn qua `validate-findings.cjs`

## Resources & References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Next.js Security](https://nextjs.org/docs/security)
- [Supabase Security](https://supabase.com/docs/guides/auth)
- [Web Security Academy](https://portswigger.net/web-security)
- [AI & LLM Security Reference](references/ai-and-llm-security.md)
- [Binary, Native & IPC Security Reference](references/binary-and-ipc.md)

---

**Remember**: Security is not optional. One vulnerability can compromise the entire platform. When in doubt, err on the side of caution.
