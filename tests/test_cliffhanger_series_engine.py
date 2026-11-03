"""
Comprehensive Test Suite for AI Cliffhanger Series Engine.
Covers:
1. Intelligent Story Detection & Story Arc Generation
2. Dynamic Episode Sizing & Sentence-Aligned Boundary Snapping
3. Advanced Cliffhanger Intelligence (7 Paradigms & 0-100 Scoring)
4. Series Continuity Engine & Series Memory Tracking
5. AI Series Quality Scoring (8 Dimensions & Composite Score)
6. Database Schema, State Persistence, Crash Recovery & Episode Manipulation (Split, Merge, Reorder, Delete)
7. Full FastAPI Series Studio REST API Suite (Auto, Guided, Custom Modes, Export, Rendering)
"""

import os
import sys
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.series_engine import (
    CliffhangerSeriesEngine,
    StoryDetector,
    CliffhangerIntelligenceEngine,
    SeriesContinuityEngine,
    SeriesQualityScorer,
    find_sentence_boundaries,
    snap_to_clean_sentence_boundary,
    CLIFFHANGER_TYPES,
    StoryArc,
    EpisodePlan
)
from src.db import (
    init_db,
    get_db_connection,
    create_series,
    get_series,
    list_series,
    update_series,
    delete_series,
    create_series_episode,
    get_series_episode,
    list_series_episodes,
    update_series_episode,
    delete_series_episode,
    reorder_series_episodes,
    merge_series_episodes,
    split_series_episode,
    update_episode_render_result,
    recover_interrupted_jobs,
    get_database_stats
)
from src.server import app

client = TestClient(app)


