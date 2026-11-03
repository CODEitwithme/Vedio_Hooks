"""
Comprehensive Unit & Integration Test Suite for VedioHooks AI.
Tests database, ingestion, transcription, virality scoring, subtitle generation, and FastAPI endpoints.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure workspace root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.server import app
from src.db import init_db, create_job, get_job, list_jobs, update_job_progress, save_rendered_short
from src.ingest import sanitize_filename, get_media_info
from src.virality_selector import score_candidate_text, snap_timestamp_to_words
from src.subtitle_generator import format_ass_timestamp, create_ass_subtitles, THEMES

client = TestClient(app)


def test_sanitize_filename():
    """Verifies that special characters and spaces are safely stripped."""
    assert sanitize_filename("Test: Video? / Title*") == "Test_Video__Title"
    assert sanitize_filename("A" * 100) == "A" * 50


def test_ass_timestamp_formatting():
    """Verifies centisecond timestamp precision for ASS format."""
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(1.5) == "0:00:01.50"
    assert format_ass_timestamp(65.25) == "0:01:05.25"
    assert format_ass_timestamp(3665.12) == "1:01:05.12"


def test_virality_scoring():
    """Verifies algorithmic hook, engagement, and virality scoring."""
    text_with_hook = "Why do 99% of people fail at their dreams? Because they fear hard work."
    score, h_rat, e_rat, f_rat, reas = score_candidate_text(text_with_hook, 15.0)
    assert score >= 75
    assert h_rat >= 8
    assert "hook" in reas.lower()


def test_word_timestamp_snapping():
    """Verifies word boundary snapping prevents mid-syllable cutting."""
    words = [
        {"word": "Hello", "start": 1.05, "end": 1.45},
        {"word": "world", "start": 1.50, "end": 1.95},
        {"word": "welcome", "start": 2.00, "end": 2.50}
    ]
    # Snapping 1.1s should snap to 1.05s
    assert snap_timestamp_to_words(1.1, words, mode="start") == 1.05
    # Snapping 1.9s should snap to 1.95s
    assert snap_timestamp_to_words(1.9, words, mode="end") == 1.95


def test_database_crud():
    """Verifies SQLite job and render operations."""
    import uuid
    test_id = f"test_crud_{uuid.uuid4().hex[:8]}"
    create_job(test_id, "url", "https://example.com/video")
    
    job = get_job(test_id)
    assert job is not None
    assert job["id"] == test_id
    assert job["status"] == "queued"
    
    update_job_progress(test_id, status="transcribing", progress=50, current_step="Transcribing...")
    updated = get_job(test_id)
    assert updated["status"] == "transcribing"
    assert updated["progress"] == 50

    render_id = save_rendered_short(
        job_id=test_id,
        clip_id=1,
        title="Test Short",
        start_time=0.0,
        end_time=15.0,
        virality_score=85,
        crop_mode="smart_face",
        theme="hormozi_yellow",
        video_path="output/test_video.mp4"
    )
    assert render_id > 0
    refreshed = get_job(test_id)
    assert len(refreshed["renders"]) >= 1


def test_ass_file_generation(tmp_path):
    """Verifies that create_ass_subtitles outputs a valid ASS file with karaoke tags."""
    words = [
        {"word": "NEVER", "start": 0.0, "end": 0.4},
        {"word": "GIVE", "start": 0.4, "end": 0.8},
        {"word": "UP", "start": 0.8, "end": 1.2}
    ]
    ass_path = str(tmp_path / "test.ass")
    create_ass_subtitles(words, ass_path, theme_name="hormozi_yellow", words_per_chunk=3)
    
    assert os.path.exists(ass_path)
    with open(ass_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "[Script Info]" in content
    assert "Dialogue:" in content
    assert THEMES["hormozi_yellow"]["highlight"] in content


# --- FastAPI Endpoint Integration Tests ---

def test_api_health():
    """Tests /api/health endpoint."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["ffmpeg"] is True


def test_api_jobs_list():
    """Tests /api/jobs returns list of jobs."""
    res = client.get("/api/jobs")
    assert res.status_code == 200
    data = res.json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


