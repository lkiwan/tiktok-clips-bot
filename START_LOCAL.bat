@echo off
echo ================================================
echo   TikTok Clips Bot - Local Processor
echo ================================================
echo.
echo This will process videos on your PC (faster!)
echo Close this window to stop.
echo.
echo ------------------------------------------------
echo.

cd /d "%~dp0"
python local_processor.py

pause
