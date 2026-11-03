"""
24/7 Autonomous Job Scheduler & Recovery Daemon for VedioHooks AI Media Factory.
Handles continuous processing of queued jobs, automatic restart recovery,
controlled CPU worker concurrency, and exponential backoff retry.
"""

import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import signal
import threading
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Ensure root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import (
    init_db,
    get_pending_jobs,
    recover_interrupted_jobs,
    mark_job_started,
    mark_job_completed,
    mark_job_failed,
    get_job,
    is_emergency_stopped,
    get_system_setting,
    list_content_sources,
    create_job,
    list_jobs,
    backup_database
)
from src.pipeline_worker import process_video_job

# Concurrency & cadence settings from environment
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
POLL_INTERVAL_SEC = float(os.environ.get("SCHEDULER_POLL_INTERVAL_SEC", "3.0"))
DISCOVERY_INTERVAL_SEC = float(os.environ.get("DISCOVERY_INTERVAL_SEC", "120.0"))


class AutonomousScheduler:
    """
    24/7 autonomous scheduler daemon.
    Continuously pulls queued jobs from SQLite, runs them under a concurrency semaphore,
    polls registered content sources for autonomous discovery, performs automated backups,
    and automatically recovers interrupted jobs upon Windows/app startup.
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_JOBS):
        self.max_concurrent = max_concurrent
        self.semaphore = threading.Semaphore(max_concurrent)
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.discovery_thread: Optional[threading.Thread] = None
        self.active_jobs: Dict[str, threading.Thread] = {}
        self.lock = threading.Lock()
        self.last_backup_time = 0.0

    def start(self):
        """Starts the scheduler background daemon and discovery engine."""
        if self.running:
            return

        init_db()
        # Step 1: Automatic startup crash recovery
        recovered = recover_interrupted_jobs()
        if recovered > 0:
            print(f"[+] [SCHEDULER] Automatically recovered {recovered} interrupted job(s) from previous session!")

        self.running = True
        self.worker_thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="SchedulerDaemon")
        self.worker_thread.start()

        self.discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True, name="DiscoveryDaemon")
        self.discovery_thread.start()

        print(f"[+] [SCHEDULER] 24/7 Autonomous Scheduler started (Max concurrency: {self.max_concurrent}, Poll: {POLL_INTERVAL_SEC}s, Discovery: {DISCOVERY_INTERVAL_SEC}s)")

    def stop(self, wait: bool = True):
        """Signals scheduler to stop gracefully."""
        self.running = False
        if wait and self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        if wait and self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_thread.join(timeout=5.0)
        print("[-] [SCHEDULER] Autonomous Scheduler stopped.")

    def _scheduler_loop(self):
        """Continuous polling loop for jobs."""
        while self.running:
            try:
                # Halt execution if emergency stop is engaged or automation is toggled off
                if is_emergency_stopped() or get_system_setting("global_automation", "1") != "1":
                    time.sleep(POLL_INTERVAL_SEC)
                    continue

                # Fetch pending jobs if concurrency permits
                with self.lock:
                    active_count = len(self.active_jobs)

                available_slots = self.max_concurrent - active_count
                if available_slots > 0:
                    pending = get_pending_jobs(limit=available_slots)
                    for job in pending:
                        job_id = job["id"]
                        with self.lock:
                            if job_id not in self.active_jobs:
                                t = threading.Thread(
                                    target=self._execute_job,
                                    args=(job,),
                                    daemon=True,
                                    name=f"JobWorker-{job_id}"
                                )
                                self.active_jobs[job_id] = t
                                t.start()
            except Exception as e:
                print(f"[!] [SCHEDULER] Error in scheduler loop: {e}")
                traceback.print_exc()

            time.sleep(POLL_INTERVAL_SEC)

    def _discovery_loop(self):
        """Autonomous background content discovery and backup loop."""
        while self.running:
            try:
                # Only discover if emergency stop is OFF and automation is ON
                if not is_emergency_stopped() and get_system_setting("global_automation", "1") == "1":
                    sources = list_content_sources(limit=50)
                    existing_jobs = list_jobs(limit=100)
                    existing_urls = {j.get("source_path") for j in existing_jobs}

                    for src in sources:
                        url = src.get("source_url_or_path", "").strip()
                        if url and url.startswith("http") and url not in existing_urls:
                            # Auto-enqueue new discovered content source
                            new_job_id = f"auto_{int(time.time())}_{src['id'][:4]}"
                            print(f"[+] [DISCOVERY] Ingesting new video from source '{src['title']}': {url}")
                            create_job(
                                job_id=new_job_id,
                                source_type="url",
                                source_path=url,
                                priority=1,
                                account_id=src.get("account_id", "acc_motivation")
                            )
                            existing_urls.add(url)

                    # Automated backup every 6 hours (21600 seconds)
                    now_ts = time.time()
                    if now_ts - self.last_backup_time > 21600:
                        backup_database()
                        self.last_backup_time = now_ts
            except Exception as ex:
                print(f"[!] [DISCOVERY] Discovery loop error: {ex}")

            time.sleep(DISCOVERY_INTERVAL_SEC)

    def _execute_job(self, job: Dict[str, Any]):
        """Executes a single job with concurrency management, crash protection, and retry."""
        job_id = job["id"]
        source_type = job["source_type"]
        source_path = job["source_path"]

        self.semaphore.acquire()
        try:
            print(f"[*] [SCHEDULER] Starting job {job_id} ({source_type}: {source_path})")
            mark_job_started(job_id)

            is_url = (source_type == "url")
            # Execute pipeline
            process_video_job(
                job_id=job_id,
                source=source_path,
                is_url=is_url,
                model_size="base.en"
            )

            # Check resulting status
            updated = get_job(job_id)
            if updated and updated.get("status") == "ready":
                mark_job_completed(job_id)
                print(f"[SUCCESS] [SCHEDULER] Job {job_id} successfully completed!")

        except Exception as ex:
            err_msg = str(ex)
            print(f"[ERROR] [SCHEDULER] Job {job_id} encountered exception: {err_msg}")
            will_retry = mark_job_failed(job_id, err_msg, can_retry=True)
            if will_retry:
                print(f"[*] [SCHEDULER] Job {job_id} has been re-enqueued for exponential backoff retry.")
            else:
                print(f"[-] [SCHEDULER] Job {job_id} permanently failed (max retries reached).")
        finally:
            self.semaphore.release()
            with self.lock:
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]


# Global scheduler instance
scheduler = AutonomousScheduler()


if __name__ == "__main__":
    # Allow running standalone: python -m src.scheduler
    print("=" * 60)
    print(" 24/7 AUTONOMOUS JOB SCHEDULER DAEMON (STANDALONE)")
    print("=" * 60)

    scheduler.start()

    def handle_signal(sig, frame):
        print("\n[*] Received shutdown signal. Terminating scheduler...")
        scheduler.stop(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("[*] Scheduler daemon is running 24/7. Press Ctrl+C to stop.")
    while True:
        time.sleep(1.0)
