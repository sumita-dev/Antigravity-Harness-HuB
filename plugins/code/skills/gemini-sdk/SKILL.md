---
name: gemini-sdk
description: "Chuẩn hóa lập trình Google GenAI SDK (google-genai cho Python và @google/genai cho TypeScript) cùng framework Google ADK. Hướng dẫn Builder cấu hình client, gọi model, structured JSON schema, function calling, multimodal, WorkflowAgent và Agentic Evals."
---

# Google GenAI SDK Standardization Guide

## 1. Nguyên Tắc Bất Biến (Strict Invariants)

> [!CAUTION]
> **CẤM TUYỆT ĐỐI** sử dụng các thư viện SDK cũ đã bị Google đánh dấu deprecated:
> - ❌ Python: `google-generativeai`
> - ❌ JavaScript / TypeScript: `@google/generative-ai`

Mọi mã nguồn phát triển mới hoặc nâng cấp trong hệ thống **BẮT BUỘC** sử dụng **Google GenAI SDK thế hệ mới (Unified SDK)**:
- ✅ **Python:** Package `google-genai` (`from google import genai`, `from google.genai import types`)
- ✅ **TypeScript / Node.js:** Package `@google/genai` (`import { GoogleGenAI } from '@google/genai'`)

---

## 2. Quy Chuẩn Model Routing

Khi cấu hình model trong mã nguồn, Builder tuân thủ quy tắc định tuyến:

| Tác Vụ | Khuyến Nghị Model | Đặc Tính |
| :--- | :--- | :--- |
| **Tác vụ nhanh / Real-time / Chi phí thấp** | `gemini-2.5-flash` | Tốc độ cực nhanh, context window lớn, chi phí tối ưu, mặc định cho hầu hết task sinh văn bản, trích xuất dữ liệu, tóm tắt. |
| **Lý luận sâu / Coding phức tạp / Kiến trúc** | `gemini-2.5-pro` | Năng lực reasoning đa bước, phân tích codebase lớn, giải quyết vấn đề thuật toán và logic phức tạp. |
| **Next-Gen Reasoning / Preview Features** | `gemini-3-flash-preview` | Khả năng suy luận thế hệ mới với độ trễ thấp khi cần benchmark tính năng tiên tiến. |

---

## 3. Khởi Tạo Client Chuẩn

SDK tự động nhận diện biến môi trường `GEMINI_API_KEY` (hoặc cấu hình thông qua tham số). Không hardcode API key vào mã nguồn.

### Python
```python
from google import genai
from google.genai import types

# Tự động đọc GEMINI_API_KEY từ os.environ
client = genai.Client()

# Hoặc truyền key rõ ràng nếu lấy từ config/vault
# client = genai.Client(api_key=custom_api_key)
```

### TypeScript
```typescript
import { GoogleGenAI } from '@google/genai';

// Tự động đọc process.env.GEMINI_API_KEY
const ai = new GoogleGenAI();

// Hoặc truyền qua options
// const ai = new GoogleGenAI({ apiKey: customApiKey });
```

---

## 4. Bốn Mẫu Cốt Lõi (4 Core Patterns)

### Mẫu 1: Text & Multimodal Generation
Hỗ trợ văn bản thuần, hình ảnh (local bytes hoặc File API), tài liệu PDF và âm thanh.

- **Python:**
```python
# Text
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Giải thích kiến trúc Microservices trong 2 câu.",
)
print(response.text)

# Multimodal (bytes/file)
with open("diagram.png", "rb") as f:
    image_bytes = f.read()

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        "Phân tích sơ đồ kiến trúc này.",
    ],
)
```

- **TypeScript:**
```typescript
import * as fs from 'fs';

// Text
const response = await ai.models.generateContent({
  model: 'gemini-2.5-flash',
  contents: 'Giải thích kiến trúc Microservices trong 2 câu.',
});
console.log(response.text);

// Multimodal inline buffer
const imageBuffer = fs.readFileSync('diagram.png');
const responseImg = await ai.models.generateContent({
  model: 'gemini-2.5-flash',
  contents: [
    {
      inlineData: {
        data: imageBuffer.toString('base64'),
        mimeType: 'image/png',
      },
    },
    'Phân tích sơ đồ kiến trúc này.',
  ],
});
```

