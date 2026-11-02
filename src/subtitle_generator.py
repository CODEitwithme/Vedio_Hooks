"""
Dynamic Retention-Optimized Subtitle Generator (Alex Hormozi Style).
Generates Advanced SubStation Alpha (ASS) files with word-by-word karaoke highlighting,
bold typography, customizable neon color palettes, and burns them into vertical 9:16 videos.
"""

import os
import sys
import json
import shutil
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "300"))
DEFAULT_FFMPEG_PRESET = os.environ.get("FFMPEG_PRESET", "fast")

# Emotional & Viral Keyword to Contextual Emoji Mapping
KEYWORD_EMOJIS = {
    # Motivation & Mindset
    "MONEY": "💸", "RICH": "💰", "CASH": "💵", "FIRE": "🔥", "SECRET": "🤫",
    "POWER": "⚡", "MIND": "🧠", "BRAIN": "🧠", "GOAL": "🎯", "KING": "👑",
    "WIN": "🏆", "WINNER": "🏆", "STOP": "🛑", "DANGER": "⚠️", "SUCCESS": "🚀",
    "DISCIPLINE": "⚔️", "FOCUS": "🎯", "PAIN": "💥", "HEART": "❤️",
    # Cricket & Sports
    "CRICKET": "🏏", "BALL": "⚾", "RUN": "🏃", "SIX": "💥", "MATCH": "🏟️",
    "RECORD": "📜", "RECORD-BREAKING": "🔥", "CHAMPION": "🏆", "KOHLI": "👑",
    # Gym & Fitness
    "GYM": "🏋️‍♂️", "MUSCLE": "💪", "TRAIN": "🏋️", "LIFT": "🏋️‍♂️", "HEAVY": "🧱",
    "BODY": "🦾", "SQUAT": "🦵", "GROW": "📈", "REPS": "🔢",
    # AI & Study
    "AI": "🤖", "ROBOT": "🤖", "STUDY": "📚", "BOOK": "📖", "CODE": "💻",
    "TECH": "⚡", "TOOL": "🛠️", "FREE": "🎁", "HACK": "💡", "TRUTH": "💡",
    "TIME": "⏳", "FAST": "⚡", "SECRET": "🤫", "TRICK": "✨"
}

_OPTIMAL_ENCODER_CACHE: Optional[Dict[str, Any]] = None


def get_optimal_video_encoder() -> Dict[str, Any]:
    """
    Auto-detects the highest-performing available video encoder.
    Tests hardware acceleration (NVIDIA NVENC, AMD AMF, Intel QSV) and falls back
    safely to multi-threaded CPU libx264 with preset=fast.
    """
    global _OPTIMAL_ENCODER_CACHE
    if _OPTIMAL_ENCODER_CACHE is not None:
        return _OPTIMAL_ENCODER_CACHE

    candidates = [
        ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20"]),
        ("h264_amf", ["-c:v", "h264_amf", "-quality", "speed"]),
        ("h264_qsv", ["-c:v", "h264_qsv", "-preset", "fast", "-global_quality", "20"]),
        ("libx264", ["-c:v", "libx264", "-crf", "19", "-preset", DEFAULT_FFMPEG_PRESET])
    ]

    for name, flags in candidates:
        try:
            probe = subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=30", "-t", "0.1", *flags, "-f", "null", "-"],
                capture_output=True,
                timeout=4
            )
            if probe.returncode == 0:
                _OPTIMAL_ENCODER_CACHE = {"name": name, "flags": flags}
                print(f"[+] Hardware video encoding active: {name}")
                return _OPTIMAL_ENCODER_CACHE
        except Exception:
            pass

    _OPTIMAL_ENCODER_CACHE = {
        "name": "libx264",
        "flags": ["-c:v", "libx264", "-crf", "19", "-preset", DEFAULT_FFMPEG_PRESET]
    }
    return _OPTIMAL_ENCODER_CACHE

