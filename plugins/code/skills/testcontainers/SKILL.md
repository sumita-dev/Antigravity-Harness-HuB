---
name: testcontainers
description: "Ephemeral Database Sandbox & Testcontainers: Hướng dẫn tác tử cách sử dụng DatabaseSandbox khi build và test app backend/database migration."
---

# Ephemeral Database Sandbox (Pillar 5)

## Tổng Quan

Khi xây dựng ứng dụng backend, phát triển endpoint API hoặc thực hiện database migrations, việc kiểm thử trực tiếp trên database thật của môi trường dev/staging có thể gây ra rò rỉ dữ liệu hoặc sai lệch trạng thái (side effects).

Kỹ năng `testcontainers` tích hợp công cụ `DatabaseSandbox` từ `scripts/db_sandbox.py` giúp tác tử tạo môi trường database tạm thời (ephemeral sandbox), cô lập 100% dữ liệu kiểm thử và tự động dọn dẹp sạch sẽ sau khi test xong.

## Nguyên Tắc Vận Hành

1. **Auto Docker Detection:** Tự động phát hiện xem Docker daemon có đang khả dụng hay không.
2. **Postgres Ephemeral Container:** Nếu yêu cầu `db_type="postgres"` và Docker khả dụng, khởi chạy ephemeral container Postgres độc lập trên cổng tạm.
3. **Graceful Fallback:** Nếu KHÔNG có Docker hoặc khi yêu cầu `db_type="sqlite"`, tự động fallback sang SQLite file tạm hoặc `:memory:`, bảo đảm test suite không bao giờ bị nghẽn (zero block).
4. **Zero Residual Data:** Sử dụng pattern context manager (`with DatabaseSandbox() as db:`) để đảm bảo container được dọn dẹp và thư mục tạm bị xoá hoàn toàn sau khi kiểm thử kết thúc.

## Cách Sử Dụng

### 1. Trong Code Python hoặc Pytest Fixture

```python
from scripts.db_sandbox import DatabaseSandbox

# Sử dụng với context manager
with DatabaseSandbox(db_type="postgres") as db:
    connection_url = db.get_connection_url()
    print(f"Connecting to: {connection_url}")
    # Chạy migrations hoặc test queries tại đây
```

### 2. Pytest Fixture Mẫu

```python
import pytest
from scripts.db_sandbox import DatabaseSandbox

@pytest.fixture(scope="session")
def test_db():
    with DatabaseSandbox(db_type="postgres") as db:
        yield db.get_connection_url()
```

### 3. Kiểm Tra Thủ Công từ CLI

```bash
python scripts/db_sandbox.py
```