---

### Mẫu 2: Structured Outputs (Pydantic / Type Schema)
Ép kiểu đầu ra chuẩn JSON tuân theo schema chặt chẽ, loại bỏ hoàn toàn hiện tượng parse JSON thất bại.

- **Python (Pydantic):**
```python
from pydantic import BaseModel, Field

class CodeReviewResult(BaseModel):
    summary: str = Field(description="Tóm tắt kết quả review")
    score: int = Field(ge=0, le=100, description="Điểm số từ 0 đến 100")
    issues: list[str] = Field(default_factory=list, description="Danh sách các vấn đề")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Review đoạn code sau...",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CodeReviewResult,
        temperature=0.1,
    ),
)

# Kết quả đã được parse hoặc trả về chuỗi JSON chuẩn
review: CodeReviewResult = CodeReviewResult.model_validate_json(response.text)
```

- **TypeScript (Schema Definition):**
```typescript
import { Type } from '@google/genai';

const response = await ai.models.generateContent({
  model: 'gemini-2.5-flash',
  contents: 'Review đoạn code sau...',
  config: {
    responseMimeType: 'application/json',
    responseSchema: {
      type: Type.OBJECT,
      properties: {
        summary: { type: Type.STRING },
        score: { type: Type.INTEGER },
        issues: {
          type: Type.ARRAY,
          items: { type: Type.STRING },
        },
      },
      required: ['summary', 'score', 'issues'],
    },
    temperature: 0.1,
  },
});

const data = JSON.parse(response.text ?? '{}');
```

---

### Mẫu 3: System Instructions & Streaming
Định hình tính cách/quy tắc vận hành cho model và tối ưu trải nghiệm phản hồi bằng luồng stream.

- **Python:**
```python
response_stream = client.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents="Viết 3 nguyên tắc clean code.",
    config=types.GenerateContentConfig(
        system_instruction="Bạn là Senior Tech Lead khó tính, trả lời súc tích và thực tế.",
        temperature=0.3,
    ),
)

for chunk in response_stream:
    if chunk.text:
        print(chunk.text, end="", flush=True)
```

- **TypeScript:**
```typescript
const stream = await ai.models.generateContentStream({
  model: 'gemini-2.5-flash',
  contents: 'Viết 3 nguyên tắc clean code.',
  config: {
    systemInstruction: 'Bạn là Senior Tech Lead khó tính, trả lời súc tích và thực tế.',
    temperature: 0.3,
  },
});

for await (const chunk of stream) {
  process.stdout.write(chunk.text ?? '');
}
```

---

### Mẫu 4: Function Calling (Tool Use)
Đăng ký hàm để model quyết định khi nào cần gọi tool thực thi.

- **Python:**
```python
def check_order_status(order_id: str) -> dict:
    """Tra cứu trạng thái đơn hàng theo mã đơn."""
    return {"order_id": order_id, "status": "SHIPPED", "carrier": "VNPost"}

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Kiểm tra trạng thái đơn hàng ORD-9988 giúp tôi.",
    config=types.GenerateContentConfig(
        tools=[check_order_status],
    ),
)

# Kiểm tra lời gọi hàm
for call in response.function_calls:
    print(f"Tool name: {call.name}")
    print(f"Arguments: {call.args}")
```

- **TypeScript:**
```typescript
import { Type } from '@google/genai';

const response = await ai.models.generateContent({
  model: 'gemini-2.5-flash',
  contents: 'Kiểm tra trạng thái đơn hàng ORD-9988 giúp tôi.',
  config: {
    tools: [
      {
        functionDeclarations: [
          {
            name: 'check_order_status',
            description: 'Tra cứu trạng thái đơn hàng theo mã đơn.',
            parameters: {
              type: Type.OBJECT,
              properties: {
                order_id: { type: Type.STRING, description: 'Mã đơn hàng' },
              },
              required: ['order_id'],
            },
          },
        ],
      },
    ],
  },
});

if (response.functionCalls && response.functionCalls.length > 0) {
  for (const call of response.functionCalls) {
    console.log(`Tool: ${call.name}, args:`, call.args);
  }
}
```

