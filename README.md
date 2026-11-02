# ⚡ VedioHooks AI — Autonomous Multi-Account Media Factory & Content Engine

> Transform long videos (YouTube podcasts, interviews, sports broadcasts, tutorials) into viral, crispy, 9:16 vertical short-form videos for **Instagram Reels, TikTok, and YouTube Shorts** with multi-account isolation, AI virality scoring, word-level timestamps, smart face-centered reframing, **2-speaker split-screen vertical stacking**, **kinetic pop karaoke subtitles with contextual auto-emojis**, a **14-point AI Content Director blueprint engine**, and a **commercial SaaS dashboard**.

---

## 🚀 Key Features

1. **Multi-Account Instagram Content Network**:
   - Manage multiple specialized accounts from one central dashboard with complete data isolation.
   - 5 default preconfigured niche profiles:
     - **Motivation & Mindset** (`acc_motivation`): Stoic discipline, cinematic pacing, bold yellow subtitles (`hormozi_yellow`).
     - **Cricket News & Stories** (`acc_cricket`): Verified player stories, match analysis, rights-cleared commentary disclaimers, sports graphics (`hormozi_green`).
     - **AI & Study** (`acc_ai_study`): AI tools, learning strategies, clean typography, cyber cyan subtitles (`cyber_cyan`).
     - **Gym & Fitness** (`acc_fitness`): Workout science, hypertrophy cues, injury prevention disclaimers, beast red subtitles (`beast_red`).
     - **Common / General** (`acc_general`): Curiosity loops, historical breakthroughs, clean minimal captions (`clean_minimal`).

2. **Kinetic Pop Subtitles & Contextual Auto-Emojis**:
   - **Kinetic Pop Animation:** Subtle 12% scale zoom (`\fscx112\fscy112`) on the active spoken word creating an energetic, high-retention cadence.
   - **Auto-Emoji Tagging:** Contextually maps emotional trigger words to animated emojis (e.g. *MONEY* $\to$ 💸, *FIRE* $\to$ 🔥, *SECRET* $\to$ 🤫, *POWER* $\to$ ⚡, *BRAIN* $\to$ 🧠, *GYM* $\to$ 🏋️‍♂️, *CRICKET* $\to$ 🏏).
   - 6 aesthetic themes with safe-zone margin preservation (`margin_v=720`) to prevent UI occlusion on Instagram Reels.

3. **Multi-Speaker Face Tracking & Split-Screen Stacking (1+1 Mode)**:
   - MediaPipe face detection probes speaker focal centers and applies median filtering for stable 9:16 vertical cropping.
   - **Split-Screen Stacking (`split_stack`):** Vertically stacks Host on top (1080x960) and Guest on bottom (1080x960) for 2-person podcast and interview clips.

4. **Hardware Acceleration Auto-Detection**:
   - Automatically probes and utilizes GPU hardware acceleration (NVIDIA NVENC, AMD AMF, Intel QSV) and falls back safely to multi-threaded CPU `libx264`.

5. **Autonomous Content Discovery & Automated Backups**:
   - Background discovery daemon (`_discovery_loop`) periodically checks registered content sources for newly published video links.
   - Non-blocking online SQLite backups (`POST /api/database/backup`) via `VACUUM INTO`.

6. **AI Content Director — 14-Point Strategic Blueprints**:
   - Generates comprehensive strategic content blueprints:
     1. Topic & Angle, 2. Target Audience, 3. Video Concept, 4. Viral Opening Hook (1–3s), 5. Script Selection, 6. Clip Timestamps, 7. Retention Tactics, 8. Editing Rules, 9. Subtitle Theme, 10. Optimized Captions, 11. Targeted Hashtags, 12. Cover Text, 13. Rights & Compliance Disclaimers, 14. Virality Quality Score (0–100).
   - 100% Free deterministic local heuristic generator + optional Gemini/OpenAI cloud expansion.

