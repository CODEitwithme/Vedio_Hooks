"""
Dynamic Auto-Zoom & Punch-Cut Engine for VedioHooks AI Media Factory.
Automatically detects energetic phrase transitions, speech cadence shifts, and emotional keywords,
then applies rhythmic 1.15x-1.18x punch-cut zooms in 9:16 vertical video (1080x1920)
to reset viewer dopamine, eliminate talking-head fatigue, and maximize retention.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from src.hardware_accel import get_ffmpeg_encoding_args
from src.ingest import get_media_info

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "120"))

# High-impact emotional trigger words that warrant immediate punch zoom
EMPHASIS_KEYWORDS = {
    "SECRET", "NEVER", "ALWAYS", "STOP", "TRUTH", "LIE", "MISTAKE", "WHY",
    "MONEY", "RICH", "POWER", "FIRE", "DANGER", "WARNING", "LISTEN",
    "DISCIPLINE", "HABIT", "PAIN", "SUCCESS", "FAIL", "FAILURE", "RULE",
    "RECORD", "SHOCKING", "INSANE", "UNBELIEVABLE", "CHAMPION", "KING",
    "CRITICAL", "BRUTAL", "CHANGE", "DESTROY", "FUTURE", "IMPORTANT"
}


def calculate_zoom_intervals(
    words: Optional[List[Dict[str, Any]]] = None,
    duration_sec: float = 30.0,
    min_gap_sec: float = 3.5,
    max_gap_sec: float = 5.5,
    zoom_duration_sec: float = 2.2,
    zoom_scale: float = 1.16
) -> List[Dict[str, Any]]:
    """
    Computes frame-accurate time intervals where camera cuts to a 1.16x punch-in zoom.
    
    If word-level transcript is provided, aligns punch-cuts with high-impact emphasis words.
    Otherwise, applies rhythmic, cadence-based punch zooms every 3.5 - 5.5 seconds.
    """
    intervals: List[Dict[str, Any]] = []
    if duration_sec <= 2.5:
        return []

    # For short test or teaser videos (e.g. <= 6.0s), schedule a punch cut in the middle
    if duration_sec <= 6.0:
        z_end = round(min(duration_sec - 0.4, 3.5), 2)
        if z_end > 1.5:
            return [{
                "start": 1.5,
                "end": z_end,
                "duration": round(z_end - 1.5, 2),
                "zoom_scale": zoom_scale,
                "type": "punch_cut"
            }]

    # Map emphasis word timestamps if available
    emphasis_times: List[float] = []
    if words:
        for w in words:
            clean_w = "".join(ch for ch in w.get("word", "") if ch.isalnum()).upper()
            if clean_w in EMPHASIS_KEYWORDS:
                w_start = float(w.get("start", 0.0))
                emphasis_times.append(w_start)

    cursor = 2.0  # Allow initial 0-2.0s baseline establishing shot
    while cursor + 1.5 < duration_sec:
        # Check if an emphasis word is within the upcoming window [cursor + min_gap, cursor + max_gap]
        next_target = cursor + min_gap_sec
        matched_emp = next((t for t in emphasis_times if cursor + 2.0 <= t <= cursor + max_gap_sec), None)

        if matched_emp is not None:
            z_start = round(matched_emp, 2)
        else:
            z_start = round(next_target, 2)

        z_end = round(min(duration_sec - 0.5, z_start + zoom_duration_sec), 2)

        if z_end - z_start >= 1.0:
            intervals.append({
                "start": z_start,
                "end": z_end,
                "duration": round(z_end - z_start, 2),
                "zoom_scale": zoom_scale,
                "type": "punch_cut"
            })
            cursor = z_end + 1.5  # Return to baseline 1.0x for at least 1.5s
        else:
            break

    return intervals


def build_dynamic_zoom_filter(
    intervals: List[Dict[str, Any]],
    target_width: int = 1080,
    target_height: int = 1920
) -> str:
    """
    Constructs an FFmpeg filter expression that crops and scales the vertical 9:16 frame.
    When a punch-cut is active (is_zoomed = 1), crops inwards by zoom_scale and scales back to 1080x1920.
    When inactive (is_zoomed = 0), performs an exact 1.0x pass-through without distortion.
    """
    if not intervals:
        return f"scale={target_width}:{target_height}:flags=lanczos"

    # Build between() clauses for each punch-cut interval
    between_clauses = [f"between(t\\,{item['start']:.2f}\\,{item['end']:.2f})" for item in intervals]
    combined_is_zoomed = "+".join(between_clauses)

    # Base zoom factor (e.g., 0.16 extra scale = 1.16x zoom)
    avg_zoom = intervals[0].get("zoom_scale", 1.16)
    delta_zoom = round(avg_zoom - 1.0, 3)

    # In FFmpeg crop filter:
    # crop_w = iw / (1.0 + delta_zoom * min(1, is_zoomed))
    # crop_h = ih / (1.0 + delta_zoom * min(1, is_zoomed))
    # crop_x = (iw - ow) / 2, crop_y = (ih - oh) / 2
    filter_expr = (
        f"crop=w='trunc(iw/(1+{delta_zoom}*min(1\\,{combined_is_zoomed}))/2)*2':"
        f"h='trunc(ih/(1+{delta_zoom}*min(1\\,{combined_is_zoomed}))/2)*2':"
        f"x='(iw-ow)/2':y='(ih-oh)/2',"
        f"scale={target_width}:{target_height}:flags=lanczos"
    )
    return filter_expr


def apply_dynamic_auto_zoom(
    input_video_path: str,
    output_video_path: Optional[str] = None,
    words: Optional[List[Dict[str, Any]]] = None,
    zoom_scale: float = 1.16,
    target_width: int = 1080,
    target_height: int = 1920,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> Dict[str, Any]:
    """
    Applies dynamic punch-cut auto-zoom to a 9:16 vertical video short.
    Uses hardware acceleration where available with zero-config CPU fallback.
    """
    in_p = Path(input_video_path)
    if not in_p.exists():
        raise FileNotFoundError(f"Input video not found: {input_video_path}")

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in system PATH.")

    # Probe duration
    info = get_media_info(str(in_p))
    duration = float(info.get("duration", 30.0))

    # Calculate intervals
    intervals = calculate_zoom_intervals(
        words=words,
        duration_sec=duration,
        zoom_scale=zoom_scale
    )

    os.makedirs("output", exist_ok=True)
    if not output_video_path:
        out_name = f"autozoom_{uuid.uuid4().hex[:8]}.mp4"
        output_video_path = str(Path("output") / out_name)

    filter_expr = build_dynamic_zoom_filter(intervals, target_width, target_height)
    enc_args = get_ffmpeg_encoding_args()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(in_p),
        "-vf", filter_expr,
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        *enc_args,
        "-movflags", "+faststart",
        str(output_video_path)
    ]

    print(f"[*] Applying dynamic auto-zoom ({len(intervals)} punch cuts, scale={zoom_scale}x)...")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if res.returncode != 0 or not os.path.exists(output_video_path) or os.path.getsize(output_video_path) == 0:
        # Fallback to software encoding with copy audio
        fb_cmd = [
            ffmpeg_bin, "-y",
            "-i", str(in_p),
            "-vf", filter_expr,
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_video_path)
        ]
        fb_res = subprocess.run(fb_cmd, capture_output=True, text=True, timeout=timeout)
        if fb_res.returncode != 0 or not os.path.exists(output_video_path):
            raise RuntimeError(f"FFmpeg dynamic auto-zoom failed: {fb_res.stderr[:300]}")

    out_size = os.path.getsize(output_video_path)
    print(f"[SUCCESS] Dynamic Auto-Zoom complete -> {output_video_path} ({out_size:,} bytes)")

    return {
        "status": "success",
        "output_path": output_video_path,
        "zoom_scale": zoom_scale,
        "punch_cuts_count": len(intervals),
        "intervals": intervals,
        "duration": duration,
        "file_size_bytes": out_size
    }
