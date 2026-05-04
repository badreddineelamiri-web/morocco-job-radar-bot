@echo off
REM Run Morocco Job Radar Bot
cd /d "%~dp0"

REM Set DRY_RUN=true for testing without actual publishing
REM set DRY_RUN=true

REM Run the bot
python main.py

if errorlevel 1 (
    echo.
    echo ❌ Bot run failed! Check the logs above.
) else (
    echo.
    echo ✅ Bot run completed successfully!
)

pause
