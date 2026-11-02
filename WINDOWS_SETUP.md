# VedioHooks AI Media Factory - Windows 11 Operations & Setup Guide

**Target Environment:** Windows 11 AMD64  
**Python Runtime:** Python 3.14.6 in `.venv/`  
**Media Engine:** FFmpeg 9.0.2 full build with `libass` & `freetype`  

---

## 1. Quick Start Commands

### 1.1 Activate Environment & Verify System Health
Open PowerShell or Command Prompt in the project root:

```powershell
# Activate local virtual environment
.\.venv\Scripts\Activate.ps1

# Verify system dependencies (FFmpeg, Python, Model assets)
python check_health.py
```

### 1.2 Start the Application
To run the full web application, REST API, and embedded 24/7 autonomous scheduler:

```powershell
python start_app.py
```

- **Web Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Live Telemetry & Stats:** [http://127.0.0.1:8000/api/system/stats](http://127.0.0.1:8000/api/system/stats)

### 1.3 Run the 24/7 Scheduler as a Dedicated Background Worker
If you prefer running the scheduler daemon independently from the API server:

```powershell
python -m src.scheduler
```

---

## 2. Stopping & Restarting

### How to Stop
- **In an interactive terminal:** Press `Ctrl + C`. The application executes a graceful shutdown handler, waiting for any active video render to finalize safely before releasing locks.
- **In PowerShell background task:**
  ```powershell
  # Find and terminate python server process
  Get-Process -Name python | Where-Object { $_.CommandLine -like "*start_app.py*" } | Stop-Process
  ```

### How to Restart
Simply run:
```powershell
python start_app.py
```
Upon restart, the built-in crash recovery system automatically:
1. Verifies the SQLite database integrity.
2. Identifies any jobs that were interrupted mid-flight.
3. Automatically re-queues them with retry tracking.

---

## 3. What Happens if Windows Shuts Down or Sleeps?

- **Persistent Queue:** All job states, transcripts, and render configurations are committed to `jobs.db`. No data is lost when Windows powers off.
- **Interrupted Tasks:** If the computer shuts down while a job is transcribing or rendering, that job is safely preserved. The next time you start the app, `recover_interrupted_jobs()` resets its status to `'queued'` and resumes processing.
- **Preventing Unexpected Sleep During Overnight Renders (Optional):**
  In Windows 11 Settings: `System` -> `Power & battery` -> `Screen and sleep` -> Set "When plugged in, put my device to sleep after" to **Never** or a higher threshold.

---

## 4. Configuration & Concurrency Tuning

Edit your `.env` file (copied from `.env.example`) to tune performance for your specific hardware:

### Concurrency Limit (`MAX_CONCURRENT_JOBS`)
```env
MAX_CONCURRENT_JOBS=2
```
- **Recommended for 6GB–8GB RAM:** `MAX_CONCURRENT_JOBS=1` or `2`
- **Recommended for 16GB+ RAM:** `MAX_CONCURRENT_JOBS=3` or `4`

### CPU Thread Limit (`WHISPER_CPU_THREADS`)
```env
WHISPER_CPU_THREADS=12
```
Sets the maximum CPU threads allocated to Faster-Whisper. Defaults to your physical core count.

### FFmpeg Preset (`FFMPEG_PRESET`)
```env
FFMPEG_PRESET=fast
```
Options: `ultrafast`, `faster`, `fast`, `medium`. `fast` offers the ideal balance between speed and quality.

---

## 5. Troubleshooting FFmpeg on Windows

If `check_health.py` reports `ffmpeg not found`:
1. Ensure `ffmpeg.exe` and `ffprobe.exe` are present in `C:\Users\LENOVO\.gemini\antigravity\bin\` or another directory in your Windows system PATH.
2. Verify FFmpeg has `libass` compiled:
   ```powershell
   ffmpeg -version | Select-String "enable-libass"
   ```
3. If Windows path escaping causes subtitle errors, note that `src/subtitle_generator.py` automatically normalizes filepaths into forward slashes and escapes the colon (`C\:/path/to/sub.ass`) for compatibility with FFmpeg filtergraphs.

---

## 6. Offline vs. Online Capabilities

| Feature | Offline Status | Requirement |
|---|---|---|
| **Local Video Ingestion** | **100% Offline** | Works locally with `.mp4`, `.mov`, `.mkv` files. |
| **YouTube Download** | Requires Internet | Requires internet connection for `yt-dlp`. |
| **Speech-to-Text Transcription** | **100% Offline** | Runs locally on CPU via Faster-Whisper INT8. |
| **AI Virality Selection (Heuristic)** | **100% Offline** | Built-in multi-dimensional heuristic scoring runs locally without any API keys. |
| **AI Virality Selection (LLM)** | Optional Online | Only if `GEMINI_API_KEY` or `OPENAI_API_KEY` is provided. |
| **Smart Face Tracking** | **100% Offline** | Runs locally via MediaPipe `blaze_face_full_range.tflite`. |
| **Animated Subtitle Burning** | **100% Offline** | Runs locally via FFmpeg `libass`. |
| **Web Dashboard & Streaming** | **100% Offline** | Hosted locally at `http://127.0.0.1:8000`. |
| **Instagram Reels Publishing** | Optional Online | Groundwork implemented; requires official Meta Graph API credentials. |

---

## 7. Running the Test Suite

Run all 22 automated tests:

```powershell
.\.venv\Scripts\pytest.exe -v
```
Expected output: **22 passed** in ~9.4 seconds.
