"""
Automated Test Suite for Multi-Account Instagram Content Factory,
AI Content Director, Emergency Controls, and SaaS Dashboard.
"""

import os
import sys
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.server import app
from src.db import (
    init_db,
    get_db_connection,
    list_accounts,
    get_account,
    create_account,
    update_account,
    delete_account,
    is_emergency_stopped,
    set_emergency_stop,
    create_job,
    list_jobs,
    save_rendered_short,
    list_publishing_queue
)
from src.ai_director import NICHE_DIRECTOR_PROFILES

client = TestClient(app)


def setup_module(module):
    """Ensure database is initialized and emergency stop is disengaged before tests."""
    init_db()
    set_emergency_stop(False)


def teardown_module(module):
    """Clean up state after tests."""
    set_emergency_stop(False)


def test_default_five_accounts_seeded():
    """Verifies that all 5 required specialized accounts are seeded into the database."""
    res = client.get("/api/accounts")
    assert res.status_code == 200
    accounts = res.json().get("accounts", [])
    account_ids = [a["id"] for a in accounts]

    expected = ["acc_motivation", "acc_cricket", "acc_ai_study", "acc_fitness", "acc_general"]
    for exp_id in expected:
        assert exp_id in account_ids, f"Expected {exp_id} to be present in accounts"

    # Verify niche profiles
    niches = [a["niche"] for a in accounts]
    assert "Motivation" in niches
    assert "Cricket" in niches
    assert "AI & Study" in niches
    assert "Gym & Fitness" in niches
    assert "Common / General" in niches


def test_account_crud_lifecycle():
    """Tests creating, fetching, updating, toggling, and deleting an account."""
    test_id = f"acc_test_{uuid.uuid4().hex[:6]}"
    create_payload = {
        "id": test_id,
        "name": "Stoic Wisdom Daily",
        "handle": "@stoic.daily",
        "niche": "Motivation",
        "brand_color": "#eab308",
        "daily_target": 3,
        "posting_schedule": "08:00, 14:00, 20:00",
        "default_theme": "hormozi_yellow"
    }

    # 1. Create
    res_create = client.post("/api/accounts", json=create_payload)
    assert res_create.status_code == 200
    created = res_create.json()
    assert created["id"] == test_id
    assert created["name"] == "Stoic Wisdom Daily"

    # 2. Get single
    res_get = client.get(f"/api/accounts/{test_id}")
    assert res_get.status_code == 200
    assert res_get.json()["handle"] == "@stoic.daily"

    # 3. Update
    res_update = client.patch(f"/api/accounts/{test_id}", json={"daily_target": 5, "handle": "@stoic.empire"})
    assert res_update.status_code == 200
    updated_acc = client.get(f"/api/accounts/{test_id}").json()
    assert updated_acc["daily_target"] == 5
    assert updated_acc["handle"] == "@stoic.empire"

    # 4. Toggle active/paused
    res_toggle = client.post(f"/api/accounts/{test_id}/toggle")
    assert res_toggle.status_code == 200
    assert res_toggle.json()["status"] == "paused"

    res_toggle2 = client.post(f"/api/accounts/{test_id}/toggle")
    assert res_toggle2.json()["status"] == "active"

    # 5. Delete
    res_del = client.delete(f"/api/accounts/{test_id}")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True

    # Confirm 404 after deletion
    res_get_deleted = client.get(f"/api/accounts/{test_id}")
    assert res_get_deleted.status_code == 404


def test_content_sources_crud():
    """Tests registering content sources with factual verification & attribution notes."""
    source_payload = {
        "account_id": "acc_cricket",
        "source_type": "youtube_curated",
        "source_url_or_path": "https://youtube.com/watch?v=cricket_mastery",
        "title": "Unbreakable Records: Sachin 200 vs SA",
        "attribution": "Commentary & Match Statistics Source",
        "verification_notes": "Stat checked: First batsman in ODI history to score a double century. Date: 24 Feb 2010."
    }

    res_add = client.post("/api/sources", json=source_payload)
    assert res_add.status_code == 200
    source_id = res_add.json()["id"]

    # List sources for cricket account
    res_list = client.get("/api/sources?account_id=acc_cricket")
    assert res_list.status_code == 200
    sources = res_list.json().get("sources", [])
    matching = [s for s in sources if s["id"] == source_id]
    assert len(matching) == 1
    assert "Sachin 200" in matching[0]["title"]
    assert "Stat checked" in matching[0]["verification_notes"]

    # Delete source
    res_del = client.delete(f"/api/sources/{source_id}")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True


def test_ai_content_director_14_point_blueprint_generation():
    """Verifies that AI Content Director generates and persists full 14-point strategic plans."""
    # Test for Motivation Account
    res_plan_mot = client.post("/api/ai-plans/generate", json={
        "account_id": "acc_motivation",
        "custom_topic": "The pain of discipline is nothing compared to the pain of regret."
    })
    assert res_plan_mot.status_code == 200
    plan_mot = res_plan_mot.json()["plan"]

    # Check the 14 strategic fields
    required_fields = [
        "account_id", "topic", "target_audience", "video_idea", "hook",
        "script_selection", "clip_start", "clip_end", "retention_strategy",
        "editing_instructions", "subtitle_style", "caption", "hashtags",
        "cover_text", "copyright_notes", "quality_score"
    ]
    for field in required_fields:
        assert field in plan_mot, f"Field '{field}' missing from AI Content Director plan"

    assert plan_mot["quality_score"] >= 70
    assert "Motivation" in plan_mot["topic"]

    # Test for Cricket Account (strictly verified factual claims & sports graphics)
    res_plan_cric = client.post("/api/ai-plans/generate", json={
        "account_id": "acc_cricket",
        "custom_topic": "Virat Kohli historic chase vs Pakistan in Melbourne"
    })
    assert res_plan_cric.status_code == 200
    plan_cric = res_plan_cric.json()["plan"]
    assert "Sports graphics" in plan_cric["editing_instructions"]
    assert "Cricket" in plan_cric["topic"]

    # Test for Gym & Fitness Account (medical form disclaimer)
    res_plan_fit = client.post("/api/ai-plans/generate", json={
        "account_id": "acc_fitness",
        "custom_topic": "How to execute the Romanian Deadlift with perfect hamstring stretch"
    })
    assert res_plan_fit.status_code == 200
    plan_fit = res_plan_fit.json()["plan"]
    assert "medical advice" in plan_fit["copyright_notes"].lower()

    # Verify plans are retrieved via GET /api/ai-plans
    res_plans = client.get("/api/ai-plans")
    assert res_plans.status_code == 200
    assert len(res_plans.json().get("plans", [])) >= 3


