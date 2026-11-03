"""
Database & State Manager for VedioHooks AI Multi-Account Enterprise Media Factory.
Handles accounts, content sources, AI director plans, persistent jobs, renders,
publishing queue, and system settings in SQLite with migration safety.
"""

import os
import sys
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

def get_db_path() -> str:
    """Returns the active SQLite database path, supporting environment override for testing."""
    return os.environ.get("VEDIOHOOKS_DB_PATH", "jobs.db")


def get_db_connection() -> sqlite3.Connection:
    """Creates a thread-safe connection to the SQLite database."""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


DEFAULT_ACCOUNTS = [
    {
        "id": "acc_motivation",
        "name": "Apex Mindset & Discipline",
        "handle": "@apex_discipline",
        "niche": "Motivation",
        "avatar_emoji": "🔥",
        "brand_color": "#f59e0b",
        "status": "active",
        "daily_target": 2,
        "posting_schedule": "09:00, 18:00",
        "ai_personality": (
            "A powerful motivational content strategist who understands human psychology, "
            "stoic discipline, high retention storytelling, and emotional scroll-stopping hooks. "
            "Tone: uncompromising, inspiring, direct."
        ),
        "content_style": "Cinematic pacing, dark contrast visuals, strong 1-3s hook, dramatic musical swell.",
        "default_theme": "hormozi_yellow",
        "default_crop_mode": "smart_face",
        "hashtag_strategy": "#discipline #motivation #mindset #grind #stoic #success #shorts #reels",
        "caption_template": "🔥 {hook}\n\n💡 Takeaway: {punchline}\n\n👇 Save this for later & share with someone who needs discipline today.\n—\n{hashtags}"
    },
    {
        "id": "acc_cricket",
        "name": "Cricket Vault & Analysis",
        "handle": "@cricket_vault_hd",
        "niche": "Cricket",
        "avatar_emoji": "🏏",
        "brand_color": "#10b981",
        "status": "active",
        "daily_target": 2,
        "posting_schedule": "13:00, 20:00",
        "ai_personality": (
            "A cricket content researcher and sports storyteller. Verifies factual claims, "
            "never invents player records/stats, respects broadcast rights, prioritizes confirmed match analysis. "
            "Tone: energetic, knowledgeable, passionate."
        ),
        "content_style": "Sports-themed dynamic cuts, scorecards, player milestones, energetic subtitles, clean match context.",
        "default_theme": "hormozi_green",
        "default_crop_mode": "smart_face",
        "hashtag_strategy": "#cricket #cricketreels #icc #ipl #cricketnews #crickethistory #shorts #reels",
        "caption_template": "🏏 {hook}\n\n📊 Match Context: {punchline}\n\n👇 Drop your thoughts in the comments! Follow for daily cricket analysis.\n—\n{hashtags}"
    },
    {
        "id": "acc_ai_study",
        "name": "AI Tools & Study Hacks",
        "handle": "@aistudyhub",
        "niche": "AI & Study",
        "avatar_emoji": "🤖",
        "brand_color": "#0ea5e9",
        "status": "active",
        "daily_target": 2,
        "posting_schedule": "11:00, 17:00",
        "ai_personality": (
            "An AI educator and study strategist who explains complicated tech tools, active recall, "
            "spaced repetition, and student productivity simply and accurately without hype. "
            "Tone: articulate, practical, insightful."
        ),
        "content_style": "Screen tutorial styling, step-by-step explanations, clean typography, minimalist animations, high information density.",
        "default_theme": "cyber_cyan",
        "default_crop_mode": "center",
        "hashtag_strategy": "#aitools #studyhacks #studentlife #productivity #artificialintelligence #tech #shorts #reels",
        "caption_template": "🤖 {hook}\n\n📌 Pro Tip: {punchline}\n\n👇 Bookmark this tool / technique for your next session!\n—\n{hashtags}"
    },
    {
        "id": "acc_fitness",
        "name": "Iron Physique & Training",
        "handle": "@ironphysique_fit",
        "niche": "Gym & Fitness",
        "avatar_emoji": "💪",
        "brand_color": "#ef4444",
        "status": "active",
        "daily_target": 2,
        "posting_schedule": "07:30, 19:30",
        "ai_personality": (
            "A fitness education content strategist. Strict rule: never invent medical claims or endorse "
            "dangerous exercise form; emphasizes progressive overload, biomechanics, recovery, and discipline. "
            "Tone: intense, educational, authoritative."
        ),
        "content_style": "Dynamic cuts, workout demonstrations, clear instructional cues, bold fitness graphics.",
        "default_theme": "beast_red",
        "default_crop_mode": "smart_face",
        "hashtag_strategy": "#gym #fitness #workout #bodybuilding #muscle #gymmotivation #fitnesstips #reels",
        "caption_template": "💪 {hook}\n\n🏋️ Form Cue: {punchline}\n\n👇 Save for your next workout session! Tag your gym partner.\n—\n{hashtags}"
    },
    {
        "id": "acc_general",
        "name": "Curiosity Stream & Discoveries",
        "handle": "@curiosity_stream",
        "niche": "Common / General",
        "avatar_emoji": "🌍",
        "brand_color": "#8b5cf6",
        "status": "active",
        "daily_target": 2,
        "posting_schedule": "12:00, 21:00",
        "ai_personality": (
            "A general knowledge and discovery strategist who identifies fascinating facts, history breakthroughs, "
            "and broadly appealing shareable stories with distinct identity. "
            "Tone: curious, captivating, wonder-inducing."
        ),
        "content_style": "Engaging hook-driven storytelling, intriguing questions, clean minimalist subtitles, universal appeal.",
        "default_theme": "clean_minimal",
        "default_crop_mode": "smart_face",
        "hashtag_strategy": "#didyouknow #facts #curiosity #history #science #knowledge #mindblown #reels",
        "caption_template": "🌍 {hook}\n\n🤯 The Discovery: {punchline}\n\n👇 Did you know this? Share with a curious friend!\n—\n{hashtags}"
    }
]


