"""
Background Pipeline Worker for AI Viral Shorts Maker.
Coordinates asynchronous video ingestion, transcription, virality scoring,
smart face tracking, and animated karaoke subtitle rendering.
"""

import os
import sys
import re
import json
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import (
    update_job_progress, update_job_metadata, save_rendered_short, get_job,
    is_emergency_stopped, get_account, get_series, get_series_episode,
    update_episode_render_result, update_series, save_video_metadata, save_thumbnail_asset
)
from src.metadata_generator import generate_video_metadata
from src.thumbnail_studio import generate_thumbnail_suite
from src.ingest import download_video, process_local_file
from src.transcribe import transcribe_audio
from src.virality_selector import select_viral_clips
from src.ai_director import generate_content_plan
from src.video_slicer import slice_word_timestamps, slice_and_crop_video, calculate_jumpcuts, apply_dead_air_removal
from src.subtitle_generator import create_ass_subtitles, burn_subtitles_to_video
from src.face_tracker import render_face_tracked_short
from src.audio_ducking import apply_audio_ducking
from src.sfx_engine import apply_transition_sfx
from src.broll_engine import apply_hook_motion_overlay
from src.retention_predictor import calculate_retention_curve
from src.auto_zoom import apply_dynamic_auto_zoom
from src.hook_banner import generate_smart_hook_text, BANNER_THEMES


def process_video_job(job_id: str, source: str, is_url: bool = True, model_size: str = "base.en"):
    """
    Executes the ingestion, transcription, AI Content Director planning,
    and virality analysis stages for an account-assigned job.
    """
    if is_emergency_stopped():
        print(f"[!] Emergency stop is active. Job {job_id} halted.")
        update_job_progress(job_id, status="queued", progress=0, current_step="Paused by Emergency Stop")
        return

    try:
        job = get_job(job_id)
        account_id = job.get("account_id") if job else "acc_motivation"
        account = get_account(account_id) or {"id": account_id, "name": "Default Account", "niche": "Motivation"}

        # 1. Ingestion
        update_job_progress(job_id, status="downloading", progress=15, current_step=f"Downloading video for {account['name']}...")
        if is_url:
            ingest_res = download_video(source, output_dir="temp")
        else:
            ingest_res = process_local_file(source, output_dir="temp")

        video_path = ingest_res["video_path"]
        audio_path = ingest_res["audio_path"]
        title = ingest_res["title"]
        duration = ingest_res["duration"]
        resolution = ingest_res["resolution"]

        update_job_metadata(job_id, title=title, duration=duration, resolution=resolution)

        # 2. Transcription
        update_job_progress(job_id, status="transcribing", progress=45, current_step="Running Faster-Whisper word-level transcription...")
        transcript_json_path = os.path.join("temp", f"{job_id}_transcript.json")
        trans_result = transcribe_audio(
            audio_path=audio_path,
            model_size=model_size,
            output_json_path=transcript_json_path
        )

        # 3. AI Content Director Planning & Virality Selection
        update_job_progress(job_id, status="analyzing", progress=75, current_step=f"AI Director analyzing '{account['niche']}' angles & viral hooks...")
        clips_json_path = os.path.join("temp", f"{job_id}_viral_clips.json")
        virality_rep = select_viral_clips(
            transcript_json_path=transcript_json_path,
            output_report_path=clips_json_path
        )

        # Generate overarching strategic AI plan for this account & job
        try:
            top_clip = virality_rep.clips[0].model_dump() if virality_rep.clips else None
            generate_content_plan(
                account_id=account_id,
                transcript_data=trans_result,
                clip=top_clip,
                job_id=job_id
            )
        except Exception as plan_err:
            print(f"[!] AI Content Director plan warning for job {job_id}: {plan_err}")

        update_job_metadata(job_id, title=title, duration=duration, resolution=resolution,
                            transcript_path=transcript_json_path, clips_path=clips_json_path)

        # 4. Auto-render top viral short so the user immediately sees the edited clip!
        if virality_rep.clips:
            try:
                update_job_progress(job_id, status="rendering", progress=88, current_step="Auto-rendering top viral 9:16 short with karaoke captions & face tracking...")
                niche = account.get("niche", "Motivation")
                niche_themes = {
                    "Motivation": "hormozi_yellow",
                    "Cricket": "hormozi_green",
                    "AI & Study": "cyber_cyan",
                    "Gym & Fitness": "beast_red",
                    "Common / General": "fire_orange"
                }
                auto_theme = niche_themes.get(niche, "hormozi_yellow")
                top_clip = virality_rep.clips[0]
                top_clip_id = getattr(top_clip, "clip_id", None) or getattr(top_clip, "id", 1)
                render_short_job(
                    job_id=job_id,
                    clip_id=top_clip_id,
                    crop_mode="smart_face",
                    theme=auto_theme,
                    enable_ducking=True,
                    enable_jumpcuts=True
                )
            except Exception as auto_render_err:
                print(f"[!] Auto-render notice for top clip of job {job_id}: {auto_render_err}")

        # 5. Job is fully completed with edited video ready
        update_job_progress(job_id, status="completed", progress=100, current_step=f"Video fully edited & ready for {account['name']}!")
        print(f"[SUCCESS] Job {job_id} successfully analyzed & rendered for account '{account_id}'.")

    except Exception as ex:
        err = f"{str(ex)}\n{traceback.format_exc()}"
        print(f"[ERROR] Job {job_id} failed: {err}")
        update_job_progress(job_id, status="failed", progress=0, current_step="Failed during analysis", error=str(ex))


