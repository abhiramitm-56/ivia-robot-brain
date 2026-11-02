@echo off
title IVIA AI Humanoid Chatbot Server
cd /d "%~dp0"

echo ========================================================
echo          IVIA AI HUMANOID COMPANION SERVER
echo ========================================================
echo.

:: Detect Python executable (.venv or system)
set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
    echo [INFO] Using virtual environment: .venv
) else (
    echo [INFO] Using system Python
)

echo [INFO] Starting IVIA Brain Server at http://localhost:8000 ...
echo [INFO] ESP32 WebSocket Endpoint: ws://localhost:8000/ws/esp32
echo.

:: Open the browser after 2 seconds in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: Launch FastAPI Uvicorn Server
%PYTHON_EXE% -m uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload

pause