def init_db():
    """Initializes and migrates the database schema safely without data loss."""
    conn = get_db_connection()
    with conn:
        # 1. Accounts Table (Multi-Account Architecture)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                handle TEXT NOT NULL,
                niche TEXT NOT NULL,
                avatar_emoji TEXT DEFAULT '⚡',
                brand_color TEXT DEFAULT '#6366f1',
                status TEXT DEFAULT 'active', -- active, paused
                daily_target INTEGER DEFAULT 2,
                posting_schedule TEXT DEFAULT '09:00, 18:00',
                ai_personality TEXT,
                content_style TEXT,
                default_theme TEXT DEFAULT 'hormozi_yellow',
                default_crop_mode TEXT DEFAULT 'smart_face',
                hashtag_strategy TEXT,
                caption_template TEXT,
                meta_access_token TEXT DEFAULT '',
                meta_account_id TEXT DEFAULT '',
                meta_connected INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Base jobs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                account_id TEXT DEFAULT 'acc_motivation',
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                title TEXT,
                duration REAL DEFAULT 0.0,
                resolution TEXT,
                status TEXT NOT NULL, -- queued, downloading, transcribing, analyzing, ready, failed, cancelled
                progress INTEGER DEFAULT 0,
                current_step TEXT,
                error_message TEXT,
                transcript_json_path TEXT,
                clips_json_path TEXT,
                priority INTEGER DEFAULT 1,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                scheduled_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Rendered shorts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rendered_shorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT DEFAULT 'acc_motivation',
                job_id TEXT NOT NULL,
                clip_id INTEGER NOT NULL,
                title TEXT,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                virality_score INTEGER DEFAULT 80,
                crop_mode TEXT NOT NULL, -- center, blur_fill, smart_face
                theme TEXT NOT NULL,     -- hormozi_yellow, hormozi_green, cyber_cyan, fire_orange, beast_red, clean_minimal
                video_path TEXT NOT NULL,
                caption TEXT,
                hashtags TEXT,
                status TEXT DEFAULT 'pending', -- pending, approved, rejected
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

        # 4. Instagram / Social Publishing Queue table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publishing_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT DEFAULT 'acc_motivation',
                render_id INTEGER NOT NULL,
                job_id TEXT NOT NULL,
                platform TEXT DEFAULT 'instagram', -- instagram, tiktok, youtube_shorts
                status TEXT DEFAULT 'draft',        -- draft, scheduled, approved, published, failed
                caption TEXT NOT NULL,
                hashtags TEXT NOT NULL,
                scheduled_time TIMESTAMP,
                published_time TIMESTAMP,
                post_id TEXT,
                permalink TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (render_id) REFERENCES rendered_shorts (id),
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

        # 5. Content Sources Table (Discovery & Attribution)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_sources (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                source_type TEXT NOT NULL, -- url, file, channel, rights_cleared
                source_url_or_path TEXT NOT NULL,
                title TEXT,
                attribution TEXT,
                verification_notes TEXT,
                status TEXT DEFAULT 'ready', -- ready, in_progress, archived
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. AI Content Director Plans Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_content_plans (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                job_id TEXT,
                topic TEXT NOT NULL,
                target_audience TEXT,
                video_idea TEXT,
                hook TEXT,
                script_selection TEXT,
                clip_start REAL DEFAULT 0.0,
                clip_end REAL DEFAULT 0.0,
                retention_strategy TEXT,
                editing_instructions TEXT,
                subtitle_style TEXT,
                caption TEXT,
                hashtags TEXT,
                cover_text TEXT,
                copyright_notes TEXT,
                quality_score INTEGER DEFAULT 85,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 7. Analytics metrics table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT DEFAULT 'acc_motivation',
                publishing_id INTEGER NOT NULL,
                platform TEXT DEFAULT 'instagram',
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                watch_time_sec REAL DEFAULT 0.0,
                retention_rate REAL DEFAULT 0.0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (publishing_id) REFERENCES publishing_queue (id)
            )
        """)

        # 8. System settings table (Emergency stop, globals)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 9. Dubbed Renders Table (AI Multi-Language Dubbing Lab)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dubbed_renders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                render_id INTEGER,
                account_id TEXT DEFAULT 'acc_motivation',
                source_video_path TEXT NOT NULL,
                target_language TEXT NOT NULL,
                voice_id TEXT NOT NULL,
                voice_name TEXT NOT NULL,
                blend_mode TEXT DEFAULT 'ducked',
                speed REAL DEFAULT 1.0,
                pitch INTEGER DEFAULT 0,
                dubbed_video_path TEXT NOT NULL,
                translated_transcript TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (render_id) REFERENCES rendered_shorts (id)
            )
        """)
        # 12. Video Metadata & SEO Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                target_type TEXT DEFAULT 'short', -- short, episode, long_form
                target_id TEXT NOT NULL,
                account_id TEXT DEFAULT 'acc_motivation',
                title TEXT NOT NULL,
                niche TEXT DEFAULT 'Motivation',
                youtube_json TEXT,
                instagram_json TEXT,
                tiktok_json TEXT,
                title_variations_json TEXT,
                quality_score INTEGER DEFAULT 85,
                quality_breakdown_json TEXT,
                status TEXT DEFAULT 'draft', -- draft, approved, rejected
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 13. Thumbnail Assets & Variations Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thumbnail_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                target_type TEXT DEFAULT 'short', -- short, episode, long_form
                target_id TEXT NOT NULL,
                account_id TEXT DEFAULT 'acc_motivation',
                aspect_ratio TEXT DEFAULT '9:16', -- 16:9, 9:16, 1:1
                platform TEXT DEFAULT 'universal',
                style_mode TEXT DEFAULT 'auto',   -- auto, face_focused, cinematic, custom
                variation_type TEXT DEFAULT 'emotional', -- emotional, curiosity, professional, custom
                headline TEXT,
                image_path TEXT NOT NULL,
                source_timestamp REAL DEFAULT 1.0,
                is_selected INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # 10. Viral Hook A/B Variants Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hook_ab_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                clip_id INTEGER NOT NULL,
                account_id TEXT DEFAULT 'acc_motivation',
                variant_letter TEXT NOT NULL, -- 'A', 'B', 'C'
                framework_type TEXT NOT NULL, -- 'Curiosity Gap', 'High-Urgency Command', 'Contrarian Narrative'
                hook_title TEXT NOT NULL,
                hook_overlay_text TEXT NOT NULL,
                predicted_score INTEGER DEFAULT 90,
                retention_lift TEXT DEFAULT '+15%',
                rendered_video_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

        # 11. AI Cliffhanger Series Engine Tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id TEXT PRIMARY KEY,
                account_id TEXT DEFAULT 'acc_motivation',
                job_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                main_topic TEXT,
                main_speakers TEXT,
                episode_count INTEGER DEFAULT 3,
                status TEXT DEFAULT 'ready', -- draft, generating, ready, rendering, completed, failed
                quality_score INTEGER DEFAULT 85,
                story_arc_json TEXT,
                series_memory_json TEXT,
                generation_mode TEXT DEFAULT 'auto', -- auto, guided, custom
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id),
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS series_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id TEXT NOT NULL,
                episode_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                opening_hook TEXT,
                context_premise TEXT,
                main_content TEXT,
                payoff_text TEXT,
                cliffhanger_text TEXT,
                cliffhanger_type TEXT,
                cliffhanger_score INTEGER DEFAULT 80,
                next_teaser TEXT,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                connection_prev TEXT,
                connection_next TEXT,
                is_final_episode INTEGER DEFAULT 0,
                quality_score INTEGER DEFAULT 85,
                quality_breakdown_json TEXT,
                word_boundaries_json TEXT,
                rendered_video_path TEXT,
                render_id INTEGER,
                render_status TEXT DEFAULT 'pending', -- pending, rendering, ready, failed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE,
                FOREIGN KEY (render_id) REFERENCES rendered_shorts (id)
            )
        """)

        # 12. Video Metadata & SEO Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                target_type TEXT DEFAULT 'short', -- short, episode, long_form
                target_id TEXT NOT NULL,
                account_id TEXT DEFAULT 'acc_motivation',
                title TEXT NOT NULL,
                niche TEXT DEFAULT 'Motivation',
                youtube_json TEXT,
                instagram_json TEXT,
                tiktok_json TEXT,
                title_variations_json TEXT,
                quality_score INTEGER DEFAULT 85,
                quality_breakdown_json TEXT,
                status TEXT DEFAULT 'draft', -- draft, approved, rejected
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 13. Thumbnail Assets & Variations Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thumbnail_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                target_type TEXT DEFAULT 'short', -- short, episode, long_form
                target_id TEXT NOT NULL,
                account_id TEXT DEFAULT 'acc_motivation',
                aspect_ratio TEXT DEFAULT '9:16', -- 16:9, 9:16, 1:1
                platform TEXT DEFAULT 'universal',
                style_mode TEXT DEFAULT 'auto',   -- auto, face_focused, cinematic, custom
                variation_type TEXT DEFAULT 'emotional', -- emotional, curiosity, professional, custom
                headline TEXT,
                image_path TEXT NOT NULL,
                source_timestamp REAL DEFAULT 1.0,
                is_selected INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- Safe Column Migrations for Existing Tables ---
        job_cols = [row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        if "account_id" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN account_id TEXT DEFAULT 'acc_motivation'")
        if "priority" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 1")
        if "retry_count" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN retry_count INTEGER DEFAULT 0")
        if "max_retries" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN max_retries INTEGER DEFAULT 3")
        if "scheduled_at" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN scheduled_at TIMESTAMP")
        if "started_at" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN started_at TIMESTAMP")
        if "completed_at" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN completed_at TIMESTAMP")

        render_cols = [row["name"] for row in conn.execute("PRAGMA table_info(rendered_shorts)").fetchall()]
        if "account_id" not in render_cols:
            conn.execute("ALTER TABLE rendered_shorts ADD COLUMN account_id TEXT DEFAULT 'acc_motivation'")
        if "caption" not in render_cols:
            conn.execute("ALTER TABLE rendered_shorts ADD COLUMN caption TEXT")
        if "hashtags" not in render_cols:
            conn.execute("ALTER TABLE rendered_shorts ADD COLUMN hashtags TEXT")
        if "status" not in render_cols:
            conn.execute("ALTER TABLE rendered_shorts ADD COLUMN status TEXT DEFAULT 'pending'")

        pub_cols = [row["name"] for row in conn.execute("PRAGMA table_info(publishing_queue)").fetchall()]
        if "account_id" not in pub_cols:
            conn.execute("ALTER TABLE publishing_queue ADD COLUMN account_id TEXT DEFAULT 'acc_motivation'")

        analytics_cols = [row["name"] for row in conn.execute("PRAGMA table_info(analytics_metrics)").fetchall()]
        if "account_id" not in analytics_cols:
            conn.execute("ALTER TABLE analytics_metrics ADD COLUMN account_id TEXT DEFAULT 'acc_motivation'")

        # --- Initial Seeding of 5 Accounts if table is empty ---
        acc_count = conn.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()["cnt"]
        if acc_count == 0:
            now = datetime.now(timezone.utc).isoformat()
            for acc in DEFAULT_ACCOUNTS:
                conn.execute("""
                    INSERT INTO accounts (
                        id, name, handle, niche, avatar_emoji, brand_color, status,
                        daily_target, posting_schedule, ai_personality, content_style,
                        default_theme, default_crop_mode, hashtag_strategy, caption_template,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    acc["id"], acc["name"], acc["handle"], acc["niche"],
                    acc["avatar_emoji"], acc["brand_color"], acc["status"],
                    acc["daily_target"], acc["posting_schedule"], acc["ai_personality"],
                    acc["content_style"], acc["default_theme"], acc["default_crop_mode"],
                    acc["hashtag_strategy"], acc["caption_template"], now, now
                ))

        # Default emergency_stop setting
        conn.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('emergency_stop', '0')")
        conn.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('global_automation', '1')")

    conn.close()


# --- Account Management CRUD Functions ---

def list_accounts() -> List[Dict[str, Any]]:
    """Lists all configured Instagram accounts with stats."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("SELECT * FROM accounts ORDER BY created_at ASC")
    accounts = []
    for row in cur.fetchall():
        acc = dict(row)
        # Fetch operational counts for this account
        cur_j = conn.execute("SELECT COUNT(*) as count FROM jobs WHERE account_id = ?", (acc["id"],))
        acc["jobs_count"] = cur_j.fetchone()["count"]

        cur_r = conn.execute("SELECT COUNT(*) as count FROM rendered_shorts WHERE account_id = ?", (acc["id"],))
        acc["renders_count"] = cur_r.fetchone()["count"]

        cur_p = conn.execute("SELECT COUNT(*) as count FROM publishing_queue WHERE account_id = ? AND status = 'draft'", (acc["id"],))
        acc["drafts_count"] = cur_p.fetchone()["count"]

        cur_s = conn.execute("SELECT COUNT(*) as count FROM publishing_queue WHERE account_id = ? AND status = 'scheduled'", (acc["id"],))
        acc["scheduled_count"] = cur_s.fetchone()["count"]

        accounts.append(acc)
    conn.close()
    return accounts


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a specific account."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    acc = dict(row)
    conn.close()
    return acc


def create_account(account_data: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new Instagram account entry."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    acc_id = account_data.get("id") or f"acc_{int(time.time())}"
    with conn:
        conn.execute("""
            INSERT INTO accounts (
                id, name, handle, niche, avatar_emoji, brand_color, status,
                daily_target, posting_schedule, ai_personality, content_style,
                default_theme, default_crop_mode, hashtag_strategy, caption_template,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            acc_id,
            account_data.get("name", "New Account"),
            account_data.get("handle", "@new_handle"),
            account_data.get("niche", "General"),
            account_data.get("avatar_emoji", "⚡"),
            account_data.get("brand_color", "#6366f1"),
            account_data.get("status", "active"),
            account_data.get("daily_target", 2),
            account_data.get("posting_schedule", "09:00, 18:00"),
            account_data.get("ai_personality", "Creative content strategist"),
            account_data.get("content_style", "High quality, engaging visuals"),
            account_data.get("default_theme", "hormozi_yellow"),
            account_data.get("default_crop_mode", "smart_face"),
            account_data.get("hashtag_strategy", "#shorts #reels #viral"),
            account_data.get("caption_template", "🔥 {hook}\n\n💡 {punchline}\n\n{hashtags}"),
            now, now
        ))
    conn.close()
    return get_account(acc_id)


def update_account(account_id: str, update_data: Dict[str, Any]) -> bool:
    """Updates account fields dynamically."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    allowed_fields = [
        "name", "handle", "niche", "avatar_emoji", "brand_color", "status",
        "daily_target", "posting_schedule", "ai_personality", "content_style",
        "default_theme", "default_crop_mode", "hashtag_strategy", "caption_template",
        "meta_access_token", "meta_account_id", "meta_connected"
    ]
    set_clauses = []
    values = []
    for key, val in update_data.items():
        if key in allowed_fields:
            set_clauses.append(f"{key} = ?")
            values.append(val)

    if not set_clauses:
        conn.close()
        return False

    set_clauses.append("updated_at = ?")
    values.append(now)
    values.append(account_id)

    query = f"UPDATE accounts SET {', '.join(set_clauses)} WHERE id = ?"
    with conn:
        cur = conn.execute(query, tuple(values))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def delete_account(account_id: str) -> bool:
    """Deletes an account and cascades deletions across queues & plans."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM content_sources WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM ai_content_plans WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM publishing_queue WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM rendered_shorts WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM jobs WHERE account_id = ?", (account_id,))
        cur = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        affected = cur.rowcount
    conn.close()
    return affected > 0


# --- Global Automation & Emergency Stop Controls ---

def get_system_setting(key: str, default: str = "") -> str:
    """Reads a system setting from SQLite."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_system_setting(key: str, value: str):
    """Sets a system setting in SQLite."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, now))
    conn.close()


def is_emergency_stopped() -> bool:
    """Returns True if emergency stop is engaged, halting all jobs & publishing."""
    return get_system_setting("emergency_stop", "0") == "1"


def set_emergency_stop(stopped: bool):
    """Engages or disengages global emergency stop."""
    set_system_setting("emergency_stop", "1" if stopped else "0")


# --- Content Sources CRUD ---

