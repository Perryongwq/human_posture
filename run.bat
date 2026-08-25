@echo off
rem Starts Ollama (letter reading) + backend (FastAPI :8011) + frontend (Vite :5175, LAN-exposed).
rem Ports 5173/8010 are taken by Docker/WSL on this machine — do not reuse them.

set ROOT=%~dp0vue

rem ── Ollama :11434 — calibration reads the station letters through it ──
curl -s -m 3 http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Ollama not running - starting it...
    start "ollama :11434" cmd /k ollama serve
    timeout /t 5 >nul
)
curl -s -m 5 http://127.0.0.1:11434/api/tags | find "qwen3-vl" >nul
if errorlevel 1 (
    echo [FAIL] Ollama: not reachable on :11434 or model missing.
    echo        If it keeps failing, run: ollama pull qwen3-vl:8b
) else (
    echo [ OK ] Ollama on :11434, vision model qwen3-vl available.
)

rem live Ollama log — every /api/generate call from the app shows up here
start "ollama log" powershell -NoProfile -Command "Get-Content '%LOCALAPPDATA%\Ollama\server.log' -Tail 20 -Wait"

start "backend :8011" cmd /k "cd /d %ROOT%\backend && venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8011"
start "frontend :5175" cmd /k "cd /d %ROOT%\frontend && npm run dev"

echo.
echo Connection chain:
echo    browser -^> https://%COMPUTERNAME%:5175  (frontend, LAN)
echo            -^> /api proxy -^> 127.0.0.1:8011  (FastAPI backend)
echo            -^> 127.0.0.1:11434                (Ollama, qwen3-vl - calibration only)
echo.
echo Open from this PC or any PC on the network:  https://%COMPUTERNAME%:5175
echo (self-signed cert - accept the browser warning)
echo.
pause
