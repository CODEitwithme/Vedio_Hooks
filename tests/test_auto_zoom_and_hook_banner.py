"""
Automated Test Suite for Dynamic Auto-Zoom (Punch-Cuts) and Top Hook Header Banner Engines.
Verifies interval calculation, filtergraph generation, ASS injection, standalone FFmpeg rendering,
and FastAPI REST endpoints.
"""

import os
import subprocess
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.auto_zoom import calculate_zoom_intervals, build_dynamic_zoom_filter, apply_dynamic_auto_zoom
from src.hook_banner import (
    generate_smart_hook_text,
    generate_hook_banner_ass_elements,
    apply_standalone_hook_banner,
    BANNER_THEMES
)
from src.subtitle_generator import create_ass_subtitles
from src.server import app

client = TestClient(app)


@pytest.fixture(scope="module")
def synthetic_vertical_short(tmp_path_factory):
    """Generates a tiny 5-second 1080x1920 test video for ultra-fast FFmpeg verification."""
    tmp_dir = tmp_path_factory.mktemp("zoom_banner_test")
    video_p = tmp_dir / "synthetic_short.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
        "-t", "5.0",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        str(video_p)
    ]
    res = subprocess.run(cmd, capture_output=True)
    assert res.returncode == 0
    assert video_p.exists()
    return str(video_p)


def test_calculate_zoom_intervals_with_emphasis_keywords():
    """Verifies that punch-cut intervals align with high-impact emphasis words."""
    words = [
        {"word": "Here", "start": 0.5, "end": 0.8},
        {"word": "is", "start": 0.9, "end": 1.1},
        {"word": "the", "start": 1.2, "end": 1.4},
        {"word": "SECRET", "start": 4.2, "end": 4.8},  # Emphasis word
        {"word": "to", "start": 5.0, "end": 5.2},
        {"word": "DISCIPLINE", "start": 8.5, "end": 9.1},  # Emphasis word
    ]
    intervals = calculate_zoom_intervals(words=words, duration_sec=15.0, min_gap_sec=3.5, zoom_duration_sec=2.0)
    assert len(intervals) >= 1
    first_z = intervals[0]
    assert first_z["zoom_scale"] == 1.16
    assert first_z["start"] == 4.2  # Snapped to 'SECRET'
    assert first_z["end"] > first_z["start"]


def test_build_dynamic_zoom_filter_expression():
    """Verifies that FFmpeg filter expression correctly includes crop and scale math."""
    intervals = [
        {"start": 3.5, "end": 5.5, "zoom_scale": 1.16},
        {"start": 9.0, "end": 11.2, "zoom_scale": 1.16}
    ]
    filter_expr = build_dynamic_zoom_filter(intervals, target_width=1080, target_height=1920)
    assert "crop=" in filter_expr
    assert "between(t\\,3.50\\,5.50)" in filter_expr
    assert "between(t\\,9.00\\,11.20)" in filter_expr
    assert "scale=1080:1920:flags=lanczos" in filter_expr


def test_apply_dynamic_auto_zoom_execution(synthetic_vertical_short, tmp_path):
    """Executes FFmpeg dynamic auto-zoom punch-cut on synthetic video."""
    out_p = str(tmp_path / "autozoom_test_out.mp4")
    result = apply_dynamic_auto_zoom(
        input_video_path=synthetic_vertical_short,
        output_video_path=out_p,
        zoom_scale=1.16
    )
    assert result["status"] == "success"
    assert os.path.exists(out_p)
    assert os.path.getsize(out_p) > 0
    assert result["punch_cuts_count"] >= 1


def test_generate_smart_hook_text_by_niche():
    """Verifies algorithmic headline synthesis across different niches."""
    text_mot = generate_smart_hook_text("How to build unstoppable mindset and win", niche="Motivation")
    assert "HOW TO BUILD UNSTOPPABLE" in text_mot

    text_cricket = generate_smart_hook_text("Virat Kohli", niche="Cricket")
    assert "CRICKET" in text_cricket or "RECORD" in text_cricket

    text_fitness = generate_smart_hook_text("Workout", niche="Gym & Fitness")
    assert "WORKOUT" in text_fitness or "DO NOT DO THIS" in text_fitness


def test_generate_hook_banner_ass_elements():
    """Verifies ASS style definition and fade-in/fade-out dialogue event generation."""
    elems = generate_hook_banner_ass_elements(
        hook_text="THE SECRET OF DISCIPLINE",
        theme="hormozi_yellow",
        start_sec=0.0,
        duration_sec=3.5
    )
    assert "Style: HookBanner" in elems["style_def"]
    assert "Dialogue: 2,0:00:00.00,0:00:03.50,HookBanner" in elems["dialogue_def"]
    assert "{\\fad(180,250)}" in elems["dialogue_def"]
    assert "THE SECRET OF DISCIPLINE" in elems["display_text"]


def test_create_ass_subtitles_with_hook_banner(tmp_path):
    """Verifies that create_ass_subtitles injects the HookBanner style and dialogue event."""
    words = [
        {"word": "Discipline", "start": 0.2, "end": 0.8},
        {"word": "equals", "start": 0.9, "end": 1.2},
        {"word": "freedom", "start": 1.3, "end": 1.8}
    ]
    ass_path = str(tmp_path / "test_banner_subs.ass")
    create_ass_subtitles(
        words_data=words,
        output_ass_path=ass_path,
        theme_name="hormozi_yellow",
        hook_banner_text="BRUTAL TRUTH ABOUT SUCCESS",
        hook_banner_theme="hormozi_yellow",
        hook_banner_duration=3.5
    )
    assert os.path.exists(ass_path)
    content = Path(ass_path).read_text(encoding="utf-8")
    assert "Style: HookBanner" in content
    assert "BRUTAL TRUTH ABOUT SUCCESS" in content
    assert "Style: Hormozi," in content


def test_apply_standalone_hook_banner_execution(synthetic_vertical_short, tmp_path):
    """Executes standalone FFmpeg top hook banner overlay on synthetic video."""
    out_p = str(tmp_path / "hook_banner_test_out.mp4")
    result = apply_standalone_hook_banner(
        video_path=synthetic_vertical_short,
        hook_text="STOP SCROLLING RIGHT NOW",
        output_path=out_p,
        theme="beast_red",
        duration_sec=2.5
    )
    assert result["status"] == "success"
    assert os.path.exists(out_p)
    assert os.path.getsize(out_p) > 0
    assert result["hook_text"] == "STOP SCROLLING RIGHT NOW"


def test_api_video_auto_zoom_endpoint(synthetic_vertical_short):
    """Tests POST /api/video/auto-zoom REST endpoint."""
    res = client.post("/api/video/auto-zoom", json={
        "video_path": synthetic_vertical_short,
        "zoom_scale": 1.16
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert os.path.exists(data["output_path"])


def test_api_video_hook_banner_endpoint(synthetic_vertical_short):
    """Tests POST /api/video/hook-banner REST endpoint."""
    res = client.post("/api/video/hook-banner", json={
        "video_path": synthetic_vertical_short,
        "hook_text": "THE #1 UNTOLD TRUTH",
        "theme": "cyber_cyan",
        "duration_sec": 3.0
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert os.path.exists(data["output_path"])
