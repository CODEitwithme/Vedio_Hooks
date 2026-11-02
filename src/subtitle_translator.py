"""
Multi-Language Subtitle Translator & Bilingual Caption Engine for VedioHooks AI.
Supports 100% offline vocabulary and phrase translation across:
- Spanish (es)
- Hindi (hi)
- French (fr)
- German (de)
- Portuguese (pt)
- Japanese (ja)

Enables dual-track bilingual subtitles (Original English on top, Target Language below)
which drastically improves international retention and watch time on Instagram Reels & YouTube Shorts.
"""

import re
from typing import Dict, List, Optional, Any

SUPPORTED_LANGUAGES = {
    "en": "English (Original)",
    "es": "Spanish (Español)",
    "hi": "Hindi (हिन्दी)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "pt": "Portuguese (Português)",
    "ja": "Japanese (日本語)"
}

# Domain-specific viral phrase & vocabulary dictionary
DICTIONARY: Dict[str, Dict[str, str]] = {
    # Motivational & Mindset
    "never give up": {
        "es": "nunca te rindas",
        "hi": "कभी हार मत मानो",
        "fr": "n'abandonne jamais",
        "de": "gib niemals auf",
        "pt": "nunca desista",
        "ja": "決して諦めるな"
    },
    "discipline": {
        "es": "disciplina",
        "hi": "अनुशासन",
        "fr": "discipline",
        "de": "Disziplin",
        "pt": "disciplina",
        "ja": "規律"
    },
    "focus": {
        "es": "enfoque",
        "hi": "ध्यान केंद्रित",
        "fr": "concentration",
        "de": "Fokus",
        "pt": "foco",
        "ja": "集中"
    },
    "success": {
        "es": "éxito",
        "hi": "सफलता",
        "fr": "succès",
        "de": "Erfolg",
        "pt": "sucesso",
        "ja": "成功"
    },
    "grind": {
        "es": "esfuerzo",
        "hi": "कड़ी मेहनत",
        "fr": "travail acharné",
        "de": "harte Arbeit",
        "pt": "esforço",
        "ja": "努力"
    },
    "mindset": {
        "es": "mentalidad",
        "hi": "मानसिकता",
        "fr": "état d'esprit",
        "de": "Denkweise",
        "pt": "mentalidade",
        "ja": "マインドセット"
    },
    "power": {
        "es": "poder",
        "hi": "शक्ति",
        "fr": "pouvoir",
        "de": "Macht",
        "pt": "poder",
        "ja": "力"
    },
    "believe": {
        "es": "creer",
        "hi": "विश्वास",
        "fr": "croire",
        "de": "glauben",
        "pt": "acreditar",
        "ja": "信じる"
    },
    "dream": {
        "es": "sueño",
        "hi": "सपना",
        "fr": "rêve",
        "de": "Traum",
        "pt": "sonho",
        "ja": "夢"
    },
    "consistency": {
        "es": "consistencia",
        "hi": "निरंतरता",
        "fr": "régularité",
        "de": "Beständigkeit",
        "pt": "consistência",
        "ja": "継続性"
    },
    # Cricket & Sports
    "six": {
        "es": "seis",
        "hi": "छक्का",
        "fr": "six",
        "de": "sechs",
        "pt": "seis",
        "ja": "シックス"
    },
    "wicket": {
        "es": "wicket",
        "hi": "विकेट",
        "fr": "guichet",
        "de": "Wicket",
        "pt": "wicket",
        "ja": "ウィケット"
    },
    "champion": {
        "es": "campeón",
        "hi": "चैंपियन",
        "fr": "champion",
        "de": "Meister",
        "pt": "campeão",
        "ja": "チャンピオン"
    },
    "victory": {
        "es": "victoria",
        "hi": "जीत",
        "fr": "victoire",
        "de": "Sieg",
        "pt": "vitória",
        "ja": "勝利"
    },
    "legend": {
        "es": "leyenda",
        "hi": "महान खिलाड़ी",
        "fr": "légende",
        "de": "Legende",
        "pt": "lenda",
        "ja": "伝説"
    },
    "match": {
        "es": "partido",
        "hi": "मैच",
        "fr": "match",
        "de": "Spiel",
        "pt": "jogo",
        "ja": "試合"
    },
    # AI & Tech & Study
    "artificial intelligence": {
        "es": "inteligencia artificial",
        "hi": "कृत्रिम बुद्धिमत्ता",
        "fr": "intelligence artificielle",
        "de": "Künstliche Intelligenz",
        "pt": "inteligência artificial",
        "ja": "人工知能"
    },
    "ai": {
        "es": "IA",
        "hi": "एआई",
        "fr": "IA",
        "de": "KI",
        "pt": "IA",
        "ja": "AI"
    },
    "future": {
        "es": "futuro",
        "hi": "भविष्य",
        "fr": "futur",
        "de": "Zukunft",
        "pt": "futuro",
        "ja": "未来"
    },
    "learn": {
        "es": "aprender",
        "hi": "सीखना",
        "fr": "apprendre",
        "de": "lernen",
        "pt": "aprender",
        "ja": "学ぶ"
    },
    "secret": {
        "es": "secreto",
        "hi": "रहस्य",
        "fr": "secret",
        "de": "Geheimnis",
        "pt": "segredo",
        "ja": "秘密"
    },
    "technique": {
        "es": "técnica",
        "hi": "तकनीक",
        "fr": "technique",
        "de": "Technik",
        "pt": "técnica",
        "ja": "テクニック"
    },
    # Gym & Fitness
    "workout": {
        "es": "entrenamiento",
        "hi": "व्यायाम",
        "fr": "entraînement",
        "de": "Training",
        "pt": "treino",
        "ja": "筋トレ"
    },
    "muscle": {
        "es": "músculo",
        "hi": "मांसपेशी",
        "fr": "muscle",
        "de": "Muskel",
        "pt": "músculo",
        "ja": "筋肉"
    },
    "strength": {
        "es": "fuerza",
        "hi": "ताकत",
        "fr": "force",
        "de": "Stärke",
        "pt": "força",
        "ja": "強さ"
    },
    "rep": {
        "es": "repetición",
        "hi": "रेप",
        "fr": "répétition",
        "de": "Wiederholung",
        "pt": "repetição",
        "ja": "回数"
    },
    "beast": {
        "es": "bestia",
        "hi": "योद्धा",
        "fr": "bête",
        "de": "Biest",
        "pt": "monstro",
        "ja": "野獣"
    }
}


