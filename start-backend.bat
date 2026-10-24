@echo off
rem Starts the Androyit backend on this laptop (no Docker needed).
rem Double-click this file, or run it from a terminal. Keep the window open
rem while testing; close it (or press Ctrl+C) to stop the backend.

cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up Python packages, this takes a minute...
  python -m venv .venv || goto :error
  ".venv\Scripts\python" -m pip install -q -r requirements-dev.txt || goto :error
)

echo.
echo Androyit backend starting on http://localhost:8000
echo Phones on the same Wi-Fi use this laptop's address, port 8000.
echo Texts are only printed in this window while SMS_BACKEND=console.
echo.
".venv\Scripts\python" scripts\dev_server.py
pause
exit /b

:error
echo Setup failed. Is Python installed?
pause
