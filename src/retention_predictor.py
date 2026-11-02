"""
Predictive Virality Heatmap & Second-by-Second Viewer Retention Engine for VedioHooks AI.
Analyzes speech cadence, hook velocity, silence gaps, and keyword density to simulate
an accurate second-by-second audience retention curve R(t) in [0, 100].
"""

import math
from typing import List, Dict, Any, Optional


def calculate_retention_curve(
    words: List[Dict[str, Any]],
    duration_sec: float,
    virality_score: int = 85,
    sample_rate_sec: float = 0.5
) -> Dict[str, Any]:
    """
    Computes the second-by-second viewer retention curve for a video short.

    Args:
        words: List of word timestamp dicts with 'word', 'start', 'end'.
        duration_sec: Total duration of the clip in seconds.
        virality_score: Multi-dimensional virality rating (0-100).
        sample_rate_sec: Time delta between sample points (default 0.5s).

    Returns:
        Dict containing:
        - 'retention_points': List of {'time': float, 'retention': float}
        - 'peak_viral_moment': Dict with 'time' and 'label'
        - 'drop_off_zones': List of risk intervals
        - 'predicted_completion_rate': Estimated % of viewers watching to the end
        - 'avg_wps': Average words per second
    """
    dur = max(2.0, float(duration_sec))
    num_samples = max(4, int(dur / sample_rate_sec) + 1)

    # 1. Base decay curve based on general short-form video retention dynamics
    # Higher virality score flattens the decay curve
    base_decay_rate = 0.015 * (1.0 - (min(98, max(50, virality_score)) / 120.0))

    retention = 100.0
    points = []
    drop_off_zones = []
    peak_moment = {"time": 1.5, "label": "Initial Opening Hook"}
    highest_density_wps = 0.0

    # Calculate moving window words per second
    for i in range(num_samples):
        t = round(i * sample_rate_sec, 2)
        if t > dur:
            break

        # Compute active words in a 2-second moving window around t
        window_start = max(0.0, t - 1.0)
        window_end = min(dur, t + 1.0)
        window_len = max(0.5, window_end - window_start)

        words_in_window = [
            w for w in words
            if float(w.get("start", 0)) < window_end and float(w.get("end", 0)) > window_start
        ]
        wps = len(words_in_window) / window_len

        # Natural retention decay
        step_decay = base_decay_rate * (1.2 if t < 3.0 else 0.8)
        retention = max(25.0, retention - (step_decay * 100 * sample_rate_sec))

        # Velocity and hook boosts
        if t <= 3.0:
            # First 3 seconds: high retention if pace is strong
            if wps >= 2.5:
                retention = min(100.0, retention + 0.5)
        else:
            # Pacing penalty: Slow monotonous speech (< 1.6 WPS) causes audience drop
            if wps < 1.4:
                drop_penalty = 1.2 * sample_rate_sec
                retention = max(20.0, retention - drop_penalty)
                if not drop_off_zones or drop_off_zones[-1]["end"] < t - 0.6:
                    drop_off_zones.append({
                        "start": t,
                        "end": min(dur, t + 1.0),
                        "reason": f"Pacing dip ({wps:.1f} WPS)"
                    })
                else:
                    drop_off_zones[-1]["end"] = min(dur, t + 1.0)
            elif wps >= 3.2:
                # Fast punchy delivery boosts engagement
                retention = min(98.0, retention + 0.35 * sample_rate_sec)

        # Track viral peak
        if wps > highest_density_wps and t > 0.5:
            highest_density_wps = wps
            peak_moment = {
                "time": t,
                "label": f"Peak Energy ({wps:.1f} WPS)"
            }

        points.append({
            "time": t,
            "retention": round(retention, 1),
            "wps": round(wps, 1)
        })

    # Overall completion rate is the final retention point
    completion_rate = points[-1]["retention"] if points else 65.0
    total_words = len(words)
    avg_wps = round(total_words / max(1.0, dur), 2)

    return {
        "retention_points": points,
        "peak_viral_moment": peak_moment,
        "drop_off_zones": drop_off_zones[:3],  # Top 3 risk zones
        "predicted_completion_rate": round(completion_rate, 1),
        "avg_wps": avg_wps,
        "total_words": total_words,
        "duration": round(dur, 2)
    }
