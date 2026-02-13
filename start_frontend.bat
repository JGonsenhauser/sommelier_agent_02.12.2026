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

streamlit run restaurants/app_fastapi_hybrid.py
