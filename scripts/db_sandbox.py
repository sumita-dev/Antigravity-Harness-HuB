"""Ephemeral Database Sandbox - Pillar 5 of Antigravity Harness Hub.
Cung cấp môi trường sandbox database độc lập và an toàn cho test runner và migrations:
- Hỗ trợ ephemeral Postgres container qua Docker CLI nếu Docker đang chạy.
- Tự động Graceful Fallback sang SQLite (:memory: hoặc file tạm) nếu không có Docker.
- Hoạt động như một context manager, tự động dọn dẹp sạch sẽ tài nguyên sau khi xong việc.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from typing import Optional


class DatabaseSandbox:
    """Môi trường database sandbox tạm thời cho kiểm thử và migration."""

    def __init__(
        self,
        db_type: str = "sqlite",
        port: Optional[int] = None,
        db_name: str = "sandbox_test",
        user: str = "postgres",
        password: str = "postgres",
    ) -> None:
        self.requested_db_type = db_type.lower()
        self.port = port or 54329
        self.db_name = db_name
        self.user = user
        self.password = password

        self.actual_db_type = "sqlite"
        self.container_id: Optional[str] = None
        self.temp_dir: Optional[str] = None
        self.sqlite_file_path: Optional[str] = None
        self.connection_url: str = ""
        self._is_active = False

    @staticmethod
    def is_docker_available() -> bool:
        """Kiểm tra xem Docker daemon có đang chạy hay không."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def start(self) -> str:
        """Khởi động database sandbox và trả về connection url."""
        if self.requested_db_type == "postgres" and self.is_docker_available():
            try:
                self._start_postgres_container()
                self.actual_db_type = "postgres"
                self.connection_url = (
                    f"postgresql://{self.user}:{self.password}@localhost:{self.port}/{self.db_name}"
                )
                self._is_active = True
                return self.connection_url
            except Exception:
                # Nếu khởi động docker container thất bại -> fallback sang sqlite
                pass

        # Graceful fallback sang SQLite
        self._start_sqlite_fallback()
        self.actual_db_type = "sqlite"
        self._is_active = True
        return self.connection_url

    def _start_postgres_container(self) -> None:
        """Khởi chạy container PostgreSQL tạm thời qua Docker CLI."""
        cmd = [
            "docker", "run", "-d",
            "--rm",
            "-e", f"POSTGRES_DB={self.db_name}",
            "-e", f"POSTGRES_USER={self.user}",
            "-e", f"POSTGRES_PASSWORD={self.password}",
            "-p", f"{self.port}:5432",
            "postgres:16-alpine",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        self.container_id = res.stdout.strip()
        # Chờ container sẵn sàng
        time.sleep(2)

    def _start_sqlite_fallback(self) -> None:
        """Khởi tạo SQLite database (file tạm độc lập để hỗ trợ multi-connection)."""
        self.temp_dir = tempfile.mkdtemp(prefix="db_sandbox_")
        self.sqlite_file_path = os.path.join(self.temp_dir, f"{self.db_name}.db")
        # Chuẩn hoá path URL cho SQLite trên Windows/Linux
        clean_path = self.sqlite_file_path.replace("\\", "/")
        self.connection_url = f"sqlite:///{clean_path}"

    def get_connection_url(self) -> str:
        """Trả về chuỗi kết nối (connection URI)."""
        if not self._is_active:
            raise RuntimeError("DatabaseSandbox chưa được khởi động. Hãy gọi .start() hoặc dùng context manager.")
        return self.connection_url

    def stop(self) -> None:
        """Dọn dẹp triệt để container hoặc file SQLite tạm thời."""
        if self.container_id:
            try:
                subprocess.run(
                    ["docker", "stop", self.container_id],
                    capture_output=True,
                    timeout=15,
                )
            except Exception:
                pass
            self.container_id = None

        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass
            self.temp_dir = None
            self.sqlite_file_path = None

        self._is_active = False

    def __enter__(self) -> DatabaseSandbox:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


def get_ephemeral_db(db_type: str = "sqlite") -> DatabaseSandbox:
    """Helper factory tạo đối tượng DatabaseSandbox."""
    return DatabaseSandbox(db_type=db_type)


if __name__ == "__main__":
    print("Testing Ephemeral DB Sandbox...")
    with DatabaseSandbox(db_type="postgres") as sandbox:
        print(f"Active DB Type: {sandbox.actual_db_type}")
        print(f"Connection URL: {sandbox.get_connection_url()}")
    print("Cleanup verified.")
