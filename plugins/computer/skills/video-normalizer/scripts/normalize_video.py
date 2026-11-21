#!/usr/bin/env python3
"""Normalize 9:16 videos: remove bottom-right watermark via FFmpeg delogo and
rewrite stream + container metadata to match Google Pixel 4 XL specs.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
TARGET_4K_W = 2160
TARGET_4K_H = 3840
TARGET_1080_W = 1080
TARGET_1080_H = 1920


def ensure_binaries() -> None:
    """Verify ffmpeg and ffprobe are available on PATH."""
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"Không tìm thấy `{tool}` trong PATH.")


def probe_video(input_path: Path) -> dict[str, Any]:
    """Inspect video/audio streams via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    res = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(res.stdout)


def parse_fps(r_frame_rate: str) -> float:
    """Convert ffprobe fraction string (e.g. '30000/1001') to float."""
    if "/" in r_frame_rate:
        num_s, den_s = r_frame_rate.split("/", 1)
        den = float(den_s)
        return float(num_s) / den if den > 0 else 30.0
    return float(r_frame_rate)


def compute_delogo_rect(
    width: int,
    height: int,
    wm_rect: str | None,
    w_pct: float,
    h_pct: float,
    mr_pct: float,
    mb_pct: float,
) -> tuple[int, int, int, int]:
    """Compute and safely clamp delogo (x, y, w, h) inside [1, dim - 1]."""
    if wm_rect:
        parts = [int(p.strip()) for p in wm_rect.split(",")]
        if len(parts) != 4:
            raise ValueError("--wm-rect phải có đúng 4 số nguyên: x,y,w,h")
        x, y, w, h = parts
    else:
        w = max(8, int(round(width * w_pct)))
        h = max(8, int(round(height * h_pct)))
        mr = int(round(width * mr_pct))
        mb = int(round(height * mb_pct))
        x = width - w - mr
        y = height - h - mb

    # FFmpeg delogo requires box strictly inside [1, dim - 1]
    x = max(1, min(x, width - 3))
    y = max(1, min(y, height - 3))
    w = max(2, min(w, width - 1 - x))
    h = max(2, min(h, height - 1 - y))
    return x, y, w, h


def resolve_target_fps(src_fps: float, fps_opt: str) -> int:
    """Choose 30 or 60 fps matching Pixel 4 XL video modes."""
    if fps_opt in ("30", "60"):
        return int(fps_opt)
    return 60 if src_fps >= 50.0 else 30


def build_vf_chain(
    src_w: int,
    src_h: int,
    target_w: int,
    target_h: int,
    delogo_rect: tuple[int, int, int, int] | None,
    preview_box: bool = False,
) -> str:
    """Build FFmpeg video filter chain."""
    filters: list[str] = []
    if src_w != target_w or src_h != target_h:
        filters.append(
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={target_w}:{target_h}"
        )
    if delogo_rect is not None:
        x, y, w, h = delogo_rect
        if preview_box:
            filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red@0.85:t=4")
        else:
            filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}:show=0")
    return ",".join(filters) if filters else "null"


