@echo off
rem Double-click: simulate a family for 3 weeks and open the Weekly Verdict.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -m chorecourt demo
pause
