@echo off
REM ===========================================================================
REM ForexAI - restart the running stack (Windows)
REM
REM Fast restart of the existing containers (no rebuild).
REM NOTE: if you edited .env, run start-forexai.bat instead - restarting
REM does not pick up changed environment values.
REM ===========================================================================
cd /d "%~dp0.."

echo.
echo Restarting the ForexAI stack...
docker compose restart
if errorlevel 1 (
    echo.
    echo [ERROR] docker compose restart failed - see the output above.
    pause
    exit /b 1
)
echo.
echo [OK] Restart requested. Run scripts\status-forexai.bat to verify.
echo.
pause
exit /b 0