# Sample realistic mock transcript data with multiple conversation peaks
MOCK_TRANSCRIPT = {
    "duration": 240.0,
    "total_words": 120,
    "full_text": (
        "I started with absolutely nothing in my bank account. We worked eighteen hours every single day. "
        "Everyone told me it was impossible and that I would fail. But we refused to quit because discipline is everything. "
        "Then suddenly out of nowhere, disaster struck. We lost all our funding in a single afternoon. "
        "I looked at my co-founder and asked, how are we going to survive this? There was only ten dollars left in the account. "
        "Little did we know, a single email was about to change the entire company forever. "
        "A major investor saw our resilience and called us directly. That is how we turned failure into the biggest victory of our lives."
    ),
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 20.0,
            "text": "I started with absolutely nothing in my bank account. We worked eighteen hours every single day.",
            "words": [
                {"word": "I", "start": 0.0, "end": 0.5},
                {"word": "started", "start": 0.5, "end": 1.2},
                {"word": "with", "start": 1.2, "end": 1.5},
                {"word": "absolutely", "start": 1.5, "end": 2.2},
                {"word": "nothing", "start": 2.2, "end": 2.8},
                {"word": "in", "start": 2.8, "end": 3.0},
                {"word": "my", "start": 3.0, "end": 3.3},
                {"word": "bank", "start": 3.3, "end": 3.8},
                {"word": "account.", "start": 3.8, "end": 4.5},
                {"word": "We", "start": 5.2, "end": 5.6},
                {"word": "worked", "start": 5.6, "end": 6.2},
                {"word": "eighteen", "start": 6.2, "end": 7.0},
                {"word": "hours", "start": 7.0, "end": 7.6},
                {"word": "every", "start": 7.6, "end": 8.0},
                {"word": "single", "start": 8.0, "end": 8.5},
                {"word": "day.", "start": 8.5, "end": 9.2}
            ]
        },
        {
            "id": 1,
            "start": 20.5,
            "end": 55.0,
            "text": "Everyone told me it was impossible and that I would fail. But we refused to quit because discipline is everything.",
            "words": [
                {"word": "Everyone", "start": 20.5, "end": 21.2},
                {"word": "told", "start": 21.2, "end": 21.6},
                {"word": "me", "start": 21.6, "end": 21.8},
                {"word": "it", "start": 21.8, "end": 22.0},
                {"word": "was", "start": 22.0, "end": 22.3},
                {"word": "impossible", "start": 22.3, "end": 23.2},
                {"word": "and", "start": 23.2, "end": 23.5},
                {"word": "that", "start": 23.5, "end": 23.8},
                {"word": "I", "start": 23.8, "end": 24.0},
                {"word": "would", "start": 24.0, "end": 24.4},
                {"word": "fail.", "start": 24.4, "end": 25.0},
                {"word": "But", "start": 26.0, "end": 26.3},
                {"word": "we", "start": 26.3, "end": 26.6},
                {"word": "refused", "start": 26.6, "end": 27.3},
                {"word": "to", "start": 27.3, "end": 27.5},
                {"word": "quit", "start": 27.5, "end": 28.0},
                {"word": "because", "start": 28.0, "end": 28.5},
                {"word": "discipline", "start": 28.5, "end": 29.3},
                {"word": "is", "start": 29.3, "end": 29.5},
                {"word": "everything.", "start": 29.5, "end": 30.2}
            ]
        },
        {
            "id": 2,
            "start": 56.0,
            "end": 120.0,
            "text": "Then suddenly out of nowhere, disaster struck. We lost all our funding in a single afternoon. I looked at my co-founder and asked, how are we going to survive this?",
            "words": [
                {"word": "Then", "start": 56.0, "end": 56.4},
                {"word": "suddenly", "start": 56.4, "end": 57.1},
                {"word": "out", "start": 57.1, "end": 57.3},
                {"word": "of", "start": 57.3, "end": 57.5},
                {"word": "nowhere,", "start": 57.5, "end": 58.1},
                {"word": "disaster", "start": 58.1, "end": 58.8},
                {"word": "struck.", "start": 58.8, "end": 59.5},
                {"word": "We", "start": 60.5, "end": 60.8},
                {"word": "lost", "start": 60.8, "end": 61.3},
                {"word": "all", "start": 61.3, "end": 61.6},
                {"word": "our", "start": 61.6, "end": 61.9},
                {"word": "funding", "start": 61.9, "end": 62.5},
                {"word": "in", "start": 62.5, "end": 62.7},
                {"word": "a", "start": 62.7, "end": 62.8},
                {"word": "single", "start": 62.8, "end": 63.3},
                {"word": "afternoon.", "start": 63.3, "end": 64.0},
                {"word": "I", "start": 65.0, "end": 65.2},
                {"word": "looked", "start": 65.2, "end": 65.7},
                {"word": "at", "start": 65.7, "end": 65.9},
                {"word": "my", "start": 65.9, "end": 66.1},
                {"word": "co-founder", "start": 66.1, "end": 66.8},
                {"word": "and", "start": 66.8, "end": 67.0},
                {"word": "asked,", "start": 67.0, "end": 67.5},
                {"word": "how", "start": 67.5, "end": 67.8},
                {"word": "are", "start": 67.8, "end": 68.0},
                {"word": "we", "start": 68.0, "end": 68.2},
                {"word": "going", "start": 68.2, "end": 68.5},
                {"word": "to", "start": 68.5, "end": 68.7},
                {"word": "survive", "start": 68.7, "end": 69.3},
                {"word": "this?", "start": 69.3, "end": 69.8}
            ]
        },
        {
            "id": 3,
            "start": 121.0,
            "end": 240.0,
            "text": "Little did we know, a single email was about to change the entire company forever. A major investor saw our resilience and called us directly. That is how we turned failure into the biggest victory of our lives.",
            "words": [
                {"word": "Little", "start": 121.0, "end": 121.5},
                {"word": "did", "start": 121.5, "end": 121.8},
                {"word": "we", "start": 121.8, "end": 122.0},
                {"word": "know,", "start": 122.0, "end": 122.5},
                {"word": "a", "start": 122.5, "end": 122.7},
                {"word": "single", "start": 122.7, "end": 123.2},
                {"word": "email", "start": 123.2, "end": 123.8},
                {"word": "was", "start": 123.8, "end": 124.0},
                {"word": "about", "start": 124.0, "end": 124.4},
                {"word": "to", "start": 124.4, "end": 124.6},
                {"word": "change", "start": 124.6, "end": 125.1},
                {"word": "the", "start": 125.1, "end": 125.3},
                {"word": "entire", "start": 125.3, "end": 125.8},
                {"word": "company", "start": 125.8, "end": 126.4},
                {"word": "forever.", "start": 126.4, "end": 127.1},
                {"word": "A", "start": 128.0, "end": 128.2},
                {"word": "major", "start": 128.2, "end": 128.6},
                {"word": "investor", "start": 128.6, "end": 129.2},
                {"word": "saw", "start": 129.2, "end": 129.5},
                {"word": "our", "start": 129.5, "end": 129.8},
                {"word": "resilience", "start": 129.8, "end": 130.5},
                {"word": "and", "start": 130.5, "end": 130.8},
                {"word": "called", "start": 130.8, "end": 131.3},
                {"word": "us", "start": 131.3, "end": 131.5},
                {"word": "directly.", "start": 131.5, "end": 132.1},
                {"word": "That", "start": 133.0, "end": 133.3},
                {"word": "is", "start": 133.3, "end": 133.5},
                {"word": "how", "start": 133.5, "end": 133.7},
                {"word": "we", "start": 133.7, "end": 133.9},
                {"word": "turned", "start": 133.9, "end": 134.3},
                {"word": "failure", "start": 134.3, "end": 134.8},
                {"word": "into", "start": 134.8, "end": 135.1},
                {"word": "the", "start": 135.1, "end": 135.3},
                {"word": "biggest", "start": 135.3, "end": 135.8},
                {"word": "victory", "start": 135.8, "end": 136.4},
                {"word": "of", "start": 136.4, "end": 136.6},
                {"word": "our", "start": 136.6, "end": 136.8},
                {"word": "lives.", "start": 136.8, "end": 137.5}
            ]
        }
    ]
}


