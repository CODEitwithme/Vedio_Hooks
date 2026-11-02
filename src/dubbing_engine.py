"""
AI Voice Dubbing & Speech Cloning Engine for VedioHooks AI.
Provides 100% free multi-language neural speech synthesis, voiceover translation,
audio time-stretching, and studio mixing (ducked, replaced, bilingual).
"""

import os
import sys
import uuid
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.subtitle_translator import translate_text
from src.db import create_dubbed_render


# Curated neural voices across key international languages
CURATED_VOICES = [
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher (US)",
        "language": "English",
        "lang_code": "en",
        "gender": "Male",
        "style": "Authoritative & Powerful",
        "preview_text": "Discipline is the bridge between goals and accomplishment."
    },
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny (US)",
        "language": "English",
        "lang_code": "en",
        "gender": "Female",
        "style": "Warm, Clear & Engaging",
        "preview_text": "Never trade what you want most for what you want now."
    },
    {
        "id": "es-ES-AlvaroNeural",
        "name": "Álvaro (Spain)",
        "language": "Spanish",
        "lang_code": "es",
        "gender": "Male",
        "style": "Cinematic & Resonant",
        "preview_text": "La disciplina es el puente entre las metas y los logros."
    },
    {
        "id": "es-MX-DaliaNeural",
        "name": "Dalia (Mexico)",
        "language": "Spanish",
        "lang_code": "es",
        "gender": "Female",
        "style": "Dynamic & Energetic",
        "preview_text": "El secreto de avanzar es comenzar hoy mismo."
    },
    {
        "id": "hi-IN-MadhurNeural",
        "name": "Madhur (India)",
        "language": "Hindi",
        "lang_code": "hi",
        "gender": "Male",
        "style": "Rich, Confident & Passionate",
        "preview_text": "अनुशासन ही सफलता और सपनों के बीच का सेतु है।"
    },
    {
        "id": "hi-IN-SwaraNeural",
        "name": "Swara (India)",
        "language": "Hindi",
        "lang_code": "hi",
        "gender": "Female",
        "style": "Energetic & Expressive",
        "preview_text": "सफलता का रहस्य आज से शुरुआत करने में है।"
    },
    {
        "id": "fr-FR-HenriNeural",
        "name": "Henri (France)",
        "language": "French",
        "lang_code": "fr",
        "gender": "Male",
        "style": "Smooth & Articulate",
        "preview_text": "La discipline est le pont entre les objectifs et les résultats."
    },
    {
        "id": "fr-FR-DeniseNeural",
        "name": "Denise (France)",
        "language": "French",
        "lang_code": "fr",
        "gender": "Female",
        "style": "Sophisticated & Clear",
        "preview_text": "Le secret pour avancer est de commencer maintenant."
    },
    {
        "id": "de-DE-ConradNeural",
        "name": "Conrad (Germany)",
        "language": "German",
        "lang_code": "de",
        "gender": "Male",
        "style": "Direct & Authoritative",
        "preview_text": "Disziplin ist die Brücke zwischen Zielen und Erfolg."
    },
    {
        "id": "de-DE-KatjaNeural",
        "name": "Katja (Germany)",
        "language": "German",
        "lang_code": "de",
        "gender": "Female",
        "style": "Focused & Professional",
        "preview_text": "Der Schlüssel zum Erfolg liegt darin, heute zu beginnen."
    },
    {
        "id": "ja-JP-KeitaNeural",
        "name": "Keita (Japan)",
        "language": "Japanese",
        "lang_code": "ja",
        "gender": "Male",
        "style": "Calm & Inspiring",
        "preview_text": "規律こそが目標と達成を結ぶ架け橋である。"
    },
    {
        "id": "pt-BR-AntonioNeural",
        "name": "Antônio (Brazil)",
        "language": "Portuguese",
        "lang_code": "pt",
        "gender": "Male",
        "style": "Bold & Rhythmic",
        "preview_text": "A disciplina é a ponte entre as metas e as conquistas."
    },
    {
        "id": "it-IT-DiegoNeural",
        "name": "Diego (Italy)",
        "language": "Italian",
        "lang_code": "it",
        "gender": "Male",
        "style": "Expressive & Dynamic",
        "preview_text": "La disciplina è il ponte tra gli obiettivi e il successo."
    }
]


