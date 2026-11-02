"""
Automated Audio Ducking & Niche Ambient Music Engine for VedioHooks AI.
Applies broadcast-grade sidechain compression ducking: automatically attenuates
background music by ~14dB whenever speech is detected, and swells music gently during pauses.
Supports custom MP3/WAV tracks or 100% free offline procedural ambient synthesis.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ingest import get_media_info

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "300"))

# Procedural synth configurations per niche for 100% offline royalty-free music
NICHE_SYNTH_PROFILES: Dict[str, Dict[str, Any]] = {
    "Motivation": {
        "frequencies": [110, 165, 220],
        "weights": "0.5 0.35 0.25",
        "volume": 0.18,
        "description": "Deep stoic contemplative harmonic pad"
    },
    "Cricket": {
        "frequencies": [146, 220, 330],
        "weights": "0.45 0.35 0.3",
        "volume": 0.20,
        "description": "Dynamic sports storytelling resonance"
    },
    "AI & Study": {
        "frequencies": [130, 195, 260],
        "weights": "0.4 0.3 0.2",
        "volume": 0.15,
        "description": "Calming lo-fi study ambient drone"
    },
    "Gym & Fitness": {
        "frequencies": [65, 98, 130],
        "weights": "0.6 0.4 0.3",
        "volume": 0.22,
        "description": "Heavy driving sub-bass rhythm pad"
    },
    "Common / General": {
        "frequencies": [130, 175, 260],
        "weights": "0.45 0.35 0.2",
        "volume": 0.16,
        "description": "Warm curiosity harmonic bed"
    }
}


NICHE_ID_TO_NAME: Dict[str, str] = {
    "acc_motivation": "Motivation",
    "acc_cricket": "Cricket",
    "acc_ai_study": "AI & Study",
    "acc_fitness": "Gym & Fitness",
    "acc_common": "Common / General"
}


def generate_procedural_ambient_music(
    duration_sec: float,
    niche: str = "Motivation",
    niche_id: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Generates a 100% free, royalty-free procedural ambient soundtrack matching the clip duration.
    Uses FFmpeg's built-in audio synthesis without requiring any external audio assets.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in PATH.")

    effective_niche = niche
    if niche_id and niche_id in NICHE_ID_TO_NAME:
        effective_niche = NICHE_ID_TO_NAME[niche_id]

    profile = NICHE_SYNTH_PROFILES.get(effective_niche, NICHE_SYNTH_PROFILES["Motivation"])
    freqs = profile["frequencies"]
    dur = max(2.0, float(duration_sec))

    if not output_path:
        os.makedirs("temp", exist_ok=True)
        safe_niche = effective_niche.lower().replace(" ", "_").replace("&", "and")
        output_path = f"temp/ambient_{safe_niche}_{int(dur)}s.m4a"

    inputs = []
    for f in freqs:
        inputs.extend(["-f", "lavfi", "-i", f"sine=frequency={f}:duration={dur}"])

    filter_complex = f"[0:a][1:a][2:a]amix=inputs=3:weights={profile['weights']},volume={profile['volume']}[outa]"

    is_wav = str(output_path).lower().endswith(".wav")
    codec_args = ["-c:a", "pcm_s16le"] if is_wav else ["-c:a", "aac", "-b:a", "128k"]

    cmd = [
        ffmpeg_bin, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        *codec_args,
        "-ar", "44100",
        str(output_path)
    ]

    res = subprocess.run(cmd, capture_output=True, timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f"Procedural ambient synthesis failed: {res.stderr.decode('utf-8', errors='ignore')}")

    return output_path


def get_niche_music_track(niche: str, duration_sec: float) -> str:
    """
    Locates an optional custom MP3/WAV in assets/music/, or generates a procedural ambient track.
    """
    safe_niche = niche.lower().replace(" ", "_").replace("&", "and")
    assets_dir = Path("assets") / "music"

    candidates = [
        assets_dir / f"{safe_niche}.mp3",
        assets_dir / f"{safe_niche}.wav",
        assets_dir / "ambient.mp3",
        assets_dir / "background.mp3"
    ]

    for c in candidates:
        if c.exists() and c.stat().st_size > 1000:
            return str(c.resolve())

    # Generate procedural ambient track
    return generate_procedural_ambient_music(duration_sec=duration_sec, niche=niche)


def apply_audio_ducking(
    speech_video_path: str,
    output_video_path: str,
    niche: str = "Motivation",
    niche_id: Optional[str] = None,
    custom_music_path: Optional[str] = None,
    ambient_music_path: Optional[str] = None,
    music_mix_weight: float = 0.22,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> str:
    """
    Applies real-time sidechain compression audio ducking.
    The background music volume is automatically compressed down by ~14dB whenever speech occurs,
    and swells gracefully during silent pauses.

    Uses stream copy for video (-c:v copy) to achieve fast rendering (<0.3 seconds).
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in PATH.")

    if not os.path.exists(speech_video_path):
        raise FileNotFoundError(f"Source video not found: {speech_video_path}")

    media_info = get_media_info(speech_video_path)
    duration = media_info.get("duration", 30.0)

    effective_niche = niche
    if niche_id and niche_id in NICHE_ID_TO_NAME:
        effective_niche = NICHE_ID_TO_NAME[niche_id]

    # 1. Acquire background music track
    resolved_music = ambient_music_path or custom_music_path
    if resolved_music and os.path.exists(resolved_music):
        bg_music = resolved_music
    else:
        bg_music = get_niche_music_track(niche=effective_niche, duration_sec=duration)

    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)

    # 2. Sidechain compression ducking filtergraph:
    # [1:a] (music) is ducked using [0:a] (speech) as control signal:
    # threshold=0.08 triggers attenuation when speech is present
    # ratio=6 gives ~14dB gain reduction
    # attack=20ms (fast drop when talking starts)
    # release=350ms (smooth swell during pauses)
    ducking_filter = (
        f"[1:a][0:a]sidechaincompress=threshold=0.08:ratio=6:attack=20:release=350[ducked];"
        f"[0:a][ducked]amix=inputs=2:weights=1.0 {music_mix_weight}[outa]"
    )

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(speech_video_path),
        "-stream_loop", "-1", "-i", str(bg_music),
        "-filter_complex", ducking_filter,
        "-map", "0:v",
        "-map", "[outa]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-shortest",
        "-movflags", "+faststart",
        str(output_video_path)
    ]

    print(f"[*] Applying sidechain audio ducking (niche={niche}, music={Path(bg_music).name})...")
    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"Audio ducking failed: {res.stderr.decode('utf-8', errors='ignore')}")

    if not os.path.exists(output_video_path) or os.path.getsize(output_video_path) == 0:
        raise RuntimeError(f"Ducked video output missing or empty: {output_video_path}")

    print(f"[SUCCESS] Audio Ducking applied -> {output_video_path}")
    return output_video_path