# =====================================================================
# --- UNIT TESTS: STORY DETECTION & BOUNDARIES ---
# =====================================================================

def test_story_detector_identifies_arc_and_dynamic_episodes():
    """Verifies story detection extracts topic, arc, turning point, and episode count."""
    detector = StoryDetector()
    arcs = detector.analyze_transcript_arcs(MOCK_TRANSCRIPT)

    assert len(arcs) >= 1
    arc = arcs[0]
    assert arc.title != ""
    assert arc.main_topic != ""
    assert arc.recommended_episodes >= 2
    assert arc.beginning != ""
    assert arc.turning_point != ""
    assert arc.resolution != ""
    assert len(arc.episode_sequence) == arc.recommended_episodes


def test_sentence_boundary_snapping_prevents_mid_sentence_cuts():
    """Verifies boundary detection snaps accurately to punctuation and never cuts a word."""
    all_words = []
    for s in MOCK_TRANSCRIPT["segments"]:
        all_words.extend(s["words"])

    boundaries = find_sentence_boundaries(MOCK_TRANSCRIPT["segments"], all_words)
    assert len(boundaries) > 0

    # Test target time 27.0s (in the middle of 'refused to quit')
    # It must snap to either 25.0s (fail.) or 30.2s (everything.)
    snapped = snap_to_clean_sentence_boundary(
        target_time=27.0,
        all_words=all_words,
        boundaries=boundaries,
        min_time=20.0,
        max_time=35.0
    )

    matching_word = next((w for w in all_words if abs(w["end"] - snapped) < 0.05), None)
    assert matching_word is not None
    assert matching_word["word"].endswith((".", "!", "?"))


# =====================================================================
# --- UNIT TESTS: CLIFFHANGER INTELLIGENCE ENGINE ---
# =====================================================================

def test_cliffhanger_unanswered_question_detection():
    """Verifies unanswered questions receive high curiosity scores."""
    engine = CliffhangerIntelligenceEngine()
    words = [
        {"word": "I", "start": 65.0, "end": 65.2},
        {"word": "asked,", "start": 67.0, "end": 67.5},
        {"word": "how", "start": 67.5, "end": 67.8},
        {"word": "are", "start": 67.8, "end": 68.0},
        {"word": "we", "start": 68.0, "end": 68.2},
        {"word": "going", "start": 68.2, "end": 68.5},
        {"word": "to", "start": 68.5, "end": 68.7},
        {"word": "survive", "start": 68.7, "end": 69.3},
        {"word": "this?", "start": 69.3, "end": 69.8}
    ]
    eval_res = engine.analyze_ending_window(words, "how are we going to survive this?", is_series_final=False)
    assert eval_res.cliffhanger_type == "unanswered_question"
    assert eval_res.cliffhanger_score >= 80
    assert eval_res.curiosity_score >= 80
    assert "episode" in eval_res.next_teaser.lower()