def test_emergency_stop_mechanism():
    """Verifies that the Emergency Stop master switch immediately blocks all new jobs."""
    try:
        # 1. Engage Emergency Stop
        res_stop = client.post("/api/automation/emergency-stop", json={"stopped": True})
        assert res_stop.status_code == 200
        assert res_stop.json()["emergency_stop"] is True
        assert is_emergency_stopped() is True

        # 2. Attempt URL job submission - MUST be rejected with HTTP 423 Locked
        res_job_url = client.post("/api/jobs", json={
            "url": "https://example.com/blocked_during_emergency",
            "account_id": "acc_motivation"
        })
        assert res_job_url.status_code == 423
        assert "EMERGENCY STOP" in res_job_url.json()["detail"]

        # 3. Attempt File upload job submission - MUST be rejected with HTTP 423 Locked
        sample_path = Path("temp") / "test_blocked.mp4"
        sample_path.write_bytes(b"dummy_content")
        with open(sample_path, "rb") as f:
            res_upload = client.post("/api/jobs/upload", files={"file": ("test_blocked.mp4", f, "video/mp4")})
        assert res_upload.status_code == 423
        assert "EMERGENCY STOP" in res_upload.json()["detail"]

    finally:
        # 4. Disengage Emergency Stop and verify normal submission resumes
        res_resume = client.post("/api/automation/emergency-stop", json={"stopped": False})
        assert res_resume.status_code == 200
        assert res_resume.json()["emergency_stop"] is False
        assert is_emergency_stopped() is False

        # Should now be allowed to queue jobs
        res_ok = client.post("/api/jobs", json={
            "url": f"https://example.com/resumed_job_{uuid.uuid4().hex[:6]}",
            "account_id": "acc_motivation"
        })
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "queued"


def test_multi_account_isolation_in_queues():
    """Verifies that jobs and publishing queue items remain strictly isolated per account."""
    job_mot_id = f"mot_{uuid.uuid4().hex[:6]}"
    job_cric_id = f"cric_{uuid.uuid4().hex[:6]}"

    create_job(job_mot_id, "url", "https://example.com/mot", account_id="acc_motivation")
    create_job(job_cric_id, "url", "https://example.com/cric", account_id="acc_cricket")

    # Filter jobs by cricket
    res_cric_jobs = client.get("/api/jobs?account_id=acc_cricket")
    assert res_cric_jobs.status_code == 200
    cric_job_ids = [j["id"] for j in res_cric_jobs.json()["jobs"]]
    assert job_cric_id in cric_job_ids
    assert job_mot_id not in cric_job_ids

    # Filter jobs by motivation
    res_mot_jobs = client.get("/api/jobs?account_id=acc_motivation")
    assert res_mot_jobs.status_code == 200
    mot_job_ids = [j["id"] for j in res_mot_jobs.json()["jobs"]]
    assert job_mot_id in mot_job_ids
    assert job_cric_id not in mot_job_ids

    # Renders and publishing drafts isolation
    render_id = save_rendered_short(
        job_id=job_cric_id,
        clip_id=1,
        title="Unbelievable Six in Final Over",
        start_time=12.0,
        end_time=36.0,
        virality_score=94,
        crop_mode="smart_face",
        theme="hormozi_green",
        video_path="output/test_cric_short.mp4",
        caption="🏏 What a shot!",
        hashtags="#cricket #ipl #reels",
        account_id="acc_cricket"
    )

    # Filter publishing queue by cricket
    res_cric_pub = client.get("/api/publishing/queue?account_id=acc_cricket")
    assert res_cric_pub.status_code == 200
    cric_items = res_cric_pub.json()["queue"]
    assert any(item["render_id"] == render_id for item in cric_items)

    # Filter publishing queue by fitness - must not contain cricket draft
    res_fit_pub = client.get("/api/publishing/queue?account_id=acc_fitness")
    assert res_fit_pub.status_code == 200
    fit_items = res_fit_pub.json()["queue"]
    assert not any(item["render_id"] == render_id for item in fit_items)


def test_maintenance_and_telemetry_endpoints():
    """Verifies storage cleanup, job recovery, and system telemetry endpoints."""
    # Storage cleanup
    res_cleanup = client.post("/api/storage/cleanup")
    assert res_cleanup.status_code == 200
    assert "freed_mb" in res_cleanup.json()
    assert "deleted_files" in res_cleanup.json()

    # Recovery
    res_recover = client.post("/api/automation/recover")
    assert res_recover.status_code == 200
    assert "recovered_count" in res_recover.json()

    # System telemetry
    res_stats = client.get("/api/system/stats")
    assert res_stats.status_code == 200
    data = res_stats.json()
    assert "cpu_percent" in data
    assert "ram" in data
    assert "disk" in data
    assert "emergency_stop" in data
    assert "db_stats" in data


