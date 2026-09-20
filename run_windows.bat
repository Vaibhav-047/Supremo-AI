@echo off
REM Supremo - Desktop Management AI (Windows Launcher)
REM Run this file to start Supremo in GUI mode
REM
REM Requirements: Python 3.10+ (https://python.org)
REM               tkinter (included with Python)
REM               sounddevice, SpeechRecognition (optional, for voice mode)

cd /d "%~dp0"
python3 main.py %*
