@echo off
REM BrandShield AI - start the app and create a public link for your phone.
cd /d "%~dp0"

echo Starting BrandShield AI...
start "BrandShield AI server" /min cmd /c "cd /d "%~dp0backend" && "%~dp0env\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

"%~dp0env\Scripts\python.exe" "%~dp0backend\scripts\go_live.py"

echo.
echo Leave this window open. Press any key to STOP the server and the link.
pause >nul
taskkill /FI "WINDOWTITLE eq BrandShield AI server*" /T /F >nul 2>&1
taskkill /IM cloudflared-windows-amd64.exe /F >nul 2>&1
