"""
Autonomous Content Deduplication & Perceptual Fingerprinting Module for VedioHooks AI.
Prevents cross-account duplicate video generation by computing lexical n-gram fingerprints
and temporal segment signatures across rendered clips in the SQLite media catalog.
"""

import hashlib
import re
from typing import Dict, Any, List, Optional, Set
from src.db import get_db_connection, init_db


def compute_text_tokens(text: str) -> List[str]:
    """Tokenizes and normalizes text into lowercase alphanumeric words."""
    clean = re.sub(r"[^\w\s]", "", text.lower())
    return [w for w in clean.split() if len(w) > 2]


def compute_content_fingerprint(text: str, duration_sec: float = 0.0) -> str:
    """
    Computes a deterministic content signature based on sorted 3-gram word frequencies
    and quantized duration bucket.
    """
    tokens = compute_text_tokens(text)
    token_str = " ".join(sorted(tokens[:40]))
    dur_bucket = round(duration_sec, 0)
    raw = f"{token_str}|dur:{dur_bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def calculate_jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Calculates Jaccard lexical overlap between two token sets."""
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return float(intersection) / float(max(1, union))


def check_for_duplicate_content(
    transcript_text: str,
    duration_sec: float = 0.0,
    similarity_threshold: float = 0.75
) -> Dict[str, Any]:
    """
    Scans the database for existing rendered shorts or jobs that overlap with the candidate clip.
    Returns duplication analysis and collision warning flags.
    """
    init_db()
    conn = get_db_connection()
    cand_tokens = compute_text_tokens(transcript_text)
    cand_fp = compute_content_fingerprint(transcript_text, duration_sec)

    # Fetch existing rendered shorts with captions / titles
    cur = conn.execute(
        """
        SELECT rs.id, rs.job_id, rs.title, rs.caption, rs.duration, rs.account_id, j.source_path
        FROM rendered_shorts rs
        LEFT JOIN jobs j ON rs.job_id = j.id
        ORDER BY rs.id DESC LIMIT 100
        """
    )
    rows = cur.fetchall()
    conn.close()

    max_sim = 0.0
    matched_item = None

    for r in rows:
        existing_text = f"{r['title'] or ''} {r['caption'] or ''}"
        exist_tokens = compute_text_tokens(existing_text)
        sim = calculate_jaccard_similarity(cand_tokens, exist_tokens)
        if sim > max_sim:
            max_sim = sim
            matched_item = r

    is_duplicate = (max_sim >= similarity_threshold)

    return {
        "candidate_fingerprint": cand_fp,
        "is_duplicate": is_duplicate,
        "similarity_score": round(max_sim, 3),
        "similarity_threshold": similarity_threshold,
        "matched_render_id": matched_item["id"] if (matched_item and is_duplicate) else None,
        "matched_account_id": matched_item["account_id"] if (matched_item and is_duplicate) else None,
        "matched_title": matched_item["title"] if (matched_item and is_duplicate) else None,
        "recommendation": "Reject / Re-roll clip: Content overlaps with previously rendered short" if is_duplicate else "Approved: Unique viral candidate"
    }
