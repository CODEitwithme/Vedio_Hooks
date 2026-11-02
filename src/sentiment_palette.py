"""
AI Caption Sentiment & Emotional Palette Auto-Tagging Engine for VedioHooks AI Media Factory.
Analyzes speech transcript text, emotional polarity, lexical urgency, and domain context
to automatically select the optimal visual theme, karaoke subtitle color palette,
ambient music profile, and sound design presets to maximize audience retention.
"""

import re
from typing import Dict, Any, List, Optional


# Lexical dictionaries for sentiment & intensity scoring
URGENT_WORDS = {
    "now", "stop", "never", "always", "secret", "truth", "mistake", "warning",
    "critical", "danger", "must", "listen", "urgent", "nobody", "wrong", "fail",
    "destroy", "eliminate", "wake", "broken", "shocking", "insane", "lies"
}

GROWTH_WORDS = {
    "money", "wealth", "grow", "scale", "success", "profit", "discipline",
    "achieve", "habit", "routine", "champion", "win", "million", "rich",
    "power", "results", "freedom", "invest", "unstoppable", "greatness"
}

TECH_STUDY_WORDS = {
    "ai", "tool", "website", "code", "study", "learn", "app", "model",
    "python", "student", "productivity", "technique", "algorithm", "prompt",
    "software", "extension", "free", "efficient", "hack", "tutorial", "exam"
}

FITNESS_WORDS = {
    "muscle", "gym", "workout", "lift", "training", "squat", "bench", "reps",
    "hypertrophy", "sets", "protein", "recovery", "diet", "body", "form",
    "biceps", "chest", "posture", "exercise", "strength", "biomechanics"
}

CRICKET_WORDS = {
    "cricket", "match", "wicket", "six", "over", "ball", "bat", "ipl",
    "world cup", "century", "run", "bowler", "batsman", "stadium", "kohli",
    "rohit", "dhoni", "record", "captain", "innings", "championship"
}


