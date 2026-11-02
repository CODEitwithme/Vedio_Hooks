"""
Viral Hook A/B Variation Engine for VedioHooks AI.
Generates 3 psychologically distinct opening hook frameworks for any video short:
- Variant A: Curiosity Gap & Controversy
- Variant B: Direct High-Urgency Command
- Variant C: Contrarian Paradigm Shift

Includes FFmpeg hook intro card rendering and automated A/B split-test publishing.
"""

import os
import re
import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.db import (
    save_hook_variant,
    list_hook_variants,
    update_hook_variant_render,
    add_publishing_draft
)


# Niche-specific hook templates and pattern interrupts
NICHE_HOOK_TEMPLATES = {
    "Motivation": {
        "A": {
            "framework": "Curiosity Gap & Hidden Truth",
            "templates": [
                "The 1 Brutal Truth Nobody Tells You About Success...",
                "Why 99% Of People Never Build Real Discipline...",
                "The Painful Secret Successful People Hide From Everyone..."
            ],
            "overlay": "THE 1 BRUTAL TRUTH\nNOBODY TELLS YOU",
            "score_offset": +7,
            "retention_lift": "+21% Retention Lift",
            "accent": "#f59e0b"
        },
        "B": {
            "framework": "High-Urgency Behavioral Command",
            "templates": [
                "STOP Scrolling If You Want To Change Your Life In 30 Days!",
                "Do NOT Ignore This If You Feel Stuck Right Now!",
                "Drop Your Excuses Right Now And Hear This!"
            ],
            "overlay": "STOP SCROLLING IF YOU\nWANT REAL CHANGE",
            "score_offset": +5,
            "retention_lift": "+16% Retention Lift",
            "accent": "#ef4444"
        },
        "C": {
            "framework": "Contrarian Paradigm Shift",
            "templates": [
                "Everything You Were Told About Motivation Is A Complete Lie...",
                "Hard Work Alone Will Not Make You Rich. Here Is Why...",
                "Comfort Is Quietly Destroying Your Potential..."
            ],
            "overlay": "EVERYTHING YOU WERE TOLD\nIS DEAD WRONG",
            "score_offset": +3,
            "retention_lift": "+12% Retention Lift",
            "accent": "#6366f1"
        }
    },
    "Cricket": {
        "A": {
            "framework": "Curiosity Gap & Hidden History",
            "templates": [
                "The Untold Story Behind This Historic Cricket Record...",
                "Why Umpires Were Baffled By This Unbelievable Decision...",
                "The Secret Strategy That Changed This Legendary Match..."
            ],
            "overlay": "THE UNTOLD STORY\nBEHIND THIS RECORD",
            "score_offset": +8,
            "retention_lift": "+22% Retention Lift",
            "accent": "#10b981"
        },
        "B": {
            "framework": "High-Urgency Fan Callout",
            "templates": [
                "Cricket Fans: You Will NOT Believe What Just Happened!",
                "Stop Scrolling! Watch This Insane Cricket Moment Right Now!",
                "Is This The Most Shocking Over In Cricket History?!"
            ],
            "overlay": "MOST SHOCKING OVER\nIN CRICKET HISTORY?!",
            "score_offset": +6,
            "retention_lift": "+17% Retention Lift",
            "accent": "#f59e0b"
        },
        "C": {
            "framework": "Contrarian Player / Match Debate",
            "templates": [
                "Why Stats Do Not Tell The Full Truth About This Legend...",
                "The Most Underrated Match In World Cup History...",
                "Why Everyone Is Wrong About This Controversial Play..."
            ],
            "overlay": "WHY STATS LIE ABOUT\nTHIS CRICKET LEGEND",
            "score_offset": +4,
            "retention_lift": "+13% Retention Lift",
            "accent": "#3b82f6"
        }
    },
    "AI & Study": {
        "A": {
            "framework": "Secret Tool / Efficiency Curiosity",
            "templates": [
                "This Free AI Tool Feels Illegal To Know As A Student...",
                "The Secret Study Technique Top 1% Students Use Quietly...",
                "How I Memorized 100 Pages in 2 Hours Using This Method..."
            ],
            "overlay": "THIS FREE AI TOOL\nFEELS ILLEGAL TO KNOW",
            "score_offset": +8,
            "retention_lift": "+24% Retention Lift",
            "accent": "#0ea5e9"
        },
        "B": {
            "framework": "Stop Wasting Time Command",
            "templates": [
                "STOP Studying Like It Is 2015. Use This Right Now!",
                "If You Are Still Taking Notes By Hand, Watch This!",
                "Delete Your Old Study Routine And Do This Instead!"
            ],
            "overlay": "STOP STUDYING LIKE IT'S 2015!\nDO THIS INSTEAD",
            "score_offset": +6,
            "retention_lift": "+18% Retention Lift",
            "accent": "#8b5cf6"
        },
        "C": {
            "framework": "Cognitive Science Paradigm Shift",
            "templates": [
                "Why Re-reading Notes Is Actually Wasting 80% Of Your Time...",
                "The Psychology Trick That Makes Your Brain Learn 3X Faster...",
                "What Top Universities Don't Want You To Know About Grades..."
            ],
            "overlay": "WHY RE-READING IS\nWASTING 80% TIME",
            "score_offset": +4,
            "retention_lift": "+14% Retention Lift",
            "accent": "#ec4899"
        }
    },
    "Gym & Fitness": {
        "A": {
            "framework": "Biomechanical Curiosity Gap",
            "templates": [
                "The 1 Reason Your Muscles Aren't Growing (It's Not Protein)...",
                "Why 90% Of Lifters Waste Their Leg Days Without Knowing It...",
                "The Secret Rep Tempo That Doubles Hypertrophy..."
            ],
            "overlay": "THE 1 REASON MUSCLES\nAREN'T GROWING",
            "score_offset": +8,
            "retention_lift": "+23% Retention Lift",
            "accent": "#ef4444"
        },
        "B": {
            "framework": "Urgent Form Warning Command",
            "templates": [
                "STOP Doing This Exercise Before You Blow Out Your Shoulders!",
                "Fix This Mistake Immediately If You Want Real Strength!",
                "Check Your Form Right Now: Are You Doing This?!"
            ],
            "overlay": "STOP DOING THIS BEFORE\nYOU GET INJURED!",
            "score_offset": +6,
            "retention_lift": "+17% Retention Lift",
            "accent": "#f97316"
        },
        "C": {
            "framework": "Fitness Myth Buster",
            "templates": [
                "Everything The Fitness Industry Told You About Cardio Is Wrong...",
                "Why You Don't Need To Spend 2 Hours In The Gym To Get Shredded...",
                "The Myth That Is Ruining Your Recovery And Sleep..."
            ],
            "overlay": "THE FITNESS MYTH\nRUINING YOUR GAINS",
            "score_offset": +4,
            "retention_lift": "+13% Retention Lift",
            "accent": "#eab308"
        }
    },
    "Common / General": {
        "A": {
            "framework": "Curiosity Gap & Mind-Blowing Fact",
            "templates": [
                "The Bizarre Secret About Human Psychology Almost Nobody Knows...",
                "What Happened When Scientists Tested This Will Shock You...",
                "The Most Mind-Blowing Discovery Of The Decade Explained..."
            ],
            "overlay": "THE BIZARRE SECRET\nALMOST NOBODY KNOWS",
            "score_offset": +7,
            "retention_lift": "+20% Retention Lift",
            "accent": "#f59e0b"
        },
        "B": {
            "framework": "Attention Command",
            "templates": [
                "Do NOT Scroll Past This If You Care About Your Future!",
                "Stop Everything And Listen To What Just Happened!",
                "Save This Video Right Now Before It Gets Taken Down!"
            ],
            "overlay": "DON'T SCROLL PAST THIS!\nWATCH THIS NOW",
            "score_offset": +5,
            "retention_lift": "+15% Retention Lift",
            "accent": "#3b82f6"
        },
        "C": {
            "framework": "Perspective Inversion",
            "templates": [
                "Why Everything We Assume About Daily Life Is Completely Backwards...",
                "The Hidden Pattern Behind Human Decisions Finally Revealed...",
                "What Really Happens When You Change One Small Habit..."
            ],
            "overlay": "WHY EVERYTHING WE ASSUME\nIS BACKWARDS",
            "score_offset": +3,
            "retention_lift": "+11% Retention Lift",
            "accent": "#10b981"
        }
    }
}