# Color themes in ASS format (&H00<BB><GG><RR>&)
THEMES = {
    "hormozi_yellow": {
        "name": "Alex Hormozi Yellow",
        "primary": "&H00FFFFFF&",     # White for inactive words
        "highlight": "&H0000FFFF&",   # Neon Yellow for active word (#FFFF00)
        "outline": "&H00000000&",     # Black border
        "shadow": "&H80000000&",      # Semi-translucent black shadow
    },
    "hormozi_green": {
        "name": "Viral Neon Green",
        "primary": "&H00FFFFFF&",
        "highlight": "&H0000FF00&",   # Neon Lime Green (#00FF00)
        "outline": "&H00000000&",
        "shadow": "&H80000000&",
    },
    "cyber_cyan": {
        "name": "Electric Cyan",
        "primary": "&H00FFFFFF&",
        "highlight": "&H00FFFF00&",   # Cyan (#00FFFF in BGR is #FFFF00)
        "outline": "&H00000000&",
        "shadow": "&H80000000&",
    },
    "fire_orange": {
        "name": "Flame Orange",
        "primary": "&H00FFFFFF&",
        "highlight": "&H000077FF&",   # Flame Orange in BGR
        "outline": "&H00000000&",
        "shadow": "&H80000000&",
    },
    "beast_red": {
        "name": "Beast High-Energy Red",
        "primary": "&H00FFFFFF&",
        "highlight": "&H000000FF&",   # Pure Red in BGR
        "outline": "&H00000000&",
        "shadow": "&H80000000&",
    },
    "clean_minimal": {
        "name": "Clean Minimalist White",
        "primary": "&H00CCCCCC&",     # Soft grey
        "highlight": "&H00FFFFFF&",   # Crisp white
        "outline": "&H00111111&",
        "shadow": "&H60000000&",
    }
}


