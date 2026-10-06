@echo off
REM ===========================================================================
REM ForexAI - stop the Docker stack (Windows)
REM
REM Keeps all data: containers are removed but the database volume
REM "forexai_forexai-postgres-data" is never touched.
REM ===========================================================================
cd /d "%~dp0.."

echo.
echo Stopping the ForexAI stack.
echo All data is kept - nothing is deleted.
echo.
docker compose down
if errorlevel 1 (
    echo.
    echo [ERROR] docker compose down failed - see the output above.
    pause
    exit /b 1
)
echo.
echo [OK] Stack stopped.
echo      Start it again with:  scripts\start-forexai.bat
echo.
pause
exit /b 0