def create_content_source(
    account_id: str,
    source_type: str,
    source_url_or_path: str,
    title: str,
    attribution: str = "",
    verification_notes: str = ""
) -> Dict[str, Any]:
    """Registers a content source with verification notes and attribution."""
    init_db()
    conn = get_db_connection()
    source_id = f"src_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO content_sources (id, account_id, source_type, source_url_or_path, title, attribution, verification_notes, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', ?)
        """, (source_id, account_id, source_type, source_url_or_path, title, attribution, verification_notes, now))
    conn.close()
    return {"id": source_id, "account_id": account_id, "title": title}


def list_content_sources(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists content sources, optionally filtered by account."""
    init_db()
    conn = get_db_connection()
    query = "SELECT cs.*, a.name as account_name, a.brand_color FROM content_sources cs JOIN accounts a ON cs.account_id = a.id"
    params = []
    if account_id and account_id != "all":
        query += " WHERE cs.account_id = ?"
        params.append(account_id)
    query += " ORDER BY cs.created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_content_source(source_id: str) -> bool:
    """Removes a content source."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("DELETE FROM content_sources WHERE id = ?", (source_id,))
        affected = cur.rowcount
    conn.close()
    return affected > 0


# --- AI Content Director Plans CRUD ---

def save_ai_content_plan(plan_data: Dict[str, Any]) -> str:
    """Saves a structured 14-point AI Content Director plan."""
    init_db()
    conn = get_db_connection()
    plan_id = plan_data.get("id") or f"plan_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO ai_content_plans (
                id, account_id, job_id, topic, target_audience, video_idea, hook,
                script_selection, clip_start, clip_end, retention_strategy,
                editing_instructions, subtitle_style, caption, hashtags, cover_text,
                copyright_notes, quality_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan_id,
            plan_data.get("account_id", "acc_motivation"),
            plan_data.get("job_id"),
            plan_data.get("topic", "Trending Topic"),
            plan_data.get("target_audience", "General Audience"),
            plan_data.get("video_idea", ""),
            plan_data.get("hook", ""),
            plan_data.get("script_selection", ""),
            plan_data.get("clip_start", 0.0),
            plan_data.get("clip_end", 0.0),
            plan_data.get("retention_strategy", ""),
            plan_data.get("editing_instructions", ""),
            plan_data.get("subtitle_style", "hormozi_yellow"),
            plan_data.get("caption", ""),
            plan_data.get("hashtags", ""),
            plan_data.get("cover_text", ""),
            plan_data.get("copyright_notes", ""),
            plan_data.get("quality_score", 85),
            now
        ))
    conn.close()
    return plan_id


def list_ai_content_plans(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists generated AI Content Director plans."""
    init_db()
    conn = get_db_connection()
    query = "SELECT p.*, a.name as account_name, a.brand_color FROM ai_content_plans p JOIN accounts a ON p.account_id = a.id"
    params = []
    if account_id and account_id != "all":
        query += " WHERE p.account_id = ?"
        params.append(account_id)
    query += " ORDER BY p.created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# --- Job Management (Account-Aware) ---

def create_job(
    job_id: str,
    source_type: str,
    source_path: str,
    priority: int = 1,
    scheduled_at: Optional[str] = None,
    max_retries: int = 3,
    account_id: str = "acc_motivation"
) -> Dict[str, Any]:
    """Creates a new job assigned to a specific account."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO jobs (
                id, account_id, source_type, source_path, status, progress,
                current_step, priority, max_retries, scheduled_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'queued', 0, 'Job initialized in queue', ?, ?, ?, ?, ?)
        """, (job_id, account_id, source_type, source_path, priority, max_retries, scheduled_at, now, now))
    conn.close()
    return get_job(job_id)


def update_job_progress(job_id: str, status: str, progress: int, current_step: str, error: Optional[str] = None):
    """Updates job status, progress percentage, and current step description."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            UPDATE jobs
            SET status = ?, progress = ?, current_step = ?, error_message = ?, updated_at = ?
            WHERE id = ?
        """, (status, progress, current_step, error, now, job_id))
    conn.close()


def update_job_metadata(
    job_id: str,
    title: str,
    duration: float,
    resolution: str,
    transcript_path: Optional[str] = None,
    clips_path: Optional[str] = None
):
    """Updates job with media specifications and generated asset paths."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            UPDATE jobs
            SET title = ?, duration = ?, resolution = ?, transcript_json_path = ?, clips_json_path = ?, updated_at = ?
            WHERE id = ?
        """, (title, duration, resolution, transcript_path, clips_path, now, job_id))
    conn.close()


def mark_job_started(job_id: str):
    """Marks job started timestamp."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("UPDATE jobs SET started_at = ?, updated_at = ? WHERE id = ?", (now, now, job_id))
    conn.close()


def mark_job_completed(job_id: str):
    """Marks job completed timestamp and 100% progress."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("UPDATE jobs SET status = 'ready', progress = 100, completed_at = ?, updated_at = ? WHERE id = ?", (now, now, job_id))
    conn.close()