def render_short_job(
    job_id: str,
    clip_id: int,
    crop_mode: str = "smart_face",
    theme: str = "hormozi_yellow",
    enable_ducking: bool = False,
    enable_jumpcuts: bool = False,
    target_language: str = "en",
    enable_sfx: bool = True,
    enable_broll: bool = False,
    enable_auto_zoom: bool = False,
    hook_banner_text: Optional[str] = None,
    hook_banner_theme: Optional[str] = None
) -> Dict[str, Any]:
    """
    Renders a specific viral clip into a finished 9:16 vertical short with animated subtitles,
    optional frame-accurate jump-cut dead-air removal, sidechain audio ducking, bilingual subtitles,
    transition whoosh SFX, thematic B-roll pattern interrupt, dynamic punch-cut auto-zoom,
    and top hook header banner.
    """
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    clips = job.get("clips", [])
    target_clip = next((c for c in clips if c.get("clip_id") == clip_id or c.get("id") == clip_id), None)
    if not target_clip and clips and clip_id == 1:
        target_clip = clips[0]
    if not target_clip:
        raise ValueError(f"Clip #{clip_id} not found in job {job_id}")

    start_t = float(target_clip["start_time"])
    end_t = float(target_clip["end_time"])
    title = target_clip.get("title", f"Clip #{clip_id}")
    score = int(target_clip.get("virality_score", 85))

    transcript_path = job.get("transcript_json_path")
    if not transcript_path or not os.path.exists(transcript_path):
        raise FileNotFoundError(f"Transcript JSON missing for job {job_id}")

    # Determine original video path
    # Look in temp for matching job video
    video_path = job.get("source_path")
    if not os.path.exists(video_path):
        # Look in temp for video
        candidates = list(Path("temp").glob(f"*{job['title'][:15]}*.mp4"))
        if candidates:
            video_path = str(candidates[0])
        else:
            candidates_all = list(Path("temp").glob("*.mp4"))
            if candidates_all:
                video_path = str(candidates_all[0])
            else:
                raise FileNotFoundError(f"Source video file not found for job {job_id}")

    out_base = f"output/{job_id}_clip{clip_id}_{crop_mode}_{theme}"
    final_video_path = f"{out_base}_9x16.mp4"
    words_json_path = f"{out_base}_words.json"
    ass_path = f"temp/{job_id}_clip{clip_id}_{theme}.ass"

    # Step A: Re-zero word timestamps for this cut
    sliced_sub = slice_word_timestamps(
        full_transcript_path=transcript_path,
        start_sec=start_t,
        end_sec=end_t,
        output_sliced_json=words_json_path
    )

    active_words = sliced_sub["words"]
    jumpcut_segments = []
    if enable_jumpcuts:
        jumpcut_segments, active_words = calculate_jumpcuts(sliced_sub["words"], max_silence_sec=0.35)

    # Step B: Create Alex Hormozi Karaoke ASS file (with Context Top Hook Banner)
    if not hook_banner_text:
        try:
            from src.hook_banner import generate_smart_hook_text
            from src.db import get_account
            account_niche = "Motivation"
            account_id = job.get("account_id")
            if account_id:
                acc = get_account(account_id)
                if acc:
                    account_niche = acc.get("niche", "Motivation")
            hook_banner_text = generate_smart_hook_text(
                title=title or job.get("title", "VIRAL HIGHLIGHT"),
                niche=account_niche,
                clip_text=target_clip.get("full_quote", "") or target_clip.get("hook_text", "")
            )
        except Exception as banner_err:
            print(f"[!] Warning synthesizing auto context hook banner: {banner_err}")

    create_ass_subtitles(
        words_data=active_words,
        output_ass_path=ass_path,
        theme_name=theme,
        font_name="Arial Black",
        font_size=70,
        words_per_chunk=3,
        margin_v=720,
        target_language=target_language,
        hook_banner_text=hook_banner_text,
        hook_banner_theme=hook_banner_theme or theme
    )

    # Step C: Render with requested framing mode
    if crop_mode == "smart_face":
        # Smart Face Tracking + Captions in single pass
        render_face_tracked_short(
            video_path=video_path,
            start_sec=start_t,
            end_sec=end_t,
            output_path=final_video_path,
            speaker_mode="auto",
            captions_ass_path=ass_path
        )
    elif crop_mode == "blur_fill":
        # Blurred fill background
        raw_cut = f"temp/{job_id}_raw_cut_{clip_id}.mp4"
        slice_and_crop_video(
            video_path=video_path,
            start_sec=start_t,
            end_sec=end_t,
            output_path=raw_cut,
            crop_mode="blur_fill"
        )
        burn_subtitles_to_video(
            input_video_path=raw_cut,
            ass_subtitle_path=ass_path,
            output_video_path=final_video_path
        )
        if os.path.exists(raw_cut):
            os.remove(raw_cut)
    elif crop_mode == "split_stack":
        # 2-speaker podcast / interview vertical split
        raw_cut = f"temp/{job_id}_raw_cut_{clip_id}.mp4"
        slice_and_crop_video(
            video_path=video_path,
            start_sec=start_t,
            end_sec=end_t,
            output_path=raw_cut,
            crop_mode="split_stack"
        )
        burn_subtitles_to_video(
            input_video_path=raw_cut,
            ass_subtitle_path=ass_path,
            output_video_path=final_video_path
        )
        if os.path.exists(raw_cut):
            os.remove(raw_cut)
    else:  # 'center'
        raw_cut = f"temp/{job_id}_raw_cut_{clip_id}.mp4"
        slice_and_crop_video(
            video_path=video_path,
            start_sec=start_t,
            end_sec=end_t,
            output_path=raw_cut,
            crop_mode="center"
        )
        burn_subtitles_to_video(
            input_video_path=raw_cut,
            ass_subtitle_path=ass_path,
            output_video_path=final_video_path
        )
        if os.path.exists(raw_cut):
            os.remove(raw_cut)

    # Optional: Apply frame-accurate jump-cut dead-air removal
    if jumpcut_segments:
        jumpcut_out = f"{out_base}_jumpcut.mp4"
        apply_dead_air_removal(final_video_path, jumpcut_out, jumpcut_segments)
        final_video_path = jumpcut_out

    # Optional: Apply sidechain audio ducking with niche ambient music
    if enable_ducking:
        ducked_out = f"{out_base}_ducked.mp4"
        account = get_account(job.get("account_id", "acc_motivation")) if job.get("account_id") else {}
        niche = account.get("niche", "Motivation") if account else "Motivation"
        apply_audio_ducking(speech_video_path=final_video_path, output_video_path=ducked_out, niche=niche)
        final_video_path = ducked_out

    # Optional: Apply subtle hook transition whoosh SFX
    if enable_sfx:
        sfx_out = f"{out_base}_sfx.mp4"
        apply_transition_sfx(final_video_path, sfx_out, sfx_times=[0.1], sfx_type="whoosh")
        if os.path.exists(sfx_out):
            final_video_path = sfx_out

    # Optional: Apply thematic B-roll pattern interrupt overlay
    account = get_account(job.get("account_id", "acc_motivation")) if job.get("account_id") else {}
    niche = account.get("niche", "Motivation") if account else "Motivation"
    if enable_broll:
        broll_out = f"{out_base}_broll.mp4"
        apply_hook_motion_overlay(final_video_path, broll_out, niche=niche, start_sec=0.2, end_sec=1.8)
        if os.path.exists(broll_out):
            final_video_path = broll_out

    # Optional: Apply dynamic auto-zoom punch cuts
    if enable_auto_zoom:
        zoom_out = f"{out_base}_autozoom.mp4"
        apply_dynamic_auto_zoom(
            input_video_path=final_video_path,
            output_video_path=zoom_out,
            words=active_words,
            zoom_scale=1.16
        )
        if os.path.exists(zoom_out) and os.path.getsize(zoom_out) > 0:
            final_video_path = zoom_out

    # Calculate second-by-second predictive retention curve
    retention_telemetry = calculate_retention_curve(
        words=active_words,
        duration_sec=end_t - start_t,
        virality_score=score
    )

    # Step D: Save rendered short in SQLite
    caption = target_clip.get("suggested_caption") or f"🔥 {title}\n\n👇 Save this for later!"
    tags_list = target_clip.get("suggested_hashtags", [])
    hashtags = " ".join(tags_list) if tags_list else "#shorts #reels #viral #mindset"

    account_id = job.get("account_id") or "acc_motivation"
    render_id = save_rendered_short(
        job_id=job_id,
        clip_id=clip_id,
        title=title,
        start_time=start_t,
        end_time=end_t,
        virality_score=score,
        crop_mode=crop_mode,
        theme=theme,
        video_path=final_video_path,
        caption=caption,
        hashtags=hashtags,
        account_id=account_id
    )

    # Step E: Autonomous AI Metadata & Thumbnail Suite Generation
    try:
        raw_text = target_clip.get("full_quote", "") or target_clip.get("hook_text", "") or title
        meta_res = generate_video_metadata(
            target_type="short",
            target_id=render_id,
            title=title,
            text=raw_text,
            niche=niche,
            job_id=job_id,
            duration=end_t - start_t,
            words=active_words,
            handle=account.get("handle", "@vediohooks") if account else "@vediohooks"
        )
        save_video_metadata(
            target_type="short",
            target_id=render_id,
            title=title,
            niche=niche,
            youtube_data=meta_res.youtube.model_dump(),
            instagram_data=meta_res.instagram.model_dump(),
            tiktok_data=meta_res.tiktok.model_dump(),
            title_variations=meta_res.title_variations.model_dump(),
            quality_score=meta_res.quality.overall_score,
            quality_breakdown=meta_res.quality.model_dump(),
            job_id=job_id,
            account_id=account_id
        )

        thumb_res = generate_thumbnail_suite(
            video_path=final_video_path,
            target_type="short",
            target_id=render_id,
            title=title,
            niche=niche,
            start_sec=0.0,
            end_sec=max(1.0, end_t - start_t),
            aspect_ratio="9:16",
            style_mode="auto",
            brand_handle=account.get("handle", "@vediohooks") if account else "@vediohooks"
        )
        for idx, var in enumerate(thumb_res.variations):
            save_thumbnail_asset(
                target_type="short",
                target_id=render_id,
                image_path=var.image_path,
                headline=var.headline,
                variation_type=var.variation_type,
                aspect_ratio=var.aspect_ratio,
                style_mode=var.style_mode,
                source_timestamp=var.source_timestamp,
                is_selected=1 if idx == 0 else 0,
                job_id=job_id,
                account_id=account_id
            )
    except Exception as auto_meta_err:
        print(f"[!] Warning generating auto metadata/thumbnail for short #{render_id}: {auto_meta_err}")

    print(f"[SUCCESS] Rendered short #{render_id} for job {job_id} -> {final_video_path}")
    return {
        "render_id": render_id,
        "job_id": job_id,
        "clip_id": clip_id,
        "title": title,
        "video_path": final_video_path,
        "crop_mode": crop_mode,
        "theme": theme,
        "virality_score": score,
        "caption": caption,
        "hashtags": hashtags,
        "duration": round(end_t - start_t, 2),
        "retention_telemetry": retention_telemetry
    }


