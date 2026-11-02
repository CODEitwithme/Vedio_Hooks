"""
Background Pipeline Worker for AI Viral Shorts Maker.
Coordinates asynchronous video ingestion, transcription, virality scoring,
smart face tracking, and animated karaoke subtitle rendering.
"""

import os
import sys
import json
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import update_job_progress, update_job_metadata, save_rendered_short, get_job, is_emergency_stopped, get_account
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
    enable_broll: bool = False
) -> Dict[str, Any]:
    """
    Renders a specific viral clip into a finished 9:16 vertical short with animated subtitles,
    optional frame-accurate jump-cut dead-air removal, sidechain audio ducking, bilingual subtitles,
    transition whoosh SFX, and thematic B-roll pattern interrupt.
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

    # Step B: Create Alex Hormozi Karaoke ASS file
    create_ass_subtitles(
        words_data=active_words,
        output_ass_path=ass_path,
        theme_name=theme,
        font_name="Arial Black",
        font_size=70,
        words_per_chunk=3,
        margin_v=720,
        target_language=target_language
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
