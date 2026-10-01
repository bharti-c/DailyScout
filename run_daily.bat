@echo off
REM DailyScout Morning Briefing Runner for Windows Task Scheduler
REM Scheduled to run daily at 07:00 AM IST

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo =======================================================
echo [%date% %time%] Starting DailyScout Morning Agent...
echo =======================================================

REM Run with Python
python scout.py --send-email >> reports\runner.log 2>&1

if %errorlevel% neq 0 (
    echo [ERROR] DailyScout execution failed with code %errorlevel%
    exit /b %errorlevel%
)

echo [%date% %time%] DailyScout execution completed successfully.
exit /b 0
