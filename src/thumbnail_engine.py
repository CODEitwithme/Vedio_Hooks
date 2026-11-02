"""
High-CTR Cover Thumbnail Generation Engine for VedioHooks AI Media Factory.
Generates 3 distinct psychological 9:16 vertical cover thumbnails:
1. Style 1: Bold Kinetic Box Banner (Hormozi Style)
2. Style 2: Face Zoom & Contrast Pop (MrBeast Style)
3. Style 3: Minimalist Cinematic Vignette (Documentary / Modern Style)
"""

import os
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional


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


def extract_keyframe(video_path: str, time_sec: float = 1.0, output_path: Optional[str] = None) -> str:
    """Extracts a high-quality keyframe from the vertical video using FFmpeg."""
    if not output_path:
        os.makedirs("temp", exist_ok=True)
        output_path = f"temp/frame_{uuid.uuid4().hex[:8]}.jpg"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(max(0.0, time_sec)),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=10)
    return output_path


def generate_cover_thumbnails(
    video_path: str,
    title: str = "VIRAL MOMENT",
    niche: str = "Motivation",
    time_sec: float = 1.0,
    output_dir: str = "output/thumbnails"
) -> List[Dict[str, Any]]:
    """
    Generates 3 high-CTR 9:16 vertical cover thumbnails tailored to psychological engagement styles.
    Returns list of metadata dicts with image paths and style attributes.
    """
    os.makedirs(output_dir, exist_ok=True)
    raw_frame = extract_keyframe(video_path, time_sec=time_sec)
    if not os.path.exists(raw_frame) or os.path.getsize(raw_frame) == 0:
        raise RuntimeError("Failed to extract video keyframe for cover thumbnail generation.")

    clean_title = title.replace(":", "\\:").replace("'", "")
    short_words = clean_title.split()[:8]
    headline_text = " ".join(short_words).upper()
    mid_idx = len(short_words) // 2
    line1 = " ".join(short_words[:mid_idx]) if mid_idx > 0 else headline_text
    line2 = " ".join(short_words[mid_idx:]) if mid_idx > 0 else ""
    multiline_text = f"{line1}\\n{line2}" if line2 else line1

    unique_id = uuid.uuid4().hex[:8]
    covers = []
    font_file = find_system_font()
    font_opt = f":fontfile='{font_file.replace(':', r'\:')}'" if font_file else ""

    # --- Style 1: Bold Kinetic Box Banner (Hormozi Style) ---
    style1_path = os.path.join(output_dir, f"cover_hormozi_{unique_id}.jpg")
    filter1 = (
        f"drawtext="
        f"text='{multiline_text}'"
        f"{font_opt}:"
        f"fontsize=68:"
        f"fontcolor=white:"
        f"box=1:"
        f"boxcolor=black@0.90:"
        f"boxborderw=24:"
        f"x=(w-text_w)/2:"
        f"y=(h*0.22)"
    )
    cmd1 = ["ffmpeg", "-y", "-i", raw_frame, "-vf", filter1, "-q:v", "2", style1_path]
    subprocess.run(cmd1, capture_output=True, timeout=10)
    if not os.path.exists(style1_path):
        subprocess.run(["ffmpeg", "-y", "-i", raw_frame, style1_path], capture_output=True)

    covers.append({
        "style_id": "hormozi_bold",
        "name": "Kinetic Bold Box (Hormozi Style)",
        "description": "High-contrast dark badge with uppercase lettering and heavy eye-contact placement.",
        "path": style1_path,
        "recommended_for": ["Motivation", "AI & Study", "Gym & Fitness"]
    })

    # --- Style 2: Face Zoom & Contrast Pop (MrBeast Style) ---
    style2_path = os.path.join(output_dir, f"cover_beast_{unique_id}.jpg")
    # Crop zoom 1.1x from center + saturation boost + vibrant yellow banner
    filter2 = (
        f"crop=in_w*0.9:in_h*0.9:(in_w-out_w)/2:(in_h-out_h)/2,"
        f"scale=1080:1920,"
        f"eq=saturation=1.25:contrast=1.12,"
        f"drawtext=text='{multiline_text}'"
        f"{font_opt}:"
        f"fontsize=74:fontcolor=yellow:box=1:boxcolor=black@0.85:boxborderw=20:"
        f"x=(w-text_w)/2:y=(h*0.20)"
    )
    cmd2 = ["ffmpeg", "-y", "-i", raw_frame, "-vf", filter2, "-q:v", "2", style2_path]
    subprocess.run(cmd2, capture_output=True, timeout=10)
    if not os.path.exists(style2_path):
        subprocess.run(["ffmpeg", "-y", "-i", raw_frame, style2_path], capture_output=True)

    covers.append({
        "style_id": "beast_pop",
        "name": "Face Zoom & Contrast Pop (MrBeast Style)",
        "description": "1.1x center facial punch-in with +25% saturation boost and vibrant yellow headline.",
        "path": style2_path,
        "recommended_for": ["Cricket", "Gym & Fitness", "Common / General"]
    })

    # --- Style 3: Minimalist Cinematic Vignette (Documentary / Apple Style) ---
    style3_path = os.path.join(output_dir, f"cover_cinema_{unique_id}.jpg")
    # Subtle vignette + elegant lower third typography
    filter3 = (
        f"vignette=PI/4,"
        f"drawtext=text='{headline_text}'"
        f"{font_opt}:"
        f"fontsize=54:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=16:"
        f"x=(w-text_w)/2:y=(h*0.78)"
    )
    cmd3 = ["ffmpeg", "-y", "-i", raw_frame, "-vf", filter3, "-q:v", "2", style3_path]
    subprocess.run(cmd3, capture_output=True, timeout=10)
    if not os.path.exists(style3_path):
        subprocess.run(["ffmpeg", "-y", "-i", raw_frame, style3_path], capture_output=True)

    covers.append({
        "style_id": "cinema_clean",
        "name": "Minimalist Cinema Vignette (Documentary Style)",
        "description": "Vignette edge shading with clean lower-third headline positioning for sophisticated pacing.",
        "path": style3_path,
        "recommended_for": ["AI & Study", "Motivation", "Common / General"]
    })

    # Clean temporary frame
    try:
        os.remove(raw_frame)
    except OSError:
        pass

    return covers
