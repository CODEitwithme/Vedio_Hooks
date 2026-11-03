"""
AI Virality Selector Module for Long Video to Viral Shorts Maker.
Analyzes full transcripts with word-level timestamps using LLMs (Gemini / OpenAI)
or intelligent heuristic fallback to identify, score, and extract high-engagement,
self-contained viral clips (30-60s) with 3-second hooks and satisfying punchlines.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class WordInfo(BaseModel):
    word: str
    start: float
    end: float
    probability: float = 1.0


class ViralClip(BaseModel):
    clip_id: int
    title: str = Field(description="Catchy, click-worthy title for YouTube Shorts / TikTok / Reels")
    hook_text: str = Field(description="The first 3-5 seconds that stop the scroll")
    punchline_text: str = Field(description="The closing resolution, lesson, or punchline")
    start_time: float = Field(description="Exact word-aligned start timestamp in seconds")
    end_time: float = Field(description="Exact word-aligned end timestamp in seconds")
    duration: float = Field(description="Duration in seconds (end_time - start_time)")
    virality_score: int = Field(ge=0, le=100, description="Overall virality score from 0 to 100")
    # Multi-dimensional scores (0-100)
    hook_score: int = Field(default=80, ge=0, le=100, description="Opening hook score 0-100")
    engagement_score: int = Field(default=80, ge=0, le=100, description="Emotional resonance & pace score 0-100")
    story_score: int = Field(default=75, ge=0, le=100, description="Narrative completeness score 0-100")
    context_score: int = Field(default=80, ge=0, le=100, description="Standalone context clarity score 0-100")
    overall_score: int = Field(default=80, ge=0, le=100, description="Weighted composite virality score 0-100")
    # Backwards-compatible 1-10 ratings
    hook_rating: int = Field(default=8, ge=1, le=10, description="Hook strength rating from 1 to 10")
    engagement_rating: int = Field(default=8, ge=1, le=10, description="Content interest & engagement rating from 1 to 10")
    flow_rating: int = Field(default=8, ge=1, le=10, description="Narrative completeness and flow rating from 1 to 10")
    # Granular speech telemetry
    curiosity_score: int = Field(default=70, ge=0, le=100, description="Curiosity gap rating 0-100")
    speaking_pace_wps: float = Field(default=2.5, description="Speaking pace in words per second")
    dead_air_sec: float = Field(default=0.0, description="Total dead air pauses > 1.2s")
    reasoning: str = Field(description="Detailed breakdown of why this clip was selected")
    suggested_caption: str = Field(default="", description="Ready-to-post Instagram / TikTok caption")
    suggested_hashtags: List[str] = Field(default_factory=list, description="Targeted viral hashtags")
    full_quote: str = Field(description="Exact verbatim transcript contained in this clip")


class ViralityReport(BaseModel):
    video_id: str
    total_source_duration: float
    analysis_engine: str
    clips_found: int
    clips: List[ViralClip]


def extract_all_words(transcript_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flattens all words from segments into a single ordered list with timestamps."""
    words = []
    for segment in transcript_data.get("segments", []):
        for w in segment.get("words", []):
            words.append(w)
    return words


def snap_timestamp_to_words(target_time: float, all_words: List[Dict[str, Any]], mode: str = "start") -> float:
    """
    Snaps an arbitrary timestamp to the nearest exact word boundary
    to prevent cutting off syllables.
    """
    if not all_words:
        return target_time

    if mode == "start":
        # Find the word that starts closest to target_time (preferring word start >= target_time - 0.5)
        candidates = [w for w in all_words if abs(w["start"] - target_time) <= 2.5]
        if candidates:
            best = min(candidates, key=lambda w: abs(w["start"] - target_time))
            return best["start"]
        return max(0.0, target_time)
    else:  # mode == "end"
        candidates = [w for w in all_words if abs(w["end"] - target_time) <= 2.5]
        if candidates:
            best = min(candidates, key=lambda w: abs(w["end"] - target_time))
            return best["end"]
        return target_time


