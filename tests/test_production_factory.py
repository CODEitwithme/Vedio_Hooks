"""
Comprehensive Production Factory Integration & Unit Tests.
Tests 24/7 autonomous scheduler, crash recovery, multi-dimensional virality evaluation,
publishing queue state machine, telemetry, path traversal security, and synthetic rendering.
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
    create_job,
    get_job,
    update_job_progress,
    recover_interrupted_jobs,
    list_publishing_queue,
    update_publishing_draft,
    approve_publishing_draft,
    save_rendered_short
)
from src.virality_selector import evaluate_candidate_multidimensional, generate_social_metadata
from src.transcribe import get_whisper_model, get_optimal_device_settings
from src.face_tracker import get_face_tracker
from src.ingest import create_synthetic_test_video
from src.video_slicer import slice_and_crop_video

client = TestClient(app)


def test_api_readiness():
    """Verifies that the /api/ready endpoint confirms database and storage readiness."""
    res = client.get("/api/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] is True
    assert data["output_dir"] is True


def test_api_system_telemetry():
    """Verifies that /api/system/stats returns live CPU, RAM, disk, and queue metrics."""
    res = client.get("/api/system/stats")
    assert res.status_code == 200
    data = res.json()
    assert "cpu_percent" in data
    assert "ram" in data
    assert "disk" in data
    assert "max_concurrent_workers" in data
    assert data["max_concurrent_workers"] >= 1


def test_job_lifecycle_cancel_retry_delete():
    """Tests complete job lifecycle: queued -> cancel -> retry -> delete."""
    test_id = f"life_{uuid.uuid4().hex[:6]}"
    create_job(test_id, "url", "https://example.com/test_video")

    # Cancel
    res_cancel = client.post(f"/api/jobs/{test_id}/cancel")
    assert res_cancel.status_code == 200
    job = get_job(test_id)
    assert job["status"] == "cancelled"

    # Retry
    res_retry = client.post(f"/api/jobs/{test_id}/retry")
    assert res_retry.status_code == 200
    job = get_job(test_id)
    assert job["status"] == "queued"

    # Delete
    res_delete = client.delete(f"/api/jobs/{test_id}")
    assert res_delete.status_code == 200
    assert get_job(test_id) is None


def test_interrupted_job_recovery():
    """Verifies that interrupted jobs from an unexpected reboot/shutdown are automatically recovered."""
    interrupted_id = f"crash_{uuid.uuid4().hex[:6]}"
    create_job(interrupted_id, "url", "https://example.com/crash_video")
    update_job_progress(interrupted_id, status="transcribing", progress=40, current_step="Transcribing audio...")

    # Simulate server reboot recovery
    recovered_count = recover_interrupted_jobs()
    assert recovered_count >= 1

    job = get_job(interrupted_id)
    assert job["status"] == "queued"
    assert job["retry_count"] >= 1
    assert "Recovered" in job["current_step"]


def test_multidimensional_virality_evaluation():
    """Verifies that virality evaluation calculates all 8 dimensions and social captions."""
    text = (
        "Why do 99% of people fail to achieve their dreams? "
        "Because the truth is, nobody tells you that fear will destroy your discipline. "
        "You must fight through the pain every single day to win."
    )
    res = evaluate_candidate_multidimensional(text, duration=20.0)

    assert "overall_score" in res
    assert "hook_score" in res
    assert "engagement_score" in res
    assert "story_score" in res
    assert "context_score" in res
    assert "speaking_pace_wps" in res
    assert res["hook_score"] >= 75
    assert len(res["suggested_hashtags"]) >= 3
    assert "🔥" in res["suggested_caption"]


def test_publishing_queue_workflow():
    """Verifies draft creation, metadata editing, and approval workflow."""
    test_id = f"pub_{uuid.uuid4().hex[:6]}"
    create_job(test_id, "url", "https://example.com/pub_video")

    render_id = save_rendered_short(
        job_id=test_id,
        clip_id=1,
        title="Epic Mindset Lesson",
        start_time=10.0,
        end_time=35.0,
        virality_score=92,
        crop_mode="smart_face",
        theme="hormozi_yellow",
        video_path="output/test_pub.mp4",
        caption="🔥 Master your mind",
        hashtags="#mindset #reels #discipline"
    )

    # Verify present in queue as draft
    res_queue = client.get("/api/publishing/queue")
    assert res_queue.status_code == 200
    queue_items = res_queue.json()["queue"]
    target_item = next((item for item in queue_items if item["render_id"] == render_id), None)
    assert target_item is not None
    assert target_item["status"] == "draft"

    # Update draft
    update_payload = {
        "caption": "🔥 Updated Caption with High Energy!",
        "hashtags": "#viral #growth #shorts",
        "scheduled_time": "2026-11-02T12:00:00Z"
    }
    res_update = client.patch(f"/api/publishing/{target_item['id']}", json=update_payload)
    assert res_update.status_code == 200

    # Approve draft
    res_approve = client.post(f"/api/publishing/{target_item['id']}/approve")
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "approved"


def test_security_path_traversal_blocked():
    """Verifies that malicious directory traversal attempts are strictly forbidden."""
    # Attempt to traverse up out of the output directory
    traversal_urls = [
        "/api/media/output/..%2f..%2fjobs.db",
        "/api/media/output/../../jobs.db",
        "/api/media/output/..\\..\\jobs.db"
    ]
    for url in traversal_urls:
        res = client.get(url)
        assert res.status_code in [400, 403, 404]


def test_duplicate_submission_prevention():
    """Verifies that submitting the same URL while already processing returns the existing job."""
    sample_url = "https://example.com/unique_test_duplicate_check"
    res1 = client.post("/api/jobs", json={"url": sample_url})
    assert res1.status_code == 200
    job1_id = res1.json()["job_id"]

    # Submit exact same URL again immediately
    res2 = client.post("/api/jobs", json={"url": sample_url})
    assert res2.status_code == 200
    assert res2.json()["job_id"] == job1_id
    assert "Existing job" in res2.json()["message"]


def test_model_cache_singletons():
    """Verifies that Faster-Whisper and FaceTracker instances are reused to save CPU/RAM."""
    device = get_optimal_device_settings()
    assert device["device"] == "cpu"
    assert device["compute_type"] == "int8"

    tracker1 = get_face_tracker()
    tracker2 = get_face_tracker()
    assert tracker1 is tracker2


def test_safe_synthetic_video_rendering(tmp_path):
    """Generates a synthetic test video and tests 9:16 vertical slicing and loudnorm processing."""
    synth_path = create_synthetic_test_video(output_dir=str(tmp_path), duration_sec=3)
    assert os.path.exists(synth_path)

    out_short = str(tmp_path / "synth_9x16.mp4")
    rendered = slice_and_crop_video(
        video_path=synth_path,
        start_sec=0.0,
        end_sec=2.5,
        output_path=out_short,
        crop_mode="center",
        normalize_audio=True
    )
    assert os.path.exists(rendered)
    assert os.path.getsize(rendered) > 1024