def test_api_job_detail_existing():
    """Tests /api/jobs/{id} on seeded David Goggins job."""
    res = client.get("/api/jobs/TLKxdTmk-zc")
    assert res.status_code == 200
    job = res.json()
    assert job["id"] == "TLKxdTmk-zc"
    assert "David Goggins" in job["title"]
    assert len(job["clips"]) >= 1
    assert len(job["renders"]) >= 1


def test_api_job_not_found():
    """Tests 404 on nonexistent job."""
    res = client.get("/api/jobs/nonexistent_job_999")
    assert res.status_code == 404


def test_dashboard_html_serves():
    """Tests that root endpoint / returns the full HTML single-page dashboard."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "VedioHooks" in res.text
    assert "Smart Face Tracking" in res.text


def test_media_streaming_range():
    """Tests HTTP 206 Range video streaming on rendered short."""
    media_url = "/api/media/output/David_Goggins_Face_Centered_Captions_Short.mp4"
    # Test full request
    res = client.get(media_url)
    assert res.status_code in [200, 206]
    
    # Test partial byte range request
    headers = {"Range": "bytes=0-1024"}
    res_range = client.get(media_url, headers=headers)
    assert res_range.status_code == 206
    assert "Content-Range" in res_range.headers
    assert res_range.headers["Content-Length"] == "1025"


def test_context_clarity_and_dangling_detection():
    """Verifies standalone context clarity evaluation and dangling speech detection."""
    from src.virality_selector import is_dangling_start_segment, evaluate_candidate_multidimensional

    # Dangling indicators
    assert is_dangling_start_segment("and that's why we had to do it") is True
    assert is_dangling_start_segment("he told me that he would not sign") is True
    assert is_dangling_start_segment("because when we tried that") is True
    assert is_dangling_start_segment("so they decided to leave") is True

    # Standalone setups
    assert is_dangling_start_segment("Why do 99% of people quit in their first year?") is False
    assert is_dangling_start_segment("The biggest mistake most founders make is ignoring retention.") is False

    # Context score evaluation
    eval_setup = evaluate_candidate_multidimensional(
        "Why do 99% of people fail to achieve their dreams? Because they fear hard work. You must fight through the pain.",
        duration=15.0
    )
    assert eval_setup["context_score"] >= 85

    eval_dangling = evaluate_candidate_multidimensional(
        "and so he told them that it was over and they could not do anything about it anymore",
        duration=15.0
    )
    assert eval_dangling["context_score"] < eval_setup["context_score"]


def test_heuristic_pre_roll_backward_expansion():
    """Verifies that heuristic_virality_selector rolls back to include host question anchor."""
    from src.virality_selector import heuristic_virality_selector

    mock_transcript = {
        "duration": 50.0,
        "full_text": "Interviewer: What was the pivotal moment in your career? Speaker: When I lost my job I realized I had to build my own business. That changed everything forever.",
        "segments": [
            {"start": 0.0, "end": 6.0, "text": "What was the pivotal moment in your career?"},
            {"start": 6.2, "end": 18.0, "text": "When I lost my job I realized I had to build my own business."},
            {"start": 18.2, "end": 28.0, "text": "That changed everything forever and we never looked back."}
        ]
    }
    rep = heuristic_virality_selector(mock_transcript, min_duration=10.0, max_duration=35.0)
    assert len(rep.clips) >= 1
    top_clip = rep.clips[0]
    # Verify that the clip started at 0.0s to include the question anchor
    assert top_clip.start_time <= 1.0
    assert "pivotal moment" in top_clip.full_quote.lower() or "what was" in top_clip.full_quote.lower()


def test_smart_hook_context_extraction_from_clip():
    """Verifies smart context banner extraction from clip questions and keywords."""
    from src.hook_banner import generate_smart_hook_text

    banner = generate_smart_hook_text(
        title="Viral Short #1: Clip",
        niche="Motivation",
        clip_text="Why do 99% of people fail at their dreams? Because they give up early."
    )
    assert "WHY DO 99%" in banner or "FAIL" in banner

