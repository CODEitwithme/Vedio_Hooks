# VedioHooks AI — Autonomous Media Factory Roadmap

## Mission Objective
Transform VedioHooks AI into a professional, production-grade, 24/7 autonomous Instagram Reels and vertical Shorts media factory.

---

## Autonomous Development: Top 5 High-Value Improvements

| Priority | Feature / Improvement | Module | Impact / Value |
| :---: | :--- | :--- | :--- |
| **P1** | **Database Isolation & Dummy Data Purge** | `src/db.py`, `tests/conftest.py` | Isolate test runs to `test_jobs.db` so test assertions never pollute the creator's real `jobs.db` with synthetic records (`test_crud_*`, `crash_*`, `pub_*`). Purge all mock entries. |
| **P2** | **Dynamic Real-Time Analytics Engine** | `src/analytics.py`, `src/server.py` | Replace hardcoded static skeleton numbers in `tab-analytics` with live SQLite aggregations (`/api/analytics`), reporting actual average virality, hook retention curves, and daily output per account. |
| **P3** | **Automated 9:16 High-CTR Cover Thumbnail Studio** | `src/thumbnail_engine.py`, `src/server.py` | Generate 3 distinct high-converting cover thumbnail styles (Kinetic Hormozi Headline, Face Zoom + Contrast Pop, Clean Minimalist Cinema) with 1-click preview and download. |
| **P4** | **Sound Design Beat-Sync Engine** | `src/beat_sync.py`, `src/pipeline_worker.py` | Detect musical downbeats and rhythmic audio energy peaks to snap subtitle pop animations and video cutaway transitions to the rhythm. |
| **P5** | **Multi-Platform Export Engine (Reels + Shorts + TikTok)** | `src/multi_platform_export.py`, `src/server.py` | 1-Click reformatting of captions, title hooks, sound tags, and pinned comment copy specifically tailored for YouTube Shorts and TikTok algorithms alongside Instagram Reels. |

---

## Operational Execution Protocol
1. **Zero Contamination:** Pure user-data isolation; automated tests must never write to production `jobs.db`.
2. **100% Free & Open Source:** No paid API keys, no subscriptions, no mandatory cloud dependencies.
3. **Rigorous Quality Gate:** Every improvement must include comprehensive pytest automated test coverage.
4. **Git Checkpointing:** Each milestone committed cleanly into version control.
