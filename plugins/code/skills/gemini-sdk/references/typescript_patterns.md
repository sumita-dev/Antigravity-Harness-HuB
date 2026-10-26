# Google GenAI TypeScript / Node.js Patterns (`@google/genai`)

Tài liệu này cung cấp các code mẫu sản xuất (production-ready) cho TypeScript và Node.js khi làm việc với thư viện hợp nhất chính thức `@google/genai`.

---

## 1. Cài Đặt & Khởi Tạo Client

```bash
npm install @google/genai
```

```typescript
import { GoogleGenAI } from '@google/genai';

// Khởi tạo mặc định - tự động nạp process.env.GEMINI_API_KEY
export const ai = new GoogleGenAI();

// Hoặc khởi tạo kèm cấu hình tường minh
export const customAi = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});
```

---

## 2. Text Generation & System Instruction

```typescript
import { ai } from './client';

export async function summarizeDoc(content: string): Promise<string> {
  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: `Tóm tắt nội dung sau thành 3 gạch đầu dòng:\n\n${content}`,
    config: {
      systemInstruction: 'Bạn là chuyên viên phân tích tài liệu kỹ thuật, trả lời súc tích và chính xác.',
      temperature: 0.2,
      maxOutputTokens: 600,
    },
  });

  return response.text ?? '';
}
```

---

## 3. Streaming Với Xử Lý Timeout & Hủy Yêu Cầu (AbortSignal)

```typescript
import { ai } from './client';

export async function streamResponseWithTimeout(
  prompt: string,
  onChunk: (text: string) => void,
  timeoutMs: number = 30000
): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const responseStream = await ai.models.generateContentStream({
      model: 'gemini-2.5-flash',
      contents: prompt,
      config: {
        temperature: 0.5,
        abortSignal: controller.signal,
      },
    });

    for await (const chunk of responseStream) {
      if (chunk.text) {
        onChunk(chunk.text);
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.error(`Request timed out after ${timeoutMs}ms`);
    } else {
      console.error('Streaming error:', error);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
```

---

## 4. Structured Outputs Với Type Schema & Zod

Kết hợp `Type` từ SDK và thư viện validation `zod` để bảo đảm type safety từ runtime đến compile time.

```typescript
import { GoogleGenAI, Type } from '@google/genai';
import { z } from 'zod';

const ai = new GoogleGenAI();

// 1. Zod Schema cho TypeScript Runtime Type-Safety
export const TestPlanSchema = z.object({
  feature: z.string(),
  priority: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
  testCases: z.array(
    z.object({
      id: z.string(),
      description: z.string(),
      expectedResult: z.string(),
    })
  ),
});

export type TestPlan = z.infer<typeof TestPlanSchema>;

// 2. Gọi API với Type Schema tương ứng
export async function generateTestPlan(featureDescription: string): Promise<TestPlan> {
  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: `Lập kế hoạch kiểm thử cho tính năng: ${featureDescription}`,
    config: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          feature: { type: Type.STRING },
          priority: {
            type: Type.STRING,
            enum: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
          },
          testCases: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                id: { type: Type.STRING },
                description: { type: Type.STRING },
                expectedResult: { type: Type.STRING },
              },
              required: ['id', 'description', 'expectedResult'],
            },
          },
        },
        required: ['feature', 'priority', 'testCases'],
      },
      temperature: 0.1,
    },
  });

  const rawJson = JSON.parse(response.text ?? '{}');
  // Validate dữ liệu runtime bằng Zod
  return TestPlanSchema.parse(rawJson);
}
```

---

## 5. Multimodal (Inline Image & Local File)

```typescript
import * as fs from 'fs';
import * as path from 'path';
import { ai } from './client';

export async function analyzeLocalImage(imagePath: string, question: string): Promise<string> {
  const fileBuffer = fs.readFileSync(imagePath);
  const ext = path.extname(imagePath).toLowerCase().replace('.', '');
  const mimeType = ext === 'png' ? 'image/png' : 'image/jpeg';

  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: [
      {
        inlineData: {
          data: fileBuffer.toString('base64'),
          mimeType: mimeType,
        },
      },
      question,
    ],
  });

  return response.text ?? '';
}
```

---

## 6. Function Calling (Tool Use Loop)

```typescript
import { GoogleGenAI, Type } from '@google/genai';

const ai = new GoogleGenAI();

// Khai báo tool declaration
const weatherTool = {
  functionDeclarations: [
    {
      name: 'get_current_weather',
      description: 'Lấy thông tin thời tiết hiện tại tại một địa điểm cụ thể.',
      parameters: {
        type: Type.OBJECT,
        properties: {
          location: { type: Type.STRING, description: 'Tên thành phố (ví dụ: Hanoi, Tokyo)' },
          unit: { type: Type.STRING, enum: ['celsius', 'fahrenheit'] },
        },
        required: ['location'],
      },
    },
  ],
};

// Hàm thực thi thực tế ở backend
async function executeWeatherTool(args: { location: string; unit?: string }) {
  // Giả lập kết quả trả về từ weather service
  return {
    location: args.location,
    temperature: 28,
    unit: args.unit || 'celsius',
    condition: 'Sunny',
  };
}

export async function askWithWeatherTool(userQuery: string): Promise<string> {
  // 1. Gửi truy vấn cùng định nghĩa Tools
  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: userQuery,
    config: {
      tools: [weatherTool],
      temperature: 0.1,
    },
  });

  // 2. Kiểm tra nếu Model yêu cầu gọi tool
  if (response.functionCalls && response.functionCalls.length > 0) {
    const call = response.functionCalls[0];
    console.log(`Model requests function call: ${call.name} with args:`, call.args);

    if (call.name === 'get_current_weather') {
      const toolOutput = await executeWeatherTool(call.args as any);

      // 3. Gửi lại kết quả thực thi cho Model
      const followUp = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: [
          {
            role: 'user',
            parts: [{ text: userQuery }],
          },
          {
            role: 'model',
            parts: [{ functionCall: call }],
          },
          {
            role: 'user',
            parts: [
              {
                functionResponse: {
                  name: 'get_current_weather',
                  response: toolOutput,
                },
              },
            ],
          },
        ],
      });

      return followUp.text ?? '';
    }
  }

  return response.text ?? '';
}
```

---

## 7. Multi-Turn Conversations (Chat)

```typescript
import { ai } from './client';

export async function runInteractiveChat() {
  const chat = ai.chats.create({
    model: 'gemini-2.5-flash',
    config: {
      systemInstruction: 'Bạn là chuyên gia tư vấn kiến trúc Cloud Native.',
    },
  });

  const reply1 = await chat.sendMessage({ message: 'Khi nào nên chọn Kubernetes thay vì Serverless?' });
  console.log('Turn 1:', reply1.text);

  const reply2 = await chat.sendMessage({ message: 'Nếu nhóm chỉ có 3 người thì sao?' });
  console.log('Turn 2:', reply2.text);

  const history = await chat.getHistory();
  console.log(`Total messages in history: ${history.length}`);
}
```
