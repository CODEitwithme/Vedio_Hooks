"""
Ingestion & Audio Extraction Module for AI Long Video to Viral Shorts Maker.
Handles downloading videos (via yt-dlp) or processing local video files,
extracting exact media metadata via ffprobe, and extracting 16kHz mono WAV audio
optimized for Whisper transcription.
"""

import os
import sys
import json
import shutil
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import yt_dlp


DEFAULT_FFPROBE_TIMEOUT = int(os.environ.get("FFPROBE_TIMEOUT_SEC", "60"))
DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "300"))


def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe for filenames across OS platforms."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = clean.replace(" ", "_")
    return clean[:50] if len(clean) > 50 else clean


def get_media_info(file_path: str, timeout: int = DEFAULT_FFPROBE_TIMEOUT) -> Dict[str, Any]:
    """
    Inspects a media file using ffprobe and extracts duration, resolution,
    frame rate, and audio stream specifications with timeout protection.
    """
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise RuntimeError("ffprobe not found in system PATH.")

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        probe_data = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"ffprobe timed out after {timeout} seconds inspecting {file_path}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed for {file_path}: {e.stderr}")

    info = {
        "file_path": str(file_path),
        "duration": float(probe_data.get("format", {}).get("duration", 0.0)),
        "size_bytes": int(probe_data.get("format", {}).get("size", 0)),
        "width": None,
        "height": None,
        "fps": None,
        "has_video": False,
        "has_audio": False,
        "audio_codec": None,
        "audio_sample_rate": None,
        "audio_channels": None,
    }

    for stream in probe_data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and not info["has_video"]:
            info["has_video"] = True
            info["width"] = int(stream.get("width", 0))
            info["height"] = int(stream.get("height", 0))
            # calculate fps from r_frame_rate
            r_frame_rate = stream.get("r_frame_rate", "30/1")
            try:
                num, den = map(int, r_frame_rate.split("/"))
                info["fps"] = round(num / den, 2) if den != 0 else 30.0
            except Exception:
                info["fps"] = 30.0
        elif codec_type == "audio" and not info["has_audio"]:
            info["has_audio"] = True
            info["audio_codec"] = stream.get("codec_name")
            info["audio_sample_rate"] = int(stream.get("sample_rate", 0))
            info["audio_channels"] = int(stream.get("channels", 0))

    return info


