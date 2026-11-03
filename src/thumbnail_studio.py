"""
AI Thumbnail & Cover Studio for VedioHooks AI.
Generates visually attractive, high-CTR thumbnails and covers for:
- YouTube Long-form (16:9, 1280x720)
- YouTube Shorts (9:16, 1080x1920)
- Instagram Reels covers (9:16, 1080x1920 with 1:1 square center crop preview)
- TikTok covers (9:16, 1080x1920)

Features:
- Video frame extraction via FFmpeg.
- MediaPipe / OpenCV face detection & focal center tracking.
- Laplacian sharpness scoring & safe zone calculation.
- 4 Modes: AI Auto, Face-Focused, Cinematic, Custom.
- 3 Psychological Variations: Emotional, Curiosity, Professional.
- Short high-impact headline intelligence (2-6 words).
- 100% local-first PIL compositing with drop shadows, outlines, and niche branding.
"""

import os
import sys
import re
import math
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import cv2
import numpy as np

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.face_tracker import get_face_tracker


# --- Standard Canvas Dimensions ---
CANVAS_DIMENSIONS = {
    "16:9": (1280, 720),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}

# --- Niche Branding Palettes ---
NICHE_BRANDING = {
    "Motivation": {
        "primary_color": "#eab308",  # Amber / Gold
        "secondary_color": "#ffffff",
        "badge_bg": "rgba(234, 179, 8, 0.95)",
        "accent_text": "#000000",
        "sample_headlines": ["STOP QUITTING", "NEVER GIVE UP", "THE PAIN OF DISCIPLINE", "MINDSET IS EVERYTHING", "DO NOT WAIT"]
    },
    "Cricket": {
        "primary_color": "#22c55e",  # Vibrant Green
        "secondary_color": "#ffffff",
        "badge_bg": "rgba(34, 197, 94, 0.95)",
        "accent_text": "#000000",
        "sample_headlines": ["UNBELIEVABLE FINISH!", "TURNING POINT", "MATCH DEFINING OVER", "HISTORIC RECORD", "PURE MASTERCLASS"]
    },
    "AI & Study": {
        "primary_color": "#06b6d4",  # Cyan / Tech Blue
        "secondary_color": "#ffffff",
        "badge_bg": "rgba(6, 182, 212, 0.95)",
        "accent_text": "#000000",
        "sample_headlines": ["10X STUDY HACK", "SECRET AI TOOL", "DON'T STUDY HARDER", "WORK IN HALF TIME", "AUTOMATE THIS"]
    },
    "Gym & Fitness": {
        "primary_color": "#ef4444",  # Beast Red
        "secondary_color": "#ffffff",
        "badge_bg": "rgba(239, 68, 68, 0.95)",
        "accent_text": "#ffffff",
        "sample_headlines": ["STOP SQUATTING LIKE THIS", "GROW BIGGER ARMS", "FORM MISTAKE", "BUILD REAL MUSCLE", "FIX THIS NOW"]
    },
    "Common / General": {
        "primary_color": "#a855f7",  # Purple / Curiosity
        "secondary_color": "#ffffff",
        "badge_bg": "rgba(168, 85, 247, 0.95)",
        "accent_text": "#ffffff",
        "sample_headlines": ["DID YOU KNOW?", "THE HIDDEN TRUTH", "THIS CHANGED HISTORY", "WEIRD BUT TRUE", "UNSOLVED MYSTERY"]
    }
}


# --- Font Resolution Helper ---
def get_high_impact_font(size: int = 72) -> ImageFont.FreeTypeFont:
    """Attempts to load a bold, high-impact font with cross-platform fallbacks."""
    candidate_paths = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
    ]
    # Check matplotlib bundled fonts if available
    try:
        import matplotlib
        mpl_font = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
        if mpl_font.exists():
            candidate_paths.append(str(mpl_font))
    except Exception:
        pass

    for p in candidate_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue

    # Fallback to default PIL font
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# --- Pydantic Data Models ---

class FrameCandidate(BaseModel):
    timestamp_sec: float
    frame_path: str
    sharpness_score: float
    face_count: int
    has_face: bool
    face_center_x: float = 0.5
    face_center_y: float = 0.5
    face_area: float = 0.0
    quality_score: int = 80


class ThumbnailVariation(BaseModel):
    variation_type: str = Field(description="'emotional', 'curiosity', 'professional'")
    headline: str
    image_path: str
    aspect_ratio: str = "9:16"
    platform: str = "universal"
    style_mode: str = "auto"
    source_timestamp: float = 1.0


