@echo off
REM Build standalone Supremo.exe for Windows (requires PyInstaller)
REM pyinstaller --onefile --windowed --add-data "supremo.py;." --add-data "config.py;." main.py
REM
REM Or for development/testing: just use run_windows.bat with Python installed

echo === Supremo Windows Build ===
echo.
echo Option 1 - Development mode (requires Python installed):
echo   1. Run install_deps.bat
echo   2. Run run_windows.bat
echo.
echo Option 2 - Standalone executable (requires PyInstaller):
echo   pyinstaller --onefile --windowed main.py
echo   Then run dist\main.exe
echo.
echo Option 3 - CLI mode:
echo   Run run_cli_windows.bat
echo.
pause
