"""
End-to-End Pipeline Preview (Steps 1 to 4)
Runs Ingestion -> 16kHz Audio Extraction -> Word-Level Transcription -> AI Virality Selection
"""

import sys
import json
import time
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest import download_video, process_local_file, get_media_info
from src.transcribe import transcribe_audio
from src.virality_selector import select_viral_clips


def run_pipeline(source: str, is_url: bool = False, model_size: str = "base.en"):
    print("=" * 70)
    print(" AI VIRAL SHORTS MAKER - PIPELINE PREVIEW (STEPS 1 - 4)")
    print("=" * 70)
    overall_start = time.time()

    # Step 2: Ingest
    print("\n[STEP 2] INGESTION & AUDIO EXTRACTION")
    print("-" * 50)
    if is_url:
        ingest_res = download_video(source, output_dir="temp")
    else:
        ingest_res = process_local_file(source, output_dir="temp")

    video_path = ingest_res["video_path"]
    audio_path = ingest_res["audio_path"]
    video_id = ingest_res["video_id"]

    print(f"  -> Title        : {ingest_res['title']}")
    print(f"  -> Resolution   : {ingest_res['resolution']} @ {ingest_res['fps']} FPS")
    print(f"  -> Duration     : {ingest_res['duration']:.2f}s")
    print(f"  -> Audio Target : {audio_path} ({ingest_res['audio_spec']})")

    # Step 3: Transcription
    print("\n[STEP 3] WORD-LEVEL TIMESTAMPED TRANSCRIPTION (FASTER-WHISPER)")
    print("-" * 50)
    transcript_out = f"temp/{video_id}_transcript.json"
    transcript = transcribe_audio(
        audio_path=audio_path,
        model_size=model_size,
        output_json_path=transcript_out
    )

    print(f"  -> Detected Language : {transcript['language'].upper()} (Confidence: {transcript['language_probability']})")
    print(f"  -> Transcription Speed: {transcript['duration']:.1f}s audio transcribed in {transcript['transcription_time_sec']:.2f}s")
    print(f"  -> Word Count        : {transcript['total_words']} words across {transcript['total_segments']} segments")
    print(f"  -> Full Transcript   : \"{transcript['full_text']}\"")

    # Step 4: Virality Selection
    print("\n[STEP 4] AI VIRALITY & HOOK SELECTION")
    print("-" * 50)
    clips_out = f"temp/{video_id}_viral_clips.json"
    report = select_viral_clips(
        transcript_json_path=transcript_out,
        output_report_path=clips_out
    )

    print(f"  -> Engine Used       : {report.analysis_engine}")
    print(f"  -> Clips Identified  : {report.clips_found}")
    print()

    for clip in report.clips:
        print(f"  +-------------------------------------------------------------+")
        print(f"  | VIRAL CLIP #{clip.clip_id} : {clip.title[:45]}")
        print(f"  +-------------------------------------------------------------+")
        print(f"  | Virality Score : {clip.virality_score}/100")
        print(f"  | Hook Rating    : {clip.hook_rating}/10 | Engagement: {clip.engagement_rating}/10 | Flow: {clip.flow_rating}/10")
        print(f"  | Exact Timing   : {clip.start_time:05.2f}s -> {clip.end_time:05.2f}s (Duration: {clip.duration:.2f}s)")
        print(f"  | 3-Second Hook  : \"{clip.hook_text}\"")
        print(f"  | Punchline      : \"{clip.punchline_text}\"")
        print(f"  | Why It's Viral : {clip.reasoning}")
        print(f"  +-------------------------------------------------------------+\n")

    total_time = time.time() - overall_start
    print("=" * 70)
    print(f" PIPELINE COMPLETED IN {total_time:.2f}s - READY FOR STEP 5 (VIDEO SLICING)")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run pipeline steps 1-4 end-to-end")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, help="YouTube or web video URL")
    group.add_argument("--file", type=str, help="Local video file path")
    parser.add_argument("--model", type=str, default="base.en", help="Whisper model size")
    args = parser.parse_args()

    if args.url:
        run_pipeline(args.url, is_url=True, model_size=args.model)
    else:
        run_pipeline(args.file, is_url=False, model_size=args.model)