# =====================================================================
# --- AI CLIFFHANGER SERIES RENDERING ENGINE ---
# =====================================================================

def render_series_episode_job(
    series_id: str,
    episode_id: int,
    crop_mode: str = "smart_face",
    theme: str = "hormozi_yellow",
    enable_ducking: bool = True,
    enable_jumpcuts: bool = False,
    enable_sfx: bool = True,
    enable_auto_zoom: bool = False
) -> Dict[str, Any]:
    """
    Renders an individual series episode into a 9:16 vertical short with
    MediaPipe face tracking, dynamic Alex Hormozi karaoke subtitles, and
    an episodic series header banner (e.g., [EP 1/4] TITLE or [FINAL EPISODE]).
    """
    if is_emergency_stopped():
        raise RuntimeError("Emergency stop is active. Episode render halted.")

    episode = get_series_episode(episode_id)
    if not episode or episode.get("series_id") != series_id:
        raise ValueError(f"Episode #{episode_id} not found in series {series_id}")

    series = get_series(series_id)
    if not series:
        raise ValueError(f"Series not found: {series_id}")

    update_episode_render_result(episode_id, render_status="rendering")

    try:
        start_t = float(episode["start_time"])
        end_t = float(episode["end_time"])
        title = episode.get("title", f"Episode {episode.get('episode_number', 1)}")
        score = int(episode.get("quality_score", 85))
        is_final = bool(episode.get("is_final_episode", False))
        ep_num = episode.get("episode_number", 1)
        total_eps = series.get("episode_count", len(series.get("episodes", [])))

        # Locate source video
        job_id = series.get("job_id")
        video_path = series.get("source_video_path")
        transcript_path = None

        if job_id:
            job = get_job(job_id)
            if job:
                transcript_path = job.get("transcript_json_path")
                if not video_path or not os.path.exists(video_path):
                    video_path = job.get("source_path")

        if not video_path or not os.path.exists(video_path):
            candidates = list(Path("temp").glob("*.mp4"))
            if candidates:
                video_path = str(candidates[0])
            else:
                raise FileNotFoundError(f"Source video file not found for series {series_id}")

        if not transcript_path or not os.path.exists(transcript_path):
            if job_id and os.path.exists(f"temp/{job_id}_transcript.json"):
                transcript_path = f"temp/{job_id}_transcript.json"
            else:
                trans_candidates = list(Path("temp").glob("*_transcript.json"))
                if trans_candidates:
                    transcript_path = str(trans_candidates[0])
                else:
                    raise FileNotFoundError(f"Transcript JSON missing for series {series_id}")

        out_base = f"output/{series_id}_ep{ep_num}_{crop_mode}_{theme}"
        final_video_path = f"{out_base}_9x16.mp4"
        words_json_path = f"{out_base}_words.json"
        ass_path = f"temp/{series_id}_ep{ep_num}_{theme}.ass"

        # Step A: Re-zero word timestamps for this episode cut
        sliced_sub = slice_word_timestamps(
            full_transcript_path=transcript_path,
            start_sec=start_t,
            end_sec=end_t,
            output_sliced_json=words_json_path
        )
        active_words = sliced_sub["words"]

        # Step B: Series Top Hook Banner Styling
        # e.g., "[FINAL EPISODE] HOW HE WON" or "[EP 1/4] THE FIRST FAILURE"
        clean_ep_title = re.sub(r"^(part\s*\d+|episode\s*\d+)[:\s\-]*", "", title, flags=re.IGNORECASE).strip().upper()
        if not clean_ep_title:
            clean_ep_title = series.get("title", "SERIES HIGHLIGHT").upper()

        if is_final:
            series_banner_text = f"[FINAL EPISODE] {clean_ep_title}"
        else:
            series_banner_text = f"[EP {ep_num}/{total_eps}] {clean_ep_title}"

        # Truncate if banner is too wide
        if len(series_banner_text) > 42:
            series_banner_text = series_banner_text[:39] + "..."

        create_ass_subtitles(
            words_data=active_words,
            output_ass_path=ass_path,
            theme_name=theme,
            font_name="Arial Black",
            font_size=68,
            words_per_chunk=3,
            margin_v=720,
            hook_banner_text=series_banner_text,
            hook_banner_theme=theme,
            hook_banner_duration=3.8
        )

        # Step C: Render 9:16 vertical video using existing infrastructure
        if crop_mode == "smart_face":
            render_face_tracked_short(
                video_path=video_path,
                start_sec=start_t,
                end_sec=end_t,
                output_path=final_video_path,
                speaker_mode="auto",
                captions_ass_path=ass_path
            )
        elif crop_mode == "blur_fill":
            raw_cut = f"temp/{series_id}_raw_{ep_num}.mp4"
            slice_and_crop_video(
                video_path=video_path,
                start_sec=start_t,
                end_sec=end_t,
                output_path=raw_cut,
                crop_mode="blur_fill"
            )
            burn_subtitles_to_video(
                input_video_path=raw_cut,
                ass_subtitle_path=ass_path,
                output_video_path=final_video_path
            )
            if os.path.exists(raw_cut):
                os.remove(raw_cut)
        elif crop_mode == "split_stack":
            raw_cut = f"temp/{series_id}_raw_{ep_num}.mp4"
            slice_and_crop_video(
                video_path=video_path,
                start_sec=start_t,
                end_sec=end_t,
                output_path=raw_cut,
                crop_mode="split_stack"
            )
            burn_subtitles_to_video(
                input_video_path=raw_cut,
                ass_subtitle_path=ass_path,
                output_video_path=final_video_path
            )
            if os.path.exists(raw_cut):
                os.remove(raw_cut)
        else:  # 'center'
            raw_cut = f"temp/{series_id}_raw_{ep_num}.mp4"
            slice_and_crop_video(
                video_path=video_path,
                start_sec=start_t,
                end_sec=end_t,
                output_path=raw_cut,
                crop_mode="center"
            )
            burn_subtitles_to_video(
                input_video_path=raw_cut,
                ass_subtitle_path=ass_path,
                output_video_path=final_video_path
            )
            if os.path.exists(raw_cut):
                os.remove(raw_cut)

        # Optional audio ducking
        account_id = series.get("account_id", "acc_motivation")
        account = get_account(account_id) or {}
        niche = account.get("niche", "Motivation")

        if enable_ducking:
            ducked_out = f"{out_base}_ducked.mp4"
            apply_audio_ducking(speech_video_path=final_video_path, output_video_path=ducked_out, niche=niche)
            final_video_path = ducked_out

        # Optional transition SFX
        if enable_sfx:
            sfx_out = f"{out_base}_sfx.mp4"
            apply_transition_sfx(final_video_path, sfx_out, sfx_times=[0.1], sfx_type="whoosh")
            if os.path.exists(sfx_out):
                final_video_path = sfx_out

        # Optional dynamic auto-zoom
        if enable_auto_zoom:
            zoom_out = f"{out_base}_autozoom.mp4"
            apply_dynamic_auto_zoom(
                input_video_path=final_video_path,
                output_video_path=zoom_out,
                words=active_words,
                zoom_scale=1.15
            )
            if os.path.exists(zoom_out) and os.path.getsize(zoom_out) > 0:
                final_video_path = zoom_out

        # Step D: Save into rendered_shorts and publishing_queue
        caption = (
            f"🎬 {series.get('title')} — Episode {ep_num}/{total_eps}\n\n"
            f"🔥 {episode.get('opening_hook')}\n\n"
            f"❓ {episode.get('cliffhanger_text')}\n\n"
            f"👉 Follow to watch Part {ep_num + 1} next!\n—\n"
        ) if not is_final else (
            f"🎬 {series.get('title')} — FINAL EPISODE\n\n"
            f"🏆 {title}\n\n"
            f"💡 {episode.get('payoff_text')}\n\n"
            f"👇 Save the full series & share with someone who needs this story!\n—\n"
        )
        hashtags = f"#series #part{ep_num} #shorts #reels #viral #cliffhanger"

        effective_job_id = job_id or series.get("job_id")
        render_id = save_rendered_short(
            job_id=effective_job_id,
            clip_id=ep_num,
            title=f"{series.get('title')} [Part {ep_num}/{total_eps}]",
            start_time=start_t,
            end_time=end_t,
            virality_score=score,
            crop_mode=crop_mode,
            theme=theme,
            video_path=final_video_path,
            caption=caption,
            hashtags=hashtags,
            account_id=account_id
        )

        update_episode_render_result(
            episode_id=episode_id,
            render_status="ready",
            rendered_video_path=final_video_path,
            render_id=render_id
        )

        # Step E: Autonomous Series-Aware Metadata & Thumbnail Generation
        try:
            series_info = {
                "series_id": series_id,
                "series_title": series.get("title", "Series"),
                "episode_number": ep_num,
                "total_episodes": total_eps,
                "is_final_episode": is_final,
                "next_teaser": episode.get("next_teaser", "")
            }
            ep_text = episode.get("main_content", "") or episode.get("opening_hook", "") or title
            meta_res = generate_video_metadata(
                target_type="episode",
                target_id=episode_id,
                title=f"{series.get('title')} - Part {ep_num}",
                text=ep_text,
                niche=niche,
                job_id=job_id or series_id,
                series_info=series_info,
                duration=end_t - start_t,
                words=active_words,
                handle=account.get("handle", "@vediohooks") if account else "@vediohooks"
            )
            save_video_metadata(
                target_type="episode",
                target_id=episode_id,
                title=f"{series.get('title')} - Part {ep_num}",
                niche=niche,
                youtube_data=meta_res.youtube.model_dump(),
                instagram_data=meta_res.instagram.model_dump(),
                tiktok_data=meta_res.tiktok.model_dump(),
                title_variations=meta_res.title_variations.model_dump(),
                quality_score=meta_res.quality.overall_score,
                quality_breakdown=meta_res.quality.model_dump(),
                job_id=job_id or series_id,
                account_id=account_id
            )

            thumb_res = generate_thumbnail_suite(
                video_path=final_video_path,
                target_type="episode",
                target_id=episode_id,
                title=f"[PART {ep_num}] {clean_ep_title}",
                niche=niche,
                start_sec=0.0,
                end_sec=max(1.0, end_t - start_t),
                aspect_ratio="9:16",
                style_mode="auto",
                brand_handle=account.get("handle", "@vediohooks") if account else "@vediohooks"
            )
            for idx, var in enumerate(thumb_res.variations):
                save_thumbnail_asset(
                    target_type="episode",
                    target_id=episode_id,
                    image_path=var.image_path,
                    headline=var.headline,
                    variation_type=var.variation_type,
                    aspect_ratio=var.aspect_ratio,
                    style_mode=var.style_mode,
                    source_timestamp=var.source_timestamp,
                    is_selected=1 if idx == 0 else 0,
                    job_id=job_id or series_id,
                    account_id=account_id
                )
        except Exception as auto_meta_err:
            print(f"[!] Warning generating auto metadata/thumbnail for episode #{episode_id}: {auto_meta_err}")

        print(f"[SUCCESS] Series Episode #{episode_id} (Part {ep_num}) rendered -> {final_video_path}")
        return {
            "episode_id": episode_id,
            "series_id": series_id,
            "episode_number": ep_num,
            "render_id": render_id,
            "video_path": final_video_path,
            "duration": round(end_t - start_t, 2),
            "render_status": "ready"
        }

    except Exception as ex:
        print(f"[ERROR] Episode #{episode_id} render failed: {ex}")
        update_episode_render_result(episode_id, render_status="failed")
        raise


