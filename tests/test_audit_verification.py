"""
Comprehensive Audit Verification Suite for VedioHooks AI Media Factory.
Validates end-to-end functionality, captures reproducible edge cases,
and documents bugs discovered during the technical audit.
"""

import os
import sys
import json
import sqlite3
import subprocess
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.server import app, DASHBOARD_HTML
from src.db import (
    init_db, get_db_connection, list_jobs, create_job, get_job,
    list_accounts, get_account, list_series, list_rendered_shorts
)
from src.ingest import get_media_info, create_synthetic_test_video, sanitize_filename
from src.virality_selector import (
    extract_all_words, snap_timestamp_to_words, heuristic_virality_selector,
    evaluate_candidate_multidimensional
)
from src.subtitle_generator import THEMES, create_ass_subtitles
from src.hook_banner import BANNER_THEMES, generate_smart_hook_text, generate_hook_banner_ass_elements
from src.metadata_generator import generate_video_metadata, PLATFORM_LIMITS
from src.thumbnail_studio import generate_thumbnail_headline, CANVAS_DIMENSIONS
from src.publishing_validator import validate_publishing_readiness


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Video Factory & Ingestion Edge Cases
# -----------------------------------------------------------------------------

def test_sanitize_filename():
    unsafe = 'Video: "Crazy" <Title> / Test? * 2026 | New'
    clean = sanitize_filename(unsafe)
    assert ":" not in clean
    assert '"' not in clean
    assert "<" not in clean
    assert ">" not in clean
    assert "/" not in clean
    assert "?" not in clean
    assert "*" not in clean
    assert "|" not in clean


def test_synthetic_video_generation_and_probe(tmp_path):
    clip_path = create_synthetic_test_video(str(tmp_path), duration_sec=2)
    assert os.path.exists(clip_path)
    assert os.path.getsize(clip_path) > 0

    info = get_media_info(clip_path)
    assert info["has_video"] is True
    assert info["has_audio"] is True
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["duration"] >= 1.8


def test_url_ingest_duplicate_and_empty(client):
    # Empty URL rejection
    r = client.post("/api/jobs", json={"url": "", "account_id": "acc_motivation"})
    assert r.status_code == 400

    # SSRF vulnerability check: unvalidated schemes (e.g. file://) are rejected
    r_file = client.post("/api/jobs", json={"url": "file:///c:/windows/win.ini", "account_id": "acc_motivation"})
    assert r_file.status_code == 400
    assert "Invalid URL" in r_file.json()["detail"]


# -----------------------------------------------------------------------------
# 2. Virality Selector & Context Safeguards
# -----------------------------------------------------------------------------

def test_virality_snap_timestamps():
    words = [
        {"word": "Discipline", "start": 1.05, "end": 1.62},
        {"word": "is", "start": 1.65, "end": 1.80},
        {"word": "everything.", "start": 1.85, "end": 2.40}
    ]
    # Snapping 1.0 should snap to word start 1.05
    snapped_start = snap_timestamp_to_words(1.0, words, mode="start")
    assert snapped_start == 1.05

    # Snapping 2.5 should snap to word end 2.40
    snapped_end = snap_timestamp_to_words(2.5, words, mode="end")
    assert snapped_end == 2.40


def test_virality_heuristic_evaluator():
    text = "The secret truth about discipline is nobody talks about the hard work required to win."
    res = evaluate_candidate_multidimensional(text, 30.0, [])
    assert res["hook_score"] >= 60
    assert res["curiosity_score"] >= 60
    assert res["context_score"] >= 70
    assert 0 <= res["overall_score"] <= 100


# -----------------------------------------------------------------------------
# 3. Subtitles & Hook Banner Rendering
# -----------------------------------------------------------------------------

def test_subtitle_themes_definitions():
    assert "hormozi_yellow" in THEMES
    assert "hormozi_green" in THEMES
    assert "cyber_cyan" in THEMES
    for name, t in THEMES.items():
        assert "primary" in t
        assert "highlight" in t
        assert "outline" in t


def test_hook_banner_ass_generation():
    elems = generate_hook_banner_ass_elements(
        hook_text="BRUTAL TRUTH: NEVER QUIT",
        theme="hormozi_yellow",
        start_sec=0.0,
        duration_sec=3.5
    )
    assert "Style: HookBanner" in elems["style_def"]
    assert "Dialogue: 2,0:00:00.00,0:00:03.50,HookBanner" in elems["dialogue_def"]
    assert "BRUTAL TRUTH: NEVER QUIT" in elems["dialogue_def"]


