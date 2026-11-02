"""
Sound Design Beat-Sync Engine for VedioHooks AI Media Factory.
Detects audio rhythmic transients, musical downbeats, and tempo (BPM)
to synchronize subtitle kinetic pop animations and visual cutaways to the rhythm.
"""

import os
import re
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np


def extract_audio_pcm(video_or_audio_path: str, duration: float = 30.0) -> tuple[np.ndarray, int]:
    """Extracts raw mono PCM float32 audio using FFmpeg."""
    sample_rate = 22050
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(video_or_audio_path),
        "-t", str(duration),
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=15)
    if proc.returncode != 0 or len(proc.stdout) == 0:
        # Fallback to synthetic silent array
        return np.zeros(sample_rate * 2, dtype=np.float32), sample_rate

    pcm = np.frombuffer(proc.stdout, dtype=np.float32)
    return pcm, sample_rate


def detect_audio_beats(
    video_or_audio_path: str,
    max_duration: float = 45.0,
    sensitivity: float = 1.3
) -> Dict[str, Any]:
    """
    Detects rhythmic downbeats, tempo (BPM), and high-energy transient spikes
    using spectral flux and onset envelope analysis with NumPy.
    """
    pcm, sr = extract_audio_pcm(video_or_audio_path, duration=max_duration)
    if len(pcm) < sr:
        return {"bpm": 120, "beats": [round(i * 0.5, 2) for i in range(10)], "energy_peaks": []}

    # Frame-based RMS energy envelope
    hop_length = int(sr * 0.04)  # 40ms frame
    frame_length = int(sr * 0.08)  # 80ms window
    
    num_frames = (len(pcm) - frame_length) // hop_length
    if num_frames <= 0:
        return {"bpm": 120, "beats": [0.5, 1.0, 1.5, 2.0], "energy_peaks": []}

    envelope = []
    times = []
    for i in range(num_frames):
        start = i * hop_length
        frame = pcm[start:start + frame_length]
        rms = np.sqrt(np.mean(frame**2) + 1e-9)
        envelope.append(rms)
        times.append(start / sr)

    envelope = np.array(envelope)
    # Moving average threshold for dynamic peak picking
    window = max(5, int(sr * 0.5 / hop_length))
    moving_avg = np.convolve(envelope, np.ones(window) / window, mode='same')
    
    threshold = moving_avg * sensitivity
    peaks = (envelope > threshold) & (envelope > 0.02)

    beat_times = []
    min_dist_frames = int(0.28 / (hop_length / sr))  # Min 280ms between beats (<= 214 BPM)
    last_beat_idx = -min_dist_frames

    for i in range(len(peaks)):
        if peaks[i] and (i - last_beat_idx) >= min_dist_frames:
            beat_times.append(round(times[i], 3))
            last_beat_idx = i

    # Estimate BPM from inter-beat intervals
    bpm = 120
    if len(beat_times) >= 4:
        diffs = np.diff(beat_times)
        valid_diffs = diffs[(diffs >= 0.25) & (diffs <= 1.2)]
        if len(valid_diffs) > 0:
            median_interval = np.median(valid_diffs)
            bpm = int(round(60.0 / median_interval))
            # Clamp to typical vertical video music tempo
            if bpm < 75:
                bpm *= 2
            elif bpm > 175:
                bpm //= 2

    return {
        "bpm": bpm,
        "beat_count": len(beat_times),
        "beats": beat_times,
        "confidence": "high" if len(beat_times) > 8 else "medium",
        "average_interval_sec": round(60.0 / bpm, 3)
    }


def align_word_timestamps_to_beats(
    words: List[Dict[str, Any]],
    beats: List[float],
    snap_window_ms: float = 140.0
) -> List[Dict[str, Any]]:
    """
    Rhythmically aligns subtitle word start timestamps to the nearest musical downbeat
    if the word begins within `snap_window_ms` of a beat.
    """
    if not beats or not words:
        return words

    snap_sec = snap_window_ms / 1000.0
    aligned = []

    for w in words:
        w_copy = dict(w)
        w_start = w["start"]

        # Find closest beat
        closest_beat = min(beats, key=lambda b: abs(b - w_start))
        if abs(closest_beat - w_start) <= snap_sec:
            # Snap start to beat for rhythmic pop
            w_copy["start"] = round(closest_beat, 3)
            w_copy["beat_snapped"] = True
            # Maintain minimum positive duration
            if w_copy.get("end", 0.0) <= w_copy["start"]:
                w_copy["end"] = round(w_copy["start"] + 0.15, 3)
        else:
            w_copy["beat_snapped"] = False

        aligned.append(w_copy)

    return aligned