def generate_social_metadata(text: str, hook_text: str, punchline_text: str) -> tuple[str, List[str]]:
    """
    Generates a high-converting Instagram Reel / TikTok caption and hashtag bundle.
    """
    hook_clean = hook_text.strip()
    punch_clean = punchline_text.strip()
    
    # Generate clean, engaging caption
    caption = (
        f"🔥 {hook_clean}\n\n"
        f"💡 {punch_clean}\n\n"
        f"👇 Save this for later & share with someone who needs this mindset today.\n"
        f"—\n"
    )
    
    # Topic keyword extraction for hashtags
    text_lower = text.lower()
    tag_pool = ["#shorts", "#reels", "#mindset", "#motivation", "#growth"]
    if any(k in text_lower for k in ["fear", "pain", "hard", "struggle", "fight", "discipline"]):
        tag_pool.extend(["#discipline", "#mentalstrength", "#overcome"])
    if any(k in text_lower for k in ["dream", "goal", "success", "money", "win"]):
        tag_pool.extend(["#success", "#ambition", "#hustle"])
    if any(k in text_lower for k in ["habit", "daily", "routine", "focus"]):
        tag_pool.extend(["#habits", "#productivity", "#focus"])
    if any(k in text_lower for k in ["people", "listen", "truth", "secret", "never"]):
        tag_pool.extend(["#lifelessons", "#wisdom", "#truth"])
        
    hashtags = list(dict.fromkeys(tag_pool))[:8]
    caption += " ".join(hashtags)
    return caption, hashtags


DANGLING_CONJUNCTIONS = {"and", "so", "but", "because", "or", "also", "then", "which", "plus"}
DANGLING_PRONOUNS = {"he", "she", "it", "they", "this", "that", "these", "those", "him", "her", "them", "his", "their", "its"}


def is_dangling_start_segment(seg_text: str) -> bool:
    """Detects whether a speech segment starts mid-thought without full context."""
    clean = seg_text.strip().lower()
    words = clean.split()
    if not words:
        return True
    w0 = words[0].strip(".,!?:;\"'()[]{}")
    if w0 in DANGLING_CONJUNCTIONS or w0 in DANGLING_PRONOUNS:
        return True
    if clean.startswith(("when we ", "what happened was ", "in that case ", "and that's when ", "and so ")):
        return True
    return False