def generate_hook_variants(
    clip_text: str,
    niche: str = "Motivation",
    base_score: int = 85,
    job_id: str = "temp_job",
    clip_id: int = 0,
    account_id: str = "acc_motivation"
) -> List[Dict[str, Any]]:
    """
    Generates 3 distinct viral hook frameworks tailored to the niche and clip text.
    Saves variants to database and returns structured metadata.
    """
    niche_key = niche if niche in NICHE_HOOK_TEMPLATES else "Motivation"
    templates = NICHE_HOOK_TEMPLATES[niche_key]

    variants = []
    for letter in ["A", "B", "C"]:
        t_data = templates[letter]
        # Pick template based on clip length / hash for consistent variation
        template_idx = (len(clip_text) + ord(letter)) % len(t_data["templates"])
        hook_title = t_data["templates"][template_idx]
        overlay_text = t_data["overlay"]
        predicted_score = min(99, max(75, base_score + t_data["score_offset"]))

        variant_record = {
            "variant_letter": letter,
            "framework_type": t_data["framework"],
            "hook_title": hook_title,
            "hook_overlay_text": overlay_text,
            "predicted_score": predicted_score,
            "retention_lift": t_data["retention_lift"],
            "accent_color": t_data["accent"],
            "account_id": account_id,
            "job_id": job_id,
            "clip_id": clip_id
        }

        # Save to database
        variant_id = save_hook_variant(
            job_id=job_id,
            clip_id=clip_id,
            variant_letter=letter,
            framework_type=t_data["framework"],
            hook_title=hook_title,
            hook_overlay_text=overlay_text,
            predicted_score=predicted_score,
            retention_lift=t_data["retention_lift"],
            account_id=account_id
        )
        variant_record["id"] = variant_id
        variants.append(variant_record)

    return variants