def translate_text(text: str, target_lang: str) -> str:
    """
    Translates an English sentence or phrase into the target language
    using local dictionary lookup and heuristic word mapping.
    """
    if not target_lang or target_lang == "en":
        return text

    clean = text.strip()
    low = clean.lower()

    # Exact phrase match
    if low in DICTIONARY and target_lang in DICTIONARY[low]:
        return DICTIONARY[low][target_lang]

    # Sub-phrase replacement
    translated = clean
    for phrase, lang_map in DICTIONARY.items():
        if target_lang in lang_map and phrase in low:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            translated = pattern.sub(lang_map[target_lang], translated)

    # Word-by-word token fallback if unchanged
    if translated == clean:
        tokens = re.findall(r"[\w']+|[.,!?;]", clean)
        out_tokens = []
        for t in tokens:
            t_low = t.lower()
            if t_low in DICTIONARY and target_lang in DICTIONARY[t_low]:
                out_tokens.append(DICTIONARY[t_low][target_lang])
            else:
                out_tokens.append(t)
        translated = " ".join(out_tokens)
        # Clean punctuation spacing
        translated = re.sub(r"\s+([.,!?;])", r"\1", translated)

    return translated


def build_bilingual_subtitle_events(
    chunks: List[List[Dict[str, Any]]],
    target_lang: str,
    theme: Dict[str, str],
    enable_kinetic_pop: bool = True,
    enable_emoji: bool = True,
    format_ass_timestamp_fn = None,
    keyword_emojis_map: Optional[Dict[str, str]] = None
) -> List[str]:
    """
    Generates ASS dialogue events with dual-language subtitles:
    - Top Layer: Alex Hormozi animated karaoke (English)
    - Bottom Layer: Clean translated subtitle line (Target Language)
    """
    dialogue_lines: List[str] = []
    emojis_map = keyword_emojis_map or {}

    for chunk in chunks:
        if not chunk:
            continue

        chunk_start = chunk[0]["start"]
        chunk_end = chunk[-1]["end"]
        raw_sentence = " ".join([w["word"] for w in chunk])
        translated_sentence = translate_text(raw_sentence, target_lang)

        # Emit the translated bottom line for the full chunk duration
        start_str = format_ass_timestamp_fn(chunk_start) if format_ass_timestamp_fn else f"{chunk_start:.2f}"
        end_str = format_ass_timestamp_fn(chunk_end) if format_ass_timestamp_fn else f"{chunk_end:.2f}"

        # Subtitle style: Secondary translated line placed at MarginV=640 (just below primary)
        # Using a sleek translucent silver styling
        if target_lang != "en":
            dialogue_lines.append(
                f"Dialogue: 1,{start_str},{end_str},HormoziTranslated,,0,0,0,,{{\\fs42\\c&H00D1D5DB&\\shad1\\bord2}}{translated_sentence}"
            )

        # For each word in chunk, emit the active karaoke top line
        for active_idx, active_word in enumerate(chunk):
            word_start = active_word["start"]
            word_end = active_word["end"]
            if word_end <= word_start:
                word_end = word_start + 0.15

            if active_idx == len(chunk) - 1:
                display_end = max(word_end, chunk_end)
            else:
                next_word_start = chunk[active_idx + 1]["start"]
                display_end = min(max(word_end, word_start + 0.1), next_word_start)

            line_parts = []
            for idx, w in enumerate(chunk):
                w_text = w["word"]
                if idx == active_idx:
                    clean_key = re.sub(r"[^\w]", "", w_text).upper()
                    emoji = emojis_map.get(clean_key, "") if enable_emoji else ""
                    emoji_str = f" {emoji}" if emoji else ""

                    if enable_kinetic_pop:
                        line_parts.append(f"{{\\fscx112\\fscy112\\c{theme['highlight']}}}{w_text}{emoji_str}{{\\fscx100\\fscy100\\c{theme['primary']}}}")
                    else:
                        line_parts.append(f"{{\\c{theme['highlight']}}}{w_text}{emoji_str}{{\\c{theme['primary']}}}")
                else:
                    line_parts.append(w_text)

            formatted_text = " ".join(line_parts)
            w_start_str = format_ass_timestamp_fn(word_start) if format_ass_timestamp_fn else f"{word_start:.2f}"
            w_end_str = format_ass_timestamp_fn(display_end) if format_ass_timestamp_fn else f"{display_end:.2f}"

            dialogue_lines.append(
                f"Dialogue: 0,{w_start_str},{w_end_str},Hormozi,,0,0,0,,{formatted_text}"
            )

    return dialogue_lines