def list_curated_voices(language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns curated high-fidelity neural voices, optionally filtered by language code."""
    if not language or language == "all":
        return CURATED_VOICES
    lang_lower = language.lower()
    return [v for v in CURATED_VOICES if v["lang_code"] == lang_lower or lang_lower in v["language"].lower()]


async def _synthesize_edge_tts(text: str, voice_id: str, rate: str, pitch: str, output_path: str):
    """Synthesizes speech using edge_tts async client."""
    import edge_tts
    comm = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
    await comm.save(output_path)


def synthesize_speech(
    text: str,
    voice_id: str = "en-US-ChristopherNeural",
    rate_percent: int = 0,
    pitch_hz: int = 0,
    output_path: Optional[str] = None
) -> str:
    """
    Synthesizes speech from text into an audio file.
    Tries edge_tts first; falls back to Windows SAPI5 or FFmpeg procedural tone generator if offline.
    """
    if not output_path:
        os.makedirs("temp", exist_ok=True)
        output_path = f"temp/synth_{uuid.uuid4().hex[:8]}.mp3"

    rate_str = f"{rate_percent:+d}%"
    pitch_str = f"{pitch_hz:+d}Hz"

    # Attempt 1: edge-tts (High quality neural voice)
    try:
        asyncio.run(_synthesize_edge_tts(text, voice_id, rate_str, pitch_str, output_path))
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return output_path
    except Exception as e:
        print(f"[!] edge-tts synthesis failed or offline ({e}). Attempting fallback...")

    # Attempt 2: Windows PowerShell SAPI5 SpeechSynthesizer (100% offline)
    if sys.platform == "win32":
        try:
            wav_path = str(Path(output_path).with_suffix(".wav"))
            clean_text = text.replace('"', '""').replace("'", "''")
            ps_script = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$synth.Rate = {max(-10, min(10, rate_percent // 10))}; "
                f"$synth.SetOutputToWaveFile('{wav_path}'); "
                f"$synth.Speak('{clean_text}'); "
                f"$synth.Dispose();"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=10)
            if res.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 500:
                # Convert WAV to MP3 using ffmpeg
                subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-b:a", "192k", output_path], capture_output=True, timeout=10)
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
                if os.path.exists(output_path):
                    return output_path
        except Exception as e:
            print(f"[!] Windows SAPI5 speech synthesis fallback failed: {e}")

    # Attempt 3: FFmpeg procedural beep/tone vocalizer fallback (absolute fail-safe)
    duration_estimate = max(2.0, len(text.split()) * 0.45)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=220:duration={duration_estimate}",
        "-af", "volume=0.3,tremolo=f=6:d=0.7",
        "-c:a", "libmp3lame",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=10)
    return output_path


def get_media_duration(file_path: str) -> float:
    """Returns duration of an audio or video file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def dub_video_short(
    source_video_path: str,
    transcript_text: str,
    target_language: str = "es",
    voice_id: str = "es-ES-AlvaroNeural",
    blend_mode: str = "ducked",  # 'ducked', 'replace', 'bilingual'
    speed: float = 1.0,
    pitch: int = 0,
    render_id: Optional[int] = None,
    account_id: str = "acc_motivation",
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Translates, synthesizes, time-stretches, and mixes neural speech over vertical video.
    Returns metadata and database record for the dubbed short.
    """
    source_p = Path(source_video_path)
    if not source_p.exists():
        raise FileNotFoundError(f"Source video not found: {source_video_path}")

    # 1. Translate transcript if target is not English
    translated_text = transcript_text
    if target_language.lower() != "en":
        translated_text = translate_text(transcript_text, target_lang=target_language)

    # 2. Synthesize speech
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    rate_percent = int((speed - 1.0) * 100)
    speech_audio = f"temp/dubbed_voice_{uuid.uuid4().hex[:8]}.mp3"
    synthesize_speech(
        text=translated_text,
        voice_id=voice_id,
        rate_percent=rate_percent,
        pitch_hz=pitch,
        output_path=speech_audio
    )

    # 3. Time alignment check with source video duration
    video_dur = get_media_duration(str(source_p))
    audio_dur = get_media_duration(speech_audio)

    aligned_audio = speech_audio
    if video_dur > 1.0 and audio_dur > 1.0:
        ratio = audio_dur / video_dur
        # If speech is more than 15% longer or shorter than video, apply tempo stretch
        if ratio > 1.15 or ratio < 0.85:
            tempo_factor = max(0.65, min(1.8, ratio))
            stretched_audio = f"temp/aligned_voice_{uuid.uuid4().hex[:8]}.mp3"
            cmd_tempo = [
                "ffmpeg", "-y",
                "-i", speech_audio,
                "-filter:a", f"atempo={tempo_factor:.2f}",
                "-vn", stretched_audio
            ]
            res = subprocess.run(cmd_tempo, capture_output=True, timeout=15)
            if res.returncode == 0 and os.path.exists(stretched_audio):
                aligned_audio = stretched_audio

    # 4. Generate final dubbed video output
    if not output_path:
        output_path = f"output/dubbed_{target_language}_{uuid.uuid4().hex[:8]}.mp4"

    # Audio mixing strategy
    if blend_mode == "replace":
        # Video stream copied, audio completely replaced with dubbed speech
        cmd_mix = [
            "ffmpeg", "-y",
            "-i", str(source_p),
            "-i", aligned_audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]
    elif blend_mode == "bilingual":
        # Original speech panned left (30%), dubbed speech panned right (80%)
        filter_str = (
            "[0:a]volume=0.35,pan=stereo|c0=c0|c1=0.2*c1[orig];"
            "[1:a]volume=0.90,pan=stereo|c0=0.2*c0|c1=c1[dub];"
            "[orig][dub]amix=inputs=2:duration=first"
        )
        cmd_mix = [
            "ffmpeg", "-y",
            "-i", str(source_p),
            "-i", aligned_audio,
            "-filter_complex", filter_str,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]
    else:
        # Default 'ducked': Background audio ducked to 15%, Dubbed voiceover at 90%
        filter_str = "[0:a]volume=0.15[bg];[1:a]volume=0.90[fg];[bg][fg]amix=inputs=2:duration=first"
        cmd_mix = [
            "ffmpeg", "-y",
            "-i", str(source_p),
            "-i", aligned_audio,
            "-filter_complex", filter_str,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]

    proc = subprocess.run(cmd_mix, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"FFmpeg dubbing mux failed: {proc.stderr[:400]}")

    # Find voice name
    voice_match = next((v["name"] for v in CURATED_VOICES if v["id"] == voice_id), voice_id)

    # 5. Save to database
    dubbed_id = create_dubbed_render(
        source_video_path=str(source_p),
        target_language=target_language,
        voice_id=voice_id,
        voice_name=voice_match,
        dubbed_video_path=output_path,
        render_id=render_id,
        account_id=account_id,
        blend_mode=blend_mode,
        speed=speed,
        pitch=pitch,
        translated_transcript=translated_text
    )

    return {
        "dubbed_id": dubbed_id,
        "video_path": output_path,
        "source_video_path": str(source_p),
        "target_language": target_language,
        "voice_id": voice_id,
        "voice_name": voice_match,
        "blend_mode": blend_mode,
        "speed": speed,
        "pitch": pitch,
        "translated_text": translated_text,
        "duration": get_media_duration(output_path),
        "file_size_bytes": os.path.getsize(output_path)
    }
