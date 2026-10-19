---
name: security-review
description: "Quét lỗ hổng bảo mật OWASP, injection, endpoint và rò rỉ secret/API key."
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
     * AI, LLM & MCP: Đọc [references/ai-and-llm-security.md](file:///d:/AntiGravity/Antigravity-Harness-HuB-main/plugins/code/skills/security-review/references/ai-and-llm-security.md).
     * Binary, Native C/C++ & Desktop IPC: Đọc [references/binary-and-ipc.md](file:///d:/AntiGravity/Antigravity-Harness-HuB-main/plugins/code/skills/security-review/references/binary-and-ipc.md).
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

### 1. Secrets Management

#### FAIL: NEVER Do This
```typescript
const apiKey = "sk-proj-xxxxx"  // Hardcoded secret
const dbPassword = "password123" // In source code
```

#### PASS: ALWAYS Do This
```typescript
const apiKey = process.env.OPENAI_API_KEY
const dbUrl = process.env.DATABASE_URL

// Verify secrets exist
if (!apiKey) {
  throw new Error('OPENAI_API_KEY not configured')
}
```

#### Verification Steps
- [ ] No hardcoded API keys, tokens, or passwords
- [ ] All secrets in environment variables
- [ ] `.env.local` in .gitignore
- [ ] No secrets in git history
- [ ] Production secrets in hosting platform (Vercel, Railway)

### 2. Input Validation

#### Always Validate User Input
```typescript
import { z } from 'zod'

// Define validation schema
const CreateUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
  age: z.number().int().min(0).max(150)
})

// Validate before processing
export async function createUser(input: unknown) {
  try {
    const validated = CreateUserSchema.parse(input)
    return await db.users.create(validated)
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { success: false, errors: error.issues }
    }
    throw error
  }
}
```

#### File Upload Validation
```typescript
function validateFileUpload(file: File) {
  // Size check (5MB max)
  const maxSize = 5 * 1024 * 1024
  if (file.size > maxSize) {
    throw new Error('File too large (max 5MB)')
  }

  // Type check
  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif']
  if (!allowedTypes.includes(file.type)) {
    throw new Error('Invalid file type')
  }

  // Extension check
  const allowedExtensions = ['.jpg', '.jpeg', '.png', '.gif']
  const extension = file.name.toLowerCase().match(/\.[^.]+$/)?.[0]
  if (!extension || !allowedExtensions.includes(extension)) {
    throw new Error('Invalid file extension')
  }

  return true
}
```

#### Verification Steps
- [ ] All user inputs validated with schemas
- [ ] File uploads restricted (size, type, extension)
- [ ] No direct use of user input in queries
- [ ] Whitelist validation (not blacklist)
- [ ] Error messages don't leak sensitive info

### 3. SQL Injection Prevention

#### FAIL: NEVER Concatenate SQL
```typescript
// DANGEROUS - SQL Injection vulnerability
const query = `SELECT * FROM users WHERE email = '${userEmail}'`
await db.query(query)
```

#### PASS: ALWAYS Use Parameterized Queries
```typescript
// Safe - parameterized query
const { data } = await supabase
  .from('users')
  .select('*')
  .eq('email', userEmail)

// Or with raw SQL
await db.query(
  'SELECT * FROM users WHERE email = $1',
  [userEmail]
)
```

#### Verification Steps
- [ ] All database queries use parameterized queries
- [ ] No string concatenation in SQL
- [ ] ORM/query builder used correctly
- [ ] Supabase queries properly sanitized

### 4. Authentication & Authorization

#### JWT Token Handling
```typescript
// FAIL: WRONG: localStorage (vulnerable to XSS)
localStorage.setItem('token', token)

// PASS: CORRECT: httpOnly cookies
res.setHeader('Set-Cookie',
  `token=${token}; HttpOnly; Secure; SameSite=Strict; Max-Age=3600`)
```

#### Authorization Checks
```typescript
export async function deleteUser(userId: string, requesterId: string) {
  // ALWAYS verify authorization first
  const requester = await db.users.findUnique({
    where: { id: requesterId }
  })

  if (requester.role !== 'admin') {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 403 }
    )
  }

  // Proceed with deletion
  await db.users.delete({ where: { id: userId } })
}
```

#### Row Level Security (Supabase)
```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can only view their own data
CREATE POLICY "Users view own data"
  ON users FOR SELECT
  USING (auth.uid() = id);

-- Users can only update their own data
CREATE POLICY "Users update own data"
  ON users FOR UPDATE
  USING (auth.uid() = id);
```

#### Verification Steps
- [ ] Tokens stored in httpOnly cookies (not localStorage)
- [ ] Authorization checks before sensitive operations
- [ ] Row Level Security enabled in Supabase
- [ ] Role-based access control implemented
- [ ] Session management secure

### 5. XSS Prevention

#### Sanitize HTML
```typescript
import DOMPurify from 'isomorphic-dompurify'

// ALWAYS sanitize user-provided HTML
function renderUserContent(html: string) {
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p'],
    ALLOWED_ATTR: []
  })
  return <div dangerouslySetInnerHTML={{ __html: clean }} />
}
```

#### Content Security Policy

Start strict and loosen only with a documented removal plan. Do not default to
`'unsafe-inline'` or `'unsafe-eval'`; they neutralize much of CSP's protection
and should be treated as temporary compatibility debt.

```typescript
// next.config.js
const securityHeaders = [
  {
    key: 'Content-Security-Policy',
    value: `
      default-src 'self';
      base-uri 'self';
      object-src 'none';
      frame-ancestors 'none';
      script-src 'self';
      style-src 'self';
      img-src 'self' data: https:;
      font-src 'self';
      connect-src 'self' https://api.example.com;
    `.replace(/\s{2,}/g, ' ').trim()
  }
]
```

#### Verification Steps
- [ ] User-provided HTML sanitized
- [ ] CSP headers configured
- [ ] No unvalidated dynamic content rendering
- [ ] React's built-in XSS protection used

### 6. CSRF Protection

#### CSRF Tokens
```typescript
import { csrf } from '@/lib/csrf'

export async function POST(request: Request) {
  const token = request.headers.get('X-CSRF-Token')

  if (!csrf.verify(token)) {
    return NextResponse.json(
      { error: 'Invalid CSRF token' },
      { status: 403 }
    )
  }

  // Process request
}
```

#### SameSite Cookies
```typescript
res.setHeader('Set-Cookie',
  `session=${sessionId}; HttpOnly; Secure; SameSite=Strict`)
```

#### Verification Steps
- [ ] CSRF tokens on state-changing operations
- [ ] SameSite=Strict on all cookies
- [ ] Double-submit cookie pattern implemented

### 7. Rate Limiting

#### API Rate Limiting
```typescript
import rateLimit from 'express-rate-limit'

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // 100 requests per window
  message: 'Too many requests'
})

// Apply to routes
app.use('/api/', limiter)
```

#### Expensive Operations
```typescript
// Aggressive rate limiting for searches
const searchLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 requests per minute
  message: 'Too many search requests'
})

app.use('/api/search', searchLimiter)
```

#### Verification Steps
- [ ] Rate limiting on all API endpoints
- [ ] Stricter limits on expensive operations
- [ ] IP-based rate limiting
- [ ] User-based rate limiting (authenticated)

### 8. Sensitive Data Exposure

#### Logging
```typescript
// FAIL: WRONG: Logging sensitive data
console.log('User login:', { email, password })
console.log('Payment:', { cardNumber, cvv })

// PASS: CORRECT: Redact sensitive data
console.log('User login:', { email, userId })
console.log('Payment:', { last4: card.last4, userId })
```

#### Error Messages
```typescript
// FAIL: WRONG: Exposing internal details
catch (error) {
  return NextResponse.json(
    { error: error.message, stack: error.stack },
    { status: 500 }
  )
}

// PASS: CORRECT: Generic error messages
catch (error) {
  console.error('Internal error:', error)
  return NextResponse.json(
    { error: 'An error occurred. Please try again.' },
    { status: 500 }
  )
}
```

#### Verification Steps
- [ ] No passwords, tokens, or secrets in logs
- [ ] Error messages generic for users
- [ ] Detailed errors only in server logs
- [ ] No stack traces exposed to users

### 9. Blockchain Security (Solana)

#### Wallet Verification
```typescript
import { verify } from '@solana/web3.js'

async function verifyWalletOwnership(
  publicKey: string,
  signature: string,
  message: string
) {
  try {
    const isValid = verify(
      Buffer.from(message),
      Buffer.from(signature, 'base64'),
      Buffer.from(publicKey, 'base64')
    )
    return isValid
  } catch (error) {
    return false
  }
}
```

#### Transaction Verification
```typescript
async function verifyTransaction(transaction: Transaction) {
  // Verify recipient
  if (transaction.to !== expectedRecipient) {
    throw new Error('Invalid recipient')
  }

  // Verify amount
  if (transaction.amount > maxAmount) {
    throw new Error('Amount exceeds limit')
  }

  // Verify user has sufficient balance
  const balance = await getBalance(transaction.from)
  if (balance < transaction.amount) {
    throw new Error('Insufficient balance')
  }

  return true
}
```

#### Verification Steps
- [ ] Wallet signatures verified
- [ ] Transaction details validated
- [ ] Balance checks before transactions
- [ ] No blind transaction signing

### 10. Dependency Security

#### Regular Updates
```bash
# Check for vulnerabilities
npm audit

# Fix automatically fixable issues
npm audit fix

# Update dependencies
npm update

# Check for outdated packages
npm outdated
```

#### Lock Files
```bash
# ALWAYS commit lock files
git add package-lock.json

# Use in CI/CD for reproducible builds
npm ci  # Instead of npm install
```

#### Verification Steps
- [ ] Dependencies up to date
- [ ] No known vulnerabilities (npm audit clean)
- [ ] Lock files committed
- [ ] Dependabot enabled on GitHub
- [ ] Regular security updates

### 11. AI, Agent & MCP Security

*Chi tiết chuyên sâu xem tại [references/ai-and-llm-security.md](file:///d:/AntiGravity/Antigravity-Harness-HuB-main/plugins/code/skills/security-review/references/ai-and-llm-security.md)*

#### Tool-Argument Injection & Confused Deputy
```typescript
// FAIL: WRONG: Tin tưởng tham số từ model trực tiếp vào sink nhạy cảm
async function executeAgentTool(toolCall: { name: string, args: any }) {
  if (toolCall.name === 'run_query') {
    return await db.raw(toolCall.args.sql); // Lỗ hổng SQL Injection từ LLM
  }
}

// PASS: CORRECT: Luôn validate schema và kiểm tra authorization phía handler
async function executeAgentTool(toolCall: { name: string, args: any }, userContext: UserContext) {
  if (toolCall.name === 'run_query') {
    const validated = QueryArgsSchema.parse(toolCall.args);
    // Bắt buộc re-check quyền sở hữu tài nguyên của userContext
    await authorizeUserResource(userContext.id, validated.targetId);
    return await db.query(validated);
  }
}
```

#### Action-Binding & Confirmation
- [ ] Mọi hành động có tác dụng phụ (xóa dữ liệu, gửi tiền, thay đổi quyền, gửi email hàng loạt) phải ràng buộc chính xác intent/phê duyệt của người dùng với: tên công cụ, bộ tham số hoàn chỉnh, người thực hiện, tài nguyên mục tiêu và thời hạn hiệu lực.
- [ ] Model không được tự ý thực thi các side-effects nguy hiểm chỉ dựa vào prompt gợi ý gián tiếp (Indirect Prompt Injection).

#### MCP Server & Tool Trust
- [ ] Phản hồi từ MCP Server và mô tả tool phải được coi là dữ liệu đầu vào không tin cậy (untrusted input).
- [ ] Không cấp full session/credential cho các sub-agents hoặc MCP servers; áp dụng nguyên tắc đặc quyền tối thiểu (Least Privilege).
- [ ] Kiểm tra định danh server và tool namespace để ngăn chặn tool identity collision.

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
- [AI & LLM Security Reference](file:///d:/AntiGravity/Antigravity-Harness-HuB-main/plugins/code/skills/security-review/references/ai-and-llm-security.md)
- [Binary, Native & IPC Security Reference](file:///d:/AntiGravity/Antigravity-Harness-HuB-main/plugins/code/skills/security-review/references/binary-and-ipc.md)

---

**Remember**: Security is not optional. One vulnerability can compromise the entire platform. When in doubt, err on the side of caution.
