"""
Video Slicing & 9:16 Vertical Cropping Module for AI Viral Shorts Maker.
Extracts precision sub-clips using FFmpeg with keyframe re-alignment,
reframes horizontal 16:9 footage into vertical 9:16 (1080x1920),
and normalizes word-level transcript timestamps relative to the cut.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ingest import get_media_info
from src.subtitle_generator import get_optimal_video_encoder

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "300"))
DEFAULT_FFMPEG_PRESET = os.environ.get("FFMPEG_PRESET", "fast")


def slice_word_timestamps(
    full_transcript_path: str,
    start_sec: float,
    end_sec: float,
    output_sliced_json: Optional[str] = None
) -> Dict[str, Any]:
    """
    Filters words and segments to only those falling between start_sec and end_sec,
    and shifts timestamps so t=0.0 corresponds to start_sec (relative timestamps for Step 6 subtitles).
    """
    with open(full_transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sliced_words: List[Dict[str, Any]] = []
    sliced_text_parts: List[str] = []

    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            w_start = w["start"]
            w_end = w["end"]
            # Check if word falls within clip bounds
            if w_end >= start_sec and w_start <= end_sec:
                # Re-zero timestamp relative to cut
                rel_start = max(0.0, round(w_start - start_sec, 3))
                rel_end = max(0.0, round(w_end - start_sec, 3))
                sliced_words.append({
                    "word": w["word"],
                    "start": rel_start,
                    "end": rel_end,
                    "probability": w.get("probability", 1.0)
                })
                sliced_text_parts.append(w["word"])

    result = {
        "source_transcript": str(full_transcript_path),
        "cut_start": start_sec,
        "cut_end": end_sec,
        "clip_duration": round(end_sec - start_sec, 3),
        "total_words": len(sliced_words),
        "text": " ".join(sliced_text_parts),
        "words": sliced_words
    }

    if output_sliced_json:
        os.makedirs(os.path.dirname(os.path.abspath(output_sliced_json)), exist_ok=True)
        with open(output_sliced_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[+] Re-zeroed subtitle transcript saved: {output_sliced_json}")

    return result


def slice_and_crop_video(
    video_path: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
    crop_mode: str = "center",
    target_width: int = 1080,
    target_height: int = 1920,
    x_offset_ratio: float = 0.5,  # 0.5 = center, will be dynamically adjusted by face tracking in Step 7
    normalize_audio: bool = False,
    preset: Optional[str] = None,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> str:
    """
    Slices a video between start_sec and end_sec, reframing into 9:16 (target_width x target_height).

    Modes:
      - 'center': Direct crop of the 9:16 vertical center region, scaled to 1080x1920.
      - 'blur_fill': Blurred, scaled background with centered foreground clip.
      - 'fit': Fits 16:9 horizontally into 9:16 with black padding top & bottom.

    Returns:
      Absolute path to the rendered 9:16 video.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in system PATH.")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    duration = end_sec - start_sec
    if duration <= 0:
        raise ValueError(f"Invalid duration: {duration}s (start={start_sec}, end={end_sec})")

    print(f"[*] Slicing video: {start_sec:05.2f}s -> {end_sec:05.2f}s (Duration: {duration:.2f}s)")
    print(f"[*] Framing mode: '{crop_mode}', Output: {target_width}x{target_height} (9:16 vertical)")

    # Build FFmpeg video filtergraph based on crop_mode
    if crop_mode == "center":
        # Calculate crop width for 9:16 aspect ratio: crop_w = ih * (9 / 16)
        # x offset = (iw - crop_w) * x_offset_ratio
        # Ensure dimensions are even numbers (trunc(val/2)*2)
        filter_str = (
            f"crop=w='min(iw,trunc(ih*9/16/2)*2)':h='ih':"
            f"x='(iw-ow)*{x_offset_ratio}':y=0,"
            f"scale={target_width}:{target_height}:flags=lanczos"
        )
        vf_args = ["-vf", filter_str]

    elif crop_mode == "blur_fill":
        # Blurred background + centered foreground
        filter_str = (
            f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height},"
            f"boxblur=20:5[bg];"
            f"[0:v]scale={target_width}:-2:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]"
        )
        vf_args = ["-filter_complex", filter_str, "-map", "[outv]", "-map", "0:a?"]

    elif crop_mode == "fit":
        # Letterbox fit with black bars
        filter_str = (
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
        )
        vf_args = ["-vf", filter_str]

    elif crop_mode == "split_stack":
        # 2-speaker vertical split: Left speaker on top 50%, Right speaker on bottom 50%
        filter_str = (
            f"[0:v]crop=w=iw/2:h=ih:x=0:y=0,scale={target_width}:{target_height // 2}:flags=lanczos[top];"
            f"[0:v]crop=w=iw/2:h=ih:x=iw/2:y=0,scale={target_width}:{target_height // 2}:flags=lanczos[bottom];"
            f"[top][bottom]vstack[outv]"
        )
        vf_args = ["-filter_complex", filter_str, "-map", "[outv]", "-map", "0:a?"]
    else:
        raise ValueError(f"Unknown crop_mode: {crop_mode}")

    # Accurate seek and re-encoding:
    # -ss before -i for fast seek to keyframe, followed by precise cut
    ffmpeg_preset = preset or DEFAULT_FFMPEG_PRESET
    audio_flags = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
    if normalize_audio:
        audio_flags.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])

    optimal_enc = get_optimal_video_encoder()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", str(video_path),
        *vf_args,
        *optimal_enc["flags"],
        "-pix_fmt", "yuv420p",
        *audio_flags,
        "-movflags", "+faststart",
        str(output_path)
    ]

    print(f"[*] Executing FFmpeg 9:16 rendering (crop={crop_mode}, encoder={optimal_enc['name']}, loudnorm={normalize_audio})...")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"FFmpeg slicing/cropping timed out after {timeout} seconds on {output_path}")

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg slicing/cropping failed: {res.stderr}")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"Output video missing or empty: {output_path}")

    # Inspect resulting video with ffprobe
    out_info = get_media_info(output_path)
    print(f"[SUCCESS] Rendered 9:16 Short: {output_path}")
    print(f"          Resolution: {out_info['width']}x{out_info['height']} ({out_info['width']/out_info['height']:.3f} AR)")
    print(f"          Duration  : {out_info['duration']:.2f}s | Size: {os.path.getsize(output_path):,} bytes")

    return output_path


