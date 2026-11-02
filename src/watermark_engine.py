"""
Account Watermark & Brand Logo Engine for VedioHooks AI Media Factory.
Protects content from repost theft by burning dynamic, semi-transparent
account handle pills and brand badges into 9:16 vertical shorts.
"""

import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from src.hardware_accel import get_ffmpeg_encoding_args


def find_system_font() -> Optional[str]:
    """Finds a robust system font (Windows, Linux, or macOS)."""
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def build_watermark_drawtext_filter(
    handle: str = "@vediohooks",
    position: str = "top_right",
    opacity: float = 0.75,
    font_size: int = 34
) -> str:
    """
    Constructs an FFmpeg drawtext filter string for a subtle, high-contrast watermark pill.
    """
    clean_handle = handle.replace(":", "\\:").replace("'", "").strip()
    if not clean_handle.startswith("@"):
        clean_handle = f"@{clean_handle}"

    box_alpha = max(0.2, min(0.9, opacity))

    if position == "top_left":
        pos_expr = "x=40:y=60"
    elif position == "bottom_center":
        pos_expr = "x=(w-text_w)/2:y=h-text_h-220"
    elif position == "bottom_right":
        pos_expr = "x=w-text_w-40:y=h-text_h-220"
    else:  # default top_right
        pos_expr = "x=w-text_w-40:y=60"

    font_file = find_system_font()
    font_opt = f":fontfile='{font_file.replace(':', r'\:')}'" if font_file else ""

    filter_str = (
        f"drawtext="
        f"text='{clean_handle}'"
        f"{font_opt}:"
        f"fontsize={font_size}:"
        f"fontcolor=white@{box_alpha:.2f}:"
        f"box=1:"
        f"boxcolor=black@{box_alpha * 0.75:.2f}:"
        f"boxborderw=10:"
        f"{pos_expr}"
    )
    return filter_str


def apply_watermark(
    source_video_path: str,
    handle: str = "@vediohooks",
    position: str = "top_right",
    opacity: float = 0.75,
    output_path: Optional[str] = None
) -> str:
    """
    Burns a semi-transparent account watermark into the video short.
    """
    src_p = Path(source_video_path)
    if not src_p.exists():
        raise FileNotFoundError(f"Source video not found: {source_video_path}")

    os.makedirs("output", exist_ok=True)
    if not output_path:
        output_path = f"output/watermarked_{uuid.uuid4().hex[:8]}.mp4"

    filter_str = build_watermark_drawtext_filter(
        handle=handle,
        position=position,
        opacity=opacity
    )

    enc_args = get_ffmpeg_encoding_args()

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src_p),
        "-vf", filter_str,
        "-c:a", "copy"
    ] + enc_args + [output_path]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0 or not os.path.exists(output_path):
        # Fallback to libx264 software if hardware encoder hiccups on specific filter
        cmd_fb = [
            "ffmpeg", "-y",
            "-i", str(src_p),
            "-vf", filter_str,
            "-c:a", "copy",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            output_path
        ]
        proc_fb = subprocess.run(cmd_fb, capture_output=True, text=True, timeout=45)
        if proc_fb.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"FFmpeg watermark failed: {proc_fb.stderr[:300]}")

    return output_path
