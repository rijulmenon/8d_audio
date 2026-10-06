@echo off
title 8D Audio - Real-Time Spatial Processor
echo Starting 8D Audio Application...
python app/main.py
if errorlevel 1 (
    echo.
    echo Application exited with error. Press any key to close.
    pause >nul
)