def calculate_jumpcuts(
    words: List[Dict[str, Any]],
    max_silence_sec: float = 0.35,
    speech_padding_sec: float = 0.06
) -> Tuple[List[Tuple[float, float]], List[Dict[str, Any]]]:
    """
    Computes kept audio/video intervals and shifts subtitle word timestamps forward
    to eliminate dead-air pauses > max_silence_sec.
    """
    if not words or len(words) < 2:
        return [], words

    segments = []
    seg_start = max(0.0, words[0]["start"] - speech_padding_sec)

    for i in range(1, len(words)):
        prev_end = words[i - 1]["end"]
        cur_start = words[i]["start"]
        gap = cur_start - prev_end
        if gap > max_silence_sec:
            segments.append((round(seg_start, 3), round(prev_end + speech_padding_sec, 3)))
            seg_start = max(0.0, cur_start - speech_padding_sec)

    segments.append((round(seg_start, 3), round(words[-1]["end"] + speech_padding_sec, 3)))

    # If only one segment encompasses everything, no silence gaps were removed
    if len(segments) <= 1:
        return [], words

    # Calculate shifted word timestamps
    shifted_words = []
    for w in words:
        orig_s = w["start"]
        orig_e = w["end"]
        removed_before = 0.0
        for idx in range(len(segments) - 1):
            gap_s = segments[idx][1]
            gap_e = segments[idx + 1][0]
            if orig_s >= gap_e:
                removed_before += (gap_e - gap_s)
            elif orig_s > gap_s:
                removed_before += (orig_s - gap_s)

        shifted_words.append({
            "word": w["word"],
            "start": round(max(0.0, orig_s - removed_before), 3),
            "end": round(max(0.0, orig_e - removed_before), 3),
            "probability": w.get("probability", 1.0)
        })

    return segments, shifted_words


def apply_dead_air_removal(
    video_path: str,
    output_path: str,
    segments: List[Tuple[float, float]],
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> str:
    """
    Executes single-pass frame-accurate FFmpeg select/aselect jump-cut removal of dead air.
    """
    if not segments:
        return video_path

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in PATH.")

    between_clauses = [f"between(t\\,{s}\\,{e})" for s, e in segments]
    combined_between = "+".join(between_clauses)
    vf_filter = f"select={combined_between},setpts=N/FRAME_RATE/TB"
    af_filter = f"aselect={combined_between},asetpts=N/SR/TB"

    optimal_enc = get_optimal_video_encoder()

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(video_path),
        "-vf", vf_filter,
        "-af", af_filter,
        *optimal_enc["flags"],
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-movflags", "+faststart",
        str(output_path)
    ]

    print(f"[*] Applying frame-accurate jump-cut dead-air removal ({len(segments)} speech segments)...")
    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg jump-cut failed: {res.stderr.decode('utf-8', errors='ignore')}")

    return output_path