def format_creation_time(base_dt: datetime | None, offset_minutes: int) -> str:
    """Format UTC ISO 8601 timestamp for MP4 creation_time."""
    dt = base_dt or datetime.now(timezone.utc)
    if offset_minutes:
        dt = dt - timedelta(minutes=offset_minutes)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def process_single_video(
    input_path: Path,
    output_path: Path,
    args: argparse.Namespace,
    offset_minutes: int = 0,
) -> None:
    """Normalize one video file or render a delogo preview box frame."""
    info = probe_video(input_path)
    streams = info.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if v_stream is None:
        raise RuntimeError(f"Không tìm thấy video stream trong: {input_path}")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    src_w = int(v_stream["width"])
    src_h = int(v_stream["height"])
    src_fps = parse_fps(v_stream.get("r_frame_rate", "30/1"))

    if args.scale_1080p:
        out_w, out_h = TARGET_1080_W, TARGET_1080_H
    elif args.keep_resolution:
        out_w, out_h = src_w, src_h
    else:
        out_w, out_h = TARGET_4K_W, TARGET_4K_H
    out_fps = resolve_target_fps(src_fps, args.fps)
    h264_level = "5.1" if max(out_w, out_h) > 1920 else "4.1"

    delogo_rect = None
    if not args.no_delogo:
        delogo_rect = compute_delogo_rect(
            out_w,
            out_h,
            args.wm_rect,
            args.wm_w_pct,
            args.wm_h_pct,
            args.wm_mr_pct,
            args.wm_mb_pct,
        )

    if args.preview_box:
        vf_chain = build_vf_chain(
            src_w, src_h, out_w, out_h, delogo_rect, preview_box=True
        )
        preview_out = Path(args.preview_box)
        preview_out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            "0.5",
            "-i",
            str(input_path),
            "-vf",
            vf_chain,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(preview_out),
        ]
        subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        print(f"[PREVIEW] Đã xuất khung kiểm tra delogo ({delogo_rect}) -> {preview_out}")
        return

    vf_chain = build_vf_chain(
        src_w, src_h, out_w, out_h, delogo_rect, preview_box=False
    )
    base_dt = (
        datetime.fromisoformat(args.creation_time.replace("Z", "+00:00"))
        if args.creation_time
        else None
    )
    creation_iso = format_creation_time(base_dt, offset_minutes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
    ]
    if has_audio:
        cmd.extend(["-map", "0:a:0"])

    cmd.extend(
        [
            "-vf",
            vf_chain,
            "-r",
            str(out_fps),
            "-c:v",
            "libx264",
            "-profile:v",
            "high",
            "-level:v",
            h264_level,
            "-crf",
            str(args.crf),
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
        ]
    )

    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"])

    cmd.extend(
        [
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-fflags",
            "+bitexact",
            "-movflags",
            "+faststart+use_metadata_tags",
            "-brand",
            "mp42",
            "-metadata",
            "com.android.manufacturer=Google",
            "-metadata",
            "com.android.model=Pixel 4 XL",
            "-metadata",
            f"com.android.version={args.android_version}",
            "-metadata",
            f"com.android.capture.fps={out_fps}.000000",
            "-metadata",
            "make=Google",
            "-metadata",
            "model=Pixel 4 XL",
            "-metadata",
            f"creation_time={creation_iso}",
            "-metadata:s:v:0",
            "handler_name=VideoHandle",
        ]
    )

    if has_audio:
        cmd.extend(["-metadata:s:a:0", "handler_name=SoundHandle"])

    if args.location:
        cmd.extend(["-metadata", f"location={args.location}"])
        cmd.extend(["-metadata", f"location-eng={args.location}"])

    cmd.append(str(output_path))

    res = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg lỗi khi xử lý {input_path.name}:\n{res.stderr}")

    print(
        f"[OK] {input_path.name} -> {output_path} "
        f"({out_w}x{out_h}@{out_fps}fps, delogo={delogo_rect}, Pixel 4 XL)"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chuẩn hóa video 9:16: xóa watermark góc dưới phải + metadata Google Pixel 4 XL."
    )
    parser.add_argument("-i", "--input", required=True, help="File video hoặc thư mục nguồn.")
    parser.add_argument("-o", "--output", help="File xuất hoặc thư mục xuất.")
    parser.add_argument("--wm-rect", help="Tọa độ cố định x,y,w,h (ví dụ: 780,1750,275,130).")
    parser.add_argument("--wm-w-pct", type=float, default=0.26, help="Tỷ lệ rộng watermark (mặc định 0.26).")
    parser.add_argument("--wm-h-pct", type=float, default=0.07, help="Tỷ lệ cao watermark (mặc định 0.07).")
    parser.add_argument("--wm-mr-pct", type=float, default=0.02, help="Lề phải theo tỷ lệ (mặc định 0.02).")
    parser.add_argument("--wm-mb-pct", type=float, default=0.02, help="Lề dưới theo tỷ lệ (mặc định 0.02).")
    parser.add_argument("--no-delogo", action="store_true", help="Bỏ qua xóa watermark.")
    parser.add_argument("--fps", choices=["auto", "30", "60"], default="auto", help="FPS đầu ra.")
    parser.add_argument("--crf", type=int, default=14, help="Chất lượng H.264 CRF (mặc định 14).")
    res_group = parser.add_mutually_exclusive_group()
    res_group.add_argument("--scale-1080p", action="store_true", help="Hạ/ép độ phân giải về 1080x1920 (mặc định luôn xuất 4K 2160x3840).")
    res_group.add_argument("--keep-resolution", action="store_true", help="Giữ nguyên độ phân giải gốc thay vì ép 4K 2160x3840.")
    parser.add_argument("--android-version", default="13", help="Phiên bản Android (mặc định 13).")
    parser.add_argument("--creation-time", help="ISO 8601 UTC (vd: 2026-11-17T09:15:00Z).")
    parser.add_argument("--location", help="Tọa độ GPS ISO 6709 (vd: +10.7769+106.7009/).")
    parser.add_argument("--preview-box", help="Xuất 1 ảnh .jpg vẽ khung đỏ delogo để kiểm tra.")
    return parser.parse_args()


def main() -> int:
    ensure_binaries()
    args = parse_args()
    in_path = Path(args.input).resolve()

    if not in_path.exists():
        print(f"[ERR] Không tồn tại đường dẫn: {in_path}", file=sys.stderr)
        return 1

    if in_path.is_file():
        out_path = (
            Path(args.output).resolve()
            if args.output
            else in_path.with_name(f"{in_path.stem}_pixel4xl.mp4")
        )
        process_single_video(in_path, out_path, args)
        return 0

    videos = sorted(
        p for p in in_path.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        print(f"[WARN] Không tìm thấy file video nào trong: {in_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.output).resolve() if args.output else (in_path / "normalized")
    if args.preview_box:
        process_single_video(videos[0], out_dir / videos[0].name, args)
        return 0

    for idx, vid in enumerate(videos):
        offset = 0 if args.creation_time else (idx * 7 + random.randint(0, 5))
        out_file = out_dir / f"{vid.stem}_pixel4xl.mp4"
        process_single_video(vid, out_file, args, offset_minutes=offset)

    print(f"[DONE] Đã chuẩn hóa {len(videos)}/{len(videos)} video -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
