"""
Word-Level Timestamped Transcription Module using Faster-Whisper.
Generates word-level timestamps, segment boundaries, and speech confidence scores,
optimized for CPU execution using INT8 quantization and VAD (Voice Activity Detection).
"""

import os
import sys
import io
import json
import time
import gc
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

# Suppress HF symlinks warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import av
import numpy as np
import faster_whisper.audio as _fw_audio
from faster_whisper import WhisperModel

# Defensive compatibility patch for PyAV >= 15 with faster_whisper
_orig_decode_audio = _fw_audio.decode_audio

def _compatible_decode_audio(input_file, sampling_rate=16000, split_stereo=False):
    try:
        return _orig_decode_audio(input_file, sampling_rate=sampling_rate, split_stereo=split_stereo)
    except TypeError as e:
        if "metadata_errors" in str(e):
            resampler = av.audio.resampler.AudioResampler(
                format="s16",
                layout="mono" if not split_stereo else "stereo",
                rate=sampling_rate,
            )
            raw_buffer = io.BytesIO()
            dtype = None
            with av.open(input_file, mode="r") as container:
                frames = container.decode(audio=0)
                frames = _fw_audio._ignore_invalid_frames(frames)
                frames = _fw_audio._group_frames(frames, 500000)
                frames = _fw_audio._resample_frames(frames, resampler)
                for frame in frames:
                    array = frame.to_ndarray()
                    dtype = array.dtype
                    raw_buffer.write(array)
            del resampler
            gc.collect()
            audio = np.frombuffer(raw_buffer.getbuffer(), dtype=dtype).astype(np.float32) / 32768.0
            if split_stereo:
                return audio[0::2], audio[1::2]
            return audio
        raise

_fw_audio.decode_audio = _compatible_decode_audio

# Global singleton model cache and lock to prevent repeated model reloads
_MODEL_CACHE: Dict[str, WhisperModel] = {}
_MODEL_LOCK = threading.Lock()


def get_optimal_device_settings():
    """Determine best device and compute type for local machine."""
    cpu_cores = os.cpu_count() or 4
    # Allow overriding via environment variable
    env_threads = os.environ.get("WHISPER_CPU_THREADS")
    threads = int(env_threads) if env_threads and env_threads.isdigit() else cpu_cores
    return {
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": max(1, threads),
        "num_workers": 2
    }


def get_whisper_model(model_size: str = "base.en") -> WhisperModel:
    """Thread-safe singleton getter for WhisperModel instances."""
    with _MODEL_LOCK:
        if model_size in _MODEL_CACHE:
            return _MODEL_CACHE[model_size]
        
        device_settings = get_optimal_device_settings()
        print(f"[*] Initializing Faster-Whisper model '{model_size}' on {device_settings['device'].upper()} "
              f"({device_settings['compute_type']}, {device_settings['cpu_threads']} threads)...")
        start_time = time.time()
        model = WhisperModel(
            model_size_or_path=model_size,
            device=device_settings["device"],
            compute_type=device_settings["compute_type"],
            cpu_threads=device_settings["cpu_threads"],
            num_workers=device_settings["num_workers"]
        )
        load_time = time.time() - start_time
        print(f"[+] Faster-Whisper model '{model_size}' cached successfully in {load_time:.2f}s")
        _MODEL_CACHE[model_size] = model
        return model


