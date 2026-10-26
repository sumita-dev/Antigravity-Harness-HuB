"""Feature List Validator Module (Harness 2.0).

Bọc logic kiểm tra hợp lệ của feature_list.json phục vụ các chốt chặn kiểm định.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from harness.feature_list import (
    CompletionEvidence,
    FakePassingError,
    FeatureItem,
    FeatureList,
    FeatureListValidationError,
    VCRMetrics,
    WIPViolationError,
)


class FeatureListValidator:
    """Validator kiểm toán tính toàn vẹn và các bất biến của Feature List."""

    @staticmethod
    def validate_file(path: Union[str, Path], check_manifest: bool = True) -> FeatureList:
        """Nạp file feature_list.json và kiểm tra 100% các điều kiện AC-FL-01..05."""
        target = Path(path).resolve()
        fl = FeatureList.load_from_file(target)
        manifest_root = target.parent if check_manifest else None
        fl.validate(check_manifest_against_path=manifest_root)
        return fl

    @staticmethod
    def validate_dict(data: Dict[str, Any], project_root: Optional[Path] = None) -> FeatureList:
        """Kiểm tra từ điển dữ liệu feature list."""
        fl = FeatureList.from_dict(data)
        fl.validate(check_manifest_against_path=project_root)
        return fl


__all__ = [
    "CompletionEvidence",
    "FakePassingError",
    "FeatureItem",
    "FeatureList",
    "FeatureListValidationError",
    "FeatureListValidator",
    "VCRMetrics",
    "WIPViolationError",
]