def render_hook_variant_overlay(
    source_video_path: str,
    hook_overlay_text: str,
    accent_color: str = "#f59e0b",
    duration_sec: float = 2.5,
    output_path: Optional[str] = None,
    variant_id: Optional[int] = None
) -> str:
    """
    Renders a high-impact kinetic Hook Intro Card / Top Headline Banner
    onto the first 2.5 seconds of the vertical 9:16 video short.
    Uses FFmpeg drawtext with auto-word-wrapping and a semi-transparent dark box.
    """
    src_p = Path(source_video_path)
    if not src_p.exists():
        raise FileNotFoundError(f"Source video short missing: {source_video_path}")

    os.makedirs("output", exist_ok=True)
    if not output_path:
        output_path = f"output/hook_ab_{uuid.uuid4().hex[:8]}.mp4"

    # Clean and escape text for FFmpeg drawtext
    # Replace newlines with \n for drawtext and escape colons
    clean_lines = [line.strip().replace(":", "\\:").replace("'", "") for line in hook_overlay_text.split("\n") if line.strip()]
    escaped_text = "\\n".join(clean_lines)

    # Convert hex accent color to FFmpeg color string
    ffmpeg_box_color = "black@0.85"

    # Drawtext filter positioned at the upper third (y=220 on 1080x1920) for maximum vertical eye contact
    # Displays between t=0 and t=duration_sec
    filter_expr = (
        f"drawtext="
        f"text='{escaped_text}':"
        f"fontsize=52:"
        f"fontcolor=white:"
        f"box=1:"
        f"boxcolor={ffmpeg_box_color}:"
        f"boxborderw=18:"
        f"x=(w-text_w)/2:"
        f"y=220:"
        f"enable='between(t,0,{duration_sec:.1f})'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src_p),
        "-vf", filter_expr,
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        output_path
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0 or not os.path.exists(output_path):
        # Fallback without drawtext if font/rendering issues occur
        print(f"[!] Hook drawtext failed ({proc.stderr[:200]}). Falling back to clean copy...")
        cmd_fallback = ["ffmpeg", "-y", "-i", str(src_p), "-c", "copy", output_path]
        subprocess.run(cmd_fallback, capture_output=True, timeout=15)

    if variant_id:
        update_hook_variant_render(variant_id, output_path)

    return output_path


def queue_ab_split_test(
    account_id: str,
    job_id: str,
    variants: List[Dict[str, Any]],
    base_caption: str = "Watch this viral moment!",
    hashtags: str = "#viral #shorts #reels"
) -> List[int]:
    """
    Schedules the 3 generated variants into publishing_queue as a linked A/B split-test suite.
    Each variant is tagged with [Hook A], [Hook B], [Hook C] for performance tracking.
    """
    draft_ids = []
    for var in variants:
        letter = var.get("variant_letter", "A")
        hook_title = var.get("hook_title", "")
        framework = var.get("framework_type", "Standard Hook")
        pred_score = var.get("predicted_score", 90)

        formatted_caption = (
            f"⚡ [Hook {letter}: {framework} | Score: {pred_score}/100]\n"
            f"🔥 {hook_title}\n\n"
            f"{base_caption}\n\n"
            f"{hashtags}"
        )

        draft_id = add_publishing_draft(
            render_id=var.get("render_id", 1),
            job_id=job_id,
            account_id=account_id,
            caption=formatted_caption,
            hashtags=hashtags,
            platform="instagram"
        )
        draft_ids.append(draft_id)

    return draft_ids