def extract_audio_wav(
    video_path: str,
    output_wav_path: str,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT,
    force_recompute: bool = False
) -> str:
    """
    Extracts audio from video file to 16kHz mono 16-bit PCM WAV,
    the format natively required by Whisper/Faster-Whisper.
    Reuses existing valid WAV if present to eliminate redundant decoding.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in system PATH.")

    # Cache check: if valid WAV file already exists (> 1024 bytes), reuse it!
    if not force_recompute and os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 1024:
        print(f"[+] Reusing existing intermediate 16kHz WAV: {output_wav_path} ({os.path.getsize(output_wav_path):,} bytes)")
        return output_wav_path

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-y",               # overwrite output file without asking
        "-i", str(video_path),
        "-vn",              # disable video recording
        "-acodec", "pcm_s16le", # 16-bit linear PCM
        "-ar", "16000",     # 16 kHz sample rate (Whisper standard)
        "-ac", "1",         # mono channel
        str(output_wav_path)
    ]

    print(f"[*] Extracting audio with FFmpeg to 16kHz mono WAV: {output_wav_path}")
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"FFmpeg audio extraction timed out after {timeout} seconds on {video_path}")

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {process.stderr}")

    if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
        raise RuntimeError(f"Extracted audio file is missing or empty: {output_wav_path}")

    print(f"[SUCCESS] Audio extracted successfully ({os.path.getsize(output_wav_path):,} bytes).")
    return output_wav_path


def download_video(url: str, output_dir: str = "temp") -> Dict[str, Any]:
    """
    Downloads a video from YouTube or supported platforms using yt-dlp.
    Selects best MP4 video up to 1080p and extracts 16kHz WAV audio.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    ydl_opts = {
        # Limit to 1080p max to optimize bandwidth & processing speed
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(id)s_%(title).40s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": True,
    }

    print(f"[*] Fetching metadata for URL: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        video_filename = ydl.prepare_filename(info_dict)
        # Ensure extension is .mp4 after merge
        base, _ = os.path.splitext(video_filename)
        expected_mp4 = f"{base}.mp4"
        final_video_path = expected_mp4 if os.path.exists(expected_mp4) else video_filename

    title = info_dict.get("title", "Unknown Title")
    video_id = info_dict.get("id", "video")
    print(f"[SUCCESS] Downloaded video: '{title}' -> {final_video_path}")

    # Audio extraction target
    wav_path = os.path.join(output_dir, f"{video_id}_audio_16k.wav")
    extract_audio_wav(final_video_path, wav_path)

    # Inspect media info
    video_info = get_media_info(final_video_path)
    audio_info = get_media_info(wav_path)

    return {
        "title": title,
        "video_id": video_id,
        "video_path": final_video_path,
        "audio_path": wav_path,
        "duration": video_info["duration"],
        "resolution": f"{video_info['width']}x{video_info['height']}",
        "fps": video_info["fps"],
        "audio_spec": f"{audio_info['audio_sample_rate']}Hz, {audio_info['audio_channels']}ch ({audio_info['audio_codec']})"
    }


def process_local_file(file_path: str, output_dir: str = "temp") -> Dict[str, Any]:
    """
    Processes an existing local video file: verifies stream integrity
    and extracts the 16kHz mono WAV for Whisper.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Local file does not exist: {file_path}")

    os.makedirs(output_dir, exist_ok=True)
    video_info = get_media_info(file_path)

    base_name = Path(file_path).stem
    safe_name = sanitize_filename(base_name)
    wav_path = os.path.join(output_dir, f"{safe_name}_audio_16k.wav")

    extract_audio_wav(file_path, wav_path)
    audio_info = get_media_info(wav_path)

    return {
        "title": base_name,
        "video_id": safe_name,
        "video_path": str(file_path),
        "audio_path": wav_path,
        "duration": video_info["duration"],
        "resolution": f"{video_info['width']}x{video_info['height']}",
        "fps": video_info["fps"],
        "audio_spec": f"{audio_info['audio_sample_rate']}Hz, {audio_info['audio_channels']}ch ({audio_info['audio_codec']})"
    }


def create_synthetic_test_video(output_dir: str = "temp", duration_sec: int = 5) -> str:
    """
    Generates a synthetic 1080p test video with a moving timestamp and audio beep tone.
    Used for automated offline verification of ingestion and FFmpeg pipelines.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found.")

    os.makedirs(output_dir, exist_ok=True)
    test_video_path = os.path.join(output_dir, "synthetic_test_clip.mp4")

    # Generate a 1920x1080 30fps video with sine wave audio
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_sec}:size=1920x1080:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_sec}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        test_video_path
    ]
    print(f"[*] Generating synthetic test video ({duration_sec}s, 1080p)...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate synthetic video: {res.stderr}")

    print(f"[SUCCESS] Synthetic video generated at: {test_video_path}")
    return test_video_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingestion & Audio Extraction Test Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, help="YouTube or web video URL to download")
    group.add_argument("--file", type=str, help="Path to local video file")
    group.add_argument("--test-synthetic", action="store_true", help="Generate and test with a synthetic clip")
    parser.add_argument("--output-dir", type=str, default="temp", help="Directory for output files")

    args = parser.parse_args()

    print("=" * 60)
    print(" BABY STEP 2: INGESTION & AUDIO EXTRACTION")
    print("=" * 60)

    try:
        if args.test_synthetic:
            synth_video = create_synthetic_test_video(args.output_dir, duration_sec=5)
            result = process_local_file(synth_video, args.output_dir)
        elif args.file:
            result = process_local_file(args.file, args.output_dir)
        elif args.url:
            result = download_video(args.url, args.output_dir)

        print("\n" + "=" * 60)
        print(" INGESTION & EXTRACTION RESULTS")
        print("=" * 60)
        for k, v in result.items():
            print(f"  {k:15}: {v}")
        print("=" * 60)
        print("[SUCCESS] Baby Step 2 completed successfully.")
    except Exception as ex:
        print(f"\n[ERROR] Ingestion failed: {ex}", file=sys.stderr)
        sys.exit(1)
