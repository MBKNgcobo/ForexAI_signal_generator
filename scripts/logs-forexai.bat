@echo off
REM ===========================================================================
REM ForexAI - show recent application logs (Windows, no commands needed)
REM
REM Shows the last 100 lines across all services and saves them to
REM logs.txt next to this script. Developer-level errors stay in the logs;
REM this script only adds a plain-English hint for the common cases.
REM ===========================================================================
cd /d "%~dp0.."

echo.
echo ============================================
echo   ForexAI - recent logs
echo ============================================
echo.
docker compose logs --tail 100
if errorlevel 1 (
    echo.
    echo [ERROR] Could not read the logs. Is Docker Desktop running?
    echo         Start Docker Desktop, then run start.bat first.
    echo.
    pause
    exit /b 1
)
echo.
docker compose logs --tail 200 > "logs.txt" 2>&1
echo Full output saved to:  logs.txt
echo Send that file to support if you need help.
echo.
echo Common patterns:
echo   - "POSTGRES_PASSWORD is not set" .... fill in .env, run start.bat again
echo   - "port is already in use" .......... change DASHBOARD_PORT in .env
echo   - "connection refused" on first run . services still starting, wait
echo.
pause
exit /b 0