def analyze_transcript_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyzes lexical token frequency, emotional polarity, and energy level of a transcript.
    """
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = clean.split()
    total_tokens = max(1, len(tokens))

    urgent_hits = sum(1 for t in tokens if t in URGENT_WORDS)
    growth_hits = sum(1 for t in tokens if t in GROWTH_WORDS)
    tech_hits = sum(1 for t in tokens if t in TECH_STUDY_WORDS)
    fit_hits = sum(1 for t in tokens if t in FITNESS_WORDS)
    cricket_hits = sum(1 for t in tokens if t in CRICKET_WORDS)

    # Exclamation & uppercase intensity check
    exclamation_count = text.count("!")
    caps_count = sum(1 for word in text.split() if word.isupper() and len(word) > 1)

    intensity_score = min(
        1.0,
        ((urgent_hits * 1.5 + growth_hits * 1.2 + exclamation_count * 0.8 + caps_count * 0.5) / (total_tokens * 0.25))
    )

    # Determine dominant emotional category
    scores = {
        "urgent_motivational": urgent_hits * 1.4,
        "triumphant_growth": growth_hits * 1.3,
        "analytical_educational": tech_hits * 1.5,
        "fitness_discipline": fit_hits * 1.5,
        "sports_high_tension": cricket_hits * 1.5
    }

    dominant_mood = max(scores, key=scores.get)
    # Fallback to inspirational if no specific lexical keywords triggered
    if max(scores.values()) == 0:
        dominant_mood = "inspirational_reflective"

    return {
        "dominant_mood": dominant_mood,
        "intensity_score": round(intensity_score, 2),
        "total_words": total_tokens,
        "urgent_count": urgent_hits,
        "growth_count": growth_hits,
        "tech_count": tech_hits,
        "fitness_count": fit_hits,
        "cricket_count": cricket_hits
    }


def classify_sentiment_and_palette(
    transcript_text: str,
    niche: Optional[str] = None,
    virality_score: Optional[int] = 85
) -> Dict[str, Any]:
    """
    Produces complete visual and audio packaging recommendations based on lexical sentiment
    and niche identity.
    """
    analysis = analyze_transcript_sentiment(transcript_text)
    mood = analysis["dominant_mood"]
    intensity = analysis["intensity_score"]

    # Align with account niche if specified
    clean_niche = (niche or "").lower()
    if "study" in clean_niche or "ai" in clean_niche:
        mood = "analytical_educational"
    elif "cricket" in clean_niche:
        mood = "sports_high_tension"
    elif "gym" in clean_niche or "fitness" in clean_niche:
        mood = "fitness_discipline"

    # Theme & Visual Palette mapping
    if mood == "analytical_educational":
        theme_id = "cyber_cyan"
        theme_name = "Cyber Cyan (High-Tech Clean)"
        accent_color = "#06b6d4"
        secondary_color = "#38bdf8"
        music_mood = "lofi_focus"
        ducking_db = -12.0
        sfx_preset = "subtle_whoosh"
        emojis = ["⚡", "🤖", "💡", "🧠", "📚", "🚀", "💻", "🔥"]
        rationale = "Cool cyan highlights increase focus and readability for complex technical tutorials and study workflows."

    elif mood == "fitness_discipline":
        theme_id = "crimson_bold"
        theme_name = "Crimson Bold (High-Adrenaline Power)"
        accent_color = "#ef4444"
        secondary_color = "#f97316"
        music_mood = "high_energy_trap"
        ducking_db = -16.0
        sfx_preset = "sub_bass_drop"
        emojis = ["💪", "🏋️", "🔥", "⚡", "😤", "🦍", "💯", "🦾"]
        rationale = "High-energy red-orange tones signal physical urgency, power output, and form correction authority."

    elif mood == "sports_high_tension":
        theme_id = "neon_green"
        theme_name = "Stadium Electric (Sports Energy)"
        accent_color = "#10b981"
        secondary_color = "#fbbf24"
        music_mood = "epic_strings"
        ducking_db = -14.0
        sfx_preset = "whoosh_subbass"
        emojis = ["🏏", "🏆", "🔥", "⚡", "👑", "🎯", "💥", "🏟️"]
        rationale = "High-contrast emerald and gold typography mimics premium sports broadcasting and statistical telemetry."

    elif mood == "triumphant_growth":
        theme_id = "emerald_growth"
        theme_name = "Emerald Wealth & Momentum"
        accent_color = "#10b981"
        secondary_color = "#34d399"
        music_mood = "ambient_chill"
        ducking_db = -14.0
        sfx_preset = "sub_bass_drop"
        emojis = ["💸", "📈", "👑", "🚀", "💰", "🏆", "💎", "⭐"]
        rationale = "Emerald green reinforces monetary growth, business momentum, and disciplined compounding."

    else:  # Default urgent_motivational or inspirational_reflective
        theme_id = "hormozi_yellow"
        theme_name = "Hormozi Yellow (Aggressive Retention)"
        accent_color = "#fbbf24"
        secondary_color = "#ffffff"
        music_mood = "cinematic_dark"
        ducking_db = -15.0
        sfx_preset = "whoosh_subbass"
        emojis = ["🔥", "⚡", "👑", "🤫", "🎯", "🛑", "💀", "⏳"]
        rationale = "Aggressive yellow box highlighting on dark backgrounds delivers maximum contrast and 0-3s hook retention."

    return {
        "mood": mood,
        "intensity_score": intensity,
        "recommended_theme": theme_id,
        "theme_name": theme_name,
        "accent_color": accent_color,
        "secondary_color": secondary_color,
        "ambient_music_mood": music_mood,
        "recommended_ducking_db": ducking_db,
        "sfx_preset": sfx_preset,
        "contextual_emojis": emojis,
        "editorial_rationale": rationale,
        "lexical_breakdown": analysis
    }
