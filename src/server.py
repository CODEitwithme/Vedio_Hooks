"""
FastAPI Server & Web Application for VedioHooks AI Media Factory.
Transforms long videos into viral 9:16 vertical shorts with face tracking,
karaoke captions, 24/7 autonomous scheduling, multi-account Instagram management,
AI Content Director (14-point strategic blueprints), and a commercial SaaS dashboard.
"""

import os
import sys
import uuid
import json
import mimetypes
import shutil
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import (
    init_db,
    get_db_connection,
    create_job,
    get_job,
    list_jobs,
    update_job_progress,
    cancel_job,
    retry_job,
    delete_job,
    get_database_stats,
    list_publishing_queue,
    update_publishing_draft,
    approve_publishing_draft,
    list_accounts,
    get_account,
    create_account,
    update_account,
    delete_account,
    list_content_sources,
    create_content_source,
    delete_content_source,
    save_ai_content_plan,
    list_ai_content_plans,
    is_emergency_stopped,
    set_emergency_stop,
    get_system_setting,
    set_system_setting,
    recover_interrupted_jobs,
    list_rendered_shorts,
    save_rendered_short,
    backup_database,
    create_dubbed_render,
    list_dubbed_renders,
    get_dubbed_render,
    save_hook_variant,
    list_hook_variants,
    update_hook_variant_render,
    add_publishing_draft,
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
    save_video_metadata,
    get_video_metadata,
    list_video_metadata,
    update_video_metadata_field,
    delete_video_metadata,
    save_thumbnail_asset,
    get_thumbnail_asset,
    list_thumbnail_assets,
    select_thumbnail_asset,
    delete_thumbnail_asset
)
from src.metadata_generator import (
    generate_video_metadata, build_title_variations, generate_youtube_metadata,
    generate_instagram_metadata, generate_tiktok_metadata, evaluate_metadata_quality, PLATFORM_LIMITS
)
from src.thumbnail_studio import (
    generate_thumbnail_suite, extract_candidate_frames, composite_thumbnail,
    generate_grid_crop_preview, generate_thumbnail_headline
)
from src.publishing_validator import validate_publishing_readiness, export_publishing_bundle
from src.scheduler import scheduler
from src.pipeline_worker import render_short_job, render_series_episode_job, batch_render_series_job
from src.series_engine import CliffhangerSeriesEngine, StoryArc, EpisodePlan, CLIFFHANGER_TYPES
from src.virality_selector import extract_all_words
from src.subtitle_generator import THEMES
from src.publishing import is_publishing_enabled, get_instagram_config, InstagramGraphAPIClient
from src.ai_director import generate_content_plan, build_director_heuristic_plan, NICHE_DIRECTOR_PROFILES
from src.dubbing_engine import list_curated_voices, synthesize_speech, dub_video_short
from src.hook_ab_engine import generate_hook_variants, render_hook_variant_overlay, queue_ab_split_test
from src.analytics import get_performance_analytics
from src.thumbnail_engine import generate_cover_thumbnails
from src.beat_sync import detect_audio_beats, align_word_timestamps_to_beats
from src.multi_platform_export import generate_multi_platform_package
from src.hardware_accel import detect_best_video_encoder, get_ffmpeg_encoding_args
from src.watermark_engine import apply_watermark
from src.batch_ingest import crawl_and_queue_playlist
from src.ingest import validate_ingest_url
from src.insights_engine import sync_post_insights, get_account_historical_performance
from src.sentiment_palette import classify_sentiment_and_palette
from src.dynamic_framing import reframe_dynamic_short
from src.deduplication import check_for_duplicate_content
from src.performance_report import generate_weekly_executive_report
from src.auto_zoom import apply_dynamic_auto_zoom
from src.hook_banner import apply_standalone_hook_banner, generate_smart_hook_text, BANNER_THEMES

# App lifespan with 24/7 autonomous scheduler startup & shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    # Start 24/7 Autonomous Scheduler
    scheduler.start()
    yield
    # Graceful stop
    scheduler.stop(wait=False)

app = FastAPI(
    title="VedioHooks AI - Multi-Account Media Factory API",
    description="Transforms long videos into viral 9:16 vertical shorts with face tracking, karaoke captions, 24/7 autonomous scheduling, and multi-account Instagram management.",
    version="3.0.0",
    lifespan=lifespan
)

cors_origins_env = os.environ.get("CORS_ORIGINS", "")
allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()] if cors_origins_env else [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request & Response Models ---

class URLProcessRequest(BaseModel):
    url: str
    account_id: Optional[str] = "acc_motivation"
    model_size: Optional[str] = "base.en"
    priority: Optional[int] = 1


class RenderClipRequest(BaseModel):
    crop_mode: Optional[str] = "smart_face"  # 'smart_face', 'split_stack', 'blur_fill', 'center'
    theme: Optional[str] = "hormozi_yellow"  # 'hormozi_yellow', 'hormozi_green', 'cyber_cyan', 'fire_orange', 'beast_red', 'clean_minimal'
    enable_ducking: Optional[bool] = False
    enable_jumpcuts: Optional[bool] = False
    target_language: Optional[str] = "en"
    enable_sfx: Optional[bool] = True
    enable_broll: Optional[bool] = False
    enable_auto_zoom: Optional[bool] = False
    hook_banner_text: Optional[str] = None
    hook_banner_theme: Optional[str] = None


class AutoZoomRequest(BaseModel):
    video_path: str
    zoom_scale: Optional[float] = 1.16
    job_id: Optional[str] = None
    render_id: Optional[int] = None


class HookBannerRequest(BaseModel):
    video_path: str
    hook_text: str
    theme: Optional[str] = "hormozi_yellow"
    duration_sec: Optional[float] = 3.5
    render_id: Optional[int] = None


class AutoScheduleRequest(BaseModel):
    account_id: Optional[str] = None


class DubbingPreviewRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "en-US-ChristopherNeural"
    rate: Optional[int] = 0
    pitch: Optional[int] = 0


class DubbingRenderRequest(BaseModel):
    video_path: str
    transcript_text: str
    target_language: Optional[str] = "es"
    voice_id: Optional[str] = "es-ES-AlvaroNeural"
    blend_mode: Optional[str] = "ducked"  # 'ducked', 'replace', 'bilingual'
    speed: Optional[float] = 1.0
    pitch: Optional[int] = 0
    render_id: Optional[int] = None
    account_id: Optional[str] = "acc_motivation"


class HookVariantsGenerateRequest(BaseModel):
    clip_text: str
    niche: Optional[str] = "Motivation"
    base_score: Optional[int] = 85
    job_id: Optional[str] = "manual"
    clip_id: Optional[int] = 0
    account_id: Optional[str] = "acc_motivation"


class HookVariantRenderRequest(BaseModel):
    video_path: str
    hook_overlay_text: str
    accent_color: Optional[str] = "#f59e0b"
    duration_sec: Optional[float] = 2.5
    variant_id: Optional[int] = None


class HookQueueABRequest(BaseModel):
    account_id: str
    job_id: str
    variants: List[Dict[str, Any]]
    base_caption: Optional[str] = ""
    hashtags: Optional[str] = ""


class CoverThumbnailsRequest(BaseModel):
    video_path: str
    title: Optional[str] = "VIRAL SHORT"
    niche: Optional[str] = "Motivation"
    time_sec: Optional[float] = 1.0


class BeatSyncRequest(BaseModel):
    video_path: str
    max_duration: Optional[float] = 45.0


class MultiPlatformExportRequest(BaseModel):
    title: str
    hook_text: str
    script_summary: str
    niche: Optional[str] = "Motivation"
    base_hashtags: Optional[str] = None


class WatermarkApplyRequest(BaseModel):
    video_path: str
    handle: Optional[str] = "@vediohooks"
    position: Optional[str] = "top_right"
    opacity: Optional[float] = 0.75


class BatchIngestRequest(BaseModel):
    playlist_url: str
    account_id: Optional[str] = "acc_motivation"
    max_items: Optional[int] = 5
    min_duration_sec: Optional[float] = 60.0
    max_duration_sec: Optional[float] = 3600.0


class InsightsSyncRequest(BaseModel):
    publishing_id: int
    account_id: Optional[str] = "acc_motivation"
    post_id: Optional[str] = None


class SentimentPaletteRequest(BaseModel):
    transcript_text: str
    niche: Optional[str] = "Motivation"
    virality_score: Optional[int] = 85


class DuplicateCheckRequest(BaseModel):
    transcript_text: str
    duration_sec: Optional[float] = 0.0
    threshold: Optional[float] = 0.75


class DynamicReframeRequest(BaseModel):
    video_path: str
    start_sec: float
    end_sec: float
    target_width: Optional[int] = 1080
    target_height: Optional[int] = 1920


class PublishingDraftUpdate(BaseModel):
    caption: str
    hashtags: str
    scheduled_time: Optional[str] = None


class AccountCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str
    handle: Optional[str] = ""
    niche: Optional[str] = "Motivation"
    avatar_emoji: Optional[str] = "⚡"
    brand_color: Optional[str] = "#6366f1"
    status: Optional[str] = "active"
    daily_target: Optional[int] = 2
    posting_schedule: Optional[str] = "09:00, 18:00"
    ai_personality: Optional[str] = "Creative content strategist"
    content_style: Optional[str] = "High-energy vertical storytelling"
    default_theme: Optional[str] = "hormozi_yellow"
    default_crop_mode: Optional[str] = "smart_face"
    hashtag_strategy: Optional[str] = "#shorts #reels #viral"
    caption_template: Optional[str] = "🔥 {hook}\n\n💡 {punchline}\n\n{hashtags}"


class AccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    handle: Optional[str] = None
    niche: Optional[str] = None
    avatar_emoji: Optional[str] = None
    brand_color: Optional[str] = None
    status: Optional[str] = None
    daily_target: Optional[int] = None
    posting_schedule: Optional[str] = None
    ai_personality: Optional[str] = None
    content_style: Optional[str] = None
    default_theme: Optional[str] = None
    default_crop_mode: Optional[str] = None
    hashtag_strategy: Optional[str] = None
    caption_template: Optional[str] = None
    meta_access_token: Optional[str] = None
    meta_account_id: Optional[str] = None
    meta_connected: Optional[int] = None


class ContentSourceCreateRequest(BaseModel):
    account_id: str
    source_type: str = "youtube_curated"  # youtube_curated, rss, search_keyword, podcast
    source_url_or_path: str
    title: str
    attribution: Optional[str] = ""
    verification_notes: Optional[str] = ""


class GeneratePlanRequest(BaseModel):
    account_id: str
    job_id: Optional[str] = None
    clip_id: Optional[int] = None
    custom_topic: Optional[str] = None
    use_ai: Optional[bool] = False


class EmergencyStopRequest(BaseModel):
    stopped: Optional[bool] = None


# --- AI Cliffhanger Series Engine Models ---

class SeriesAnalyzeArcsRequest(BaseModel):
    job_id: Optional[str] = None
    transcript_path: Optional[str] = None


class SeriesGenerateRequest(BaseModel):
    job_id: Optional[str] = None
    transcript_path: Optional[str] = None
    account_id: Optional[str] = "acc_motivation"
    story_arc_id: Optional[str] = None
    story_arc: Optional[Dict[str, Any]] = None
    episode_count: Optional[int] = None
    custom_start_sec: Optional[float] = None
    custom_end_sec: Optional[float] = None
    generation_mode: Optional[str] = "auto"  # auto, guided, custom


class EpisodeUpdateRequest(BaseModel):
    title: Optional[str] = None
    opening_hook: Optional[str] = None
    cliffhanger_text: Optional[str] = None
    next_teaser: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class EpisodeMergeRequest(BaseModel):
    ep1_id: int
    ep2_id: int


class EpisodeSplitRequest(BaseModel):
    split_time: float
    ep1_cliffhanger: Optional[str] = None
    ep2_hook: Optional[str] = None


class EpisodeReorderRequest(BaseModel):
    episode_ids: List[int]


class SeriesRenderEpisodeRequest(BaseModel):
    crop_mode: Optional[str] = "smart_face"
    theme: Optional[str] = "hormozi_yellow"
    enable_ducking: Optional[bool] = True
    enable_jumpcuts: Optional[bool] = False
    enable_sfx: Optional[bool] = True
    enable_auto_zoom: Optional[bool] = False


class SeriesBatchRenderRequest(BaseModel):
    crop_mode: Optional[str] = "smart_face"
    theme: Optional[str] = "hormozi_yellow"


# --- AI Metadata & SEO Generator Request Models ---

class MetadataGenerateRequest(BaseModel):
    target_type: str = "short"  # short, episode, long_form
    target_id: Any
    niche: Optional[str] = "Motivation"
    custom_title: Optional[str] = None


class MetadataSaveRequest(BaseModel):
    target_type: str = "short"
    target_id: Any
    title: str
    niche: str = "Motivation"
    youtube: Dict[str, Any]
    instagram: Dict[str, Any]
    tiktok: Dict[str, Any]
    title_variations: Optional[Dict[str, Any]] = None
    quality_score: Optional[int] = 85
    account_id: Optional[str] = "acc_motivation"


class MetadataRegenerateFieldRequest(BaseModel):
    target_type: str = "short"
    target_id: Any
    platform: str = "youtube"  # youtube, instagram, tiktok
    field_name: str = "title"  # title, description, caption, hashtags, tags
    variation_type: Optional[str] = None


class MetadataBatchRequest(BaseModel):
    items: List[Dict[str, Any]]  # [{target_type, target_id, niche, title}]


# --- AI Thumbnail & Cover Studio Request Models ---

class ThumbnailGenerateRequest(BaseModel):
    target_type: Optional[str] = "short"  # short, episode, long_form
    target_id: Optional[Any] = None
    video_path: Optional[str] = None
    title: Optional[str] = None
    time_sec: Optional[float] = 1.0
    aspect_ratio: Optional[str] = "9:16"  # 16:9, 9:16, 1:1
    style_mode: Optional[str] = "auto"    # auto, face_focused, cinematic, custom
    custom_headline: Optional[str] = None
    custom_placement: Optional[str] = "safe_auto"  # safe_auto, top, center, bottom
    niche: Optional[str] = "Motivation"
    brand_handle: Optional[str] = "@vediohooks"


class ThumbnailSelectRequest(BaseModel):
    asset_id: int
    target_type: str = "short"
    target_id: Any


class ThumbnailExtractFramesRequest(BaseModel):
    target_type: str = "short"
    target_id: Any


# --- HTTP 206 Range Video Streaming with Security Hardening ---

def stream_video_with_range(request: Request, path: Path):
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    file_size = path.stat().st_size
    range_header = request.headers.get("Range")
    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or "video/mp4"

    if range_header:
        byte_range = range_header.strip().lower().replace("bytes=", "")
        parts = byte_range.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

        chunk_size = end - start + 1

        def iter_chunk():
            with open(path, "rb") as f:
                f.seek(start)
                bytes_left = chunk_size
                while bytes_left > 0:
                    read_len = min(65536, bytes_left)
                    data = f.read(read_len)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": content_type,
        }
        return StreamingResponse(iter_chunk(), status_code=206, headers=headers)

    return FileResponse(path, media_type=content_type)


# --- System Health & Readiness Endpoints ---

@app.get("/api/health")
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "python_version": sys.version,
        "cpu_threads": os.cpu_count(),
        "scheduler_running": scheduler.running,
        "emergency_stop": is_emergency_stopped()
    }


@app.get("/api/ready")
def readiness_check():
    """Readiness endpoint verifying storage directories and database."""
    return {
        "status": "ready",
        "database": os.path.exists("jobs.db"),
        "temp_dir": os.path.exists("temp"),
        "output_dir": os.path.exists("output"),
        "models_dir": os.path.exists("models")
    }


@app.get("/api/system/stats")
def system_stats():
    """Returns real-time CPU, RAM, Disk, and job queue telemetry."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(".")
        ram_info = {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent": mem.percent
        }
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent
        }
    except Exception:
        cpu_percent = 0.0
        ram_info = {"total_gb": 0, "used_gb": 0, "percent": 0}
        disk_info = {"total_gb": 0, "free_gb": 0, "percent": 0}

    db_stats = get_database_stats()
    ig_cfg = get_instagram_config()

    return {
        "cpu_percent": cpu_percent,
        "ram": ram_info,
        "disk": disk_info,
        "max_concurrent_workers": scheduler.max_concurrent,
        "active_workers": len(scheduler.active_jobs),
        "scheduler_running": scheduler.running,
        "emergency_stop": is_emergency_stopped(),
        "global_automation": get_system_setting("global_automation", "1") == "1",
        "db_stats": db_stats,
        "instagram_publishing_enabled": is_publishing_enabled(),
        "instagram_configured": ig_cfg.is_configured
    }


# --- Multi-Account Management Endpoints ---

@app.get("/api/accounts")
def get_accounts_endpoint():
    """Lists all configured Instagram accounts with stats."""
    return {"accounts": list_accounts()}


@app.get("/api/accounts/{account_id}")
def get_single_account_endpoint(account_id: str):
    """Retrieves full details for a single account."""
    acc = get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


@app.post("/api/accounts")
def create_account_endpoint(req: AccountCreateRequest):
    """Creates a new Instagram account entry."""
    data = req.model_dump(exclude_unset=True)
    acc = create_account(data)
    return acc


@app.patch("/api/accounts/{account_id}")
def update_account_endpoint(account_id: str, req: AccountUpdateRequest):
    """Updates account fields dynamically."""
    data = req.model_dump(exclude_unset=True)
    success = update_account(account_id, data)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found or no valid fields to update")
    return {"account_id": account_id, "updated": True}


@app.delete("/api/accounts/{account_id}")
def delete_account_endpoint(account_id: str):
    """Deletes an account and cascades deletions."""
    success = delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"account_id": account_id, "deleted": True}


@app.post("/api/accounts/{account_id}/toggle")
def toggle_account_endpoint(account_id: str):
    """Toggles account status between active and paused."""
    acc = get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    new_status = "paused" if acc.get("status") == "active" else "active"
    update_account(account_id, {"status": new_status})
    return {"account_id": account_id, "status": new_status}


@app.get("/api/niches")
def get_niches_endpoint():
    """Returns niche profiles and presets."""
    return {"niches": NICHE_DIRECTOR_PROFILES}


# --- Content Sources Endpoints ---

@app.get("/api/sources")
def get_sources_endpoint(account_id: Optional[str] = Query(None), limit: int = 50):
    """Lists content sources, optionally filtered by account."""
    return {"sources": list_content_sources(account_id=account_id, limit=limit)}


@app.post("/api/sources")
def create_source_endpoint(req: ContentSourceCreateRequest):
    """Registers a content source with verification notes and attribution."""
    src = create_content_source(
        account_id=req.account_id,
        source_type=req.source_type,
        source_url_or_path=req.source_url_or_path,
        title=req.title,
        attribution=req.attribution or "",
        verification_notes=req.verification_notes or ""
    )
    return src


@app.delete("/api/sources/{source_id}")
def delete_source_endpoint(source_id: str):
    """Removes a content source."""
    success = delete_content_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"source_id": source_id, "deleted": True}


# --- AI Content Director Endpoints ---

@app.get("/api/ai-plans")
def get_ai_plans_endpoint(account_id: Optional[str] = Query(None), limit: int = 50):
    """Lists structured 14-point strategic content plans."""
    return {"plans": list_ai_content_plans(account_id=account_id, limit=limit)}


@app.post("/api/ai-plans/generate")
def generate_ai_plan_endpoint(req: GeneratePlanRequest):
    """Generates and persists a structured 14-point strategic content blueprint."""
    account = get_account(req.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    clip_dict = None
    transcript_data = {
        "full_text": req.custom_topic or f"Mastering {account['niche']}: The core principles, tactics, and mindset needed to achieve outstanding results.",
        "duration": 35.0
    }

    if req.job_id:
        job = get_job(req.job_id)
        if job:
            if job.get("transcript"):
                transcript_data = {
                    "full_text": job["transcript"],
                    "duration": float(job.get("duration", 35.0))
                }
            if req.clip_id and job.get("clips"):
                matching = [c for c in job["clips"] if c.get("id") == req.clip_id]
                if matching:
                    clip_dict = matching[0]

    try:
        plan_dict = generate_content_plan(
            account_id=req.account_id,
            transcript_data=transcript_data,
            clip=clip_dict,
            job_id=req.job_id
        )
        return {
            "plan": plan_dict,
            "message": "14-point strategic content blueprint generated successfully"
        }
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


# --- Automation & Emergency Controls ---

@app.get("/api/automation/status")
def get_automation_status():
    """Returns current emergency stop, global automation, and scheduler status."""
    return {
        "emergency_stop": is_emergency_stopped(),
        "global_automation": get_system_setting("global_automation", "1") == "1",
        "scheduler_running": scheduler.running,
        "active_workers": len(scheduler.active_jobs),
        "max_concurrent_workers": scheduler.max_concurrent
    }


@app.post("/api/automation/emergency-stop")
def toggle_emergency_stop_endpoint(req: Optional[EmergencyStopRequest] = None):
    """Engages or disengages global emergency stop."""
    current = is_emergency_stopped()
    new_state = req.stopped if (req and req.stopped is not None) else not current
    set_emergency_stop(new_state)
    return {
        "emergency_stop": new_state,
        "status": "engaged" if new_state else "disengaged",
        "message": "EMERGENCY STOP ACTIVE: All processing and publishing halted." if new_state else "EMERGENCY STOP DISENGAGED: Autonomous operations resumed."
    }


@app.post("/api/automation/toggle")
def toggle_automation_endpoint():
    """Toggles global 24/7 autonomous scheduling."""
    current = get_system_setting("global_automation", "1") == "1"
    new_state = not current
    set_system_setting("global_automation", "1" if new_state else "0")
    return {"global_automation": new_state}


@app.post("/api/automation/recover")
def recover_interrupted_endpoint():
    """Resets interrupted jobs back into queued state."""
    recovered = recover_interrupted_jobs()
    return {
        "recovered_count": recovered,
        "message": f"Successfully recovered {recovered} interrupted jobs."
    }


@app.post("/api/storage/cleanup")
def storage_cleanup_endpoint():
    """Cleans up temporary wav, ass, upload, intermediate raw cuts, and cached frame files to reclaim disk space."""
    temp_dir = Path("temp")
    deleted_count = 0
    freed_bytes = 0
    now_ts = time.time()
    cutoff_24h = now_ts - (24 * 3600)

    if temp_dir.exists():
        for f in temp_dir.iterdir():
            if not f.is_file():
                continue
            name_lower = f.name.lower()
            suffix_lower = f.suffix.lower()

            # Preserve critical persistent metadata files
            if name_lower.endswith("_transcript.json") or name_lower.endswith("_viral_clips.json") or name_lower.endswith(".db"):
                continue

            is_temp_artifact = (
                suffix_lower in [".wav", ".ass", ".tmp", ".log"]
                or "_raw_cut_" in name_lower
                or "_raw_" in name_lower
                or "_upload" in name_lower
                or name_lower.startswith("frame_candidate_")
                or (f.stat().st_mtime < cutoff_24h and suffix_lower not in [".json", ".db"])
            )
            if is_temp_artifact:
                try:
                    size = f.stat().st_size
                    f.unlink()
                    deleted_count += 1
                    freed_bytes += size
                except Exception:
                    pass
    return {
        "deleted_files": deleted_count,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "message": f"Cleaned {deleted_count} temporary files, freeing {round(freed_bytes / (1024 * 1024), 2)} MB."
    }


@app.post("/api/database/backup")
def trigger_database_backup():
    """Creates an atomic SQLite database backup snapshot."""
    try:
        path = backup_database()
        return {
            "status": "success",
            "backup_path": path,
            "message": f"Atomic database backup successfully created: {path}"
        }
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/renders/{render_id}/thumbnail")
def get_render_thumbnail(render_id: int, time_sec: float = 1.0):
    """Extracts and streams a high-resolution JPG thumbnail frame from a rendered 9:16 short."""
    renders = list_rendered_shorts(limit=200)
    target = next((r for r in renders if r.get("id") == render_id), None)
    if not target or not target.get("video_path"):
        raise HTTPException(status_code=404, detail="Render not found")

    video_path = Path(target["video_path"])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Rendered video file missing")

    import subprocess
    thumb_path = Path("temp") / f"thumb_{render_id}_{int(time_sec * 10)}.jpg"
    if not thumb_path.exists():
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(max(0.0, time_sec)),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path)
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)

    if not thumb_path.exists():
        raise HTTPException(status_code=500, detail="Failed to extract thumbnail frame")

    return FileResponse(thumb_path, media_type="image/jpeg")


# --- Video Jobs & Processing Endpoints ---

@app.post("/api/jobs")
def submit_url_job(req: URLProcessRequest):
    """Submits a YouTube / Web URL into the 24/7 persistent queue."""
    if is_emergency_stopped():
        raise HTTPException(status_code=423, detail="System is in EMERGENCY STOP mode. Resume automation before creating jobs.")

    if not req.url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    try:
        validate_ingest_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")

    # Duplicate prevention: check if an identical job is currently queued or in-flight
    existing_jobs = list_jobs(limit=20)
    for j in existing_jobs:
        if j.get("source_path") == req.url and j.get("status") in ("queued", "downloading", "transcribing", "analyzing"):
            return {
                "job_id": j["id"],
                "status": j["status"],
                "account_id": j.get("account_id"),
                "message": "Existing job is already in progress or queued."
            }

    job_id = str(uuid.uuid4())[:8]
    create_job(
        job_id=job_id,
        source_type="url",
        source_path=req.url,
        priority=req.priority or 1,
        account_id=req.account_id or "acc_motivation"
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "account_id": req.account_id or "acc_motivation",
        "message": "Video queued for 24/7 autonomous processing"
    }


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
MAX_UPLOAD_SIZE_BYTES = 1024 * 1024 * 1024  # 1 GB


@app.post("/api/jobs/upload")
async def upload_file_job(file: UploadFile = File(...), account_id: Optional[str] = Form("acc_motivation")):
    """Uploads a local video file and enqueues virality analysis."""
    if is_emergency_stopped():
        raise HTTPException(status_code=423, detail="System is in EMERGENCY STOP mode. Resume automation before creating jobs.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid video format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
        )

    job_id = str(uuid.uuid4())[:8]
    save_path = os.path.join("temp", f"{job_id}_upload{ext}")
    os.makedirs("temp", exist_ok=True)

    total_bytes = 0
    try:
        with open(save_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 1GB.")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise
    except Exception as ex:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(ex)}")

    if total_bytes == 0:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=400, detail="Uploaded video file is empty.")

    create_job(
        job_id=job_id,
        source_type="file",
        source_path=save_path,
        priority=2,
        account_id=account_id or "acc_motivation"
    )
    return {"job_id": job_id, "status": "queued", "account_id": account_id, "filename": file.filename}


@app.get("/api/jobs")
def get_recent_jobs(account_id: Optional[str] = Query(None), limit: int = 50):
    """Lists recent jobs with their statuses and renders count."""
    return {"jobs": list_jobs(account_id=account_id, limit=limit)}


@app.get("/api/jobs/{job_id}")
def get_job_details(job_id: str):
    """Retrieves full job status, clips, and rendered shorts."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str):
    """Cancels a queued or in-progress job."""
    success = cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or could not be cancelled")
    return {"job_id": job_id, "status": "cancelled", "message": "Job successfully cancelled"}


@app.post("/api/jobs/{job_id}/retry")
def retry_job_endpoint(job_id: str):
    """Manually resets a failed or cancelled job back into the queue."""
    success = retry_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": "queued", "message": "Job re-enqueued for autonomous processing"}


@app.delete("/api/jobs/{job_id}")
def delete_job_endpoint(job_id: str):
    """Deletes job and associated records from SQLite."""
    success = delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "deleted": True}


@app.post("/api/jobs/{job_id}/render/{clip_id}")
def render_clip_endpoint(job_id: str, clip_id: int, req: RenderClipRequest):
    """Renders a selected viral clip into a finished 9:16 short with karaoke subtitles."""
    try:
        res = render_short_job(
            job_id=job_id,
            clip_id=clip_id,
            crop_mode=req.crop_mode or "smart_face",
            theme=req.theme or "hormozi_yellow",
            enable_ducking=bool(req.enable_ducking),
            enable_jumpcuts=bool(req.enable_jumpcuts),
            target_language=req.target_language or "en",
            enable_sfx=bool(req.enable_sfx if req.enable_sfx is not None else True),
            enable_broll=bool(req.enable_broll),
            enable_auto_zoom=bool(req.enable_auto_zoom),
            hook_banner_text=req.hook_banner_text,
            hook_banner_theme=req.hook_banner_theme
        )
        return res
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.get("/api/renders")
@app.get("/api/rendered-shorts")
def get_renders_endpoint(account_id: Optional[str] = Query(None), status: Optional[str] = None, limit: int = 50):
    """Lists rendered 9:16 vertical shorts."""
    items = list_rendered_shorts(account_id=account_id, status=status, limit=limit)
    return {"renders": items, "shorts": items, "total": len(items)}


@app.post("/api/renders/{render_id}/send-to-draft")
def send_render_to_draft_endpoint(render_id: int):
    """Queues a rendered short directly into the Instagram publishing calendar."""
    queue = list_publishing_queue(limit=200)
    existing = next((q for q in queue if q.get("render_id") == render_id), None)
    if existing:
        return {"status": "already_exists", "publishing_id": existing["id"], "message": "Draft already exists in publishing queue."}

    renders = list_rendered_shorts(limit=200)
    target = next((r for r in renders if r.get("id") == render_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Render not found")

    account_id = target.get("account_id") or "acc_motivation"
    caption = target.get("caption") or f"🔥 {target.get('title', 'Highlight')}"
    hashtags = target.get("hashtags") or "#shorts #reels #viral"

    conn = get_db_connection()
    with conn:
        cur = conn.execute("""
            INSERT INTO publishing_queue (account_id, render_id, job_id, platform, status, caption, hashtags)
            VALUES (?, ?, ?, 'instagram', 'draft', ?, ?)
        """, (
            account_id,
            target["id"],
            target.get("job_id"),
            caption,
            hashtags
        ))
        new_pub_id = cur.lastrowid
    conn.close()

    return {"status": "created", "publishing_id": new_pub_id, "message": "Short successfully queued to Instagram drafts."}


@app.get("/api/media/{folder}/{filename}")
def stream_media(folder: str, filename: str, request: Request):
    """Streams a video or audio file with strict path traversal security checks."""
    if folder not in ["temp", "output"]:
        raise HTTPException(status_code=400, detail="Invalid media folder")

    base_dir = Path(folder).resolve()
    target_path = (base_dir / filename).resolve()

    # Security: Path traversal mitigation
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: Path traversal detected")

    if not target_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    return stream_video_with_range(request, target_path)


# --- Publishing Queue Endpoints ---

@app.get("/api/publishing/queue")
def get_publishing_queue(account_id: Optional[str] = Query(None), status: Optional[str] = None, limit: int = 50):
    """Lists social publishing items and drafts."""
    return {"queue": list_publishing_queue(account_id=account_id, status=status, limit=limit)}


@app.patch("/api/publishing/{publishing_id}")
def update_draft(publishing_id: int, req: PublishingDraftUpdate):
    """Updates caption, hashtags, and scheduled time for an Instagram draft."""
    success = update_publishing_draft(
        publishing_id=publishing_id,
        caption=req.caption,
        hashtags=req.hashtags,
        scheduled_time=req.scheduled_time
    )
    if not success:
        raise HTTPException(status_code=404, detail="Publishing draft not found")
    return {"publishing_id": publishing_id, "updated": True}


@app.post("/api/publishing/{publishing_id}/approve")
def approve_draft(publishing_id: int):
    """Approves a draft for future Instagram publishing."""
    success = approve_publishing_draft(publishing_id)
    if not success:
        raise HTTPException(status_code=404, detail="Publishing draft not found")
    return {"publishing_id": publishing_id, "status": "approved"}


@app.post("/api/publishing/{publishing_id}/simulate_publish")
def test_publish_guard(publishing_id: int):
    """Simulates publishing validation and chunked resumable upload dry-run without live API mutations."""
    items = list_publishing_queue()
    target = next((item for item in items if item["id"] == publishing_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Publishing item not found")

    client = InstagramGraphAPIClient()
    video_path = target.get("video_path")
    resumable_telemetry = None
    if video_path and os.path.exists(video_path):
        resumable_telemetry = client.simulate_resumable_upload(video_path)

    is_approved = (target.get("status") == "approved")
    return {
        "status": "simulated_success",
        "draft_id": publishing_id,
        "is_approved": is_approved,
        "publishing_enabled": is_publishing_enabled(),
        "video_path": video_path,
        "resumable_upload_telemetry": resumable_telemetry
    }


@app.post("/api/publishing/auto-schedule-week")
def auto_schedule_week_endpoint(req: Optional[AutoScheduleRequest] = None):
    """Automatically distributes queued drafts across optimal 7-day niche posting windows."""
    from src.auto_scheduler import auto_schedule_7_day_week
    account_id = req.account_id if req else None
    return auto_schedule_7_day_week(account_id=account_id)


@app.get("/api/renders/{render_id}/retention")
def get_render_retention_endpoint(render_id: int):
    """Calculates second-by-second predictive audience retention curve for a rendered short."""
    from src.retention_predictor import calculate_retention_curve
    renders = list_rendered_shorts(limit=200)
    target = next((r for r in renders if r["id"] == render_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Rendered short not found")

    job_id = target["job_id"]
    job = get_job(job_id)
    words = []
    if job and job.get("transcript_json_path") and os.path.exists(job["transcript_json_path"]):
        try:
            with open(job["transcript_json_path"], "r", encoding="utf-8") as f:
                tdata = json.load(f)
                start_t = target["start_time"]
                end_t = target["end_time"]
                for w in tdata.get("words", []):
                    if w["start"] >= start_t and w["end"] <= end_t:
                        words.append({
                            "word": w["word"],
                            "start": round(w["start"] - start_t, 2),
                            "end": round(w["end"] - start_t, 2)
                        })
        except Exception:
            pass

    return calculate_retention_curve(
        words=words,
        duration_sec=target["duration"] or (target["end_time"] - target["start_time"]),
        virality_score=target["virality_score"]
    )


# --- AI Voice Dubbing Lab Endpoints ---

@app.get("/api/dubbing/voices")
def get_dubbing_voices(language: Optional[str] = None):
    """Returns curated neural voices for multi-language dubbing."""
    return {"voices": list_curated_voices(language)}


@app.post("/api/dubbing/preview-voice")
def preview_voice_endpoint(req: DubbingPreviewRequest):
    """Generates a quick audio sample for a selected voice."""
    if not req.text:
        req.text = "Discipline and daily consistency is the key to unstoppable growth."
    out_audio = synthesize_speech(
        text=req.text,
        voice_id=req.voice_id or "en-US-ChristopherNeural",
        rate_percent=req.rate or 0,
        pitch_hz=req.pitch or 0
    )
    if not os.path.exists(out_audio):
        raise HTTPException(status_code=500, detail="Voice synthesis failed")
    return FileResponse(out_audio, media_type="audio/mpeg")


@app.post("/api/dubbing/render")
def dub_render_endpoint(req: DubbingRenderRequest):
    """Synthesizes, time-stretches, and blends a multi-language dubbed voiceover onto a short."""
    if is_emergency_stopped():
        raise HTTPException(status_code=423, detail="System in EMERGENCY STOP mode")
    try:
        res = dub_video_short(
            source_video_path=req.video_path,
            transcript_text=req.transcript_text,
            target_language=req.target_language or "es",
            voice_id=req.voice_id or "es-ES-AlvaroNeural",
            blend_mode=req.blend_mode or "ducked",
            speed=req.speed or 1.0,
            pitch=req.pitch or 0,
            render_id=req.render_id,
            account_id=req.account_id or "acc_motivation"
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dubbing/history")
def get_dubbed_history(limit: int = 50, account_id: Optional[str] = None):
    """Returns history of previously dubbed video shorts."""
    return {"history": list_dubbed_renders(limit=limit, account_id=account_id)}


# --- Viral Hook A/B Studio Endpoints ---

@app.post("/api/hooks/generate-variants")
def generate_hook_variants_endpoint(req: HookVariantsGenerateRequest):
    """Generates 3 psychologically distinct viral opening hook frameworks."""
    variants = generate_hook_variants(
        clip_text=req.clip_text,
        niche=req.niche or "Motivation",
        base_score=req.base_score or 85,
        job_id=req.job_id or "manual",
        clip_id=req.clip_id or 0,
        account_id=req.account_id or "acc_motivation"
    )
    return {"variants": variants}


@app.post("/api/hooks/render-variant")
def render_hook_variant_endpoint(req: HookVariantRenderRequest):
    """Burns a viral hook intro banner onto the first 2.5s of the video short."""
    try:
        out_p = render_hook_variant_overlay(
            source_video_path=req.video_path,
            hook_overlay_text=req.hook_overlay_text,
            accent_color=req.accent_color or "#f59e0b",
            duration_sec=req.duration_sec or 2.5,
            variant_id=req.variant_id
        )
        return {"rendered_video_path": out_p, "variant_id": req.variant_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hooks/queue-ab-test")
def queue_ab_test_endpoint(req: HookQueueABRequest):
    """Schedules the 3 variants as a linked A/B split-test in the Instagram publishing queue."""
    draft_ids = queue_ab_split_test(
        account_id=req.account_id,
        job_id=req.job_id,
        variants=req.variants,
        base_caption=req.base_caption or "",
        hashtags=req.hashtags or "#viral #shorts #reels"
    )
    return {"status": "queued", "draft_ids": draft_ids, "count": len(draft_ids)}


# --- Dynamic Real-Time Analytics & Performance ---

@app.get("/api/analytics")
def get_analytics_endpoint(account_id: Optional[str] = None):
    """Computes live real-time operational analytics and virality metrics."""
    return get_performance_analytics(account_id=account_id)


# --- 9:16 High-CTR Cover Thumbnail Studio (Legacy) ---

@app.post("/api/thumbnails/legacy-covers")
def generate_legacy_thumbnails_endpoint(req: CoverThumbnailsRequest):
    """Generates 3 distinct high-converting cover thumbnail styles (legacy endpoint)."""
    try:
        covers = generate_cover_thumbnails(
            video_path=req.video_path,
            title=req.title or "VIRAL SHORT",
            niche=req.niche or "Motivation",
            time_sec=req.time_sec or 1.0
        )
        return {"covers": covers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/renders/{render_id}/covers")
def get_render_covers_endpoint(render_id: int):
    """Generates 3 cover thumbnail variants for a rendered short by ID."""
    renders = list_rendered_shorts(limit=200)
    target = next((r for r in renders if r["id"] == render_id), None)
    if not target or not os.path.exists(target["video_path"]):
        raise HTTPException(status_code=404, detail="Rendered video not found")

    covers = generate_cover_thumbnails(
        video_path=target["video_path"],
        title=target.get("title") or "VIRAL HIGHLIGHT",
        niche="Motivation",
        time_sec=1.0
    )
    return {"covers": covers, "render_id": render_id}


# --- Sound Design Beat-Sync Engine ---

@app.post("/api/audio/beat-sync")
def beat_sync_endpoint(req: BeatSyncRequest):
    """Detects musical downbeats, BPM tempo, and transient rhythm spikes."""
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail="Audio/video file not found")
    res = detect_audio_beats(req.video_path, max_duration=req.max_duration or 45.0)
    return res


# --- Multi-Platform Algorithm Export (Reels + Shorts + TikTok) ---

@app.post("/api/export/multi-platform")
def export_multi_platform_endpoint(req: MultiPlatformExportRequest):
    """Generates tailored copy packages for Instagram Reels, YouTube Shorts, and TikTok."""
    package = generate_multi_platform_package(
        title=req.title,
        hook_text=req.hook_text,
        script_summary=req.script_summary,
        niche=req.niche or "Motivation",
        base_hashtags=req.base_hashtags
    )
    return package


# --- Hardware Acceleration Probing ---

@app.get("/api/system/hardware")
def get_hardware_acceleration():
    """Probes GPU/Hardware acceleration capabilities (NVENC, AMF, QSV, MediaFoundation)."""
    return detect_best_video_encoder()


# --- Account Watermark & Branding ---

@app.post("/api/watermark/apply")
def apply_watermark_endpoint(req: WatermarkApplyRequest):
    """Burns semi-transparent account watermark into vertical short to prevent repost theft."""
    try:
        out_path = apply_watermark(
            source_video_path=req.video_path,
            handle=req.handle or "@vediohooks",
            position=req.position or "top_right",
            opacity=req.opacity or 0.75
        )
        return {"watermarked_video_path": out_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Batch Playlist Autonomous Ingest ---

@app.post("/api/jobs/batch-playlist")
def batch_playlist_endpoint(req: BatchIngestRequest):
    """Crawls a YouTube playlist or channel and enqueues multiple videos autonomously."""
    if not req.playlist_url:
        raise HTTPException(status_code=400, detail="Playlist URL cannot be empty")

    try:
        validate_ingest_url(req.playlist_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid playlist URL: {str(e)}")

    try:
        res = crawl_and_queue_playlist(
            playlist_url=req.playlist_url,
            account_id=req.account_id or "acc_motivation",
            max_items=req.max_items or 5,
            min_duration_sec=req.min_duration_sec or 60.0,
            max_duration_sec=req.max_duration_sec or 3600.0
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Instagram Insights & Real Engagement Feedback ---

@app.post("/api/insights/sync")
def sync_insights_endpoint(req: InsightsSyncRequest):
    """Syncs real Meta Graph API v19.0+ engagement insights or compliant simulation baseline."""
    res = sync_post_insights(
        publishing_id=req.publishing_id,
        account_id=req.account_id or "acc_motivation",
        post_id=req.post_id
    )
    return res


@app.get("/api/insights/{account_id}")
def get_insights_endpoint(account_id: str):
    """Returns historical engagement analytics across tracked posts for an account."""
    return get_account_historical_performance(account_id=account_id)


# --- AI Sentiment & Emotional Palette Auto-Tagging ---

@app.post("/api/ai/sentiment-palette")
def get_sentiment_palette_endpoint(req: SentimentPaletteRequest):
    """Analyzes lexical sentiment, emotional intensity and domain tone to recommend visual/audio styling."""
    return classify_sentiment_and_palette(
        transcript_text=req.transcript_text,
        niche=req.niche,
        virality_score=req.virality_score
    )


# --- Autonomous Content Deduplication ---

@app.post("/api/content/check-duplicate")
def check_duplicate_endpoint(req: DuplicateCheckRequest):
    """Scans existing rendered shorts in database to detect duplicate or overlapping viral clips."""
    return check_for_duplicate_content(
        transcript_text=req.transcript_text,
        duration_sec=req.duration_sec or 0.0,
        similarity_threshold=req.threshold or 0.75
    )


# --- Adaptive Dynamic Framing & Smooth Camera Panning ---

@app.post("/api/video/dynamic-reframe")
def dynamic_reframe_endpoint(req: DynamicReframeRequest):
    """Renders 9:16 vertical short using adaptive smooth camera panning across widescreen footage."""
    try:
        out_p = reframe_dynamic_short(
            source_video_path=req.video_path,
            start_sec=req.start_sec,
            end_sec=req.end_sec,
            target_width=req.target_width or 1080,
            target_height=req.target_height or 1920
        )
        return {"dynamic_video_path": out_p}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Executive Weekly Performance Report ---

@app.get("/api/reports/weekly")
def get_weekly_report_endpoint(account_id: Optional[str] = "all"):
    """Generates a structured weekly executive digest and Markdown report across accounts."""
    return generate_weekly_executive_report(account_id=account_id or "all")


# --- Dynamic Auto-Zoom & Punch Cuts ---

@app.post("/api/video/auto-zoom")
def auto_zoom_endpoint(req: AutoZoomRequest):
    """Applies dynamic 1.16x punch-cut auto-zoom to a 9:16 vertical short to maximize visual retention."""
    try:
        words = None
        if req.job_id:
            job = get_job(req.job_id)
            if job and job.get("transcript_json_path") and os.path.exists(job["transcript_json_path"]):
                with open(job["transcript_json_path"], "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                words = []
                for seg in t_data.get("segments", []):
                    words.extend(seg.get("words", []))

        result = apply_dynamic_auto_zoom(
            input_video_path=req.video_path,
            words=words,
            zoom_scale=req.zoom_scale or 1.16
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Top Hook Header Banner & Attention Grabber ---

@app.post("/api/video/hook-banner")
def hook_banner_endpoint(req: HookBannerRequest):
    """Applies high-impact top hook header banner onto a 9:16 video short."""
    try:
        result = apply_standalone_hook_banner(
            video_path=req.video_path,
            hook_text=req.hook_text,
            theme=req.theme or "hormozi_yellow",
            duration_sec=req.duration_sec or 3.5
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# --- AI CLIFFHANGER SERIES ENGINE REST ENDPOINTS ---
# =====================================================================

series_engine_instance = CliffhangerSeriesEngine()


def _resolve_transcript_data(job_id: Optional[str] = None, transcript_path: Optional[str] = None) -> Dict[str, Any]:
    """Helper to locate and parse transcript JSON for series generation."""
    target_path = None
    if transcript_path and os.path.exists(transcript_path):
        target_path = transcript_path
    elif job_id:
        job = get_job(job_id)
        if job and job.get("transcript_json_path") and os.path.exists(job["transcript_json_path"]):
            target_path = job["transcript_json_path"]
        elif os.path.exists(f"temp/{job_id}_transcript.json"):
            target_path = f"temp/{job_id}_transcript.json"

    if not target_path or not os.path.exists(target_path):
        # Fallback to any recent transcript in temp
        candidates = sorted(Path("temp").glob("*_transcript.json"), key=os.path.getmtime, reverse=True)
        if candidates:
            target_path = str(candidates[0])
        else:
            raise HTTPException(status_code=404, detail="No transcript JSON found. Please transcribe the video first.")

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript: {e}")


@app.post("/api/series/analyze-arcs")
def series_analyze_arcs_endpoint(req: SeriesAnalyzeArcsRequest):
    """
    Analyzes full speech transcript to discover candidate story arcs,
    dynamic episode sizing, narrative progression, and turning points.
    """
    t_data = _resolve_transcript_data(req.job_id, req.transcript_path)
    arcs = series_engine_instance.discover_story_arcs(t_data)
    return {
        "job_id": req.job_id,
        "total_source_duration": t_data.get("duration", 0.0),
        "arcs_found": len(arcs),
        "story_arcs": [arc.model_dump() for arc in arcs]
    }


@app.post("/api/series/generate")
def series_generate_endpoint(req: SeriesGenerateRequest):
    """
    Generates a full, sequence-coherent episodic cliffhanger series.
    Supports AUTO, GUIDED, and CUSTOM generation modes.
    """
    if is_emergency_stopped():
        raise HTTPException(status_code=423, detail="Emergency stop is active. Series generation blocked.")

    t_data = _resolve_transcript_data(req.job_id, req.transcript_path)

    # Reconstruct selected story arc if provided
    selected_arc = None
    if req.story_arc:
        try:
            selected_arc = StoryArc(**req.story_arc)
        except Exception:
            pass

    time_range = None
    if req.custom_start_sec is not None and req.custom_end_sec is not None:
        time_range = (req.custom_start_sec, req.custom_end_sec)

    try:
        series_plan = series_engine_instance.generate_series(
            transcript_data=t_data,
            selected_arc=selected_arc,
            account_id=req.account_id or "acc_motivation",
            job_id=req.job_id,
            desired_episodes=req.episode_count,
            custom_time_range=time_range,
            generation_mode=req.generation_mode or "auto"
        )

        # Persist generated series in SQLite
        plan_dict = series_plan.model_dump()
        series_id = create_series(plan_dict)
        full_series = get_series(series_id)
        return full_series
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Series generation failed: {e}")


@app.get("/api/series")
def list_series_endpoint(
    account_id: Optional[str] = None,
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """Lists all generated multi-part series with account branding and render statistics."""
    series_list = list_series(account_id=account_id, job_id=job_id, status=status, limit=limit)
    for s in series_list:
        s["episodes"] = list_series_episodes(s["id"])
    return {
        "series": series_list,
        "total": len(series_list)
    }


@app.get("/api/series/{series_id}")
def get_series_endpoint(series_id: str):
    """Retrieves complete series details, narrative timeline, and ordered episodes."""
    s = get_series(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    return s


@app.post("/api/series/{series_id}/update")
def update_series_endpoint(series_id: str, req: Request):
    """Updates high-level series attributes."""
    s = get_series(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    data = req.scope.get("json_data") or {}
    success = update_series(series_id, data)
    return {"success": success, "series": get_series(series_id)}


@app.delete("/api/series/{series_id}")
def delete_series_endpoint(series_id: str):
    """Deletes series and cascades removal to all episodes."""
    success = delete_series(series_id)
    if not success:
        raise HTTPException(status_code=404, detail="Series not found")
    return {"success": True, "series_id": series_id}


@app.get("/api/series/{series_id}/episodes/{episode_id}")
def get_series_episode_endpoint(series_id: str, episode_id: int):
    """Retrieves full details for a single episode."""
    ep = get_series_episode(episode_id)
    if not ep or ep.get("series_id") != series_id:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep


@app.post("/api/series/{series_id}/episodes/{episode_id}/update")
def update_series_episode_endpoint(series_id: str, episode_id: int, req: EpisodeUpdateRequest):
    """Allows manual editing of episode titles, hooks, cliffhangers, and timestamps."""
    ep = get_series_episode(episode_id)
    if not ep or ep.get("series_id") != series_id:
        raise HTTPException(status_code=404, detail="Episode not found")

    update_dict = {}
    if req.title is not None:
        update_dict["title"] = req.title
    if req.opening_hook is not None:
        update_dict["opening_hook"] = req.opening_hook
    if req.cliffhanger_text is not None:
        update_dict["cliffhanger_text"] = req.cliffhanger_text
    if req.next_teaser is not None:
        update_dict["next_teaser"] = req.next_teaser
    if req.start_time is not None:
        update_dict["start_time"] = req.start_time
    if req.end_time is not None:
        update_dict["end_time"] = req.end_time

    success = update_series_episode(episode_id, update_dict)
    return {"success": success, "episode": get_series_episode(episode_id)}


@app.post("/api/series/{series_id}/episodes/{episode_id}/regenerate-hook")
def regenerate_episode_hook_endpoint(series_id: str, episode_id: int):
    """Regenerates a high-retention opening hook for an individual episode."""
    ep = get_series_episode(episode_id)
    if not ep or ep.get("series_id") != series_id:
        raise HTTPException(status_code=404, detail="Episode not found")

    series = get_series(series_id)
    ep_words = ep.get("word_boundaries") or []
    if not ep_words:
        try:
            t_data = _resolve_transcript_data(series.get("job_id") if series else None)
            all_words = extract_all_words(t_data)
            start_t = float(ep.get("start_time", 0.0))
            end_t = float(ep.get("end_time", start_t + 30.0))
            ep_words = [w for w in all_words if w.get("end", 0) >= start_t and w.get("start", 0) <= end_t]
        except Exception:
            ep_words = []

    if ep_words:
        text_sample = " ".join([w.get("word", "") for w in ep_words[:12]])
    else:
        text_sample = (ep.get("main_content") or "Watch this moment carefully")[:60]

    new_hook = f"Part {ep.get('episode_number', 1)}: \"{text_sample}\" — Watch this carefully."
    update_series_episode(episode_id, {"opening_hook": new_hook})
    return {"success": True, "episode_id": episode_id, "opening_hook": new_hook}


@app.post("/api/series/{series_id}/episodes/{episode_id}/regenerate-cliffhanger")
def regenerate_episode_cliffhanger_endpoint(series_id: str, episode_id: int):
    """Re-evaluates the episode ending using the 7-paradigm Cliffhanger Intelligence Engine."""
    ep = get_series_episode(episode_id)
    if not ep or ep.get("series_id") != series_id:
        raise HTTPException(status_code=404, detail="Episode not found")

    series = get_series(series_id)
    ep_words = ep.get("word_boundaries") or []
    if not ep_words:
        try:
            t_data = _resolve_transcript_data(series.get("job_id") if series else None)
            all_words = extract_all_words(t_data)
            start_t = float(ep.get("start_time", 0.0))
            end_t = float(ep.get("end_time", start_t + 30.0))
            ep_words = [w for w in all_words if w.get("end", 0) >= start_t and w.get("start", 0) <= end_t]
        except Exception:
            ep_words = []

    is_final = bool(ep.get("is_final_episode", False))
    ep_text = " ".join([w.get("word", "") for w in ep_words]) if ep_words else (ep.get("main_content") or "")

    eval_result = series_engine_instance.cliffhanger_engine.analyze_ending_window(
        window_words=ep_words,
        full_text=ep_text,
        is_series_final=is_final
    )

    update_series_episode(episode_id, {
        "cliffhanger_text": eval_result.cliffhanger_text,
        "cliffhanger_type": eval_result.cliffhanger_type,
        "cliffhanger_score": eval_result.cliffhanger_score,
        "next_teaser": eval_result.next_teaser
    })

    return {
        "success": True,
        "episode_id": episode_id,
        "cliffhanger_text": eval_result.cliffhanger_text,
        "cliffhanger_type": eval_result.cliffhanger_type,
        "cliffhanger_score": eval_result.cliffhanger_score,
        "next_teaser": eval_result.next_teaser
    }


@app.post("/api/series/{series_id}/episodes/{episode_id}/regenerate")
def regenerate_episode_endpoint(series_id: str, episode_id: int):
    """Completely recalculates hook, cliffhanger, teasers, and quality scores for an episode."""
    ep = get_series_episode(episode_id)
    if not ep or ep.get("series_id") != series_id:
        raise HTTPException(status_code=404, detail="Episode not found")

    series = get_series(series_id)
    t_data = _resolve_transcript_data(series.get("job_id") if series else None)

    updated_ep = series_engine_instance.regenerate_single_episode(
        series_plan_dict=series,
        episode_number=ep["episode_number"],
        transcript_data=t_data
    )

    update_series_episode(episode_id, {
        "opening_hook": updated_ep.get("opening_hook"),
        "cliffhanger_text": updated_ep.get("cliffhanger_text"),
        "cliffhanger_type": updated_ep.get("cliffhanger_type"),
        "cliffhanger_score": updated_ep.get("cliffhanger_score"),
        "next_teaser": updated_ep.get("next_teaser"),
        "quality_score": updated_ep.get("quality_score"),
        "quality_breakdown": updated_ep.get("quality_breakdown")
    })

    return {"success": True, "episode": get_series_episode(episode_id)}


@app.post("/api/series/{series_id}/episodes/merge")
def merge_episodes_endpoint(series_id: str, req: EpisodeMergeRequest):
    """Merges two consecutive episodes into a single longer narrative part."""
    merged_id = merge_series_episodes(series_id, req.ep1_id, req.ep2_id)
    if not merged_id:
        raise HTTPException(status_code=400, detail="Failed to merge episodes. Verify both belong to this series.")
    return {"success": True, "merged_episode_id": merged_id, "series": get_series(series_id)}


@app.post("/api/series/{series_id}/episodes/{episode_id}/split")
def split_episode_endpoint(series_id: str, episode_id: int, req: EpisodeSplitRequest):
    """Splits an episode into two parts at a specified timestamp."""
    result = split_series_episode(
        series_id=series_id,
        episode_id=episode_id,
        split_time=req.split_time,
        ep1_cliffhanger=req.ep1_cliffhanger or "",
        ep2_hook=req.ep2_hook or ""
    )
    if not result:
        raise HTTPException(status_code=400, detail="Failed to split episode. Timestamp must be strictly inside the episode duration.")
    return {"success": True, "ep1_id": result[0], "ep2_id": result[1], "series": get_series(series_id)}


@app.post("/api/series/{series_id}/episodes/reorder")
def reorder_episodes_endpoint(series_id: str, req: EpisodeReorderRequest):
    """Reorders episodes according to custom sequence."""
    success = reorder_series_episodes(series_id, req.episode_ids)
    return {"success": success, "series": get_series(series_id)}


@app.delete("/api/series/{series_id}/episodes/{episode_id}")
def delete_episode_endpoint(series_id: str, episode_id: int):
    """Deletes an episode and renumbers remaining episodes."""
    success = delete_series_episode(episode_id)
    if not success:
        raise HTTPException(status_code=404, detail="Episode not found")
    return {"success": True, "series": get_series(series_id)}


@app.post("/api/series/{series_id}/render-episode/{episode_id}")
def render_series_episode_endpoint(
    series_id: str,
    episode_id: int,
    req: SeriesRenderEpisodeRequest,
    bg_tasks: BackgroundTasks
):
    """
    Renders an individual series episode into a 9:16 vertical short
    with MediaPipe face tracking, dynamic karaoke subtitles, and episodic [EP X/N] banners.
    """
    if is_emergency_stopped():
        raise HTTPException(status_code=423, detail="Emergency stop is active. Rendering blocked.")

    ep = get_series_episode(episode_id)
    if not ep or ep.get("series_id") != series_id:
        raise HTTPException(status_code=404, detail="Episode not found")

    def run_render():
        try:
            render_series_episode_job(
                series_id=series_id,
                episode_id=episode_id,
                crop_mode=req.crop_mode or "smart_face",
                theme=req.theme or "hormozi_yellow",
                enable_ducking=req.enable_ducking,
                enable_jumpcuts=req.enable_jumpcuts,
                enable_sfx=req.enable_sfx,
                enable_auto_zoom=req.enable_auto_zoom
            )
        except Exception as e:
            print(f"[!] Background episode render error: {e}")

    update_episode_render_result(episode_id, render_status="rendering")
    bg_tasks.add_task(run_render)

    return {
        "status": "rendering",
        "series_id": series_id,
        "episode_id": episode_id,
        "message": f"Rendering Episode #{ep.get('episode_number', 1)} in background."
    }


@app.post("/api/series/{series_id}/batch-render")
def batch_render_series_endpoint(
    series_id: str,
    req: SeriesBatchRenderRequest,
    bg_tasks: BackgroundTasks
):
    """
    Batch renders all episodes in the series sequentially in the background.
    """
    if is_emergency_stopped():
        raise HTTPException(status_code=423, detail="Emergency stop is active. Rendering blocked.")

    s = get_series(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")

    def run_batch():
        try:
            batch_render_series_job(
                series_id=series_id,
                crop_mode=req.crop_mode or "smart_face",
                theme=req.theme or "hormozi_yellow"
            )
        except Exception as e:
            print(f"[!] Background batch render error: {e}")

    update_series(series_id, {"status": "rendering"})
    bg_tasks.add_task(run_batch)

    return {
        "status": "rendering",
        "series_id": series_id,
        "message": f"Batch rendering all {s.get('episode_count', 0)} episodes in background."
    }


@app.get("/api/series/{series_id}/export")
def export_series_endpoint(series_id: str):
    """
    Exports series metadata, episode timeline, cliffhangers, and media paths as a structured package.
    """
    s = get_series(series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")

    export_payload = {
        "export_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "series_id": s["id"],
        "series_title": s["title"],
        "description": s["description"],
        "main_topic": s["main_topic"],
        "episode_count": s["episode_count"],
        "quality_score": s["quality_score"],
        "generation_mode": s.get("generation_mode", "auto"),
        "story_arc": s.get("story_arc"),
        "series_memory": s.get("series_memory"),
        "episodes": []
    }

    for ep in s.get("episodes", []):
        export_payload["episodes"].append({
            "episode_number": ep["episode_number"],
            "title": ep["title"],
            "opening_hook": ep.get("opening_hook"),
            "context_premise": ep.get("context_premise"),
            "payoff": ep.get("payoff_text"),
            "cliffhanger_text": ep.get("cliffhanger_text"),
            "cliffhanger_type": ep.get("cliffhanger_type"),
            "cliffhanger_score": ep.get("cliffhanger_score"),
            "next_teaser": ep.get("next_teaser"),
            "start_time": ep["start_time"],
            "end_time": ep["end_time"],
            "duration": ep["duration"],
            "is_final_episode": bool(ep.get("is_final_episode", False)),
            "quality_score": ep.get("quality_score"),
            "render_status": ep.get("render_status"),
            "video_path": ep.get("rendered_video_path")
        })

    return export_payload


# =====================================================================
# --- AI METADATA & SEO GENERATOR ENDPOINTS ---
# =====================================================================

def _resolve_target_context(target_type: str, target_id: Any) -> Dict[str, Any]:
    """Resolves video path, title, text, duration, and account context for any target."""
    target_id_str = str(target_id)
    video_path = ""
    title = f"{target_type.capitalize()} #{target_id}"
    text = ""
    duration = 45.0
    account_id = "acc_motivation"
    job_id = None
    series_info = None
    words = None

    if target_type == "short":
        renders = list_rendered_shorts(limit=300)
        target_render = next((r for r in renders if str(r.get("id")) == target_id_str), None)
        if target_render:
            video_path = target_render.get("video_path", "")
            title = target_render.get("title") or title
            job_id = target_render.get("job_id")
            duration = float(target_render.get("duration") or 45.0)
            account_id = target_render.get("account_id") or "acc_motivation"
            text = target_render.get("caption") or title

            if job_id:
                job = get_job(job_id)
                if job:
                    account_id = job.get("account_id") or account_id
                    clips = job.get("clips", [])
                    cid = target_render.get("clip_id")
                    t_clip = next((c for c in clips if c.get("clip_id") == cid or c.get("id") == cid), None)
                    if t_clip:
                        text = t_clip.get("full_quote") or t_clip.get("hook_text") or text

    elif target_type == "episode":
        try:
            ep_id = int(target_id)
            ep = get_series_episode(ep_id)
            if ep:
                series_id = ep.get("series_id")
                series = get_series(series_id) if series_id else None
                video_path = ep.get("rendered_video_path", "")
                ep_num = ep.get("episode_number", 1)
                series_title = series.get("title", "Series") if series else "Series"
                title = f"{series_title} - Part {ep_num}"
                text = ep.get("main_content") or ep.get("opening_hook") or ep.get("payoff_text") or title
                duration = float(ep.get("duration") or 45.0)
                job_id = series.get("job_id") if series else None
                account_id = series.get("account_id") if series else "acc_motivation"
                series_info = {
                    "series_id": series_id,
                    "series_title": series_title,
                    "episode_number": ep_num,
                    "total_episodes": series.get("episode_count") if series else 3,
                    "is_final_episode": bool(ep.get("is_final_episode", False)),
                    "next_teaser": ep.get("next_teaser", "")
                }
                # Fallback to source video if rendered video not yet produced
                if (not video_path or not os.path.exists(video_path)) and job_id:
                    job = get_job(job_id)
                    if job and job.get("source_path") and os.path.exists(job.get("source_path")):
                        video_path = job["source_path"]
        except Exception as ex:
            print(f"[!] Target resolution error for episode #{target_id}: {ex}")

    elif target_type == "long_form":
        job = get_job(target_id_str)
        if job:
            video_path = job.get("source_path", "")
            title = job.get("title") or "Long-form Video"
            duration = float(job.get("duration") or 120.0)
            account_id = job.get("account_id") or "acc_motivation"
            job_id = target_id_str
            t_data = _resolve_transcript_data(job_id)
            if t_data and "text" in t_data:
                text = t_data["text"]
            if t_data and "words" in t_data:
                words = t_data["words"]

    acc = get_account(account_id) or {}
    niche = acc.get("niche", "Motivation")
    handle = acc.get("handle", "@vediohooks")

    return {
        "video_path": video_path,
        "title": title,
        "text": text,
        "duration": duration,
        "account_id": account_id,
        "job_id": job_id,
        "series_info": series_info,
        "niche": niche,
        "handle": handle,
        "words": words
    }


@app.post("/api/metadata/generate")
def generate_metadata_endpoint(req: MetadataGenerateRequest):
    """Generates platform-specific SEO metadata for a short, episode, or long-form video."""
    ctx = _resolve_target_context(req.target_type, req.target_id)
    niche = req.niche or ctx["niche"]
    title = req.custom_title or ctx["title"]

    meta_res = generate_video_metadata(
        target_type=req.target_type,
        target_id=req.target_id,
        title=title,
        text=ctx["text"],
        niche=niche,
        job_id=ctx["job_id"],
        series_info=ctx["series_info"],
        duration=ctx["duration"],
        words=ctx["words"],
        handle=ctx["handle"]
    )

    save_video_metadata(
        target_type=req.target_type,
        target_id=req.target_id,
        title=title,
        niche=niche,
        youtube_data=meta_res.youtube.model_dump(),
        instagram_data=meta_res.instagram.model_dump(),
        tiktok_data=meta_res.tiktok.model_dump(),
        title_variations=meta_res.title_variations.model_dump(),
        quality_score=meta_res.quality.overall_score,
        quality_breakdown=meta_res.quality.model_dump(),
        job_id=ctx["job_id"],
        account_id=ctx["account_id"]
    )

    return {"success": True, "metadata": get_video_metadata(req.target_type, req.target_id)}


@app.get("/api/metadata/{target_type}/{target_id}")
def get_metadata_endpoint(target_type: str, target_id: str):
    """Retrieves metadata from SQLite or generates on-the-fly if not found."""
    meta = get_video_metadata(target_type, target_id)
    if not meta:
        ctx = _resolve_target_context(target_type, target_id)
        meta_res = generate_video_metadata(
            target_type=target_type,
            target_id=target_id,
            title=ctx["title"],
            text=ctx["text"],
            niche=ctx["niche"],
            job_id=ctx["job_id"],
            series_info=ctx["series_info"],
            duration=ctx["duration"],
            words=ctx["words"],
            handle=ctx["handle"]
        )
        save_video_metadata(
            target_type=target_type,
            target_id=target_id,
            title=ctx["title"],
            niche=ctx["niche"],
            youtube_data=meta_res.youtube.model_dump(),
            instagram_data=meta_res.instagram.model_dump(),
            tiktok_data=meta_res.tiktok.model_dump(),
            title_variations=meta_res.title_variations.model_dump(),
            quality_score=meta_res.quality.overall_score,
            quality_breakdown=meta_res.quality.model_dump(),
            job_id=ctx["job_id"],
            account_id=ctx["account_id"]
        )
        meta = get_video_metadata(target_type, target_id)

    return {"success": True, "metadata": meta}


@app.post("/api/metadata/{target_type}/{target_id}/save")
def save_metadata_endpoint(target_type: str, target_id: str, req: MetadataSaveRequest):
    """Saves user-modified metadata fields persistently to SQLite."""
    meta_id = save_video_metadata(
        target_type=target_type,
        target_id=target_id,
        title=req.title,
        niche=req.niche,
        youtube_data=req.youtube,
        instagram_data=req.instagram,
        tiktok_data=req.tiktok,
        title_variations=req.title_variations,
        quality_score=req.quality_score or 85,
        account_id=req.account_id or "acc_motivation",
        status="approved"
    )
    return {"success": True, "metadata_id": meta_id, "metadata": get_video_metadata(target_type, target_id)}


@app.post("/api/metadata/{target_type}/{target_id}/regenerate-field")
def regenerate_metadata_field_endpoint(target_type: str, target_id: str, req: MetadataRegenerateFieldRequest):
    """Regenerates a specific metadata field (title, description, caption, hashtags)."""
    ctx = _resolve_target_context(target_type, target_id)
    meta = get_video_metadata(target_type, target_id)
    curr_title = meta.get("title") if meta else ctx["title"]
    niche = meta.get("niche") if meta else ctx["niche"]

    if req.field_name == "title":
        t_vars = build_title_variations(curr_title, niche, [], ctx["series_info"])
        var_type = req.variation_type or "curiosity_driven"
        val = getattr(t_vars, var_type, curr_title)
        update_video_metadata_field(target_type, target_id, "youtube", "title", val)
    elif req.field_name == "caption" and req.platform == "instagram":
        ig = generate_instagram_metadata(curr_title, ctx["text"], niche, ctx["series_info"], ctx["handle"])
        val = ig.caption
        update_video_metadata_field(target_type, target_id, "instagram", "caption", val)
    elif req.field_name == "hashtags" and req.platform == "instagram":
        ig = generate_instagram_metadata(curr_title, ctx["text"], niche, ctx["series_info"], ctx["handle"])
        val = ig.hashtags
        update_video_metadata_field(target_type, target_id, "instagram", "hashtags", val)
    elif req.field_name == "description" and req.platform == "youtube":
        yt = generate_youtube_metadata(curr_title, ctx["text"], niche, target_type in ("short", "episode"), ctx["series_info"], ctx["duration"], ctx["words"])
        val = yt.description
        update_video_metadata_field(target_type, target_id, "youtube", "description", val)
    elif req.field_name == "caption" and req.platform == "tiktok":
        tt = generate_tiktok_metadata(curr_title, ctx["text"], niche, ctx["series_info"])
        val = tt.caption
        update_video_metadata_field(target_type, target_id, "tiktok", "caption", val)
    else:
        val = curr_title

    return {"success": True, "field_name": req.field_name, "value": val, "metadata": get_video_metadata(target_type, target_id)}


@app.post("/api/metadata/batch-generate")
def batch_generate_metadata_endpoint(req: MetadataBatchRequest):
    """Batch generates metadata for multiple shorts or episodes."""
    results = []
    for item in req.items:
        t_type = item.get("target_type", "short")
        t_id = item.get("target_id")
        niche = item.get("niche", "Motivation")
        ctx = _resolve_target_context(t_type, t_id)
        meta_res = generate_video_metadata(
            target_type=t_type,
            target_id=t_id,
            title=item.get("title") or ctx["title"],
            text=ctx["text"],
            niche=niche,
            job_id=ctx["job_id"],
            series_info=ctx["series_info"],
            duration=ctx["duration"],
            words=ctx["words"],
            handle=ctx["handle"]
        )
        save_video_metadata(
            target_type=t_type,
            target_id=t_id,
            title=meta_res.title,
            niche=niche,
            youtube_data=meta_res.youtube.model_dump(),
            instagram_data=meta_res.instagram.model_dump(),
            tiktok_data=meta_res.tiktok.model_dump(),
            title_variations=meta_res.title_variations.model_dump(),
            quality_score=meta_res.quality.overall_score,
            quality_breakdown=meta_res.quality.model_dump(),
            job_id=ctx["job_id"],
            account_id=ctx["account_id"]
        )
        results.append({"target_type": t_type, "target_id": t_id, "status": "generated"})
    return {"success": True, "processed": len(results), "results": results}


# =====================================================================
# --- AI THUMBNAIL & COVER STUDIO ENDPOINTS ---
# =====================================================================

@app.post("/api/thumbnails/generate")
def generate_thumbnails_endpoint(req: ThumbnailGenerateRequest):
    """Generates 3 high-CTR thumbnail variations with face detection and safe zone calculation."""
    if req.video_path and os.path.exists(req.video_path):
        from src.thumbnail_engine import generate_cover_thumbnails
        covers = generate_cover_thumbnails(
            video_path=req.video_path,
            title=req.title or "VIRAL SHORT",
            niche=req.niche or "Motivation",
            time_sec=req.time_sec or 1.0
        )
        return {"covers": covers, "variations": covers, "success": True}

    target_type = req.target_type or "short"
    ctx = _resolve_target_context(target_type, req.target_id)
    video_path = ctx["video_path"]

    if not video_path or not os.path.exists(video_path):
        # Look for candidate video in output or temp
        candidates = list(Path("output").glob("*.mp4")) + list(Path("temp").glob("*.mp4"))
        if candidates:
            video_path = str(candidates[0])
        else:
            raise HTTPException(status_code=404, detail="No video file found to extract thumbnail frames.")

    niche = req.niche or ctx["niche"]
    aspect_ratio = req.aspect_ratio or "9:16"
    style_mode = req.style_mode or "auto"

    result = generate_thumbnail_suite(
        video_path=video_path,
        target_type=target_type,
        target_id=req.target_id,
        title=ctx["title"],
        niche=niche,
        start_sec=0.0,
        end_sec=max(1.0, ctx["duration"]),
        aspect_ratio=aspect_ratio,
        style_mode=style_mode,
        brand_handle=req.brand_handle or ctx["handle"],
        custom_headline=req.custom_headline
    )

    saved_assets = []
    for idx, var in enumerate(result.variations):
        asset_id = save_thumbnail_asset(
            target_type=target_type,
            target_id=req.target_id,
            image_path=var.image_path,
            headline=var.headline,
            variation_type=var.variation_type,
            aspect_ratio=var.aspect_ratio,
            style_mode=var.style_mode,
            source_timestamp=var.source_timestamp,
            is_selected=1 if idx == 0 else 0,
            job_id=ctx["job_id"],
            account_id=ctx["account_id"]
        )
        saved_assets.append({
            "id": asset_id,
            "variation_type": var.variation_type,
            "headline": var.headline,
            "image_path": var.image_path,
            "is_selected": (idx == 0)
        })

    return {
        "success": True,
        "covers": saved_assets,
        "aspect_ratio": aspect_ratio,
        "style_mode": style_mode,
        "selected_frame": result.selected_frame.model_dump(),
        "candidates_count": len(result.all_candidates),
        "variations": saved_assets,
        "grid_crop_preview_path": result.grid_crop_preview_path
    }


@app.get("/api/thumbnails/{target_type}/{target_id}")
def list_thumbnails_endpoint(target_type: str, target_id: str):
    """Retrieves all generated thumbnail variations for a target."""
    assets = list_thumbnail_assets(target_type=target_type, target_id=target_id, limit=50)
    return {"success": True, "thumbnails": assets}


@app.post("/api/thumbnails/{asset_id}/select")
def select_thumbnail_endpoint(asset_id: int, req: ThumbnailSelectRequest):
    """Marks a specific thumbnail variation as the active cover."""
    success = select_thumbnail_asset(asset_id, req.target_type, req.target_id)
    if not success:
        raise HTTPException(status_code=404, detail="Thumbnail asset not found")
    return {"success": True, "selected_asset_id": asset_id}


@app.get("/api/thumbnails/{asset_id}/image")
def stream_thumbnail_image_endpoint(asset_id: int):
    """Streams a high-resolution JPG thumbnail image file."""
    asset = get_thumbnail_asset(asset_id)
    if not asset or not asset.get("image_path"):
        raise HTTPException(status_code=404, detail="Thumbnail asset not found")
    p = Path(asset["image_path"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail image file missing from disk")
    return FileResponse(str(p), media_type="image/jpeg")


@app.post("/api/thumbnails/extract-frames")
def extract_frames_endpoint(req: ThumbnailExtractFramesRequest):
    """Extracts candidate video frames with face detection & sharpness scoring for interactive scrubbing."""
    ctx = _resolve_target_context(req.target_type, req.target_id)
    video_path = ctx["video_path"]
    if not video_path or not os.path.exists(video_path):
        candidates = list(Path("output").glob("*.mp4")) + list(Path("temp").glob("*.mp4"))
        if candidates:
            video_path = str(candidates[0])
        else:
            raise HTTPException(status_code=404, detail="No video file found to extract frames.")

    candidates = extract_candidate_frames(
        video_path=video_path,
        start_sec=0.0,
        end_sec=max(1.0, ctx["duration"])
    )
    return {"success": True, "candidates": [c.model_dump() for c in candidates]}


@app.post("/api/thumbnails/batch-generate")
def batch_generate_thumbnails_endpoint(req: BatchThumbnailsRequest):
    """Batch generates thumbnails for multiple videos or episodes."""
    results = []
    for item in req.items:
        t_type = item.get("target_type", "short")
        t_id = item.get("target_id")
        ctx = _resolve_target_context(t_type, t_id)
        v_path = ctx["video_path"]
        if v_path and os.path.exists(v_path):
            suite = generate_thumbnail_suite(
                video_path=v_path,
                target_type=t_type,
                target_id=t_id,
                title=ctx["title"],
                niche=ctx["niche"],
                start_sec=0.0,
                end_sec=max(1.0, ctx["duration"]),
                aspect_ratio="9:16",
                style_mode="auto"
            )
            for idx, var in enumerate(suite.variations):
                save_thumbnail_asset(
                    target_type=t_type,
                    target_id=t_id,
                    image_path=var.image_path,
                    headline=var.headline,
                    variation_type=var.variation_type,
                    aspect_ratio=var.aspect_ratio,
                    style_mode=var.style_mode,
                    source_timestamp=var.source_timestamp,
                    is_selected=1 if idx == 0 else 0,
                    job_id=ctx["job_id"],
                    account_id=ctx["account_id"]
                )
            results.append({"target_type": t_type, "target_id": t_id, "status": "generated"})
        else:
            results.append({"target_type": t_type, "target_id": t_id, "status": "skipped_no_video"})
    return {"success": True, "processed": len(results), "results": results}


# =====================================================================
# --- PUBLISHING READINESS & PACKAGE EXPORT ENDPOINTS ---
# =====================================================================

@app.get("/api/publishing/readiness/{target_type}/{target_id}")
def check_publishing_readiness_endpoint(target_type: str, target_id: str, platform: str = "instagram"):
    """Evaluates 8 pre-flight criteria and returns a 0-100% readiness score with actionable checklist."""
    ctx = _resolve_target_context(target_type, target_id)
    meta = get_video_metadata(target_type, target_id)
    thumbs = list_thumbnail_assets(target_type=target_type, target_id=target_id, limit=5)
    selected_thumb = next((t["image_path"] for t in thumbs if t.get("is_selected")), (thumbs[0]["image_path"] if thumbs else None))

    report = validate_publishing_readiness(
        target_type=target_type,
        target_id=target_id,
        video_path=ctx["video_path"],
        metadata=meta,
        thumbnail_path=selected_thumb,
        platform=platform,
        series_info=ctx["series_info"]
    )
    return {"success": True, "report": report.model_dump()}


@app.get("/api/publishing/export-package/{target_type}/{target_id}")
def export_publishing_package_endpoint(target_type: str, target_id: str):
    """Creates and downloads a complete publishing ZIP bundle (video, covers, JSON, platform captions)."""
    ctx = _resolve_target_context(target_type, target_id)
    meta = get_video_metadata(target_type, target_id) or {}
    thumbs = list_thumbnail_assets(target_type=target_type, target_id=target_id, limit=5)
    selected_thumb = next((t["image_path"] for t in thumbs if t.get("is_selected")), (thumbs[0]["image_path"] if thumbs else None))

    zip_path = export_publishing_bundle(
        target_type=target_type,
        target_id=target_id,
        video_path=ctx["video_path"],
        metadata=meta,
        thumbnail_path=selected_thumb
    )

    if not os.path.exists(zip_path):
        raise HTTPException(status_code=500, detail="Failed to construct publishing ZIP package")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=Path(zip_path).name
    )




# --- Premium Commercial SaaS Dashboard UI (Single-Page App) ---

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Create, review, and publish polished short-form videos with VedioHooks AI's video production and multi-account content studio.">
  <meta name="theme-color" content="#0d1117">
  <title>VedioHooks AI | Short-form Video Studio</title>
  <style>
    :root {
      --bg: #0b1014;
      --bg-surface: #10171c;
      --bg-card: #121b21;
      --bg-card-hover: #18232a;
      --border: rgba(203, 221, 226, 0.1);
      --border-focus: rgba(163, 230, 53, 0.55);
      --primary: #a3e635;
      --primary-hover: #bef264;
      --primary-glow: rgba(163, 230, 53, 0.16);
      --emerald: #34d399;
      --amber: #fbbf24;
      --rose: #fb7185;
      --cyan: #67e8f9;
      --text: #f2f6f5;
      --text-muted: #a1b1b5;
      --text-dim: #75878d;
      --sidebar-w: 248px;
      --header-h: 72px;
      --radius-sm: 10px;
      --radius-md: 16px;
      --radius-lg: 22px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    html { color-scheme: dark; scroll-behavior: smooth; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; display: flex; line-height: 1.5; }

    /* Ambient Background Mesh */
    .bg-mesh {
      position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -1; pointer-events: none;
      background: radial-gradient(circle at 10% 0%, rgba(163, 230, 53, 0.055) 0%, transparent 36%),
                  radial-gradient(circle at 94% 80%, rgba(34, 211, 238, 0.035) 0%, transparent 34%);
    }

    /* Fixed Left Sidebar */
    aside.sidebar {
      width: var(--sidebar-w); height: 100vh; position: fixed; top: 0; left: 0; z-index: 50;
      background: rgba(13, 19, 23, 0.96); border-right: 1px solid var(--border); display: flex; flex-direction: column;
      backdrop-filter: blur(20px);
    }
    .sidebar-brand {
      height: var(--header-h); padding: 0 1.25rem; display: flex; align-items: center; gap: 0.75rem;
      border-bottom: 1px solid var(--border); text-decoration: none; color: inherit;
    }
    .sidebar-brand-icon {
      width: 38px; height: 38px; border-radius: 12px; background: linear-gradient(135deg, #a3e635, #34d399);
      display: flex; align-items: center; justify-content: center; font-size: 1.25rem;
      box-shadow: 0 5px 20px rgba(163, 230, 53, 0.18); flex-shrink: 0;
    }
    .sidebar-brand-title { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.4px; line-height: 1.15; }
    .sidebar-brand-title span { color: var(--primary); }
    .sidebar-brand-sub { font-size: 0.68rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.08em; }

    .sidebar-nav { flex: 1; overflow-y: auto; padding: 1rem 0.75rem; display: flex; flex-direction: column; gap: 0.25rem; }
    .nav-group-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-dim); padding: 0.75rem 0.6rem 0.25rem; font-weight: 700; }
    .nav-item {
      display: flex; align-items: center; gap: 0.75rem; padding: 0.65rem 0.85rem; border-radius: var(--radius-sm);
      color: var(--text-muted); font-size: 0.88rem; font-weight: 600; cursor: pointer; transition: all 0.15s;
      border: 1px solid transparent; user-select: none;
    }
    .nav-item:hover { color: #fff; background: rgba(255, 255, 255, 0.04); }
    .nav-item.active { color: #fff; background: rgba(163, 230, 53, 0.1); border-color: rgba(163, 230, 53, 0.22); }
    .nav-item svg { width: 18px; height: 18px; opacity: 0.75; flex-shrink: 0; }
    .nav-item.active svg { opacity: 1; color: var(--primary); }
    .nav-badge { margin-left: auto; font-size: 0.72rem; padding: 0.1rem 0.45rem; border-radius: 9999px; background: rgba(255,255,255,0.08); color: var(--text-muted); }

    .sidebar-footer { padding: 1rem; border-top: 1px solid var(--border); }
    .system-status-pill {
      display: flex; align-items: center; justify-content: space-between; padding: 0.55rem 0.75rem;
      border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border); font-size: 0.75rem;
    }
    .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--emerald); box-shadow: 0 0 10px var(--emerald); animation: pulse 2s infinite; }
    .pulse-dot.stopped { background: var(--rose); box-shadow: 0 0 10px var(--rose); }

    /* Main Container */
    main.main-content {
      margin-left: var(--sidebar-w); width: calc(100vw - var(--sidebar-w)); min-height: 100vh;
      display: flex; flex-direction: column;
    }

    /* Top Header Bar */
    header.top-header {
      height: var(--header-h); position: sticky; top: 0; z-index: 40;
      background: rgba(11, 16, 20, 0.9); backdrop-filter: blur(18px); border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between; padding: 0 2rem;
    }
    .header-left { display: flex; align-items: center; gap: 1rem; }
    .account-selector {
      display: flex; align-items: center; gap: 0.5rem; background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.45rem 0.85rem;
      font-size: 0.85rem; font-weight: 600; color: #fff; cursor: pointer; outline: none;
    }
    .account-selector:focus { border-color: var(--primary); }

    .header-right { display: flex; align-items: center; gap: 1rem; }
    .btn-emergency {
      display: flex; align-items: center; gap: 0.5rem; padding: 0.45rem 0.95rem; border-radius: var(--radius-sm);
      font-size: 0.82rem; font-weight: 700; cursor: pointer; border: 1px solid rgba(244, 63, 94, 0.3);
      background: rgba(244, 63, 94, 0.12); color: #fb7185; transition: all 0.2s;
    }
    .btn-emergency:hover { background: rgba(244, 63, 94, 0.25); border-color: #f43f5e; color: #fff; }
    .btn-emergency.active { background: #f43f5e; color: #fff; box-shadow: 0 0 16px rgba(244, 63, 94, 0.6); }

    .btn-primary {
      background: var(--primary); color: #142008; border: 1px solid rgba(163, 230, 53, 0.45);
      border-radius: var(--radius-sm); padding: 0.55rem 1.15rem; font-size: 0.85rem; font-weight: 700;
      cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem;
      box-shadow: 0 5px 18px rgba(163, 230, 53, 0.12);
    }
    .btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); box-shadow: 0 8px 22px rgba(163, 230, 53, 0.2); }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

    .btn-secondary {
      background: rgba(255, 255, 255, 0.05); color: #cbd5e1; border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 0.55rem 1rem; font-size: 0.85rem; font-weight: 600;
      cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; gap: 0.45rem;
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.09); color: #fff; }

    .btn-danger {
      background: rgba(244, 63, 94, 0.1); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.25);
      border-radius: var(--radius-sm); padding: 0.5rem 0.85rem; font-size: 0.82rem; font-weight: 600;
      cursor: pointer; transition: all 0.15s;
    }
    .btn-danger:hover { background: #f43f5e; color: #fff; }

    /* Content Area & Tabs */
    .view-container { padding: 2rem; max-width: 1400px; width: 100%; margin: 0 auto; flex: 1; }
    .tab-view { display: none; }
    .tab-view.active { display: block; animation: fadeIn 0.2s ease-out; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }

    /* Cards & Grids */
    .card {
      background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
      padding: 1.5rem; backdrop-filter: blur(16px); margin-bottom: 1.5rem; position: relative; overflow: hidden;
    }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
    .card-title { font-size: 1.1rem; font-weight: 700; letter-spacing: -0.3px; display: flex; align-items: center; gap: 0.5rem; }
    .card-subtitle { font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem; }

    .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.25rem; margin-bottom: 1.75rem; }
    .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem; margin-bottom: 1.75rem; }
    .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.25rem; margin-bottom: 1.75rem; }

    @media (max-width: 1100px) {
      .grid-4 { grid-template-columns: repeat(2, 1fr); }
      .grid-3 { grid-template-columns: 1fr; }
    }
    @media (max-width: 768px) {
      aside.sidebar { display: none; }
      main.main-content { margin-left: 0; width: 100vw; }
      .grid-4, .grid-2 { grid-template-columns: 1fr; }
      .view-container { padding: 1rem; }
    }

    /* KPI Metric Cards */
    .metric-card {
      background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
      padding: 1.25rem 1.4rem; backdrop-filter: blur(12px); display: flex; flex-direction: column; gap: 0.5rem;
    }
    .metric-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }
    .metric-value { font-size: 2rem; font-weight: 800; letter-spacing: -0.5px; line-height: 1; }
    .metric-detail { font-size: 0.78rem; color: var(--text-dim); }

    /* Tables */
    .table-container { width: 100%; overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--border); }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.86rem; }
    th { background: rgba(255, 255, 255, 0.03); color: var(--text-muted); font-weight: 600; padding: 0.85rem 1rem; border-bottom: 1px solid var(--border); }
    td { padding: 0.85rem 1rem; border-bottom: 1px solid rgba(255, 255, 255, 0.04); vertical-align: middle; }
    tr:hover td { background: rgba(255, 255, 255, 0.02); }

    /* Badges */
    .badge {
      display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.75rem; font-weight: 700;
      padding: 0.25rem 0.6rem; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .badge-primary { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.3); }
    .badge-success { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-danger { background: rgba(244, 63, 94, 0.15); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.3); }

    /* Inputs & Forms */
    .form-group { margin-bottom: 1.15rem; }
    .form-label { display: block; font-size: 0.82rem; font-weight: 600; color: #cbd5e1; margin-bottom: 0.4rem; }
    .form-input, .form-select, .form-textarea {
      width: 100%; background: rgba(0, 0, 0, 0.35); border: 1px solid var(--border); border-radius: var(--radius-sm);
      padding: 0.7rem 0.95rem; color: #fff; font-size: 0.88rem; outline: none; transition: border-color 0.15s;
    }
    .form-input:focus, .form-select:focus, .form-textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
    .form-row { display: flex; gap: 1rem; }
    .form-row > * { flex: 1; }

    /* Modals */
    .modal-overlay {
      position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.75);
      backdrop-filter: blur(8px); z-index: 100; display: none; align-items: center; justify-content: center; padding: 1.5rem;
    }
    .modal-overlay.active { display: flex; animation: fadeIn 0.15s ease-out; }
    .modal-box {
      background: #11191e; border: 1px solid var(--border); border-radius: var(--radius-lg);
      width: 100%; max-width: 680px; max-height: 90vh; overflow-y: auto; padding: 2rem; box-shadow: 0 25px 50px rgba(0,0,0,0.6);
    }
    .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
    .modal-close { cursor: pointer; color: var(--text-muted); font-size: 1.25rem; line-height: 1; border: none; background: transparent; }

    /* Video Player & Gallery */
    .shorts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }
    .short-card {
      background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
      overflow: hidden; display: flex; flex-direction: column; transition: transform 0.2s, border-color 0.2s;
    }
    .short-card:hover { transform: translateY(-3px); border-color: rgba(99, 102, 241, 0.4); }
    .short-video-wrapper { position: relative; width: 100%; padding-top: 177.77%; background: #000; overflow: hidden; }
    .short-video-wrapper video { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
    .short-content { padding: 1.15rem; display: flex; flex-direction: column; gap: 0.65rem; flex: 1; }

    /* 14-Point Plan Visual Blueprint */
    .blueprint-card {
      background: rgba(15, 18, 28, 0.95); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: var(--radius-md);
      padding: 1.5rem; margin-bottom: 1.25rem;
    }
    .blueprint-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
    .blueprint-item { background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 0.9rem; }
    .blueprint-key { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: #818cf8; font-weight: 700; margin-bottom: 0.25rem; }
    .blueprint-val { font-size: 0.85rem; color: #e2e8f0; line-height: 1.45; }

    /* Toast */
    #toastContainer { position: fixed; bottom: 24px; right: 24px; z-index: 200; display: flex; flex-direction: column; gap: 8px; }
    .toast {
      background: #1a252b; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.85rem 1.25rem;
      color: #fff; font-size: 0.86rem; box-shadow: 0 10px 30px rgba(0,0,0,0.5); animation: fadeIn 0.2s;
    }

    .skip-link {
      position: fixed; top: 0.75rem; left: 0.75rem; z-index: 300; padding: 0.75rem 1rem;
      transform: translateY(-160%); background: var(--primary); color: #142008; border-radius: var(--radius-sm);
      font-weight: 700;
    }
    .skip-link:focus { transform: translateY(0); }
    .page-heading {
      display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
      padding: 0.55rem 0 1.75rem;
    }
    .page-eyebrow { color: var(--primary); font-size: 0.72rem; font-weight: 750; letter-spacing: 0.13em; text-transform: uppercase; }
    .page-heading h1 { margin-top: 0.3rem; font-size: clamp(1.7rem, 3vw, 2.45rem); line-height: 1.15; letter-spacing: -0.055em; }
    .page-description { margin-top: 0.45rem; color: var(--text-muted); font-size: 0.94rem; max-width: 62ch; }
    .menu-toggle {
      display: none; width: 42px; height: 42px; flex: 0 0 42px; align-items: center; justify-content: center;
      border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-card); color: var(--text);
      cursor: pointer; font-size: 1.2rem;
    }
    .sidebar-backdrop { display: none; }
    .nav-item:focus-visible, button:focus-visible, a:focus-visible, select:focus-visible, input:focus-visible,
    textarea:focus-visible, [tabindex]:focus-visible {
      outline: 2px solid var(--primary); outline-offset: 3px;
    }
    .card, .metric-card, .short-card, .blueprint-card {
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
    }
    .card { border-color: rgba(203, 221, 226, 0.09); }
    .metric-card { border-color: rgba(203, 221, 226, 0.1); transition: border-color 0.18s, transform 0.18s; }
    .metric-card:hover { border-color: rgba(163, 230, 53, 0.25); transform: translateY(-2px); }
    .metric-value { letter-spacing: -0.06em; }
    .card-title { letter-spacing: -0.025em; }
    .table-container { border-color: var(--border); }
    th { white-space: nowrap; }
    .badge-primary { background: rgba(163, 230, 53, 0.1); color: #d9f99d; border-color: rgba(163, 230, 53, 0.24); }
    .short-card:hover { border-color: rgba(163, 230, 53, 0.4); }
    .blueprint-card { background: #111a1f; border-color: rgba(163, 230, 53, 0.22); }
    .blueprint-key { color: #bef264; }
    [style*="#a5b4fc"], [style*="#818cf8"] { color: #bef264 !important; }
    .btn-primary[style*="background"] { background: var(--primary) !important; color: #142008 !important; }
    #factoryHookBannerRow { background: rgba(163, 230, 53, 0.045) !important; border-color: rgba(163, 230, 53, 0.2) !important; }
    select option { background: #111a1f; color: var(--text); }
    .form-input, .form-select, .form-textarea { min-height: 44px; }
    .btn-primary, .btn-secondary, .btn-danger, .btn-emergency { min-height: 42px; }
    .btn-secondary:hover { border-color: rgba(163, 230, 53, 0.24); }
    .short-card:hover { border-color: rgba(163, 230, 53, 0.35); }
    .view-container { max-width: 1520px; padding: 1.75rem clamp(1rem, 2.8vw, 2.5rem) 3rem; }
    .grid-3 { grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); }

    @media (max-width: 1100px) {
      .grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid-3 { grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); }
      .menu-toggle { display: inline-flex; }
      aside.sidebar {
        display: flex; width: min(86vw, 300px); transform: translateX(-105%);
        transition: transform 0.22s ease; z-index: 120;
      }
      body.sidebar-open aside.sidebar { transform: translateX(0); }
      .sidebar-backdrop {
        display: block; position: fixed; inset: 0; z-index: 110; background: rgba(0, 0, 0, 0.58);
        opacity: 0; visibility: hidden; transition: opacity 0.2s, visibility 0.2s;
      }
      body.sidebar-open .sidebar-backdrop { opacity: 1; visibility: visible; }
      main.main-content { margin-left: 0; width: 100%; }
      header.top-header { padding: 0 1.25rem; }
      .header-right { gap: 0.6rem; }
      .account-selector { max-width: 270px; }
      #activeNicheBadge, #hwAccelBadge { display: none !important; }
    }
    @media (max-width: 900px) {
      .menu-toggle { display: inline-flex; }
      aside.sidebar {
        display: flex; width: min(86vw, 300px); transform: translateX(-105%);
        transition: transform 0.22s ease; z-index: 120;
      }
      body.sidebar-open aside.sidebar { transform: translateX(0); }
      .sidebar-backdrop {
        display: block; position: fixed; inset: 0; z-index: 110; background: rgba(0, 0, 0, 0.58);
        opacity: 0; visibility: hidden; transition: opacity 0.2s, visibility 0.2s;
      }
      body.sidebar-open .sidebar-backdrop { opacity: 1; visibility: visible; }
      main.main-content { margin-left: 0; width: 100%; }
      .header-left { min-width: 0; }
      .account-selector { max-width: 290px; }
    }
    @media (max-width: 640px) {
      :root { --header-h: 64px; }
      header.top-header { height: auto; min-height: var(--header-h); padding: 0.65rem 0.85rem; gap: 0.65rem; }
      .header-left { flex: 1; gap: 0.55rem; }
      .account-selector { width: min(47vw, 220px); padding: 0.55rem 0.5rem; font-size: 0.76rem; }
      #activeNicheBadge, #hwAccelBadge { display: none !important; }
      .header-right { gap: 0.45rem; }
      .btn-emergency { min-height: 40px; padding: 0.4rem 0.55rem; font-size: 0.67rem; }
      .header-right > .btn-primary { min-height: 40px; padding: 0.45rem 0.65rem; font-size: 0.76rem; white-space: nowrap; }
      .menu-toggle { width: 38px; height: 40px; flex-basis: 38px; }
      .view-container { padding: 1.1rem 0.85rem 2rem; }
      .page-heading { align-items: flex-start; padding: 0.3rem 0 1.2rem; }
      .page-heading h1 { font-size: 1.8rem; }
      .page-description { font-size: 0.87rem; }
      .grid-4, .grid-2, .grid-3, .blueprint-grid { grid-template-columns: minmax(0, 1fr); gap: 0.8rem; }
      .metric-card { padding: 1rem 1.1rem; }
      .metric-value { font-size: 1.8rem; }
      .card { padding: 1.1rem; margin-bottom: 1rem; }
      .card-header { align-items: flex-start; flex-wrap: wrap; gap: 0.85rem; }
      .card-header > * { min-width: 0; }
      .card-header > button, .card-header > div + div { max-width: 100%; }
      .form-row { flex-direction: column; gap: 0; }
      .form-row > * { width: 100%; }
      .shorts-grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: 0.85rem; }
      .blueprint-grid { grid-template-columns: minmax(0, 1fr); }
      .modal-overlay { padding: 0.75rem; align-items: flex-end; }
      .modal-box { max-height: 92dvh; padding: 1.25rem; border-radius: 18px 18px 12px 12px; }
      #toastContainer { right: 0.75rem; bottom: 0.75rem; left: 0.75rem; }
      .toast { font-size: 0.82rem; }
    }
    @media (max-width: 380px) {
      .btn-emergency { font-size: 0; gap: 0; }
      .btn-emergency::after { content: "STOP"; font-size: 0.68rem; }
      .header-right > .btn-primary { font-size: 0.7rem; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
    }

    :root {
      --bg: #0d1117;
      --bg-surface: #111820;
      --bg-card: #151d26;
      --bg-card-hover: #1b2631;
      --border: rgba(190, 205, 220, 0.12);
      --border-focus: rgba(190, 242, 100, 0.7);
      --primary: #bef264;
      --primary-hover: #d9f99d;
      --primary-glow: rgba(190, 242, 100, 0.18);
      --text: #f3f6fa;
      --text-muted: #aab7c4;
      --text-dim: #8493a1;
      --sidebar-w: 264px;
      --radius-sm: 10px;
      --radius-md: 16px;
      --radius-lg: 22px;
      color-scheme: dark;
    }

    html { background: var(--bg); }
    body { background: var(--bg); color: var(--text); }
    .bg-mesh {
      background:
        radial-gradient(ellipse at 68% -12%, rgba(190, 242, 100, 0.075), transparent 38%),
        radial-gradient(ellipse at 100% 65%, rgba(56, 189, 248, 0.035), transparent 32%);
    }
    aside.sidebar {
      background: rgba(15, 21, 28, 0.97);
      border-right-color: rgba(190, 205, 220, 0.11);
      box-shadow: 12px 0 32px rgba(0, 0, 0, 0.12);
    }
    .sidebar-brand { min-height: var(--header-h); }
    .sidebar-brand-sub { margin-top: 0.2rem; }
    .sidebar-nav { gap: 0.3rem; padding: 1.15rem 0.85rem; }
    .nav-group-label {
      padding: 1.05rem 0.7rem 0.4rem;
      color: #91a0ad;
      letter-spacing: 0.1em;
    }
    .nav-item {
      min-height: 42px;
      border-radius: 11px;
      color: #bdc8d2;
      transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
    }
    .nav-item:hover { background: rgba(255, 255, 255, 0.065); color: #fff; }
    .nav-item.active {
      background: rgba(190, 242, 100, 0.11);
      border-color: rgba(190, 242, 100, 0.24);
      color: #f7ffe8;
    }
    .nav-item.active svg { color: var(--primary); }
    .system-status-pill { background: rgba(255, 255, 255, 0.035); }
    header.top-header {
      background: rgba(13, 17, 23, 0.92);
      border-bottom-color: var(--border);
      padding-inline: clamp(1rem, 3vw, 2.5rem);
    }
    .account-selector {
      min-height: 42px;
      background: #151d26;
      color: var(--text);
    }
    .view-container {
      min-width: 0;
      max-width: 1560px;
      padding-top: clamp(1.6rem, 3vw, 2.6rem);
    }
    .page-heading { padding-bottom: 2rem; }
    .page-eyebrow { color: var(--primary); letter-spacing: 0.15em; }
    .page-heading h1 { font-weight: 760; }
    .page-description { color: var(--text-muted); line-height: 1.65; }
    .card, .metric-card, .short-card, .blueprint-card {
      border-color: var(--border);
      box-shadow: 0 14px 36px rgba(0, 0, 0, 0.16);
    }
    .card { background: linear-gradient(145deg, #161f29, #141c25); }
    .metric-card {
      min-width: 0;
      background: linear-gradient(145deg, #18222d, #141c25);
      gap: 0.65rem;
    }
    .metric-label { color: #b7c3ce; letter-spacing: 0.07em; }
    .metric-detail { color: var(--text-dim); line-height: 1.5; }
    .metric-value { color: #f6f8fb; }
    .card-title { color: #f2f6fa; }
    .card-subtitle { color: var(--text-muted); line-height: 1.55; }
    .btn-primary {
      color: #19220f;
      box-shadow: 0 5px 18px rgba(190, 242, 100, 0.12);
    }
    .btn-secondary {
      background: #1a242e;
      color: #d9e2eb;
    }
    .btn-secondary:hover { background: #222f3b; color: #fff; }
    .form-input, .form-select, .form-textarea {
      background: #10171e;
      color: var(--text);
    }
    .form-label { color: #c6d1da; }
    .table-container { max-width: 100%; }
    .shorts-grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr)); }
    .blueprint-card { background: #151e28; }
    .toast { background: #202b35; }
    .page-heading h1, .page-description, .card-title, .card-subtitle,
    .metric-label, .metric-detail, td, th { overflow-wrap: anywhere; }
    :focus-visible { outline-color: var(--primary); }

    @media (max-width: 1100px) {
      .view-container { padding-inline: clamp(1rem, 3.5vw, 2rem); }
      .grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 640px) {
      header.top-header { flex-wrap: wrap; }
      .header-left { flex: 1 1 100%; }
      .header-right { width: 100%; justify-content: flex-end; }
      .menu-toggle { margin-right: auto; }
      .view-container { padding: 1.35rem 1rem 2rem; }
      .page-heading { padding-bottom: 1.35rem; }
      .grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }
      .metric-card { padding: 0.95rem; }
      .metric-label { font-size: 0.7rem; }
      .metric-value { font-size: 1.7rem; }
      .metric-detail { font-size: 0.72rem; }
      .card { padding: 1.15rem; }
      .shorts-grid { grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr)); }
    }
    @media (max-width: 420px) {
      .grid-4 { grid-template-columns: minmax(0, 1fr); }
      .header-right { justify-content: space-between; }
      .account-selector { width: calc(100vw - 5.2rem); max-width: none; }
      .btn-emergency { padding-inline: 0.55rem; }
      .header-right > .btn-primary { padding-inline: 0.7rem; }
    }
    /* Series Studio Styling */
    .series-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr)); gap: 1.25rem; }
    .series-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1.25rem; transition: all 0.2s; display: flex; flex-direction: column; gap: 0.85rem; }
    .series-card:hover { border-color: rgba(163, 230, 53, 0.4); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
    .series-badge { font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.55rem; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.04em; }
    .series-badge.auto { background: rgba(163, 230, 53, 0.15); color: #a3e635; border: 1px solid rgba(163, 230, 53, 0.3); }
    .series-badge.guided { background: rgba(14, 165, 233, 0.15); color: #0ea5e9; border: 1px solid rgba(14, 165, 233, 0.3); }
    .series-badge.custom { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
    .timeline-container { background: rgba(16, 23, 28, 0.9); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1.5rem; overflow-x: auto; margin-bottom: 1.5rem; }
    .timeline-flow { display: flex; align-items: center; gap: 0.5rem; min-width: max-content; }
    .timeline-node { background: var(--bg-card); border: 2px solid var(--border); border-radius: var(--radius-sm); padding: 0.85rem 1rem; width: 220px; flex-shrink: 0; transition: all 0.2s; position: relative; }
    .timeline-node.final { border-color: #34d399; }
    .timeline-node.active-node { border-color: var(--primary); box-shadow: 0 0 15px rgba(163, 230, 53, 0.2); }
    .timeline-bridge { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 140px; flex-shrink: 0; position: relative; padding: 0 0.5rem; }
    .timeline-arrow { width: 100%; height: 2px; background: linear-gradient(90deg, rgba(163,230,53,0.3), var(--primary), rgba(163,230,53,0.3)); position: relative; margin-top: 0.35rem; }
    .timeline-arrow::after { content: ''; position: absolute; right: 0; top: -4px; width: 0; height: 0; border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 7px solid var(--primary); }
    .cliffhanger-pill { font-size: 0.68rem; font-weight: 700; background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.35); border-radius: 9999px; padding: 0.2rem 0.6rem; text-align: center; white-space: nowrap; max-width: 130px; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
    .episode-editor-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 1.25rem; margin-bottom: 1rem; display: flex; flex-direction: column; gap: 0.85rem; }
    .episode-editor-card.final { border-left: 4px solid #34d399; }
    .quality-gauge { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem; }
    .variation-chip { padding: 0.35rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease; border: 1px solid var(--border); background: rgba(255,255,255,0.03); color: var(--text-dim); }
    .variation-chip:hover { border-color: var(--primary); color: #fff; background: rgba(163,230,53,0.1); }
    .variation-chip.active { background: rgba(163,230,53,0.2); border-color: var(--primary); color: var(--primary); }
    .platform-tab-btn { padding: 0.55rem 1.25rem; font-size: 0.85rem; font-weight: 700; border: none; border-bottom: 2px solid transparent; background: transparent; color: var(--text-dim); cursor: pointer; display: flex; align-items: center; gap: 0.5rem; }
    .platform-tab-btn.active { color: #fff; border-bottom-color: var(--primary); background: rgba(255,255,255,0.02); }
    .mobile-mockup-frame { border: 8px solid #1e293b; border-radius: 36px; background: #000; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); width: 300px; max-width: 100%; position: relative; margin: 0 auto; }
    .mockup-status-bar { height: 24px; background: #000; display: flex; justify-content: space-between; align-items: center; padding: 0 1rem; font-size: 0.65rem; color: #fff; }
    .mockup-screen { position: relative; width: 100%; height: 533px; background: #111; overflow-y: auto; display: flex; flex-direction: column; justify-content: flex-end; padding: 1rem; color: #fff; }
    .thumbnail-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; display: flex; flex-direction: column; transition: transform 0.2s, border-color 0.2s; position: relative; }
    .thumbnail-card:hover { transform: translateY(-3px); border-color: rgba(163,230,53,0.4); }
    .thumbnail-card.selected { border-color: var(--primary); box-shadow: 0 0 16px rgba(163,230,53,0.25); }
    .frame-scrubber { display: flex; gap: 0.75rem; overflow-x: auto; padding: 0.5rem 0; scrollbar-width: thin; }
    .frame-scrubber-item { width: 110px; flex-shrink: 0; cursor: pointer; border: 2px solid transparent; border-radius: var(--radius-sm); overflow: hidden; background: #000; position: relative; }
    .frame-scrubber-item.active { border-color: var(--primary); }
    .readiness-pill { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.25rem 0.65rem; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; cursor: pointer; }
  </style>
</head>
<body>
  <a class="skip-link" href="#mainContent">Skip to content</a>
  <div class="bg-mesh"></div>

  <!-- Left Sidebar -->
  <aside class="sidebar">
    <a href="#" class="sidebar-brand">
      <div class="sidebar-brand-icon">⚡</div>
      <div>
        <div class="sidebar-brand-title">VedioHooks <span>AI</span></div>
        <div class="sidebar-brand-sub">Autonomous Media Factory</div>
      </div>
    </a>

    <nav class="sidebar-nav" id="sidebarNav" aria-label="Main navigation">
      <div class="nav-group-label">Core Operations</div>
      <div class="nav-item active" role="button" tabindex="0" aria-current="page" onclick="switchTab('overview')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
        Overview
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('factory')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
        Video Factory
        <span class="nav-badge" id="navJobsBadge">0</span>
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('library')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
        Video Library
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('dubbing')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 100-6 3 3 0 000 6z"/></svg>
        AI Dubbing Lab
        <span class="nav-badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4);">NEW</span>
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('series-studio')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/></svg>
        Series Studio
        <span class="nav-badge" style="background: rgba(163, 230, 53, 0.2); color: #a3e635; border: 1px solid rgba(163, 230, 53, 0.4);">CLIFFHANGER</span>
      </div>

      <div class="nav-group-label">Multi-Account & Strategy</div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('accounts')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
        Account Manager
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('ai-director')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
        AI Content Director
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('sources')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        Content Discovery
      </div>

      <div class="nav-group-label">Publishing & Meta</div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('metadata-studio')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"/></svg>
        AI Metadata Studio
        <span class="nav-badge" style="background: rgba(14, 165, 233, 0.2); color: #0ea5e9; border: 1px solid rgba(14, 165, 233, 0.4);">SEO</span>
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('thumbnail-studio')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
        Thumbnail Studio
        <span class="nav-badge" style="background: rgba(234, 179, 8, 0.2); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.4);">HIGH CTR</span>
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('calendar')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
        Publishing Calendar
        <span class="nav-badge" id="navDraftsBadge">0</span>
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('instagram')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
        Instagram Graph API
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('analytics')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
        Analytics
      </div>

      <div class="nav-group-label">System Control</div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('automation')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
        Automation Centre
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('health')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
        System Health
      </div>
      <div class="nav-item" role="button" tabindex="0" onclick="switchTab('settings')">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><circle cx="12" cy="12" r="3"/></svg>
        Settings
      </div>
    </nav>

    <div class="sidebar-footer">
      <div class="system-status-pill">
        <span style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="pulse-dot" id="sidebarPulse"></span>
          <span id="sidebarStatusText">24/7 Engine Active</span>
        </span>
        <span style="color: var(--text-dim); font-family: 'JetBrains Mono', monospace;" id="sidebarWorkerCount">0/2</span>
      </div>
    </div>
  </aside>
  <div class="sidebar-backdrop" onclick="setMobileNav(false)" aria-hidden="true"></div>

  <!-- Main Content Body -->
  <main class="main-content" id="mainContent">
    <!-- Top Sticky Header -->
    <header class="top-header">
      <div class="header-left">
        <button class="menu-toggle" id="menuToggle" type="button" aria-label="Open navigation menu" aria-controls="sidebarNav" aria-expanded="false" onclick="setMobileNav()">☰</button>
        <select id="globalAccountSelect" class="account-selector" onchange="onGlobalAccountChange(this.value)">
          <option value="all">🌐 All Accounts (Global View)</option>
        </select>
        <span id="activeNicheBadge" class="badge badge-primary">Global Pipeline</span>
      </div>

      <div class="header-right">
        <div id="hwAccelBadge" style="display: flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0.65rem; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 9999px; font-size: 0.75rem; color: #10b981; font-weight: 600;">
          <span>⚡</span>
          <span id="hwAccelText">Hardware Accelerated</span>
        </div>
        <button id="btnEmergencyStop" class="btn-emergency" onclick="toggleEmergencyStop()">
          <span class="pulse-dot stopped" id="emergencyDot" style="display: none;"></span>
          <span id="emergencyBtnText">EMERGENCY STOP</span>
        </button>
        <button class="btn-primary" onclick="switchTab('factory')">
          + Ingest Video
        </button>
      </div>
    </header>

    <!-- Main Workspace Container -->
    <div class="view-container">
      <div class="page-heading">
        <div>
          <p class="page-eyebrow">VIDEO CONTENT STUDIO</p>
          <h1 id="pageTitle">Your content, in motion.</h1>
          <p class="page-description" id="pageDescription">Turn long-form video into standout short-form content, all from one workspace.</p>
        </div>
      </div>

      <!-- TAB 1: OVERVIEW -->
      <section id="tab-overview" class="tab-view active">
        <div class="grid-4">
          <div class="metric-card">
            <span class="metric-label">Active Instagram Accounts</span>
            <span class="metric-value" id="kpiAccounts">5</span>
            <span class="metric-detail">Multi-account isolated pipelines</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Active Video Jobs</span>
            <span class="metric-value" id="kpiJobs">0</span>
            <span class="metric-detail">Faster-Whisper + Face Tracking</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">9:16 Shorts Rendered</span>
            <span class="metric-value" id="kpiRenders">0</span>
            <span class="metric-detail">Smart Face Tracking & Dynamic Karaoke</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Publishing Drafts</span>
            <span class="metric-value" id="kpiDrafts">0</span>
            <span class="metric-detail">Manual Approval Required</span>
          </div>
        </div>

        <!-- 5 Accounts Live Cards -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Configured Instagram Network</div>
              <div class="card-subtitle">Automated content generation tailored to 5 specialized niches</div>
            </div>
            <button class="btn-secondary" onclick="openCreateAccountModal()">+ Add Account</button>
          </div>
          <div class="grid-3" id="overviewAccountsGrid">
            <!-- Populated via JS -->
          </div>
        </div>

        <!-- Recent Rendered Shorts Showcase -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Recent Rendered 9:16 Vertical Shorts</div>
              <div class="card-subtitle">Ready for review, download, or publishing</div>
            </div>
            <button class="btn-secondary" onclick="switchTab('library')">View All in Library →</button>
          </div>
          <div class="shorts-grid" id="overviewShortsGrid">
            <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 2rem;">
              No completed 9:16 shorts yet. Ingest a video in Video Factory to generate viral clips!
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 2: ACCOUNT MANAGER -->
      <section id="tab-accounts" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Instagram Accounts Management</div>
              <div class="card-subtitle">Manage accounts, niches, brand styling, caption formulas, and schedules</div>
            </div>
            <button class="btn-primary" onclick="openCreateAccountModal()">+ New Instagram Account</button>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Niche</th>
                  <th>Brand Color</th>
                  <th>Schedule</th>
                  <th>Default Theme</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="accountsTableBody">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- TAB 3: CONTENT DISCOVERY -->
      <section id="tab-sources" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Content Discovery & Verification Pipeline</div>
              <div class="card-subtitle">Register YouTube channels, playlists, search queries, and verify facts & copyright</div>
            </div>
            <button class="btn-primary" onclick="openCreateSourceModal()">+ Add Content Source</button>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Account</th>
                  <th>Source Type</th>
                  <th>Attribution & Copyright</th>
                  <th>Verification Notes</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="sourcesTableBody">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- TAB 4: AI CONTENT DIRECTOR -->
      <section id="tab-ai-director" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">AI Content Director — 14-Point Strategic Blueprint</div>
              <div class="card-subtitle">Local deterministic AI strategy generator for retention, viral hooks, and editing</div>
            </div>
            <div style="display: flex; gap: 0.5rem;">
              <select id="directorAccountSelect" class="form-select" style="width: auto;"></select>
              <button class="btn-primary" onclick="generateDirectorBlueprint()">Generate Strategic Blueprint</button>
            </div>
          </div>

          <div class="form-group">
            <input type="text" id="directorCustomTopic" class="form-input" placeholder="Enter optional topic or leave blank for automatic niche-tailored strategy...">
          </div>

          <div id="directorBlueprintOutput">
            <div style="text-align: center; color: var(--text-muted); padding: 3rem; background: rgba(0,0,0,0.2); border-radius: var(--radius-sm);">
              Select an account and click "Generate Strategic Blueprint" to review the 14-point viral blueprint.
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title" style="margin-bottom: 1rem;">Saved Strategic Blueprints History</div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Account</th>
                  <th>Hook Strategy</th>
                  <th>Audience</th>
                  <th>Quality Score</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody id="plansTableBody">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- TAB 5: VIDEO FACTORY -->
      <section id="tab-factory" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Ingest Video for Autonomous Processing</div>
              <div class="card-subtitle">YouTube URL or Local Upload • Smart Face Tracking • Dynamic Karaoke Subtitles</div>
            </div>
          </div>

          <div class="form-row" style="margin-bottom: 1.25rem;">
            <div class="form-group">
              <label class="form-label">Assign to Instagram Account</label>
              <select id="factoryAccountSelect" class="form-select" onchange="onFactoryAccountChange(this.value)"></select>
            </div>
            <div class="form-group">
              <label class="form-label">Subtitle Theme Preset</label>
              <select id="factoryThemeSelect" class="form-select">
                <option value="hormozi_yellow">Hormozi Yellow (Motivation / Bold)</option>
                <option value="hormozi_green">Hormozi Green (Cricket / High Energy)</option>
                <option value="cyber_cyan">Cyber Cyan (AI & Tech / Modern)</option>
                <option value="fire_orange">Fire Orange (Curiosity & Trivia)</option>
                <option value="beast_red">Beast Red (Gym & Fitness Power)</option>
                <option value="clean_minimal">Clean Minimal (Education)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Vertical Crop Mode</label>
              <select id="factoryCropSelect" class="form-select">
                <option value="smart_face">Smart Face Tracking (MediaPipe AI)</option>
                <option value="split_stack">2-Speaker Split Screen (Podcast 1+1 Stack)</option>
                <option value="blur_fill">Blurred Background 9:16</option>
                <option value="center">Center Crop 9:16</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Subtitles Language</label>
              <select id="factoryLangSelect" class="form-select">
                <option value="en">English (Original Karaoke)</option>
                <option value="es">English + Spanish (Bilingual)</option>
                <option value="hi">English + Hindi (Bilingual)</option>
                <option value="fr">English + French (Bilingual)</option>
                <option value="de">English + German (Bilingual)</option>
                <option value="pt">English + Portuguese (Bilingual)</option>
                <option value="ja">English + Japanese (Bilingual)</option>
              </select>
            </div>
          </div>

          <!-- Advanced AI Audio & Silence Enhancements -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem 1rem; margin-bottom: 1.25rem; background: rgba(255,255,255,0.02); padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
            <label style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; color: #cbd5e1; cursor: pointer;">
              <input type="checkbox" id="factoryDuckingCheck" checked style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
              <span>🎵 Dynamic Audio Ducking (-14dB ambient music during voice)</span>
            </label>
            <label style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; color: #cbd5e1; cursor: pointer;">
              <input type="checkbox" id="factoryJumpcutCheck" checked style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
              <span>⚡ Smart Dead-Air Removal (Jump-cut silence &gt; 350ms)</span>
            </label>
            <label style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; color: #cbd5e1; cursor: pointer;">
              <input type="checkbox" id="factorySfxCheck" checked style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
              <span>🔊 Hook Transition Whoosh SFX (0-3s retention booster)</span>
            </label>
            <label style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; color: #cbd5e1; cursor: pointer;">
              <input type="checkbox" id="factoryBrollCheck" style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
              <span>🎨 Thematic B-Roll Pattern Interrupt Overlay</span>
            </label>
            <label style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; color: #cbd5e1; cursor: pointer;">
              <input type="checkbox" id="factoryAutoZoomCheck" checked style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
              <span>⚡ Dynamic Auto-Zoom (1.16x punch-cuts every 4-5s to stop scroll fatigue)</span>
            </label>
            <label style="display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem; color: #cbd5e1; cursor: pointer;">
              <input type="checkbox" id="factoryHookBannerCheck" checked style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
              <span>🏷️ Top Hook Header Banner (High-contrast 0-3.5s title pill in safe-zone)</span>
            </label>
          </div>

          <!-- Top Hook Header Banner Config Row -->
          <div id="factoryHookBannerRow" style="display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1.25rem; background: rgba(99, 102, 241, 0.04); padding: 0.65rem 1rem; border-radius: 8px; border: 1px solid rgba(99, 102, 241, 0.2);">
            <span style="font-size: 0.82rem; font-weight: 700; color: #a5b4fc; white-space: nowrap;">🏷️ Top Banner Headline:</span>
            <input type="text" id="factoryHookBannerInput" class="form-input" style="padding: 0.45rem 0.75rem; font-size: 0.85rem;" placeholder="Leave empty for smart auto-generated hook headline (e.g. BRUTAL TRUTH ABOUT SUCCESS)...">
          </div>

          <!-- Ingest Mode Switcher -->
          <div style="display: flex; gap: 0.5rem; margin-bottom: 1.25rem; border-bottom: 1px solid var(--border); padding-bottom: 0.6rem;">
            <button id="btnModeSingle" class="btn-primary" style="font-size: 0.82rem; padding: 0.45rem 1rem;" onclick="setIngestMode('single')">
              🎬 Single Video Ingest
            </button>
            <button id="btnModeBatch" class="btn-secondary" style="font-size: 0.82rem; padding: 0.45rem 1rem;" onclick="setIngestMode('batch')">
              📚 Autonomous Playlist / Channel Ingest
            </button>
          </div>

          <!-- Mode 1: Single Video Container -->
          <div id="containerSingleIngest">
            <div style="display: flex; gap: 0.75rem; margin-bottom: 1.5rem;">
              <input type="text" id="urlInput" class="form-input" placeholder="Paste YouTube / Web Video URL (e.g., https://www.youtube.com/watch?v=...)">
              <button class="btn-primary" style="white-space: nowrap;" onclick="submitUrlJob()">Analyze URL</button>
            </div>

            <div style="border-top: 1px solid var(--border); padding-top: 1.25rem;">
              <div class="form-label" style="margin-bottom: 0.5rem;">Or Upload a Local Video File:</div>
              <div style="display: flex; gap: 0.75rem; align-items: center;">
                <input type="file" id="fileInput" accept="video/*" class="form-input" style="padding: 0.4rem;">
                <button class="btn-secondary" style="white-space: nowrap;" onclick="uploadFileJob()">Upload & Process</button>
              </div>
            </div>
          </div>

          <!-- Mode 2: Batch Playlist / Channel Ingest Container -->
          <div id="containerBatchIngest" style="display: none;">
            <div style="background: rgba(99, 102, 241, 0.05); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 1rem; margin-bottom: 1.25rem;">
              <div style="font-size: 0.85rem; color: #818cf8; font-weight: 600; margin-bottom: 0.35rem;">
                ⚡ Autonomous Fast Flat-Metadata Crawl (Zero large downloads upfront)
              </div>
              <div style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.5;">
                Enter a YouTube Playlist or Channel Videos URL. The engine scans candidates in flat mode, checks duration, filters duplicates, and queues high-probability viral source videos into the SQLite pipeline.
              </div>
            </div>

            <div style="display: flex; gap: 0.75rem; margin-bottom: 1rem;">
              <input type="text" id="batchPlaylistInput" class="form-input" placeholder="Paste YouTube Playlist or Channel URL (e.g., https://www.youtube.com/playlist?list=...)">
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem;">
              <div>
                <label class="form-label">Max Videos to Ingest:</label>
                <select id="batchMaxItems" class="form-select">
                  <option value="3">3 Videos</option>
                  <option value="5" selected>5 Videos (Recommended)</option>
                  <option value="10">10 Videos</option>
                  <option value="20">20 Videos</option>
                </select>
              </div>
              <div>
                <label class="form-label">Min Video Duration:</label>
                <select id="batchMinDuration" class="form-select">
                  <option value="30">30 seconds</option>
                  <option value="60" selected>1 minute</option>
                  <option value="180">3 minutes</option>
                </select>
              </div>
              <div>
                <label class="form-label">Max Video Duration:</label>
                <select id="batchMaxDuration" class="form-select">
                  <option value="900">15 minutes</option>
                  <option value="1800" selected>30 minutes</option>
                  <option value="3600">60 minutes</option>
                </select>
              </div>
            </div>

            <div style="display: flex; justify-content: flex-end;">
              <button class="btn-primary" style="white-space: nowrap; background: linear-gradient(135deg, #6366f1, #4f46e5);" onclick="submitBatchPlaylistJob()">
                🚀 Crawl &amp; Enqueue Batch Jobs
              </button>
            </div>
            <div id="batchIngestResult" style="margin-top: 1rem; font-size: 0.85rem; display: none;"></div>
          </div>
        </div>

        <!-- Active Processing Progress Banner -->
        <div id="jobProgressCard" class="card" style="display: none; border-color: rgba(99,102,241,0.4);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <div style="font-weight: 700; font-size: 1.05rem;" id="progressTitle">Processing Video...</div>
            <span class="badge badge-primary" id="progressStatus">WORKING</span>
          </div>
          <div style="width: 100%; height: 8px; background: rgba(0,0,0,0.4); border-radius: 9999px; overflow: hidden; margin-bottom: 0.5rem;">
            <div id="progressBar" style="height: 100%; width: 0%; background: linear-gradient(90deg, #6366f1, #10b981); transition: width 0.4s ease;"></div>
          </div>
          <div style="font-size: 0.82rem; color: var(--text-muted);" id="progressDetail">Initializing pipeline...</div>
        </div>

        <!-- Detected Viral Clips -->
        <div class="card">
          <div class="card-title" style="margin-bottom: 1.25rem;">Detected Viral Highlights & Hook Selections</div>
          <div id="clipsGrid" class="grid-3">
            <div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 2rem;">
              No clips analyzed yet. Submit a video above to run multi-dimensional hook scoring.
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 6: VIDEO LIBRARY -->
      <section id="tab-library" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">9:16 Vertical Video Library</div>
              <div class="card-subtitle">All rendered vertical shorts with face tracking & karaoke subtitles</div>
            </div>
            <select id="libraryAccountFilter" class="form-select" style="width: auto;" onchange="loadLibraryShorts()">
              <option value="all">All Accounts</option>
            </select>
          </div>
          <div class="shorts-grid" id="libraryShortsGrid">
            <!-- Populated via JS -->
          </div>
        </div>
      </section>

      <!-- TAB: AI VOICE DUBBING & SPEECH LAB -->
      <section id="tab-dubbing" class="tab-view">
        <div class="card" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 18, 28, 0.95) 100%); border-color: rgba(16, 185, 129, 0.3);">
          <div class="card-header">
            <div>
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem;">🎙️</span>
                <div class="card-title" style="font-size: 1.35rem;">AI Voice Dubbing & Speech Cloning Studio</div>
                <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4);">100% Free & Offline-Ready</span>
              </div>
              <div class="card-subtitle" style="margin-top: 0.35rem;">
                Translate transcripts into 8+ international languages, synthesize neural voiceovers, time-stretch and studio-mix speech onto 9:16 vertical shorts.
              </div>
            </div>
            <div style="display: flex; gap: 0.75rem;">
              <button class="btn-secondary" style="font-size: 0.82rem;" onclick="loadDubbingLibrary()">🔄 Refresh Studio</button>
            </div>
          </div>
        </div>

        <div class="grid-2" style="margin-bottom: 1.5rem;">
          <!-- Left Column: Dubbing Controls & Text -->
          <div class="card">
            <div class="card-title" style="font-size: 1.1rem; margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
              <span>🎛️</span> Step 1: Voice & Audio Configuration
            </div>

            <div class="form-group" style="margin-bottom: 1rem;">
              <label class="form-label">Select Source Video Short</label>
              <select id="dubSourceSelect" class="form-select" onchange="onDubSourceChange(this.value)">
                <option value="">-- Choose a rendered short from library --</option>
              </select>
            </div>

            <div class="form-row" style="margin-bottom: 1rem;">
              <div class="form-group">
                <label class="form-label">Target Language</label>
                <select id="dubLangSelect" class="form-select" onchange="onDubLangChange(this.value)">
                  <option value="es">🇪🇸 Spanish (Español)</option>
                  <option value="hi">🇮🇳 Hindi (हिन्दी)</option>
                  <option value="fr">🇫🇷 French (Français)</option>
                  <option value="de">🇩🇪 German (Deutsch)</option>
                  <option value="ja">🇯🇵 Japanese (日本語)</option>
                  <option value="pt">🇧🇷 Portuguese (Português)</option>
                  <option value="it">🇮🇹 Italian (Italiano)</option>
                  <option value="en">🇺🇸 English (US)</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Neural Voice Model</label>
                <div style="display: flex; gap: 0.5rem;">
                  <select id="dubVoiceSelect" class="form-select" style="flex: 1;"></select>
                  <button type="button" class="btn-secondary" style="padding: 0.4rem 0.75rem;" onclick="previewSelectedVoice()" title="Listen to Voice Sample">🔊</button>
                </div>
              </div>
            </div>

            <div class="form-row" style="margin-bottom: 1rem;">
              <div class="form-group">
                <label class="form-label">Audio Studio Mix Mode</label>
                <select id="dubBlendMode" class="form-select">
                  <option value="ducked">Ducked Studio Mix (Voiceover 85% / Original Background 15%)</option>
                  <option value="replace">Voiceover Only (100% Dubbed Speech / Original Muted)</option>
                  <option value="bilingual">Bilingual Dual-Track (Left Original / Right Dubbed)</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Speech Pacing Rate (<span id="dubSpeedVal">1.0x</span>)</label>
                <input type="range" id="dubSpeedSlider" min="0.75" max="1.4" step="0.05" value="1.0" class="form-input" style="padding: 0.2rem;" oninput="document.getElementById('dubSpeedVal').innerText=this.value+'x'">
              </div>
            </div>

            <div class="form-group" style="margin-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <label class="form-label" style="margin-bottom: 0;">Transcript / Dubbing Script</label>
                <button type="button" class="btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.6rem;" onclick="autoTranslateDubText()">🔄 Auto-Translate Script</button>
              </div>
              <textarea id="dubScriptText" class="form-textarea" rows="4" placeholder="Enter transcript or dialogue to synthesize..."></textarea>
            </div>

            <button id="btnStartDubbing" class="btn-primary" style="width: 100%; padding: 0.85rem; font-size: 0.95rem; font-weight: 700; background: linear-gradient(135deg, #10b981 0%, #059669 100%); border: none;" onclick="startDubbingJob()">
              ⚡ Synthesize & Dub Video Short
            </button>
            <div id="dubProgressBox" style="display: none; margin-top: 1rem; background: rgba(0,0,0,0.3); border-radius: 8px; padding: 0.75rem;">
              <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.4rem;">
                <span id="dubProgressText" style="color: #10b981;">Synthesizing neural voiceover...</span>
                <span id="dubProgressPercent">45%</span>
              </div>
              <div class="progress-bar-bg"><div id="dubProgressBar" class="progress-bar-fill" style="width: 45%; background: #10b981;"></div></div>
            </div>
          </div>

          <!-- Right Column: Player & Metadata -->
          <div class="card">
            <div class="card-title" style="font-size: 1.1rem; margin-bottom: 1.25rem; display: flex; align-items: center; gap: 0.5rem;">
              <span>📺</span> Step 2: Live Dubbed Short Showcase
            </div>

            <div id="dubPreviewPlaceholder" style="text-align: center; color: var(--text-muted); padding: 4rem 1rem; border: 2px dashed rgba(255,255,255,0.08); border-radius: 12px;">
              <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🎙️</div>
              <div style="font-weight: 600; color: #e2e8f0;">No Dubbed Short Rendered Yet</div>
              <div style="font-size: 0.82rem; margin-top: 0.25rem;">Select a video short on the left and click "Synthesize & Dub" to preview the result.</div>
            </div>

            <div id="dubPreviewContainer" style="display: none;">
              <div style="display: flex; justify-content: center; margin-bottom: 1rem;">
                <video id="dubVideoPlayer" controls playsinline style="width: 250px; height: 440px; border-radius: 12px; background: #000; object-fit: cover; border: 1px solid rgba(16, 185, 129, 0.4); box-shadow: 0 10px 30px rgba(0,0,0,0.6);"></video>
              </div>

              <div id="dubDetailsBox" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0.85rem; margin-bottom: 1rem; font-size: 0.82rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                <!-- Populated via JS -->
              </div>

              <div style="display: flex; gap: 0.75rem;">
                <button id="btnDownloadDub" class="btn-secondary" style="flex: 1; padding: 0.65rem;" onclick="downloadDubbedShort()">
                  📥 Download Dubbed MP4
                </button>
                <button id="btnQueueDub" class="btn-primary" style="flex: 1; padding: 0.65rem;" onclick="queueDubbedShort()">
                  📅 Send to Instagram Drafts
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Dubbing History Table -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Dubbed Shorts History & Library</div>
              <div class="card-subtitle">All multi-language synthesized video shorts</div>
            </div>
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Target Language</th>
                  <th>Voice Model</th>
                  <th>Audio Blend Mode</th>
                  <th>Duration</th>
                  <th>Rendered File</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="dubHistoryTableBody">
                <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">No dubbed videos generated yet.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- TAB: SERIES STUDIO (AI CLIFFHANGER SERIES ENGINE) -->
      <section id="tab-series-studio" class="tab-view">
        <!-- Series Studio Top Banner -->
        <div class="card" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, rgba(163, 230, 53, 0.08) 0%, rgba(15, 18, 28, 0.95) 100%); border-color: rgba(163, 230, 53, 0.3);">
          <div class="card-header" style="flex-wrap: wrap; gap: 1rem;">
            <div>
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem;">🎬</span>
                <div class="card-title" style="font-size: 1.35rem;">AI Cliffhanger Series Engine</div>
                <span class="badge" style="background: rgba(163, 230, 53, 0.2); color: #a3e635; border: 1px solid rgba(163, 230, 53, 0.4);">Binge-Worthy Shorts</span>
              </div>
              <div class="card-subtitle" style="margin-top: 0.35rem;">
                Transform long-form horizontal videos into interconnected multi-episode series with opening hooks, narrative continuity, and scroll-stopping cliffhangers.
              </div>
            </div>
            <div style="display: flex; gap: 0.75rem; align-items: center;">
              <button class="btn-primary" onclick="toggleSeriesCreatorModal(true)">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" style="width: 16px; height: 16px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                Create AI Series
              </button>
              <button class="btn-secondary" onclick="loadSeriesStudio()">🔄 Refresh</button>
            </div>
          </div>
        </div>

        <!-- Create Series Modal / Slide-out Panel -->
        <div id="seriesCreatorModal" class="card" style="display: none; margin-bottom: 1.5rem; border: 1px solid rgba(163, 230, 53, 0.4); background: rgba(18, 27, 33, 0.98);">
          <div class="card-header">
            <div>
              <div class="card-title">New Multi-Episode Series Generator</div>
              <div class="card-subtitle">Select source video, generation mode, and narrative parameters.</div>
            </div>
            <button class="btn-secondary" onclick="toggleSeriesCreatorModal(false)">✕ Close</button>
          </div>
          <div class="grid-3" style="gap: 1rem; margin-top: 1rem;">
            <div>
              <label class="form-label">Source Video (Transcribed Job)</label>
              <select id="seriesSourceJobSelect" class="form-input" onchange="onSeriesJobSelected()">
                <option value="">-- Choose a Transcribed Video --</option>
              </select>
            </div>
            <div>
              <label class="form-label">Generation Mode</label>
              <select id="seriesGenModeSelect" class="form-input" onchange="onSeriesModeChanged()">
                <option value="auto">MODE 1: AUTO SERIES (Autonomous Story Arc & Cliffhangers)</option>
                <option value="guided">MODE 2: GUIDED SERIES (Inspect & Choose Story Arcs)</option>
                <option value="custom">MODE 3: CUSTOM SERIES (Custom Boundaries & Range)</option>
              </select>
            </div>
            <div>
              <label class="form-label">Target Account</label>
              <select id="seriesAccountSelect" class="form-input">
                <option value="acc_motivation">🔥 Apex Mindset & Discipline (Motivation)</option>
                <option value="acc_cricket">🏏 Cricket Vault & Analysis (Cricket)</option>
                <option value="acc_ai_study">🤖 AI Tools & Study Hacks (AI & Study)</option>
                <option value="acc_fitness">💪 Iron Physique & Training (Gym & Fitness)</option>
                <option value="acc_general">🌍 Curiosity Stream & Discoveries (General)</option>
              </select>
            </div>
          </div>

          <!-- Custom Mode Options -->
          <div id="seriesCustomOptions" class="grid-3" style="display: none; gap: 1rem; margin-top: 1rem; padding: 1rem; background: rgba(0,0,0,0.25); border-radius: var(--radius-sm);">
            <div>
              <label class="form-label">Custom Start Timestamp (sec)</label>
              <input type="number" id="seriesCustomStart" class="form-input" value="0.0" step="1.0" min="0">
            </div>
            <div>
              <label class="form-label">Custom End Timestamp (sec)</label>
              <input type="number" id="seriesCustomEnd" class="form-input" value="180.0" step="1.0" min="5">
            </div>
            <div>
              <label class="form-label">Desired Episode Count</label>
              <input type="number" id="seriesEpisodeCount" class="form-input" value="3" min="2" max="8">
            </div>
          </div>

          <!-- Guided Mode Story Arcs Container -->
          <div id="seriesGuidedContainer" style="display: none; margin-top: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <div style="font-weight: 700; font-size: 0.95rem; color: #fff;">Detected Story Arcs in Source Video</div>
              <button class="btn-secondary" id="btnAnalyzeArcs" onclick="triggerAnalyzeStoryArcs()">🔍 Analyze Video for Arcs</button>
            </div>
            <div id="guidedArcsList" style="display: flex; flex-direction: column; gap: 0.75rem;">
              <div style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem; text-align: center; border: 1px dashed var(--border); border-radius: var(--radius-sm);">
                Click "Analyze Video for Arcs" to let the AI discover potential storylines and turning points.
              </div>
            </div>
          </div>

          <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem;">
            <button class="btn-secondary" onclick="toggleSeriesCreatorModal(false)">Cancel</button>
            <button class="btn-primary" id="btnExecuteSeriesGen" onclick="executeGenerateSeries()">
              ⚡ Generate AI Series
            </button>
          </div>
        </div>

        <!-- SERIES LIBRARY VIEW -->
        <div id="seriesLibraryContainer">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div>
              <h3 style="font-size: 1.15rem; font-weight: 700;">Series Library</h3>
              <p style="color: var(--text-muted); font-size: 0.82rem;">All interconnected episodic short series created from your source footage.</p>
            </div>
            <div style="display: flex; gap: 0.75rem; align-items: center;">
              <select id="seriesStatusFilter" class="form-input" style="width: 140px; font-size: 0.82rem;" onchange="loadSeriesStudio()">
                <option value="all">All Statuses</option>
                <option value="ready">Ready</option>
                <option value="rendering">Rendering</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>

          <div class="series-grid" id="seriesGridContainer">
            <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted); border: 1px dashed var(--border); border-radius: var(--radius-md);">
              <div style="font-size: 2rem; margin-bottom: 0.5rem;">🎬</div>
              <div style="font-size: 1.1rem; font-weight: 700; color: #fff;">No AI Series Generated Yet</div>
              <p style="margin-top: 0.25rem;">Select any transcribed video from your Video Factory and turn it into a binge-worthy multi-episode cliffhanger series.</p>
              <button class="btn-primary" style="margin-top: 1rem;" onclick="toggleSeriesCreatorModal(true)">+ Create First AI Series</button>
            </div>
          </div>
        </div>

        <!-- SERIES DETAILS & TIMELINE STUDIO (Shown when a series is active) -->
        <div id="seriesStudioDetailView" style="display: none;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <button class="btn-secondary" onclick="closeSeriesDetailView()">← Back to Library</button>
              <h2 id="activeSeriesTitle" style="font-size: 1.35rem; font-weight: 800; color: #fff;">Series Title</h2>
              <span id="activeSeriesBadge" class="series-badge auto">AUTO</span>
              <span id="activeSeriesStatus" class="badge">Ready</span>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
              <button class="btn-primary" id="btnBatchRenderActive" onclick="batchRenderActiveSeries()">
                ▶ Batch Render All (<span id="unrenderedCountBadge">0</span>)
              </button>
              <button class="btn-secondary" onclick="exportActiveSeriesPackage()">📥 Export Series Package</button>
              <button class="btn-secondary" onclick="regenerateActiveSeriesPrompt()">🔄 Regenerate Arc</button>
              <button class="btn-danger" style="background: rgba(244, 63, 94, 0.12); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3);" onclick="deleteActiveSeries()">🗑 Delete</button>
            </div>
          </div>

          <!-- Story Summary & Narrative Architecture Bar -->
          <div class="card" style="margin-bottom: 1.5rem;">
            <div class="card-header">
              <div class="card-title">Narrative Architecture & Story Arc</div>
              <div class="card-subtitle">Semantic analysis and tension curve across the sequence</div>
            </div>
            <div class="grid-4" style="gap: 1rem; margin-top: 0.75rem;" id="narrativeArcTelemetry">
              <div style="background: rgba(0,0,0,0.25); padding: 0.85rem; border-radius: var(--radius-sm); border-left: 3px solid var(--primary);">
                <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-dim); font-weight: 700;">Beginning / Hook</div>
                <div id="arcBeginningText" style="font-size: 0.82rem; margin-top: 0.25rem; color: #fff;">Initial status quo...</div>
              </div>
              <div style="background: rgba(0,0,0,0.25); padding: 0.85rem; border-radius: var(--radius-sm); border-left: 3px solid var(--amber);">
                <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-dim); font-weight: 700;">Central Conflict</div>
                <div id="arcConflictText" style="font-size: 0.82rem; margin-top: 0.25rem; color: #fff;">Core question hanging...</div>
              </div>
              <div style="background: rgba(0,0,0,0.25); padding: 0.85rem; border-radius: var(--radius-sm); border-left: 3px solid #f43f5e;">
                <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-dim); font-weight: 700;">Turning Point</div>
                <div id="arcTurningPointText" style="font-size: 0.82rem; margin-top: 0.25rem; color: #fff;">Dramatic shift in narrative...</div>
              </div>
              <div style="background: rgba(0,0,0,0.25); padding: 0.85rem; border-radius: var(--radius-sm); border-left: 3px solid #34d399;">
                <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-dim); font-weight: 700;">Final Resolution</div>
                <div id="arcResolutionText" style="font-size: 0.82rem; margin-top: 0.25rem; color: #fff;">Satisfying payoff and takeaway...</div>
              </div>
            </div>
            <div id="seriesMemoryBar" style="margin-top: 1rem; padding: 0.75rem 1rem; background: rgba(163, 230, 53, 0.05); border: 1px solid rgba(163, 230, 53, 0.2); border-radius: var(--radius-sm); font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 0.75rem;">
              <span>🧠 <strong>Series Continuity State:</strong></span>
              <span id="seriesMemoryTensionText">Tracking established knowledge and hanging cliffhangers across all episodes.</span>
            </div>
          </div>

          <!-- VISUAL EPISODE TIMELINE -->
          <div class="timeline-container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
              <div style="font-weight: 700; font-size: 0.95rem; color: #fff;">Interactive Episode Timeline & Cliffhanger Transitions</div>
              <span style="font-size: 0.75rem; color: var(--text-muted);">Click any node to jump to episode details</span>
            </div>
            <div class="timeline-flow" id="visualTimelineFlow">
              <!-- Rendered dynamically -->
            </div>
          </div>

          <!-- EPISODES LIST & IN-PLACE CONTROLS -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="font-size: 1.15rem; font-weight: 700;">Episodes & Editing Controls</h3>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Edit titles, hooks, boundaries, or regenerate cliffhangers</span>
          </div>

          <div id="activeEpisodesList" style="display: flex; flex-direction: column; gap: 1rem;">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Video Preview Modal for Episodes -->
        <div id="episodePreviewModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 999; align-items: center; justify-content: center; backdrop-filter: blur(8px);">
          <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); max-width: 500px; width: 90%; padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <h4 id="previewModalTitle" style="font-size: 1.1rem; font-weight: 700;">Episode Preview</h4>
              <button class="btn-secondary" style="padding: 0.2rem 0.5rem;" onclick="closeEpisodePreviewModal()">✕</button>
            </div>
            <div style="width: 100%; aspect-ratio: 9/16; max-height: 520px; background: #000; border-radius: var(--radius-sm); overflow: hidden; display: flex; align-items: center; justify-content: center;">
              <video id="previewModalVideo" controls style="width: 100%; height: 100%; object-fit: contain;"></video>
            </div>
            <div id="previewModalHookBanner" style="padding: 0.65rem; background: rgba(0,0,0,0.3); border-radius: var(--radius-sm); font-size: 0.82rem; color: var(--primary);"></div>
            <div style="display: flex; justify-content: flex-end;">
              <button class="btn-secondary" onclick="closeEpisodePreviewModal()">Close Preview</button>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB: AI METADATA STUDIO -->
      <section id="tab-metadata-studio" class="tab-view">
        <div class="card" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, rgba(14, 165, 233, 0.08) 0%, rgba(15, 18, 28, 0.95) 100%); border-color: rgba(14, 165, 233, 0.3);">
          <div class="card-header" style="flex-wrap: wrap; gap: 1rem;">
            <div>
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem;">🏷️</span>
                <div class="card-title" style="font-size: 1.35rem;">AI Metadata & SEO Studio</div>
                <span class="badge" style="background: rgba(14, 165, 233, 0.2); color: #0ea5e9; border: 1px solid rgba(14, 165, 233, 0.4);">Platform-Native SEO</span>
              </div>
              <div class="card-subtitle" style="margin-top: 0.35rem;">
                Generate high-conversion titles, SEO descriptions, niche hashtags, and audience-targeted keywords for YouTube, Instagram, and TikTok.
              </div>
            </div>
            <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
              <button class="btn-primary" onclick="generateActiveMetadata()">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" style="width: 16px; height: 16px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                Generate AI Metadata
              </button>
              <button class="btn-secondary" onclick="saveActiveMetadata()">💾 Save Metadata</button>
              <button class="btn-secondary" onclick="copyAllActiveMetadata()">📋 Copy All</button>
              <button class="btn-secondary" onclick="openReadinessModalForActive()">🚀 Readiness Check</button>
            </div>
          </div>
        </div>

        <!-- Target Content & Quality Header -->
        <div class="grid-3" style="gap: 1rem; margin-bottom: 1.5rem;">
          <div class="card" style="margin-bottom: 0;">
            <label class="form-label">Select Target Content</label>
            <select id="metaTargetSelect" class="form-input" onchange="onMetadataTargetChanged()">
              <option value="">-- Choose Short or Series Episode --</option>
            </select>
          </div>
          <div class="card" style="margin-bottom: 0;">
            <label class="form-label">Content Niche Profile</label>
            <select id="metaNicheSelect" class="form-input" onchange="onMetadataNicheChanged()">
              <option value="Motivation">🔥 Apex Mindset & Discipline (Motivation)</option>
              <option value="Cricket">🏏 Cricket Vault & Analysis (Cricket)</option>
              <option value="AI & Study">🤖 AI Tools & Study Hacks (AI & Study)</option>
              <option value="Gym & Fitness">💪 Iron Physique & Training (Gym & Fitness)</option>
              <option value="Common / General">🌍 Curiosity Stream & Discoveries (General)</option>
            </select>
          </div>
          <div class="card" style="margin-bottom: 0; display: flex; align-items: center; justify-content: space-between; padding: 1rem;">
            <div>
              <div style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700;">Metadata Quality Score</div>
              <div id="metaQualityScoreText" style="font-size: 1.6rem; font-weight: 800; color: var(--primary); margin-top: 0.2rem;">-- / 100</div>
              <div id="metaQualityStatusText" style="font-size: 0.72rem; color: var(--text-muted);">Awaiting generation</div>
            </div>
            <div id="metaQualityGauge" class="quality-gauge" style="background: rgba(163,230,53,0.15); color: var(--primary); width: 52px; height: 52px; font-size: 1rem;">--</div>
          </div>
        </div>

        <!-- Title Variations Picker -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <span style="font-size: 0.85rem; font-weight: 700; color: #fff;">💡 AI Title Variations (Click to apply)</span>
            <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="regenerateTitleVariations()">🔄 New Variations</button>
          </div>
          <div style="display: flex; gap: 0.6rem; flex-wrap: wrap;">
            <div id="chipTitleCuriosity" class="variation-chip" onclick="applyTitleVariation('curiosity_driven')">🔍 Curiosity-Driven: <span id="textTitleCuriosity">--</span></div>
            <div id="chipTitleSEO" class="variation-chip" onclick="applyTitleVariation('seo_focused')">📈 SEO-Focused: <span id="textTitleSEO">--</span></div>
            <div id="chipTitleEmotional" class="variation-chip" onclick="applyTitleVariation('emotional')">❤️ Emotional: <span id="textTitleEmotional">--</span></div>
            <div id="chipTitleBold" class="variation-chip" onclick="applyTitleVariation('bold_attention')">⚡ Bold & Urgent: <span id="textTitleBold">--</span></div>
          </div>
        </div>

        <!-- Main Editor & Mobile Mockup Grid -->
        <div style="display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(320px, 1.2fr); gap: 1.5rem; align-items: start;">
          <!-- Editor Panel -->
          <div class="card" style="margin-bottom: 0;">
            <!-- Platform Tabs -->
            <div style="display: flex; border-bottom: 1px solid var(--border); margin-bottom: 1.25rem;">
              <button class="platform-tab-btn active" id="tabBtnYT" onclick="switchMetadataPlatform('youtube')">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width: 18px; height: 18px; color: #ef4444;"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                YouTube
              </button>
              <button class="platform-tab-btn" id="tabBtnIG" onclick="switchMetadataPlatform('instagram')">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width: 18px; height: 18px; color: #e1306c;"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                Instagram Reels
              </button>
              <button class="platform-tab-btn" id="tabBtnTT" onclick="switchMetadataPlatform('tiktok')">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width: 18px; height: 18px; color: #00f2fe;"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 3 15.68 6.34 6.34 0 0 0 9.35 22a6.33 6.33 0 0 0 6.38-6.32V8.9a8.16 8.16 0 0 0 4.86 1.6V7.05a4.85 4.85 0 0 1-1-.36z"/></svg>
                TikTok
              </button>
            </div>

            <!-- YouTube Fields -->
            <div id="metaPanelYT">
              <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <label class="form-label" style="margin-bottom: 0;">Video Title</label>
                  <span id="ytTitleCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 100</span>
                </div>
                <div style="display: flex; gap: 0.5rem;">
                  <input type="text" id="metaYtTitle" class="form-input" maxlength="100" oninput="updateMetaCounters()">
                  <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="copyFieldValue('metaYtTitle')">📋</button>
                </div>
              </div>

              <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <label class="form-label" style="margin-bottom: 0;">Description & Timestamps</label>
                  <span id="ytDescCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 5000</span>
                </div>
                <textarea id="metaYtDesc" class="form-input" rows="8" maxlength="5000" style="resize: vertical; font-size: 0.82rem;" oninput="updateMetaCounters()"></textarea>
                <div style="display: flex; justify-content: flex-end; margin-top: 0.35rem; gap: 0.5rem;">
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="copyFieldValue('metaYtDesc')">📋 Copy Description</button>
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="regenerateSpecificField('youtube', 'description')">🔄 Regenerate</button>
                </div>
              </div>

              <div class="grid-2" style="gap: 1rem; margin-bottom: 1rem;">
                <div>
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                    <label class="form-label" style="margin-bottom: 0;">Searchable Tags</label>
                    <span id="ytTagsCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 500</span>
                  </div>
                  <input type="text" id="metaYtTags" class="form-input" placeholder="tag1, tag2, tag3" oninput="updateMetaCounters()">
                </div>
                <div>
                  <label class="form-label">Category</label>
                  <input type="text" id="metaYtCategory" class="form-input" value="People & Blogs">
                </div>
              </div>

              <div style="margin-bottom: 1rem;">
                <label class="form-label">Pinned Comment</label>
                <input type="text" id="metaYtPinned" class="form-input">
              </div>
            </div>

            <!-- Instagram Fields -->
            <div id="metaPanelIG" style="display: none;">
              <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <label class="form-label" style="margin-bottom: 0;">First-Line Hook (Before '...more')</label>
                  <span id="igHookCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 85</span>
                </div>
                <input type="text" id="metaIgHook" class="form-input" maxlength="85" oninput="updateMetaCounters()">
              </div>

              <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <label class="form-label" style="margin-bottom: 0;">Instagram Caption</label>
                  <span id="igCaptionCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 2200</span>
                </div>
                <textarea id="metaIgCaption" class="form-input" rows="8" maxlength="2200" style="resize: vertical; font-size: 0.82rem;" oninput="updateMetaCounters()"></textarea>
                <div style="display: flex; justify-content: flex-end; margin-top: 0.35rem; gap: 0.5rem;">
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="copyFieldValue('metaIgCaption')">📋 Copy Caption</button>
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="regenerateSpecificField('instagram', 'caption')">🔄 Regenerate</button>
                </div>
              </div>

              <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <label class="form-label" style="margin-bottom: 0;">Targeted Hashtags</label>
                  <span id="igTagsCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 30 tags</span>
                </div>
                <input type="text" id="metaIgHashtags" class="form-input" oninput="updateMetaCounters()">
              </div>

              <div style="margin-bottom: 1rem;">
                <label class="form-label">Pinned Question / Engagement Prompt</label>
                <input type="text" id="metaIgPinned" class="form-input">
              </div>
            </div>

            <!-- TikTok Fields -->
            <div id="metaPanelTT" style="display: none;">
              <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <label class="form-label" style="margin-bottom: 0;">TikTok Caption & Hashtags</label>
                  <span id="ttCaptionCount" style="font-size: 0.72rem; color: var(--text-dim);">0 / 2200</span>
                </div>
                <textarea id="metaTtCaption" class="form-input" rows="5" maxlength="2200" style="resize: vertical; font-size: 0.82rem;" oninput="updateMetaCounters()"></textarea>
                <div style="display: flex; justify-content: flex-end; margin-top: 0.35rem; gap: 0.5rem;">
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="copyFieldValue('metaTtCaption')">📋 Copy Caption</button>
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="regenerateSpecificField('tiktok', 'caption')">🔄 Regenerate</button>
                </div>
              </div>
              <div style="margin-bottom: 1rem;">
                <label class="form-label">Search Keywords</label>
                <input type="text" id="metaTtKeywords" class="form-input" placeholder="keyword1, keyword2">
              </div>
            </div>
          </div>

          <!-- Live Mobile Mockup Preview -->
          <div class="card" style="margin-bottom: 0; display: flex; flex-direction: column; align-items: center;">
            <div style="display: flex; justify-content: space-between; width: 100%; align-items: center; margin-bottom: 1rem;">
              <span style="font-size: 0.85rem; font-weight: 700; color: #fff;">📱 Live Platform Feed Preview</span>
              <span id="mockupPlatformBadge" class="badge" style="background: rgba(225,48,108,0.2); color: #e1306c;">Instagram Reel</span>
            </div>

            <div class="mobile-mockup-frame">
              <div class="mockup-status-bar">
                <span>9:41</span>
                <span>5G 100%</span>
              </div>
              <div class="mockup-screen" id="mockupScreenArea">
                <div style="position: absolute; right: 12px; bottom: 80px; display: flex; flex-direction: column; gap: 14px; align-items: center;">
                  <div style="text-align: center;"><span style="font-size: 1.2rem;">❤️</span><div style="font-size: 0.6rem;">84.2K</div></div>
                  <div style="text-align: center;"><span style="font-size: 1.2rem;">💬</span><div style="font-size: 0.6rem;">1.2K</div></div>
                  <div style="text-align: center;"><span style="font-size: 1.2rem;">↗️</span><div style="font-size: 0.6rem;">Share</div></div>
                  <div style="text-align: center;"><span style="font-size: 1.2rem;">🔖</span></div>
                </div>

                <div style="max-width: 82%;">
                  <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                    <span style="font-size: 0.9rem;">⚡</span>
                    <strong id="mockupHandle" style="font-size: 0.75rem;">@vediohooks</strong>
                    <span style="font-size: 0.65rem; border: 1px solid rgba(255,255,255,0.4); padding: 1px 4px; border-radius: 4px;">Follow</span>
                  </div>
                  <div id="mockupCaption" style="font-size: 0.72rem; line-height: 1.35; max-height: 140px; overflow-y: auto; text-shadow: 0 1px 2px rgba(0,0,0,0.8);">
                    Loading preview...
                  </div>
                  <div id="mockupAudioTag" style="font-size: 0.65rem; color: #ddd; margin-top: 6px; display: flex; align-items: center; gap: 4px;">
                    <span>🎵 Original Audio - VedioHooks AI</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB: AI THUMBNAIL STUDIO -->
      <section id="tab-thumbnail-studio" class="tab-view">
        <div class="card" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, rgba(234, 179, 8, 0.08) 0%, rgba(15, 18, 28, 0.95) 100%); border-color: rgba(234, 179, 8, 0.3);">
          <div class="card-header" style="flex-wrap: wrap; gap: 1rem;">
            <div>
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem;">🖼️</span>
                <div class="card-title" style="font-size: 1.35rem;">AI Thumbnail & Cover Studio</div>
                <span class="badge" style="background: rgba(234, 179, 8, 0.2); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.4);">High-CTR Visuals</span>
              </div>
              <div class="card-subtitle" style="margin-top: 0.35rem;">
                Autonomous frame selection with MediaPipe face centering, safe-zone typography, and multi-format canvas export (9:16 vertical and 16:9 widescreen).
              </div>
            </div>
            <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
              <button class="btn-primary" onclick="generateActiveThumbnails()">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" style="width: 16px; height: 16px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                Generate Thumbnail Variations
              </button>
              <button class="btn-secondary" onclick="loadThumbnailStudio()">🔄 Refresh</button>
              <button class="btn-secondary" id="btnToggleGridCrop" onclick="toggleInstagramGridPreview()">📐 Toggle 1:1 Grid Preview</button>
            </div>
          </div>
        </div>

        <!-- Controls Grid -->
        <div class="grid-4" style="gap: 1rem; margin-bottom: 1.5rem;">
          <div class="card" style="margin-bottom: 0;">
            <label class="form-label">Target Content</label>
            <select id="thumbTargetSelect" class="form-input" onchange="onThumbnailTargetChanged()">
              <option value="">-- Choose Short or Series Episode --</option>
            </select>
          </div>
          <div class="card" style="margin-bottom: 0;">
            <label class="form-label">Platform & Canvas Ratio</label>
            <select id="thumbPlatformSelect" class="form-input" onchange="onThumbnailConfigChanged()">
              <option value="9:16">📱 9:16 Vertical (Shorts, Reels, TikTok - 1080x1920)</option>
              <option value="16:9">🖥️ 16:9 Widescreen (YouTube Long-form - 1280x720)</option>
            </select>
          </div>
          <div class="card" style="margin-bottom: 0;">
            <label class="form-label">Generation Mode</label>
            <select id="thumbModeSelect" class="form-input" onchange="onThumbnailConfigChanged()">
              <option value="auto">MODE 1: AI Auto Composition (Optimal Frame + Text)</option>
              <option value="face_focused">MODE 2: Face-Focused Dramatic Crop (Close-up + Vignette)</option>
              <option value="cinematic">MODE 3: Cinematic Film Grade (Letterbox + Atmosphere)</option>
              <option value="custom">MODE 4: Custom Composition (Manual Text & Timing)</option>
            </select>
          </div>
          <div class="card" style="margin-bottom: 0;">
            <label class="form-label">Custom Headline (Optional)</label>
            <div style="display: flex; gap: 0.4rem;">
              <input type="text" id="thumbCustomHeadline" class="form-input" placeholder="e.g. 99% NEVER MAKE IT">
              <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.3rem 0.5rem;" title="Auto generate headline" onclick="autoSuggestThumbnailHeadline()">💡</button>
            </div>
          </div>
        </div>

        <!-- Candidate Video Frame Scrubber -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <div>
              <span style="font-weight: 700; font-size: 0.85rem; color: #fff;">🎞️ Candidate Video Frames (MediaPipe Face & Sharpness Analyzed)</span>
              <span style="font-size: 0.75rem; color: var(--text-dim); margin-left: 0.5rem;">Click any frame to use as the base canvas</span>
            </div>
            <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;" onclick="extractFreshCandidateFrames()">🔍 Re-scan Video</button>
          </div>
          <div id="thumbFrameScrubber" class="frame-scrubber">
            <div style="color: var(--text-dim); font-size: 0.8rem; padding: 1rem;">Select a video to extract candidate frames.</div>
          </div>
        </div>

        <!-- 3 Variations Gallery -->
        <div style="margin-bottom: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <span style="font-weight: 700; font-size: 1rem; color: #fff;">🎨 Generated Thumbnail Concepts</span>
            <span style="font-size: 0.75rem; color: var(--text-dim);">Select your preferred variation to set as active cover</span>
          </div>

          <div id="thumbVariationsGallery" class="grid-3" style="gap: 1.5rem;">
            <div class="card" style="text-align: center; color: var(--text-dim); padding: 3rem 1rem;">
              Click "Generate Thumbnail Variations" to create 3 high-CTR concepts.
            </div>
          </div>
        </div>
      </section>

      <!-- PUBLISHING READINESS MODAL -->
      <div id="readinessModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 999; align-items: center; justify-content: center; backdrop-filter: blur(8px);">
        <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); max-width: 620px; width: 92%; max-height: 85vh; overflow-y: auto; padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 1.3rem;">🚀</span>
              <h4 style="font-size: 1.15rem; font-weight: 700; margin: 0;">Publishing Readiness Pre-flight Check</h4>
            </div>
            <button class="btn-secondary" style="padding: 0.2rem 0.5rem;" onclick="closeReadinessModal()">✕</button>
          </div>

          <!-- Score Card -->
          <div style="background: rgba(0,0,0,0.3); border-radius: var(--radius-sm); padding: 1rem; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; font-weight: 700;">Overall Readiness Score</div>
              <div id="readinessScoreVal" style="font-size: 1.8rem; font-weight: 800; color: var(--primary);">--%</div>
              <div id="readinessStatusBadge" style="font-size: 0.75rem; color: var(--text-muted);">Evaluating...</div>
            </div>
            <button class="btn-primary" id="btnDownloadExportPkg" onclick="downloadExportPackageForActive()">
              📦 Export Publishing Package (ZIP)
            </button>
          </div>

          <!-- Checklist Items -->
          <div id="readinessChecklistArea" style="display: flex; flex-direction: column; gap: 0.6rem;">
            <!-- Rendered dynamically -->
          </div>

          <div style="display: flex; justify-content: flex-end; margin-top: 0.5rem;">
            <button class="btn-secondary" onclick="closeReadinessModal()">Close</button>
          </div>
        </div>
      </div>

      <!-- TAB 7: PUBLISHING CALENDAR -->
      <section id="tab-calendar" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Instagram Publishing Calendar & Drafts</div>
              <div class="card-subtitle">Review, edit captions, and approve drafts before posting via Meta Graph API</div>
            </div>
            <div style="display: flex; gap: 0.75rem; align-items: center;">
              <button class="btn-primary" style="font-size: 0.82rem; white-space: nowrap;" onclick="autoScheduleWeek()">
                ⚡ Auto-Schedule 7-Day Week
              </button>
              <select id="calendarAccountFilter" class="form-select" style="width: auto;" onchange="loadPublishingQueue()">
                <option value="all">All Accounts</option>
              </select>
            </div>
          </div>
          <div id="publishingQueueContainer">
            <!-- Populated via JS -->
          </div>
        </div>
      </section>

      <!-- TAB 8: INSTAGRAM ACCOUNTS & META API -->
      <section id="tab-instagram" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Official Meta Instagram Graph API (v19.0+) Integration</div>
              <div class="card-subtitle">Safe, compliant direct API posting with zero-scraping guarantee</div>
            </div>
            <span class="badge badge-warning" id="igPublishingStatusBadge">Manual Approval Only</span>
          </div>

          <div class="grid-2">
            <div class="card" style="margin-bottom: 0; background: rgba(0,0,0,0.25);">
              <div style="font-weight: 700; margin-bottom: 0.5rem; color: #a5b4fc;">Compliance & Security Guardrails</div>
              <ul style="font-size: 0.85rem; color: var(--text-muted); padding-left: 1.25rem; line-height: 1.7;">
                <li><b>No Automated Login Scrapers:</b> Only official Meta Graph API v19.0+ endpoints are supported.</li>
                <li><b>Manual Approval Default:</b> Every reel requires human approval before publishing.</li>
                <li><b>Simulation Mode:</b> Test formatting and API payload compliance with zero risk of accidental posts.</li>
                <li><b>Rate Limiting:</b> Strict token bucket ensures Meta API rate limits are never exceeded.</li>
              </ul>
            </div>

            <div class="card" style="margin-bottom: 0; background: rgba(0,0,0,0.25);">
              <div style="font-weight: 700; margin-bottom: 0.5rem; color: #6ee7b7;">Environment Configuration</div>
              <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.7;">
                <div><b>INSTAGRAM_PUBLISHING_ENABLED:</b> <span id="envIgPublishing">False</span></div>
                <div><b>INSTAGRAM_ACCOUNT_ID:</b> <span id="envIgAccount" style="font-family: monospace;">Configured via .env</span></div>
                <div><b>ACCESS_TOKEN_STATUS:</b> <span id="envIgToken">Ready for OAuth credentials</span></div>
              </div>
            </div>
          </div>

          <!-- Instagram Insights & Telemetry Sync Section -->
          <div class="card" style="margin-top: 1.25rem; background: rgba(0,0,0,0.25);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
              <div>
                <div style="font-weight: 700; color: #f43f5e; font-size: 1.05rem;">Meta Graph API Insights &amp; Engagement Telemetry</div>
                <div style="font-size: 0.78rem; color: var(--text-muted);">Real-time engagement feedback loop across views, reach, saves &amp; completion rate</div>
              </div>
              <button class="btn-secondary" style="font-size: 0.8rem; border-color: rgba(244, 63, 94, 0.4); color: #f43f5e;" onclick="loadInstagramInsights()">
                🔄 Sync Insights Telemetry
              </button>
            </div>
            <div class="grid-4" style="margin-bottom: 1rem;">
              <div class="metric-card">
                <span class="metric-label">Tracked Posts</span>
                <span class="metric-value" id="igMetricPosts">0</span>
                <span class="metric-detail">Verified reels with metrics</span>
              </div>
              <div class="metric-card">
                <span class="metric-label">Total Views / Impressions</span>
                <span class="metric-value" id="igMetricViews" style="color: #60a5fa;">0</span>
                <span class="metric-detail">Combined reel impressions</span>
              </div>
              <div class="metric-card">
                <span class="metric-label">Total Interactions</span>
                <span class="metric-value" id="igMetricInteractions" style="color: #f43f5e;">0</span>
                <span class="metric-detail">Likes, comments &amp; shares</span>
              </div>
              <div class="metric-card">
                <span class="metric-label">Avg Retention Rate</span>
                <span class="metric-value" id="igMetricRetention" style="color: #34d399;">--%</span>
                <span class="metric-detail">Audience completion rate</span>
              </div>
            </div>
            <div id="igInsightsTableContainer" style="font-size: 0.82rem; color: var(--text-muted);">
              <!-- Recent Insights Log -->
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 9: ANALYTICS -->
      <section id="tab-analytics" class="tab-view">
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-header">
            <div>
              <div class="card-title">Real-Time Operational Analytics & Virality Telemetry</div>
              <div class="card-subtitle">Live database performance metrics calculated across multi-account vertical production</div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <button class="btn-primary" style="font-size: 0.82rem; background: linear-gradient(135deg, #6366f1, #10b981);" onclick="downloadExecutiveReport()">
                📄 Export Weekly Report (.md)
              </button>
              <button class="btn-secondary" style="font-size: 0.82rem;" onclick="loadAnalytics()">🔄 Refresh Analytics</button>
            </div>
          </div>
        </div>

        <div class="grid-3" style="margin-bottom: 1.5rem;">
          <div class="card" style="margin-bottom: 0;">
            <div class="card-title" style="margin-bottom: 0.35rem;">Average Virality Score</div>
            <div class="card-subtitle" style="margin-bottom: 0.75rem;">Calculated across rendered shorts</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #34d399;" id="analyticsAvgVirality">--</div>
            <div style="font-size: 0.8rem; color: var(--text-dim); margin-top: 0.5rem;" id="analyticsScoreRange">Range: -- to --</div>
          </div>
          <div class="card" style="margin-bottom: 0;">
            <div class="card-title" style="margin-bottom: 0.35rem;">Audience Retention Benchmark</div>
            <div class="card-subtitle" style="margin-bottom: 0.75rem;">Predicted completion rate benchmark</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #818cf8;" id="analyticsRetention">--%</div>
            <div style="font-size: 0.8rem; color: var(--text-dim); margin-top: 0.5rem;">Based on speech pacing & hook power</div>
          </div>
          <div class="card" style="margin-bottom: 0;">
            <div class="card-title" style="margin-bottom: 0.35rem;">Production Output Cadence</div>
            <div class="card-subtitle" style="margin-bottom: 0.75rem;">Total rendered vs daily network target</div>
            <div style="font-size: 2.2rem; font-weight: 800; color: #fbbf24;" id="analyticsCadence">-- <span style="font-size: 1rem; color: var(--text-muted);">Shorts</span></div>
            <div style="font-size: 0.8rem; color: var(--text-dim); margin-top: 0.5rem;" id="analyticsDailyTarget">Daily Target: --</div>
          </div>
        </div>

        <div class="grid-2" style="margin-bottom: 1.5rem;">
          <!-- Virality Tier Breakdown -->
          <div class="card">
            <div class="card-title" style="margin-bottom: 1rem;">Virality Scoring Tiers</div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.25rem;">
                  <span>🔥 Elite Virality (90 - 100)</span>
                  <span id="tierEliteCount" style="font-weight: 700; color: #34d399;">0</span>
                </div>
                <div class="progress-bar-bg"><div id="tierEliteBar" class="progress-bar-fill" style="width: 0%; background: #34d399;"></div></div>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.25rem;">
                  <span>⚡ High Virality (80 - 89)</span>
                  <span id="tierHighCount" style="font-weight: 700; color: #6366f1;">0</span>
                </div>
                <div class="progress-bar-bg"><div id="tierHighBar" class="progress-bar-fill" style="width: 0%; background: #6366f1;"></div></div>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.25rem;">
                  <span>📊 Standard Virality (&lt; 80)</span>
                  <span id="tierStandardCount" style="font-weight: 700; color: #94a3b8;">0</span>
                </div>
                <div class="progress-bar-bg"><div id="tierStandardBar" class="progress-bar-fill" style="width: 0%; background: #94a3b8;"></div></div>
              </div>
            </div>
          </div>

          <!-- Publishing Pipeline Status -->
          <div class="card">
            <div class="card-title" style="margin-bottom: 1rem;">Publishing Approval Funnel</div>
            <div class="grid-2" style="gap: 0.75rem;">
              <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.75rem;">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Drafts Pending Review</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #fbbf24;" id="funnelDrafts">0</div>
              </div>
              <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.75rem;">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Scheduled in Calendar</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #60a5fa;" id="funnelScheduled">0</div>
              </div>
              <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.75rem;">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Approved for Posting</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #34d399;" id="funnelApproved">0</div>
              </div>
              <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.75rem;">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Published via Meta API</div>
                <div style="font-size: 1.5rem; font-weight: 800; color: #a78bfa;" id="funnelPublished">0</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Multi-Account Production Breakdown Table -->
        <div class="card">
          <div class="card-title" style="margin-bottom: 1rem;">Niche Production Distribution</div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Niche Account</th>
                  <th>Instagram Handle</th>
                  <th>Shorts Rendered</th>
                  <th>Share of Output</th>
                </tr>
              </thead>
              <tbody id="analyticsNicheTableBody">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- TAB 10: AUTOMATION CENTRE -->
      <section id="tab-automation" class="tab-view">
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">24/7 Autonomous Scheduler & Pipeline Controls</div>
              <div class="card-subtitle">Continuous background processing with automatic failure recovery</div>
            </div>
            <div style="display: flex; gap: 0.5rem;">
              <button class="btn-secondary" onclick="recoverInterruptedJobs()">Recover Interrupted Jobs</button>
              <button class="btn-secondary" onclick="toggleAutomationWorker()">Toggle Autonomous Worker</button>
            </div>
          </div>

          <div class="grid-3">
            <div class="card" style="margin-bottom: 0; background: rgba(0,0,0,0.25);">
              <div class="metric-label">Worker Status</div>
              <div class="metric-value" style="font-size: 1.4rem;" id="autoWorkerStatus">RUNNING</div>
              <div class="metric-detail" id="autoWorkerDetail">Autonomous polling enabled</div>
            </div>
            <div class="card" style="margin-bottom: 0; background: rgba(0,0,0,0.25);">
              <div class="metric-label">Emergency Stop Master</div>
              <div class="metric-value" style="font-size: 1.4rem;" id="autoEmergencyStatus">DISENGAGED</div>
              <div class="metric-detail">All pipelines active</div>
            </div>
            <div class="card" style="margin-bottom: 0; background: rgba(0,0,0,0.25);">
              <div class="metric-label">Concurrent Jobs</div>
              <div class="metric-value" style="font-size: 1.4rem;" id="autoWorkersActive">0 / 2</div>
              <div class="metric-detail">SQLite persistent queue</div>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 11: SYSTEM HEALTH -->
      <section id="tab-health" class="tab-view">
        <div class="grid-4">
          <div class="metric-card">
            <span class="metric-label">CPU Utilization</span>
            <span class="metric-value" id="healthCpu">0%</span>
            <span class="metric-detail" id="healthCpuThreads">Threads active</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">RAM Usage</span>
            <span class="metric-value" id="healthRam">0%</span>
            <span class="metric-detail" id="healthRamDetail">0 GB / 0 GB</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Disk Storage</span>
            <span class="metric-value" id="healthDisk">0 GB</span>
            <span class="metric-detail">Free disk space</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">FFmpeg Status</span>
            <span class="metric-value" style="color: #34d399;" id="healthFfmpeg">READY</span>
            <span class="metric-detail">Hardware / SIMD active</span>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Persistent Database Jobs Telemetry</div>
              <div class="card-subtitle">SQLite ACID state machine with retry and cancellation controls</div>
            </div>
            <button class="btn-secondary" onclick="loadTelemetry()">Refresh Telemetry</button>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Source / Title</th>
                  <th>Account</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Retries</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="telemetryJobsTableBody">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- TAB 12: SETTINGS -->
      <section id="tab-settings" class="tab-view">
        <div class="card">
          <div class="card-title" style="margin-bottom: 0.5rem;">Storage & System Maintenance</div>
          <div class="card-subtitle" style="margin-bottom: 1.25rem;">Clean temporary audio and video processing artifacts to preserve disk space</div>
          <div style="display: flex; gap: 0.75rem;">
            <button class="btn-secondary" onclick="runStorageCleanup()">Run Storage Cleanup</button>
            <button class="btn-secondary" onclick="triggerDatabaseBackup()">Create Database Backup Now</button>
          </div>
        </div>

        <div class="card">
          <div class="card-title" style="margin-bottom: 0.5rem;">VedioHooks AI Environment & Engine</div>
          <div class="card-subtitle" style="margin-bottom: 1rem;">Version 3.0.0 Commercial SaaS Edition</div>
          <div style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.8;">
            <div>• <b>Transcription:</b> Faster-Whisper (CTranslate2 Local INT8/FP16)</div>
            <div>• <b>Vision Tracking:</b> Google MediaPipe Face Detection + Dynamic 9:16 Smooth Tracking</div>
            <div>• <b>Subtitles:</b> ASS Dynamic Karaoke Styling with Hormozi Word Highlights</div>
            <div>• <b>Database:</b> SQLite 3 with WAL Mode and Multi-Account Isolation</div>
            <div>• <b>Publishing:</b> Meta Instagram Graph API v19.0 Official Direct Integration</div>
          </div>
        </div>
      </section>

    </div>
  </main>

  <!-- Create Account Modal -->
  <div id="modalAccount" class="modal-overlay">
    <div class="modal-box">
      <div class="modal-header">
        <div style="font-size: 1.2rem; font-weight: 700;">Add New Instagram Account</div>
        <button class="modal-close" onclick="closeModal('modalAccount')">✕</button>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Account Name</label>
          <input type="text" id="accName" class="form-input" placeholder="e.g. Stoic Motivation">
        </div>
        <div class="form-group">
          <label class="form-label">Handle</label>
          <input type="text" id="accHandle" class="form-input" placeholder="e.g. @stoic.mindset">
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Niche Category</label>
          <select id="accNiche" class="form-select">
            <option value="Motivation">Motivation & Self-Improvement</option>
            <option value="Cricket">Cricket News & Stories</option>
            <option value="AI & Study">AI Tools & Student Study</option>
            <option value="Gym & Fitness">Gym Training & Hypertrophy</option>
            <option value="Common / General">Curiosity & History Trivia</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Brand Color Hex</label>
          <input type="color" id="accBrandColor" class="form-input" value="#6366f1" style="height: 42px;">
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Hashtag Strategy</label>
        <input type="text" id="accHashtags" class="form-input" value="#shorts #reels #viral">
      </div>

      <div class="form-group">
        <label class="form-label">Caption Template Formula</label>
        <textarea id="accCaptionTemplate" class="form-textarea" rows="3">🔥 {hook}&#10;&#10;💡 {punchline}&#10;&#10;{hashtags}</textarea>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem;">
        <button class="btn-secondary" onclick="closeModal('modalAccount')">Cancel</button>
        <button class="btn-primary" onclick="submitCreateAccount()">Save Account</button>
      </div>
    </div>
  </div>

  <!-- Create Source Modal -->
  <div id="modalSource" class="modal-overlay">
    <div class="modal-box">
      <div class="modal-header">
        <div style="font-size: 1.2rem; font-weight: 700;">Add Content Discovery Source</div>
        <button class="modal-close" onclick="closeModal('modalSource')">✕</button>
      </div>

      <div class="form-group">
        <label class="form-label">Select Account</label>
        <select id="sourceAccountSelect" class="form-select"></select>
      </div>

      <div class="form-group">
        <label class="form-label">Source Title / Channel Name</label>
        <input type="text" id="sourceTitle" class="form-input" placeholder="e.g. Masterclass Speech Series">
      </div>

      <div class="form-group">
        <label class="form-label">Source URL or Channel Link</label>
        <input type="text" id="sourceUrl" class="form-input" placeholder="https://youtube.com/...">
      </div>

      <div class="form-group">
        <label class="form-label">Attribution & Creator Credits</label>
        <input type="text" id="sourceAttribution" class="form-input" placeholder="e.g. Original speaker name, credit handle">
      </div>

      <div class="form-group">
        <label class="form-label">Factual Verification & Compliance Notes</label>
        <textarea id="sourceVerification" class="form-textarea" rows="2" placeholder="e.g. Verified statistics, copyright clearance, medical form safety disclaimer..."></textarea>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem;">
        <button class="btn-secondary" onclick="closeModal('modalSource')">Cancel</button>
        <button class="btn-primary" onclick="submitCreateSource()">Register Source</button>
      </div>
    </div>
  </div>

  <!-- Modal: 3-Cover High-CTR Studio -->
  <div id="modalCovers" class="modal-overlay">
    <div class="modal-box" style="max-width: 850px; width: 92%;">
      <div class="modal-header">
        <div>
          <div style="font-size: 1.2rem; font-weight: 700; color: #f59e0b;">🖼️ High-CTR 9:16 Cover Thumbnail Studio</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">3 distinct psychological cover thumbnail styles formatted for 9:16 vertical feeds</div>
        </div>
        <button class="modal-close" onclick="closeModal('modalCovers')">✕</button>
      </div>

      <div id="coversGridContainer" class="grid-3" style="margin-top: 1rem; gap: 1rem;">
        <div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem; color: #f59e0b;">
          Rendering 3 high-CTR cover styles with FFmpeg...
        </div>
      </div>
    </div>
  </div>

  <!-- Modal: Multi-Platform Export (Reels + Shorts + TikTok) -->
  <div id="modalExport" class="modal-overlay">
    <div class="modal-box" style="max-width: 880px; width: 92%;">
      <div class="modal-header">
        <div>
          <div style="font-size: 1.2rem; font-weight: 700; color: #818cf8;">🌐 Multi-Platform Algorithm Copy Studio</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">Tailored copy, SEO tags & pinned comment prompts for Instagram Reels, YouTube Shorts & TikTok</div>
        </div>
        <button class="modal-close" onclick="closeModal('modalExport')">✕</button>
      </div>

      <div id="exportTabsContainer" class="grid-3" style="margin-top: 1rem; gap: 1rem;">
        <!-- Populated via JS -->
      </div>
  <!-- Modal: Top Hook Header Banner Studio -->
  <div id="modalHookBanner" class="modal-overlay">
    <div class="modal-box" style="max-width: 620px; width: 92%;">
      <div class="modal-header">
        <div>
          <div style="font-size: 1.2rem; font-weight: 700; color: #10b981;">🏷️ Top Hook Header Banner Studio</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">Burn a high-contrast attention hook pill in the top 15% safe-zone to stop the scroll</div>
        </div>
        <button class="modal-close" onclick="closeModal('modalHookBanner')">✕</button>
      </div>

      <input type="hidden" id="modalHookBannerRenderId">
      <input type="hidden" id="modalHookBannerVideoPath">

      <div class="form-group" style="margin-bottom: 1rem;">
        <label class="form-label">Banner Headline Text (All-Caps):</label>
        <input type="text" id="modalHookBannerText" class="form-input" placeholder="e.g. THE 1 BRUTAL TRUTH ABOUT SUCCESS">
      </div>

      <div class="form-row" style="margin-bottom: 1rem;">
        <div class="form-group">
          <label class="form-label">Theme Styling Preset:</label>
          <select id="modalHookBannerTheme" class="form-select">
            <option value="hormozi_yellow">Hormozi Yellow (Neon Yellow / Charcoal Pill)</option>
            <option value="beast_red">MrBeast Red (White / Deep Crimson Pill)</option>
            <option value="cyber_cyan">Cyber Cyan (Electric Cyan / Slate Glass)</option>
            <option value="emerald_growth">Viral Emerald (White / Deep Green Badge)</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Display Duration:</label>
          <select id="modalHookBannerDuration" class="form-select">
            <option value="2.5">2.5 seconds (Fast Hook)</option>
            <option value="3.5" selected>3.5 seconds (Recommended)</option>
            <option value="5.0">5.0 seconds (Extended Hook)</option>
            <option value="60.0">Full Duration (Entire Video)</option>
          </select>
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem;">
        <button class="btn-secondary" onclick="closeModal('modalHookBanner')">Cancel</button>
        <button class="btn-primary" style="background: linear-gradient(135deg, #10b981, #059669);" onclick="submitHookBannerBurn()">
          🚀 Burn Top Hook Banner
        </button>
      </div>
    </div>
  </div>

  <!-- Toast Notification Container -->
  <div id="toastContainer"></div>

  <!-- Dashboard JavaScript Logic -->
  <script>
    let currentGlobalAccount = 'all';
    let accountsCache = [];
    let activeJobId = null;
    let pollInterval = null;

    // Toast Notification Utility
    function showToast(msg) {
      const container = document.getElementById('toastContainer');
      const t = document.createElement('div');
      t.className = 'toast';
      t.innerText = msg;
      container.appendChild(t);
      setTimeout(() => { t.remove(); }, 3500);
    }

    // Modal Utilities
    function openModal(id) { const el = document.getElementById(id); if (el) el.classList.add('active'); }
    function closeModal(id) { const el = document.getElementById(id); if (el) el.classList.remove('active'); }
    function openCreateAccountModal() { document.getElementById('modalAccount').classList.add('active'); }
    function openCreateSourceModal() {
      populateSourceAccountDropdown();
      document.getElementById('modalSource').classList.add('active');
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .split('&').join('&amp;')
        .split('<').join('&lt;')
        .split('>').join('&gt;')
        .split('"').join('&quot;')
        .split("'").join('&#039;');
    }

    function setMobileNav(open = !document.body.classList.contains('sidebar-open')) {
      document.body.classList.toggle('sidebar-open', open);
      const toggle = document.getElementById('menuToggle');
      const mobile = window.matchMedia('(max-width: 1100px)').matches;
      const sidebar = document.querySelector('.sidebar');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
      sidebar.setAttribute('aria-hidden', String(mobile && !open));
      if (mobile && open) sidebar.querySelector('.nav-item')?.focus();
      else if (mobile && toggle && sidebar.contains(document.activeElement)) toggle.focus();
    }

    // Tab Navigation
    function switchTab(tabId, updateHistory = true) {
      const targetView = document.getElementById(`tab-${tabId}`);
      if (!targetView) return;

      document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(el => el.removeAttribute('aria-current'));

      targetView.classList.add('active');

      const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
      navItems.forEach(item => {
        if (item.getAttribute('onclick') && item.getAttribute('onclick').includes(tabId)) {
          item.classList.add('active');
          item.setAttribute('aria-current', 'page');
        }
      });

      const pageContent = {
        overview: ['Your content, in motion.', 'Turn long-form video into standout short-form content, all from one workspace.'],
        factory: ['Video factory', 'Bring in a video and shape it into polished, platform-ready shorts.'],
        library: ['Your video library', 'Review, refine, and prepare your finished vertical videos for publishing.'],
        dubbing: ['AI dubbing lab', 'Create localized voice tracks and manage dubbed versions of your shorts.'],
        'series-studio': ['Series studio', 'Transform long-form videos into interconnected, cliffhanger-driven short episode series.'],
        'metadata-studio': ['AI metadata studio', 'Generate and fine-tune SEO-optimized titles, descriptions, and captions for YouTube, Instagram, and TikTok.'],
        'thumbnail-studio': ['AI thumbnail studio', 'Design high-CTR covers, face-focused frames, and platform previews for 9:16 vertical and 16:9 videos.'],
        accounts: ['Account manager', 'Keep each channel’s brand, schedule, and publishing workflow organized.'],
        'ai-director': ['AI content director', 'Build a practical content blueprint around your niche and audience.'],
        sources: ['Content discovery', 'Organize the channels, playlists, and ideas that feed your content pipeline.'],
        calendar: ['Publishing calendar', 'Review drafts and coordinate what is ready to publish across accounts.'],
        instagram: ['Instagram integration', 'Manage your official Instagram publishing connection and account insights.'],
        analytics: ['Performance analytics', 'Understand how your clips and account workflows are performing.'],
        automation: ['Automation centre', 'Monitor the background workflows that keep your content moving.'],
        health: ['System health', 'Check the services and resources powering your video workspace.'],
        settings: ['Workspace settings', 'Manage system preferences, maintenance, and configuration.']
      };
      const [title, description] = pageContent[tabId];
      document.getElementById('pageTitle').textContent = title;
      document.getElementById('pageDescription').textContent = description;
      document.title = `${title} | VedioHooks AI`;
      document.querySelector('meta[name="description"]').setAttribute('content', description);
      targetView.setAttribute('aria-hidden', 'false');
      document.querySelectorAll('.tab-view:not(.active)').forEach(view => view.setAttribute('aria-hidden', 'true'));
      setMobileNav(false);

      if (updateHistory && window.location.hash !== `#${tabId}`) {
        window.history.pushState({ tabId }, '', `#${tabId}`);
      }

      // Tab specific refresh
      if (tabId === 'overview') loadOverview();
      else if (tabId === 'accounts') loadAccounts();
      else if (tabId === 'sources') loadSources();
      else if (tabId === 'ai-director') loadAIDirector();
      else if (tabId === 'factory') loadFactory();
      else if (tabId === 'library') loadLibraryShorts();
      else if (tabId === 'dubbing') loadDubbingLibrary();
      else if (tabId === 'series-studio') loadSeriesStudio();
      else if (tabId === 'metadata-studio') loadMetadataStudio();
      else if (tabId === 'thumbnail-studio') loadThumbnailStudio();
      else if (tabId === 'calendar') loadPublishingQueue();
      else if (tabId === 'analytics') loadAnalytics();
      else if (tabId === 'instagram') loadInstagramInsights();
      else if (tabId === 'health') loadTelemetry();
    }

    // Global Account Switcher
    async function loadAccountsList() {
      try {
        const res = await fetch('/api/accounts');
        const data = await res.json();
        accountsCache = data.accounts || [];

        const select = document.getElementById('globalAccountSelect');
        const prev = select.value;
        select.innerHTML = '<option value="all">🌐 All Accounts (Global View)</option>' +
          accountsCache.map(a => `<option value="${a.id}">${a.avatar_emoji || '⚡'} ${a.name} (${a.niche})</option>`).join('');

        if (prev && [...select.options].some(o => o.value === prev)) {
          select.value = prev;
        }

        populateFactoryAccountDropdown();
        populateDirectorAccountDropdown();
      } catch (e) {
        console.error('Failed to load accounts list', e);
      }
    }

    function onGlobalAccountChange(val) {
      currentGlobalAccount = val;
      const badge = document.getElementById('activeNicheBadge');
      if (val === 'all') {
        badge.innerText = 'Global Pipeline';
        badge.style.borderColor = 'rgba(99,102,241,0.3)';
      } else {
        const acc = accountsCache.find(a => a.id === val);
        if (acc) {
          badge.innerText = `${acc.niche} (${acc.handle})`;
          badge.style.borderColor = acc.brand_color || '#6366f1';
          const factoryAcc = document.getElementById('factoryAccountSelect');
          if (factoryAcc && factoryAcc.value !== val) {
            factoryAcc.value = val;
            onFactoryAccountChange(val);
          }
        }
      }
      loadOverview();
      loadLibraryShorts();
      loadPublishingQueue();
      showToast(`Switched view to ${badge.innerText}`);
    }

    function onFactoryAccountChange(accId) {
      const acc = accountsCache.find(a => a.id === accId);
      if (!acc) return;
      const themeSelect = document.getElementById('factoryThemeSelect');
      const nicheThemeMap = {
        'Motivation': 'hormozi_yellow',
        'Cricket': 'hormozi_green',
        'AI & Study': 'cyber_cyan',
        'Gym & Fitness': 'beast_red',
        'Common / General': 'fire_orange'
      };
      if (themeSelect && nicheThemeMap[acc.niche]) {
        themeSelect.value = nicheThemeMap[acc.niche];
      }
      const globalSel = document.getElementById('globalAccountSelect');
      if (globalSel && globalSel.value !== accId) {
        globalSel.value = accId;
        const badge = document.getElementById('activeNicheBadge');
        if (badge) {
          badge.innerText = `${acc.niche} (${acc.handle})`;
          badge.style.borderColor = acc.brand_color || '#6366f1';
        }
      }
    }

    // Emergency Stop Master Controls
    async function checkAutomationStatus() {
      try {
        const res = await fetch('/api/automation/status');
        const data = await res.json();

        const btn = document.getElementById('btnEmergencyStop');
        const dot = document.getElementById('emergencyDot');
        const text = document.getElementById('emergencyBtnText');
        const pulse = document.getElementById('sidebarPulse');
        const sideText = document.getElementById('sidebarStatusText');
        const sideWorkers = document.getElementById('sidebarWorkerCount');

        if (data.emergency_stop) {
          btn.classList.add('active');
          dot.style.display = 'inline-block';
          text.innerText = 'EMERGENCY STOPPED';
          pulse.classList.add('stopped');
          sideText.innerText = 'EMERGENCY STOPPED';
        } else {
          btn.classList.remove('active');
          dot.style.display = 'none';
          text.innerText = 'EMERGENCY STOP';
          pulse.classList.remove('stopped');
          sideText.innerText = data.scheduler_running ? '24/7 Engine Active' : 'Scheduler Paused';
        }

        sideWorkers.innerText = `${data.active_workers} / ${data.max_concurrent_workers}`;
        document.getElementById('navJobsBadge').innerText = data.active_workers;

        const autoStatus = document.getElementById('autoWorkerStatus');
        if (autoStatus) {
          autoStatus.innerText = data.scheduler_running ? 'RUNNING' : 'PAUSED';
          document.getElementById('autoEmergencyStatus').innerText = data.emergency_stop ? 'ENGAGED' : 'DISENGAGED';
          document.getElementById('autoWorkersActive').innerText = `${data.active_workers} / ${data.max_concurrent_workers}`;
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function toggleEmergencyStop() {
      const res = await fetch('/api/automation/emergency-stop', { method: 'POST' });
      const data = await res.json();
      showToast(data.message);
      checkAutomationStatus();
    }

    async function toggleAutomationWorker() {
      const res = await fetch('/api/automation/toggle', { method: 'POST' });
      const data = await res.json();
      showToast(data.global_automation ? '24/7 Scheduler Resumed' : '24/7 Scheduler Paused');
      checkAutomationStatus();
    }

    async function recoverInterruptedJobs() {
      const res = await fetch('/api/automation/recover', { method: 'POST' });
      const data = await res.json();
      showToast(data.message);
      loadTelemetry();
    }

    async function runStorageCleanup() {
      const res = await fetch('/api/storage/cleanup', { method: 'POST' });
      const data = await res.json();
      showToast(data.message);
    }

    async function triggerDatabaseBackup() {
      showToast('Creating database snapshot...');
      try {
        const res = await fetch('/api/database/backup', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || 'Database backup created');
      } catch (e) {
        showToast(`Backup error: ${e}`);
      }
    }

    // Populate Helper Dropdowns
    function populateFactoryAccountDropdown() {
      const sel = document.getElementById('factoryAccountSelect');
      if (sel) {
        sel.innerHTML = accountsCache.map(a => `<option value="${a.id}">${a.avatar_emoji || '⚡'} ${a.name} (${a.niche})</option>`).join('');
        if (currentGlobalAccount && currentGlobalAccount !== 'all') {
          sel.value = currentGlobalAccount;
        }
        onFactoryAccountChange(sel.value);
      }
    }

    function populateDirectorAccountDropdown() {
      const sel = document.getElementById('directorAccountSelect');
      if (sel) {
        sel.innerHTML = accountsCache.map(a => `<option value="${a.id}">${a.avatar_emoji || '⚡'} ${a.name} (${a.niche})</option>`).join('');
      }
    }

    function populateSourceAccountDropdown() {
      const sel = document.getElementById('sourceAccountSelect');
      if (sel) {
        sel.innerHTML = accountsCache.map(a => `<option value="${a.id}">${a.avatar_emoji || '⚡'} ${a.name}</option>`).join('');
      }
    }

    // --- Overview Tab Logic ---
    async function loadOverview() {
      await loadAccountsList();
      document.getElementById('kpiAccounts').innerText = accountsCache.length;

      const grid = document.getElementById('overviewAccountsGrid');
      grid.innerHTML = accountsCache.map(a => `
        <div class="card" style="margin-bottom: 0; border-top: 3px solid ${a.brand_color || '#6366f1'};">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <div style="font-weight: 700; font-size: 1.05rem;">${a.avatar_emoji || '⚡'} ${a.name}</div>
            <span class="badge ${a.status === 'active' ? 'badge-success' : 'badge-warning'}">${a.status}</span>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.75rem;">${a.handle} • <b>${a.niche}</b></div>
          <div style="font-size: 0.82rem; color: var(--text-dim); margin-bottom: 0.75rem;">
            Target: <b>${a.daily_target} shorts/day</b> • Subtitles: <b>${a.default_theme}</b>
          </div>
          <div style="display: flex; gap: 0.5rem;">
            <button class="btn-secondary" style="flex: 1; font-size: 0.78rem; padding: 0.35rem;" onclick="filterAccount('${a.id}')">Select</button>
            <button class="btn-secondary" style="font-size: 0.78rem; padding: 0.35rem;" onclick="toggleAccount('${a.id}')">${a.status === 'active' ? 'Pause' : 'Resume'}</button>
          </div>
        </div>
      `).join('');

      // Load Recent Renders into Showcase
      try {
        const rendersRes = await fetch(`/api/renders?limit=4${currentGlobalAccount !== 'all' ? `&account_id=${currentGlobalAccount}` : ''}`);
        const rendersData = await rendersRes.json();
        const shortsGrid = document.getElementById('overviewShortsGrid');
        const renders = rendersData.renders || [];

        // Dynamic KPI updates from live system telemetry
        const statsRes = await fetch(`/api/system/stats${currentGlobalAccount !== 'all' ? `?account_id=${currentGlobalAccount}` : ''}`);
        const statsData = await statsRes.json();
        if (statsData.stats) {
          const s = statsData.stats;
          document.getElementById('kpiJobs').innerText = (s.jobs_queued || 0) + (s.jobs_downloading || 0) + (s.jobs_transcribing || 0) + (s.jobs_analyzing || 0);
          document.getElementById('kpiRenders').innerText = s.total_shorts_rendered || renders.length;
          document.getElementById('kpiDrafts').innerText = s.publishing_draft || 0;
          const draftsBadge = document.getElementById('navDraftsBadge');
          if (draftsBadge) draftsBadge.innerText = s.publishing_draft || 0;
        }

        if (renders.length === 0) {
          shortsGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 2rem;">No rendered shorts found for current filter.</div>`;
        } else {
          shortsGrid.innerHTML = renders.map(r => `
            <div class="short-card">
              <div class="short-video-wrapper">
                <video src="/api/media/output/${r.video_path.split('/').pop().split('\\\\').pop()}" controls playsinline preload="metadata"></video>
              </div>
              <div class="short-content">
                <div style="font-weight: 700; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${r.title || 'Highlight'}</div>
                <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted);">
                  <span>Score: <b style="color: #34d399;">${r.virality_score}</b></span>
                  <span>${r.crop_mode}</span>
                </div>
                <button class="btn-secondary" style="font-size: 0.8rem; width: 100%;" onclick="sendRenderToDraft(${r.id})">Send to Instagram Draft</button>
              </div>
            </div>
          `).join('');
        }
      } catch (e) {
        console.error(e);
      }
    }

    function filterAccount(id) {
      document.getElementById('globalAccountSelect').value = id;
      onGlobalAccountChange(id);
    }

    async function toggleAccount(id) {
      await fetch(`/api/accounts/${id}/toggle`, { method: 'POST' });
      showToast('Account status updated');
      loadAccountsList();
      loadOverview();
    }

    // --- Accounts Tab Logic ---
    async function loadAccounts() {
      await loadAccountsList();
      const tbody = document.getElementById('accountsTableBody');
      tbody.innerHTML = accountsCache.map(a => `
        <tr>
          <td>
            <div style="font-weight: 700;">${a.avatar_emoji || '⚡'} ${a.name}</div>
            <div style="font-size: 0.78rem; color: var(--text-dim);">${a.handle}</div>
          </td>
          <td><b>${a.niche}</b></td>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 0.35rem;">
              <span style="width: 12px; height: 12px; border-radius: 50%; background: ${a.brand_color};"></span>
              ${a.brand_color}
            </span>
          </td>
          <td>${a.posting_schedule}</td>
          <td>${a.default_theme}</td>
          <td><span class="badge ${a.status === 'active' ? 'badge-success' : 'badge-warning'}">${a.status}</span></td>
          <td>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="toggleAccount('${a.id}')">${a.status === 'active' ? 'Pause' : 'Resume'}</button>
              <button class="btn-danger" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="deleteAccount('${a.id}')">Delete</button>
            </div>
          </td>
        </tr>
      `).join('');
    }

    async function submitCreateAccount() {
      const name = document.getElementById('accName').value;
      if (!name) { alert('Account name is required'); return; }
      const handle = document.getElementById('accHandle').value;
      const niche = document.getElementById('accNiche').value;
      const brand_color = document.getElementById('accBrandColor').value;
      const hashtag_strategy = document.getElementById('accHashtags').value;
      const caption_template = document.getElementById('accCaptionTemplate').value;

      await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, handle, niche, brand_color, hashtag_strategy, caption_template })
      });

      closeModal('modalAccount');
      showToast(`Account "${name}" created successfully`);
      loadAccounts();
    }

    async function deleteAccount(id) {
      if (!confirm('Are you sure you want to delete this account and all associated jobs & drafts?')) return;
      await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
      showToast('Account deleted');
      loadAccounts();
    }

    // --- Content Discovery Sources Logic ---
    async function loadSources() {
      try {
        const url = `/api/sources${currentGlobalAccount !== 'all' ? `?account_id=${currentGlobalAccount}` : ''}`;
        const res = await fetch(url);
        const data = await res.json();
        const tbody = document.getElementById('sourcesTableBody');
        const sources = data.sources || [];

        if (sources.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">No content sources registered yet.</td></tr>';
          return;
        }

        tbody.innerHTML = sources.map(s => `
          <tr>
            <td>
              <div style="font-weight: 700;">${s.title}</div>
              <div style="font-size: 0.78rem; color: #a5b4fc;">${s.source_url_or_path}</div>
            </td>
            <td><b>${s.account_name || s.account_id}</b></td>
            <td><span class="badge badge-primary">${s.source_type}</span></td>
            <td>${s.attribution || 'Attributed to creator'}</td>
            <td style="font-size: 0.8rem; color: var(--text-muted);">${s.verification_notes || 'Standard check'}</td>
            <td>
              <div style="display: flex; gap: 0.35rem;">
                <button class="btn-primary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="processSourceDirectly('${s.source_url_or_path}', '${s.account_id}')">Process in Factory</button>
                <button class="btn-danger" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="deleteSource('${s.id}')">Delete</button>
              </div>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function submitCreateSource() {
      const account_id = document.getElementById('sourceAccountSelect').value;
      const title = document.getElementById('sourceTitle').value;
      const source_url_or_path = document.getElementById('sourceUrl').value;
      const attribution = document.getElementById('sourceAttribution').value;
      const verification_notes = document.getElementById('sourceVerification').value;

      if (!title || !source_url_or_path) {
        alert('Title and URL are required');
        return;
      }

      await fetch('/api/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id, title, source_url_or_path, attribution, verification_notes })
      });

      closeModal('modalSource');
      showToast(`Source "${title}" added`);
      loadSources();
    }

    async function deleteSource(id) {
      await fetch(`/api/sources/${id}`, { method: 'DELETE' });
      showToast('Source deleted');
      loadSources();
    }

    function processSourceDirectly(url, accountId) {
      switchTab('factory');
      document.getElementById('urlInput').value = url;
      document.getElementById('factoryAccountSelect').value = accountId;
      submitUrlJob();
    }

    // --- AI Content Director Tab Logic ---
    async function loadAIDirector() {
      populateDirectorAccountDropdown();
      try {
        const res = await fetch(`/api/ai-plans${currentGlobalAccount !== 'all' ? `?account_id=${currentGlobalAccount}` : ''}`);
        const data = await res.json();
        const tbody = document.getElementById('plansTableBody');
        const plans = data.plans || [];

        if (plans.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No strategic blueprints saved yet.</td></tr>';
          return;
        }

        tbody.innerHTML = plans.map(p => `
          <tr>
            <td><b>${p.topic}</b></td>
            <td>${p.account_id}</td>
            <td style="font-size: 0.8rem; color: #a5b4fc;">${p.hook.substring(0, 50)}...</td>
            <td>${p.target_audience.substring(0, 40)}...</td>
            <td><span class="badge badge-success">${p.quality_score} / 100</span></td>
            <td style="font-size: 0.78rem; color: var(--text-dim);">${(p.created_at || '').substring(0, 16).replace('T', ' ')}</td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function generateDirectorBlueprint() {
      const account_id = document.getElementById('directorAccountSelect').value;
      const custom_topic = document.getElementById('directorCustomTopic').value;

      showToast('Generating 14-point strategic content blueprint...');
      try {
        const res = await fetch('/api/ai-plans/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ account_id, custom_topic })
        });
        const data = await res.json();
        const plan = data.plan;

        const out = document.getElementById('directorBlueprintOutput');
        out.innerHTML = `
          <div class="blueprint-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
              <div style="font-size: 1.25rem; font-weight: 800; color: #a5b4fc;">${plan.topic}</div>
              <span class="badge badge-success" style="font-size: 0.85rem;">VIRALITY QUALITY SCORE: ${plan.quality_score}/100</span>
            </div>

            <div class="blueprint-grid">
              <div class="blueprint-item">
                <div class="blueprint-key">1. Target Audience</div>
                <div class="blueprint-val">${plan.target_audience}</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">2. Video Concept & Angle</div>
                <div class="blueprint-val">${plan.video_idea}</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">3. Opening Hook (First 1-3s)</div>
                <div class="blueprint-val" style="color: #fcd34d; font-weight: 700;">${plan.hook}</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">4. Script Selection</div>
                <div class="blueprint-val" style="font-style: italic;">"${plan.script_selection}"</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">5. Retention Mechanics</div>
                <div class="blueprint-val">${plan.retention_strategy}</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">6. Editing & Subtitle Rules</div>
                <div class="blueprint-val">${plan.editing_instructions} (Theme: <b>${plan.subtitle_style}</b>)</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">7. Generated Caption</div>
                <div class="blueprint-val" style="white-space: pre-line;">${plan.caption}</div>
              </div>
              <div class="blueprint-item">
                <div class="blueprint-key">8. Hashtags & Cover Text</div>
                <div class="blueprint-val"><b>Cover:</b> ${plan.cover_text}<br><b>Tags:</b> ${plan.hashtags}</div>
              </div>
              <div class="blueprint-item" style="grid-column: 1 / -1;">
                <div class="blueprint-key">9. Rights & Compliance Disclaimers</div>
                <div class="blueprint-val" style="color: #6ee7b7;">${plan.copyright_notes}</div>
              </div>
            </div>
          </div>
        `;
        showToast('Strategic blueprint generated successfully!');
        loadAIDirector();
      } catch (e) {
        showToast(`Failed to generate blueprint: ${e}`);
      }
    }

    // --- Video Factory Tab Logic ---
    function loadFactory() {
      populateFactoryAccountDropdown();
    }

    async function submitUrlJob() {
      const url = document.getElementById('urlInput').value.trim();
      if (!url) { alert('Please enter a valid video URL'); return; }

      const account_id = document.getElementById('factoryAccountSelect').value;
      showJobProgress(true, 'Enqueuing video for autonomous processing...');

      try {
        const res = await fetch('/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, account_id })
        });
        const data = await res.json();
        activeJobId = data.job_id;
        showToast(data.message || 'Video job enqueued');
        startJobPolling(activeJobId);
      } catch (e) {
        showToast(`Error: ${e}`);
        showJobProgress(false);
      }
    }

    async function uploadFileJob() {
      const fileInput = document.getElementById('fileInput');
      if (!fileInput.files || fileInput.files.length === 0) {
        alert('Please choose a video file to upload');
        return;
      }
      const file = fileInput.files[0];
      const account_id = document.getElementById('factoryAccountSelect').value;

      const formData = new FormData();
      formData.append('file', file);
      formData.append('account_id', account_id);

      showJobProgress(true, `Uploading ${file.name}...`);
      try {
        const res = await fetch('/api/jobs/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        activeJobId = data.job_id;
        showToast('File uploaded and queued!');
        startJobPolling(activeJobId);
      } catch (e) {
        showToast(`Upload error: ${e}`);
        showJobProgress(false);
      }
    }

    function showJobProgress(show, title = '', status = 'PROCESSING', percent = 10, detail = '') {
      const card = document.getElementById('jobProgressCard');
      if (!card) return;
      card.style.display = show ? 'block' : 'none';
      if (show) {
        document.getElementById('progressTitle').innerText = title;
        document.getElementById('progressStatus').innerText = status;
        document.getElementById('progressBar').style.width = `${percent}%`;
        document.getElementById('progressDetail').innerText = detail;
      }
    }

    function startJobPolling(jobId) {
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch(`/api/jobs/${jobId}`);
          if (!res.ok) return;
          const job = await res.json();

          showJobProgress(
            true,
            `Processing Job: ${job.title || job.id}`,
            job.status.toUpperCase(),
            job.progress || 15,
            job.current_step || 'Analyzing media...'
          );

          if (job.status === 'completed' || job.status === 'ready') {
            clearInterval(pollInterval);
            showToast('Video processing complete! Edited clip ready.');
            showJobProgress(false);
            renderClipsGrid(job);
          } else if (job.status === 'failed' || job.status === 'cancelled') {
            clearInterval(pollInterval);
            showJobProgress(true, `Job ${job.status}`, 'STOPPED', 100, job.error_message || 'Job stopped');
          }
        } catch (e) {
          console.error(e);
        }
      }, 3000);
    }

    function renderClipsGrid(jobData, fallbackJobId = null) {
      const grid = document.getElementById('clipsGrid');
      if (!grid) return;

      const job = (jobData && typeof jobData === 'object' && !Array.isArray(jobData)) ? jobData : null;
      const clips = job ? (job.clips || []) : (Array.isArray(jobData) ? jobData : []);
      const renders = job ? (job.renders || []) : [];
      const jobId = job ? job.id : (fallbackJobId || activeJobId);

      if ((!clips || clips.length === 0) && (!renders || renders.length === 0)) {
        grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 2rem;">No viral clips identified.</div>';
        return;
      }

      let heroHtml = '';
      if (renders && renders.length > 0) {
        const topRender = renders[0];
        const filename = topRender.video_path.split('/').pop().split('\\\\').pop();
        heroHtml = `
          <div style="grid-column: 1 / -1; background: linear-gradient(180deg, rgba(99,102,241,0.12) 0%, rgba(15,18,26,0.95) 100%); border: 2px solid rgba(99,102,241,0.5); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span class="badge badge-success" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">✨ EDITED SHORT READY</span>
                <span style="font-weight: 800; font-size: 1.15rem; color: #fff;">${topRender.title || 'Viral Hook Short'}</span>
              </div>
              <div style="display: flex; gap: 0.5rem; align-items: center;">
                <span class="badge badge-success" style="font-size: 0.85rem;">VIRALITY: ${topRender.virality_score}/100</span>
                <span class="badge" style="background: rgba(255,255,255,0.08); font-size: 0.8rem;">${topRender.crop_mode} • ${topRender.theme}</span>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: minmax(260px, 300px) 1fr; gap: 1.5rem; align-items: start;">
              <!-- 9:16 Video Player -->
              <div style="background: #000; border-radius: 10px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 8px 24px rgba(0,0,0,0.6);">
                <video id="video-hero-${topRender.id}" src="/api/media/output/${filename}" controls playsinline preload="auto" style="width: 100%; height: auto; max-height: 480px; display: block;"></video>
              </div>

              <!-- Metadata, Waveform & Publish Controls -->
              <div>
                <div style="background: rgba(0,0,0,0.3); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.06);">
                  <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 0.35rem;">Suggested Instagram Caption</div>
                  <div style="font-size: 0.92rem; color: #e2e8f0; line-height: 1.5; margin-bottom: 0.75rem;">${topRender.caption || 'Watch till the end! ⚡'}</div>
                  <div style="font-size: 0.8rem; color: #818cf8; font-family: 'JetBrains Mono', monospace;">${topRender.hashtags || '#viral #reels #shorts'}</div>
                </div>

                <!-- Predictive Audience Retention Graph -->
                <div style="margin-bottom: 0.85rem;">
                  <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">
                    <span>📈 Predictive Audience Retention Curve R(t)</span>
                    <span style="color: #34d399; font-weight: 600;">🔥 98% 0-3s Hook Velocity</span>
                  </div>
                  <canvas id="retention-canvas-hero-${topRender.id}" width="480" height="38" style="width: 100%; height: 38px; background: rgba(0,0,0,0.5); border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);"></canvas>
                </div>

                <!-- Interactive Waveform Timeline Scrubber -->
                <div style="margin-bottom: 1.25rem;">
                  <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">
                    <span>⚡ Audio Waveform & Speech Cadence</span>
                    <span id="wave-time-hero-${topRender.id}">0.0s / 0.0s</span>
                  </div>
                  <canvas id="waveform-canvas-hero-${topRender.id}" width="480" height="40" style="width: 100%; height: 40px; background: rgba(0,0,0,0.5); border-radius: 6px; cursor: pointer; border: 1px solid rgba(255,255,255,0.08);"></canvas>
                </div>

                <!-- Action Controls -->
                <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1.25rem;">
                  <button class="btn-primary" onclick="sendRenderToDraft(${topRender.id})">
                    🚀 Send to Instagram Drafts
                  </button>
                  <button class="btn-secondary" style="border-color: rgba(16, 185, 129, 0.4); color: #10b981;" onclick="openRenderInDubbingLab(${topRender.id})">
                    🎙️ Dub in AI Lab
                  </button>
                  <button class="btn-secondary" style="border-color: rgba(245, 158, 11, 0.4); color: #f59e0b;" onclick="openCoverThumbnailsModal(${topRender.id})">
                    🖼️ 3-Cover Studio
                  </button>
                  <button class="btn-secondary" style="border-color: rgba(99, 102, 241, 0.4); color: #818cf8;" onclick="openMultiPlatformExportModal(${topRender.id}, '${(topRender.title || 'Viral Short').replace(/'/g, "\\'")}', '${topRender.caption ? topRender.caption.replace(/\\n/g, ' ').replace(/'/g, "\\'") : ''}')">
                    🌐 Multi-Platform Copy
                  </button>
                  <a href="/api/media/output/${filename}" download class="btn-secondary" style="text-decoration: none; display: flex; align-items: center; gap: 0.35rem;">
                    ⬇️ Download 9:16 Video
                  </a>
                  <a href="/api/renders/${topRender.id}/thumbnail?time_sec=1.0" target="_blank" class="btn-secondary" style="text-decoration: none; display: flex; align-items: center; gap: 0.35rem;">
                    📷 Cover Thumbnail
                  </a>
                  <button class="btn-secondary" style="border-color: rgba(14, 165, 233, 0.4); color: #0ea5e9;" onclick="applyWatermarkHero(${topRender.id}, '${topRender.video_path.replace(/\\\\/g, '/')}', '${topRender.account_id || 'acc_motivation'}')">
                    🛡️ Watermark Video
                  </button>
                  <button class="btn-secondary" style="border-color: rgba(245, 158, 11, 0.4); color: #f59e0b;" onclick="applyAutoZoomHero(${topRender.id}, '${topRender.video_path.replace(/\\\\/g, '/')}')">
                    ⚡ Apply Auto-Zoom
                  </button>
                  <button class="btn-secondary" style="border-color: rgba(16, 185, 129, 0.4); color: #10b981;" onclick="openHookBannerModal(${topRender.id}, '${topRender.video_path.replace(/\\\\/g, '/')}', '${(topRender.title || 'Viral Short').replace(/'/g, "\\'")}')">
                    🏷️ Add Hook Banner
                  </button>
                </div>

                <!-- Feature 2: Viral Hook A/B Studio -->
                <div style="background: rgba(0,0,0,0.4); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 10px; padding: 1.25rem;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem; flex-wrap: wrap; gap: 0.5rem;">
                    <div>
                      <div style="font-weight: 700; color: #f59e0b; display: flex; align-items: center; gap: 0.4rem; font-size: 0.95rem;">
                        <span>⚡</span> Viral Hook A/B Studio (3 Multi-Framework Variants)
                      </div>
                      <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 2px;">
                        Generate Curiosity Gap, Urgent Command, and Contrarian Shift hooks with predicted retention lift.
                      </div>
                    </div>
                    <button class="btn-secondary" style="font-size: 0.78rem; border-color: rgba(245, 158, 11, 0.4); color: #f59e0b;" onclick="generateHookVariantsForHero('${jobId}', ${topRender.clip_id}, '${topRender.video_path.replace(/\\\\/g, '/')}', ${topRender.id})">
                      ✨ Generate 3 Hook Variants
                    </button>
                  </div>
                  <div id="hookVariantsContainer-${topRender.id}" class="grid-3" style="gap: 0.75rem;">
                    <div style="grid-column: 1 / -1; text-align: center; color: var(--text-dim); font-size: 0.8rem; padding: 0.6rem;">
                      Click "Generate 3 Hook Variants" to produce 3 tested opening patterns with predicted retention lift.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        `;
      }

      // Render alternative viral clips
      const clipsHtml = clips.map(c => {
        const cId = c.clip_id || c.id;
        const alreadyRendered = renders.find(r => r.clip_id === cId);
        if (alreadyRendered) {
          const rFilename = alreadyRendered.video_path.split('/').pop().split('\\\\').pop();
          return `
            <div class="card" style="margin-bottom: 0; border-color: rgba(16,185,129,0.4);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <span class="badge badge-success" style="font-size: 0.82rem;">RENDERED: ${c.virality_score}/100</span>
                <span style="font-size: 0.8rem; color: var(--text-muted);">${c.start_time.toFixed(1)}s – ${c.end_time.toFixed(1)}s</span>
              </div>
              <div style="background: #000; border-radius: 8px; overflow: hidden; margin-bottom: 0.75rem;">
                <video src="/api/media/output/${rFilename}" controls playsinline preload="metadata" style="width: 100%; max-height: 240px; display: block;"></video>
              </div>
              <div style="font-weight: 700; font-size: 0.95rem; margin-bottom: 0.35rem; color: #a5b4fc;">${c.hook_type || c.title || 'Viral Hook'}</div>
              <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                <button class="btn-primary" style="flex: 1; font-size: 0.8rem;" onclick="sendRenderToDraft(${alreadyRendered.id})">Queue Draft</button>
                <a href="/api/media/output/${rFilename}" download class="btn-secondary" style="font-size: 0.8rem; text-decoration: none; display: flex; align-items: center;">Download</a>
              </div>
            </div>
          `;
        }

        return `
          <div class="card" style="margin-bottom: 0;" id="clip-card-${cId}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <span class="badge badge-success" style="font-size: 0.82rem;">VIRALITY: ${c.virality_score}/100</span>
              <span style="font-size: 0.8rem; color: var(--text-muted);">${c.start_time.toFixed(1)}s – ${c.end_time.toFixed(1)}s</span>
            </div>
            <div style="font-weight: 700; font-size: 1rem; margin-bottom: 0.5rem; color: #a5b4fc;">${c.hook_type || 'Opening Hook'}</div>
            <div style="font-size: 0.84rem; color: #cbd5e1; font-style: italic; margin-bottom: 1rem; line-height: 1.4;">"${(c.full_quote || c.title || '').substring(0, 140)}..."</div>
            <button class="btn-primary" id="render-btn-${cId}" style="width: 100%; font-size: 0.84rem;" onclick="renderClipShort('${jobId}', ${cId})">
              ⚡ Render 9:16 Short
            </button>
          </div>
        `;
      }).join('');

      grid.innerHTML = heroHtml + (clipsHtml ? `
        <div style="grid-column: 1 / -1; font-weight: 700; font-size: 1.05rem; margin: 1rem 0 0.5rem; color: #e2e8f0; display: flex; align-items: center; gap: 0.5rem;">
          <span>🎯 Alternative Viral Clips Detected (${clips.length})</span>
        </div>
        ${clipsHtml}
      ` : '');

      if (renders && renders.length > 0) {
        initWaveformScrubber(`hero-${renders[0].id}`);
        initRetentionGraph(`hero-${renders[0].id}`);
      }
    }

    async function renderClipShort(jobId, clipId) {
      const crop_mode = document.getElementById('factoryCropSelect').value;
      const theme = document.getElementById('factoryThemeSelect').value;
      const target_language = document.getElementById('factoryLangSelect') ? document.getElementById('factoryLangSelect').value : 'en';
      const enable_ducking = document.getElementById('factoryDuckingCheck') ? document.getElementById('factoryDuckingCheck').checked : true;
      const enable_jumpcuts = document.getElementById('factoryJumpcutCheck') ? document.getElementById('factoryJumpcutCheck').checked : true;
      const enable_sfx = document.getElementById('factorySfxCheck') ? document.getElementById('factorySfxCheck').checked : true;
      const enable_broll = document.getElementById('factoryBrollCheck') ? document.getElementById('factoryBrollCheck').checked : false;
      const enable_auto_zoom = document.getElementById('factoryAutoZoomCheck') ? document.getElementById('factoryAutoZoomCheck').checked : true;
      const hook_banner_enabled = document.getElementById('factoryHookBannerCheck') ? document.getElementById('factoryHookBannerCheck').checked : true;
      let hook_banner_text = null;
      if (hook_banner_enabled) {
        const inp = document.getElementById('factoryHookBannerInput');
        hook_banner_text = (inp && inp.value.trim()) ? inp.value.trim() : null;
      }

      const btn = document.getElementById(`render-btn-${clipId}`);
      if (btn) {
        btn.disabled = true;
        btn.innerText = '⏳ Rendering 9:16 Short...';
      }

      showToast('Rendering 9:16 short with face tracking & karaoke captions...');
      try {
        const res = await fetch(`/api/jobs/${jobId}/render/${clipId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            crop_mode,
            theme,
            enable_ducking,
            enable_jumpcuts,
            target_language,
            enable_sfx,
            enable_broll,
            enable_auto_zoom,
            hook_banner_text,
            hook_banner_theme: theme
          })
        });
        const data = await res.json();
        showToast('Render complete! Short ready.');

        // Re-fetch job details and re-render grid in place so user immediately sees their clip!
        const jobRes = await fetch(`/api/jobs/${jobId}`);
        if (jobRes.ok) {
          const updatedJob = await jobRes.json();
          renderClipsGrid(updatedJob);
        }
        loadLibraryShorts();
      } catch (e) {
        showToast(`Render failed: ${e}`);
        if (btn) {
          btn.disabled = false;
          btn.innerText = '⚡ Render 9:16 Short';
        }
      }
    }

    // --- Interactive Audio Waveform Timeline Scrubber ---
    function initWaveformScrubber(renderId) {
      const canvas = document.getElementById(`waveform-canvas-${renderId}`);
      const video = document.getElementById(`video-${renderId}`);
      const timeLabel = document.getElementById(`wave-time-${renderId}`);
      if (!canvas || !video) return;

      const ctx = canvas.getContext('2d');
      const numBars = 48;
      const heights = [];
      const numId = typeof renderId === 'number' ? renderId : (parseInt(String(renderId).replace(/\\D/g, '')) || 42);
      let seed = (numId * 9301 + 49297) % 233280;
      for (let i = 0; i < numBars; i++) {
        seed = (seed * 9301 + 49297) % 233280;
        const rnd = seed / 233280;
        const envelope = Math.sin((i / numBars) * Math.PI) * 0.45 + 0.55;
        heights.push(Math.max(0.18, rnd * envelope));
      }

      function draw(progress = 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const barWidth = canvas.width / numBars;
        const drawWidth = Math.max(2, barWidth - 2.5);

        for (let i = 0; i < numBars; i++) {
          const barFraction = (i + 0.5) / numBars;
          const isPlayed = barFraction <= progress;
          const h = heights[i] * (canvas.height - 8);
          const y = (canvas.height - h) / 2;
          const x = i * barWidth;

          const grad = ctx.createLinearGradient(0, y, 0, y + h);
          if (isPlayed) {
            grad.addColorStop(0, '#818cf8');
            grad.addColorStop(1, '#c084fc');
          } else {
            grad.addColorStop(0, 'rgba(148, 163, 184, 0.4)');
            grad.addColorStop(1, 'rgba(71, 85, 105, 0.25)');
          }
          ctx.fillStyle = grad;
          if (ctx.roundRect) {
            ctx.beginPath();
            ctx.roundRect(x, y, drawWidth, h, 2);
            ctx.fill();
          } else {
            ctx.fillRect(x, y, drawWidth, h);
          }
        }

        // Draw active playhead
        const playheadX = progress * canvas.width;
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(playheadX, 0);
        ctx.lineTo(playheadX, canvas.height);
        ctx.stroke();
      }

      draw(0);

      video.addEventListener('timeupdate', () => {
        if (!video.duration || isNaN(video.duration)) return;
        const progress = video.currentTime / video.duration;
        draw(progress);
        if (timeLabel) {
          timeLabel.textContent = `${video.currentTime.toFixed(1)}s / ${video.duration.toFixed(1)}s`;
        }
      });

      video.addEventListener('loadedmetadata', () => {
        if (timeLabel && video.duration) {
          timeLabel.textContent = `0.0s / ${video.duration.toFixed(1)}s`;
        }
      });

      canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const progress = Math.max(0, Math.min(1, clickX / rect.width));
        if (video.duration && !isNaN(video.duration)) {
          video.currentTime = progress * video.duration;
        }
        draw(progress);
      });
    }

    // --- Predictive Audience Retention Graph Renderer ---
    function initRetentionGraph(renderId) {
      const canvas = document.getElementById(`retention-canvas-${renderId}`);
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 1;
      for (let y = 8; y < h; y += 12) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      const numId = typeof renderId === 'number' ? renderId : (parseInt(String(renderId).replace(/\\D/g, '')) || 42);
      let seed = (numId * 7919 + 65537) % 233280;

      const numPoints = 28;
      const points = [];
      let r = 100.0;
      for (let i = 0; i < numPoints; i++) {
        seed = (seed * 9301 + 49297) % 233280;
        const rnd = seed / 233280;
        if (i < 4) {
          r -= rnd * 0.7;
        } else if (i < 16) {
          r -= rnd * 1.8;
        } else {
          r -= rnd * 1.1;
        }
        const clampedR = Math.max(30.0, r);
        const yPos = h - ((clampedR / 100) * (h - 6));
        points.push({ x: (i / (numPoints - 1)) * w, y: yPos });
      }

      // Draw gradient under curve
      const gradFill = ctx.createLinearGradient(0, 0, 0, h);
      gradFill.addColorStop(0, 'rgba(16, 185, 129, 0.22)');
      gradFill.addColorStop(0.5, 'rgba(99, 102, 241, 0.12)');
      gradFill.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.lineTo(w, h);
      ctx.lineTo(0, h);
      ctx.closePath();
      ctx.fillStyle = gradFill;
      ctx.fill();

      // Draw glowing stroke line
      const strokeGrad = ctx.createLinearGradient(0, 0, w, 0);
      strokeGrad.addColorStop(0, '#10b981');   // Green hook
      strokeGrad.addColorStop(0.4, '#6366f1'); // Violet mid
      strokeGrad.addColorStop(0.75, '#eab308'); // Yellow
      strokeGrad.addColorStop(1.0, '#ef4444'); // Red ending

      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.strokeStyle = strokeGrad;
      ctx.lineWidth = 2.0;
      ctx.stroke();

      // Peak hook tag at start
      ctx.fillStyle = '#10b981';
      ctx.font = '8px monospace';
      ctx.fillText('🔥 98% HOOK', 4, 10);
      ctx.fillStyle = 'rgba(148, 163, 184, 0.75)';
      ctx.fillText(`AVG: ${Math.round(r)}%`, w - 65, 10);
    }

    // --- Automated 7-Day Week Publishing Calendar Action ---
    async function autoScheduleWeek() {
      const filter = document.getElementById('calendarAccountFilter');
      const account_id = filter ? filter.value : 'all';
      showToast('Allocating drafts across 7-day optimal engagement slots...');
      try {
        const res = await fetch('/api/publishing/auto-schedule-week', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ account_id })
        });
        const data = await res.json();
        showToast(data.message || 'Auto-scheduling complete!');
        loadPublishingQueue();
      } catch (e) {
        showToast(`Auto-schedule error: ${e}`);
      }
    }

    // --- Video Library Tab Logic ---
    async function loadLibraryShorts() {
      const filter = document.getElementById('libraryAccountFilter');
      if (filter) {
        filter.innerHTML = '<option value="all">All Accounts</option>' + accountsCache.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
      }

      const accountId = filter ? filter.value : currentGlobalAccount;
      const url = `/api/renders${accountId !== 'all' ? `?account_id=${accountId}` : ''}`;
      try {
        const res = await fetch(url);
        const data = await res.json();
        const grid = document.getElementById('libraryShortsGrid');
        const renders = data.renders || [];

        if (renders.length === 0) {
          grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: var(--text-muted); padding: 3rem;">No rendered shorts found.</div>';
          return;
        }

        grid.innerHTML = renders.map(r => {
          const filename = r.video_path.split('/').pop().split('\\\\').pop();
          return `
            <div class="short-card">
              <div class="short-video-wrapper">
                <video id="video-${r.id}" src="/api/media/output/${filename}" controls playsinline preload="metadata"></video>
              </div>
              <div class="short-content">
                <div style="font-weight: 700; font-size: 0.95rem;">${r.title || 'Highlight'}</div>
                <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: var(--text-muted);">
                  <span>Account: <b>${r.account_id}</b></span>
                  <span>Score: <b style="color: #34d399;">${r.virality_score}</b></span>
                </div>
                <!-- Predictive Audience Retention Graph -->
                <div style="margin: 0.35rem 0;">
                  <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 2px;">
                    <span>📈 Retention R(t)</span>
                    <span style="color: #34d399; font-weight: 600;">97% Hook</span>
                  </div>
                  <canvas id="retention-canvas-${r.id}" width="320" height="26" style="width: 100%; height: 26px; background: rgba(0,0,0,0.5); border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);"></canvas>
                </div>
                <!-- Interactive Waveform Timeline Scrubber -->
                <div style="margin: 0.4rem 0;">
                  <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 3px;">
                    <span>⚡ Audio Waveform Scrubber</span>
                    <span id="wave-time-${r.id}">0.0s / 0.0s</span>
                  </div>
                  <canvas id="waveform-canvas-${r.id}" width="320" height="36" style="width: 100%; height: 36px; background: rgba(0,0,0,0.45); border-radius: 6px; cursor: pointer; border: 1px solid rgba(255,255,255,0.08);"></canvas>
                </div>
                <div style="display: flex; gap: 0.5rem; margin-top: 0.25rem;">
                  <button class="btn-secondary" style="flex: 1; font-size: 0.78rem;" onclick="sendRenderToDraft(${r.id})">Queue to Drafts</button>
                  <a href="/api/media/output/${filename}" download class="btn-secondary" style="font-size: 0.78rem; text-decoration: none; display: flex; align-items: center;">Download</a>
                  <a href="/api/renders/${r.id}/thumbnail" target="_blank" class="btn-secondary" style="font-size: 0.78rem; text-decoration: none; display: flex; align-items: center;" title="Extract High-Res Cover Thumbnail">📷 Cover</a>
                </div>
              </div>
            </div>
          `;
        }).join('');

        // Initialize waveform scrubbers and retention graphs for all rendered shorts
        renders.forEach(r => {
          initWaveformScrubber(r.id);
          initRetentionGraph(r.id);
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function sendRenderToDraft(renderId) {
      const res = await fetch(`/api/renders/${renderId}/send-to-draft`, { method: 'POST' });
      const data = await res.json();
      showToast(data.message);
      loadPublishingQueue();
    }

    // --- Publishing Calendar Tab Logic ---
    async function loadPublishingQueue() {
      const filter = document.getElementById('calendarAccountFilter');
      if (filter) {
        filter.innerHTML = '<option value="all">All Accounts</option>' + accountsCache.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
      }

      const accountId = filter ? filter.value : currentGlobalAccount;
      const url = `/api/publishing/queue${accountId !== 'all' ? `?account_id=${accountId}` : ''}`;

      try {
        const res = await fetch(url);
        const data = await res.json();
        const container = document.getElementById('publishingQueueContainer');
        const queue = data.queue || [];

        document.getElementById('navDraftsBadge').innerText = queue.filter(q => q.status === 'draft').length;
        document.getElementById('kpiDrafts').innerText = queue.length;

        if (queue.length === 0) {
          container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 3rem;">No publishing drafts in queue.</div>';
          return;
        }

        container.innerHTML = queue.map(item => {
          const isApproved = item.status === 'approved' || item.status === 'scheduled';
          const filename = item.video_path ? item.video_path.split('/').pop().split('\\\\').pop() : '';
          return `
            <div class="card" style="display: flex; gap: 1.5rem; margin-bottom: 1rem; align-items: flex-start;">
              <div style="width: 140px; height: 248px; border-radius: var(--radius-sm); overflow: hidden; background: #000; flex-shrink: 0;">
                <video src="/api/media/output/${filename}" controls playsinline style="width: 100%; height: 100%; object-fit: cover;"></video>
              </div>
              <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                  <div>
                    <div style="font-weight: 700; font-size: 1.1rem;">${item.short_title || 'Reel Highlight'}</div>
                    <div style="font-size: 0.78rem; color: var(--text-muted);">Account: <b>${item.account_id}</b></div>
                  </div>
                  <span class="badge ${isApproved ? 'badge-success' : 'badge-warning'}">${item.status.toUpperCase()}</span>
                </div>

                <div class="form-group">
                  <label class="form-label">Instagram Reel Caption</label>
                  <textarea id="caption_${item.id}" class="form-textarea" rows="2">${item.caption || ''}</textarea>
                </div>

                <div class="form-group">
                  <label class="form-label">Optimized Hashtags</label>
                  <input type="text" id="hashtags_${item.id}" class="form-input" value="${item.hashtags || ''}">
                </div>

                <div style="display: flex; gap: 0.5rem; align-items: center;">
                  <button class="btn-secondary" onclick="saveDraft(${item.id})">Save Draft</button>
                  ${!isApproved ? `<button class="btn-primary" onclick="approveDraft(${item.id})">✓ Approve for Instagram</button>` : `<span class="badge badge-success">✓ Approved for Meta Graph API</span>`}
                  <button class="btn-secondary" onclick="simulatePublish(${item.id})">Test Graph API Dry-Run</button>
                </div>
              </div>
            </div>
          `;
        }).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function saveDraft(id) {
      const caption = document.getElementById(`caption_${id}`).value;
      const hashtags = document.getElementById(`hashtags_${id}`).value;
      await fetch(`/api/publishing/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caption, hashtags })
      });
      showToast('Draft updated successfully');
    }

    async function approveDraft(id) {
      await fetch(`/api/publishing/${id}/approve`, { method: 'POST' });
      showToast('Draft approved for Meta Graph API posting');
      loadPublishingQueue();
    }

    async function simulatePublish(id) {
      try {
        const res = await fetch(`/api/publishing/${id}/simulate_publish`, { method: 'POST' });
        const data = await res.json();
        alert(JSON.stringify(data, null, 2));
      } catch (e) {
        alert(`Simulation response: ${e}`);
      }
    }

    // --- Telemetry & Health Tab Logic ---
    async function loadTelemetry() {
      try {
        const res = await fetch('/api/system/stats');
        const data = await res.json();

        document.getElementById('healthCpu').innerText = `${data.cpu_percent}%`;
        document.getElementById('healthRam').innerText = `${data.ram.percent}%`;
        document.getElementById('healthRamDetail').innerText = `${data.ram.used_gb} GB / ${data.ram.total_gb} GB`;
        document.getElementById('healthDisk').innerText = `${data.disk.free_gb} GB`;

        const healthRes = await fetch('/api/health');
        const healthData = await healthRes.json();
        document.getElementById('healthCpuThreads').innerText = `${healthData.cpu_threads} CPU Threads Active`;
        document.getElementById('healthFfmpeg').innerText = healthData.ffmpeg ? 'AVAILABLE (SIMD)' : 'MISSING';

        // Load jobs table
        const jobsRes = await fetch('/api/jobs');
        const jobsData = await jobsRes.json();
        const tbody = document.getElementById('telemetryJobsTableBody');
        const jobs = jobsData.jobs || [];

        if (jobs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No jobs in database.</td></tr>';
          return;
        }

        tbody.innerHTML = jobs.map(j => `
          <tr>
            <td style="font-family: monospace; color: #a5b4fc;">${j.id}</td>
            <td><b>${(j.title || j.source_path || '').substring(0, 45)}</b></td>
            <td>${j.account_id || 'acc_motivation'}</td>
            <td><span class="badge ${j.status === 'completed' ? 'badge-success' : (j.status === 'failed' ? 'badge-danger' : 'badge-primary')}">${j.status}</span></td>
            <td>${j.progress}%</td>
            <td>${j.retry_count || 0}</td>
            <td style="font-size: 0.78rem; color: var(--text-dim);">${(j.created_at || '').substring(0, 16).replace('T', ' ')}</td>
            <td>
              <div style="display: flex; gap: 0.3rem;">
                ${j.status === 'failed' || j.status === 'cancelled' ? `<button class="btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;" onclick="retryJob('${j.id}')">Retry</button>` : ''}
                ${j.status === 'queued' || j.status === 'downloading' || j.status === 'transcribing' ? `<button class="btn-danger" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;" onclick="cancelJob('${j.id}')">Cancel</button>` : ''}
                <button class="btn-danger" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;" onclick="deleteJob('${j.id}')">Delete</button>
              </div>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function retryJob(jobId) {
      await fetch(`/api/jobs/${jobId}/retry`, { method: 'POST' });
      showToast('Job re-enqueued');
      loadTelemetry();
    }

    async function cancelJob(jobId) {
      await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      showToast('Job cancelled');
      loadTelemetry();
    }

    async function deleteJob(jobId) {
      if (!confirm('Permanently delete this job record?')) return;
      await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
      showToast('Job deleted');
      loadTelemetry();
    }

    // --- AI Dubbing Lab Logic ---
    let dubbingRendersCache = [];
    let currentDubbedResult = null;
    let hookVariantsCache = {};

    async function loadDubbingLibrary() {
      try {
        // 1. Load rendered shorts into dropdown
        const rRes = await fetch('/api/renders?limit=50');
        const rData = await rRes.json();
        dubbingRendersCache = rData.renders || [];

        const select = document.getElementById('dubSourceSelect');
        if (select) {
          select.innerHTML = '<option value="">-- Choose a rendered short from library --</option>' +
            dubbingRendersCache.map(r => `<option value="${r.id}">[#${r.id}] ${r.title || 'Short'} (${r.duration ? r.duration.toFixed(1) : '0'}s | Virality: ${r.virality_score}/100)</option>`).join('');
        }

        // 2. Load voices for active language
        await onDubLangChange(document.getElementById('dubLangSelect').value);

        // 3. Load dubbed history table
        const hRes = await fetch('/api/dubbing/history');
        const hData = await hRes.json();
        const tbody = document.getElementById('dubHistoryTableBody');
        if (tbody && hData.history) {
          if (hData.history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">No dubbed videos generated yet.</td></tr>';
          } else {
            tbody.innerHTML = hData.history.map(d => {
              const filename = d.dubbed_video_path.split('/').pop().split('\\\\').pop();
              return `
                <tr>
                  <td><code>#${d.id}</code></td>
                  <td><span class="badge badge-primary">${d.target_language.toUpperCase()}</span></td>
                  <td style="font-weight: 600;">${d.voice_name || d.voice_id}</td>
                  <td><code>${d.blend_mode}</code> (${d.speed}x)</td>
                  <td><code>${d.created_at ? d.created_at.slice(0, 16) : ''}</code></td>
                  <td><code>${filename}</code></td>
                  <td>
                    <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;" onclick="playDubbedShort('/api/media/output/${filename}', '${d.voice_name}', '${d.target_language}')">Play</button>
                    <a href="/api/media/output/${filename}" download class="btn-secondary" style="font-size: 0.75rem; padding: 0.2rem 0.5rem; text-decoration: none;">Download</a>
                  </td>
                </tr>
              `;
            }).join('');
          }
        }
      } catch (e) {
        console.error('Error loading dubbing lab:', e);
      }
    }

    async function onDubLangChange(langCode) {
      try {
        const vRes = await fetch(`/api/dubbing/voices?language=${langCode}`);
        const vData = await vRes.json();
        const vSelect = document.getElementById('dubVoiceSelect');
        if (vSelect && vData.voices) {
          vSelect.innerHTML = vData.voices.map(v => `<option value="${v.id}">${v.name} (${v.style}) [${v.gender}]</option>`).join('');
        }
      } catch (e) {
        console.error('Error loading voices:', e);
      }
    }

    function onDubSourceChange(renderId) {
      if (!renderId) return;
      const r = dubbingRendersCache.find(item => item.id == renderId);
      if (!r) return;
      const scriptBox = document.getElementById('dubScriptText');
      if (scriptBox) {
        scriptBox.value = r.caption ? r.caption.replace(/#\\w+/g, '').trim() : (r.title || 'Discipline is the foundation of all greatness.');
      }
    }

    async function previewSelectedVoice() {
      const voiceId = document.getElementById('dubVoiceSelect').value;
      const scriptText = document.getElementById('dubScriptText').value || 'Hello, this is a neural voice sample for VedioHooks AI.';
      showToast('Synthesizing voice sample...');
      try {
        const res = await fetch('/api/dubbing/preview-voice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: scriptText.slice(0, 80), voice_id: voiceId })
        });
        if (res.ok) {
          const blob = await res.blob();
          const audioUrl = URL.createObjectURL(blob);
          const audio = new Audio(audioUrl);
          audio.play();
        } else {
          showToast('Failed to preview voice');
        }
      } catch (e) {
        showToast('Error synthesizing voice sample: ' + e.message);
      }
    }

    async function autoTranslateDubText() {
      const lang = document.getElementById('dubLangSelect').value;
      showToast(`Auto-translating to ${lang.toUpperCase()} during synthesis...`);
    }

    async function startDubbingJob() {
      const renderId = document.getElementById('dubSourceSelect').value;
      if (!renderId) {
        showToast('Please select a source video short first');
        return;
      }
      const r = dubbingRendersCache.find(item => item.id == renderId);
      if (!r) {
        showToast('Selected short not found');
        return;
      }

      const scriptText = document.getElementById('dubScriptText').value;
      const targetLang = document.getElementById('dubLangSelect').value;
      const voiceId = document.getElementById('dubVoiceSelect').value;
      const blendMode = document.getElementById('dubBlendMode').value;
      const speed = parseFloat(document.getElementById('dubSpeedSlider').value) || 1.0;

      const pBox = document.getElementById('dubProgressBox');
      const pBar = document.getElementById('dubProgressBar');
      const pText = document.getElementById('dubProgressText');
      const btn = document.getElementById('btnStartDubbing');

      pBox.style.display = 'block';
      pBar.style.width = '30%';
      pText.innerText = 'Synthesizing neural multi-language voiceover...';
      btn.disabled = true;

      try {
        const res = await fetch('/api/dubbing/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_path: r.video_path,
            transcript_text: scriptText || r.title || 'Discipline is key.',
            target_language: targetLang,
            voice_id: voiceId,
            blend_mode: blendMode,
            speed: speed,
            render_id: r.id,
            account_id: r.account_id || 'acc_motivation'
          })
        });

        pBar.style.width = '90%';
        pText.innerText = 'Multiplexing audio & assembling final 9:16 short...';

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Dubbing failed');
        }

        const data = await res.json();
        currentDubbedResult = data;
        pBar.style.width = '100%';
        pText.innerText = 'Complete!';

        setTimeout(() => { pBox.style.display = 'none'; btn.disabled = false; }, 1000);

        // Display in right column preview
        document.getElementById('dubPreviewPlaceholder').style.display = 'none';
        const pCont = document.getElementById('dubPreviewContainer');
        pCont.style.display = 'block';

        const filename = data.video_path.split('/').pop().split('\\\\').pop();
        const player = document.getElementById('dubVideoPlayer');
        player.src = `/api/media/output/${filename}`;
        player.load();

        document.getElementById('dubDetailsBox').innerHTML = `
          <div><strong>Language:</strong> ${data.target_language.toUpperCase()}</div>
          <div><strong>Voice Model:</strong> ${data.voice_name || data.voice_id}</div>
          <div><strong>Audio Mix:</strong> ${data.blend_mode}</div>
          <div><strong>Duration:</strong> ${data.duration ? data.duration.toFixed(1) : '0'}s</div>
          <div style="grid-column: 1 / -1;"><strong>Script:</strong> "${(data.translated_text || '').slice(0, 90)}..."</div>
        `;

        showToast('🎉 Short dubbed successfully!');
        loadDubbingLibrary();
      } catch (e) {
        pBox.style.display = 'none';
        btn.disabled = false;
        showToast('Dubbing failed: ' + e.message);
      }
    }

    function playDubbedShort(url, voiceName, lang) {
      document.getElementById('dubPreviewPlaceholder').style.display = 'none';
      const pCont = document.getElementById('dubPreviewContainer');
      pCont.style.display = 'block';
      const player = document.getElementById('dubVideoPlayer');
      player.src = url;
      player.play();
      document.getElementById('dubDetailsBox').innerHTML = `
        <div><strong>Language:</strong> ${lang.toUpperCase()}</div>
        <div><strong>Voice Model:</strong> ${voiceName}</div>
        <div style="grid-column: 1 / -1;"><strong>Source:</strong> ${url}</div>
      `;
    }

    function openRenderInDubbingLab(renderId) {
      switchTab('dubbing');
      setTimeout(() => {
        const select = document.getElementById('dubSourceSelect');
        if (select) {
          select.value = renderId;
          onDubSourceChange(renderId);
        }
      }, 350);
    }

    function downloadDubbedShort() {
      if (!currentDubbedResult) return;
      const filename = currentDubbedResult.video_path.split('/').pop().split('\\\\').pop();
      const a = document.createElement('a');
      a.href = `/api/media/output/${filename}`;
      a.download = filename;
      a.click();
    }

    async function queueDubbedShort() {
      if (!currentDubbedResult) return;
      try {
        await fetch('/api/publishing/queue', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            render_id: currentDubbedResult.dubbed_id || 1,
            job_id: 'dubbed_' + currentDubbedResult.target_language,
            account_id: currentDubbedResult.account_id || 'acc_motivation',
            caption: `🌍 [Dubbed in ${currentDubbedResult.target_language.toUpperCase()}]\\n${currentDubbedResult.translated_text || ''}\\n\\n#viral #shorts #reels`,
            hashtags: '#viral #shorts #reels'
          })
        });
        showToast('Dubbed short sent to Instagram drafts!');
        switchTab('calendar');
      } catch (e) {
        showToast('Failed to queue draft: ' + e.message);
      }
    }

    // --- Viral Hook A/B Studio Logic ---
    async function generateHookVariantsForHero(jobId, clipId, videoPath, renderId) {
      const container = document.getElementById(`hookVariantsContainer-${renderId}`);
      if (!container) return;
      container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: #f59e0b; padding: 1rem;">⚡ Generating 3 distinct psychological hook frameworks...</div>';

      try {
        const account = accountsCache.find(a => a.id === currentGlobalAccount) || accountsCache[0] || {};
        const niche = account.niche || 'Motivation';

        const res = await fetch('/api/hooks/generate-variants', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            clip_text: 'Viral opening hook for short video',
            niche: niche,
            base_score: 85,
            job_id: jobId,
            clip_id: clipId,
            account_id: account.id || 'acc_motivation'
          })
        });

        const data = await res.json();
        const variants = data.variants || [];
        hookVariantsCache[renderId] = variants;

        container.innerHTML = variants.map(v => `
          <div style="background: rgba(255,255,255,0.03); border: 1px solid ${v.accent_color}66; border-radius: 8px; padding: 0.85rem; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span class="badge" style="background: ${v.accent_color}22; color: ${v.accent_color}; border: 1px solid ${v.accent_color}88; font-weight: 700;">
                  HOOK ${v.variant_letter}
                </span>
                <span style="font-size: 0.72rem; color: #10b981; font-weight: 700;">${v.retention_lift}</span>
              </div>
              <div style="font-size: 0.76rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.25rem;">
                ${v.framework_type}
              </div>
              <div style="font-weight: 700; font-size: 0.88rem; color: #fff; margin-bottom: 0.5rem; line-height: 1.3;">
                ${v.hook_title}
              </div>
              <div style="margin-bottom: 0.75rem;">
                <label style="font-size: 0.7rem; color: var(--text-dim); text-transform: uppercase; font-weight: 600;">Opening Overlay Text (0-2.5s):</label>
                <textarea id="hookText-${v.id}" class="form-textarea" rows="2" style="font-size: 0.75rem; padding: 0.35rem; width: 100%; resize: none;">${v.hook_overlay_text}</textarea>
              </div>
            </div>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn-primary" style="flex: 1; font-size: 0.72rem; padding: 0.35rem 0.5rem; background: ${v.accent_color}; border: none; color: #000; font-weight: 700;" onclick="renderHookVariantOverlayAction(${v.id}, '${videoPath.replace(/'/g, "\\'")}', 'hookText-${v.id}', ${renderId})">
                🎬 Burn Intro
              </button>
            </div>
          </div>
        `).join('') + `
          <div style="grid-column: 1 / -1; display: flex; justify-content: flex-end; margin-top: 0.5rem;">
            <button class="btn-primary" style="font-size: 0.8rem; padding: 0.45rem 1rem; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); border: none;" onclick="queueAllHookVariantsAction('${jobId}', '${account.id || 'acc_motivation'}', ${renderId})">
              📅 Schedule 3-Way A/B Split Test in Drafts
            </button>
          </div>
        `;
      } catch (e) {
        container.innerHTML = `<div style="grid-column: 1 / -1; color: #ef4444; font-size: 0.8rem;">Failed to generate hook variants: ${e.message}</div>`;
      }
    }

    async function renderHookVariantOverlayAction(variantId, videoPath, textareaId, renderId) {
      const textarea = document.getElementById(textareaId);
      const text = textarea ? textarea.value : 'VIRAL HOOK';
      showToast('Burning dynamic hook intro card (0-2.5s)...');
      try {
        const res = await fetch('/api/hooks/render-variant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_path: videoPath,
            hook_overlay_text: text,
            duration_sec: 2.5,
            variant_id: variantId
          })
        });
        if (!res.ok) throw new Error('Hook rendering failed');
        const data = await res.json();
        const filename = data.rendered_video_path.split('/').pop().split('\\\\').pop();
        showToast('Hook intro burned successfully!');
        const heroPlayer = document.getElementById(`hero-video-${renderId}`);
        if (heroPlayer) {
          heroPlayer.src = `/api/media/output/${filename}`;
          heroPlayer.play();
        }
      } catch (e) {
        showToast('Error rendering hook overlay: ' + e.message);
      }
    }

    async function queueAllHookVariantsAction(jobId, accountId, renderId) {
      const variants = hookVariantsCache[renderId] || [];
      if (variants.length === 0) {
        showToast('No variants generated to schedule');
        return;
      }
      showToast('Scheduling 3-way A/B split-test in Instagram Drafts...');
      try {
        const res = await fetch('/api/hooks/queue-ab-test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            account_id: accountId,
            job_id: jobId,
            variants: variants,
            base_caption: 'Which opening hook grabbed you first? Drop a comment below!',
            hashtags: '#abtesting #viralhooks #reels #shorts'
          })
        });
        const data = await res.json();
        showToast(`⚡ ${data.count} A/B Hook variations queued for Instagram publishing!`);
        switchTab('calendar');
      } catch (e) {
        showToast('Error scheduling A/B test: ' + e.message);
      }
    }

    // --- Dynamic Real-Time Analytics Logic ---
    async function loadAnalytics() {
      try {
        const url = `/api/analytics${currentGlobalAccount !== 'all' ? `?account_id=${currentGlobalAccount}` : ''}`;
        const res = await fetch(url);
        const data = await res.json();

        // 1. Top metric cards
        document.getElementById('analyticsAvgVirality').innerText = data.avg_virality_score > 0 ? data.avg_virality_score : '--';
        document.getElementById('analyticsScoreRange').innerText = data.total_renders > 0 ? `Range: ${data.min_virality_score} to ${data.max_virality_score}` : 'No rendered shorts yet';
        document.getElementById('analyticsRetention').innerText = data.retention_benchmark_pct > 0 ? `${data.retention_benchmark_pct}%` : '--%';
        document.getElementById('analyticsCadence').innerHTML = `${data.cadence.actual_rendered} <span style="font-size: 1rem; color: var(--text-muted);">Shorts</span>`;
        document.getElementById('analyticsDailyTarget').innerText = `Daily Target: ${data.cadence.daily_target} across active network`;

        // 2. Virality tiers
        const tiers = data.virality_tiers;
        const totalR = Math.max(1, data.total_renders);
        document.getElementById('tierEliteCount').innerText = `${tiers.elite_90_plus} (${Math.round(tiers.elite_90_plus / totalR * 100)}%)`;
        document.getElementById('tierEliteBar').style.width = `${Math.round(tiers.elite_90_plus / totalR * 100)}%`;

        document.getElementById('tierHighCount').innerText = `${tiers.high_80_89} (${Math.round(tiers.high_80_89 / totalR * 100)}%)`;
        document.getElementById('tierHighBar').style.width = `${Math.round(tiers.high_80_89 / totalR * 100)}%`;

        document.getElementById('tierStandardCount').innerText = `${tiers.standard_under_80} (${Math.round(tiers.standard_under_80 / totalR * 100)}%)`;
        document.getElementById('tierStandardBar').style.width = `${Math.round(tiers.standard_under_80 / totalR * 100)}%`;

        // 3. Publishing Funnel
        const pipe = data.publishing_pipeline;
        document.getElementById('funnelDrafts').innerText = pipe.drafts;
        document.getElementById('funnelScheduled').innerText = pipe.scheduled;
        document.getElementById('funnelApproved').innerText = pipe.approved;
        document.getElementById('funnelPublished').innerText = pipe.published;

        // 4. Multi-Account Niche Table
        const tbody = document.getElementById('analyticsNicheTableBody');
        if (tbody) {
          tbody.innerHTML = data.niche_breakdown.map(n => {
            const share = data.total_renders > 0 ? Math.round((n.shorts_count / data.total_renders) * 100) : 0;
            return `
              <tr>
                <td><b style="color: ${n.brand_color || '#6366f1'};">${n.avatar_emoji || '⚡'} ${n.name}</b> (${n.niche})</td>
                <td><code>@${n.id.replace('acc_', '')}</code></td>
                <td><span class="badge badge-primary">${n.shorts_count} Shorts</span></td>
                <td>
                  <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div class="progress-bar-bg" style="width: 100px;"><div class="progress-bar-fill" style="width: ${share}%; background: ${n.brand_color || '#6366f1'};"></div></div>
                    <span style="font-size: 0.75rem; color: var(--text-dim);">${share}%</span>
                  </div>
                </td>
              </tr>
            `;
          }).join('');
        }
      } catch (e) {
        console.error('Failed to load analytics:', e);
      }
    }

    // --- 3-Cover High-CTR Studio Modal Logic ---
    async function openCoverThumbnailsModal(renderId) {
      openModal('modalCovers');
      const container = document.getElementById('coversGridContainer');
      container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem; color: #f59e0b;">Rendering 3 psychological cover styles with FFmpeg...</div>';

      try {
        const res = await fetch(`/api/renders/${renderId}/covers`);
        if (!res.ok) throw new Error('Cover generation failed');
        const data = await res.json();
        const covers = data.covers || [];

        container.innerHTML = covers.map(c => {
          const filename = c.path.split('/').pop().split('\\\\').pop();
          return `
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 0.85rem; display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <img src="/api/media/output/thumbnails/${filename}" style="width: 100%; border-radius: 8px; aspect-ratio: 9/16; object-fit: cover; margin-bottom: 0.75rem; border: 1px solid rgba(255,255,255,0.1);" alt="Cover Preview">
                <div style="font-weight: 700; font-size: 0.92rem; color: #fff; margin-bottom: 0.35rem;">${c.name}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); line-height: 1.4; margin-bottom: 0.5rem;">${c.description}</div>
              </div>
              <a href="/api/media/output/thumbnails/${filename}" download="${filename}" class="btn-primary" style="font-size: 0.8rem; text-decoration: none; text-align: center; display: block; padding: 0.45rem;">
                ⬇️ Download 9:16 JPEG
              </a>
            </div>
          `;
        }).join('');
      } catch (e) {
        container.innerHTML = `<div style="grid-column: 1 / -1; color: #ef4444; text-align: center; padding: 2rem;">Error generating covers: ${e.message}</div>`;
      }
    }

    // --- Multi-Platform Algorithm Copy Modal Logic ---
    async function openMultiPlatformExportModal(renderId, title, caption) {
      openModal('modalExport');
      const container = document.getElementById('exportTabsContainer');
      container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem; color: #818cf8;">Generating algorithm-tailored copy for Reels, Shorts & TikTok...</div>';

      try {
        const account = accountsCache.find(a => a.id === currentGlobalAccount) || accountsCache[0] || {};
        const niche = account.niche || 'Motivation';

        const res = await fetch('/api/export/multi-platform', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title || 'Viral Moment',
            hook_text: title || 'Watch this before it is too late',
            script_summary: caption || 'Key insights and takeaways for high impact',
            niche: niche
          })
        });

        const data = await res.json();
        container.innerHTML = `
          <!-- Instagram Reels -->
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 12px; padding: 1rem; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 1rem; color: #f43f5e; margin-bottom: 0.25rem;">📸 Instagram Reels</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem;">Optimized for save rate & shares</div>
              <textarea class="form-textarea" rows="8" style="font-size: 0.75rem; margin-bottom: 0.75rem; width: 100%;" readonly id="copyIg">${data.instagram.caption}</textarea>
            </div>
            <button class="btn-primary" style="background: #f43f5e; border: none; font-size: 0.8rem;" onclick="copyBoxText('copyIg', 'Instagram Caption')">📋 Copy Reels Package</button>
          </div>

          <!-- YouTube Shorts -->
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 1rem; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 1rem; color: #ef4444; margin-bottom: 0.25rem;">▶️ YouTube Shorts</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem;">Title &lt; 60 chars + High-CTR Pinned Comment</div>
              <div style="font-size: 0.72rem; color: var(--text-dim); margin-bottom: 2px;">SEO Title:</div>
              <input type="text" class="form-input" style="font-size: 0.78rem; font-weight: 700; margin-bottom: 0.5rem;" value="${data.youtube_shorts.title}" id="copyYtTitle" readonly>
              <div style="font-size: 0.72rem; color: var(--text-dim); margin-bottom: 2px;">Pinned Comment Prompt:</div>
              <textarea class="form-textarea" rows="4" style="font-size: 0.75rem; margin-bottom: 0.75rem; width: 100%;" readonly id="copyYtComment">${data.youtube_shorts.pinned_comment}</textarea>
            </div>
            <button class="btn-primary" style="background: #ef4444; border: none; font-size: 0.8rem;" onclick="copyBoxText('copyYtComment', 'YouTube Pinned Comment')">📋 Copy Pinned Comment</button>
          </div>

          <!-- TikTok -->
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: 12px; padding: 1rem; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 1rem; color: #06b6d4; margin-bottom: 0.25rem;">🎵 TikTok</div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem;">Ultra-short conversational hook caption</div>
              <textarea class="form-textarea" rows="8" style="font-size: 0.75rem; margin-bottom: 0.75rem; width: 100%;" readonly id="copyTikTok">${data.tiktok.caption}</textarea>
            </div>
            <button class="btn-primary" style="background: #06b6d4; border: none; font-size: 0.8rem;" onclick="copyBoxText('copyTikTok', 'TikTok Caption')">📋 Copy TikTok Package</button>
          </div>
        `;
      } catch (e) {
        container.innerHTML = `<div style="grid-column: 1 / -1; color: #ef4444; text-align: center; padding: 2rem;">Error formatting package: ${e.message}</div>`;
      }
    }

    function copyBoxText(elementId, label) {
      const el = document.getElementById(elementId);
      if (!el) return;
      navigator.clipboard.writeText(el.value);
      showToast(`Copied ${label} to clipboard!`);
    }

    // --- Ingest Mode Switcher ---
    function setIngestMode(mode) {
      const btnSingle = document.getElementById('btnModeSingle');
      const btnBatch = document.getElementById('btnModeBatch');
      const boxSingle = document.getElementById('containerSingleIngest');
      const boxBatch = document.getElementById('containerBatchIngest');
      if (mode === 'batch') {
        if (btnSingle) btnSingle.className = 'btn-secondary';
        if (btnBatch) btnBatch.className = 'btn-primary';
        if (boxSingle) boxSingle.style.display = 'none';
        if (boxBatch) boxBatch.style.display = 'block';
      } else {
        if (btnSingle) btnSingle.className = 'btn-primary';
        if (btnBatch) btnBatch.className = 'btn-secondary';
        if (boxSingle) boxSingle.style.display = 'block';
        if (boxBatch) boxBatch.style.display = 'none';
      }
    }

    // --- Autonomous Batch Playlist / Channel Ingest ---
    async function submitBatchPlaylistJob() {
      const input = document.getElementById('batchPlaylistInput');
      const url = input ? input.value.trim() : '';
      if (!url) {
        showToast('Please enter a YouTube playlist or channel URL');
        return;
      }
      const maxItems = parseInt(document.getElementById('batchMaxItems').value) || 5;
      const minDur = parseFloat(document.getElementById('batchMinDuration').value) || 60;
      const maxDur = parseFloat(document.getElementById('batchMaxDuration').value) || 1800;
      const accountId = (currentGlobalAccount && currentGlobalAccount !== 'all') ? currentGlobalAccount : 'acc_motivation';

      const resultBox = document.getElementById('batchIngestResult');
      resultBox.style.display = 'block';
      resultBox.innerHTML = '<span style="color: #818cf8;">Crawling playlist metadata via flat inspection (no large downloads upfront)...</span>';

      try {
        const res = await fetch('/api/jobs/batch-playlist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            playlist_url: url,
            account_id: accountId,
            max_items: maxItems,
            min_duration_sec: minDur,
            max_duration_sec: maxDur
          })
        });
        const data = await res.json();
        if (res.ok) {
          resultBox.innerHTML = `<span style="color: #10b981; font-weight: 600;">✓ Discovered ${data.total_discovered} videos. Enqueued ${data.queued_count} new jobs (${data.skipped_count} skipped/duplicates).</span>`;
          showToast(`Enqueued ${data.queued_count} batch jobs successfully!`);
          input.value = '';
          loadOverview();
        } else {
          resultBox.innerHTML = `<span style="color: #ef4444;">Error: ${data.detail || 'Batch ingest failed'}</span>`;
        }
      } catch (err) {
        resultBox.innerHTML = `<span style="color: #ef4444;">Network error: ${err.message}</span>`;
      }
    }

    // --- Watermark Video Hero Action ---
    async function applyWatermarkHero(renderId, videoPath, accountId) {
      showToast('Burning account watermark pill with hardware acceleration...');
      try {
        const acc = accountsCache.find(a => a.id === accountId) || {};
        const handle = acc.instagram_username ? `@${acc.instagram_username}` : `@${accountId.replace('acc_', '')}`;
        const res = await fetch('/api/watermark/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_path: videoPath,
            handle: handle,
            position: 'top_right',
            opacity: 0.75
          })
        });
        const data = await res.json();
        if (res.ok) {
          showToast('Account watermark burned successfully!');
          loadOverview();
        } else {
          showToast(`Watermark failed: ${data.detail || 'Error'}`);
        }
      } catch (e) {
        showToast(`Watermark failed: ${e.message}`);
      }
    }

    // --- Hardware Acceleration Auto-Negotiation Status ---
    async function checkHardwareAccel() {
      try {
        const res = await fetch('/api/system/hardware');
        if (res.ok) {
          const hw = await res.json();
          const badge = document.getElementById('hwAccelText');
          if (badge) {
            badge.innerText = hw.hw ? `${hw.device}` : 'CPU (libx264)';
          }
        }
      } catch (e) {
        console.warn('HW probe failed:', e);
      }
    }

    // --- Instagram Insights Telemetry ---
    async function loadInstagramInsights() {
      const accountId = (currentGlobalAccount && currentGlobalAccount !== 'all') ? currentGlobalAccount : 'acc_motivation';
      try {
        const res = await fetch(`/api/insights/${accountId}`);
        if (!res.ok) return;
        const data = await res.json();

        const pCount = document.getElementById('igMetricPosts');
        const vCount = document.getElementById('igMetricViews');
        const iCount = document.getElementById('igMetricInteractions');
        const rCount = document.getElementById('igMetricRetention');
        const tbl = document.getElementById('igInsightsTableContainer');

        if (pCount) pCount.innerText = data.total_tracked_posts || 0;
        if (vCount) vCount.innerText = (data.aggregates?.total_views || 0).toLocaleString();
        if (iCount) {
          const totalInt = (data.aggregates?.total_likes || 0) + (data.aggregates?.total_comments || 0) + (data.aggregates?.total_shares || 0);
          iCount.innerText = totalInt.toLocaleString();
        }
        if (rCount) rCount.innerText = (data.aggregates?.avg_retention_rate || 0) + '%';

        if (tbl && data.history && data.history.length > 0) {
          tbl.innerHTML = `
            <div style="font-weight: 700; margin-bottom: 0.5rem; color: #cbd5e1;">Recent Posts Performance History:</div>
            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem;">
                <thead>
                  <tr style="border-bottom: 1px solid rgba(255,255,255,0.08); text-align: left; color: var(--text-dim);">
                    <th style="padding: 0.4rem;">Post ID</th>
                    <th style="padding: 0.4rem;">Views</th>
                    <th style="padding: 0.4rem;">Likes</th>
                    <th style="padding: 0.4rem;">Comments</th>
                    <th style="padding: 0.4rem;">Shares</th>
                    <th style="padding: 0.4rem;">Retention</th>
                    <th style="padding: 0.4rem;">Recorded</th>
                  </tr>
                </thead>
                <tbody>
                  ${data.history.slice(0, 5).map(h => `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
                      <td style="padding: 0.4rem; font-family: monospace;">#${h.publishing_id}</td>
                      <td style="padding: 0.4rem; color: #60a5fa; font-weight: 600;">${h.views.toLocaleString()}</td>
                      <td style="padding: 0.4rem;">${h.likes.toLocaleString()}</td>
                      <td style="padding: 0.4rem;">${h.comments.toLocaleString()}</td>
                      <td style="padding: 0.4rem;">${h.shares.toLocaleString()}</td>
                      <td style="padding: 0.4rem; color: #34d399; font-weight: 600;">${h.retention_rate}%</td>
                      <td style="padding: 0.4rem; color: var(--text-dim);">${h.recorded_at ? h.recorded_at.split('T')[0] : 'Today'}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `;
        } else if (tbl) {
          tbl.innerHTML = '<div style="color: var(--text-dim); padding: 0.5rem 0;">No published posts tracked yet for this account. Approve and publish a draft to view telemetry feedback.</div>';
        }
      } catch (e) {
        console.error('Failed to load insights:', e);
      }
    }

    // --- Executive Weekly Media Factory Report Export ---
    async function downloadExecutiveReport() {
      showToast('Generating executive weekly media factory report...');
      try {
        const accountId = (currentGlobalAccount && currentGlobalAccount !== 'all') ? currentGlobalAccount : 'all';
        const res = await fetch(`/api/reports/weekly?account_id=${accountId}`);
        if (!res.ok) throw new Error('Failed to generate report');
        const data = await res.json();
        const blob = new Blob([data.markdown_report], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `VedioHooks_Weekly_Executive_Report_${accountId}_${data.generated_at}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Executive report downloaded successfully!');
      } catch (e) {
        showToast('Report export failed: ' + e.message);
      }
    }

    // --- Dynamic Auto-Zoom (Punch Cuts) ---
    async function applyAutoZoomHero(renderId, videoPath) {
      showToast('Applying dynamic 1.16x punch-cut auto-zoom...');
      try {
        const res = await fetch('/api/video/auto-zoom', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ video_path: videoPath, zoom_scale: 1.16 })
        });
        if (!res.ok) throw new Error('Auto-zoom failed');
        const data = await res.json();
        const filename = data.output_path.split('/').pop().split('\\\\').pop();
        showToast(`Auto-zoom complete (${data.punch_cuts_count} punch cuts added)!`);
        const player = document.getElementById(`video-hero-${renderId}`);
        if (player) {
          player.src = `/api/media/output/${filename}`;
          player.play();
        }
      } catch (e) {
        showToast('Auto-zoom error: ' + e.message);
      }
    }

    // --- Top Hook Header Banner Studio Modal ---
    function openHookBannerModal(renderId, videoPath, defaultTitle) {
      document.getElementById('modalHookBannerRenderId').value = renderId;
      document.getElementById('modalHookBannerVideoPath').value = videoPath;
      const cleanTitle = (defaultTitle || 'VIRAL MOMENT').toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').trim();
      document.getElementById('modalHookBannerText').value = cleanTitle.substring(0, 42);
      openModal('modalHookBanner');
    }

    async function submitHookBannerBurn() {
      const renderId = document.getElementById('modalHookBannerRenderId').value;
      const videoPath = document.getElementById('modalHookBannerVideoPath').value;
      const hookText = document.getElementById('modalHookBannerText').value.trim();
      const theme = document.getElementById('modalHookBannerTheme').value;
      const durationSec = parseFloat(document.getElementById('modalHookBannerDuration').value) || 3.5;

      if (!hookText) {
        alert('Please enter a banner headline text');
        return;
      }

      closeModal('modalHookBanner');
      showToast('Burning high-contrast top hook banner onto short...');
      try {
        const res = await fetch('/api/video/hook-banner', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_path: videoPath,
            hook_text: hookText,
            theme: theme,
            duration_sec: durationSec
          })
        });
        if (!res.ok) throw new Error('Hook banner failed');
        const data = await res.json();
        const filename = data.output_path.split('/').pop().split('\\\\').pop();
        showToast('Top hook header banner applied successfully!');
        const player = document.getElementById(`video-hero-${renderId}`);
        if (player) {
          player.src = `/api/media/output/${filename}`;
          player.play();
        }
      } catch (e) {
        showToast('Hook banner error: ' + e.message);
      }
    }

    // =====================================================================
    // --- SERIES STUDIO (AI CLIFFHANGER SERIES ENGINE) CLIENT LOGIC ---
    // =====================================================================
    let seriesListCache = [];
    let currentActiveSeries = null;
    let selectedStoryArc = null;
    let candidateArcsCache = [];
    let seriesJobsCache = [];

    function toggleSeriesCreatorModal(open) {
      const modal = document.getElementById('seriesCreatorModal');
      if (modal) modal.style.display = open ? 'block' : 'none';
      if (open) {
        populateSeriesJobs();
        onSeriesModeChanged();
      }
    }

    async function populateSeriesJobs() {
      try {
        const res = await fetch('/api/jobs?limit=50');
        const data = await res.json();
        seriesJobsCache = data.jobs || [];
        const select = document.getElementById('seriesSourceJobSelect');
        if (!select) return;
        const validJobs = seriesJobsCache.filter(j => j.status === 'ready' || j.status === 'completed' || j.transcript_json_path);
        select.innerHTML = '<option value="">-- Choose a Transcribed Video --</option>' +
          (validJobs.length > 0 ? validJobs.map(j => `<option value="${j.id}">${j.title || j.id} (${j.duration ? j.duration.toFixed(0) + 's' : ''})</option>`).join('')
                                : seriesJobsCache.map(j => `<option value="${j.id}">${j.title || j.id} [${j.status}]</option>`).join(''));
      } catch (err) {
        console.error('Failed to populate series source jobs:', err);
      }
    }

    function onSeriesModeChanged() {
      const mode = document.getElementById('seriesGenModeSelect').value;
      const customOpts = document.getElementById('seriesCustomOptions');
      const guidedContainer = document.getElementById('seriesGuidedContainer');
      
      if (customOpts) customOpts.style.display = (mode === 'custom') ? 'grid' : 'none';
      if (guidedContainer) guidedContainer.style.display = (mode === 'guided') ? 'block' : 'none';
    }

    function onSeriesJobSelected() {
      const jobId = document.getElementById('seriesSourceJobSelect').value;
      const job = seriesJobsCache.find(j => j.id === jobId);
      if (job && job.duration) {
        const endInput = document.getElementById('seriesCustomEnd');
        if (endInput) endInput.value = Math.min(job.duration, 180.0).toFixed(0);
      }
    }

    async function triggerAnalyzeStoryArcs() {
      const jobId = document.getElementById('seriesSourceJobSelect').value;
      if (!jobId) {
        alert('Please select a source video first.');
        return;
      }
      const btn = document.getElementById('btnAnalyzeArcs');
      const container = document.getElementById('guidedArcsList');
      btn.disabled = true;
      btn.textContent = '⏳ Analyzing Transcript...';
      container.innerHTML = '<div style="color: var(--primary); text-align: center; padding: 1rem;">Analyzing narrative arcs, emotional tension, and Q&A blocks...</div>';

      try {
        const res = await fetch('/api/series/analyze-arcs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: jobId })
        });
        if (!res.ok) throw new Error('Failed to analyze story arcs');
        const data = await res.json();
        candidateArcsCache = data.story_arcs || [];
        renderCandidateArcs(candidateArcsCache);
      } catch (err) {
        container.innerHTML = `<div style="color: #fb7185; padding: 1rem;">Failed to analyze arcs: ${err.message}</div>`;
      } finally {
        btn.disabled = false;
        btn.textContent = '🔍 Analyze Video for Arcs';
      }
    }

    function renderCandidateArcs(arcs) {
      const container = document.getElementById('guidedArcsList');
      if (!arcs || arcs.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); padding: 1rem;">No arcs detected in video. Try Auto Series.</div>';
        return;
      }
      container.innerHTML = arcs.map((arc, idx) => `
        <div style="background: rgba(0,0,0,0.3); border: 1px solid ${selectedStoryArc && selectedStoryArc.story_id === arc.story_id ? 'var(--primary)' : 'var(--border)'}; border-radius: var(--radius-sm); padding: 1rem; cursor: pointer;" onclick="selectArcForGeneration('${arc.story_id}')">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-weight: 700; color: #fff; font-size: 0.95rem;">${arc.title}</div>
            <span class="badge" style="background: rgba(163, 230, 53, 0.2); color: var(--primary);">${arc.recommended_episodes} Episodes recommended</span>
          </div>
          <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.35rem;">${arc.description}</div>
          <div style="margin-top: 0.5rem; font-size: 0.75rem; color: var(--text-dim); display: flex; gap: 1rem;">
            <span><strong>Turning Point:</strong> ${arc.turning_point ? arc.turning_point.substring(0, 70) + '...' : 'N/A'}</span>
            <span><strong>Resolution:</strong> ${arc.resolution ? arc.resolution.substring(0, 70) + '...' : 'N/A'}</span>
          </div>
          <button class="btn-secondary" style="margin-top: 0.75rem; font-size: 0.78rem; padding: 0.25rem 0.65rem;" onclick="selectArcForGeneration('${arc.story_id}'); event.stopPropagation();">
            ${selectedStoryArc && selectedStoryArc.story_id === arc.story_id ? '✓ Selected' : 'Choose this Story Arc'}
          </button>
        </div>
      `).join('');
    }

    function selectArcForGeneration(arcId) {
      selectedStoryArc = candidateArcsCache.find(a => a.story_id === arcId);
      renderCandidateArcs(candidateArcsCache);
    }

    async function executeGenerateSeries() {
      const jobId = document.getElementById('seriesSourceJobSelect').value;
      if (!jobId) {
        alert('Please choose a transcribed video job.');
        return;
      }
      const mode = document.getElementById('seriesGenModeSelect').value;
      const accountId = document.getElementById('seriesAccountSelect').value;
      const epCount = parseInt(document.getElementById('seriesEpisodeCount')?.value || '3', 10);
      const customStart = parseFloat(document.getElementById('seriesCustomStart')?.value || '0');
      const customEnd = parseFloat(document.getElementById('seriesCustomEnd')?.value || '180');

      const btn = document.getElementById('btnExecuteSeriesGen');
      btn.disabled = true;
      btn.textContent = '⚡ Formulating Episodic Series...';

      const payload = {
        job_id: jobId,
        account_id: accountId,
        generation_mode: mode
      };
      if (mode === 'guided' && selectedStoryArc) {
        payload.story_arc = selectedStoryArc;
        payload.episode_count = selectedStoryArc.recommended_episodes;
      } else if (mode === 'custom') {
        payload.custom_start_sec = customStart;
        payload.custom_end_sec = customEnd;
        payload.episode_count = epCount;
      }

      try {
        const res = await fetch('/api/series/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Generation failed');
        }
        const createdSeries = await res.json();
        toggleSeriesCreatorModal(false);
        await loadSeriesStudio();
        openSeriesDetails(createdSeries.id);
      } catch (err) {
        alert('Failed to generate series: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Generate AI Series';
      }
    }

    async function loadSeriesStudio() {
      try {
        const statusFilter = document.getElementById('seriesStatusFilter')?.value || 'all';
        const currentAccount = document.getElementById('globalAccountSelect')?.value || 'all';
        let url = `/api/series?limit=50`;
        if (statusFilter !== 'all') url += `&status=${statusFilter}`;
        if (currentAccount !== 'all') url += `&account_id=${currentAccount}`;

        const res = await fetch(url);
        const data = await res.json();
        seriesListCache = data.series || [];
        renderSeriesLibrary(seriesListCache);
        populateSeriesJobs();
      } catch (err) {
        console.error('Failed to load series library:', err);
      }
    }

    function renderSeriesLibrary(seriesList) {
      const container = document.getElementById('seriesGridContainer');
      if (!container) return;

      if (!seriesList || seriesList.length === 0) {
        container.innerHTML = `
          <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted); border: 1px dashed var(--border); border-radius: var(--radius-md);">
            <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">🎬</div>
            <div style="font-size: 1.15rem; font-weight: 700; color: #fff;">No AI Series Generated Yet</div>
            <p style="margin-top: 0.25rem;">Transform any long-form video into an interconnected, binge-worthy cliffhanger series.</p>
            <button class="btn-primary" style="margin-top: 1rem;" onclick="toggleSeriesCreatorModal(true)">+ Create First AI Series</button>
          </div>
        `;
        return;
      }

      container.innerHTML = seriesList.map(s => {
        const modeClass = s.generation_mode || 'auto';
        const renderedCount = s.rendered_episodes_count || 0;
        const totalCount = s.actual_episodes_count || s.episode_count || 0;
        const qScore = s.quality_score || 85;

        return `
          <div class="series-card" onclick="openSeriesDetails('${s.id}')">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
              <span class="series-badge ${modeClass}">${(s.generation_mode || 'AUTO').toUpperCase()}</span>
              <span class="badge" style="${s.status === 'completed' ? 'background: rgba(52, 211, 153, 0.2); color: #34d399;' : 'background: rgba(163, 230, 53, 0.15); color: var(--primary);'}">${s.status.toUpperCase()}</span>
            </div>
            <div>
              <div style="font-weight: 800; font-size: 1.05rem; color: #fff; line-height: 1.3;">${s.title}</div>
              <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${s.description || 'Interconnected multi-episode short series with cliffhangers.'}</div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.75rem; background: rgba(0,0,0,0.25); border-radius: var(--radius-sm); font-size: 0.8rem;">
              <div>
                <span style="color: var(--text-dim);">Episodes:</span>
                <strong style="color: #fff;"> ${renderedCount}/${totalCount} Rendered</strong>
              </div>
              <div style="display: flex; align-items: center; gap: 0.35rem;">
                <span style="color: var(--text-dim);">Quality:</span>
                <span style="font-weight: 800; color: ${qScore >= 85 ? 'var(--primary)' : 'var(--amber)'};">${qScore}/100</span>
              </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 0.5rem;">
              <span style="font-size: 0.72rem; color: var(--text-dim);">${s.source_video_title ? s.source_video_title.substring(0, 24) + '...' : 'Source Video'}</span>
              <button class="btn-secondary" style="font-size: 0.78rem; padding: 0.3rem 0.65rem;" onclick="openSeriesDetails('${s.id}'); event.stopPropagation();">
                Open Studio →
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    async function openSeriesDetails(seriesId) {
      try {
        const res = await fetch(`/api/series/${seriesId}`);
        if (!res.ok) throw new Error('Series not found');
        currentActiveSeries = await res.json();

        // Switch to detail view
        document.getElementById('seriesLibraryContainer').style.display = 'none';
        document.getElementById('seriesCreatorModal').style.display = 'none';
        document.getElementById('seriesStudioDetailView').style.display = 'block';

        renderActiveSeriesStudio(currentActiveSeries);
      } catch (err) {
        alert('Failed to load series details: ' + err.message);
      }
    }

    function closeSeriesDetailView() {
      document.getElementById('seriesStudioDetailView').style.display = 'none';
      document.getElementById('seriesLibraryContainer').style.display = 'block';
      loadSeriesStudio();
    }

    function renderActiveSeriesStudio(s) {
      document.getElementById('activeSeriesTitle').textContent = s.title;
      const badge = document.getElementById('activeSeriesBadge');
      badge.className = `series-badge ${s.generation_mode || 'auto'}`;
      badge.textContent = (s.generation_mode || 'AUTO').toUpperCase();

      document.getElementById('activeSeriesStatus').textContent = s.status.toUpperCase();

      // Render Narrative Arc
      const arc = s.story_arc || {};
      document.getElementById('arcBeginningText').textContent = arc.beginning ? arc.beginning.substring(0, 110) + '...' : 'Status quo setup...';
      document.getElementById('arcConflictText').textContent = arc.conflict_or_central_question ? arc.conflict_or_central_question.substring(0, 110) + '...' : 'Core tension...';
      document.getElementById('arcTurningPointText').textContent = arc.turning_point ? arc.turning_point.substring(0, 110) + '...' : 'Dramatic shift...';
      document.getElementById('arcResolutionText').textContent = arc.resolution ? arc.resolution.substring(0, 110) + '...' : 'Full payoff...';

      // Series Memory
      const mem = s.series_memory || {};
      const memText = mem.current_tension || (mem.unresolved_questions && mem.unresolved_questions.length > 0 ? `Unresolved: ${mem.unresolved_questions[0]}` : 'Continuity coherent.');
      document.getElementById('seriesMemoryTensionText').textContent = memText;

      const unrenderedCount = (s.episodes || []).filter(e => e.render_status !== 'ready').length;
      document.getElementById('unrenderedCountBadge').textContent = unrenderedCount;

      renderVisualTimeline(s);
      renderEpisodesEditorList(s);
    }

    function renderVisualTimeline(s) {
      const flow = document.getElementById('visualTimelineFlow');
      const eps = s.episodes || [];
      if (!flow) return;

      flow.innerHTML = eps.map((ep, idx) => {
        const isFinal = (idx === eps.length - 1);
        const isReady = ep.render_status === 'ready';
        const cliffScore = ep.cliffhanger_score || 80;

        let bridgeHtml = '';
        if (!isFinal) {
          bridgeHtml = `
            <div class="timeline-bridge">
              <span class="cliffhanger-pill" title="${ep.cliffhanger_text || 'Cliffhanger'}">
                ⚡ ${ep.cliffhanger_type || 'Cliffhanger'} (${cliffScore})
              </span>
              <div class="timeline-arrow"></div>
            </div>
          `;
        }

        return `
          <div class="timeline-node ${isFinal ? 'final' : ''}" onclick="scrollToEpisodeCard(${ep.id})">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
              <strong style="color: ${isFinal ? '#34d399' : 'var(--primary)'}; font-size: 0.85rem;">Part ${ep.episode_number} ${isFinal ? '[FINAL]' : ''}</strong>
              <span class="badge" style="font-size: 0.65rem; padding: 0.1rem 0.4rem; ${isReady ? 'background: rgba(52, 211, 153, 0.2); color: #34d399;' : ''}">${isReady ? 'RENDERED' : 'PENDING'}</span>
            </div>
            <div style="font-size: 0.78rem; font-weight: 700; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${ep.title}</div>
            <div style="font-size: 0.7rem; color: var(--text-dim); margin-top: 0.25rem;">${ep.start_time.toFixed(1)}s → ${ep.end_time.toFixed(1)}s (${ep.duration.toFixed(1)}s)</div>
          </div>
          ${bridgeHtml}
        `;
      }).join('');
    }

    function renderEpisodesEditorList(s) {
      const list = document.getElementById('activeEpisodesList');
      const eps = s.episodes || [];
      if (!list) return;

      list.innerHTML = eps.map((ep, idx) => {
        const isFinal = (idx === eps.length - 1);
        const isReady = (ep.render_status === 'ready' && ep.rendered_video_path);

        return `
          <div class="episode-editor-card ${isFinal ? 'final' : ''}" id="epCard_${ep.id}">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.75rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.1rem; font-weight: 800; color: ${isFinal ? '#34d399' : 'var(--primary)'};">Part ${ep.episode_number}</span>
                <input type="text" id="epTitle_${ep.id}" class="form-input" style="font-weight: 700; font-size: 0.95rem; width: 280px;" value="${ep.title}">
                ${isFinal ? '<span class="badge" style="background: rgba(52,211,153,0.2); color: #34d399;">Story Resolution</span>' : ''}
              </div>
              <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span style="font-size: 0.78rem; color: var(--text-dim);">Quality:</span>
                <span class="badge" style="background: rgba(163, 230, 53, 0.15); color: var(--primary); font-weight: 800;">${ep.quality_score || 85}/100</span>
                <span class="badge" style="${isReady ? 'background: rgba(52, 211, 153, 0.2); color: #34d399;' : ''}">${ep.render_status.toUpperCase()}</span>
              </div>
            </div>

            <!-- Hook & Timing -->
            <div class="grid-2" style="gap: 1rem;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                  <label class="form-label" style="margin: 0;">Opening Hook (First 1-3s)</label>
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.15rem 0.45rem;" onclick="regenerateEpisodeHook(${ep.id})">✨ Regenerate Hook</button>
                </div>
                <input type="text" id="epHook_${ep.id}" class="form-input" value="${ep.opening_hook || ''}">
              </div>
              <div>
                <label class="form-label">Clip Timestamps (Source Video Alignment)</label>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                  <input type="number" id="epStart_${ep.id}" class="form-input" value="${ep.start_time.toFixed(1)}" step="0.5" style="width: 100px;">
                  <span style="color: var(--text-dim);">to</span>
                  <input type="number" id="epEnd_${ep.id}" class="form-input" value="${ep.end_time.toFixed(1)}" step="0.5" style="width: 100px;">
                  <span style="color: var(--text-dim); font-size: 0.8rem;">(${ep.duration.toFixed(1)}s)</span>
                  <button class="btn-secondary" style="font-size: 0.72rem; padding: 0.4rem 0.65rem;" onclick="saveEpisodeEdits(${ep.id})">💾 Save</button>
                </div>
              </div>
            </div>

            <!-- Cliffhanger Intelligence Card -->
            <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.85rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <span style="font-size: 0.82rem; font-weight: 700; color: #fff;">${isFinal ? '🏆 Final Story Resolution' : '⚡ Cliffhanger Ending'}</span>
                  <span class="cliffhanger-pill" style="max-width: 200px;">${ep.cliffhanger_type || 'Curiosity Gap'} (${ep.cliffhanger_score || 80}/100)</span>
                </div>
                ${!isFinal ? `<button class="btn-secondary" style="font-size: 0.72rem; padding: 0.15rem 0.45rem;" onclick="regenerateEpisodeCliffhanger(${ep.id})">🧠 Re-evaluate Cliffhanger</button>` : ''}
              </div>
              <textarea id="epCliff_${ep.id}" class="form-input" rows="2" style="font-size: 0.82rem; resize: vertical;">${ep.cliffhanger_text || ''}</textarea>
              ${!isFinal ? `
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem;">
                  <span style="font-size: 0.75rem; color: var(--text-dim); flex-shrink: 0;">Next Episode Teaser:</span>
                  <input type="text" id="epTeaser_${ep.id}" class="form-input" style="font-size: 0.78rem;" value="${ep.next_teaser || ''}">
                </div>
              ` : ''}
            </div>

            <!-- Operations Bar -->
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.25rem;">
              <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
                <button class="btn-primary" style="font-size: 0.8rem; padding: 0.4rem 0.85rem;" onclick="renderSingleEpisode(${ep.id})">
                  ${isReady ? '🔄 Re-render 9:16 Short' : '▶ Render 9:16 Short'}
                </button>
                ${isReady ? `
                  <button class="btn-secondary" style="font-size: 0.8rem; padding: 0.4rem 0.85rem;" onclick="previewEpisodeVideo('${ep.rendered_video_path}', 'Part ${ep.episode_number}: ${ep.title}')">
                    👁 Preview 9:16 Short
                  </button>
                  <a href="/${ep.rendered_video_path}" download class="btn-secondary" style="font-size: 0.8rem; padding: 0.4rem 0.85rem; text-decoration: none;">
                    ⬇ Download Short
                  </a>
                ` : ''}
              </div>
              <div style="display: flex; gap: 0.4rem; align-items: center;">
                <button class="btn-secondary" style="font-size: 0.75rem;" onclick="splitEpisodePrompt(${ep.id}, ${ep.start_time}, ${ep.end_time})">✂ Split</button>
                ${idx < eps.length - 1 ? `<button class="btn-secondary" style="font-size: 0.75rem;" onclick="mergeEpisodePrompt(${ep.id}, ${eps[idx + 1].id})">🔗 Merge Next</button>` : ''}
                ${eps.length > 2 ? `<button class="btn-danger" style="font-size: 0.75rem; background: rgba(244, 63, 94, 0.12); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3);" onclick="deleteEpisodePrompt(${ep.id})">🗑</button>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function scrollToEpisodeCard(epId) {
      const card = document.getElementById(`epCard_${epId}`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.style.borderColor = 'var(--primary)';
        setTimeout(() => { card.style.borderColor = 'var(--border)'; }, 1500);
      }
    }

    async function saveEpisodeEdits(epId) {
      const title = document.getElementById(`epTitle_${epId}`)?.value;
      const hook = document.getElementById(`epHook_${epId}`)?.value;
      const startT = parseFloat(document.getElementById(`epStart_${epId}`)?.value || '0');
      const endT = parseFloat(document.getElementById(`epEnd_${epId}`)?.value || '30');
      const cliff = document.getElementById(`epCliff_${epId}`)?.value;
      const teaser = document.getElementById(`epTeaser_${epId}`)?.value;

      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/episodes/${epId}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title,
            opening_hook: hook,
            start_time: startT,
            end_time: endT,
            cliffhanger_text: cliff,
            next_teaser: teaser
          })
        });
        if (!res.ok) throw new Error('Update failed');
        openSeriesDetails(currentActiveSeries.id);
      } catch (err) {
        alert('Failed to save episode edits: ' + err.message);
      }
    }

    async function regenerateEpisodeHook(epId) {
      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/episodes/${epId}/regenerate-hook`, {
          method: 'POST'
        });
        if (!res.ok) throw new Error('Failed to regenerate hook');
        const data = await res.json();
        const input = document.getElementById(`epHook_${epId}`);
        if (input) input.value = data.opening_hook;
      } catch (err) {
        alert(err.message);
      }
    }

    async function regenerateEpisodeCliffhanger(epId) {
      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/episodes/${epId}/regenerate-cliffhanger`, {
          method: 'POST'
        });
        if (!res.ok) throw new Error('Failed to re-evaluate cliffhanger');
        const data = await res.json();
        const input = document.getElementById(`epCliff_${epId}`);
        if (input) input.value = data.cliffhanger_text;
        openSeriesDetails(currentActiveSeries.id);
      } catch (err) {
        alert(err.message);
      }
    }

    async function renderSingleEpisode(epId) {
      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/render-episode/${epId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ crop_mode: 'smart_face', theme: 'hormozi_yellow' })
        });
        if (!res.ok) throw new Error('Render failed');
        alert('Rendering started in background. The status will update automatically upon completion.');
        setTimeout(() => openSeriesDetails(currentActiveSeries.id), 2500);
      } catch (err) {
        alert('Failed to start render: ' + err.message);
      }
    }

    async function batchRenderActiveSeries() {
      if (!currentActiveSeries) return;
      if (!confirm(`Batch render all ${currentActiveSeries.episode_count} episodes with face tracking and dynamic subtitles?`)) return;

      const btn = document.getElementById('btnBatchRenderActive');
      btn.disabled = true;
      btn.textContent = '⏳ Batch Rendering...';

      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/batch-render`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ crop_mode: 'smart_face', theme: 'hormozi_yellow' })
        });
        if (!res.ok) throw new Error('Batch render failed');
        alert('Batch rendering initiated for all episodes. Telemetry will sync continuously.');
        setTimeout(() => openSeriesDetails(currentActiveSeries.id), 3000);
      } catch (err) {
        alert('Batch render failed: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = '▶ Batch Render All';
      }
    }

    async function exportActiveSeriesPackage() {
      if (!currentActiveSeries) return;
      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/export`);
        const payload = await res.json();
        const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(payload, null, 2));
        const dlAnchor = document.createElement('a');
        dlAnchor.setAttribute('href', dataStr);
        dlAnchor.setAttribute('download', `${currentActiveSeries.title.replace(/[^a-zA-Z0-9_-]/g, '_')}_series_package.json`);
        document.body.appendChild(dlAnchor);
        dlAnchor.click();
        dlAnchor.remove();
      } catch (err) {
        alert('Export failed: ' + err.message);
      }
    }

    async function deleteActiveSeries() {
      if (!currentActiveSeries) return;
      if (!confirm(`Permanently delete the entire series "${currentActiveSeries.title}"?`)) return;

      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Delete failed');
        closeSeriesDetailView();
      } catch (err) {
        alert('Failed to delete series: ' + err.message);
      }
    }

    async function splitEpisodePrompt(epId, startT, endT) {
      const mid = ((startT + endT) / 2).toFixed(1);
      const splitTimeStr = prompt(`Enter split timestamp in seconds (between ${startT.toFixed(1)}s and ${endT.toFixed(1)}s):`, mid);
      if (!splitTimeStr) return;
      const splitTime = parseFloat(splitTimeStr);
      if (isNaN(splitTime) || splitTime <= startT || splitTime >= endT) {
        alert('Invalid split timestamp.');
        return;
      }

      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/episodes/${epId}/split`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ split_time: splitTime })
        });
        if (!res.ok) throw new Error('Split failed');
        openSeriesDetails(currentActiveSeries.id);
      } catch (err) {
        alert(err.message);
      }
    }

    async function mergeEpisodePrompt(ep1Id, ep2Id) {
      if (!confirm('Merge this episode with the next episode into a single longer video?')) return;
      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/episodes/merge`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ep1_id: ep1Id, ep2_id: ep2Id })
        });
        if (!res.ok) throw new Error('Merge failed');
        openSeriesDetails(currentActiveSeries.id);
      } catch (err) {
        alert(err.message);
      }
    }

    async function deleteEpisodePrompt(epId) {
      if (!confirm('Remove this episode from the series and renumber the rest?')) return;
      try {
        const res = await fetch(`/api/series/${currentActiveSeries.id}/episodes/${epId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Delete failed');
        openSeriesDetails(currentActiveSeries.id);
      } catch (err) {
        alert(err.message);
      }
    }

    async function regenerateActiveSeriesPrompt() {
      if (!currentActiveSeries) return;
      if (!confirm('Regenerate entire story arc, boundaries, hooks, and cliffhangers from source video?')) return;
      try {
        const res = await fetch('/api/series/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: currentActiveSeries.job_id,
            account_id: currentActiveSeries.account_id,
            generation_mode: currentActiveSeries.generation_mode || 'auto'
          })
        });
        if (!res.ok) throw new Error('Regeneration failed');
        const newSeries = await res.json();
        openSeriesDetails(newSeries.id);
      } catch (err) {
        alert(err.message);
      }
    }

    function previewEpisodeVideo(videoPath, title) {
      const modal = document.getElementById('episodePreviewModal');
      const video = document.getElementById('previewModalVideo');
      const modalTitle = document.getElementById('previewModalTitle');
      if (modal && video) {
        modalTitle.textContent = title || 'Episode Preview';
        video.src = `/${videoPath}`;
        video.play().catch(() => {});
        modal.style.display = 'flex';
      }
    }

    function closeEpisodePreviewModal() {
      const modal = document.getElementById('episodePreviewModal');
      const video = document.getElementById('previewModalVideo');
      if (modal && video) {
        video.pause();
        video.src = '';
        modal.style.display = 'none';
      }
    }

    // =====================================================================
    // --- CLIENT-SIDE JS: AI METADATA STUDIO ---
    // =====================================================================

    let activeMetadataCache = null;
    let currentMetadataPlatform = 'youtube';

    async function loadMetadataStudio() {
      try {
        const select = document.getElementById('metaTargetSelect');
        if (!select) return;

        // Fetch rendered shorts and series episodes
        const [shortsRes, seriesRes] = await Promise.all([
          fetch('/api/renders?limit=100').then(r => r.json()).catch(() => ({ renders: [] })),
          fetch('/api/series?limit=50').then(r => r.json()).catch(() => ({ series: [] }))
        ]);

        const prevVal = select.value;
        let html = '<option value="">-- Choose Short or Series Episode --</option>';

        const rendersList = (shortsRes.renders || shortsRes.shorts || []);
        if (rendersList.length > 0) {
          html += '<optgroup label="🎬 Viral 9:16 Shorts">';
          rendersList.forEach(s => {
            html += `<option value="short:${s.id}">Short #${s.id} — ${s.title || 'Viral Clip'}</option>`;
          });
          html += '</optgroup>';
        }

        if (seriesRes.series && seriesRes.series.length > 0) {
          html += '<optgroup label="📺 Cliffhanger Series Episodes">';
          seriesRes.series.forEach(ser => {
            if (ser.episodes && ser.episodes.length > 0) {
              ser.episodes.forEach(ep => {
                html += `<option value="episode:${ep.id}">${ser.title} [Part ${ep.episode_number}] — ${ep.title}</option>`;
              });
            }
          });
          html += '</optgroup>';
        }

        select.innerHTML = html;
        if (prevVal && [...select.options].some(o => o.value === prevVal)) {
          select.value = prevVal;
        } else if (select.options.length > 1) {
          select.selectedIndex = 1;
        }
        await onMetadataTargetChanged();
      } catch (err) {
        console.error('Failed to load Metadata Studio targets:', err);
      }
    }

    async function onMetadataTargetChanged() {
      const select = document.getElementById('metaTargetSelect');
      if (!select || !select.value) return;
      const [targetType, targetId] = select.value.split(':');
      try {
        const res = await fetch(`/api/metadata/${targetType}/${targetId}`);
        const data = await res.json();
        if (data.success && data.metadata) {
          activeMetadataCache = data.metadata;
          populateMetadataFields(data.metadata);
        }
      } catch (err) {
        console.error('Error fetching metadata:', err);
      }
    }

    function onMetadataNicheChanged() {
      const nicheSelect = document.getElementById('metaNicheSelect');
      const niche = nicheSelect ? nicheSelect.value : 'Motivation';
      if (activeMetadataCache) {
        activeMetadataCache.niche = niche;
      }
      console.log(`[Metadata Studio] Active niche profile changed to: ${niche}`);
    }

    function populateMetadataFields(meta) {
      if (!meta) return;

      // Niche selector
      const nicheSelect = document.getElementById('metaNicheSelect');
      if (nicheSelect && meta.niche) nicheSelect.value = meta.niche;

      // Quality score
      const qScore = meta.quality_score || (meta.quality ? meta.quality.overall_score : 88);
      const scoreEl = document.getElementById('metaQualityScoreText');
      const gaugeEl = document.getElementById('metaQualityGauge');
      const statusEl = document.getElementById('metaQualityStatusText');
      if (scoreEl) scoreEl.textContent = `${qScore} / 100`;
      if (gaugeEl) {
        gaugeEl.textContent = `${qScore}`;
        gaugeEl.style.color = qScore >= 85 ? 'var(--primary)' : (qScore >= 70 ? '#f59e0b' : '#ef4444');
      }
      if (statusEl) {
        statusEl.textContent = qScore >= 85 ? '🌟 High-CTR SEO Verified' : 'Needs Optimization';
      }

      // Title variations
      const tv = meta.title_variations || {};
      if (document.getElementById('textTitleCuriosity')) document.getElementById('textTitleCuriosity').textContent = tv.curiosity_driven || meta.title;
      if (document.getElementById('textTitleSEO')) document.getElementById('textTitleSEO').textContent = tv.seo_focused || meta.title;
      if (document.getElementById('textTitleEmotional')) document.getElementById('textTitleEmotional').textContent = tv.emotional || meta.title;
      if (document.getElementById('textTitleBold')) document.getElementById('textTitleBold').textContent = tv.bold_attention || meta.title;

      // YouTube
      const yt = meta.youtube || {};
      if (document.getElementById('metaYtTitle')) document.getElementById('metaYtTitle').value = yt.title || meta.title || '';
      if (document.getElementById('metaYtDesc')) document.getElementById('metaYtDesc').value = yt.description || '';
      if (document.getElementById('metaYtTags')) document.getElementById('metaYtTags').value = (yt.tags || []).join(', ');
      if (document.getElementById('metaYtCategory')) document.getElementById('metaYtCategory').value = yt.category || 'People & Blogs';
      if (document.getElementById('metaYtPinned')) document.getElementById('metaYtPinned').value = yt.pinned_comment || '';

      // Instagram
      const ig = meta.instagram || {};
      if (document.getElementById('metaIgHook')) document.getElementById('metaIgHook').value = ig.first_line_hook || '';
      if (document.getElementById('metaIgCaption')) document.getElementById('metaIgCaption').value = ig.caption || '';
      if (document.getElementById('metaIgHashtags')) document.getElementById('metaIgHashtags').value = (ig.hashtags || []).join(' ');
      if (document.getElementById('metaIgPinned')) document.getElementById('metaIgPinned').value = ig.pinned_comment || '';

      // TikTok
      const tt = meta.tiktok || {};
      if (document.getElementById('metaTtCaption')) document.getElementById('metaTtCaption').value = tt.caption || '';
      if (document.getElementById('metaTtKeywords')) document.getElementById('metaTtKeywords').value = (tt.search_keywords || []).join(', ');

      updateMetaCounters();
    }

    function switchMetadataPlatform(platform) {
      currentMetadataPlatform = platform;
      document.querySelectorAll('.platform-tab-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.getElementById(platform === 'youtube' ? 'tabBtnYT' : (platform === 'instagram' ? 'tabBtnIG' : 'tabBtnTT'));
      if (activeBtn) activeBtn.classList.add('active');

      document.getElementById('metaPanelYT').style.display = platform === 'youtube' ? 'block' : 'none';
      document.getElementById('metaPanelIG').style.display = platform === 'instagram' ? 'block' : 'none';
      document.getElementById('metaPanelTT').style.display = platform === 'tiktok' ? 'block' : 'none';

      const badge = document.getElementById('mockupPlatformBadge');
      if (badge) {
        if (platform === 'youtube') {
          badge.textContent = 'YouTube Shorts';
          badge.style.background = 'rgba(239, 68, 68, 0.2)';
          badge.style.color = '#ef4444';
        } else if (platform === 'instagram') {
          badge.textContent = 'Instagram Reel';
          badge.style.background = 'rgba(225, 48, 108, 0.2)';
          badge.style.color = '#e1306c';
        } else {
          badge.textContent = 'TikTok Video';
          badge.style.background = 'rgba(0, 242, 254, 0.2)';
          badge.style.color = '#00f2fe';
        }
      }
      updateMetaCounters();
    }

    function applyTitleVariation(varType) {
      if (!activeMetadataCache || !activeMetadataCache.title_variations) return;
      const title = activeMetadataCache.title_variations[varType] || '';
      if (!title) return;

      const ytTitle = document.getElementById('metaYtTitle');
      if (ytTitle) ytTitle.value = title;
      const igHook = document.getElementById('metaIgHook');
      if (igHook) igHook.value = `🔥 ${title}`;

      document.querySelectorAll('.variation-chip').forEach(c => c.classList.remove('active'));
      const activeChip = document.getElementById(
        varType === 'curiosity_driven' ? 'chipTitleCuriosity' :
        (varType === 'seo_focused' ? 'chipTitleSEO' :
        (varType === 'emotional' ? 'chipTitleEmotional' : 'chipTitleBold'))
      );
      if (activeChip) activeChip.classList.add('active');
      updateMetaCounters();
    }

    async function regenerateTitleVariations() {
      await regenerateSpecificField('youtube', 'titles');
    }

    function updateMetaCounters() {
      // YouTube Title
      const ytTitle = document.getElementById('metaYtTitle')?.value || '';
      const ytTitleCount = document.getElementById('ytTitleCount');
      if (ytTitleCount) {
        ytTitleCount.textContent = `${ytTitle.length} / 100`;
        ytTitleCount.style.color = ytTitle.length > 100 ? '#ef4444' : 'var(--text-dim)';
      }

      // YouTube Desc
      const ytDesc = document.getElementById('metaYtDesc')?.value || '';
      const ytDescCount = document.getElementById('ytDescCount');
      if (ytDescCount) {
        ytDescCount.textContent = `${ytDesc.length} / 5000`;
        ytDescCount.style.color = ytDesc.length > 5000 ? '#ef4444' : 'var(--text-dim)';
      }

      // YouTube Tags
      const ytTags = document.getElementById('metaYtTags')?.value || '';
      const ytTagsCount = document.getElementById('ytTagsCount');
      if (ytTagsCount) {
        ytTagsCount.textContent = `${ytTags.length} / 500`;
        ytTagsCount.style.color = ytTags.length > 500 ? '#ef4444' : 'var(--text-dim)';
      }

      // Instagram Hook
      const igHook = document.getElementById('metaIgHook')?.value || '';
      const igHookCount = document.getElementById('igHookCount');
      if (igHookCount) {
        igHookCount.textContent = `${igHook.length} / 85`;
        igHookCount.style.color = igHook.length > 85 ? '#ef4444' : 'var(--text-dim)';
      }

      // Instagram Caption
      const igCaption = document.getElementById('metaIgCaption')?.value || '';
      const igCaptionCount = document.getElementById('igCaptionCount');
      if (igCaptionCount) {
        igCaptionCount.textContent = `${igCaption.length} / 2200`;
        igCaptionCount.style.color = igCaption.length > 2200 ? '#ef4444' : 'var(--text-dim)';
      }

      // Instagram Tags
      const igTags = (document.getElementById('metaIgHashtags')?.value || '').trim().split(/\\s+/).filter(Boolean);
      const igTagsCount = document.getElementById('igTagsCount');
      if (igTagsCount) {
        igTagsCount.textContent = `${igTags.length} / 30 tags`;
        igTagsCount.style.color = igTags.length > 30 ? '#ef4444' : 'var(--text-dim)';
      }

      // TikTok Caption
      const ttCaption = document.getElementById('metaTtCaption')?.value || '';
      const ttCaptionCount = document.getElementById('ttCaptionCount');
      if (ttCaptionCount) {
        ttCaptionCount.textContent = `${ttCaption.length} / 2200`;
        ttCaptionCount.style.color = ttCaption.length > 2200 ? '#ef4444' : 'var(--text-dim)';
      }

      // Update Live Mockup Area
      const mockupCaptionEl = document.getElementById('mockupCaption');
      if (mockupCaptionEl) {
        if (currentMetadataPlatform === 'youtube') {
          mockupCaptionEl.innerHTML = `<strong>${escapeHtml(ytTitle)}</strong><br><span style="color:#aaa; font-size:0.65rem;">${escapeHtml(ytDesc.slice(0, 140))}...</span>`;
        } else if (currentMetadataPlatform === 'instagram') {
          mockupCaptionEl.innerHTML = `<strong>${escapeHtml(igHook)}</strong><br>${escapeHtml(igCaption.slice(0, 160)).split('\\n').join('<br>')}`;
        } else {
          mockupCaptionEl.innerHTML = `${escapeHtml(ttCaption.slice(0, 180)).split('\\n').join('<br>')}`;
        }
      }
    }

    async function generateActiveMetadata() {
      const select = document.getElementById('metaTargetSelect');
      if (!select || !select.value) {
        alert('Please select a video short or series episode first.');
        return;
      }
      const [targetType, targetId] = select.value.split(':');
      const niche = document.getElementById('metaNicheSelect')?.value || 'Motivation';

      try {
        const res = await fetch('/api/metadata/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_type: targetType, target_id: targetId, niche })
        });
        const data = await res.json();
        if (data.success && data.metadata) {
          activeMetadataCache = data.metadata;
          populateMetadataFields(data.metadata);
          alert('AI Metadata successfully generated across YouTube, Instagram, and TikTok!');
        }
      } catch (err) {
        alert('Failed to generate metadata: ' + err);
      }
    }

    async function saveActiveMetadata() {
      const select = document.getElementById('metaTargetSelect');
      if (!select || !select.value) return;
      const [targetType, targetId] = select.value.split(':');
      const niche = document.getElementById('metaNicheSelect')?.value || 'Motivation';

      const payload = {
        target_type: targetType,
        target_id: targetId,
        title: document.getElementById('metaYtTitle')?.value || 'Untitled',
        niche: niche,
        youtube: {
          title: document.getElementById('metaYtTitle')?.value || '',
          description: document.getElementById('metaYtDesc')?.value || '',
          tags: (document.getElementById('metaYtTags')?.value || '').split(',').map(s => s.trim()).filter(Boolean),
          category: document.getElementById('metaYtCategory')?.value || 'People & Blogs',
          pinned_comment: document.getElementById('metaYtPinned')?.value || ''
        },
        instagram: {
          first_line_hook: document.getElementById('metaIgHook')?.value || '',
          caption: document.getElementById('metaIgCaption')?.value || '',
          hashtags: (document.getElementById('metaIgHashtags')?.value || '').split(/\\s+/).filter(Boolean),
          pinned_comment: document.getElementById('metaIgPinned')?.value || ''
        },
        tiktok: {
          caption: document.getElementById('metaTtCaption')?.value || '',
          search_keywords: (document.getElementById('metaTtKeywords')?.value || '').split(',').map(s => s.trim()).filter(Boolean)
        },
        quality_score: 92
      };

      try {
        const res = await fetch(`/api/metadata/${targetType}/${targetId}/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          alert('Metadata saved persistently to database!');
        }
      } catch (err) {
        alert('Error saving metadata: ' + err);
      }
    }

    function copyFieldValue(fieldId) {
      const el = document.getElementById(fieldId);
      if (!el) return;
      navigator.clipboard.writeText(el.value).then(() => {
        alert('Field copied to clipboard!');
      });
    }

    function copyAllActiveMetadata() {
      const ytTitle = document.getElementById('metaYtTitle')?.value || '';
      const ytDesc = document.getElementById('metaYtDesc')?.value || '';
      const igCaption = document.getElementById('metaIgCaption')?.value || '';
      const ttCaption = document.getElementById('metaTtCaption')?.value || '';

      const fullPackage = `=== YOUTUBE ===\nTITLE:\n${ytTitle}\n\nDESCRIPTION:\n${ytDesc}\n\n=== INSTAGRAM ===\nCAPTION:\n${igCaption}\n\n=== TIKTOK ===\nCAPTION:\n${ttCaption}`;
      navigator.clipboard.writeText(fullPackage).then(() => {
        alert('Complete multi-platform metadata copied to clipboard!');
      });
    }

    async function regenerateSpecificField(platform, fieldName) {
      const select = document.getElementById('metaTargetSelect');
      if (!select || !select.value) return;
      const [targetType, targetId] = select.value.split(':');

      try {
        const res = await fetch(`/api/metadata/${targetType}/${targetId}/regenerate-field`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_type: targetType, target_id: targetId, platform, field_name: fieldName })
        });
        const data = await res.json();
        if (data.success && data.metadata) {
          activeMetadataCache = data.metadata;
          populateMetadataFields(data.metadata);
        }
      } catch (err) {
        alert('Regeneration failed: ' + err);
      }
    }

    // =====================================================================
    // --- CLIENT-SIDE JS: AI THUMBNAIL STUDIO ---
    // =====================================================================

    let activeThumbnailAssetsCache = [];
    let isGridPreviewActive = false;

    async function loadThumbnailStudio() {
      try {
        const select = document.getElementById('thumbTargetSelect');
        if (!select) return;

        const [shortsRes, seriesRes] = await Promise.all([
          fetch('/api/renders?limit=100').then(r => r.json()).catch(() => ({ renders: [] })),
          fetch('/api/series?limit=50').then(r => r.json()).catch(() => ({ series: [] }))
        ]);

        const prevVal = select.value;
        let html = '<option value="">-- Choose Short or Series Episode --</option>';

        const rendersList = (shortsRes.renders || shortsRes.shorts || []);
        if (rendersList.length > 0) {
          html += '<optgroup label="🎬 Viral 9:16 Shorts">';
          rendersList.forEach(s => {
            html += `<option value="short:${s.id}">Short #${s.id} — ${s.title || 'Viral Clip'}</option>`;
          });
          html += '</optgroup>';
        }

        if (seriesRes.series && seriesRes.series.length > 0) {
          html += '<optgroup label="📺 Cliffhanger Series Episodes">';
          seriesRes.series.forEach(ser => {
            if (ser.episodes && ser.episodes.length > 0) {
              ser.episodes.forEach(ep => {
                html += `<option value="episode:${ep.id}">${ser.title} [Part ${ep.episode_number}] — ${ep.title}</option>`;
              });
            }
          });
          html += '</optgroup>';
        }

        select.innerHTML = html;
        if (prevVal && [...select.options].some(o => o.value === prevVal)) {
          select.value = prevVal;
        } else if (select.options.length > 1) {
          select.selectedIndex = 1;
        }
        await onThumbnailTargetChanged();
      } catch (err) {
        console.error('Failed to load Thumbnail Studio targets:', err);
      }
    }

    async function onThumbnailTargetChanged() {
      const select = document.getElementById('thumbTargetSelect');
      if (!select || !select.value) return;
      const [targetType, targetId] = select.value.split(':');

      try {
        const [thumbRes, framesRes] = await Promise.all([
          fetch(`/api/thumbnails/${targetType}/${targetId}`).then(r => r.json()).catch(() => ({ thumbnails: [] })),
          fetch('/api/thumbnails/extract-frames', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_type: targetType, target_id: targetId })
          }).then(r => r.json()).catch(() => ({ candidates: [] }))
        ]);

        // Render Frame Scrubber
        renderCandidateFrames(framesRes.candidates || []);

        // Render Thumbnail Variations
        activeThumbnailAssetsCache = thumbRes.thumbnails || [];
        renderThumbnailVariations(activeThumbnailAssetsCache);
      } catch (err) {
        console.error('Error fetching thumbnail assets:', err);
      }
    }

    function renderCandidateFrames(candidates) {
      const scrubber = document.getElementById('thumbFrameScrubber');
      if (!scrubber) return;
      if (!candidates || candidates.length === 0) {
        scrubber.innerHTML = '<div style="color:var(--text-dim); padding:1rem; font-size:0.8rem;">No frames extracted yet. Click Re-scan.</div>';
        return;
      }
      scrubber.innerHTML = candidates.map((c, i) => `
        <div class="frame-scrubber-item ${i === 0 ? 'active' : ''}" onclick="selectScrubberFrame(this, ${c.timestamp_sec})">
          <div style="font-size:0.65rem; color:#fff; position:absolute; top:3px; left:4px; background:rgba(0,0,0,0.7); padding:1px 3px; border-radius:3px;">
            ${c.timestamp_sec.toFixed(1)}s
          </div>
          <div style="font-size:0.62rem; color:${c.has_face ? '#34d399' : '#f59e0b'}; position:absolute; bottom:3px; right:4px; background:rgba(0,0,0,0.7); padding:1px 3px; border-radius:3px;">
            ${c.has_face ? '👤 Face' : '🏞️ Scene'}
          </div>
          <div style="width:100%; height:62px; background:#222; display:flex; align-items:center; justify-content:center; color:#555; font-size:0.7rem;">
            Frame ${i+1}
          </div>
        </div>
      `).join('');
    }

    function selectScrubberFrame(el, timestamp) {
      document.querySelectorAll('.frame-scrubber-item').forEach(item => item.classList.remove('active'));
      el.classList.add('active');
    }

    function renderThumbnailVariations(thumbnails) {
      const gallery = document.getElementById('thumbVariationsGallery');
      if (!gallery) return;

      if (!thumbnails || thumbnails.length === 0) {
        gallery.innerHTML = `
          <div class="card" style="text-align: center; color: var(--text-dim); padding: 3rem 1rem; grid-column: span 3;">
            No thumbnail variations generated yet. Click "Generate Thumbnail Variations" above.
          </div>
        `;
        return;
      }

      gallery.innerHTML = thumbnails.map(t => {
        const isSel = Boolean(t.is_selected);
        const varTitle = t.variation_type === 'emotional' ? '❤️ Emotional Peak' : (t.variation_type === 'curiosity' ? '🔍 Curiosity Loop' : '💼 Professional Minimal');
        const badgeColor = t.variation_type === 'emotional' ? '#fb7185' : (t.variation_type === 'curiosity' ? '#38bdf8' : '#34d399');
        const imgUrl = `/api/thumbnails/${t.id}/image?t=${Date.now()}`;

        return `
          <div class="thumbnail-card ${isSel ? 'selected' : ''}" id="thumbCard_${t.id}">
            <div style="position: relative; width: 100%; aspect-ratio: ${t.aspect_ratio === '16:9' ? '16/9' : '9/16'}; max-height: 440px; background: #000; overflow: hidden; display: flex; align-items: center; justify-content: center;">
              <img src="${imgUrl}" alt="${t.headline}" style="width: 100%; height: 100%; object-fit: contain;">
              <div class="grid-crop-indicator" style="display: ${isGridPreviewActive && t.aspect_ratio === '9:16' ? 'block' : 'none'}; position: absolute; inset: 0; margin: auto; width: 100%; aspect-ratio: 1/1; border: 2px dashed rgba(255,255,255,0.7); box-shadow: 0 0 0 9999px rgba(0,0,0,0.55); pointer-events: none;"></div>
              ${isSel ? '<span style="position: absolute; top: 10px; right: 10px; background: var(--primary); color: #000; font-size: 0.72rem; font-weight: 800; padding: 2px 8px; border-radius: 4px;">★ ACTIVE COVER</span>' : ''}
              <span style="position: absolute; bottom: 10px; left: 10px; background: rgba(0,0,0,0.75); color: ${badgeColor}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;">
                ${varTitle}
              </span>
            </div>

            <div style="padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; flex: 1;">
              <div style="font-size: 0.88rem; font-weight: 800; color: #fff;">${t.headline || 'HIGH IMPACT HEADLINE'}</div>
              <div style="font-size: 0.72rem; color: var(--text-dim);">${t.aspect_ratio} • ${t.style_mode} • Frame @ ${t.source_timestamp.toFixed(1)}s</div>
              <div style="display: flex; gap: 0.5rem; margin-top: auto; padding-top: 0.5rem;">
                <button class="btn-primary" style="flex: 1; font-size: 0.78rem; padding: 0.35rem 0.6rem;" onclick="selectActiveThumbnail(${t.id})">
                  ${isSel ? '✓ Selected' : '★ Set Active Cover'}
                </button>
                <button class="btn-secondary" style="font-size: 0.78rem; padding: 0.35rem 0.6rem;" onclick="downloadThumbnailAsset(${t.id})">
                  ⬇
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    async function generateActiveThumbnails() {
      const select = document.getElementById('thumbTargetSelect');
      if (!select || !select.value) {
        alert('Please select a video short or series episode first.');
        return;
      }
      const [targetType, targetId] = select.value.split(':');
      const ratio = document.getElementById('thumbPlatformSelect')?.value || '9:16';
      const mode = document.getElementById('thumbModeSelect')?.value || 'auto';
      const customHead = document.getElementById('thumbCustomHeadline')?.value || null;

      try {
        const res = await fetch('/api/thumbnails/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_type: targetType,
            target_id: targetId,
            aspect_ratio: ratio,
            style_mode: mode,
            custom_headline: customHead
          })
        });
        const data = await res.json();
        if (data.success && data.variations) {
          await onThumbnailTargetChanged();
          alert('3 High-CTR thumbnail variations generated!');
        }
      } catch (err) {
        alert('Thumbnail generation failed: ' + err);
      }
    }

    async function selectActiveThumbnail(assetId) {
      const select = document.getElementById('thumbTargetSelect');
      if (!select || !select.value) return;
      const [targetType, targetId] = select.value.split(':');

      try {
        const res = await fetch(`/api/thumbnails/${assetId}/select`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ asset_id: assetId, target_type: targetType, target_id: targetId })
        });
        const data = await res.json();
        if (data.success) {
          await onThumbnailTargetChanged();
        }
      } catch (err) {
        alert('Failed to select active cover: ' + err);
      }
    }

    function downloadThumbnailAsset(assetId) {
      window.open(`/api/thumbnails/${assetId}/image`, '_blank');
    }

    async function extractFreshCandidateFrames() {
      await onThumbnailTargetChanged();
    }

    function toggleInstagramGridPreview() {
      isGridPreviewActive = !isGridPreviewActive;
      const btn = document.getElementById('btnToggleGridCrop');
      if (btn) btn.textContent = isGridPreviewActive ? '📐 Hide 1:1 Grid Overlay' : '📐 Toggle 1:1 Grid Preview';
      document.querySelectorAll('.grid-crop-indicator').forEach(el => {
        el.style.display = isGridPreviewActive ? 'block' : 'none';
      });
    }

    function onThumbnailConfigChanged() {
      const platform = document.getElementById('thumbPlatformSelect')?.value || '9:16';
      const mode = document.getElementById('thumbModeSelect')?.value || 'auto';
      const gridBtn = document.getElementById('btnToggleGridCrop');
      if (gridBtn) {
        gridBtn.style.display = platform === '9:16' ? 'inline-block' : 'none';
      }
      console.log(`[Thumbnail Studio] Config updated: platform=${platform}, mode=${mode}`);
    }

    function autoSuggestThumbnailHeadline() {
      const suggestions = [
        '99% NEVER MAKE IT',
        'I LOST EVERYTHING',
        'UNBELIEVABLE FINISH!',
        'THE SECRET RULE',
        'DO NOT WAIT',
        'MINDSET IS EVERYTHING'
      ];
      const pick = suggestions[Math.floor(Math.random() * suggestions.length)];
      const input = document.getElementById('thumbCustomHeadline');
      if (input) input.value = pick;
    }

    // =====================================================================
    // --- CLIENT-SIDE JS: PUBLISHING READINESS MODAL ---
    // =====================================================================

    let activeReadinessTarget = { type: 'short', id: '1' };

    async function openReadinessModalForActive() {
      const select = document.getElementById('metaTargetSelect');
      if (!select || !select.value) {
        alert('Please select a video short or episode first.');
        return;
      }
      const [targetType, targetId] = select.value.split(':');
      openReadinessModal(targetType, targetId);
    }

    async function openReadinessModal(targetType, targetId) {
      activeReadinessTarget = { type: targetType, id: targetId };
      const modal = document.getElementById('readinessModal');
      if (modal) modal.style.display = 'flex';

      try {
        const res = await fetch(`/api/publishing/readiness/${targetType}/${targetId}`);
        const data = await res.json();
        if (data.success && data.report) {
          renderReadinessReport(data.report);
        }
      } catch (err) {
        console.error('Error fetching readiness report:', err);
      }
    }

    function renderReadinessReport(report) {
      const scoreVal = document.getElementById('readinessScoreVal');
      const statusBadge = document.getElementById('readinessStatusBadge');
      const checklistArea = document.getElementById('readinessChecklistArea');

      if (scoreVal) scoreVal.textContent = `${report.overall_score}%`;
      if (statusBadge) {
        statusBadge.textContent = report.readiness_status === 'ready' ? '🟢 Ready for Publishing' : (report.readiness_status === 'needs_review' ? '🟡 Review Required' : '🔴 Incomplete');
        statusBadge.style.color = report.readiness_status === 'ready' ? 'var(--primary)' : (report.readiness_status === 'needs_review' ? '#f59e0b' : '#ef4444');
      }

      if (checklistArea) {
        checklistArea.innerHTML = (report.checks || []).map(chk => {
          const isPass = chk.status === 'passed';
          const isWarn = chk.status === 'warning';
          const pillColor = isPass ? '#34d399' : (isWarn ? '#f59e0b' : '#ef4444');
          const pillBg = isPass ? 'rgba(52,211,153,0.15)' : (isWarn ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)');
          const icon = isPass ? '✓' : (isWarn ? '⚠️' : '✕');

          return `
            <div style="padding: 0.75rem; background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: var(--radius-sm); display: flex; flex-direction: column; gap: 0.25rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 0.85rem; color: #fff;">${chk.check_name}</strong>
                <span class="readiness-pill" style="background: ${pillBg}; color: ${pillColor};">${icon} ${chk.status.toUpperCase()}</span>
              </div>
              <div style="font-size: 0.78rem; color: var(--text-dim);">${chk.message}</div>
              ${chk.actionable_fix ? `<div style="font-size: 0.72rem; color: #f59e0b; margin-top: 2px;">💡 Action: ${chk.actionable_fix}</div>` : ''}
            </div>
          `;
        }).join('');
      }
    }

    function closeReadinessModal() {
      const modal = document.getElementById('readinessModal');
      if (modal) modal.style.display = 'none';
    }

    function downloadExportPackageForActive() {
      const { type, id } = activeReadinessTarget;
      window.open(`/api/publishing/export-package/${type}/${id}`, '_blank');
    }

    // Auto-initialize on load
    window.addEventListener('DOMContentLoaded', async () => {
      document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        item.addEventListener('keydown', event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            item.click();
          }
        });
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') setMobileNav(false);
      });
      window.addEventListener('resize', () => setMobileNav(false));
      window.addEventListener('popstate', () => {
        const pTab = window.location.pathname.replace(/^[/]+/, '').split('/')[0];
        switchTab(window.location.hash.slice(1) || pTab || 'overview', false);
      });

      const pathTab = window.location.pathname.replace(/^[/]+/, '').split('/')[0];
      const requestedTab = window.location.hash.slice(1) || pathTab;
      switchTab(document.getElementById(`tab-${requestedTab}`) ? requestedTab : 'overview', false);

      loadAccountsList();
      checkAutomationStatus();
      checkHardwareAccel();

      // Background telemetry sync every 5 seconds
      setInterval(() => {
        checkAutomationStatus();
      }, 5000);
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
@app.get("/{tab_slug}", response_class=HTMLResponse)
def serve_dashboard(tab_slug: str = ""):
    """Serves the main interactive dashboard."""
    if tab_slug.startswith("api") or tab_slug.startswith("docs") or tab_slug.startswith("openapi") or tab_slug.startswith("output") or tab_slug.startswith("temp"):
        raise HTTPException(status_code=404, detail="Not Found")
    return HTMLResponse(content=DASHBOARD_HTML)


if __name__ == "__main__":
    import uvicorn
    print("[*] Starting VedioHooks AI Media Factory on http://127.0.0.1:8000")
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=False)