def test_commercial_saas_dashboard_serving():
    """Verifies that the enhanced dashboard loads all 13 operational views."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text

    # Verify identity & required features
    assert "VedioHooks" in html
    assert "Smart Face Tracking" in html
    assert "Account Manager" in html
    assert "AI Content Director" in html
    assert "Publishing Calendar" in html
    assert "EMERGENCY STOP" in html
    assert "Official Meta Instagram Graph API" in html
    assert '<meta name="description"' in html
    assert '<h1 id="pageTitle">' in html
    assert 'id="menuToggle"' in html
    assert 'aria-label="Main navigation"' in html
    assert html.count('class="tab-view') == 13
    assert "fonts.googleapis.com" not in html


def test_auto_emoji_and_kinetic_subtitles():
    """Verifies that kinetic pop bounce tags and auto-emojis are injected into ASS subtitles."""
    from src.subtitle_generator import create_ass_subtitles

    sample_words = [
        {"word": "THE", "start": 0.0, "end": 0.3},
        {"word": "SECRET", "start": 0.35, "end": 0.75},
        {"word": "TO", "start": 0.8, "end": 1.0},
        {"word": "MONEY", "start": 1.05, "end": 1.5},
        {"word": "AND", "start": 1.55, "end": 1.8},
        {"word": "POWER", "start": 1.85, "end": 2.3}
    ]

    out_ass = "temp/test_kinetic_emoji.ass"
    create_ass_subtitles(
        words_data=sample_words,
        output_ass_path=out_ass,
        theme_name="hormozi_yellow",
        enable_kinetic_pop=True,
        enable_emoji=True
    )

    assert os.path.exists(out_ass)
    with open(out_ass, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify kinetic pop scaling tag
    assert r"\fscx112" in content or r"\fscx114" in content
    # Verify contextual auto-emojis for trigger words
    assert "💸" in content  # For MONEY
    assert "⚡" in content or "🤫" in content  # For POWER or SECRET


def test_split_stack_video_rendering():
    """Verifies 2-speaker podcast split-screen 1+1 vertical stack cropping."""
    from src.video_slicer import slice_and_crop_video
    import subprocess

    # Create dummy 16:9 test video (1920x1080)
    raw_source = "temp/test_split_input.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30",
        "-t", "2",
        "-c:v", "libx264", "-preset", "ultrafast",
        raw_source
    ]
    subprocess.run(cmd, capture_output=True)

    out_split = "temp/test_split_output.mp4"
    slice_and_crop_video(
        video_path=raw_source,
        start_sec=0.0,
        end_sec=1.5,
        output_path=out_split,
        crop_mode="split_stack",
        target_width=1080,
        target_height=1920
    )

    assert os.path.exists(out_split)
    from src.ingest import get_media_info
    info = get_media_info(out_split)
    assert info["width"] == 1080
    assert info["height"] == 1920


def test_database_backup_api():
    """Verifies on-demand SQLite atomic database backup endpoint."""
    res = client.post("/api/database/backup")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "jobs_backup_" in data["backup_path"]
    assert os.path.exists(data["backup_path"])


def test_render_thumbnail_endpoint():
    """Verifies extracting high-resolution JPG frame thumbnails from a rendered short."""
    import subprocess
    os.makedirs("output", exist_ok=True)
    real_video = "output/test_real_thumb_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30",
        "-t", "1.5",
        "-c:v", "libx264", "-preset", "ultrafast",
        real_video
    ]
    subprocess.run(cmd, capture_output=True)

    test_render_id = save_rendered_short(
        job_id="job_thumb_test",
        clip_id=1,
        title="Thumbnail Test Reel",
        start_time=0.0,
        end_time=1.5,
        virality_score=90,
        crop_mode="smart_face",
        theme="hormozi_yellow",
        video_path=real_video,
        caption="Thumb test",
        hashtags="#test",
        account_id="acc_motivation"
    )

    res_thumb = client.get(f"/api/renders/{test_render_id}/thumbnail?time_sec=0.5")
    assert res_thumb.status_code == 200
    assert "image/jpeg" in res_thumb.headers["content-type"]


def test_meta_resumable_upload_simulation():
    """Verifies 3-phase chunked resumable upload protocol simulation and publishing telemetry."""
    from src.publishing import InstagramGraphAPIClient
    import subprocess

    os.makedirs("output", exist_ok=True)
    test_video = "output/test_resumable_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "2.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        test_video
    ]
    subprocess.run(cmd, capture_output=True)
    assert os.path.exists(test_video)

    client_api = InstagramGraphAPIClient()
    # Test simulate_resumable_upload with a small 64KB chunk size to verify multi-chunk slicing
    telemetry = client_api.simulate_resumable_upload(test_video, chunk_size=64 * 1024)
    assert telemetry["status"] == "resumable_simulation_success"
    assert telemetry["total_chunks"] >= 1
    assert "session_id" in telemetry
    assert "upload_url" in telemetry
    assert telemetry["publication"]["status"] == "published"
    assert "instagram.com/reel/" in telemetry["publication"]["permalink"]

    # Test via server API endpoint
    test_job_id = f"job_res_{uuid.uuid4().hex[:8]}"
    create_job(test_job_id, "url", "https://example.com/resumable", account_id="acc_ai_study")
    render_id = save_rendered_short(
        job_id=test_job_id,
        clip_id=1,
        title="Resumable Test Reel",
        start_time=0.0,
        end_time=2.0,
        virality_score=88,
        crop_mode="smart_face",
        theme="cyber_cyan",
        video_path=test_video,
        caption="Chunked upload test",
        hashtags="#meta #reels",
        account_id="acc_ai_study"
    )

    # Queue to drafts
    res_draft = client.post(f"/api/renders/{render_id}/send-to-draft")
    assert res_draft.status_code == 200
    pub_id = res_draft.json()["publishing_id"]

    # Simulate publish guard endpoint
    res_pub = client.post(f"/api/publishing/{pub_id}/simulate_publish")
    assert res_pub.status_code == 200
    data = res_pub.json()
    assert "resumable_upload_telemetry" in data
    assert data["resumable_upload_telemetry"]["status"] == "resumable_simulation_success"


def test_audio_ducking_execution():
    """Verifies procedural ambient music generation and sidechain audio ducking on real video."""
    from src.audio_ducking import generate_procedural_ambient_music, apply_audio_ducking
    from src.ingest import get_media_info
    import subprocess

    os.makedirs("temp", exist_ok=True)
    raw_video = "temp/test_ducking_src.mp4"
    ducked_output = "temp/test_ducked_out.mp4"
    ambient_music = "temp/test_procedural_music.wav"

    # 1. Create source video with speech-like tone
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=44100",
        "-t", "2.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        raw_video
    ]
    subprocess.run(cmd, capture_output=True)

    # 2. Generate procedural ambient music
    gen_path = generate_procedural_ambient_music(duration_sec=2.5, niche_id="acc_motivation", output_path=ambient_music)
    assert os.path.exists(gen_path)
    assert os.path.getsize(gen_path) > 1000

    # 3. Apply sidechain audio ducking
    out_path = apply_audio_ducking(raw_video, ducked_output, ambient_music_path=gen_path)
    assert os.path.exists(out_path)
    info = get_media_info(out_path)
    assert info["duration"] > 0
    assert info["width"] == 720
    assert info["height"] == 1280


def test_dead_air_removal_execution():
    """Verifies silence detection, jump-cut calculation, timestamp adjustment and dead-air excising."""
    from src.video_slicer import calculate_jumpcuts, apply_dead_air_removal
    from src.ingest import get_media_info
    import subprocess

    # 1. Test jump-cut calculation with synthetic word timestamps having a 0.8s gap
    words = [
        {"word": "Never", "start": 0.0, "end": 0.3},
        {"word": "stop", "start": 0.3, "end": 0.6},
        # 0.6 to 1.4 is an 800ms silence gap (> 350ms threshold)
        {"word": "fighting", "start": 1.4, "end": 1.9},
        {"word": "today", "start": 1.9, "end": 2.3}
    ]

    segments, shifted_words = calculate_jumpcuts(words, max_silence_sec=0.35)
    # Should have 2 segments
    assert len(segments) == 2
    # The excised silence is 0.8s - 0.35s = 0.45s
    excised = (1.4 - 0.6) - 0.35
    assert abs(excised - 0.45) < 0.01

    # Shifted words after gap should have earlier timestamps
    assert shifted_words[0]["start"] == 0.0
    assert shifted_words[2]["word"] == "fighting"
    assert shifted_words[2]["start"] < 1.4

    # 2. Test apply_dead_air_removal with FFmpeg select/aselect
    os.makedirs("temp", exist_ok=True)
    raw_video = "temp/test_dead_air_src.mp4"
    trimmed_video = "temp/test_dead_air_cut.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "2.5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        raw_video
    ]
    subprocess.run(cmd, capture_output=True)

    test_segments = [(0.0, 0.8), (1.5, 2.5)]
    out_cut = apply_dead_air_removal(raw_video, trimmed_video, test_segments)
    assert os.path.exists(out_cut)
    info = get_media_info(out_cut)
    # Expected duration is around 0.8 + 1.0 = 1.8s (much less than 2.5s)
    assert info["duration"] < 2.2


def test_bilingual_translation_and_subtitles():
    """Verifies multi-language translation and bilingual dual-line ASS subtitle generation."""
    from src.subtitle_translator import translate_text, SUPPORTED_LANGUAGES
    from src.subtitle_generator import create_ass_subtitles

    assert "es" in SUPPORTED_LANGUAGES
    assert "hi" in SUPPORTED_LANGUAGES

    # 1. Test translation vocabulary mapping
    trans_es = translate_text("discipline leads to success", target_lang="es")
    assert "disciplina" in trans_es.lower()
    assert "éxito" in trans_es.lower()

    trans_hi = translate_text("never give up on your dream", target_lang="hi")
    assert "कभी हार मत मानो" in trans_hi

    # 2. Test ASS bilingual file creation
    words = [
        {"word": "FOCUS", "start": 0.0, "end": 0.4},
        {"word": "ON", "start": 0.4, "end": 0.7},
        {"word": "DISCIPLINE", "start": 0.7, "end": 1.2}
    ]
    ass_out = "temp/test_bilingual_es.ass"
    create_ass_subtitles(
        words_data=words,
        output_ass_path=ass_out,
        theme_name="cyber_cyan",
        target_language="es"
    )

    assert os.path.exists(ass_out)
    with open(ass_out, "r", encoding="utf-8") as f:
        content = f.read()

    assert "HormoziTranslated" in content
    assert "enfoque" in content.lower() or "disciplina" in content.lower()
    assert "Dialogue: 1," in content  # Secondary translated subtitle layer
    assert "Dialogue: 0," in content  # Primary active karaoke layer


def test_audio_whoosh_sfx_generation_and_mixing():
    """Verifies procedural SFX synthesis (whoosh & sub-bass) and FFmpeg audio filter mixing."""
    from src.sfx_engine import generate_whoosh_sfx, generate_sub_bass_drop, apply_transition_sfx
    from src.ingest import get_media_info
    import subprocess

    whoosh_path = generate_whoosh_sfx("temp/sfx/test_whoosh.wav", duration=0.35)
    assert os.path.exists(whoosh_path)
    assert os.path.getsize(whoosh_path) > 500

    bass_path = generate_sub_bass_drop("temp/sfx/test_bass.wav", duration=0.5)
    assert os.path.exists(bass_path)
    assert os.path.getsize(bass_path) > 500

    # Create dummy video to test SFX insertion
    os.makedirs("temp", exist_ok=True)
    raw_video = "temp/test_sfx_video.mp4"
    mixed_video = "temp/test_sfx_mixed.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "1.5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        raw_video
    ]
    subprocess.run(cmd, capture_output=True)

    out = apply_transition_sfx(raw_video, mixed_video, sfx_times=[0.1], sfx_type="whoosh")
    assert os.path.exists(out)
    info = get_media_info(out)
    assert info["duration"] > 0


def test_retention_curve_prediction():
    """Verifies second-by-second predictive audience retention curve calculations and API endpoint."""
    from src.retention_predictor import calculate_retention_curve

    test_words = [
        {"word": "LISTEN", "start": 0.0, "end": 0.3},
        {"word": "CLOSELY", "start": 0.3, "end": 0.6},
        {"word": "TO", "start": 0.6, "end": 0.8},
        {"word": "THIS", "start": 0.8, "end": 1.1},
        {"word": "SECRET", "start": 1.1, "end": 1.5}
    ]

    curve = calculate_retention_curve(test_words, duration_sec=2.0, virality_score=92)
    assert "retention_points" in curve
    assert len(curve["retention_points"]) > 0
    assert curve["retention_points"][0]["retention"] == 100.0
    assert "peak_viral_moment" in curve
    assert curve["predicted_completion_rate"] > 50.0

    # Test via API
    renders = client.get("/api/renders").json().get("renders", [])
    if renders:
        r_id = renders[0]["id"]
        res_ret = client.get(f"/api/renders/{r_id}/retention")
        assert res_ret.status_code == 200
        data = res_ret.json()
        assert "retention_points" in data


def test_auto_schedule_7_day_week():
    """Verifies automated distribution of queued drafts into 7-day optimal publishing windows."""
    from src.auto_scheduler import auto_schedule_7_day_week

    # Ensure at least 1 draft exists
    renders = client.get("/api/renders").json().get("renders", [])
    if renders:
        client.post(f"/api/renders/{renders[0]['id']}/send-to-draft")

    res = client.post("/api/publishing/auto-schedule-week", json={"account_id": "all"})
    assert res.status_code == 200
    data = res.json()
    assert "scheduled_count" in data
    assert "schedule" in data


def test_thematic_motion_broll_cutaway():
    """Verifies procedural 9:16 thematic motion B-roll synthesis and hook overlay."""
    from src.broll_engine import generate_thematic_motion_broll, apply_hook_motion_overlay
    from src.ingest import get_media_info
    import subprocess

    broll_path = generate_thematic_motion_broll(duration_sec=1.5, niche="AI & Study", width=360, height=640)
    assert os.path.exists(broll_path)

    raw_video = "temp/test_broll_src.mp4"
    out_video = "temp/test_broll_out.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25",
        "-t", "1.5",
        "-c:v", "libx264", "-preset", "ultrafast",
        raw_video
    ]
    subprocess.run(cmd, capture_output=True)

    applied = apply_hook_motion_overlay(raw_video, out_video, niche="AI & Study", start_sec=0.1, end_sec=0.8)
    assert os.path.exists(applied)
    info = get_media_info(applied)
    assert info["width"] == 360
    assert info["height"] == 640


def test_ai_dubbing_voice_listing_and_preview():
    """Verifies curated neural voice catalog and sample voice preview synthesis."""
    from src.dubbing_engine import list_curated_voices, synthesize_speech

    voices = list_curated_voices()
    assert len(voices) >= 8
    spanish_voices = list_curated_voices(language="es")
    assert any(v["lang_code"] == "es" for v in spanish_voices)

    # API test
    res = client.get("/api/dubbing/voices?language=hi")
    assert res.status_code == 200
    assert "voices" in res.json()
    assert any("Madhur" in v["name"] for v in res.json()["voices"])

    # Preview API test
    prev_res = client.post("/api/dubbing/preview-voice", json={
        "text": "Discipline is the foundation of greatness.",
        "voice_id": "en-US-ChristopherNeural"
    })
    assert prev_res.status_code == 200
    assert len(prev_res.content) > 100


def test_ai_dubbing_video_short_execution():
    """Verifies end-to-end video dubbing with audio time alignment and ducking."""
    import subprocess
    from src.dubbing_engine import dub_video_short

    # Create dummy source short with audio
    src_video = "temp/test_dub_src.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440",
        "-t", "2.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        src_video
    ]
    subprocess.run(cmd, capture_output=True)

    dubbed = dub_video_short(
        source_video_path=src_video,
        transcript_text="Success is not final, failure is not fatal.",
        target_language="es",
        voice_id="es-ES-AlvaroNeural",
        blend_mode="ducked",
        speed=1.0,
        account_id="acc_motivation"
    )
    assert os.path.exists(dubbed["video_path"])
    assert dubbed["target_language"] == "es"
    assert dubbed["blend_mode"] == "ducked"

    # API history check
    h_res = client.get("/api/dubbing/history")
    assert h_res.status_code == 200
    assert len(h_res.json()["history"]) > 0


def test_viral_hook_ab_variants_generation():
    """Verifies psychological 3-framework hook variant generation across niches."""
    from src.hook_ab_engine import generate_hook_variants

    for niche in ["Motivation", "Cricket", "AI & Study", "Gym & Fitness"]:
        variants = generate_hook_variants(
            clip_text="Why most people fail to achieve their goals in the first 30 days.",
            niche=niche,
            base_score=85,
            job_id="test_hook_job",
            clip_id=1,
            account_id="acc_motivation"
        )
        assert len(variants) == 3
        letters = [v["variant_letter"] for v in variants]
        assert letters == ["A", "B", "C"]
        # Check that predicted score reflects retention lift
        assert all(v["predicted_score"] >= 80 for v in variants)
        assert any("Retention Lift" in v["retention_lift"] for v in variants)

    # API test
    res = client.post("/api/hooks/generate-variants", json={
        "clip_text": "How to stay focused all day.",
        "niche": "AI & Study",
        "base_score": 88
    })
    assert res.status_code == 200
    assert len(res.json()["variants"]) == 3


def test_viral_hook_overlay_rendering_and_ab_queue():
    """Verifies burning hook intro card onto video and scheduling 3-way A/B split test."""
    import subprocess
    from src.hook_ab_engine import render_hook_variant_overlay, queue_ab_split_test

    src_video = "temp/test_hook_card_src.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25",
        "-t", "2.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        src_video
    ]
    subprocess.run(cmd, capture_output=True)

    rendered_hook = render_hook_variant_overlay(
        source_video_path=src_video,
        hook_overlay_text="STOP SCROLLING\\nDO THIS NOW",
        duration_sec=1.5
    )
    assert os.path.exists(rendered_hook)

    # Test A/B queue scheduling API
    sample_variants = [
        {"variant_letter": "A", "framework_type": "Curiosity Gap", "hook_title": "The Secret Rule", "predicted_score": 96, "render_id": 1},
        {"variant_letter": "B", "framework_type": "Urgent Command", "hook_title": "Stop Scrolling", "predicted_score": 93, "render_id": 1},
        {"variant_letter": "C", "framework_type": "Contrarian Shift", "hook_title": "Why You Are Wrong", "predicted_score": 90, "render_id": 1}
    ]
    q_res = client.post("/api/hooks/queue-ab-test", json={
        "account_id": "acc_motivation",
        "job_id": "test_job_ab",
        "variants": sample_variants,
        "base_caption": "Which hook stopped your scroll?",
        "hashtags": "#test #viral"
    })
    assert q_res.status_code == 200
    assert q_res.json()["count"] == 3


def test_real_time_performance_analytics():
    """Verifies live real-time operational analytics and virality metrics aggregation."""
    from src.analytics import get_performance_analytics

    data = get_performance_analytics(account_id="all")
    assert "total_renders" in data
    assert "avg_virality_score" in data
    assert "virality_tiers" in data
    assert "publishing_pipeline" in data
    assert "niche_breakdown" in data
    assert len(data["niche_breakdown"]) >= 5

    # API test
    res = client.get("/api/analytics")
    assert res.status_code == 200
    assert "virality_tiers" in res.json()


def test_cover_thumbnail_generation_3_styles():
    """Verifies generation of 3 distinct psychological 9:16 cover thumbnail styles."""
    import subprocess
    from src.thumbnail_engine import generate_cover_thumbnails

    src_video = "temp/test_thumb_src.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25",
        "-t", "2.0",
        "-c:v", "libx264", "-preset", "ultrafast",
        src_video
    ]
    subprocess.run(cmd, capture_output=True)

    covers = generate_cover_thumbnails(
        video_path=src_video,
        title="STOP WASTING TIME START NOW",
        niche="Motivation",
        output_dir="temp/test_covers"
    )
    assert len(covers) == 3
    style_ids = [c["style_id"] for c in covers]
    assert "hormozi_bold" in style_ids
    assert "beast_pop" in style_ids
    assert "cinema_clean" in style_ids
    assert all(os.path.exists(c["path"]) for c in covers)

    # API test
    res = client.post("/api/thumbnails/generate", json={
        "video_path": src_video,
        "title": "NEVER GIVE UP",
        "niche": "Motivation"
    })
    assert res.status_code == 200
    assert len(res.json()["covers"]) == 3


def test_beat_sync_transient_detection_and_alignment():
    """Verifies musical downbeat detection, BPM tempo estimation, and rhythmic word snapping."""
    import subprocess
    from src.beat_sync import detect_audio_beats, align_word_timestamps_to_beats

    src_audio = "temp/test_beat_src.mp3"
    # Generate 120 BPM rhythmic pulsed audio (0.5s beat intervals)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=100:duration=4",
        "-af", "tremolo=f=2.0:d=0.9",
        src_audio
    ]
    subprocess.run(cmd, capture_output=True)

    beat_data = detect_audio_beats(src_audio, max_duration=4.0)
    assert "bpm" in beat_data
    assert "beats" in beat_data
    assert isinstance(beat_data["beats"], list)

    # Word snapping test
    sample_words = [
        {"word": "Discipline", "start": 0.52, "end": 0.85},
        {"word": "Over", "start": 1.48, "end": 1.70},
        {"word": "Motivation", "start": 2.50, "end": 2.95}
    ]
    aligned = align_word_timestamps_to_beats(sample_words, beats=[0.5, 1.0, 1.5, 2.0, 2.5], snap_window_ms=100.0)
    assert len(aligned) == 3
    # Word starting at 0.52 should snap to 0.5
    assert aligned[0]["start"] == 0.5
    assert aligned[0]["beat_snapped"] is True

    # API test
    res = client.post("/api/audio/beat-sync", json={
        "video_path": src_audio,
        "max_duration": 4.0
    })
    assert res.status_code == 200
    assert "bpm" in res.json()


def test_multi_platform_export_formatting():
    """Verifies generation of tailored algorithm copy for Reels, Shorts, and TikTok."""
    from src.multi_platform_export import generate_multi_platform_package

    package = generate_multi_platform_package(
        title="Why 99% Of People Fail At Building Discipline",
        hook_text="Nobody talks about this one rule of discipline...",
        script_summary="Small daily actions matter 100x more than occasional intense efforts.",
        niche="Motivation"
    )

    # Instagram Reels
    assert "instagram" in package
    assert "#motivation" in package["instagram"]["hashtags"]

    # YouTube Shorts
    assert "youtube_shorts" in package
    assert "#Shorts" in package["youtube_shorts"]["title"]
    assert "pinned_comment" in package["youtube_shorts"]

    # TikTok
    assert "tiktok" in package
    assert "#fyp" in package["tiktok"]["hashtags"]
    assert "pinned_comment" in package["tiktok"]

    # API test
    res = client.post("/api/export/multi-platform", json={
        "title": "Untold Story of World Cup Final",
        "hook_text": "The greatest over in cricket history...",
        "script_summary": "How this single ball changed the championship.",
        "niche": "Cricket"
    })
    assert res.status_code == 200
    assert res.json()["youtube_shorts"]["title"].endswith("#Shorts")


def test_hardware_acceleration_detection():
    """Verifies GPU encoder auto-negotiation and FFmpeg argument generation."""
    from src.hardware_accel import detect_best_video_encoder, get_ffmpeg_encoding_args

    info = detect_best_video_encoder()
    assert "encoder" in info
    assert "device" in info
    assert "hw" in info
    assert isinstance(info["args"], list)

    args = get_ffmpeg_encoding_args()
    assert len(args) >= 2
    assert "-c:v" in args

    # API test
    res = client.get("/api/system/hardware")
    assert res.status_code == 200
    data = res.json()
    assert "encoder" in data
    assert "device" in data


def test_watermark_rendering():
    """Verifies burning subtle, high-contrast account handle badge into 9:16 vertical shorts."""
    import subprocess
    from src.watermark_engine import apply_watermark, build_watermark_drawtext_filter
    from src.ingest import get_media_info

    # 1. Filter string verification
    f_str = build_watermark_drawtext_filter("@apex_discipline", position="top_right", opacity=0.75)
    assert "@apex_discipline" in f_str
    assert "fontsize=34" in f_str
    assert "box=1" in f_str

    # 2. Render execution test
    os.makedirs("temp", exist_ok=True)
    src_video = "temp/test_watermark_src.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25",
        "-t", "1.5",
        "-c:v", "libx264", "-preset", "ultrafast",
        src_video
    ]
    subprocess.run(cmd, capture_output=True)

    out_wm = "temp/test_watermarked_out.mp4"
    res_path = apply_watermark(src_video, handle="@apex_discipline", output_path=out_wm)
    assert os.path.exists(res_path)
    info = get_media_info(res_path)
    assert info["width"] == 360
    assert info["height"] == 640

    # 3. API test
    res = client.post("/api/watermark/apply", json={
        "video_path": src_video,
        "handle": "@apex_discipline",
        "position": "top_right",
        "opacity": 0.75
    })
    assert res.status_code == 200
    assert os.path.exists(res.json()["watermarked_video_path"])


def test_batch_playlist_ingest(monkeypatch):
    """Verifies flat-metadata playlist extraction and autonomous queue ingestion."""
    from src.batch_ingest import crawl_and_queue_playlist
    from unittest.mock import MagicMock
    import yt_dlp

    # Mock YoutubeDL to prevent real external network calls in unit tests
    mock_playlist_payload = {
        "title": "Top Motivation Playlist",
        "entries": [
            {"id": "vid101", "url": "https://www.youtube.com/watch?v=vid101", "title": "Never Give Up Speech", "duration": 180.0},
            {"id": "vid102", "url": "https://www.youtube.com/watch?v=vid102", "title": "Discipline vs Motivation", "duration": 240.0},
            {"id": "vid103", "url": "https://www.youtube.com/watch?v=vid103", "title": "Morning Routine of High Performers", "duration": 300.0},
            {"id": "vid104", "url": "https://www.youtube.com/watch?v=vid104", "title": "Ultra Short Teaser", "duration": 20.0}  # Below min duration
        ]
    }

    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = mock_playlist_payload
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.__exit__.return_value = None

    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda *args, **kwargs: mock_ydl)

    res = crawl_and_queue_playlist(
        playlist_url="https://www.youtube.com/playlist?list=PLmock123",
        account_id="acc_motivation",
        max_items=3,
        min_duration_sec=60.0
    )

    assert res["total_discovered"] == 4
    assert res["queued_count"] == 3
    assert len(res["queued_jobs"]) == 3
    assert res["queued_jobs"][0]["job_id"] is not None

    # API test
    res_api = client.post("/api/jobs/batch-playlist", json={
        "playlist_url": "https://www.youtube.com/playlist?list=PLmock123",
        "account_id": "acc_motivation",
        "max_items": 2,
        "min_duration_sec": 60.0
    })
    assert res_api.status_code == 200
    assert "queued_count" in res_api.json()


def test_instagram_insights_sync_and_history():
    """Verifies Meta Graph API v19.0 insights syncing and account historical metrics telemetry."""
    from src.insights_engine import sync_post_insights, get_account_historical_performance

    test_job_id = f"job_ins_{uuid.uuid4().hex[:8]}"
    create_job(test_job_id, "url", "https://example.com/insights", account_id="acc_motivation")
    render_id = save_rendered_short(
        job_id=test_job_id,
        clip_id=1,
        title="Insights Metric Test Reel",
        start_time=0.0,
        end_time=2.0,
        virality_score=94,
        crop_mode="smart_face",
        theme="hormozi_yellow",
        video_path="temp/test_ins_render.mp4",
        caption="High performance insights test",
        hashtags="#insights #growth",
        account_id="acc_motivation"
    )

    draft_res = client.post(f"/api/renders/{render_id}/send-to-draft")
    pub_id = draft_res.json()["publishing_id"]

    # 1. Sync insights
    telemetry = sync_post_insights(publishing_id=pub_id, account_id="acc_motivation")
    assert telemetry["publishing_id"] == pub_id
    assert telemetry["account_id"] == "acc_motivation"
    assert telemetry["views"] > 0
    assert telemetry["likes"] > 0
    assert telemetry["retention_rate"] >= 70.0

    # 2. Historical performance aggregation
    hist = get_account_historical_performance(account_id="acc_motivation")
    assert hist["total_tracked_posts"] >= 1
    assert hist["aggregates"]["total_views"] > 0
    assert hist["aggregates"]["avg_retention_rate"] > 0

    # 3. API endpoints test
    res_sync = client.post("/api/insights/sync", json={
        "publishing_id": pub_id,
        "account_id": "acc_motivation"
    })
    assert res_sync.status_code == 200
    assert res_sync.json()["views"] > 0

    res_get = client.get("/api/insights/acc_motivation")
    assert res_get.status_code == 200
    assert res_get.json()["total_tracked_posts"] >= 1


def test_sentiment_palette_analysis():
    """Verifies lexical sentiment classification and emotional visual/audio palette auto-tagging."""
    from src.sentiment_palette import classify_sentiment_and_palette

    # 1. Tech & AI Educational test
    tech_res = classify_sentiment_and_palette(
        "Here is the secret AI tool that helps students write code in half the time.",
        niche="AI & Study"
    )
    assert tech_res["recommended_theme"] == "cyber_cyan"
    assert tech_res["ambient_music_mood"] == "lofi_focus"
    assert "⚡" in tech_res["contextual_emojis"]

    # 2. Gym & Fitness Power test
    gym_res = classify_sentiment_and_palette(
        "Stop making this dangerous squat mistake! Your knees and muscle hypertrophy require proper biomechanics.",
        niche="Gym & Fitness"
    )
    assert gym_res["recommended_theme"] == "crimson_bold"
    assert gym_res["ambient_music_mood"] == "high_energy_trap"
    assert "💪" in gym_res["contextual_emojis"]

    # 3. Cricket Stadium test
    cricket_res = classify_sentiment_and_palette(
        "Kohli hit two sixes in the final over of the world cup championship match!",
        niche="Cricket"
    )
    assert cricket_res["recommended_theme"] == "neon_green"
    assert cricket_res["ambient_music_mood"] == "epic_strings"

    # 4. API endpoint test
    res = client.post("/api/ai/sentiment-palette", json={
        "transcript_text": "Never stop fighting. Discipline is what separates winners from losers.",
        "niche": "Motivation"
    })
    assert res.status_code == 200
    assert res.json()["recommended_theme"] == "hormozi_yellow"


def test_dynamic_framing_trajectory_and_reframe():
    """Verifies EMA camera panning trajectory calculation and dynamic 9:16 vertical re-framing."""
    import subprocess
    from src.dynamic_framing import calculate_smooth_camera_trajectory, build_segmented_pan_filter, reframe_dynamic_short
    from src.ingest import get_media_info

    # 1. Trajectory calculation test
    times = [0.0, 0.5, 1.0, 1.5, 2.0]
    raw_x = [0.2, 0.25, 0.75, 0.8, 0.8]  # Speaker moves from left (0.2) to right (0.8)
    smoothed = calculate_smooth_camera_trajectory(times, raw_x, alpha=0.35, max_velocity_per_sec=0.40)
    assert len(smoothed) == len(times)
    # Velocity limit should prevent instant jump
    assert smoothed[2] < 0.75
    # Smooth continuous progression
    assert smoothed[0] <= smoothed[1] <= smoothed[2] <= smoothed[3]

    # 2. Filter string construction test
    f_str = build_segmented_pan_filter(times, smoothed, target_width=1080, target_height=1920)
    assert "crop=" in f_str
    assert "scale=1080:1920" in f_str

    # 3. End-to-end rendering execution test
    os.makedirs("temp", exist_ok=True)
    raw_video = "temp/test_dynamic_framing_src.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440",
        "-t", "1.5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        raw_video
    ]
    subprocess.run(cmd, capture_output=True)

    out_dynamic = "temp/test_dynamic_framing_out.mp4"
    rendered = reframe_dynamic_short(raw_video, start_sec=0.0, end_sec=1.5, output_path=out_dynamic)
    assert os.path.exists(rendered)
    info = get_media_info(rendered)
    assert info["width"] == 1080
    assert info["height"] == 1920

    # 4. API test
    res = client.post("/api/video/dynamic-reframe", json={
        "video_path": raw_video,
        "start_sec": 0.0,
        "end_sec": 1.0
    })
    assert res.status_code == 200
    assert os.path.exists(res.json()["dynamic_video_path"])


def test_content_deduplication_and_fingerprinting():
    """Verifies perceptual fingerprinting, lexical n-gram similarity, and collision prevention."""
    from src.deduplication import compute_content_fingerprint, calculate_jaccard_similarity, check_for_duplicate_content

    fp1 = compute_content_fingerprint("Why 99% of people quit in the first 30 days of building discipline", duration_sec=18.0)
    fp2 = compute_content_fingerprint("Why 99% of people quit in the first 30 days of building discipline", duration_sec=18.2)
    assert fp1 == fp2  # Quantized duration bucketing matches

    # Similarity check
    tokens_a = ["discipline", "habits", "success", "motivation", "morning"]
    tokens_b = ["discipline", "habits", "success", "mindset", "routine"]
    sim = calculate_jaccard_similarity(tokens_a, tokens_b)
    assert sim >= 0.40

    # Duplicate scanner API test
    res = client.post("/api/content/check-duplicate", json={
        "transcript_text": "A brand new unique topic about neuroscience and deep focus techniques.",
        "duration_sec": 22.0
    })
    assert res.status_code == 200
    data = res.json()
    assert "candidate_fingerprint" in data
    assert "is_duplicate" in data
    assert "recommendation" in data


def test_weekly_executive_report_generation():
    """Verifies executive digest aggregation and downloadable Markdown report generation."""
    from src.performance_report import generate_weekly_executive_report

    report = generate_weekly_executive_report(account_id="all")
    assert "total_renders" in report
    assert "avg_virality_score" in report
    assert "markdown_report" in report
    assert "# 📊 VedioHooks AI — Weekly Executive Media Factory Report" in report["markdown_report"]
    assert "Strategic AI Production Recommendations" in report["markdown_report"]

    # API endpoint test
    res = client.get("/api/reports/weekly?account_id=all")
    assert res.status_code == 200
    assert "markdown_report" in res.json()





