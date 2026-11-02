import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.db import init_db, get_db_connection

def seed():
    init_db()
    conn = get_db_connection()
    with conn:
        # Check if already exists
        cur = conn.execute("SELECT id FROM jobs WHERE id = 'TLKxdTmk-zc'")
        if not cur.fetchone():
            conn.execute("""
                INSERT INTO jobs (id, source_type, source_path, title, duration, resolution, status, progress, current_step, transcript_json_path, clips_json_path)
                VALUES (
                    'TLKxdTmk-zc',
                    'url',
                    'https://youtu.be/TLKxdTmk-zc',
                    'The Most Eye Opening 10 Minutes Of Your Life | David Goggins',
                    615.12,
                    '1920x1080',
                    'ready',
                    100,
                    'Analysis complete. 3 viral clips discovered.',
                    'temp/TLKxdTmk-zc_transcript.json',
                    'temp/TLKxdTmk-zc_viral_clips.json'
                )
            """)

            # Add existing rendered shorts
            conn.execute("""
                INSERT INTO rendered_shorts (job_id, clip_id, title, start_time, end_time, duration, virality_score, crop_mode, theme, video_path)
                VALUES
                (
                    'TLKxdTmk-zc',
                    1,
                    'Viral Short #1: The Hard Work Dilemma (Smart Face Centered)',
                    64.73, 81.40, 16.67, 85,
                    'smart_face', 'hormozi_yellow',
                    'output/David_Goggins_Face_Centered_Captions_Short.mp4'
                ),
                (
                    'TLKxdTmk-zc',
                    1,
                    'Viral Short #1: The Hard Work Dilemma (Center Crop)',
                    64.73, 81.40, 16.67, 85,
                    'center', 'hormozi_yellow',
                    'output/TLKxdTmk-zc_The Most Eye Opening 10 Minutes Of Your _clip1_center_9x16_captions_hormozi_yellow.mp4'
                ),
                (
                    'TLKxdTmk-zc',
                    1,
                    'Viral Short #1: The Hard Work Dilemma (Blurred Fill)',
                    64.73, 81.40, 16.67, 85,
                    'blur_fill', 'hormozi_green',
                    'output/TLKxdTmk-zc_The Most Eye Opening 10 Minutes Of Your _clip1_blur_fill_9x16_captions_hormozi_green.mp4'
                )
            """)
            print("Successfully seeded existing David Goggins job and rendered shorts!")
        else:
            print("Job already exists in database.")
    conn.close()

if __name__ == "__main__":
    seed()
