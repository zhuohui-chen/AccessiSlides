@echo off
REM Double-click this file (Windows) to start AccessiSlides.
REM It launches the local web app and opens it in your browser.
cd /d "%~dp0"
echo Starting AccessiSlides... a browser window will open shortly.
uv run python cli.py serve
pause