7. **Commercial SaaS Dashboard (Linear / Vercel / Stripe Aesthetic)**:
   - Polished dark-mode UI with high-density metrics, subtle glassmorphism, responsive navigation, and 12 dedicated operational views:
     - **Overview**: Global KPI metrics, account switcher, active jobs, recent renders reel.
     - **Account Manager**: Full account CRUD, status toggling, posting schedules, caption formulas.
     - **Content Discovery**: Curated source tracking (YouTube, RSS, keywords) with factual verification notes.
     - **AI Content Director**: On-demand 14-point blueprint generator & history viewer.
     - **Video Factory**: URL and file ingestion, face tracking & split-stack selector, theme preview, live progress bar.
     - **Video Library**: 9:16 vertical shorts gallery with HTML5 video player, HTTP 206 Range streaming, and 1-click **📷 Cover Frame** thumbnail extraction.
     - **Publishing Calendar**: Instagram drafts queue, caption editor, schedule picker, manual approvals.
     - **Instagram Graph API**: Official Meta API v19.0 compliance status, rate limit monitoring, zero-scraping guarantee.
     - **Analytics**: Hook retention distribution, virality scores, account production cadences.
     - **Automation Centre**: 24/7 background worker controls, queue health, auto-recovery.
     - **System Health**: Telemetry gauges (CPU, RAM, Disk, Workers, FFmpeg status, Database CRUD).
     - **Settings**: System maintenance, disk cleanup tools, online database backup creator, engine configuration.

8. **Global Emergency Stop & Crash Recovery**:
   - Immediate master kill switch (`POST /api/automation/emergency-stop`) that instantly freezes all new job ingestion (rejecting with HTTP 423) and halts background rendering.
   - Persistent SQLite ACID job queue with automatic recovery of interrupted jobs.

---

## 💻 Quick Start on Windows 11

### 1. Launch the Media Factory
```powershell
.\.venv\Scripts\python.exe start_app.py
```
- **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Live System Telemetry**: [http://127.0.0.1:8000/api/system/stats](http://127.0.0.1:8000/api/system/stats)

### 2. Run Automated Test Suite
```powershell
.\.venv\Scripts\pytest.exe -v
```
Runs all 34 automated unit, API, integration, and multi-account tests (**100% pass rate** in ~13 seconds).

---

## 📁 Project Architecture

```text
Vedio_Hooks/
├── src/
│   ├── server.py               # FastAPI application, 12-view commercial dashboard & thumbnail streaming
│   ├── scheduler.py            # 24/7 autonomous scheduler, discovery engine & backup daemon
│   ├── db.py                   # SQLite database manager, atomic backups & multi-account migrations
│   ├── ai_director.py          # AI Content Director 14-point strategic blueprint generator
│   ├── publishing.py           # Meta Instagram Graph API client & safety guardrails
│   ├── pipeline_worker.py      # Async background rendering orchestrator (smart face & split stack)
│   ├── ingest.py               # Video ingestion & 16kHz WAV extraction (yt-dlp + FFmpeg)
│   ├── transcribe.py           # Faster-Whisper singleton model & word-level timestamp engine
│   ├── virality_selector.py    # Multi-dimensional virality evaluation & NMS selector
│   ├── video_slicer.py         # 9:16 vertical cropping, split-stack & hardware encoder detection
│   ├── subtitle_generator.py   # Kinetic pop animation, contextual auto-emojis & ASS generator
│   └── face_tracker.py         # MediaPipe & OpenCV smart speaker centering and split stacking
├── tests/
│   ├── test_multi_account_factory.py  # Multi-account CRUD, AI director, kinetic subtitles, split-stack
│   ├── test_pipeline_and_api.py       # Baseline pipeline & REST API tests
│   └── test_production_factory.py     # 24/7 scheduler, recovery, telemetry & security tests
├── output/                     # Rendered 9:16 viral shorts
├── temp/                       # Ingested streams, intermediate WAVs, transcripts, thumbnails
├── models/                     # MediaPipe face detection TFLite model
├── backups/                    # Atomic SQLite database snapshots
├── start_app.py                # Production application launcher
├── jobs.db                     # SQLite database tracking accounts, jobs, renders, and drafts
├── PROJECT_AUDIT.md            # Comprehensive project audit report
├── PRODUCTION_READINESS.md     # Production readiness scorecard & risk matrix
└── ARCHITECTURE.md             # Architecture specification & Mermaid diagrams
```