def transcribe_audio(
    audio_path: str,
    model_size: str = "base.en",
    output_json_path: Optional[str] = None,
    language: Optional[str] = None,
    force_recompute: bool = False
) -> Dict[str, Any]:
    """
    Transcribes a 16kHz WAV audio file with word-level timestamps.
    Reuses existing valid transcript file if present, unless force_recompute=True.

    Args:
        audio_path: Path to the 16kHz mono WAV file.
        model_size: Model size ("tiny.en", "base.en", "small", "medium", "large-v3").
        output_json_path: Path to save the structured JSON transcript.
        language: Language code (e.g. 'en') or None for auto-detection.
        force_recompute: If True, ignores cached transcript file.

    Returns:
        Structured dictionary containing full text, segments, and word-level timestamps.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # 1. Fast cache check: if output JSON exists and is valid, reuse it!
    if output_json_path and os.path.exists(output_json_path) and not force_recompute:
        try:
            with open(output_json_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            if cached_data.get("segments") and cached_data.get("full_text"):
                print(f"[+] Reusing cached transcript: {output_json_path} ({cached_data.get('total_words', 0)} words)")
                cached_data["cached"] = True
                return cached_data
        except Exception as e:
            print(f"[!] Cached transcript read failed, re-transcribing: {e}")

    model = get_whisper_model(model_size)

    print(f"[*] Transcribing '{audio_path}' with word_timestamps=True & VAD filtering...")
    transcribe_start = time.time()

    segments_gen, info = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        language=language
    )

    detected_lang = info.language
    lang_prob = round(info.language_probability, 3)
    duration = round(info.duration, 2)
    print(f"[+] Audio Info: Detected Language='{detected_lang}' (conf: {lang_prob}), Duration={duration}s")

    structured_segments: List[Dict[str, Any]] = []
    total_words_count = 0
    full_text_list: List[str] = []

    for seg_idx, segment in enumerate(segments_gen):
        seg_text = segment.text.strip()
        full_text_list.append(seg_text)

        seg_words = []
        if segment.words:
            for w in segment.words:
                cleaned_word = w.word.strip()
                if cleaned_word:
                    seg_words.append({
                        "word": cleaned_word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3)
                    })
                    total_words_count += 1

        structured_segments.append({
            "id": seg_idx,
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": seg_text,
            "avg_logprob": round(segment.avg_logprob, 3),
            "no_speech_prob": round(segment.no_speech_prob, 3),
            "words": seg_words
        })

    elapsed_transcribe = time.time() - transcribe_start
    full_transcript_text = " ".join(full_text_list)

    result = {
        "audio_path": str(audio_path),
        "model_used": model_size,
        "language": detected_lang,
        "language_probability": lang_prob,
        "duration": duration,
        "transcription_time_sec": round(elapsed_transcribe, 2),
        "total_segments": len(structured_segments),
        "total_words": total_words_count,
        "full_text": full_transcript_text,
        "segments": structured_segments
    }

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Transcript saved to: {output_json_path}")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Word-Level Timestamped Transcription Engine")
    parser.add_argument("--audio", type=str, required=True, help="Path to 16kHz WAV audio file")
    parser.add_argument("--model", type=str, default="base.en", help="Whisper model size (tiny.en, base.en, small, etc.)")
    parser.add_argument("--output", type=str, default=None, help="Path to output JSON file")
    parser.add_argument("--lang", type=str, default=None, help="Language code (optional)")

    args = parser.parse_args()

    out_path = args.output
    if not out_path:
        base_stem = Path(args.audio).stem.replace("_audio_16k", "")
        out_path = f"temp/{base_stem}_transcript.json"

    print("=" * 60)
    print(" BABY STEP 3: WORD-LEVEL TIMESTAMPED TRANSCRIPTION")
    print("=" * 60)

    try:
        transcript = transcribe_audio(
            audio_path=args.audio,
            model_size=args.model,
            output_json_path=out_path,
            language=args.lang
        )

        print("\n" + "=" * 60)
        print(" TRANSCRIPTION SUMMARY")
        print("=" * 60)
        print(f"  Duration              : {transcript['duration']}s")
        print(f"  Transcribe Time       : {transcript['transcription_time_sec']}s")
        print(f"  Total Words           : {transcript['total_words']}")
        print(f"  Total Segments        : {transcript['total_segments']}")
        print(f"  Full Text             : \"{transcript['full_text']}\"")
        print("-" * 60)
        print(" First few word-level timestamps:")
        word_sample_count = 0
        for seg in transcript["segments"]:
            for w in seg["words"]:
                print(f"    [{w['start']:06.2f}s -> {w['end']:06.2f}s] (p={w['probability']:.2f}) : \"{w['word']}\"")
                word_sample_count += 1
                if word_sample_count >= 10:
                    break
            if word_sample_count >= 10:
                print("    ... (and more words in output JSON)")
                break
        print("=" * 60)
        print("[SUCCESS] Baby Step 3 completed successfully.")
    except Exception as e:
        print(f"\n[ERROR] Transcription failed: {e}", file=sys.stderr)
        sys.exit(1)