def mark_job_failed(job_id: str, error_message: str, can_retry: bool = True) -> bool:
    """Handles job failure with retry counter."""
    conn = get_db_connection()
    cur = conn.execute("SELECT retry_count, max_retries FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    now = datetime.now(timezone.utc).isoformat()
    will_retry = False

    if row:
        retry_count = (row["retry_count"] or 0) + 1
        max_retries = row["max_retries"] or 3
        if can_retry and retry_count <= max_retries:
            will_retry = True
            with conn:
                conn.execute("""
                    UPDATE jobs
                    SET status = 'queued', retry_count = ?, error_message = ?, current_step = ?, updated_at = ?
                    WHERE id = ?
                """, (retry_count, f"Retry #{retry_count} scheduled: {error_message}", f"Waiting for retry #{retry_count}...", now, job_id))
        else:
            with conn:
                conn.execute("""
                    UPDATE jobs
                    SET status = 'failed', retry_count = ?, error_message = ?, current_step = 'Failed permanently', updated_at = ?
                    WHERE id = ?
                """, (retry_count, error_message, now, job_id))
    conn.close()
    return will_retry


def cancel_job(job_id: str) -> bool:
    """Cancels a queued or processing job."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        cur = conn.execute("UPDATE jobs SET status = 'cancelled', current_step = 'Job cancelled by user', updated_at = ? WHERE id = ?", (now, job_id))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def retry_job(job_id: str) -> bool:
    """Resets a failed or cancelled job back to queued state."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        cur = conn.execute("""
            UPDATE jobs
            SET status = 'queued', progress = 0, current_step = 'Re-queued for processing', error_message = NULL, updated_at = ?
            WHERE id = ?
        """, (now, job_id))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def delete_job(job_id: str) -> bool:
    """Deletes job and associated records from SQLite."""
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM publishing_queue WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM rendered_shorts WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM ai_content_plans WHERE job_id = ?", (job_id,))
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def get_pending_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches queued jobs ready for processing, checking for global emergency stop and account active status."""
    if is_emergency_stopped():
        return []

    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("""
        SELECT j.* FROM jobs j
        JOIN accounts a ON j.account_id = a.id
        WHERE j.status = 'queued'
          AND a.status = 'active'
          AND (j.scheduled_at IS NULL OR j.scheduled_at <= ?)
        ORDER BY j.priority DESC, j.created_at ASC
        LIMIT ?
    """, (now, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_interrupted_jobs() -> List[Dict[str, Any]]:
    """Identifies jobs stuck in active processing states from a previous abnormal termination."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("""
        SELECT * FROM jobs
        WHERE status IN ('downloading', 'transcribing', 'analyzing')
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def recover_interrupted_jobs() -> int:
    """Automatically resets interrupted jobs, series, and episodes on startup."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    recovered_count = 0
    interrupted = get_interrupted_jobs()

    with conn:
        for job in interrupted:
            job_id = job["id"]
            retry_count = (job.get("retry_count") or 0) + 1
            max_retries = job.get("max_retries") or 3
            if retry_count <= max_retries:
                conn.execute("""
                    UPDATE jobs
                    SET status = 'queued', retry_count = ?,
                        current_step = 'Recovered after server restart. Resuming...',
                        updated_at = ?
                    WHERE id = ?
                """, (retry_count, now, job_id))
                recovered_count += 1
            else:
                conn.execute("""
                    UPDATE jobs
                    SET status = 'failed',
                        error_message = 'Interrupted during server shutdown and exceeded maximum retries',
                        current_step = 'Failed permanently after restart',
                        updated_at = ?
                    WHERE id = ?
                """, (now, job_id))

        # Also recover any series and series episodes interrupted while generating or rendering
        conn.execute("""
            UPDATE series
            SET status = 'ready', updated_at = ?
            WHERE status IN ('rendering', 'generating')
        """, (now,))
        conn.execute("""
            UPDATE series_episodes
            SET render_status = 'pending', updated_at = ?
            WHERE render_status = 'rendering'
        """, (now,))

    conn.close()
    return recovered_count


def save_rendered_short(
    job_id: str,
    clip_id: int,
    title: str,
    start_time: float,
    end_time: float,
    virality_score: int,
    crop_mode: str,
    theme: str,
    video_path: str,
    caption: Optional[str] = None,
    hashtags: Optional[str] = None,
    account_id: Optional[str] = None
) -> int:
    """Saves a rendered short to SQLite and creates an associated publishing draft."""
    init_db()
    conn = get_db_connection()

    # If account_id not passed, fetch from job
    if not account_id:
        cur_job = conn.execute("SELECT account_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        account_id = cur_job["account_id"] if cur_job else "acc_motivation"

    with conn:
        cur = conn.execute("""
            INSERT INTO rendered_shorts (
                account_id, job_id, clip_id, title, start_time, end_time,
                duration, virality_score, crop_mode, theme, video_path, caption, hashtags, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            account_id, job_id, clip_id, title, start_time, end_time,
            round(end_time - start_time, 2), virality_score, crop_mode, theme,
            video_path, caption or "", hashtags or ""
        ))
        render_id = cur.lastrowid

        safe_caption = caption or f"🔥 {title}\n\n👇 Save this for later!"
        safe_hashtags = hashtags or "#shorts #reels #viral"
        conn.execute("""
            INSERT INTO publishing_queue (
                account_id, render_id, job_id, platform, status, caption, hashtags
            ) VALUES (?, ?, ?, 'instagram', 'draft', ?, ?)
        """, (account_id, render_id, job_id, safe_caption, safe_hashtags))

    conn.close()
    return render_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full job record, account details, clips, and renders."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("""
        SELECT j.*, a.name as account_name, a.handle as account_handle, a.brand_color as account_color
        FROM jobs j
        LEFT JOIN accounts a ON j.account_id = a.id
        WHERE j.id = ?
    """, (job_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    job = dict(row)

    # Load viral clips from JSON if available
    clips = []
    if job.get("clips_json_path") and os.path.exists(job["clips_json_path"]):
        try:
            with open(job["clips_json_path"], "r", encoding="utf-8") as f:
                cdata = json.load(f)
                clips = cdata.get("clips", [])
        except Exception:
            pass
    job["clips"] = clips

    # Load rendered shorts
    cur_r = conn.execute("SELECT * FROM rendered_shorts WHERE job_id = ? ORDER BY id DESC", (job_id,))
    job["renders"] = [dict(r) for r in cur_r.fetchall()]

    conn.close()
    return job


def list_jobs(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists recent jobs with account attribution and renders count."""
    init_db()
    conn = get_db_connection()
    query = """
        SELECT j.*, a.name as account_name, a.handle as account_handle, a.brand_color as account_color, a.avatar_emoji as account_avatar
        FROM jobs j
        LEFT JOIN accounts a ON j.account_id = a.id
    """
    params = []
    if account_id and account_id != "all":
        query += " WHERE j.account_id = ?"
        params.append(account_id)

    query += " ORDER BY j.created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, tuple(params))
    jobs = []
    for row in cur.fetchall():
        j = dict(row)
        cur_c = conn.execute("SELECT COUNT(*) as count FROM rendered_shorts WHERE job_id = ?", (j["id"],))
        j["renders_count"] = cur_c.fetchone()["count"]
        jobs.append(j)
    conn.close()
    return jobs


def list_rendered_shorts(account_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists rendered shorts for the Video Library."""
    init_db()
    conn = get_db_connection()
    query = """
        SELECT rs.*, a.name as account_name, a.handle as account_handle, a.brand_color as account_color, a.avatar_emoji as account_avatar
        FROM rendered_shorts rs
        LEFT JOIN accounts a ON rs.account_id = a.id
    """
    clauses = []
    params = []
    if account_id and account_id != "all":
        clauses.append("rs.account_id = ?")
        params.append(account_id)
    if status and status != "all":
        clauses.append("rs.status = ?")
        params.append(status)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY rs.created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, tuple(params))
    renders = [dict(r) for r in cur.fetchall()]
    conn.close()
    return renders


def update_rendered_short_status(render_id: int, status: str) -> bool:
    """Updates rendered short approval status (approved, rejected, pending)."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("UPDATE rendered_shorts SET status = ? WHERE id = ?", (status, render_id))
        affected = cur.rowcount
    conn.close()
    return affected > 0


# --- Publishing Queue Functions ---

def add_publishing_draft(
    render_id: int,
    job_id: str,
    account_id: str = "acc_motivation",
    caption: str = "",
    hashtags: str = "#viral #shorts",
    platform: str = "instagram",
    scheduled_time: Optional[str] = None
) -> int:
    """Inserts a new draft item into publishing_queue."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO publishing_queue (
                account_id, render_id, job_id, platform, status, caption, hashtags, scheduled_time
            ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?)
            """,
            (account_id, render_id, job_id, platform, caption, hashtags, scheduled_time)
        )
        new_id = cur.lastrowid
    conn.close()
    return new_id


def list_publishing_queue(account_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists items in publishing queue with account details and video specifications."""
    init_db()
    conn = get_db_connection()
    query = """
        SELECT pq.*, rs.video_path, rs.duration, rs.virality_score, rs.title as short_title,
               j.title as source_title, a.name as account_name, a.handle as account_handle,
               a.brand_color as account_color, a.avatar_emoji as account_avatar
        FROM publishing_queue pq
        JOIN rendered_shorts rs ON pq.render_id = rs.id
        LEFT JOIN jobs j ON pq.job_id = j.id
        LEFT JOIN accounts a ON pq.account_id = a.id
    """
    clauses = []
    params = []
    if account_id and account_id != "all":
        clauses.append("pq.account_id = ?")
        params.append(account_id)
    if status and status != "all":
        clauses.append("pq.status = ?")
        params.append(status)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY pq.created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, tuple(params))
    items = [dict(r) for r in cur.fetchall()]
    conn.close()
    return items


def update_publishing_draft(
    publishing_id: int,
    caption: str,
    hashtags: str,
    scheduled_time: Optional[str] = None,
    status: Optional[str] = None
) -> bool:
    """Updates draft metadata and schedule."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    fields = ["caption = ?", "hashtags = ?", "updated_at = ?"]
    params = [caption, hashtags, now]
    if scheduled_time is not None:
        fields.append("scheduled_time = ?")
        params.append(scheduled_time)
    if status is not None:
        fields.append("status = ?")
        params.append(status)
    params.append(publishing_id)

    query = f"UPDATE publishing_queue SET {', '.join(fields)} WHERE id = ?"
    with conn:
        cur = conn.execute(query, tuple(params))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def approve_publishing_draft(publishing_id: int) -> bool:
    """Transitions a publishing draft from 'draft' to 'approved'."""
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        cur = conn.execute("UPDATE publishing_queue SET status = 'approved', updated_at = ? WHERE id = ?", (now, publishing_id))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def get_database_stats(account_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves operational aggregate counts for dashboard telemetry."""
    init_db()
    conn = get_db_connection()
    stats = {}
    with conn:
        # Emergency stop & global automation status
        stats["emergency_stop"] = is_emergency_stopped()
        stats["global_automation"] = get_system_setting("global_automation", "1") == "1"

        # Account counts
        cur_acc = conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active FROM accounts")
        acc_row = cur_acc.fetchone()
        stats["accounts_total"] = acc_row["total"]
        stats["accounts_active"] = acc_row["active"]

        # Job counts
        job_query = "SELECT status, COUNT(*) as cnt FROM jobs"
        job_params = []
        if account_id and account_id != "all":
            job_query += " WHERE account_id = ?"
            job_params.append(account_id)
        job_query += " GROUP BY status"
        for row in conn.execute(job_query, tuple(job_params)).fetchall():
            stats[f"jobs_{row['status']}"] = row["cnt"]

        # Total renders
        render_query = "SELECT COUNT(*) as cnt FROM rendered_shorts"
        render_params = []
        if account_id and account_id != "all":
            render_query += " WHERE account_id = ?"
            render_params.append(account_id)
        cur_r = conn.execute(render_query, tuple(render_params))
        stats["total_shorts_rendered"] = cur_r.fetchone()["cnt"]

        # Series counts
        series_query = "SELECT COUNT(*) as cnt FROM series"
        series_params = []
        if account_id and account_id != "all":
            series_query += " WHERE account_id = ?"
            series_params.append(account_id)
        cur_s = conn.execute(series_query, tuple(series_params))
        stats["total_series"] = cur_s.fetchone()["cnt"]

        ep_query = "SELECT COUNT(*) as cnt FROM series_episodes se JOIN series s ON se.series_id = s.id"
        ep_params = []
        if account_id and account_id != "all":
            ep_query += " WHERE s.account_id = ?"
            ep_params.append(account_id)
        cur_ep = conn.execute(ep_query, tuple(ep_params))
        stats["total_series_episodes"] = cur_ep.fetchone()["cnt"]

        # Metadata & Thumbnail counts
        meta_query = "SELECT COUNT(*) as cnt FROM video_metadata"
        meta_params = []
        if account_id and account_id != "all":
            meta_query += " WHERE account_id = ?"
            meta_params.append(account_id)
        stats["total_metadata_records"] = conn.execute(meta_query, tuple(meta_params)).fetchone()["cnt"]

        thumb_query = "SELECT COUNT(*) as cnt FROM thumbnail_assets"
        thumb_params = []
        if account_id and account_id != "all":
            thumb_query += " WHERE account_id = ?"
            thumb_params.append(account_id)
        stats["total_thumbnail_assets"] = conn.execute(thumb_query, tuple(thumb_params)).fetchone()["cnt"]

        # Publishing items by status
        pub_query = "SELECT status, COUNT(*) as cnt FROM publishing_queue"
        pub_params = []
        if account_id and account_id != "all":
            pub_query += " WHERE account_id = ?"
            pub_params.append(account_id)
        pub_query += " GROUP BY status"
        for row in conn.execute(pub_query, tuple(pub_params)).fetchall():
            stats[f"publishing_{row['status']}"] = row["cnt"]

        # Metadata & Thumbnail counts
        meta_query = "SELECT COUNT(*) as cnt FROM video_metadata"
        meta_params = []
        if account_id and account_id != "all":
            meta_query += " WHERE account_id = ?"
            meta_params.append(account_id)
        stats["total_metadata_records"] = conn.execute(meta_query, tuple(meta_params)).fetchone()["cnt"]

        thumb_query = "SELECT COUNT(*) as cnt FROM thumbnail_assets"
        thumb_params = []
        if account_id and account_id != "all":
            thumb_query += " WHERE account_id = ?"
            thumb_params.append(account_id)
        stats["total_thumbnail_assets"] = conn.execute(thumb_query, tuple(thumb_params)).fetchone()["cnt"]

    conn.close()
    return stats


def backup_database(backup_dir: str = "backups") -> str:
    """Creates an atomic online SQLite snapshot backup in backup_dir."""
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"jobs_backup_{timestamp}.db")
    safe_dest = Path(backup_file).resolve().as_posix()

    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute(f"VACUUM INTO '{safe_dest}'")
    conn.close()

    print(f"[+] Database backup created: {safe_dest}")
    return safe_dest


# --- Dubbed Renders CRUD ---

def create_dubbed_render(
    source_video_path: str,
    target_language: str,
    voice_id: str,
    voice_name: str,
    dubbed_video_path: str,
    render_id: Optional[int] = None,
    account_id: str = "acc_motivation",
    blend_mode: str = "ducked",
    speed: float = 1.0,
    pitch: int = 0,
    translated_transcript: Optional[str] = None
) -> int:
    """Inserts a completed dubbed render record and returns its ID."""
    init_db()
    conn = get_db_connection()
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO dubbed_renders (
                render_id, account_id, source_video_path, target_language,
                voice_id, voice_name, blend_mode, speed, pitch,
                dubbed_video_path, translated_transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                render_id, account_id, source_video_path, target_language,
                voice_id, voice_name, blend_mode, speed, pitch,
                dubbed_video_path, translated_transcript
            )
        )
        dubbed_id = cursor.lastrowid
    conn.close()
    return dubbed_id


def list_dubbed_renders(limit: int = 50, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists dubbed renders ordered by creation date descending."""
    init_db()
    conn = get_db_connection()
    query = "SELECT * FROM dubbed_renders"
    params = []
    if account_id and account_id != "all":
        query += " WHERE account_id = ?"
        params.append(account_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dubbed_render(dubbed_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single dubbed render by ID."""
    init_db()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM dubbed_renders WHERE id = ?", (dubbed_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Viral Hook A/B Variants CRUD ---

def save_hook_variant(
    job_id: str,
    clip_id: int,
    variant_letter: str,
    framework_type: str,
    hook_title: str,
    hook_overlay_text: str,
    predicted_score: int = 90,
    retention_lift: str = "+15%",
    account_id: str = "acc_motivation",
    rendered_video_path: Optional[str] = None
) -> int:
    """Saves a viral hook A/B variant."""
    init_db()
    conn = get_db_connection()
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO hook_ab_variants (
                job_id, clip_id, account_id, variant_letter,
                framework_type, hook_title, hook_overlay_text,
                predicted_score, retention_lift, rendered_video_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, clip_id, account_id, variant_letter,
                framework_type, hook_title, hook_overlay_text,
                predicted_score, retention_lift, rendered_video_path
            )
        )
        variant_id = cursor.lastrowid
    conn.close()
    return variant_id


def list_hook_variants(job_id: Optional[str] = None, clip_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lists hook variants for a job and clip."""
    init_db()
    conn = get_db_connection()
    query = "SELECT * FROM hook_ab_variants WHERE 1=1"
    params = []
    if job_id:
        query += " AND job_id = ?"
        params.append(job_id)
    if clip_id is not None:
        query += " AND clip_id = ?"
        params.append(clip_id)
    query += " ORDER BY variant_letter ASC"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_hook_variant_render(variant_id: int, rendered_video_path: str):
    """Updates the rendered video path for a hook variant."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute(
            "UPDATE hook_ab_variants SET rendered_video_path = ? WHERE id = ?",
            (rendered_video_path, variant_id)
        )
    conn.close()


# =====================================================================
# --- AI CLIFFHANGER SERIES ENGINE (SERIES & EPISODES CRUD) ---
# =====================================================================

def create_series(series_data: Dict[str, Any]) -> str:
    """
    Creates a new multi-episode series record and associated episodes in SQLite.
    Returns the series ID.
    """
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    series_id = series_data.get("id") or f"series_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Serialize JSON fields if needed
    story_arc = series_data.get("story_arc")
    story_arc_json = story_arc if isinstance(story_arc, str) else (json.dumps(story_arc, ensure_ascii=False) if story_arc else None)

    series_memory = series_data.get("series_memory")
    series_memory_json = series_memory if isinstance(series_memory, str) else (json.dumps(series_memory, ensure_ascii=False) if series_memory else None)

    episodes = series_data.get("episodes", [])
    ep_count = len(episodes) if episodes else int(series_data.get("episode_count", 3))

    with conn:
        conn.execute("""
            INSERT INTO series (
                id, account_id, job_id, title, description, main_topic, main_speakers,
                episode_count, status, quality_score, story_arc_json, series_memory_json,
                generation_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            series_id,
            series_data.get("account_id", "acc_motivation"),
            series_data.get("job_id"),
            series_data.get("title", "Untitled Series"),
            series_data.get("description", ""),
            series_data.get("main_topic", "General Narrative"),
            series_data.get("main_speakers", ""),
            ep_count,
            series_data.get("status", "ready"),
            int(series_data.get("quality_score", 85)),
            story_arc_json,
            series_memory_json,
            series_data.get("generation_mode", "auto"),
            now, now
        ))

        # Insert episodes if provided
        for ep_idx, ep in enumerate(episodes):
            ep_num = ep.get("episode_number") or (ep_idx + 1)
            is_final = 1 if (ep.get("is_final_episode") or ep_num == len(episodes)) else 0
            
            qb = ep.get("quality_breakdown")
            qb_json = qb if isinstance(qb, str) else (json.dumps(qb, ensure_ascii=False) if qb else None)

            wb = ep.get("word_boundaries")
            wb_json = wb if isinstance(wb, str) else (json.dumps(wb, ensure_ascii=False) if wb else None)

            start_t = float(ep.get("start_time", 0.0))
            end_t = float(ep.get("end_time", start_t + 30.0))
            dur = float(ep.get("duration") or round(end_t - start_t, 2))

            conn.execute("""
                INSERT INTO series_episodes (
                    series_id, episode_number, title, opening_hook, context_premise,
                    main_content, payoff_text, cliffhanger_text, cliffhanger_type,
                    cliffhanger_score, next_teaser, start_time, end_time, duration,
                    connection_prev, connection_next, is_final_episode, quality_score,
                    quality_breakdown_json, word_boundaries_json, rendered_video_path,
                    render_id, render_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                series_id,
                ep_num,
                ep.get("title", f"Episode {ep_num}"),
                ep.get("opening_hook", ""),
                ep.get("context_premise", ""),
                ep.get("main_content", ""),
                ep.get("payoff_text", ""),
                ep.get("cliffhanger_text", ""),
                ep.get("cliffhanger_type", "curiosity_gap"),
                int(ep.get("cliffhanger_score", 80)),
                ep.get("next_teaser", ""),
                start_t,
                end_t,
                dur,
                ep.get("connection_prev", ""),
                ep.get("connection_next", ""),
                is_final,
                int(ep.get("quality_score", 85)),
                qb_json,
                wb_json,
                ep.get("rendered_video_path"),
                ep.get("render_id"),
                ep.get("render_status", "pending"),
                now, now
            ))

    conn.close()
    return series_id


def get_series(series_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a complete series record, including account attributes,
    source job details, and all ordered episodes with timeline continuity data.
    """
    init_db()
    conn = get_db_connection()
    cur = conn.execute("""
        SELECT s.*,
               a.name as account_name, a.handle as account_handle, a.brand_color as account_color, a.avatar_emoji as account_avatar,
               j.title as source_video_title, j.duration as source_video_duration, j.source_path as source_video_path,
               j.source_type as source_video_type
        FROM series s
        LEFT JOIN accounts a ON s.account_id = a.id
        LEFT JOIN jobs j ON s.job_id = j.id
        WHERE s.id = ?
    """, (series_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    s = dict(row)

    # Safely parse JSON columns
    if s.get("story_arc_json"):
        try:
            s["story_arc"] = json.loads(s["story_arc_json"])
        except Exception:
            s["story_arc"] = s["story_arc_json"]
    else:
        s["story_arc"] = None

    if s.get("series_memory_json"):
        try:
            s["series_memory"] = json.loads(s["series_memory_json"])
        except Exception:
            s["series_memory"] = s["series_memory_json"]
    else:
        s["series_memory"] = None

    # Load episodes
    cur_ep = conn.execute("""
        SELECT se.*, rs.video_path as direct_render_path
        FROM series_episodes se
        LEFT JOIN rendered_shorts rs ON se.render_id = rs.id
        WHERE se.series_id = ?
        ORDER BY se.episode_number ASC
    """, (series_id,))
    
    episodes = []
    for ep_row in cur_ep.fetchall():
        ep = dict(ep_row)
        if ep.get("quality_breakdown_json"):
            try:
                ep["quality_breakdown"] = json.loads(ep["quality_breakdown_json"])
            except Exception:
                ep["quality_breakdown"] = ep["quality_breakdown_json"]
        else:
            ep["quality_breakdown"] = {}

        if ep.get("word_boundaries_json"):
            try:
                ep["word_boundaries"] = json.loads(ep["word_boundaries_json"])
            except Exception:
                ep["word_boundaries"] = []
        else:
            ep["word_boundaries"] = []

        # Fallback to direct_render_path if rendered_video_path wasn't stored
        if not ep.get("rendered_video_path") and ep.get("direct_render_path"):
            ep["rendered_video_path"] = ep["direct_render_path"]

        episodes.append(ep)

    s["episodes"] = episodes
    s["episode_count"] = len(episodes)
    conn.close()
    return s


def list_series(
    account_id: Optional[str] = None,
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lists all generated series with account badges, episode counts, and rendered statuses."""
    init_db()
    conn = get_db_connection()
    query = """
        SELECT s.*,
               a.name as account_name, a.handle as account_handle, a.brand_color as account_color, a.avatar_emoji as account_avatar,
               j.title as source_video_title, j.duration as source_video_duration,
               COUNT(se.id) as actual_episodes_count,
               SUM(CASE WHEN se.render_status = 'ready' THEN 1 ELSE 0 END) as rendered_episodes_count
        FROM series s
        LEFT JOIN accounts a ON s.account_id = a.id
        LEFT JOIN jobs j ON s.job_id = j.id
        LEFT JOIN series_episodes se ON s.id = se.series_id
    """
    clauses = []
    params = []

    if account_id and account_id != "all":
        clauses.append("s.account_id = ?")
        params.append(account_id)
    if job_id:
        clauses.append("s.job_id = ?")
        params.append(job_id)
    if status and status != "all":
        clauses.append("s.status = ?")
        params.append(status)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " GROUP BY s.id ORDER BY s.created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, tuple(params))
    series_list = []
    for row in cur.fetchall():
        s = dict(row)
        if s.get("story_arc_json"):
            try:
                s["story_arc"] = json.loads(s["story_arc_json"])
            except Exception:
                s["story_arc"] = None
        series_list.append(s)

    conn.close()
    return series_list


def update_series(series_id: str, update_data: Dict[str, Any]) -> bool:
    """Updates top-level series metadata."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    allowed_fields = [
        "title", "description", "main_topic", "main_speakers", "episode_count",
        "status", "quality_score", "generation_mode"
    ]
    set_clauses = []
    values = []

    for k, v in update_data.items():
        if k in allowed_fields:
            set_clauses.append(f"{k} = ?")
            values.append(v)
        elif k == "story_arc":
            set_clauses.append("story_arc_json = ?")
            values.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
        elif k == "series_memory":
            set_clauses.append("series_memory_json = ?")
            values.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))

    if not set_clauses:
        conn.close()
        return False

    set_clauses.append("updated_at = ?")
    values.append(now)
    values.append(series_id)

    query = f"UPDATE series SET {', '.join(set_clauses)} WHERE id = ?"
    with conn:
        cur = conn.execute(query, tuple(values))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def delete_series(series_id: str) -> bool:
    """Deletes series and cascades removal to all associated episodes."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM series_episodes WHERE series_id = ?", (series_id,))
        cur = conn.execute("DELETE FROM series WHERE id = ?", (series_id,))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def create_series_episode(episode_data: Dict[str, Any]) -> int:
    """Creates a new episode within an existing series."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()

    qb = episode_data.get("quality_breakdown")
    qb_json = qb if isinstance(qb, str) else (json.dumps(qb, ensure_ascii=False) if qb else None)

    wb = episode_data.get("word_boundaries")
    wb_json = wb if isinstance(wb, str) else (json.dumps(wb, ensure_ascii=False) if wb else None)

    start_t = float(episode_data.get("start_time", 0.0))
    end_t = float(episode_data.get("end_time", start_t + 30.0))
    dur = float(episode_data.get("duration") or round(end_t - start_t, 2))

    with conn:
        cur = conn.execute("""
            INSERT INTO series_episodes (
                series_id, episode_number, title, opening_hook, context_premise,
                main_content, payoff_text, cliffhanger_text, cliffhanger_type,
                cliffhanger_score, next_teaser, start_time, end_time, duration,
                connection_prev, connection_next, is_final_episode, quality_score,
                quality_breakdown_json, word_boundaries_json, rendered_video_path,
                render_id, render_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_data["series_id"],
            int(episode_data.get("episode_number", 1)),
            episode_data.get("title", "New Episode"),
            episode_data.get("opening_hook", ""),
            episode_data.get("context_premise", ""),
            episode_data.get("main_content", ""),
            episode_data.get("payoff_text", ""),
            episode_data.get("cliffhanger_text", ""),
            episode_data.get("cliffhanger_type", "curiosity_gap"),
            int(episode_data.get("cliffhanger_score", 80)),
            episode_data.get("next_teaser", ""),
            start_t,
            end_t,
            dur,
            episode_data.get("connection_prev", ""),
            episode_data.get("connection_next", ""),
            int(episode_data.get("is_final_episode", 0)),
            int(episode_data.get("quality_score", 85)),
            qb_json,
            wb_json,
            episode_data.get("rendered_video_path"),
            episode_data.get("render_id"),
            episode_data.get("render_status", "pending"),
            now, now
        ))
        ep_id = cur.lastrowid

        # Update episode_count on parent series
        conn.execute("""
            UPDATE series
            SET episode_count = (SELECT COUNT(*) FROM series_episodes WHERE series_id = ?),
                updated_at = ?
            WHERE id = ?
        """, (episode_data["series_id"], now, episode_data["series_id"]))

    conn.close()
    return ep_id


def get_series_episode(episode_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves full details for a single episode."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("""
        SELECT se.*, s.title as series_title, s.account_id, s.job_id
        FROM series_episodes se
        JOIN series s ON se.series_id = s.id
        WHERE se.id = ?
    """, (episode_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    ep = dict(row)
    if ep.get("quality_breakdown_json"):
        try:
            ep["quality_breakdown"] = json.loads(ep["quality_breakdown_json"])
        except Exception:
            ep["quality_breakdown"] = {}
    if ep.get("word_boundaries_json"):
        try:
            ep["word_boundaries"] = json.loads(ep["word_boundaries_json"])
        except Exception:
            ep["word_boundaries"] = []
    conn.close()
    return ep


def list_series_episodes(series_id: str) -> List[Dict[str, Any]]:
    """Lists all episodes in a series ordered by sequence."""
    init_db()
    conn = get_db_connection()
    cur = conn.execute("""
        SELECT * FROM series_episodes
        WHERE series_id = ?
        ORDER BY episode_number ASC
    """, (series_id,))
    episodes = []
    for row in cur.fetchall():
        ep = dict(row)
        if ep.get("quality_breakdown_json"):
            try:
                ep["quality_breakdown"] = json.loads(ep["quality_breakdown_json"])
            except Exception:
                ep["quality_breakdown"] = {}
        if ep.get("word_boundaries_json"):
            try:
                ep["word_boundaries"] = json.loads(ep["word_boundaries_json"])
            except Exception:
                ep["word_boundaries"] = []
        episodes.append(ep)
    conn.close()
    return episodes


def update_series_episode(episode_id: int, update_data: Dict[str, Any]) -> bool:
    """Updates specific fields of an episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    allowed_fields = [
        "episode_number", "title", "opening_hook", "context_premise", "main_content",
        "payoff_text", "cliffhanger_text", "cliffhanger_type", "cliffhanger_score",
        "next_teaser", "start_time", "end_time", "duration", "connection_prev",
        "connection_next", "is_final_episode", "quality_score", "rendered_video_path",
        "render_id", "render_status"
    ]
    set_clauses = []
    values = []

    for k, v in update_data.items():
        if k in allowed_fields:
            set_clauses.append(f"{k} = ?")
            values.append(v)
        elif k == "quality_breakdown":
            set_clauses.append("quality_breakdown_json = ?")
            values.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
        elif k == "word_boundaries":
            set_clauses.append("word_boundaries_json = ?")
            values.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))

    # Recalculate duration if timestamps provided
    if "start_time" in update_data and "end_time" in update_data and "duration" not in update_data:
        set_clauses.append("duration = ?")
        values.append(round(float(update_data["end_time"]) - float(update_data["start_time"]), 2))

    if not set_clauses:
        conn.close()
        return False

    set_clauses.append("updated_at = ?")
    values.append(now)
    values.append(episode_id)

    query = f"UPDATE series_episodes SET {', '.join(set_clauses)} WHERE id = ?"
    with conn:
        cur = conn.execute(query, tuple(values))
        affected = cur.rowcount
    conn.close()
    return affected > 0


def delete_series_episode(episode_id: int) -> bool:
    """
    Deletes an episode, renumbers subsequent episodes in that series to maintain a clean sequence,
    ensures the new last episode is flagged as final, and updates the series episode count.
    """
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()

    with conn:
        cur_find = conn.execute("SELECT series_id FROM series_episodes WHERE id = ?", (episode_id,))
        row = cur_find.fetchone()
        if not row:
            conn.close()
            return False
        series_id = row["series_id"]

        # Delete episode
        conn.execute("DELETE FROM series_episodes WHERE id = ?", (episode_id,))

        # Renumber remaining episodes
        remaining = conn.execute("""
            SELECT id FROM series_episodes
            WHERE series_id = ?
            ORDER BY episode_number ASC, id ASC
        """, (series_id,)).fetchall()

        total = len(remaining)
        for idx, r in enumerate(remaining):
            is_final = 1 if (idx == total - 1) else 0
            conn.execute("""
                UPDATE series_episodes
                SET episode_number = ?, is_final_episode = ?, updated_at = ?
                WHERE id = ?
            """, (idx + 1, is_final, now, r["id"]))

        # Update parent series count
        conn.execute("""
            UPDATE series
            SET episode_count = ?, updated_at = ?
            WHERE id = ?
        """, (total, now, series_id))

    conn.close()
    return True


# =====================================================================
# --- AI METADATA & SEO GENERATOR PERSISTENCE ---
# =====================================================================

def save_video_metadata(
    target_type: str,
    target_id: Any,
    title: str,
    niche: str = "Motivation",
    youtube_data: Optional[Dict[str, Any]] = None,
    instagram_data: Optional[Dict[str, Any]] = None,
    tiktok_data: Optional[Dict[str, Any]] = None,
    title_variations: Optional[Dict[str, Any]] = None,
    quality_score: int = 85,
    quality_breakdown: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation",
    status: str = "draft"
) -> int:
    """Saves or updates full platform metadata for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        # Check if record already exists
        cur = conn.execute(
            "SELECT id FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        existing = cur.fetchone()
        yt_json = json.dumps(youtube_data or {})
        ig_json = json.dumps(instagram_data or {})
        tt_json = json.dumps(tiktok_data or {})
        tv_json = json.dumps(title_variations or {})
        qb_json = json.dumps(quality_breakdown or {})

        if existing:
            meta_id = existing["id"]
            conn.execute("""
                UPDATE video_metadata
                SET title = ?, niche = ?, youtube_json = ?, instagram_json = ?,
                    tiktok_json = ?, title_variations_json = ?, quality_score = ?,
                    quality_breakdown_json = ?, job_id = COALESCE(?, job_id),
                    account_id = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (title, niche, yt_json, ig_json, tt_json, tv_json, quality_score,
                  qb_json, job_id, account_id, status, now, meta_id))
        else:
            cur_ins = conn.execute("""
                INSERT INTO video_metadata (
                    job_id, target_type, target_id, account_id, title, niche,
                    youtube_json, instagram_json, tiktok_json, title_variations_json,
                    quality_score, quality_breakdown_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, target_type, t_id_str, account_id, title, niche,
                  yt_json, ig_json, tt_json, tv_json, quality_score, qb_json, status, now, now))
            meta_id = cur_ins.lastrowid

    conn.close()
    return meta_id


def get_video_metadata(target_type: str, target_id: Any) -> Optional[Dict[str, Any]]:
    """Retrieves full platform metadata for a specific target."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute(
            "SELECT * FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
        if res.get(f):
            try:
                res[f.replace("_json", "")] = json.loads(res[f])
            except Exception:
                pass
    return res


def list_video_metadata(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists video metadata records."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM video_metadata"
        params = []
        if account_id and account_id != "all":
            q += " WHERE account_id = ?"
            params.append(account_id)
        q += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
            if d.get(f):
                try:
                    d[f.replace("_json", "")] = json.loads(d[f])
                except Exception:
                    pass
        res.append(d)
    return res


def update_video_metadata_field(
    target_type: str,
    target_id: Any,
    platform: str,
    field_name: str,
    new_value: Any
) -> bool:
    """Updates a specific field in YouTube, Instagram, or TikTok metadata."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    now = datetime.now(timezone.utc).isoformat()
    json_col = f"{platform}_json"
    with conn:
        cur = conn.execute(
            f"SELECT id, {json_col} FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False

        meta_id = row["id"]
        curr_data = {}
        if row[json_col]:
            try:
                curr_data = json.loads(row[json_col])
            except Exception:
                pass

        curr_data[field_name] = new_value
        conn.execute(
            f"UPDATE video_metadata SET {json_col} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(curr_data), now, meta_id)
        )
    conn.close()
    return True


def delete_video_metadata(target_type: str, target_id: Any) -> bool:
    """Deletes metadata record."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute(
            "DELETE FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
    conn.close()
    return True


# =====================================================================
# --- AI THUMBNAIL & COVER ASSET PERSISTENCE ---
# =====================================================================

def save_thumbnail_asset(
    target_type: str,
    target_id: Any,
    image_path: str,
    headline: str,
    variation_type: str = "emotional",
    aspect_ratio: str = "9:16",
    style_mode: str = "auto",
    source_timestamp: float = 1.0,
    is_selected: int = 0,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation"
) -> int:
    """Saves a thumbnail asset variation for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        if is_selected:
            # Unselect other thumbnails for this target and aspect ratio
            conn.execute("""
                UPDATE thumbnail_assets
                SET is_selected = 0
                WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
            """, (target_type, t_id_str, aspect_ratio))

        cur = conn.execute("""
            INSERT INTO thumbnail_assets (
                job_id, target_type, target_id, account_id, aspect_ratio,
                platform, style_mode, variation_type, headline, image_path,
                source_timestamp, is_selected, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, target_type, t_id_str, account_id, aspect_ratio,
              "universal", style_mode, variation_type, headline, image_path,
              source_timestamp, is_selected, now))
        asset_id = cur.lastrowid
    conn.close()
    return asset_id


def get_thumbnail_asset(asset_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single thumbnail asset by ID."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT * FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_thumbnail_assets(
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    account_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lists thumbnail assets with optional filtering."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM thumbnail_assets WHERE 1=1"
        params = []
        if target_type:
            q += " AND target_type = ?"
            params.append(target_type)
        if target_id is not None:
            q += " AND target_id = ?"
            params.append(str(target_id))
        if account_id and account_id != "all":
            q += " AND account_id = ?"
            params.append(account_id)
        q += " ORDER BY is_selected DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def select_thumbnail_asset(asset_id: int, target_type: str, target_id: Any) -> bool:
    """Designates a specific thumbnail variation as the approved active cover."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    with conn:
        # Get aspect ratio of the target asset
        cur = conn.execute("SELECT aspect_ratio FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        ar = row["aspect_ratio"]
        conn.execute("""
            UPDATE thumbnail_assets
            SET is_selected = 0
            WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
        """, (target_type, t_id_str, ar))
        conn.execute("UPDATE thumbnail_assets SET is_selected = 1 WHERE id = ?", (asset_id,))
    conn.close()
    return True


def delete_thumbnail_asset(asset_id: int) -> bool:
    """Deletes a thumbnail asset and removes its local file if present."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT image_path FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if row and row["image_path"] and os.path.exists(row["image_path"]):
            try:
                os.remove(row["image_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM thumbnail_assets WHERE id = ?", (asset_id,))
    conn.close()
    return True



def reorder_series_episodes(series_id: str, episode_ids_order: List[int]) -> bool:
    """
    Reorders episodes according to the given list of IDs,
    marking the last element as final.
    """
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()

    with conn:
        total = len(episode_ids_order)
        for idx, ep_id in enumerate(episode_ids_order):
            is_final = 1 if (idx == total - 1) else 0
            conn.execute("""
                UPDATE series_episodes
                SET episode_number = ?, is_final_episode = ?, updated_at = ?
                WHERE id = ? AND series_id = ?
            """, (idx + 1, is_final, now, ep_id, series_id))

        conn.execute("""
            UPDATE series
            SET episode_count = ?, updated_at = ?
            WHERE id = ?
        """, (total, now, series_id))

    conn.close()
    return True


# =====================================================================
# --- AI METADATA & SEO GENERATOR PERSISTENCE ---
# =====================================================================

def save_video_metadata(
    target_type: str,
    target_id: Any,
    title: str,
    niche: str = "Motivation",
    youtube_data: Optional[Dict[str, Any]] = None,
    instagram_data: Optional[Dict[str, Any]] = None,
    tiktok_data: Optional[Dict[str, Any]] = None,
    title_variations: Optional[Dict[str, Any]] = None,
    quality_score: int = 85,
    quality_breakdown: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation",
    status: str = "draft"
) -> int:
    """Saves or updates full platform metadata for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        # Check if record already exists
        cur = conn.execute(
            "SELECT id FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        existing = cur.fetchone()
        yt_json = json.dumps(youtube_data or {})
        ig_json = json.dumps(instagram_data or {})
        tt_json = json.dumps(tiktok_data or {})
        tv_json = json.dumps(title_variations or {})
        qb_json = json.dumps(quality_breakdown or {})

        if existing:
            meta_id = existing["id"]
            conn.execute("""
                UPDATE video_metadata
                SET title = ?, niche = ?, youtube_json = ?, instagram_json = ?,
                    tiktok_json = ?, title_variations_json = ?, quality_score = ?,
                    quality_breakdown_json = ?, job_id = COALESCE(?, job_id),
                    account_id = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (title, niche, yt_json, ig_json, tt_json, tv_json, quality_score,
                  qb_json, job_id, account_id, status, now, meta_id))
        else:
            cur_ins = conn.execute("""
                INSERT INTO video_metadata (
                    job_id, target_type, target_id, account_id, title, niche,
                    youtube_json, instagram_json, tiktok_json, title_variations_json,
                    quality_score, quality_breakdown_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, target_type, t_id_str, account_id, title, niche,
                  yt_json, ig_json, tt_json, tv_json, quality_score, qb_json, status, now, now))
            meta_id = cur_ins.lastrowid

    conn.close()
    return meta_id


def get_video_metadata(target_type: str, target_id: Any) -> Optional[Dict[str, Any]]:
    """Retrieves full platform metadata for a specific target."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute(
            "SELECT * FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
        if res.get(f):
            try:
                res[f.replace("_json", "")] = json.loads(res[f])
            except Exception:
                pass
    return res


def list_video_metadata(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists video metadata records."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM video_metadata"
        params = []
        if account_id and account_id != "all":
            q += " WHERE account_id = ?"
            params.append(account_id)
        q += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
            if d.get(f):
                try:
                    d[f.replace("_json", "")] = json.loads(d[f])
                except Exception:
                    pass
        res.append(d)
    return res


def update_video_metadata_field(
    target_type: str,
    target_id: Any,
    platform: str,
    field_name: str,
    new_value: Any
) -> bool:
    """Updates a specific field in YouTube, Instagram, or TikTok metadata."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    now = datetime.now(timezone.utc).isoformat()
    json_col = f"{platform}_json"
    with conn:
        cur = conn.execute(
            f"SELECT id, {json_col} FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False

        meta_id = row["id"]
        curr_data = {}
        if row[json_col]:
            try:
                curr_data = json.loads(row[json_col])
            except Exception:
                pass

        curr_data[field_name] = new_value
        conn.execute(
            f"UPDATE video_metadata SET {json_col} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(curr_data), now, meta_id)
        )
    conn.close()
    return True


def delete_video_metadata(target_type: str, target_id: Any) -> bool:
    """Deletes metadata record."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute(
            "DELETE FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
    conn.close()
    return True


# =====================================================================
# --- AI THUMBNAIL & COVER ASSET PERSISTENCE ---
# =====================================================================

def save_thumbnail_asset(
    target_type: str,
    target_id: Any,
    image_path: str,
    headline: str,
    variation_type: str = "emotional",
    aspect_ratio: str = "9:16",
    style_mode: str = "auto",
    source_timestamp: float = 1.0,
    is_selected: int = 0,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation"
) -> int:
    """Saves a thumbnail asset variation for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        if is_selected:
            # Unselect other thumbnails for this target and aspect ratio
            conn.execute("""
                UPDATE thumbnail_assets
                SET is_selected = 0
                WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
            """, (target_type, t_id_str, aspect_ratio))

        cur = conn.execute("""
            INSERT INTO thumbnail_assets (
                job_id, target_type, target_id, account_id, aspect_ratio,
                platform, style_mode, variation_type, headline, image_path,
                source_timestamp, is_selected, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, target_type, t_id_str, account_id, aspect_ratio,
              "universal", style_mode, variation_type, headline, image_path,
              source_timestamp, is_selected, now))
        asset_id = cur.lastrowid
    conn.close()
    return asset_id


def get_thumbnail_asset(asset_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single thumbnail asset by ID."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT * FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_thumbnail_assets(
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    account_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lists thumbnail assets with optional filtering."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM thumbnail_assets WHERE 1=1"
        params = []
        if target_type:
            q += " AND target_type = ?"
            params.append(target_type)
        if target_id is not None:
            q += " AND target_id = ?"
            params.append(str(target_id))
        if account_id and account_id != "all":
            q += " AND account_id = ?"
            params.append(account_id)
        q += " ORDER BY is_selected DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def select_thumbnail_asset(asset_id: int, target_type: str, target_id: Any) -> bool:
    """Designates a specific thumbnail variation as the approved active cover."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    with conn:
        # Get aspect ratio of the target asset
        cur = conn.execute("SELECT aspect_ratio FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        ar = row["aspect_ratio"]
        conn.execute("""
            UPDATE thumbnail_assets
            SET is_selected = 0
            WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
        """, (target_type, t_id_str, ar))
        conn.execute("UPDATE thumbnail_assets SET is_selected = 1 WHERE id = ?", (asset_id,))
    conn.close()
    return True


def delete_thumbnail_asset(asset_id: int) -> bool:
    """Deletes a thumbnail asset and removes its local file if present."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT image_path FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if row and row["image_path"] and os.path.exists(row["image_path"]):
            try:
                os.remove(row["image_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM thumbnail_assets WHERE id = ?", (asset_id,))
    conn.close()
    return True



def merge_series_episodes(series_id: str, ep1_id: int, ep2_id: int) -> Optional[int]:
    """
    Merges ep2 into ep1:
    - Combines start and end times.
    - Joins content and preserves ep2's cliffhanger.
    - Removes ep2 and renumbers remaining episodes.
    """
    init_db()
    conn = get_db_connection()
    ep1 = get_series_episode(ep1_id)
    ep2 = get_series_episode(ep2_id)

    if not ep1 or not ep2 or ep1["series_id"] != series_id or ep2["series_id"] != series_id:
        conn.close()
        return None

    # Determine chronological order
    if ep1["start_time"] > ep2["start_time"]:
        ep1, ep2 = ep2, ep1

    new_start = min(ep1["start_time"], ep2["start_time"])
    new_end = max(ep1["end_time"], ep2["end_time"])
    new_dur = round(new_end - new_start, 2)
    merged_title = f"{ep1['title']} & {ep2['title']}".replace("Episode ", "Ep ")
    merged_content = f"{ep1.get('main_content', '')} {ep2.get('main_content', '')}".strip()

    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            UPDATE series_episodes
            SET title = ?, start_time = ?, end_time = ?, duration = ?,
                main_content = ?, cliffhanger_text = ?, cliffhanger_type = ?,
                cliffhanger_score = ?, next_teaser = ?, is_final_episode = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            merged_title, new_start, new_end, new_dur, merged_content,
            ep2.get("cliffhanger_text", ep1.get("cliffhanger_text", "")),
            ep2.get("cliffhanger_type", ep1.get("cliffhanger_type", "curiosity_gap")),
            ep2.get("cliffhanger_score", ep1.get("cliffhanger_score", 80)),
            ep2.get("next_teaser", ep1.get("next_teaser", "")),
            ep2.get("is_final_episode", 0),
            now, ep1["id"]
        ))
        conn.execute("DELETE FROM series_episodes WHERE id = ?", (ep2["id"],))

        # Renumber remaining
        remaining = conn.execute("""
            SELECT id FROM series_episodes
            WHERE series_id = ?
            ORDER BY episode_number ASC, id ASC
        """, (series_id,)).fetchall()

        total = len(remaining)
        for idx, r in enumerate(remaining):
            is_final = 1 if (idx == total - 1) else 0
            conn.execute("""
                UPDATE series_episodes
                SET episode_number = ?, is_final_episode = ?, updated_at = ?
                WHERE id = ?
            """, (idx + 1, is_final, now, r["id"]))

        conn.execute("""
            UPDATE series
            SET episode_count = ?, updated_at = ?
            WHERE id = ?
        """, (total, now, series_id))

    conn.close()
    return ep1["id"]


def split_series_episode(
    series_id: str,
    episode_id: int,
    split_time: float,
    ep1_cliffhanger: str = "",
    ep2_hook: str = ""
) -> Optional[Tuple[int, int]]:
    """
    Splits an episode into two at split_time.
    Creates a new following episode and adjusts boundaries and cliffhangers.
    """
    init_db()
    conn = get_db_connection()
    ep = get_series_episode(episode_id)
    if not ep or ep["series_id"] != series_id:
        conn.close()
        return None

    if not (ep["start_time"] < split_time < ep["end_time"]):
        conn.close()
        return None

    now = datetime.now(timezone.utc).isoformat()
    cliff1 = ep1_cliffhanger or "Wait... what happens next?"
    hook2 = ep2_hook or f"Picking up right where we left off in Part {ep['episode_number']}..."

    part1_dur = round(split_time - ep["start_time"], 2)
    part2_dur = round(ep["end_time"] - split_time, 2)

    with conn:
        # Update part 1
        conn.execute("""
            UPDATE series_episodes
            SET end_time = ?, duration = ?, cliffhanger_text = ?, is_final_episode = 0, updated_at = ?
            WHERE id = ?
        """, (split_time, part1_dur, cliff1, now, episode_id))

        # Insert part 2
        cur = conn.execute("""
            INSERT INTO series_episodes (
                series_id, episode_number, title, opening_hook, context_premise,
                main_content, payoff_text, cliffhanger_text, cliffhanger_type,
                cliffhanger_score, next_teaser, start_time, end_time, duration,
                connection_prev, connection_next, is_final_episode, quality_score,
                render_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            series_id,
            ep["episode_number"] + 1,
            f"{ep['title']} (Part 2)",
            hook2,
            f"Continuation of {ep['title']}",
            ep.get("main_content", ""),
            ep.get("payoff_text", ""),
            ep.get("cliffhanger_text", ""),
            ep.get("cliffhanger_type", "curiosity_gap"),
            ep.get("cliffhanger_score", 80),
            ep.get("next_teaser", ""),
            split_time,
            ep["end_time"],
            part2_dur,
            f"Follows directly from {ep['title']}",
            ep.get("connection_next", ""),
            ep.get("is_final_episode", 0),
            ep.get("quality_score", 85),
            now, now
        ))
        ep2_id = cur.lastrowid

        # Renumber all episodes
        all_eps = conn.execute("""
            SELECT id FROM series_episodes
            WHERE series_id = ?
            ORDER BY start_time ASC, id ASC
        """, (series_id,)).fetchall()

        total = len(all_eps)
        for idx, r in enumerate(all_eps):
            is_final = 1 if (idx == total - 1) else 0
            conn.execute("""
                UPDATE series_episodes
                SET episode_number = ?, is_final_episode = ?, updated_at = ?
                WHERE id = ?
            """, (idx + 1, is_final, now, r["id"]))

        conn.execute("""
            UPDATE series
            SET episode_count = ?, updated_at = ?
            WHERE id = ?
        """, (total, now, series_id))

    conn.close()
    return (episode_id, ep2_id)


def update_episode_render_result(
    episode_id: int,
    render_status: str,
    rendered_video_path: Optional[str] = None,
    render_id: Optional[int] = None
) -> bool:
    """
    Updates the render state of an episode and automatically transitions
    the parent series to 'completed' if all episodes are rendered.
    """
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            UPDATE series_episodes
            SET render_status = ?, rendered_video_path = COALESCE(?, rendered_video_path),
                render_id = COALESCE(?, render_id), updated_at = ?
            WHERE id = ?
        """, (render_status, rendered_video_path, render_id, now, episode_id))

        # Check parent series status
        cur_find = conn.execute("SELECT series_id FROM series_episodes WHERE id = ?", (episode_id,))
        row = cur_find.fetchone()
        if row:
            sid = row["series_id"]
            cur_check = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN render_status = 'ready' THEN 1 ELSE 0 END) as ready_count,
                       SUM(CASE WHEN render_status = 'rendering' THEN 1 ELSE 0 END) as rendering_count
                FROM series_episodes
                WHERE series_id = ?
            """, (sid,))
            stat = cur_check.fetchone()
            if stat["total"] > 0 and stat["ready_count"] == stat["total"]:
                conn.execute("UPDATE series SET status = 'completed', updated_at = ? WHERE id = ?", (now, sid))
            elif stat["rendering_count"] > 0:
                conn.execute("UPDATE series SET status = 'rendering', updated_at = ? WHERE id = ?", (now, sid))

    conn.close()
    return True


# =====================================================================
# --- AI METADATA & SEO GENERATOR PERSISTENCE ---
# =====================================================================


# =====================================================================
# --- AI METADATA & SEO GENERATOR PERSISTENCE ---
# =====================================================================

def save_video_metadata(
    target_type: str,
    target_id: Any,
    title: str,
    niche: str = "Motivation",
    youtube_data: Optional[Dict[str, Any]] = None,
    instagram_data: Optional[Dict[str, Any]] = None,
    tiktok_data: Optional[Dict[str, Any]] = None,
    title_variations: Optional[Dict[str, Any]] = None,
    quality_score: int = 85,
    quality_breakdown: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation",
    status: str = "draft"
) -> int:
    """Saves or updates full platform metadata for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        cur = conn.execute(
            "SELECT id FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        existing = cur.fetchone()
        yt_json = json.dumps(youtube_data or {})
        ig_json = json.dumps(instagram_data or {})
        tt_json = json.dumps(tiktok_data or {})
        tv_json = json.dumps(title_variations or {})
        qb_json = json.dumps(quality_breakdown or {})

        if existing:
            meta_id = existing["id"]
            conn.execute("""
                UPDATE video_metadata
                SET title = ?, niche = ?, youtube_json = ?, instagram_json = ?,
                    tiktok_json = ?, title_variations_json = ?, quality_score = ?,
                    quality_breakdown_json = ?, job_id = COALESCE(?, job_id),
                    account_id = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (title, niche, yt_json, ig_json, tt_json, tv_json, quality_score,
                  qb_json, job_id, account_id, status, now, meta_id))
        else:
            cur_ins = conn.execute("""
                INSERT INTO video_metadata (
                    job_id, target_type, target_id, account_id, title, niche,
                    youtube_json, instagram_json, tiktok_json, title_variations_json,
                    quality_score, quality_breakdown_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, target_type, t_id_str, account_id, title, niche,
                  yt_json, ig_json, tt_json, tv_json, quality_score, qb_json, status, now, now))
            meta_id = cur_ins.lastrowid

    conn.close()
    return meta_id


def get_video_metadata(target_type: str, target_id: Any) -> Optional[Dict[str, Any]]:
    """Retrieves full platform metadata for a specific target."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute(
            "SELECT * FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
        if res.get(f):
            try:
                res[f.replace("_json", "")] = json.loads(res[f])
            except Exception:
                pass
    return res


def list_video_metadata(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists video metadata records."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM video_metadata"
        params = []
        if account_id and account_id != "all":
            q += " WHERE account_id = ?"
            params.append(account_id)
        q += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
            if d.get(f):
                try:
                    d[f.replace("_json", "")] = json.loads(d[f])
                except Exception:
                    pass
        res.append(d)
    return res


def update_video_metadata_field(
    target_type: str,
    target_id: Any,
    platform: str,
    field_name: str,
    new_value: Any
) -> bool:
    """Updates a specific field in YouTube, Instagram, or TikTok metadata."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    now = datetime.now(timezone.utc).isoformat()
    json_col = f"{platform}_json"
    with conn:
        cur = conn.execute(
            f"SELECT id, {json_col} FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False

        meta_id = row["id"]
        curr_data = {}
        if row[json_col]:
            try:
                curr_data = json.loads(row[json_col])
            except Exception:
                pass

        curr_data[field_name] = new_value
        conn.execute(
            f"UPDATE video_metadata SET {json_col} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(curr_data), now, meta_id)
        )
    conn.close()
    return True


def delete_video_metadata(target_type: str, target_id: Any) -> bool:
    """Deletes metadata record."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute(
            "DELETE FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
    conn.close()
    return True


# =====================================================================
# --- AI THUMBNAIL & COVER ASSET PERSISTENCE ---
# =====================================================================

def save_thumbnail_asset(
    target_type: str,
    target_id: Any,
    image_path: str,
    headline: str,
    variation_type: str = "emotional",
    aspect_ratio: str = "9:16",
    style_mode: str = "auto",
    source_timestamp: float = 1.0,
    is_selected: int = 0,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation"
) -> int:
    """Saves a thumbnail asset variation for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        if is_selected:
            conn.execute("""
                UPDATE thumbnail_assets
                SET is_selected = 0
                WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
            """, (target_type, t_id_str, aspect_ratio))

        cur = conn.execute("""
            INSERT INTO thumbnail_assets (
                job_id, target_type, target_id, account_id, aspect_ratio,
                platform, style_mode, variation_type, headline, image_path,
                source_timestamp, is_selected, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, target_type, t_id_str, account_id, aspect_ratio,
              "universal", style_mode, variation_type, headline, image_path,
              source_timestamp, is_selected, now))
        asset_id = cur.lastrowid
    conn.close()
    return asset_id


def get_thumbnail_asset(asset_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single thumbnail asset by ID."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT * FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_thumbnail_assets(
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    account_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lists thumbnail assets with optional filtering."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM thumbnail_assets WHERE 1=1"
        params = []
        if target_type:
            q += " AND target_type = ?"
            params.append(target_type)
        if target_id is not None:
            q += " AND target_id = ?"
            params.append(str(target_id))
        if account_id and account_id != "all":
            q += " AND account_id = ?"
            params.append(account_id)
        q += " ORDER BY is_selected DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def select_thumbnail_asset(asset_id: int, target_type: str, target_id: Any) -> bool:
    """Designates a specific thumbnail variation as the approved active cover."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    with conn:
        cur = conn.execute("SELECT aspect_ratio FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        ar = row["aspect_ratio"]
        conn.execute("""
            UPDATE thumbnail_assets
            SET is_selected = 0
            WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
        """, (target_type, t_id_str, ar))
        conn.execute("UPDATE thumbnail_assets SET is_selected = 1 WHERE id = ?", (asset_id,))
    conn.close()
    return True


def delete_thumbnail_asset(asset_id: int) -> bool:
    """Deletes a thumbnail asset and removes its local file if present."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT image_path FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if row and row["image_path"] and os.path.exists(row["image_path"]):
            try:
                os.remove(row["image_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM thumbnail_assets WHERE id = ?", (asset_id,))
    conn.close()
    return True

def save_video_metadata(
    target_type: str,
    target_id: Any,
    title: str,
    niche: str = "Motivation",
    youtube_data: Optional[Dict[str, Any]] = None,
    instagram_data: Optional[Dict[str, Any]] = None,
    tiktok_data: Optional[Dict[str, Any]] = None,
    title_variations: Optional[Dict[str, Any]] = None,
    quality_score: int = 85,
    quality_breakdown: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation",
    status: str = "draft"
) -> int:
    """Saves or updates full platform metadata for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        # Check if record already exists
        cur = conn.execute(
            "SELECT id FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        existing = cur.fetchone()
        yt_json = json.dumps(youtube_data or {})
        ig_json = json.dumps(instagram_data or {})
        tt_json = json.dumps(tiktok_data or {})
        tv_json = json.dumps(title_variations or {})
        qb_json = json.dumps(quality_breakdown or {})

        if existing:
            meta_id = existing["id"]
            conn.execute("""
                UPDATE video_metadata
                SET title = ?, niche = ?, youtube_json = ?, instagram_json = ?,
                    tiktok_json = ?, title_variations_json = ?, quality_score = ?,
                    quality_breakdown_json = ?, job_id = COALESCE(?, job_id),
                    account_id = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (title, niche, yt_json, ig_json, tt_json, tv_json, quality_score,
                  qb_json, job_id, account_id, status, now, meta_id))
        else:
            cur_ins = conn.execute("""
                INSERT INTO video_metadata (
                    job_id, target_type, target_id, account_id, title, niche,
                    youtube_json, instagram_json, tiktok_json, title_variations_json,
                    quality_score, quality_breakdown_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, target_type, t_id_str, account_id, title, niche,
                  yt_json, ig_json, tt_json, tv_json, quality_score, qb_json, status, now, now))
            meta_id = cur_ins.lastrowid

    conn.close()
    return meta_id


def get_video_metadata(target_type: str, target_id: Any) -> Optional[Dict[str, Any]]:
    """Retrieves full platform metadata for a specific target."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute(
            "SELECT * FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
        if res.get(f):
            try:
                res[f.replace("_json", "")] = json.loads(res[f])
            except Exception:
                pass
    return res


def list_video_metadata(account_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Lists video metadata records."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM video_metadata"
        params = []
        if account_id and account_id != "all":
            q += " WHERE account_id = ?"
            params.append(account_id)
        q += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        for f in ("youtube_json", "instagram_json", "tiktok_json", "title_variations_json", "quality_breakdown_json"):
            if d.get(f):
                try:
                    d[f.replace("_json", "")] = json.loads(d[f])
                except Exception:
                    pass
        res.append(d)
    return res


def update_video_metadata_field(
    target_type: str,
    target_id: Any,
    platform: str,
    field_name: str,
    new_value: Any
) -> bool:
    """Updates a specific field in YouTube, Instagram, or TikTok metadata."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    now = datetime.now(timezone.utc).isoformat()
    json_col = f"{platform}_json"
    with conn:
        cur = conn.execute(
            f"SELECT id, {json_col} FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, t_id_str)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False

        meta_id = row["id"]
        curr_data = {}
        if row[json_col]:
            try:
                curr_data = json.loads(row[json_col])
            except Exception:
                pass

        curr_data[field_name] = new_value
        conn.execute(
            f"UPDATE video_metadata SET {json_col} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(curr_data), now, meta_id)
        )
    conn.close()
    return True


def delete_video_metadata(target_type: str, target_id: Any) -> bool:
    """Deletes metadata record."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute(
            "DELETE FROM video_metadata WHERE target_type = ? AND target_id = ?",
            (target_type, str(target_id))
        )
    conn.close()
    return True


# =====================================================================
# --- AI THUMBNAIL & COVER ASSET PERSISTENCE ---
# =====================================================================

def save_thumbnail_asset(
    target_type: str,
    target_id: Any,
    image_path: str,
    headline: str,
    variation_type: str = "emotional",
    aspect_ratio: str = "9:16",
    style_mode: str = "auto",
    source_timestamp: float = 1.0,
    is_selected: int = 0,
    job_id: Optional[str] = None,
    account_id: str = "acc_motivation"
) -> int:
    """Saves a thumbnail asset variation for a video, short, or episode."""
    init_db()
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    t_id_str = str(target_id)
    with conn:
        if is_selected:
            # Unselect other thumbnails for this target and aspect ratio
            conn.execute("""
                UPDATE thumbnail_assets
                SET is_selected = 0
                WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
            """, (target_type, t_id_str, aspect_ratio))

        cur = conn.execute("""
            INSERT INTO thumbnail_assets (
                job_id, target_type, target_id, account_id, aspect_ratio,
                platform, style_mode, variation_type, headline, image_path,
                source_timestamp, is_selected, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, target_type, t_id_str, account_id, aspect_ratio,
              "universal", style_mode, variation_type, headline, image_path,
              source_timestamp, is_selected, now))
        asset_id = cur.lastrowid
    conn.close()
    return asset_id


def get_thumbnail_asset(asset_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single thumbnail asset by ID."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT * FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_thumbnail_assets(
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    account_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Lists thumbnail assets with optional filtering."""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "SELECT * FROM thumbnail_assets WHERE 1=1"
        params = []
        if target_type:
            q += " AND target_type = ?"
            params.append(target_type)
        if target_id is not None:
            q += " AND target_id = ?"
            params.append(str(target_id))
        if account_id and account_id != "all":
            q += " AND account_id = ?"
            params.append(account_id)
        q += " ORDER BY is_selected DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def select_thumbnail_asset(asset_id: int, target_type: str, target_id: Any) -> bool:
    """Designates a specific thumbnail variation as the approved active cover."""
    init_db()
    conn = get_db_connection()
    t_id_str = str(target_id)
    with conn:
        # Get aspect ratio of the target asset
        cur = conn.execute("SELECT aspect_ratio FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        ar = row["aspect_ratio"]
        conn.execute("""
            UPDATE thumbnail_assets
            SET is_selected = 0
            WHERE target_type = ? AND target_id = ? AND aspect_ratio = ?
        """, (target_type, t_id_str, ar))
        conn.execute("UPDATE thumbnail_assets SET is_selected = 1 WHERE id = ?", (asset_id,))
    conn.close()
    return True


def delete_thumbnail_asset(asset_id: int) -> bool:
    """Deletes a thumbnail asset and removes its local file if present."""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("SELECT image_path FROM thumbnail_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if row and row["image_path"] and os.path.exists(row["image_path"]):
            try:
                os.remove(row["image_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM thumbnail_assets WHERE id = ?", (asset_id,))
    conn.close()
    return True



