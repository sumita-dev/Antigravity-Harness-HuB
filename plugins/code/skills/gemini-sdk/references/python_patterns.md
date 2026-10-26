# Google GenAI Python Patterns (`google-genai`)

Tài liệu này cung cấp các code mẫu sản xuất (production-ready) cho Python khi làm việc với thư viện hợp nhất chính thức `google-genai`.

---

## 1. Khởi Tạo Client & Biến Môi Trường

```python
import os
from google import genai
from google.genai import types

# Tự động đọc biến môi trường GEMINI_API_KEY
client = genai.Client()

# Hoặc khởi tạo tường minh với api_key và options
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1alpha"}  # khi cần tính năng preview cụ thể
)
```

---

## 2. Bất Đồng Bộ (Async / `client.aio`)

SDK hỗ trợ interface `client.aio` dành cho các framework bất đồng bộ như FastAPI, asyncio, hoặc Celery.

```python
import asyncio
from google import genai
from google.genai import types

async def generate_async_example():
    client = genai.Client()
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents="Liệt kê 3 lợi ích của kiến trúc Event-Driven.",
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=500,
        ),
    )
    print("Async response:")
    print(response.text)

async def stream_async_example():
    client = genai.Client()
    
    response_stream = await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents="Viết hàm tính Fibonacci bằng Python.",
    )
    
    print("Streaming chunks:")
    async for chunk in response_stream:
        if chunk.text:
            print(chunk.text, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(generate_async_example())
    asyncio.run(stream_async_example())
```

---

## 3. Xử Lý Lỗi & Cơ Chế Retry / Backoff

```python
import time
import logging
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

def generate_with_retry(
    prompt: str,
    model: str = "gemini-2.5-flash",
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> str:
    """Gọi Gemini API với cơ chế Exponential Backoff khi gặp lỗi mạng hoặc rate-limit."""
    client = genai.Client()
    delay = initial_delay

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            if response.text is None:
                raise ValueError("Model returned empty text response.")
            return response.text

        except APIError as exc:
            # 429 = Rate limit / ResourceExhausted, 503 = Service Unavailable
            logger.warning(
                "Attempt %d/%d failed with APIError (code=%s): %s",
                attempt,
                max_retries,
                getattr(exc, "code", "UNKNOWN"),
                exc.message,
            )
            if attempt == max_retries:
                raise

        except Exception as exc:
            logger.error("Unexpected error on attempt %d: %s", attempt, exc)
            if attempt == max_retries:
                raise

        time.sleep(delay)
        delay *= 2.0  # Exponential backoff

    raise RuntimeError("Failed to generate content after max retries.")
```

---

## 4. Structured Outputs Với Pydantic

Ép model trả về kết quả tuân thủ nghiêm ngặt Schema của Pydantic `BaseModel`.

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class VulnerabilityItem(BaseModel):
    cve_id: Optional[str] = Field(None, description="Mã CVE nếu có")
    severity: str = Field(description="Mức độ: LOW, MEDIUM, HIGH, CRITICAL")
    description: str = Field(description="Mô tả lỗ hổng")
    remediation: str = Field(description="Giải pháp khắc phục")

class SecurityAuditReport(BaseModel):
    repository_name: str = Field(description="Tên repo được quét")
    overall_risk: str = Field(description="Đánh giá tổng quan: SAFE, WARNING, DANGER")
    vulnerabilities: List[VulnerabilityItem] = Field(
        default_factory=list, description="Danh sách các phát hiện"
    )

def audit_code_security(code_snippet: str) -> SecurityAuditReport:
    client = genai.Client()

    prompt = f"Phân tích bảo mật cho đoạn code sau và báo cáo theo schema:\n\n```python\n{code_snippet}\n```"

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SecurityAuditReport,
            temperature=0.0,
        ),
    )

    # Validate và deserialize dữ liệu
    return SecurityAuditReport.model_validate_json(response.text)
```

---

## 5. Multimodal & Files API (Audio, Video, PDF lớn)

Đối với file > 20MB hoặc tệp video/âm thanh dài, sử dụng File API thay vì inline bytes.

```python
from google import genai
from google.genai import types

client = genai.Client()

# 1. Upload file lên Gemini Storage
uploaded_file = client.files.upload(
    file="path/to/annual_report.pdf",
    config={"display_name": "Annual Financial Report 2025"}
)

print(f"File uploaded. Name: {uploaded_file.name}, URI: {uploaded_file.uri}")

# 2. Truy vấn nội dung tài liệu
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        uploaded_file,
        "Trích xuất tổng doanh thu quý 4 và tỷ suất lợi nhuận ròng từ báo cáo này.",
    ],
    config=types.GenerateContentConfig(temperature=0.1),
)

print(response.text)

# 3. Dọn dẹp file khi không dùng nữa (nếu cần bảo mật)
client.files.delete(name=uploaded_file.name)
```

---

## 6. Multi-turn Chat với Session

```python
from google import genai
from google.genai import types

client = genai.Client()

chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction="Bạn là trợ lý giải thích kiến trúc phần mềm trực quan.",
    )
)

response1 = chat.send_message("REST API là gì?")
print("AI:", response1.text)

response2 = chat.send_message("Nó khác với gRPC ở những điểm cốt lõi nào?")
print("AI:", response2.text)

# Xem lịch sử trò chuyện
for msg in chat.get_history():
    print(f"[{msg.role}]: {msg.parts[0].text if msg.parts else ''}")
```

---

## 7. Function Calling (Tool Calling Loop)

```python
from google import genai
from google.genai import types

def get_exchange_rate(from_currency: str, to_currency: str) -> dict:
    """Lấy tỷ giá hối đoái hiện tại giữa 2 đơn vị tiền tệ."""
    # Giả lập tỷ giá
    rates = {("USD", "VND"): 25400.0, ("EUR", "VND"): 27500.0}
    rate = rates.get((from_currency.upper(), to_currency.upper()), 1.0)
    return {"from": from_currency, "to": to_currency, "rate": rate}

client = genai.Client()

# Đăng ký hàm trực tiếp qua config.tools
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="100 USD quy đổi ra bao nhiêu VND hôm nay?",
    config=types.GenerateContentConfig(
        tools=[get_exchange_rate],
        temperature=0.1,
    ),
)

# Kiểm tra nếu model yêu cầu gọi function
if response.function_calls:
    for call in response.function_calls:
        print(f"Model muốn gọi tool: {call.name} với args: {call.args}")
        if call.name == "get_exchange_rate":
            args = call.args
            tool_result = get_exchange_rate(
                from_currency=args["from_currency"],
                to_currency=args["to_currency"],
            )
            
            # Gửi kết quả tool ngược lại cho model để sinh câu trả lời cuối
            follow_up = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_function_response(
                        name="get_exchange_rate",
                        response={"result": tool_result},
                    )
                ],
            )
            print("Final Answer:", follow_up.text)
else:
    print(response.text)
```
