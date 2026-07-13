#!/bin/bash
# Double-click this file (macOS) to start AccessiSlides.
# It launches the local web app and opens it in your browser.
cd "$(dirname "$0")" || exit 1
echo "Starting AccessiSlides… a browser window will open shortly."
uv run python cli.py serve
