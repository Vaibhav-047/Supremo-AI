@echo off
REM Supremo - Install Dependencies (Windows)
REM Run this file first to install required packages

pip install SpeechRecognition sounddevice numpy 2>nul || python -m pip install SpeechRecognition sounddevice numpy

echo.
echo Dependencies installed. Run 'run_windows.bat' to start Supremo.
pause