# -----------------------------------------------------------------------------
# 4. Face Tracker Split Stack Rendering Verification
# -----------------------------------------------------------------------------

def test_face_tracker_split_stack_rendering(tmp_path):
    """
    Verifies that split_stack renders successfully using -filter_complex without error.
    """
    from src.face_tracker import render_face_tracked_short
    clip_path = create_synthetic_test_video(str(tmp_path), duration_sec=2)
    out_path = str(tmp_path / "split_test_out.mp4")

    res = render_face_tracked_short(
        video_path=clip_path,
        start_sec=0.0,
        end_sec=1.5,
        output_path=out_path,
        speaker_mode="split_stack"
    )
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0
    info = get_media_info(out_path)
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert res["speaker_mode"] == "split_stack"


# -----------------------------------------------------------------------------
# 5. Metadata Generator & Platform Limits
# -----------------------------------------------------------------------------

def test_metadata_generator_limits():
    meta = generate_video_metadata(
        target_type="short",
        target_id=1,
        title="Stop Quitting: The Truth About Discipline",
        text="If you want to achieve greatness, motivation is never enough. Discipline is what gets you through.",
        niche="Motivation",
        duration=30.0
    )
    assert len(meta.youtube.title) <= PLATFORM_LIMITS["youtube"]["title_max"]
    assert len(meta.instagram.caption) <= PLATFORM_LIMITS["instagram"]["caption_max"]
    assert len(meta.instagram.hashtags) <= PLATFORM_LIMITS["instagram"]["hashtags_max"]
    assert len(meta.tiktok.caption) <= PLATFORM_LIMITS["tiktok"]["caption_max"]
    assert meta.quality.overall_score >= 70


# -----------------------------------------------------------------------------
# 6. Database Schema & Secondary Indexes Verification
# -----------------------------------------------------------------------------

def test_database_foreign_keys_and_indexes():
    conn = get_db_connection()
    c = conn.cursor()

    # Foreign key checks
    c.execute("PRAGMA foreign_keys = ON;")
    violations = c.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(violations) == 0

    # Index audit: verify that performance secondary indexes exist
    indexes = c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex_%'").fetchall()
    index_names = {idx["name"] for idx in indexes}
    expected_indexes = {
        "idx_jobs_status_prio",
        "idx_jobs_account",
        "idx_rendered_shorts_job_id",
        "idx_rendered_shorts_account",
        "idx_publishing_queue_account_status",
        "idx_series_account_id",
        "idx_series_episodes_series_id",
        "idx_thumbnail_assets_target",
        "idx_video_metadata_target",
    }
    assert expected_indexes.issubset(index_names)


# -----------------------------------------------------------------------------
# 7. Frontend UI Inline Event Handlers Verification
# -----------------------------------------------------------------------------

def test_frontend_inline_handlers_defined():
    """
    Verifies that onMetadataNicheChanged and onThumbnailConfigChanged are referenced in HTML
    and properly defined in JavaScript functions.
    """
    assert 'onchange="onMetadataNicheChanged()"' in DASHBOARD_HTML
    assert 'onchange="onThumbnailConfigChanged()"' in DASHBOARD_HTML

    # Verify function definitions exist in the script block
    assert "function onMetadataNicheChanged" in DASHBOARD_HTML
    assert "function onThumbnailConfigChanged" in DASHBOARD_HTML


# -----------------------------------------------------------------------------
# 8. Publishing Readiness Pre-flight Evaluation
# -----------------------------------------------------------------------------

def test_publishing_readiness_missing_video():
    rep = validate_publishing_readiness(
        target_type="short",
        target_id=9999,
        video_path="non_existent_video.mp4"
    )
    assert rep.has_video is False
    assert rep.readiness_status in ("needs_review", "incomplete")
    assert rep.overall_score < 70


# -----------------------------------------------------------------------------
# 9. Security Audit - CORS Policy Verification
# -----------------------------------------------------------------------------

def test_cors_security_policy(client):
    # Trusted local origin receives Access-Control-Allow-Origin
    resp_local = client.get("/api/health", headers={"Origin": "http://localhost:8000"})
    assert resp_local.status_code == 200
    assert resp_local.headers.get("access-control-allow-origin") == "http://localhost:8000"

    # Untrusted third-party origin does NOT receive Access-Control-Allow-Origin
    resp_untrusted = client.get("/api/health", headers={"Origin": "http://malicious-site.com"})
    assert resp_untrusted.status_code == 200
    assert resp_untrusted.headers.get("access-control-allow-origin") is None


