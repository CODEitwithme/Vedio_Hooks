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
    """Automatically resets interrupted jobs to 'queued' on startup."""
    interrupted = get_interrupted_jobs()
    if not interrupted:
        return 0

    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    recovered_count = 0
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

        # Publishing items by status
        pub_query = "SELECT status, COUNT(*) as cnt FROM publishing_queue"
        pub_params = []
        if account_id and account_id != "all":
            pub_query += " WHERE account_id = ?"
            pub_params.append(account_id)
        pub_query += " GROUP BY status"
        for row in conn.execute(pub_query, tuple(pub_params)).fetchall():
            stats[f"publishing_{row['status']}"] = row["cnt"]

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

