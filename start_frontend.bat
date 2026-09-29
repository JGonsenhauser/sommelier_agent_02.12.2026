@echo off
echo.
echo ============================================================
echo Starting Jarvis Wine Sommelier FRONTEND (Streamlit UI)
echo ============================================================
echo.
echo IMPORTANT: Make sure the API is running first!
echo   (Run start_api.bat in another terminal)
echo.
echo Frontend will be available at: http://localhost:8501
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

"%JARVIS_PY%" -m streamlit run restaurants/app_fastapi_hybrid.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
