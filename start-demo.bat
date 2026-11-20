@echo off
REM BrandShield AI - demo launcher
REM   http://127.0.0.1:8000  real data   (YouTube, news, App Store - your existing database)
REM   http://127.0.0.1:8001  demo data   (fresh database with 3 days of simulated history,
REM                                       used for the live crisis simulation)
REM The real database is never modified by the demo instance.

cd /d "%~dp0"

echo Stopping any running BrandShield servers...
taskkill /FI "WINDOWTITLE eq BrandShield REAL*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq BrandShield DEMO*" /T /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 :8001" ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1

echo Resetting the demo database (fresh history every run)...
del /q "backend\data\demo.db" "backend\data\demo.db-wal" "backend\data\demo.db-shm" >nul 2>&1

REM Use the models already downloaded - do not wait on the network
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

start "BrandShield REAL :8000" /min cmd /c "cd /d "%~dp0backend" && "%~dp0env\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "BrandShield DEMO :8001" /min cmd /c "cd /d "%~dp0backend" && set DATABASE_PATH=data/demo.db&& set SIMULATOR_RATE_PER_MIN=20&& set ANALYTICS_INTERVAL_SECONDS=10&& "%~dp0env\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001"

echo.
echo Starting... the demo instance needs about 5 minutes to generate its history.
echo Watch the progress bar in the 8001 tab, then you are ready.
timeout /t 20 /nobreak >nul
start "" http://127.0.0.1:8001
start "" http://127.0.0.1:8000
echo.
echo Both servers run minimised. Close their windows (or run this file again) to stop them.
pause