class ThumbnailGenerationResult(BaseModel):
    target_type: str
    target_id: Any
    job_id: Optional[str] = None
    aspect_ratio: str = "9:16"
    selected_frame: FrameCandidate
    all_candidates: List[FrameCandidate]
    variations: List[ThumbnailVariation]
    grid_crop_preview_path: Optional[str] = None


# --- Frame Extraction & Analysis Engine ---

def extract_video_frame(video_path: str, timestamp_sec: float, output_path: str) -> bool:
    """Uses FFmpeg to grab a single high-quality JPG frame at a specific timestamp."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(max(0.0, float(timestamp_sec))),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1024
    except Exception as ex:
        print(f"[!] Frame extraction error at {timestamp_sec}s: {ex}")
        return False


def analyze_frame_quality(frame_path: str, timestamp_sec: float) -> FrameCandidate:
    """
    Analyzes an extracted video frame using OpenCV and MediaPipe:
    - Calculates Laplacian sharpness.
    - Detects faces, face centers, and face sizes.
    - Computes composite quality score (0-100).
    """
    if not os.path.exists(frame_path):
        return FrameCandidate(
            timestamp_sec=timestamp_sec,
            frame_path=frame_path,
            sharpness_score=0.0,
            face_count=0,
            has_face=False
        )

    bgr = cv2.imread(frame_path)
    if bgr is None:
        return FrameCandidate(
            timestamp_sec=timestamp_sec,
            frame_path=frame_path,
            sharpness_score=0.0,
            face_count=0,
            has_face=False
        )

    # 1. Sharpness via Laplacian variance
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # 2. Face Detection via SmartFaceTracker
    face_count = 0
    has_face = False
    fc_x, fc_y, f_area = 0.5, 0.5, 0.0

    try:
        tracker = get_face_tracker()
        faces = tracker.detect_faces_in_frame(bgr)
        face_count = len(faces)
        if face_count > 0:
            has_face = True
            # Find largest face
            largest = max(faces, key=lambda f: f.get("area", 0.0))
            fc_x = float(largest.get("center_x", 0.5))
            fc_y = float(largest.get("center_y", 0.5))
            f_area = float(largest.get("area", 0.0))
    except Exception as face_err:
        # Fallback to Haar cascade or skip face detection gracefully
        pass

    # Composite Quality Score (0 - 100)
    # Norm sharpness: 0 - 500 mapped to 0 - 40
    norm_sharp = min(40, int((sharpness / 400.0) * 40))
    face_bonus = 40 if has_face and f_area >= 0.02 else (25 if has_face else 10)
    recency_bonus = 20 if timestamp_sec <= 4.0 else 10
    total_score = min(100, max(50, norm_sharp + face_bonus + recency_bonus))

    return FrameCandidate(
        timestamp_sec=timestamp_sec,
        frame_path=frame_path,
        sharpness_score=round(sharpness, 2),
        face_count=face_count,
        has_face=has_face,
        face_center_x=round(fc_x, 3),
        face_center_y=round(fc_y, 3),
        face_area=round(f_area, 4),
        quality_score=total_score
    )


def extract_candidate_frames(
    video_path: str,
    start_sec: float,
    end_sec: float,
    temp_dir: str = "temp/thumbnails"
) -> List[FrameCandidate]:
    """
    Extracts candidate frames across the clip:
    - Early hook frames: start + 0.5s, start + 1.5s, start + 3.0s
    - Midpoint frame: (start + end) / 2
    - Climax frame: max(start, end - 3.0s)
    """
    os.makedirs(temp_dir, exist_ok=True)
    duration = max(1.0, end_sec - start_sec)
    timestamps = [
        start_sec + min(0.5, duration * 0.1),
        start_sec + min(1.5, duration * 0.25),
        start_sec + min(3.0, duration * 0.4),
        start_sec + duration * 0.5,
        start_sec + max(0.5, duration * 0.8)
    ]
    # Deduplicate and sort
    timestamps = sorted(list(set([round(t, 2) for t in timestamps if t <= end_sec])))

    candidates: List[FrameCandidate] = []
    base_name = Path(video_path).stem

    for idx, ts in enumerate(timestamps):
        out_frame = os.path.join(temp_dir, f"{base_name}_ts_{int(ts * 10)}_{idx}.jpg")
        success = extract_video_frame(video_path, ts, out_frame)
        if success:
            cand = analyze_frame_quality(out_frame, ts)
            candidates.append(cand)

    if not candidates:
        # Fallback to single frame at start_sec
        fallback_path = os.path.join(temp_dir, f"{base_name}_fallback.jpg")
        extract_video_frame(video_path, start_sec, fallback_path)
        candidates.append(analyze_frame_quality(fallback_path, start_sec))

    return sorted(candidates, key=lambda c: c.quality_score, reverse=True)


# --- Headline Intelligence (2 to 6 Words) ---

def generate_thumbnail_headline(
    title: str,
    niche: str,
    variation_type: str = "emotional"
) -> str:
    """
    Synthesizes short, punchy 2-5 word thumbnail headlines tailored to the variation type.
    """
    branding = NICHE_BRANDING.get(niche, NICHE_BRANDING["Common / General"])
    clean_title = re.sub(r"[#|\[\]]", "", title).strip().upper()
    words = [w for w in clean_title.split() if len(w) > 2]

    if variation_type == "emotional":
        emotional_words = {
            "Motivation": ["NEVER QUIT", "I WAS WRONG", "THE HARD TRUTH", "PAIN IS TEMPORARY", "NO MORE EXCUSES"],
            "Cricket": ["HEARTBREAKING", "PURE PASSION", "UNBELIEVABLE", "TEARS IN EYES", "EPIC COMEBACK"],
            "AI & Study": ["I WAS SHOCKED", "THIS SAVED ME", "GAME CHANGER", "DON'T PANIC", "SECRET REVEALED"],
            "Gym & Fitness": ["STOP HURTING YOURSELF", "PAIN TO GAIN", "NEVER AGAIN", "WAKE UP CALL", "BRUTAL TRUTH"],
            "Common / General": ["SHOCKING TRUTH", "I WAS LIED TO", "CAN'T UNSEE THIS", "UNBELIEVABLE", "NEVER FORGET"]
        }
        options = emotional_words.get(niche, ["SHOCKING REVEAL", "UNBELIEVABLE", "THE REAL TRUTH"])
        return options[hash(title) % len(options)]

    elif variation_type == "curiosity":
        curiosity_words = {
            "Motivation": ["WHY 99% FAIL", "THE SECRET RULE", "DON'T DO THIS", "THE 1% HABIT", "BEFORE YOU GIVE UP"],
            "Cricket": ["HOW THEY WON", "LAST BALL DRAMA", "NOBODY NOTICED", "THE TURNING POINT", "ILLEGAL MOVE?"],
            "AI & Study": ["10X PRODUCTIVITY", "SECRET AI TOOL", "THE LOOPHOLE", "WORK IN HALF TIME", "DELETE CHATGPT?"],
            "Gym & Fitness": ["THE #1 MISTAKE", "WHY NO GAINS?", "GROW 2X FASTER", "STOP DOING THIS", "FIX YOUR FORM"],
            "Common / General": ["DID YOU KNOW?", "THE HIDDEN TRUTH", "WHAT HAPPENED?", "DON'T TRUST THIS", "MYSTERY SOLVED"]
        }
        options = curiosity_words.get(niche, ["THE HIDDEN TRUTH", "WHY 99% FAIL", "DON'T MISS THIS"])
        return options[hash(title) % len(options)]

    else:  # professional / clean
        if len(words) >= 2:
            return " ".join(words[:4])
        return branding["sample_headlines"][hash(title) % len(branding["sample_headlines"])]


# --- Canvas Compositing & Typography Engine ---

def composite_thumbnail(
    frame_path: str,
    output_path: str,
    headline: str,
    aspect_ratio: str = "9:16",
    style_mode: str = "auto",
    niche: str = "Motivation",
    face_candidate: Optional[FrameCandidate] = None,
    custom_placement: str = "safe_auto",
    brand_handle: Optional[str] = "@vediohooks"
) -> str:
    """
    Renders high-CTR thumbnail with PIL:
    - Crops/resizes to target canvas (16:9, 9:16, 1:1).
    - Applies visual grading: dark bottom scrim, radial vignette (face-focused), or cinematic fades.
    - Draws high-contrast typography with thick outline & shadow.
    - Positions headline in safe zone away from speaker faces.
    - Injects niche branding accent pill badge.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    target_w, target_h = CANVAS_DIMENSIONS.get(aspect_ratio, (1080, 1920))

    # 1. Load source frame
    if not os.path.exists(frame_path):
        # Create solid gradient background fallback
        base_img = Image.new("RGB", (target_w, target_h), (18, 27, 33))
    else:
        src_img = Image.open(frame_path).convert("RGB")
        sw, sh = src_img.size

        # Fit & crop to target aspect ratio
        target_ratio = target_w / float(target_h)
        src_ratio = sw / float(sh)

        if style_mode == "face_focused" and face_candidate and face_candidate.has_face:
            # Zoom and center on speaker's face
            fc_x = int(face_candidate.face_center_x * sw)
            fc_y = int(face_candidate.face_center_y * sh)
            crop_w = int(sw * 0.75)
            crop_h = int(crop_w / target_ratio)
            if crop_h > sh:
                crop_h = sh
                crop_w = int(crop_h * target_ratio)

            left = max(0, min(sw - crop_w, fc_x - crop_w // 2))
            top = max(0, min(sh - crop_h, fc_y - crop_h // 2))
            cropped = src_img.crop((left, top, left + crop_w, top + crop_h))
            base_img = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        else:
            # Standard center crop
            if src_ratio > target_ratio:
                # Source is wider than target
                crop_w = int(sh * target_ratio)
                left = (sw - crop_w) // 2
                cropped = src_img.crop((left, 0, left + crop_w, sh))
            else:
                crop_h = int(sw / target_ratio)
                top = (sh - crop_h) // 2
                cropped = src_img.crop((0, top, sw, top + crop_h))
            base_img = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 2. Apply Visual Enhancements per Mode
    enhancer = ImageEnhance.Contrast(base_img)
    base_img = enhancer.enhance(1.15)  # Boost contrast
    color_enhancer = ImageEnhance.Color(base_img)
    base_img = color_enhancer.enhance(1.20)  # Boost saturation

    # 3. Create Gradient Scrim Overlays for Readability
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Determine safe zone for headline
    safe_y_ratio = 0.70  # Default lower third
    if custom_placement == "top":
        safe_y_ratio = 0.15
    elif custom_placement == "center":
        safe_y_ratio = 0.45
    elif custom_placement == "bottom":
        safe_y_ratio = 0.75
    else:  # safe_auto
        if face_candidate and face_candidate.has_face:
            if face_candidate.face_center_y > 0.55:
                safe_y_ratio = 0.18  # Place on top if face is low
            else:
                safe_y_ratio = 0.70  # Place on bottom if face is high

    # Add dark scrim behind text region
    scrim_start = int(target_h * max(0.0, safe_y_ratio - 0.15))
    scrim_end = int(target_h * min(1.0, safe_y_ratio + 0.22))

    for y in range(scrim_start, scrim_end):
        prog = (y - scrim_start) / float(max(1, scrim_end - scrim_start))
        # Bell curve opacity peaking in center
        alpha = int(180 * math.sin(prog * math.pi))
        overlay_draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))

    # Cinematic letterbox bars if cinematic mode
    if style_mode == "cinematic" and aspect_ratio == "16:9":
        bar_h = int(target_h * 0.10)
        overlay_draw.rectangle([0, 0, target_w, bar_h], fill=(0, 0, 0, 255))
        overlay_draw.rectangle([0, target_h - bar_h, target_w, target_h], fill=(0, 0, 0, 255))

    # Merge overlay with base image
    base_img = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(base_img)

    # 4. Typography Layout & Word Wrapping
    branding = NICHE_BRANDING.get(niche, NICHE_BRANDING["Common / General"])
    primary_color = branding["primary_color"]

    # Calculate optimal font size
    base_font_size = 86 if aspect_ratio == "9:16" else 64
    font = get_high_impact_font(size=base_font_size)

    # Word wrap headline to max 2 lines
    words = headline.upper().split()
    lines = []
    if len(words) <= 3:
        lines = [" ".join(words)]
    else:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    # Calculate total text height
    line_metrics = []
    total_text_h = 0
    max_line_w = 0
    for l in lines:
        bbox = draw.textbbox((0, 0), l, font=font, stroke_width=6)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        line_metrics.append((lw, lh))
        total_text_h += lh + 16
        if lw > max_line_w:
            max_line_w = lw

    # Compute text start position
    curr_y = int(target_h * safe_y_ratio) - (total_text_h // 2)

    # Draw Text Lines with High-Contrast Stroke and Drop Shadow
    for idx, line in enumerate(lines):
        lw, lh = line_metrics[idx]
        curr_x = (target_w - lw) // 2

        # 1. Drop Shadow
        draw.text(
            (curr_x + 6, curr_y + 6),
            line,
            font=font,
            fill=(0, 0, 0, 220),
            stroke_width=6,
            stroke_fill=(0, 0, 0, 220)
        )

        # 2. Stroke & Fill (Accent color for second line or last word)
        fill_color = primary_color if idx == len(lines) - 1 else "#FFFFFF"
        draw.text(
            (curr_x, curr_y),
            line,
            font=font,
            fill=fill_color,
            stroke_width=6,
            stroke_fill=(0, 0, 0)
        )
        curr_y += lh + 16

    # 5. Add Brand Badge / Handle Pill
    if brand_handle:
        pill_font = get_high_impact_font(size=28)
        pill_text = f"🔥 {brand_handle.upper()}"
        pbbox = draw.textbbox((0, 0), pill_text, font=pill_font)
        pw = pbbox[2] - pbbox[0] + 32
        ph = pbbox[3] - pbbox[1] + 16
        px = (target_w - pw) // 2
        py = target_h - ph - (60 if aspect_ratio == "9:16" else 30)

        # Draw rounded pill
        draw.rounded_rectangle([px, py, px + pw, py + ph], radius=12, fill=(15, 23, 42), outline=primary_color, width=2)
        draw.text((px + 16, py + 8), pill_text, font=pill_font, fill=primary_color)

    # Save output
    base_img.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path


def generate_grid_crop_preview(vertical_image_path: str, output_path: str) -> str:
    """
    Creates a 1:1 square center-crop preview of a 9:16 Reel/Shorts cover
    to simulate how the post appears on an Instagram Profile Grid (1080x1080).
    """
    if not os.path.exists(vertical_image_path):
        return ""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img = Image.open(vertical_image_path).convert("RGB")
    w, h = img.size
    # Center square crop
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    crop = img.crop((left, top, left + size, top + size))
    square = crop.resize((1080, 1080), Image.Resampling.LANCZOS)

    # Add subtle Instagram grid border indicator
    draw = ImageDraw.Draw(square)
    draw.rectangle([0, 0, 1080, 1080], outline=(255, 255, 255, 120), width=4)

    square.save(output_path, "JPEG", quality=90)
    return output_path


# --- Thumbnail Studio Orchestrator ---

def generate_thumbnail_suite(
    video_path: str,
    target_type: str,
    target_id: Any,
    title: str,
    niche: str = "Motivation",
    start_sec: float = 0.0,
    end_sec: float = 45.0,
    aspect_ratio: str = "9:16",
    style_mode: str = "auto",
    brand_handle: str = "@vediohooks",
    custom_headline: Optional[str] = None,
    output_dir: str = "output/thumbnails"
) -> ThumbnailGenerationResult:
    """
    Autonomous AI Thumbnail & Cover generator:
    1. Extracts and evaluates candidate video frames.
    2. Identifies the optimal frame using face presence and sharpness telemetry.
    3. Produces 3 high-CTR variations: Emotional, Curiosity, and Professional.
    4. Generates Instagram Profile Grid (1:1) center-crop preview.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Candidate frame extraction
    candidates = extract_candidate_frames(
        video_path=video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        temp_dir=os.path.join(output_dir, "candidates")
    )
    best_frame = candidates[0] if candidates else FrameCandidate(
        timestamp_sec=start_sec,
        frame_path="",
        sharpness_score=0.0,
        face_count=0,
        has_face=False
    )

    # 2. Build 3 variations: Emotional, Curiosity, Professional
    variations: List[ThumbnailVariation] = []
    var_types = ["emotional", "curiosity", "professional"]

    for idx, v_type in enumerate(var_types):
        # Pick corresponding candidate frame if available
        cand = candidates[idx % len(candidates)]
        headline = custom_headline if custom_headline else generate_thumbnail_headline(
            title=title,
            niche=niche,
            variation_type=v_type
        )
        out_name = f"thumb_{target_type}_{target_id}_{v_type}_{aspect_ratio.replace(':', 'x')}.jpg"
        out_path = os.path.join(output_dir, out_name)

        composite_thumbnail(
            frame_path=cand.frame_path,
            output_path=out_path,
            headline=headline,
            aspect_ratio=aspect_ratio,
            style_mode=style_mode,
            niche=niche,
            face_candidate=cand,
            brand_handle=brand_handle
        )

        variations.append(ThumbnailVariation(
            variation_type=v_type,
            headline=headline,
            image_path=out_path,
            aspect_ratio=aspect_ratio,
            platform="universal",
            style_mode=style_mode,
            source_timestamp=cand.timestamp_sec
        ))

    # 3. If vertical (9:16), also generate 1:1 Instagram profile grid preview
    grid_crop_path = None
    if aspect_ratio == "9:16" and variations:
        grid_name = f"thumb_{target_type}_{target_id}_grid_preview.jpg"
        grid_crop_path = os.path.join(output_dir, grid_name)
        generate_grid_crop_preview(variations[0].image_path, grid_crop_path)

    return ThumbnailGenerationResult(
        target_type=target_type,
        target_id=target_id,
        aspect_ratio=aspect_ratio,
        selected_frame=best_frame,
        all_candidates=candidates,
        variations=variations,
        grid_crop_preview_path=grid_crop_path
    )

