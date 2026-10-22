"""Mode normalizer inherited only by Python child processes of the test runner."""
import os


def _normalize_mode(mode):
    return 0o777 if mode == 0o700 else mode


if os.name == "nt" and os.environ.get("PYTEST_WINDOWS_NORMALIZE_TEMP_MODE") == "1":
    _original_mkdir = os.mkdir

    def _normalized_mkdir(path, mode=0o777, *, dir_fd=None):
        mode = _normalize_mode(mode)
        if dir_fd is None:
            return _original_mkdir(path, mode)
        return _original_mkdir(path, mode, dir_fd=dir_fd)

    os.mkdir = _normalized_mkdir
