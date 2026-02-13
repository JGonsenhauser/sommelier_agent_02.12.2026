@echo off
echo.
echo ============================================================
echo Starting Jarvis Wine Sommelier API (Fresh Instance)
echo ============================================================
echo.
echo API will be available at: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo.
echo Press CTRL+C to stop
echo.

uvicorn api.mobile_api:app --reload --port 8000
