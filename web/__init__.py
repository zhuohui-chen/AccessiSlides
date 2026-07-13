"""Local web app for the PowerPoint accessibility agent.

This package is an orchestration entry point (peer to ``cli.py``): it wraps the
existing checker/fixer/audit/report engine behind a small FastAPI server and a
single self-contained browser page. It must not implement any rule or fix logic
of its own — all detection and remediation stays in the engine modules.
"""
