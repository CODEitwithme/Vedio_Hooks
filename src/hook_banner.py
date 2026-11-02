"""
Top Hook Header Banner & Attention Grabber Engine for VedioHooks AI Media Factory.
Renders high-contrast, scroll-stopping headline banners in the upper 15% safe zone
(Y=180-240 on 1080x1920 vertical shorts) during the critical first 3-5 seconds (or full duration).
Dual-mode execution:
1. Native ASS Subtitle burning (zero extra encoding passes; burns simultaneously with karaoke subtitles).
2. Standalone FFmpeg overlay filter for post-processing existing rendered shorts.
"""

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from src.hardware_accel import get_ffmpeg_encoding_args
from src.ingest import get_media_info

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "120"))

# High-CTR visual theme styling for Top Hook Banners
BANNER_THEMES = {
    "hormozi_yellow": {
        "name": "Alex Hormozi Yellow",
        "ass_primary": "&H0000FFFF&",      # Neon Yellow (#FFFF00)
        "ass_box": "&HCC111827&",          # Deep Charcoal Pill 80% opacity
        "ass_outline": "&H00000000&",      # Black border
        "ffmpeg_fontcolor": "#ffff00",
        "ffmpeg_boxcolor": "black@0.85",
        "emoji_left": "🔥",
        "emoji_right": "⚡"
    },
    "beast_red": {
        "name": "MrBeast High-Energy Red",
        "ass_primary": "&H00FFFFFF&",      # Pure White
        "ass_box": "&HCC201199&",          # Deep Crimson Red
        "ass_outline": "&H00000000&",
        "ffmpeg_fontcolor": "white",
        "ffmpeg_boxcolor": "#b91c1c@0.90",
        "emoji_left": "🛑",
        "emoji_right": "⚠️"
    },
    "cyber_cyan": {
        "name": "Electric Cyber Cyan",
        "ass_primary": "&H00FFFF00&",      # Cyan (#00FFFF in BGR)
        "ass_box": "&HCC0F172A&",          # Slate 900 Glass
        "ass_outline": "&H00000000&",
        "ffmpeg_fontcolor": "#00f0ff",
        "ffmpeg_boxcolor": "#0f172a@0.85",
        "emoji_left": "🤖",
        "emoji_right": "💡"
    },
    "emerald_growth": {
        "name": "Viral Emerald Sports",
        "ass_primary": "&H00FFFFFF&",      # White text
        "ass_box": "&HCC14532D&",          # Deep Forest Green
        "ass_outline": "&H00000000&",
        "ffmpeg_fontcolor": "white",
        "ffmpeg_boxcolor": "#15803d@0.90",
        "emoji_left": "🏏",
        "emoji_right": "🏆"
    }
}


def generate_smart_hook_text(title: str, niche: str = "Motivation", clip_text: str = "") -> str:
    """
    Synthesizes a high-CTR, 3-6 word scroll-stopping headline from title and niche.
    """
    clean_title = re.sub(r"[|\-_#].*$", "", title).strip()
    words = clean_title.split()

    niche_lower = niche.lower()
    if "cricket" in niche_lower:
        prefix = "THE UNTOLD STORY:"
        fallback = "SHOCKING CRICKET RECORD"
    elif "fitness" in niche_lower or "gym" in niche_lower:
        prefix = "DO NOT DO THIS:"
        fallback = "THE #1 WORKOUT MISTAKE"
    elif "ai" in niche_lower or "study" in niche_lower:
        prefix = "FREE AI TOOL:"
        fallback = "SECRET STUDY HACK"
    else:  # Motivation / General
        prefix = "BRUTAL TRUTH:"
        fallback = "THE 1 HABIT TO CHANGE YOUR LIFE"

    if len(words) >= 3:
        short_title = " ".join(words[:6]).upper()
        return f"{short_title}"
    else:
        return f"{prefix} {fallback}".upper()


