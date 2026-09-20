@echo off
REM Supremo CLI mode (Windows)
REM Run this file for terminal/command-line mode

cd /d "%~dp0"
python3 main.py --cli %*