def format_ass_timestamp(seconds: float) -> str:
    """Converts seconds into ASS timestamp format: H:MM:SS.cs (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int(round((seconds - int(seconds)) * 100))
    if centisecs >= 100:
        centisecs = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def create_ass_subtitles(
    words_data: List[Dict[str, Any]],
    output_ass_path: str,
    theme_name: str = "hormozi_yellow",
    font_name: str = "Arial Black",
    font_size: int = 70,
    words_per_chunk: int = 3,
    margin_v: int = 720,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    enable_kinetic_pop: bool = True,
    enable_emoji: bool = True,
    target_language: str = "en"
) -> str:
    """
    Generates an ASS subtitle file with word-by-word active karaoke highlighting,
    kinetic pop bounce animations, and contextual auto-emojis.
    Optionally includes secondary translated bilingual subtitles.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_ass_path)), exist_ok=True)
    theme = THEMES.get(theme_name, THEMES["hormozi_yellow"])

    # Clean punctuation and filter empty entries
    clean_words = []
    for w in words_data:
        text = w["word"].strip()
        if text:
            clean_words.append({
                "word": text.upper(),
                "start": max(0.0, float(w["start"])),
                "end": max(0.0, float(w["end"]))
            })

    if not clean_words:
        raise ValueError("No valid words to generate subtitles for.")

    # Group words into chunks of `words_per_chunk`
    chunks: List[List[Dict[str, Any]]] = []
    current_chunk: List[Dict[str, Any]] = []

    for w in clean_words:
        current_chunk.append(w)
        # Break chunk if size reached or if there's a long pause (> 0.6s)
        if len(current_chunk) >= words_per_chunk:
            chunks.append(current_chunk)
            current_chunk = []
        elif len(current_chunk) > 1 and (w["start"] - current_chunk[-2]["end"]) > 0.6:
            chunks.append(current_chunk[:-1])
            current_chunk = [w]

    if current_chunk:
        chunks.append(current_chunk)

    # Build ASS content
    header = f"""[Script Info]
Title: Alex Hormozi Style Karaoke Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,{font_name},{font_size},{theme['primary']},{theme['highlight']},{theme['outline']},{theme['shadow']},-1,0,0,0,100,100,2,0,1,5,3,2,30,30,{margin_v},1
Style: HormoziTranslated,Arial,42,&H00E2E8F0&,&H00FFFFFF&,&H00000000&,&H80000000&,0,0,0,0,100,100,1,0,1,4,2,2,30,30,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    if target_language and target_language != "en":
        from src.subtitle_translator import build_bilingual_subtitle_events
        dialogue_lines = build_bilingual_subtitle_events(
            chunks=chunks,
            target_lang=target_language,
            theme=theme,
            enable_kinetic_pop=enable_kinetic_pop,
            enable_emoji=enable_emoji,
            format_ass_timestamp_fn=format_ass_timestamp,
            keyword_emojis_map=KEYWORD_EMOJIS
        )
    else:
        dialogue_lines = []
        for chunk in chunks:
            if not chunk:
                continue
            # Chunk duration
            chunk_start = chunk[0]["start"]
            chunk_end = chunk[-1]["end"]

            # For each word in the chunk, emit a dialogue event highlighting that specific word
            for active_idx, active_word in enumerate(chunk):
                word_start = active_word["start"]
                word_end = active_word["end"]

                # If adjacent words overlap or have 0 duration, enforce minimum 0.1s
                if word_end <= word_start:
                    word_end = word_start + 0.15

                # If this is the last word in chunk, extend display to chunk_end + brief buffer
                if active_idx == len(chunk) - 1:
                    display_end = max(word_end, chunk_end)
                else:
                    # Next word's start
                    next_word_start = chunk[active_idx + 1]["start"]
                    display_end = min(max(word_end, word_start + 0.1), next_word_start)

                # Build line text with active word highlighted
                line_parts = []
                for idx, w in enumerate(chunk):
                    w_text = w["word"]
                    if idx == active_idx:
                        # Check for contextual emoji
                        clean_key = re.sub(r"[^\w]", "", w_text).upper()
                        emoji = KEYWORD_EMOJIS.get(clean_key, "") if enable_emoji else ""
                        emoji_str = f" {emoji}" if emoji else ""

                        if enable_kinetic_pop:
                            # Subtle 12% scale pop for active word + highlight color
                            line_parts.append(f"{{\\fscx112\\fscy112\\c{theme['highlight']}}}{w_text}{emoji_str}{{\\fscx100\\fscy100\\c{theme['primary']}}}")
                        else:
                            line_parts.append(f"{{\\c{theme['highlight']}}}{w_text}{emoji_str}{{\\c{theme['primary']}}}")
                    else:
                        line_parts.append(w_text)

                formatted_text = " ".join(line_parts)
                start_str = format_ass_timestamp(word_start)
                end_str = format_ass_timestamp(display_end)

                dialogue_lines.append(
                    f"Dialogue: 0,{start_str},{end_str},Hormozi,,0,0,0,,{formatted_text}"
                )

    full_ass = header + "\n".join(dialogue_lines) + "\n"

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(full_ass)

    print(f"[+] Generated ASS subtitle script: {output_ass_path} ({len(dialogue_lines)} animation frames)")
    return output_ass_path


def burn_subtitles_to_video(
    input_video_path: str,
    ass_subtitle_path: str,
    output_video_path: str,
    preset: Optional[str] = None,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> str:
    """
    Burns ASS subtitles directly into the video stream using FFmpeg's libass filter.
    Audio stream is copied without re-encoding (-c:a copy) to preserve fidelity.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in system PATH.")

    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"Input video not found: {input_video_path}")
    if not os.path.exists(ass_subtitle_path):
        raise FileNotFoundError(f"Subtitle file not found: {ass_subtitle_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
    ffmpeg_preset = preset or DEFAULT_FFMPEG_PRESET

    # Windows-safe path escaping for FFmpeg filtergraph:
    # Use forward slashes and escape the colon after drive letter: C\:/path/to/sub.ass
    safe_ass_path = str(Path(ass_subtitle_path).resolve().as_posix()).replace(":", r"\:")

    filter_str = f"ass='{safe_ass_path}'"
    optimal_enc = get_optimal_video_encoder()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_video_path),
        "-vf", filter_str,
        *optimal_enc["flags"],
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_video_path)
    ]

    print(f"[*] Burning animated karaoke subtitles (encoder={optimal_enc['name']})...")
    print(f"    Source  : {input_video_path}")
    print(f"    Subtitles: {ass_subtitle_path}")
    print(f"    Target  : {output_video_path}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"FFmpeg subtitle burning timed out after {timeout}s on {output_video_path}")

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg subtitle burning failed: {res.stderr}")

    if not os.path.exists(output_video_path) or os.path.getsize(output_video_path) == 0:
        raise RuntimeError(f"Output video missing or empty: {output_video_path}")

    print(f"[SUCCESS] Rendered Viral Short with Captions: {output_video_path} ({os.path.getsize(output_video_path):,} bytes)")
    return output_video_path


def generate_subtitled_short(
    video_9x16_path: str,
    words_json_path: str,
    output_video_path: Optional[str] = None,
    theme: str = "hormozi_yellow",
    font_name: str = "Arial Black",
    font_size: int = 70,
    words_per_chunk: int = 3,
    margin_v: int = 720,
    enable_kinetic_pop: bool = True,
    enable_emoji: bool = True
) -> Dict[str, Any]:
    """
    End-to-end wrapper for Step 6: Takes a 9:16 vertical video and zero-aligned words JSON,
    generates the karaoke ASS file with kinetic pop and auto-emoji, burns the subtitles into the video,
    and returns results.
    """
    with open(words_json_path, "r", encoding="utf-8") as f:
        words_data = json.load(f)

    words_list = words_data.get("words", [])
    if not words_list:
        raise ValueError(f"No word timestamps found in {words_json_path}")

    base_name = Path(video_9x16_path).stem
    temp_ass_path = os.path.join("temp", f"{base_name}_{theme}.ass")

    # 1. Generate ASS karaoke file
    create_ass_subtitles(
        words_data=words_list,
        output_ass_path=temp_ass_path,
        theme_name=theme,
        font_name=font_name,
        font_size=font_size,
        words_per_chunk=words_per_chunk,
        margin_v=margin_v,
        enable_kinetic_pop=enable_kinetic_pop,
        enable_emoji=enable_emoji
    )

    # 2. Determine target video path
    if not output_video_path:
        out_dir = Path(video_9x16_path).parent
        output_video_path = os.path.join(out_dir, f"{base_name}_captions_{theme}.mp4")

    # 3. Burn subtitles into video
    final_video = burn_subtitles_to_video(
        input_video_path=video_9x16_path,
        ass_subtitle_path=temp_ass_path,
        output_video_path=output_video_path
    )

    return {
        "final_video_path": final_video,
        "ass_subtitle_path": temp_ass_path,
        "theme": theme,
        "theme_name": THEMES.get(theme, {}).get("name", theme),
        "font_name": font_name,
        "font_size": font_size,
        "words_count": len(words_list),
        "file_size_bytes": os.path.getsize(final_video)
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dynamic Colored Karaoke Subtitle Generator (Alex Hormozi Style)")
    parser.add_argument("--video", type=str, required=True, help="Path to 9:16 vertical video MP4")
    parser.add_argument("--words", type=str, required=True, help="Path to re-zeroed words JSON from Step 5")
    parser.add_argument("--output", type=str, default=None, help="Path for output captioned MP4")
    parser.add_argument("--theme", type=str, default="hormozi_yellow", choices=list(THEMES.keys()), help="Color theme")
    parser.add_argument("--font", type=str, default="Arial Black", help="Font name")
    parser.add_argument("--font-size", type=int, default=70, help="Font size")
    parser.add_argument("--words-per-chunk", type=int, default=3, help="Words per subtitle line")
    parser.add_argument("--margin-v", type=int, default=720, help="Bottom margin (pixels)")

    args = parser.parse_args()

    print("=" * 60)
    print(" BABY STEP 6: DYNAMIC KARAOKE SUBTITLE GENERATOR")
    print("=" * 60)

    try:
        res = generate_subtitled_short(
            video_9x16_path=args.video,
            words_json_path=args.words,
            output_video_path=args.output,
            theme=args.theme,
            font_name=args.font,
            font_size=args.font_size,
            words_per_chunk=args.words_per_chunk,
            margin_v=args.margin_v
        )

        print("\n" + "=" * 60)
        print(" BABY STEP 6 RENDER SUMMARY")
        print("=" * 60)
        for k, v in res.items():
            print(f"  {k:20}: {v}")
        print("=" * 60)
        print("[SUCCESS] Baby Step 6 completed successfully.")
    except Exception as ex:
        print(f"\n[ERROR] Step 6 failed: {ex}", file=sys.stderr)
        sys.exit(1)
