@echo off
cd /d "%~dp0" || exit /b 1
title godd.ai - NVIDIA RTX GPU Accelerated Studio
echo ========================================================
echo  🚀 godd.ai Local GPU Server (RTX 3050 NVENC)
echo ========================================================
echo  Hardware: NVIDIA GeForce RTX 3050
echo  Encoder : Hardware h264_nvenc (Lightning ~1.8s renders)
echo  Server  : http://localhost:8080
echo ========================================================
echo.
echo Opening browser at http://localhost:8080 ...
start http://localhost:8080
python server.py
pause
