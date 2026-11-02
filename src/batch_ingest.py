"""
Batch Playlist & Channel Autonomous Ingest Engine for VedioHooks AI Media Factory.
Crawls YouTube playlists and channel feeds in flat-metadata mode, filters viral candidates,
and autonomously enqueues jobs into the persistent 24/7 processing pipeline.
"""

import uuid
from typing import Dict, Any, List, Optional
import yt_dlp

from src.db import create_job, list_jobs, is_emergency_stopped


def crawl_and_queue_playlist(
    playlist_url: str,
    account_id: str = "acc_motivation",
    max_items: int = 5,
    min_duration_sec: float = 60.0,
    max_duration_sec: float = 3600.0
) -> Dict[str, Any]:
    """
    Crawls a YouTube playlist or channel in flat metadata mode (zero full-video download upfront),
    filters candidates by duration, and queues them into the ACID SQLite jobs queue.
    """
    if is_emergency_stopped():
        raise RuntimeError("System is in EMERGENCY STOP mode. Cannot enqueue batch jobs.")

    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
    except Exception as e:
        raise RuntimeError(f"Failed to extract playlist metadata: {e}")

    entries = info.get("entries") or []
    if not entries and info.get("url"):
        # Single video treated as a 1-item batch
        entries = [info]

    existing_jobs = list_jobs(limit=100)
    existing_urls = {j.get("source_path") for j in existing_jobs}

    queued_jobs = []
    skipped_count = 0

    for idx, entry in enumerate(entries):
        if len(queued_jobs) >= max_items:
            break

        video_url = entry.get("url") or entry.get("webpage_url")
        if not video_url and entry.get("id"):
            video_url = f"https://www.youtube.com/watch?v={entry['id']}"

        if not video_url or video_url in existing_urls:
            skipped_count += 1
            continue

        duration = entry.get("duration") or 0.0
        # If duration is present, filter by range
        if duration > 0 and (duration < min_duration_sec or duration > max_duration_sec):
            skipped_count += 1
            continue

        job_id = str(uuid.uuid4())[:8]
        title = entry.get("title") or f"Batch Video #{idx+1}"

        create_job(
            job_id=job_id,
            source_type="url",
            source_path=video_url,
            priority=2,  # Batch ingestion default priority
            account_id=account_id
        )

        existing_urls.add(video_url)
        queued_jobs.append({
            "job_id": job_id,
            "title": title,
            "url": video_url,
            "duration": duration
        })

    return {
        "playlist_url": playlist_url,
        "account_id": account_id,
        "total_discovered": len(entries),
        "queued_count": len(queued_jobs),
        "skipped_count": skipped_count,
        "queued_jobs": queued_jobs
    }
