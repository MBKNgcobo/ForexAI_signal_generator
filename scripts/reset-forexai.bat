@echo off
REM ===========================================================================
REM ForexAI - factory reset (Windows). DESTRUCTIVE - deletes ALL data.
REM
REM Stops the stack and deletes the database + DataProtection volumes.
REM The client must type RESET to confirm and must have a backup first.
REM ===========================================================================
cd /d "%~dp0.."

echo.
echo ============================================
echo   ForexAI - factory reset (DELETES DATA)
echo ============================================
echo.
echo This will permanently delete:
echo   - all user accounts
echo   - all signals and history
echo   - all application data in Docker
echo.
echo The code and .env file are kept. Only the database is deleted.
echo.
echo If you want a backup first, close this window and run:
echo   scripts\backup-forexai.bat
echo.
set "CONFIRM="
set /p "CONFIRM= Type RESET (all capitals) to continue, or press Enter to cancel: "
if not "%CONFIRM%"=="RESET" (
    echo.
    echo Cancelled. Nothing was deleted.
    echo.
    pause
    exit /b 0
)
echo.
echo Resetting - deleting containers and database volumes...
docker compose down -v
if errorlevel 1 (
    echo.
    echo [ERROR] Reset failed - see the output above.
    pause
    exit /b 1
)
echo.
echo [OK] Reset complete. All data deleted.
echo      Run start.bat to create a fresh system.
echo.
pause
exit /b 0
