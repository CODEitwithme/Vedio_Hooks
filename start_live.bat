@echo off
title VedioHooks AI - Live Production Media Factory
cd /d "%~dp0"
echo =====================================================================
echo  Launching VedioHooks AI Live Production Factory...
echo =====================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_live_production.py
) else (
    python run_live_production.py
)
pause
