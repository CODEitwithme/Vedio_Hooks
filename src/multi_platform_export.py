"""
Multi-Platform Export & Algorithm Adaptation Engine for VedioHooks AI Media Factory.
Generates tailored titles, captions, hashtags, and pinned comment copy
specifically optimized for Instagram Reels, YouTube Shorts, and TikTok algorithms.
"""

from typing import Dict, Any, List, Optional


PLATFORM_STRATEGIES = {
    "Motivation": {
        "yt_tags": ["motivation", "discipline", "selfimprovement", "mindset", "success", "shorts"],
        "tiktok_tags": ["#fyp", "#mindset", "#discipline", "#motivation", "#growth", "#stoic"],
        "ig_tags": ["#motivation", "#discipline", "#growthmindset", "#stoicism", "#reels", "#viral"]
    },
    "Cricket": {
        "yt_tags": ["cricket", "crickethighlights", "cricketlover", "ipl", "icc", "shorts"],
        "tiktok_tags": ["#cricket", "#crickettok", "#viratkohli", "#cricketfever", "#sports", "#fyp"],
        "ig_tags": ["#cricketreels", "#cricketfever", "#cricketnews", "#icc", "#ipl", "#reels"]
    },
    "AI & Study": {
        "yt_tags": ["aitools", "studytips", "productivity", "chatgpt", "studenthacks", "shorts"],
        "tiktok_tags": ["#studytok", "#aitools", "#studentlife", "#productivityhacks", "#tech", "#fyp"],
        "ig_tags": ["#aitools", "#studygram", "#productivity", "#artificialintelligence", "#reels"]
    },
    "Gym & Fitness": {
        "yt_tags": ["gym", "workout", "fitness", "bodybuilding", "hypertrophy", "shorts"],
        "tiktok_tags": ["#gymtok", "#fitness", "#workoutroutine", "#musclebuilding", "#gains", "#fyp"],
        "ig_tags": ["#gymreels", "#fitnessmotivation", "#bodybuilding", "#hypertrophy", "#reels"]
    },
    "Common / General": {
        "yt_tags": ["facts", "didyouknow", "interestingfacts", "curiosity", "learnontiktok", "shorts"],
        "tiktok_tags": ["#learnontiktok", "#mindblowing", "#interestingfacts", "#didyouknow", "#fyp"],
        "ig_tags": ["#interestingfacts", "#generalknowledge", "#mindblowing", "#facts", "#reels"]
    }
}


def generate_multi_platform_package(
    title: str,
    hook_text: str,
    script_summary: str,
    niche: str = "Motivation",
    base_hashtags: Optional[str] = None
) -> Dict[str, Any]:
    """
    Produces complete copy packages tailored to the unique metadata algorithms of
    Instagram Reels, YouTube Shorts, and TikTok.
    """
    niche_data = PLATFORM_STRATEGIES.get(niche, PLATFORM_STRATEGIES["Motivation"])
    clean_title = title.replace("\n", " ").strip()
    clean_hook = hook_text.replace("\n", " ").strip()

    # 1. Instagram Reels Package
    ig_hashtags = base_hashtags or " ".join(niche_data["ig_tags"])
    ig_caption = (
        f"🔥 {clean_hook}\n\n"
        f"💡 {script_summary}\n\n"
        f"👇 Save this reel for later & follow for daily {niche.lower()} insight.\n—\n"
        f"{ig_hashtags}"
    )

    # 2. YouTube Shorts Package
    # YouTube titles optimal <= 60 chars with #Shorts
    yt_title_base = clean_title[:45].strip()
    yt_title = f"{yt_title_base} #Shorts"
    yt_description = (
        f"{clean_hook}\n\n"
        f"{script_summary}\n\n"
        f"🔔 Subscribe to our channel for daily {niche} vertical shorts!\n\n"
        f"Tags: {', '.join(niche_data['yt_tags'])}"
    )
    yt_pinned_comment = (
        f"📌 What was your biggest takeaway from this? Drop your thoughts below and subscribe for daily videos! 👇"
    )

    # 3. TikTok Package
    # Short, punchy, conversational, 1-3 sentences max
    tk_caption = (
        f"{clean_hook} 👀 What do you think about this? "
        f"{' '.join(niche_data['tiktok_tags'])}"
    )
    tk_pinned_comment = (
        f"Follow for Part 2! Drop a 🔥 if this resonated with you."
    )

    return {
        "niche": niche,
        "instagram": {
            "platform": "Instagram Reels",
            "caption": ig_caption,
            "hashtags": ig_hashtags,
            "cta": "Save and share to story"
        },
        "youtube_shorts": {
            "platform": "YouTube Shorts",
            "title": yt_title,
            "description": yt_description,
            "tags": niche_data["yt_tags"],
            "pinned_comment": yt_pinned_comment
        },
        "tiktok": {
            "platform": "TikTok",
            "caption": tk_caption,
            "hashtags": niche_data["tiktok_tags"],
            "pinned_comment": tk_pinned_comment
        }
    }
