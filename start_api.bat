@echo off
echo.
echo ============================================================
echo Starting Jarvis Wine Sommelier API (Fresh Instance)
echo ============================================================
echo.
echo Guest PWA + API on port 8000
echo Live:      https://jarvis.agenthaus.io/?r=maass
echo Phone:     http://THIS-PC-LAN-IP:8000/?r=maass
echo QR table:  http://THIS-PC-LAN-IP:8000/showcase
echo Admin:     http://localhost:8000/admin  (dev password: maass-admin)
echo.
echo Press CTRL+C to stop
echo.

REM Project venv lives on OneDrive and can be cloud-stubbed; use a local copy.
set "JARVIS_PY=%LOCALAPPDATA%\jarvis-sommelier-venv\Scripts\python.exe"
if not exist "%JARVIS_PY%" (
  echo ERROR: Local venv not found at %JARVIS_PY%
  echo Recreate it with: uv venv "%%LOCALAPPDATA%%\jarvis-sommelier-venv" --python 3.11
  echo Then: uv pip install -r requirements.txt --python "%%LOCALAPPDATA%%\jarvis-sommelier-venv\Scripts\python.exe"
  exit /b 1
)

"%JARVIS_PY%" -m uvicorn api.mobile_api:app --host 0.0.0.0 --port 8000