def generate_hook_banner_ass_elements(
    hook_text: str,
    theme: str = "hormozi_yellow",
    start_sec: float = 0.0,
    duration_sec: float = 3.5,
    margin_v: int = 180,
    font_size: int = 46,
    font_name: str = "Arial Black"
) -> Dict[str, str]:
    """
    Generates ASS subtitle formatting elements for the Top Hook Banner:
    - Style definition (Alignment 8 = Top-Center, BorderStyle 3 = Solid Box Pill)
    - Dialogue event with smooth 180ms fade-in and 250ms fade-out
    """
    theme_info = BANNER_THEMES.get(theme, BANNER_THEMES["hormozi_yellow"])

    # Clean text and add bracket / emoji framing
    clean_text = hook_text.strip().upper()
    left_emoji = theme_info["emoji_left"]
    right_emoji = theme_info["emoji_right"]
    banner_display = f"{left_emoji}  {clean_text}  {right_emoji}"

    # Style: HookBanner
    # Format: Style: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # BorderStyle=3 (opaque rectangular box), Alignment=8 (top center), MarginV=180
    style_def = (
        f"Style: HookBanner,{font_name},{font_size},"
        f"{theme_info['ass_primary']},{theme_info['ass_primary']},"
        f"{theme_info['ass_outline']},{theme_info['ass_box']},"
        f"-1,0,0,0,100,100,2,0,3,12,0,8,40,40,{margin_v},1"
    )

    # Format timestamps
    def fmt_ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        cs = int(round((sec - int(sec)) * 100))
        if cs >= 100:
            cs = 99
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    start_str = fmt_ts(start_sec)
    end_str = fmt_ts(start_sec + duration_sec)

    # Dialogue line with smooth fade in and fade out
    dialogue_def = (
        f"Dialogue: 2,{start_str},{end_str},HookBanner,,0,0,0,,"
        f"{{\\fad(180,250)}}{banner_display}"
    )

    return {
        "style_def": style_def,
        "dialogue_def": dialogue_def,
        "display_text": banner_display
    }


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


def apply_standalone_hook_banner(
    video_path: str,
    hook_text: str,
    output_path: Optional[str] = None,
    theme: str = "hormozi_yellow",
    duration_sec: float = 3.5,
    font_size: int = 42,
    y_pos: int = 200,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> Dict[str, Any]:
    """
    Applies the Top Hook Header Banner directly onto an existing MP4 video short
    using FFmpeg drawtext with a high-contrast bounding pill.
    """
    in_p = Path(video_path)
    if not in_p.exists():
        raise FileNotFoundError(f"Source video not found: {video_path}")

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in PATH.")

    os.makedirs("output", exist_ok=True)
    if not output_path:
        out_name = f"hookbanner_{uuid.uuid4().hex[:8]}.mp4"
        output_path = str(Path("output") / out_name)

    theme_info = BANNER_THEMES.get(theme, BANNER_THEMES["hormozi_yellow"])

    # Clean text for FFmpeg drawtext escaping
    clean_txt = hook_text.strip().replace(":", "\\:").replace("'", "").upper()
    display_txt = f"{clean_txt}"

    font_color = theme_info["ffmpeg_fontcolor"]
    box_color = theme_info["ffmpeg_boxcolor"]

    font_file = find_system_font()
    font_opt = f":fontfile='{font_file.replace(':', r'\:')}'" if font_file else ""

    # Upper third safe-zone positioning (y=200 on 1080x1920)
    # enable='between(t, 0, duration_sec)'
    drawtext_filter = (
        f"drawtext="
        f"text='{display_txt}'"
        f"{font_opt}:"
        f"fontsize={font_size}:"
        f"fontcolor={font_color}:"
        f"box=1:"
        f"boxcolor={box_color}:"
        f"boxborderw=20:"
        f"x=(w-text_w)/2:"
        f"y={y_pos}:"
        f"enable='between(t\\,0\\,{duration_sec:.2f})'"
    )

    enc_args = get_ffmpeg_encoding_args()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(in_p),
        "-vf", drawtext_filter,
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        *enc_args,
        "-movflags", "+faststart",
        str(output_path)
    ]

    print(f"[*] Applying standalone top hook banner ('{clean_txt}', theme={theme}, duration={duration_sec}s)...")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        # Fallback to software encoding
        fb_cmd = [
            ffmpeg_bin, "-y",
            "-i", str(in_p),
            "-vf", drawtext_filter,
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path)
        ]
        fb_res = subprocess.run(fb_cmd, capture_output=True, text=True, timeout=timeout)
        if fb_res.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"FFmpeg hook banner overlay failed: {fb_res.stderr[:300]}")

    out_size = os.path.getsize(output_path)
    print(f"[SUCCESS] Top Hook Banner applied -> {output_path} ({out_size:,} bytes)")

    return {
        "status": "success",
        "output_path": output_path,
        "hook_text": clean_txt,
        "theme": theme,
        "duration_sec": duration_sec,
        "file_size_bytes": out_size
    }