def process_viral_clip_to_short(
    video_path: str,
    transcript_path: str,
    clip_info: Dict[str, Any],
    output_dir: str = "output",
    crop_mode: str = "center"
) -> Dict[str, Any]:
    """
    End-to-end function for Step 5: takes video + transcript + a selected clip,
    slices the video, converts to 9:16, and produces the zero-aligned transcript.
    """
    os.makedirs(output_dir, exist_ok=True)
    clip_id = clip_info.get("clip_id", 1)
    start_t = float(clip_info["start_time"])
    end_t = float(clip_info["end_time"])

    base_name = Path(video_path).stem
    safe_title = f"{base_name}_clip{clip_id}_{crop_mode}"
    out_video_path = os.path.join(output_dir, f"{safe_title}_9x16.mp4")
    out_sub_json = os.path.join(output_dir, f"{safe_title}_words.json")

    # 1. Render 9:16 Video
    slice_and_crop_video(
        video_path=video_path,
        start_sec=start_t,
        end_sec=end_t,
        output_path=out_video_path,
        crop_mode=crop_mode
    )

    # 2. Slice Transcript Timestamps (t=0 aligned)
    sliced_transcript = slice_word_timestamps(
        full_transcript_path=transcript_path,
        start_sec=start_t,
        end_sec=end_t,
        output_sliced_json=out_sub_json
    )

    return {
        "clip_id": clip_id,
        "title": clip_info.get("title", f"Clip #{clip_id}"),
        "video_9x16_path": out_video_path,
        "sliced_transcript_path": out_sub_json,
        "start_time": start_t,
        "end_time": end_t,
        "duration": round(end_t - start_t, 2),
        "crop_mode": crop_mode,
        "total_words": sliced_transcript["total_words"],
        "speech_text": sliced_transcript["text"]
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Video Slicing & 9:16 Vertical Cropping Tool")
    parser.add_argument("--video", type=str, required=True, help="Path to source video MP4")
    parser.add_argument("--transcript", type=str, required=True, help="Path to transcript JSON")
    parser.add_argument("--clips-report", type=str, default=None, help="Path to viral clips report JSON")
    parser.add_argument("--clip-id", type=int, default=1, help="Clip index from report to render (default: 1)")
    parser.add_argument("--start", type=float, default=None, help="Explicit start timestamp (seconds)")
    parser.add_argument("--end", type=float, default=None, help="Explicit end timestamp (seconds)")
    parser.add_argument("--crop-mode", type=str, choices=["center", "blur_fill", "fit"], default="center", help="Framing mode")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")

    args = parser.parse_args()

    print("=" * 60)
    print(" BABY STEP 5: VIDEO SLICING & 9:16 VERTICAL CROPPING")
    print("=" * 60)

    # Determine clip timing
    if args.start is not None and args.end is not None:
        clip_dict = {
            "clip_id": 1,
            "title": "Custom Timestamp Slice",
            "start_time": args.start,
            "end_time": args.end
        }
    elif args.clips_report and os.path.exists(args.clips_report):
        with open(args.clips_report, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        clips = report_data.get("clips", [])
        selected = next((c for c in clips if c.get("clip_id") == args.clip_id), None)
        if not selected:
            if clips:
                selected = clips[0]
            else:
                raise ValueError("No clips found in clips report.")
        clip_dict = selected
    else:
        raise ValueError("Must provide either --clips-report or both --start and --end.")

    try:
        res = process_viral_clip_to_short(
            video_path=args.video,
            transcript_path=args.transcript,
            clip_info=clip_dict,
            output_dir=args.output_dir,
            crop_mode=args.crop_mode
        )

        print("\n" + "=" * 60)
        print(" BABY STEP 5 RENDER RESULTS")
        print("=" * 60)
        for k, v in res.items():
            print(f"  {k:22}: {v}")
        print("=" * 60)
        print("[SUCCESS] Baby Step 5 completed successfully.")
    except Exception as ex:
        print(f"\n[ERROR] Step 5 failed: {ex}", file=sys.stderr)
        sys.exit(1)