---

## 5. Tài Liệu Tham Chiếu Chi Tiết (Deep References)

Để xem code mẫu production hoàn chỉnh, xử lý lỗi API (`APIError`, rate limit), async client (`client.aio`), upload tệp dung lượng lớn (Files API) và tích hợp Zod:

- 📖 **Python Patterns:** [`references/python_patterns.md`](./references/python_patterns.md)
  - Async API (`client.aio`)
  - Error Handling & Backoff Retry
  - File Upload API (`client.files.upload`)
  - Multi-turn Chat với ChatSession
- 📖 **TypeScript Patterns:** [`references/typescript_patterns.md`](./references/typescript_patterns.md)
  - TypeScript Interfaces & Zod validation
  - Async Streaming Pipeline & AbortSignal
  - Error Handling & Rate Limiting
  - Multi-turn Conversations

---

## 6. Xử Lý Lỗi, Retry & Production Checklist

Trong môi trường production, mọi lệnh gọi qua Google GenAI SDK cần tuân thủ các chốt chặn:
- **Exponential Backoff:** Bắt lỗi `APIError` và tự động retry với khoảng chờ tăng dần khi gặp mã HTTP 429 (`ResourceExhausted`) hoặc 503 (`Unavailable`).
- **Sanitization & Redaction:** Không ghi log API keys hoặc token người dùng ra terminal hay file log.
- **Async Execution:** Sử dụng client async (`client.aio`) cho các tác vụ I/O song song để tránh block luồng chính.
- **Deterministic Validation:** Luôn kiểm tra tính hợp lệ của schema bằng Pydantic hoặc Zod trước khi đưa vào các bước xử lý nghiệp vụ tiếp theo.

---

## 7. Xây Dựng Multi-Agent Với Google ADK (Agent Development Kit)

### 7.1. Định Vị Google ADK Trong Hệ Sinh Thái GenAI
`google-adk` (Agent Development Kit) là framework chính thức từ Google, thiết kế đi kèm đồng bộ với `google-genai` SDK để chuẩn hóa phát triển, điều phối và kiểm định các hệ thống AI Agents:
- **Hạ tầng thực thi chuẩn hóa:** Cung cấp cơ chế thực thi bất đồng bộ (`Runner.run_async`), lưu trữ phiên (`SessionService`) và kiểm định hành vi (`AgentEvaluator`).
- **Cơ chế Zero-Bloat:** Được tích hợp theo mô hình Lazy Import (chỉ nạp khi chạy Live Mode hoặc Evals), đảm bảo không làm chậm tốc độ khởi động của hệ thống cốt lõi.

### 7.2. Quy Chuẩn Kiến Trúc: Phân Định Tác Tử Ngẫu Nhiên vs Tất Định
ADK phân định rõ 2 phân lớp tác tử:
1. **LLM Agent (`adk.Agent` / Reasoning Node):**
   - Vận hành dựa trên mô hình suy luận ngôn ngữ tự nhiên (Stochastic / Probabilistic).
   - Thích hợp cho các nhiệm vụ sáng tạo, phân tích ý định, bóc tách thông tin hoặc tổng hợp ngữ cảnh.
   - Luôn kèm theo `system_instruction` chặt chẽ và danh mục công cụ (`tools`).
2. **Workflow Agents (`WorkflowAgent` / Deterministic Orchestrators):**
   - Vận hành dựa trên luồng điều phối lập trình tất định (Deterministic), loại bỏ sự mơ hồ trong giao tiếp giữa các tác tử:
     - `SequentialAgent`: Chuỗi thực thi tuyến tính (A -> B -> C), dữ liệu đầu ra của bước trước trở thành đầu vào bước sau (áp dụng cho Pipeline Content / Marketing).
     - `ParallelAgent`: Fan-out thực thi song song nhiều tác tử độc lập và tổng hợp kết quả (áp dụng cho Multi-Solution Arena, đa kênh trinh sát).
     - `LoopAgent`: Chu trình lặp có điều kiện dừng hoặc số vòng tối đa (áp dụng cho Dynamic Triad Maker - Critic).

