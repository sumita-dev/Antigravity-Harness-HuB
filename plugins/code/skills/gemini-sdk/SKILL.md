---
name: gemini-sdk
description: "Chuẩn hóa lập trình Google GenAI SDK (google-genai cho Python và @google/genai cho TypeScript). Hướng dẫn Builder cấu hình client, gọi model, structured JSON schema, function calling và multimodal không dùng thư viện cũ."
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
