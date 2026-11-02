@echo off
title IVIA OV3660 Vision Dashboard
cd /d "%~dp0"

echo =======================================================
echo    IVIA OV3660 STANDALONE VISION DASHBOARD LAUNCHER
echo =======================================================
echo.

:: Prompt for IP or use default
set /p ESP_IP="Enter your ESP32-S3 IP Address (or press Enter for 10.35.199.118): "
if "%ESP_IP%"=="" set ESP_IP=10.35.199.118

:: Strip http:// or https:// if pasted by user
set ESP_IP=%ESP_IP:http://=%
set ESP_IP=%ESP_IP:https://=%
set ESP_IP=%ESP_IP:/=%

echo.
echo Launching AI Vision Dashboard for IP: %ESP_IP%...
echo (Press 'q' in the video window to quit, 's' to save snapshot)
echo.

python vision_dashboard.py --ip %ESP_IP%

pause