### 7.3. Khởi Tạo Agent, Tool Call & Kết Nối Session Service
```python
from google import genai
from google.genai import types

# Optional / Lazy-loaded ADK imports
try:
    from google.adk.agents import Agent, SequentialAgent
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner
except ImportError:
    pass

# 1. Khai báo công cụ (Tool Call)
def search_market_intel(query: str) -> dict:
    """Truy vấn dữ liệu thị trường và nguồn tin."""
    return {"query": query, "sources": ["https://example.com/report-2026"]}

# 2. Khởi tạo LLM Agent với System Instruction & Tools
researcher = Agent(
    name="WebResearcher",
    model="gemini-2.5-flash",
    instruction="Bạn là Web Researcher. Thu thập dữ liệu thực tế và trích dẫn URL chính xác.",
    tools=[search_market_intel],
)

creator = Agent(
    name="ContentCreator",
    model="gemini-2.5-pro",
    instruction="Bạn là Creator. Dựa trên dữ liệu từ Researcher để viết bài.",
)

# 3. Kết nối WorkflowAgent tất định (Sequential Pipeline)
pipeline = SequentialAgent(
    name="MarketingPipeline",
    sub_agents=[researcher, creator],
)

# 4. Quản lý phiên với Session Service và thực thi qua Runner
session_service = InMemorySessionService()
# runner = Runner(agent=pipeline, session_service=session_service)
```

### 7.4. Kiểm Định Hành Vi Tác Tử (Agentic Evals Với AgentEvaluator)
Đánh giá độ chính xác và an toàn của tác tử một cách định lượng bằng `google.adk.evaluation.AgentEvaluator`:
- **Trajectory Evaluator:** Kiểm tra thứ tự gọi tool, tính hợp lệ của tham số và chuỗi hành động của agent so với trajectory chuẩn (Golden Trajectory).
- **Fact Grounding Evaluator:** Đo lường tỷ lệ thông tin được đối soát từ Dossier / Nguồn dữ liệu, phát hiện và chấm dứt ảo giác (Hallucination).
- **Policy Safety Evaluator:** Quét cụm từ cấm (Red-flag phrases: "should work", "probably", "chắc là") và vi phạm chính sách bảo mật / đạo đức.

```python
from harness.eval import AgentEvaluatorBridge, TrajectoryEvaluator, FactGroundingEvaluator

evaluator = AgentEvaluatorBridge()
result = evaluator.evaluate(
    task_id="task-marketing-01",
    trajectory=recorded_trajectory,
    evalset_path="tests/evals/test_marketing_triad.evalset.json",
)
print(f"Eval Verdict: {result.verdict}, Score: {result.score:.2f}")
```

### 7.5. Trực Quan Hóa & Debug Trực Tiếp (Visual Dashboard & CLI Live Running)
- **Visual Web Dashboard (`adk web`):**
  Cung cấp giao diện trực quan thời gian thực để inspect luồng gọi agent, độ trễ từng bước, payload công cụ và cây phân nhánh mà không cần đọc log JSON dài dòng:
  ```powershell
  # Kiểm tra hoặc khởi động standalone visual dashboard
  python run_harness.py --visual --port 8000
  ```
- **CLI Live Running (`--live`):**
  Kích hoạt chế độ thực thi headless tự động thật qua `ADKLiveRunner`:
  ```powershell
  # Chạy pipeline thật và quan sát tiến trình
  python run_harness.py --task "Quét tin tức AI và viết bài tóm tắt" --branch marketing --live
  ```
- **Process Lifecycle Guard:**
  Mọi tiến trình dashboard và server background của ADK đều được quản lý với port check an toàn và cơ chế tự động dọn dẹp (`cleanup_dashboard_process`), triệt tiêu hoàn toàn tiến trình mồ côi (Zero Orphan Process).
