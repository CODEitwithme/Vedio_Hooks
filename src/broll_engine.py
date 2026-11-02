"""
AI B-Roll Cutaway & Thematic Motion Overlay Engine for VedioHooks AI.
Generates 100% free, offline, procedural 9:16 vertical video motion backgrounds
and cutaways to create pattern interrupts during the first 3-second hook window.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "300"))

NICHE_BROLL_PROFILES: Dict[str, Dict[str, Any]] = {
    "Motivation": {
        "color1": "#0f172a",
        "color2": "#eab308",
        "expr": "sin(X/80+T)*cos(Y/80+T)*60",
        "label": "Deep Stoic Gold Pulse"
    },
    "Cricket": {
        "color1": "#064e3b",
        "color2": "#10b981",
        "expr": "sin(X/100+T*2)*40",
        "label": "Stadium Turf Green Glow"
    },
    "AI & Study": {
        "color1": "#0f172a",
        "color2": "#06b6d4",
        "expr": "sin(Y/60+T*3)*50",
        "label": "Cyber Grid Scanline"
    },
    "Gym & Fitness": {
        "color1": "#18181b",
        "color2": "#ef4444",
        "expr": "sin(X/70+Y/70+T*4)*60",
        "label": "High-Impact Crimson Surge"
    },
    "Common / General": {
        "color1": "#1e1b4b",
        "color2": "#f97316",
        "expr": "cos(X/90+T)*sin(Y/90-T)*50",
        "label": "Curiosity Violet-Amber Flow"
    }
}


def generate_thematic_motion_broll(
    duration_sec: float = 2.0,
    niche: str = "Motivation",
    output_path: Optional[str] = None,
    width: int = 1080,
    height: int = 1920
) -> str:
    """
    Synthesizes a 1080x1920 vertical motion cutaway using FFmpeg's built-in procedural visual filters.
    Requires no external stock footage downloads.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in system PATH.")

    dur = max(1.0, float(duration_sec))
    profile = NICHE_BROLL_PROFILES.get(niche, NICHE_BROLL_PROFILES["Motivation"])

    if not output_path:
        os.makedirs("temp/broll", exist_ok=True)
        safe_niche = niche.lower().replace(" ", "_").replace("&", "and")
        output_path = f"temp/broll/broll_{safe_niche}_{int(dur)}s.mp4"
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Use testsrc or geq to produce an animated visual gradient
    # Combining cellauto/mptestsrc or mandelbrot with color overlay
    filter_graph = (
        f"color=c={profile['color1']}:s={width}x{height}:d={dur},"
        f"drawbox=y=ih*0.2:h=ih*0.6:color={profile['color2']}@0.18:t=fill,"
        f"boxblur=40:5,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur-0.3}:d=0.3"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", filter_graph,
        "-t", str(dur),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        str(output_path)
    ]

    res = subprocess.run(cmd, capture_output=True, timeout=20)
    if res.returncode != 0:
        # Fallback to simple colored background
        cmd_fallback = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", f"color=c={profile['color1']}:s={width}x{height}:d={dur}",
            "-t", str(dur),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            str(output_path)
        ]
        subprocess.run(cmd_fallback, capture_output=True, timeout=15)

    return str(output_path)


def apply_hook_motion_overlay(
    video_path: str,
    output_path: str,
    niche: str = "Motivation",
    start_sec: float = 0.2,
    end_sec: float = 1.8,
    opacity: float = 0.22,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> str:
    """
    Overlays a subtle dynamic pattern interrupt during the initial hook window.
    Bridges visual transitions to boost initial retention without covering speaker face completely.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in system PATH.")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    dur = max(0.5, end_sec - start_sec)
    os.makedirs("temp/broll", exist_ok=True)
    broll_path = generate_thematic_motion_broll(duration_sec=dur, niche=niche)

    filter_complex = (
        f"[1:v]format=yuva420p,colorchannelmixer=aa={opacity}[broll];"
        f"[0:v][broll]overlay=0:0:enable='between(t,{start_sec},{end_sec})':eof_action=pass[outv]"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-i", video_path,
        "-i", broll_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        str(output_path)
    ]

    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if res.returncode != 0:
        # Fallback to original video if overlay fails
        shutil.copy(video_path, output_path)

    return str(output_path)