def batch_render_series_job(
    series_id: str,
    crop_mode: str = "smart_face",
    theme: str = "hormozi_yellow"
) -> Dict[str, Any]:
    """
    Renders all un-rendered episodes in a series sequentially,
    with error recovery and state preservation.
    """
    series = get_series(series_id)
    if not series:
        raise ValueError(f"Series not found: {series_id}")

    update_series(series_id, {"status": "rendering"})
    episodes = series.get("episodes", [])
    results = []
    failed = 0

    for ep in episodes:
        if ep.get("render_status") == "ready" and ep.get("rendered_video_path") and os.path.exists(ep["rendered_video_path"]):
            results.append({"episode_id": ep["id"], "render_status": "already_rendered"})
            continue

        try:
            res = render_series_episode_job(
                series_id=series_id,
                episode_id=ep["id"],
                crop_mode=crop_mode,
                theme=theme
            )
            results.append(res)
        except Exception as e:
            print(f"[!] Error batch rendering episode {ep['id']}: {e}")
            failed += 1
            results.append({"episode_id": ep["id"], "render_status": "failed", "error": str(e)})

    # Final series status
    series_final = get_series(series_id)
    all_ready = all(e.get("render_status") == "ready" for e in series_final.get("episodes", [])) if series_final else False
    if all_ready:
        update_series(series_id, {"status": "completed"})
    elif failed > 0:
        update_series(series_id, {"status": "ready"})

    return {
        "series_id": series_id,
        "total_episodes": len(episodes),
        "rendered_count": len([r for r in results if r.get("render_status") in ("ready", "already_rendered")]),
        "failed_count": failed,
        "results": results
    }