def evaluate_candidate_multidimensional(
    text: str,
    duration: float,
    words: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Evaluates a candidate clip window across 8 transparent viral dimensions:
      1. Opening Hook Strength (0-100)
      2. Curiosity Gap (0-100)
      3. Emotional Intensity (0-100)
      4. Story Completeness & Punchline (0-100)
      5. Standalone Context Clarity (0-100)
      6. Information Density & Speaking Pace (WPS)
      7. Dead Air & Silence Penalties
      8. Overall Weighted Virality Score (0-100)
    """
    text_clean = text.strip()
    text_lower = text_clean.lower()
    words_list = text_clean.split()
    word_count = len(words_list)
    effective_dur = max(1.0, duration)
    wps = round(word_count / effective_dur, 2)

    # 1. Opening Hook Strength (first 8 words / ~4 seconds)
    hook_keywords = [
        "why", "how", "what", "never", "always", "secret", "truth", "mind", "pain",
        "fear", "stop", "realize", "people", "tell you", "listen", "remember", "hard",
        "discipline", "impossible", "hate", "fight", "strong", "weak", "crazy", "rule"
    ]
    first_8_words = " ".join(words_list[:8]).lower() if words_list else ""
    hook_hits = sum(1 for kw in hook_keywords if kw in first_8_words)
    has_question = "?" in text_clean[:90]

    hook_score = 65
    if has_question:
        hook_score += 15
    hook_score += min(20, hook_hits * 7)
    if any(pronoun in first_8_words for pronoun in ["you", "your", "yourself"]):
        hook_score += 8
    hook_score = min(98, max(45, hook_score))

    # 2. Curiosity Gap
    curiosity_phrases = ["the reason", "the secret", "nobody talks about", "truth is", "what happens", "most people", "mistake"]
    curiosity_hits = sum(1 for phrase in curiosity_phrases if phrase in text_lower)
    curiosity_score = min(95, 60 + curiosity_hits * 12)

    # 3. Emotional Intensity & Keyword Density
    emotional_words = [
        "pain", "fear", "hate", "love", "die", "kill", "fight", "broke", "win", "lose",
        "destroy", "suffer", "danger", "obsessed", "relentless", "tears", "greatest", "darkness"
    ]
    emotional_hits = sum(1 for ew in emotional_words if ew in text_lower)
    emotional_score = min(98, 65 + min(30, emotional_hits * 6))

    # 4. Speaking Pace & Pacing Score (sweet spot 2.2 to 3.5 wps)
    if 2.2 <= wps <= 3.5:
        pace_score = 95
    elif 1.8 <= wps < 2.2 or 3.5 < wps <= 4.0:
        pace_score = 80
    else:
        pace_score = 65

    # 5. Dead Air Calculation
    dead_air_sec = 0.0
    if words and len(words) > 1:
        for k in range(len(words) - 1):
            gap = words[k + 1].get("start", 0.0) - words[k].get("end", 0.0)
            if gap > 1.2:
                dead_air_sec += gap
    dead_air_penalty = min(20, int(dead_air_sec * 5))

    # 6. Standalone Context Clarity (Deep context verification)
    context_score = 85
    first_clean = first_8_words.lower()

    # Penalize dangling starters that require prior knowledge
    if first_clean.startswith(("and ", "so ", "but ", "because ", "or ", "also ", "then ", "which ", "plus ")):
        context_score -= 18
    if words_list and words_list[0].lower().strip(".,!?:;\"'()[]{}") in [
        "he", "she", "it", "they", "this", "that", "these", "those", "him", "her", "them", "his", "their", "its"
    ]:
        context_score -= 15
    if first_clean.startswith(("when we ", "what happened was ", "in that case ", "and that's when ", "and so ")):
        context_score -= 15

    # Reward explicit setup anchors, interviewer question anchors, and premise statements
    has_question_setup = any("?" in w for w in words_list[:12]) if words_list else False
    if has_question_setup:
        context_score += 15

    setup_phrases = (
        "why do", "how to", "how do", "the biggest", "the secret to",
        "if you want", "most people", "here is why", "the reason why",
        "the truth about", "what happens when", "did you know", "someone asked me"
    )
    if any(sp in first_clean for sp in setup_phrases):
        context_score += 12

    context_score = min(98, max(40, context_score))

    # 7. Story Completeness & Punchline Quality
    ends_cleanly = text_clean.endswith((".", "!", "?"))
    last_8_words = " ".join(words_list[-8:]).lower() if words_list else ""
    resolution_words = ["that's why", "remember", "finally", "lesson", "win", "believe", "done", "forever", "result", "truth"]
    has_resolution = any(rw in last_8_words for rw in resolution_words)

    story_score = 75
    if ends_cleanly:
        story_score += 15
    else:
        # Penalize mid-sentence premature cutoffs
        story_score -= 15

    if has_resolution:
        story_score += 10
    story_score = min(98, max(40, story_score))

    # Composite Engagement Score
    engagement_score = int(0.5 * emotional_score + 0.3 * pace_score + 0.2 * curiosity_score)

    # Overall Virality Score
    raw_overall = (
        0.35 * hook_score +
        0.25 * engagement_score +
        0.20 * story_score +
        0.20 * context_score -
        dead_air_penalty
    )
    overall_score = min(98, max(55, int(round(raw_overall))))

    # Mapped 1-10 ratings for backward compatibility
    hook_rating = min(10, max(1, int(round(hook_score / 10))))
    engagement_rating = min(10, max(1, int(round(engagement_score / 10))))
    flow_rating = min(10, max(1, int(round(story_score / 10))))

    hook_text = " ".join(words_list[:7]) if words_list else "Opening hook"
    punchline_text = " ".join(words_list[-7:]) if words_list else "Closing punchline"
    caption, hashtags = generate_social_metadata(text_clean, hook_text, punchline_text)

    reasoning = (
        f"Strong opening hook ({hook_rating}/10, score {hook_score}) with high emotional keyword density; "
        f"pacing {wps} words/sec (engagement {engagement_score}); "
        f"narrative resolution ({story_score}/100); context ({context_score}/100)."
    )

    return {
        "overall_score": overall_score,
        "hook_score": hook_score,
        "engagement_score": engagement_score,
        "story_score": story_score,
        "context_score": context_score,
        "curiosity_score": curiosity_score,
        "speaking_pace_wps": wps,
        "dead_air_sec": round(dead_air_sec, 2),
        "hook_rating": hook_rating,
        "engagement_rating": engagement_rating,
        "flow_rating": flow_rating,
        "reasoning": reasoning,
        "suggested_caption": caption,
        "suggested_hashtags": hashtags,
        "hook_text": hook_text,
        "punchline_text": punchline_text
    }


def score_candidate_text(text: str, duration: float) -> tuple[int, int, int, int, str]:
    """
    Scores a text segment for short-form virality based on hook strength,
    emotional resonance, speaking cadence, and narrative payoff.
    Returns: (virality_score, hook_rating, engagement_rating, flow_rating, reasoning)
    """
    eval_res = evaluate_candidate_multidimensional(text, duration)
    return (
        eval_res["overall_score"],
        eval_res["hook_rating"],
        eval_res["engagement_rating"],
        eval_res["flow_rating"],
        eval_res["reasoning"]
    )


def heuristic_virality_selector(
    transcript_data: Dict[str, Any],
    min_duration: float = 25.0,
    max_duration: float = 60.0,
    max_clips: int = 3
) -> ViralityReport:
    """
    Intelligent heuristic selector used when no LLM API key is configured.
    Evaluates speech density, sentence hooks, emotional keywords, and narrative payoff.
    """
    all_words = extract_all_words(transcript_data)
    segments = transcript_data.get("segments", [])
    total_duration = transcript_data.get("duration", 0.0)

    clips: List[ViralClip] = []

    # If the whole video is short (e.g. <= 60 seconds), the entire clip is a candidate short
    if total_duration <= max_duration and total_duration >= 3.0:
        full_text = transcript_data.get("full_text", "")
        start_t = all_words[0]["start"] if all_words else 0.0
        end_t = all_words[-1]["end"] if all_words else total_duration

        eval_res = evaluate_candidate_multidimensional(full_text, end_t - start_t, all_words)

        clip = ViralClip(
            clip_id=1,
            title="Short Highlight: " + (full_text[:35] + "..." if len(full_text) > 35 else full_text),
            hook_text=eval_res["hook_text"],
            punchline_text=eval_res["punchline_text"],
            start_time=round(start_t, 2),
            end_time=round(end_t, 2),
            duration=round(end_t - start_t, 2),
            virality_score=eval_res["overall_score"],
            hook_score=eval_res["hook_score"],
            engagement_score=eval_res["engagement_score"],
            story_score=eval_res["story_score"],
            context_score=eval_res["context_score"],
            overall_score=eval_res["overall_score"],
            hook_rating=eval_res["hook_rating"],
            engagement_rating=eval_res["engagement_rating"],
            flow_rating=eval_res["flow_rating"],
            curiosity_score=eval_res["curiosity_score"],
            speaking_pace_wps=eval_res["speaking_pace_wps"],
            dead_air_sec=eval_res["dead_air_sec"],
            reasoning=eval_res["reasoning"],
            suggested_caption=eval_res["suggested_caption"],
            suggested_hashtags=eval_res["suggested_hashtags"],
            full_quote=full_text
        )
        clips.append(clip)
    else:
        # Multi-clip candidate window scanner across long video
        candidates = []
        step_stride = max(1, len(segments) // 25)  # scan through segments with stride
        
        for i in range(0, len(segments), step_stride):
            # 1. Pre-Roll Context Expansion:
            # Check if segment i starts mid-thought/dangling pronoun or if previous segment was an anchor question
            start_i = i
            if i > 0:
                prev_text = segments[i - 1].get("text", "").strip()
                curr_text = segments[i].get("text", "").strip()
                # Include host question or setup anchor
                if prev_text.endswith("?"):
                    start_i = i - 1
                elif is_dangling_start_segment(curr_text):
                    start_i = i - 1

            seg_start = segments[start_i]["start"]
            best_candidate = None
            best_score = -1.0

            # 2. Multi-Window Terminal Boundary Resolution:
            # Scan endpoints within [min_duration, max_duration] to avoid mid-sentence cuts
            for j in range(start_i, len(segments)):
                seg_end = segments[j]["end"]
                duration = seg_end - seg_start
                if duration > max_duration:
                    break
                if duration >= min_duration:
                    cand_text = " ".join(s.get("text", "") for s in segments[start_i:j + 1]).strip()
                    cand_words = [w for w in all_words if seg_start <= w.get("start", 0.0) <= seg_end]
                    eval_res = evaluate_candidate_multidimensional(cand_text, duration, cand_words)

                    seg_j_clean = segments[j].get("text", "").strip()
                    ends_cleanly = seg_j_clean.endswith((".", "!", "?"))

                    # Natural speech breath pause before next segment
                    next_pause = 0.0
                    if j + 1 < len(segments):
                        next_pause = max(0.0, segments[j + 1].get("start", 0.0) - seg_end)

                    cand_score = float(eval_res["overall_score"])
                    if ends_cleanly:
                        cand_score += 10.0  # Reward complete sentence ending
                    if next_pause >= 0.35:
                        cand_score += 5.0   # Reward natural speech pause

                    if cand_score > best_score:
                        best_score = cand_score
                        start_snap = snap_timestamp_to_words(seg_start, all_words, mode="start")
                        end_snap = snap_timestamp_to_words(seg_end, all_words, mode="end")
                        best_candidate = {
                            "seg_i": start_i,
                            "seg_j": j,
                            "start_time": start_snap,
                            "end_time": end_snap,
                            "duration": round(end_snap - start_snap, 2),
                            "eval": eval_res,
                            "text": cand_text
                        }

            if best_candidate and best_candidate["duration"] >= min_duration:
                candidates.append(best_candidate)

        # Sort candidates by virality score descending
        candidates.sort(key=lambda c: c["eval"]["overall_score"], reverse=True)

        # Non-Maximum Suppression (NMS) to strictly prevent overlapping clips
        selected_ranges = []
        clip_counter = 1
        for cand in candidates:
            c_start = cand["start_time"]
            c_end = cand["end_time"]
            # Enforce at least 15s separation or < 15% overlap
            overlap = False
            for s_start, s_end in selected_ranges:
                overlap_start = max(c_start, s_start)
                overlap_end = min(c_end, s_end)
                if overlap_end > overlap_start:
                    overlap_dur = overlap_end - overlap_start
                    if overlap_dur > 0.15 * min(cand["duration"], s_end - s_start):
                        overlap = True
                        break
            if not overlap and cand["duration"] >= min_duration:
                selected_ranges.append((c_start, c_end))
                ev = cand["eval"]
                words = cand["text"].split()
                title_clean = " ".join(words[:5])
                
                clips.append(ViralClip(
                    clip_id=clip_counter,
                    title=f"Viral Short #{clip_counter}: {title_clean}...",
                    hook_text=ev["hook_text"],
                    punchline_text=ev["punchline_text"],
                    start_time=round(c_start, 2),
                    end_time=round(c_end, 2),
                    duration=cand["duration"],
                    virality_score=ev["overall_score"],
                    hook_score=ev["hook_score"],
                    engagement_score=ev["engagement_score"],
                    story_score=ev["story_score"],
                    context_score=ev["context_score"],
                    overall_score=ev["overall_score"],
                    hook_rating=ev["hook_rating"],
                    engagement_rating=ev["engagement_rating"],
                    flow_rating=ev["flow_rating"],
                    curiosity_score=ev["curiosity_score"],
                    speaking_pace_wps=ev["speaking_pace_wps"],
                    dead_air_sec=ev["dead_air_sec"],
                    reasoning=ev["reasoning"],
                    suggested_caption=ev["suggested_caption"],
                    suggested_hashtags=ev["suggested_hashtags"],
                    full_quote=cand["text"]
                ))
                clip_counter += 1
                if len(clips) >= max_clips:
                    break

        # Sort selected clips chronologically by start_time for a logical presentation
        clips.sort(key=lambda c: c.start_time)
        for idx, cl in enumerate(clips):
            cl.clip_id = idx + 1

    return ViralityReport(
        video_id=transcript_data.get("audio_path", "video"),
        total_source_duration=total_duration,
        analysis_engine="Heuristic-WordBoundary-v1",
        clips_found=len(clips),
        clips=clips
    )


def build_llm_prompt(transcript_data: Dict[str, Any], min_duration: float = 30.0, max_duration: float = 60.0) -> str:
    """Builds the system and user prompt for LLM virality analysis."""
    segments = transcript_data.get("segments", [])
    total_duration = transcript_data.get("duration", 0.0)

    # Format segments with timing for the LLM
    formatted_transcript = []
    for s in segments:
        formatted_transcript.append(f"[{s['start']:.2f}s -> {s['end']:.2f}s] {s['text']}")
    transcript_str = "\n".join(formatted_transcript)

    # Adjust min duration if the entire video is shorter than 30s
    effective_min = min(min_duration, max(5.0, total_duration * 0.7))
    effective_max = min(max_duration, max(effective_min + 5.0, total_duration))

    prompt = f"""
You are an expert viral video editor and content strategist specializing in TikTok, YouTube Shorts, and Instagram Reels (inspired by Opus Clip and Alex Hormozi style pacing).

TASK:
Analyze the following timestamped video transcript. Identify up to 3 self-contained, high-potential viral short clips.

RULES FOR VIRAL CLIPS:
1. TARGET DURATION: Between {effective_min:.0f} and {effective_max:.0f} seconds.
2. 3-SECOND HOOK: The clip MUST start with an attention-grabbing statement, question, surprise, or curiosity hook.
3. STANDALONE CONTEXT (CRITICAL): The clip MUST be 100% self-contained and immediately clear to a viewer who has NEVER seen the original video.
   - NEVER start mid-sentence or with dangling pronouns ("he said...", "and then they...", "because when that happened...").
   - If the highlight is an answer to an interviewer/host's question, INCLUDE the question at the start so the premise is crystal clear.
   - The opening 3-5 seconds must establish WHO or WHAT the topic is about.
4. SATISFYING PUNCHLINE & RESOLUTION: The clip MUST resolve cleanly with a full conclusion, moral, or realization. NEVER cut off mid-thought or mid-sentence.
5. EXACT TIMESTAMPS: start_time and end_time MUST strictly align with the segment timestamps provided below.
6. VIRALITY SCORING (0-100):
   - Hook Rating (1-10): Ability to stop the scroll in first 3s.
   - Engagement Rating (1-10): Information density or emotional resonance.
   - Flow Rating (1-10): Clean standalone narrative arc & context clarity.
   - Score = (Hook * 4) + (Engagement * 3) + (Flow * 3).

TRANSCRIPT:
Total Duration: {total_duration:.2f}s
{transcript_str}

OUTPUT FORMAT:
Return a JSON array of objects with the following schema:
[
  {{
    "clip_id": 1,
    "title": "Short punchy click-worthy title",
    "hook_text": "Exact text of the opening 3-5 seconds",
    "punchline_text": "Exact text of the concluding takeaway",
    "start_time": 0.0,
    "end_time": 30.0,
    "hook_rating": 9,
    "engagement_rating": 9,
    "flow_rating": 9,
    "virality_score": 90,
    "reasoning": "Why this clip will capture attention and retain viewers",
    "full_quote": "Exact transcript text for this clip"
  }}
]
Only return the valid JSON array.
"""
    return prompt.strip()


def llm_virality_selector(
    transcript_data: Dict[str, Any],
    min_duration: float = 30.0,
    max_duration: float = 60.0
) -> ViralityReport:
    """
    Evaluates transcript virality using Gemini or OpenAI API when configured.
    Falls back gracefully to heuristic selector if keys are absent or API fails.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    all_words = extract_all_words(transcript_data)
    total_duration = transcript_data.get("duration", 0.0)

    if not gemini_key and not openai_key:
        print("[!] Neither GEMINI_API_KEY nor OPENAI_API_KEY found in environment.")
        print("[*] Using intelligent Heuristic Word-Boundary Selector...")
        return heuristic_virality_selector(transcript_data, min_duration=min_duration, max_duration=max_duration)

    prompt = build_llm_prompt(transcript_data, min_duration, max_duration)
    raw_response_text = None
    engine_name = None

    # Try Google Gemini first if key available
    if gemini_key:
        try:
            print("[*] Calling Gemini API for virality analysis...")
            from google import genai
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            raw_response_text = response.text
            engine_name = "Gemini-2.5-Flash"
        except Exception as ex:
            print(f"[WARNING] Gemini API call failed: {ex}")

    # Fallback to OpenAI if Gemini failed or wasn't set
    if not raw_response_text and openai_key:
        try:
            print("[*] Calling OpenAI API for virality analysis...")
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert short-form video editor."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            raw_response_text = response.choices[0].message.content
            engine_name = "OpenAI-GPT-4o-mini"
        except Exception as ex:
            print(f"[WARNING] OpenAI API call failed: {ex}")

    # If LLM succeeded, parse JSON and snap timestamps
    if raw_response_text:
        try:
            # Clean markdown codeblocks if present
            cleaned = re.sub(r"^```json\s*", "", raw_response_text.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed_data = json.loads(cleaned)

            if isinstance(parsed_data, dict) and "clips" in parsed_data:
                parsed_clips = parsed_data["clips"]
            elif isinstance(parsed_data, list):
                parsed_clips = parsed_data
            else:
                parsed_clips = [parsed_data]

            final_clips: List[ViralClip] = []
            for idx, c in enumerate(parsed_clips):
                start_t = snap_timestamp_to_words(float(c.get("start_time", 0.0)), all_words, mode="start")
                end_t = snap_timestamp_to_words(float(c.get("end_time", total_duration)), all_words, mode="end")
                dur = round(end_t - start_t, 2)

                final_clips.append(ViralClip(
                    clip_id=idx + 1,
                    title=c.get("title", f"Viral Clip #{idx + 1}"),
                    hook_text=c.get("hook_text", ""),
                    punchline_text=c.get("punchline_text", ""),
                    start_time=round(start_t, 2),
                    end_time=round(end_t, 2),
                    duration=dur,
                    virality_score=int(c.get("virality_score", 85)),
                    hook_rating=int(c.get("hook_rating", 8)),
                    engagement_rating=int(c.get("engagement_rating", 8)),
                    flow_rating=int(c.get("flow_rating", 8)),
                    reasoning=c.get("reasoning", "Strong hook with clean arc."),
                    full_quote=c.get("full_quote", "")
                ))

            return ViralityReport(
                video_id=transcript_data.get("audio_path", "video"),
                total_source_duration=total_duration,
                analysis_engine=engine_name or "LLM-Processed",
                clips_found=len(final_clips),
                clips=final_clips
            )
        except Exception as parse_err:
            print(f"[WARNING] Failed to parse LLM response JSON ({parse_err}). Falling back to heuristic.")

    # Fallback to heuristic
    return heuristic_virality_selector(transcript_data, min_duration=min_duration, max_duration=max_duration)


def select_viral_clips(
    transcript_json_path: str,
    output_report_path: Optional[str] = None,
    min_duration: float = 15.0,
    max_duration: float = 60.0,
    force_recompute: bool = False
) -> ViralityReport:
    """
    Main entry point for Step 4. Takes a transcript JSON file, runs AI virality analysis,
    and returns a structured report with selected clips. Reuses valid existing report if present.
    """
    if not os.path.exists(transcript_json_path):
        raise FileNotFoundError(f"Transcript JSON not found: {transcript_json_path}")

    # Cache check
    if output_report_path and os.path.exists(output_report_path) and not force_recompute:
        try:
            with open(output_report_path, "r", encoding="utf-8") as f:
                cached_report_dict = json.load(f)
            cached_report = ViralityReport(**cached_report_dict)
            if cached_report.clips:
                print(f"[+] Reusing cached virality report: {output_report_path} ({cached_report.clips_found} clips)")
                return cached_report
        except Exception as e:
            print(f"[!] Cached virality report read failed, re-analyzing: {e}")

    with open(transcript_json_path, "r", encoding="utf-8") as f:
        transcript_data = json.load(f)

    print(f"[*] Running AI Virality Selector on '{transcript_json_path}'...")
    report = llm_virality_selector(
        transcript_data,
        min_duration=min_duration,
        max_duration=max_duration
    )

    if output_report_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_report_path)), exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"[SUCCESS] Virality report saved to: {output_report_path}")

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Virality Selector Tool")
    parser.add_argument("--transcript", type=str, required=True, help="Path to transcript JSON file")
    parser.add_argument("--output", type=str, default=None, help="Path to save virality report JSON")
    parser.add_argument("--min-sec", type=float, default=15.0, help="Minimum clip duration in seconds")
    parser.add_argument("--max-sec", type=float, default=60.0, help="Maximum clip duration in seconds")

    args = parser.parse_args()

    out_file = args.output
    if not out_file:
        base_stem = Path(args.transcript).stem.replace("_transcript", "")
        out_file = f"temp/{base_stem}_viral_clips.json"

    print("=" * 60)
    print(" BABY STEP 4: AI VIRALITY SELECTOR")
    print("=" * 60)

    try:
        report_result = select_viral_clips(
            args.transcript,
            output_report_path=out_file,
            min_duration=args.min_sec,
            max_duration=args.max_sec
        )

        print("\n" + "=" * 60)
        print(" VIRALITY ANALYSIS REPORT")
        print("=" * 60)
        print(f"  Analysis Engine : {report_result.analysis_engine}")
        print(f"  Total Duration  : {report_result.total_source_duration}s")
        print(f"  Clips Selected  : {report_result.clips_found}")
        print("-" * 60)
        for clip in report_result.clips:
            print(f"  [Clip #{clip.clip_id}] Virality Score: {clip.virality_score}/100")
            print(f"    Title      : {clip.title}")
            print(f"    Timing     : {clip.start_time:05.2f}s -> {clip.end_time:05.2f}s ({clip.duration:.2f}s)")
            print(f"    Hook       : \"{clip.hook_text}\" (Rating: {clip.hook_rating}/10)")
            print(f"    Punchline  : \"{clip.punchline_text}\"")
            print(f"    Reasoning  : {clip.reasoning}")
            print("-" * 60)
        print("=" * 60)
        print("[SUCCESS] Baby Step 4 completed successfully.")
    except Exception as e:
        print(f"\n[ERROR] Virality selection failed: {e}", file=sys.stderr)
        sys.exit(1)
