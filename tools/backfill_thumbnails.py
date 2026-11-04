"""
Backfills AI high-CTR thumbnails for all rendered shorts that lack thumbnails.
"""
import sys
import os
import sqlite3
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.thumbnail_studio import generate_thumbnail_suite
from src.db import save_thumbnail_asset, get_account

def backfill():
    conn = sqlite3.connect("jobs.db")
    conn.row_factory = sqlite3.Row
    shorts = conn.execute("SELECT id, job_id, title, video_path, duration, account_id FROM rendered_shorts").fetchall()
    existing = set(str(r[0]) for r in conn.execute("SELECT target_id FROM thumbnail_assets WHERE target_type='short'").fetchall())

    missing = [s for s in shorts if str(s["id"]) not in existing]
    print(f"[*] Found {len(missing)} shorts missing thumbnails out of {len(shorts)} total.")

    for idx, s in enumerate(missing, 1):
        s_id = s["id"]
        v_path = s["video_path"]
        if not v_path or not os.path.exists(v_path):
            print(f"[-] [{idx}/{len(missing)}] Short #{s_id} video file missing on disk ({v_path}), skipping.")
            continue

        acc = get_account(s["account_id"]) if s["account_id"] else {}
        niche = acc.get("niche", "Motivation") if acc else "Motivation"
        handle = acc.get("handle", "@vediohooks") if acc else "@vediohooks"
        title = s["title"] or f"Viral Short #{s_id}"
        duration = float(s["duration"] or 45.0)

        print(f"[+] [{idx}/{len(missing)}] Generating thumbnails for Short #{s_id} ('{title[:30]}')...")
        try:
            suite = generate_thumbnail_suite(
                video_path=v_path,
                target_type="short",
                target_id=s_id,
                title=title,
                niche=niche,
                start_sec=0.0,
                end_sec=max(1.0, duration),
                aspect_ratio="9:16",
                style_mode="auto",
                brand_handle=handle
            )
            for v_idx, var in enumerate(suite.variations):
                save_thumbnail_asset(
                    target_type="short",
                    target_id=s_id,
                    image_path=var.image_path,
                    headline=var.headline,
                    variation_type=var.variation_type,
                    aspect_ratio=var.aspect_ratio,
                    style_mode=var.style_mode,
                    source_timestamp=var.source_timestamp,
                    is_selected=1 if v_idx == 0 else 0,
                    job_id=s["job_id"],
                    account_id=s["account_id"]
                )
            print(f"    -> Saved {len(suite.variations)} thumbnail variations for Short #{s_id}")
        except Exception as err:
            print(f"[!] Error generating thumbnails for Short #{s_id}: {err}")

    print("[*] Backfill complete!")

if __name__ == "__main__":
    backfill()