def test_cliffhanger_final_episode_resolution():
    """Verifies that final episode does not create artificial suspense, but delivers satisfying resolution."""
    engine = CliffhangerIntelligenceEngine()
    words = [
        {"word": "That", "start": 133.0, "end": 133.3},
        {"word": "is", "start": 133.3, "end": 133.5},
        {"word": "how", "start": 133.5, "end": 133.7},
        {"word": "we", "start": 133.7, "end": 133.9},
        {"word": "won.", "start": 133.9, "end": 134.3}
    ]
    eval_res = engine.analyze_ending_window(words, "That is how we won.", is_series_final=True)
    assert eval_res.cliffhanger_type == "resolution"
    assert eval_res.cliffhanger_score >= 90
    assert "Resolution" in eval_res.cliffhanger_text


# =====================================================================
# --- UNIT TESTS: SERIES CONTINUITY & QUALITY SCORING ---
# =====================================================================

def test_series_continuity_and_quality_score():
    """Verifies SeriesMemory tracks established knowledge and quality score returns composite rating."""
    engine = CliffhangerSeriesEngine()
    plan = engine.generate_series(MOCK_TRANSCRIPT, account_id="acc_motivation", desired_episodes=3)

    assert plan.episode_count == 3
    assert len(plan.episodes) == 3
    assert plan.quality_score >= 75

    # Episode 1 should connect to Episode 2
    ep1 = plan.episodes[0]
    ep2 = plan.episodes[1]
    ep3 = plan.episodes[2]

    assert ep1.is_final_episode is False
    assert ep2.is_final_episode is False
    assert ep3.is_final_episode is True

    assert ep1.opening_hook != ""
    assert ep1.cliffhanger_text != ""
    assert ep3.cliffhanger_type == "resolution"

    # Series memory verification
    assert plan.series_memory.series_title == plan.title
    assert len(plan.series_memory.established_facts) >= 3


# =====================================================================
# --- DATABASE & PERSISTENCE TESTS ---
# =====================================================================

def test_database_series_crud_and_episode_operations(tmp_path):
    """Verifies full lifecycle of series in SQLite: create, retrieve, split, merge, reorder, and delete."""
    init_db()
    
    # 1. Create series with 3 episodes
    series_data = {
        "title": "Rise of a Founder",
        "description": "An entrepreneurial struggle.",
        "main_topic": "Entrepreneurship",
        "account_id": "acc_motivation",
        "episode_count": 3,
        "episodes": [
            {
                "episode_number": 1,
                "title": "Starting from Zero",
                "opening_hook": "We had no money.",
                "start_time": 0.0,
                "end_time": 30.0,
                "cliffhanger_text": "Then disaster struck.",
                "cliffhanger_score": 88
            },
            {
                "episode_number": 2,
                "title": "The Crisis",
                "opening_hook": "We lost everything.",
                "start_time": 30.0,
                "end_time": 65.0,
                "cliffhanger_text": "Would anyone help?",
                "cliffhanger_score": 90
            },
            {
                "episode_number": 3,
                "title": "The Breakthrough",
                "opening_hook": "The phone rang.",
                "start_time": 65.0,
                "end_time": 100.0,
                "cliffhanger_text": "Victory achieved.",
                "is_final_episode": 1,
                "cliffhanger_score": 95
            }
        ]
    }

    series_id = create_series(series_data)
    assert series_id.startswith("series_")

    # 2. Retrieve series
    s = get_series(series_id)
    assert s is not None
    assert s["title"] == "Rise of a Founder"
    assert len(s["episodes"]) == 3
    assert s["episodes"][0]["title"] == "Starting from Zero"

    ep1_id = s["episodes"][0]["id"]
    ep2_id = s["episodes"][1]["id"]
    ep3_id = s["episodes"][2]["id"]

    # 3. Update episode title and timestamps
    success = update_series_episode(ep1_id, {"title": "Part 1: The Dark Beginning", "start_time": 0.0, "end_time": 32.0})
    assert success is True
    updated_ep1 = get_series_episode(ep1_id)
    assert updated_ep1["title"] == "Part 1: The Dark Beginning"
    assert updated_ep1["duration"] == 32.0

    # 4. Split episode 2 at 45.0s
    split_res = split_series_episode(series_id, ep2_id, split_time=45.0)
    assert split_res is not None
    s_after_split = get_series(series_id)
    assert s_after_split["episode_count"] == 4
    assert len(s_after_split["episodes"]) == 4

    # 5. Merge episode 1 and episode 2
    merged_id = merge_series_episodes(series_id, ep1_id, ep2_id)
    assert merged_id == ep1_id
    s_after_merge = get_series(series_id)
    assert s_after_merge["episode_count"] == 3

    # 6. Reorder episodes
    new_order = [s_after_merge["episodes"][1]["id"], s_after_merge["episodes"][0]["id"], s_after_merge["episodes"][2]["id"]]
    reorder_res = reorder_series_episodes(series_id, new_order)
    assert reorder_res is True
    s_reordered = get_series(series_id)
    assert s_reordered["episodes"][0]["id"] == new_order[0]
    assert s_reordered["episodes"][-1]["is_final_episode"] == 1

    # 7. Render status updates
    update_episode_render_result(ep1_id, render_status="ready", rendered_video_path="output/test_render.mp4", render_id=1)
    ep_check = get_series_episode(ep1_id)
    assert ep_check["render_status"] == "ready"
    assert ep_check["rendered_video_path"] == "output/test_render.mp4"

    # 8. Crash recovery
    conn = get_db_connection()
    with conn:
        conn.execute("UPDATE series SET status = 'rendering' WHERE id = ?", (series_id,))
        conn.execute("UPDATE series_episodes SET render_status = 'rendering' WHERE id = ?", (ep1_id,))
    conn.close()

    recover_interrupted_jobs()
    s_recovered = get_series(series_id)
    assert s_recovered["status"] == "ready"
    ep_recovered = get_series_episode(ep1_id)
    assert ep_recovered["render_status"] == "pending"

    # 9. Cleanup delete
    del_res = delete_series(series_id)
    assert del_res is True
    assert get_series(series_id) is None


