"""
Hardware Acceleration Auto-Negotiation Engine for VedioHooks AI Media Factory.
Automatically probes FFmpeg GPU encoders (NVIDIA NVENC, AMD AMF, Intel QSV,
Windows MediaFoundation) and gracefully falls back to CPU libx264.
"""

import os
import subprocess
from typing import Dict, Any, List, Optional

# Module-level cache so we don't re-probe on every render
_CACHED_ENCODER_INFO: Optional[Dict[str, Any]] = None


def test_encoder_viability(encoder_name: str) -> bool:
    """Tests whether an encoder actually succeeds on this machine with a micro-frame."""
    os.makedirs("temp", exist_ok=True)
    test_out = "temp/hw_test_probe.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=1",
        "-t", "0.1",
        "-c:v", encoder_name,
        test_out
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=5)
        success = (proc.returncode == 0) and os.path.exists(test_out) and (os.path.getsize(test_out) > 0)
        if os.path.exists(test_out):
            try:
                os.remove(test_out)
            except OSError:
                pass
        return success
    except Exception:
        return False


def detect_best_video_encoder(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Probes available hardware encoders in priority order and returns optimal encoding arguments.
    """
    global _CACHED_ENCODER_INFO
    if _CACHED_ENCODER_INFO and not force_refresh:
        return _CACHED_ENCODER_INFO

    # Priority candidate order
    candidates = [
        {
            "encoder": "h264_nvenc",
            "device": "NVIDIA NVENC",
            "hw": True,
            "args": ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"]
        },
        {
            "encoder": "h264_amf",
            "device": "AMD AMF",
            "hw": True,
            "args": ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cbr"]
        },
        {
            "encoder": "h264_qsv",
            "device": "Intel QuickSync (QSV)",
            "hw": True,
            "args": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "23"]
        },
        {
            "encoder": "h264_mf",
            "device": "Windows MediaFoundation",
            "hw": True,
            "args": ["-c:v", "h264_mf", "-rate_control", "cbr"]
        },
        {
            "encoder": "libx264",
            "device": "CPU Software (libx264)",
            "hw": False,
            "args": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
        }
    ]

    chosen = candidates[-1]  # Default to libx264
    for cand in candidates:
        if test_encoder_viability(cand["encoder"]):
            chosen = cand
            break

    _CACHED_ENCODER_INFO = chosen
    return chosen


def get_ffmpeg_encoding_args() -> List[str]:
    """Returns the list of optimal FFmpeg encoding arguments for video output."""
    info = detect_best_video_encoder()
    return list(info["args"])