# -----------------------------------------------------------------------------
# 10. Security Audit - URL Ingestion & SSRF Protection
# -----------------------------------------------------------------------------

def test_url_ingestion_ssrf_protection(client):
    from src.ingest import validate_ingest_url

    # Unit validation checks
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_ingest_url("file:///etc/passwd")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_ingest_url("ftp://example.com/video.mp4")

    with pytest.raises(ValueError):
        validate_ingest_url("http://localhost:8000/internal")

    with pytest.raises(ValueError):
        validate_ingest_url("http://127.0.0.1:8000/admin")

    with pytest.raises(ValueError):
        validate_ingest_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError):
        validate_ingest_url("http://10.0.0.1/private")

    with pytest.raises(ValueError):
        validate_ingest_url("http://[::1]:8000/internal")

    # API endpoint enforcement
    res_file = client.post("/api/jobs", json={"url": "file:///C:/Windows/win.ini"})
    assert res_file.status_code == 400
    assert "Invalid URL" in res_file.json()["detail"]

    res_local = client.post("/api/jobs", json={"url": "http://127.0.0.1:8000/api/emergency-stop"})
    assert res_local.status_code == 400
    assert "prohibited" in res_local.json()["detail"].lower()

    res_meta = client.post("/api/jobs", json={"url": "http://169.254.169.254/metadata"})
    assert res_meta.status_code == 400
    assert "prohibited" in res_meta.json()["detail"].lower()

    # Valid public URL should be accepted
    res_valid = client.post("/api/jobs", json={"url": "https://example.com/valid_public_clip_test"})
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "queued"


# -----------------------------------------------------------------------------
# 11. Database Deduplication & Function Uniqueness Verification
# -----------------------------------------------------------------------------

def test_database_no_duplicate_functions():
    import ast
    from collections import Counter
    db_path = Path(__file__).resolve().parent.parent / "src" / "db.py"
    with open(db_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    func_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    counts = Counter(func_names)
    duplicates = {k: v for k, v in counts.items() if v > 1}
    assert len(duplicates) == 0, f"Duplicate functions found in src/db.py: {duplicates}"


# -----------------------------------------------------------------------------
# 12. File Upload Format & Size Ingestion Validation
# -----------------------------------------------------------------------------

def test_upload_file_format_and_size_validation(client, tmp_path):
    # Reject non-video extension (.txt)
    txt_file = tmp_path / "malicious.txt"
    txt_file.write_text("not a video")
    with open(txt_file, "rb") as f:
        res_txt = client.post("/api/jobs/upload", files={"file": ("malicious.txt", f, "text/plain")})
    assert res_txt.status_code == 400
    assert "Invalid video format" in res_txt.json()["detail"]

    # Reject empty video file
    empty_vid = tmp_path / "empty.mp4"
    empty_vid.write_bytes(b"")
    with open(empty_vid, "rb") as f:
        res_empty = client.post("/api/jobs/upload", files={"file": ("empty.mp4", f, "video/mp4")})
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()

    # Accept valid synthetic mp4
    clip_path = create_synthetic_test_video(str(tmp_path), duration_sec=1)
    with open(clip_path, "rb") as f:
        res_ok = client.post("/api/jobs/upload", files={"file": ("valid.mp4", f, "video/mp4")})
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "queued"


# -----------------------------------------------------------------------------
# 13. Storage Cleanup Expanded Scope Verification
# -----------------------------------------------------------------------------

def test_storage_cleanup_expanded_scope(client):
    os.makedirs("temp", exist_ok=True)
    dummy_cut = Path("temp") / "unit_test_raw_cut_9999.mp4"
    dummy_cut.write_bytes(b"dummy temporary cut content")
    assert dummy_cut.exists()

    res = client.post("/api/storage/cleanup")
    assert res.status_code == 200
    data = res.json()
    assert data["deleted_files"] >= 1
    assert not dummy_cut.exists()


# -----------------------------------------------------------------------------
# 14. Metadata Platform Whitelist Validation Guard
# -----------------------------------------------------------------------------

def test_metadata_platform_whitelist_guard():
    from src.db import update_video_metadata_field
    with pytest.raises(ValueError, match="Invalid platform"):
        update_video_metadata_field(
            target_type="short",
            target_id=9999,
            platform="invalid_social_network",
            field_name="title",
            new_value="Sample"
        )