# =====================================================================
# --- FASTAPI REST API INTEGRATION TESTS ---
# =====================================================================

def test_api_series_endpoints(tmp_path):
    """Tests all REST endpoints for Series Studio."""
    # Write temp transcript file
    trans_file = tmp_path / "test_api_transcript.json"
    with open(trans_file, "w", encoding="utf-8") as f:
        json.dump(MOCK_TRANSCRIPT, f)

    # 1. Analyze Arcs
    res_arcs = client.post("/api/series/analyze-arcs", json={"transcript_path": str(trans_file)})
    assert res_arcs.status_code == 200
    arcs_data = res_arcs.json()
    assert arcs_data["arcs_found"] >= 1
    first_arc = arcs_data["story_arcs"][0]

    # 2. Generate Series (Auto Mode)
    res_gen = client.post("/api/series/generate", json={
        "transcript_path": str(trans_file),
        "account_id": "acc_motivation",
        "generation_mode": "auto"
    })
    assert res_gen.status_code == 200
    series_obj = res_gen.json()
    series_id = series_obj["id"]
    assert series_id.startswith("series_")
    assert len(series_obj["episodes"]) >= 2

    # 3. List Series
    res_list = client.get("/api/series")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1

    # 4. Get Series by ID
    res_get = client.get(f"/api/series/{series_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == series_id

    # 5. Update Episode
    ep0_id = series_obj["episodes"][0]["id"]
    res_up = client.post(f"/api/series/{series_id}/episodes/{ep0_id}/update", json={
        "title": "Custom Episode 1 Title",
        "opening_hook": "Viral opening hook here!"
    })
    assert res_up.status_code == 200
    assert res_up.json()["episode"]["title"] == "Custom Episode 1 Title"

    # 6. Regenerate Hook
    res_hook = client.post(f"/api/series/{series_id}/episodes/{ep0_id}/regenerate-hook")
    assert res_hook.status_code == 200
    assert "opening_hook" in res_hook.json()

    # 7. Regenerate Cliffhanger
    res_cliff = client.post(f"/api/series/{series_id}/episodes/{ep0_id}/regenerate-cliffhanger")
    assert res_cliff.status_code == 200
    assert "cliffhanger_score" in res_cliff.json()

    # 8. Export Series Package
    res_exp = client.get(f"/api/series/{series_id}/export")
    assert res_exp.status_code == 200
    exp_data = res_exp.json()
    assert exp_data["series_id"] == series_id
    assert len(exp_data["episodes"]) >= 2

    # 9. Delete Series
    res_del = client.delete(f"/api/series/{series_id}")
    assert res_del.status_code == 200
    assert client.get(f"/api/series/{series_id}").status_code == 404


def test_api_dashboard_html_contains_series_studio():
    """Verifies that the Commercial SaaS Dashboard HTML contains Series Studio navigation and view panel."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "Series Studio" in html
    assert 'id="tab-series-studio"' in html
    assert "AI Cliffhanger Series Engine" in html
    assert "visualTimelineFlow" in html
    assert "seriesCreatorModal" in html


def test_render_series_episode_pipeline(tmp_path):
    """
    Verifies that the series video rendering pipeline slices footage,
    burns episodic [EP X/N] banners, Hormozi karaoke subtitles,
    reframes into 9:16 vertical output, and records into database tables.
    """
    import subprocess
    from src.pipeline_worker import render_series_episode_job
    from src.ingest import get_media_info

    # 1. Create a 5-second test video with audio using FFmpeg
    test_video = str(tmp_path / "test_series_src.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "5.0",
        "-c:v", "libx264", "-c:a", "aac",
        test_video
    ], check=True, capture_output=True)

    # 2. Create matching transcript JSON
    test_transcript = str(tmp_path / "test_series_trans.json")
    t_data = {
        "audio_path": test_video,
        "duration": 5.0,
        "total_words": 10,
        "full_text": "This is part one of the story. Notice what happens next.",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 4.5,
                "text": "This is part one of the story. Notice what happens next.",
                "words": [
                    {"word": "This", "start": 0.0, "end": 0.4},
                    {"word": "is", "start": 0.4, "end": 0.7},
                    {"word": "part", "start": 0.7, "end": 1.1},
                    {"word": "one", "start": 1.1, "end": 1.5},
                    {"word": "of", "start": 1.5, "end": 1.7},
                    {"word": "the", "start": 1.7, "end": 1.9},
                    {"word": "story.", "start": 1.9, "end": 2.4},
                    {"word": "Notice", "start": 2.6, "end": 3.0},
                    {"word": "what", "start": 3.0, "end": 3.3},
                    {"word": "happens", "start": 3.3, "end": 3.7},
                    {"word": "next.", "start": 3.7, "end": 4.2}
                ]
            }
        ]
    }
    with open(test_transcript, "w", encoding="utf-8") as f:
        json.dump(t_data, f)

    # 3. Create Job and Series
    conn = get_db_connection()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO jobs (id, source_type, source_path, title, duration, resolution, status, transcript_json_path)
            VALUES ('test_series_job', 'file', ?, 'Test Series Source Video', 5.0, '1280x720', 'ready', ?)
        """, (test_video, test_transcript))
    conn.close()

    series_data = {
        "title": "Mastering the Art of Discipline",
        "description": "A high impact multi-part test series.",
        "main_topic": "Discipline",
        "job_id": "test_series_job",
        "account_id": "acc_motivation",
        "episode_count": 2,
        "episodes": [
            {
                "episode_number": 1,
                "title": "The First Step",
                "opening_hook": "This is part one.",
                "start_time": 0.0,
                "end_time": 3.5,
                "cliffhanger_text": "Notice what happens next.",
                "cliffhanger_type": "suspense",
                "cliffhanger_score": 85,
                "is_final_episode": 0
            },
            {
                "episode_number": 2,
                "title": "The Victory",
                "opening_hook": "Part two outcome.",
                "start_time": 3.5,
                "end_time": 5.0,
                "cliffhanger_text": "Resolution reached.",
                "cliffhanger_type": "resolution",
                "cliffhanger_score": 95,
                "is_final_episode": 1
            }
        ]
    }
    series_id = create_series(series_data)
    episodes = list_series_episodes(series_id)
    ep1_id = episodes[0]["id"]

    # 4. Render Episode 1
    render_res = render_series_episode_job(
        series_id=series_id,
        episode_id=ep1_id,
        crop_mode="center",
        theme="hormozi_yellow",
        enable_ducking=False,
        enable_jumpcuts=False,
        enable_sfx=False,
        enable_auto_zoom=False
    )

    out_video = render_res["video_path"]
    assert os.path.exists(out_video)
    assert os.path.getsize(out_video) > 0

    # 5. Verify 9:16 vertical resolution
    info = get_media_info(out_video)
    assert info["width"] == 1080
    assert info["height"] == 1920

    # 6. Verify SQLite record
    ep1_db = get_series_episode(ep1_id)
    assert ep1_db["render_status"] == "ready"
    assert ep1_db["rendered_video_path"] == out_video
    assert ep1_db["render_id"] is not None

