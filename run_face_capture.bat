@echo off
title IVIA Face Recognition + Voice Greeting (ESP32-S3)
cd /d "%~dp0face_robot\face_robot"

echo ========================================================
echo   IVIA MULTI-PERSON FACE RECOGNITION (ESP32-S3 OV3660)
echo ========================================================
echo.

:: Prompt for IP address or use default
set /p ESP_IP="Enter ESP32-S3 IP Address (or press Enter for 10.35.199.118): "
if "%ESP_IP%"=="" set ESP_IP=10.35.199.118

:: Strip http:// if entered
set ESP_IP=%ESP_IP:http://=%
set ESP_IP=%ESP_IP:https://=%
set ESP_IP=%ESP_IP:/=%

echo.
echo Launching Face Recognition on ESP32-S3: http://%ESP_IP%/stream
echo (Press 'Q' to quit, 'F' to flip image)
echo.

python capture.py --ip %ESP_IP%

pause

