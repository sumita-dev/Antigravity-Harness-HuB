"""Cấu hình chung cho test suite.

Chuyển dữ liệu runtime (.brain) sang thư mục tạm để test KHÔNG bao giờ ghi
vào repo — tránh việc `pytest` làm bẩn trajectories/patterns đã commit.
"""

import os
import sys
import tempfile

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

os.environ.setdefault("HARNESS_BRAIN_DIR", tempfile.mkdtemp(prefix="harness-brain-"))
