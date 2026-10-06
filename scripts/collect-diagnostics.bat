@echo off
REM ===========================================================================
REM ForexAI - collect diagnostic bundle for support (Windows)
REM
REM Creates diagnostics\ with container status + recent logs + a redacted
REM config check. Secrets are NEVER written: values appear as ***SET*** or
REM ***MISSING*** only.
REM ===========================================================================
cd /d "%~dp0.."
setlocal enabledelayedexpansion

if not exist "diagnostics" mkdir "diagnostics" >nul 2>&1
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%i"
set "DIR=diagnostics\forexai-!TS!"
mkdir "!DIR!" >nul 2>&1

echo.
echo Collecting diagnostics into  !DIR! ...
echo.

echo --- ForexAI diagnostics !DATE! !TIME! --- > "!DIR!\docker-status.txt"
docker --version >> "!DIR!\docker-status.txt" 2>&1
docker compose version >> "!DIR!\docker-status.txt" 2>&1
docker info >> "!DIR!\docker-status.txt" 2>&1

docker compose ps -a > "!DIR!\container-status.txt" 2>&1

docker compose logs --tail 200 > "!DIR!\application-logs.txt" 2>&1

REM --- Redacted config check: names + SET/MISSING only, never values -------
> "!DIR!\configuration-check.txt" (
    echo Configuration check - values are never shown here.
    echo.
    if exist ".env" ( echo .env file: present ) else ( echo .env file: MISSING - run start.bat once )
    echo.
)
for %%V in (POSTGRES_PASSWORD JWT_KEY TWELVE_DATA_API_KEY OPENROUTER_API_KEY) do (
    findstr /b /c:"%%V=" ".env" >nul 2>&1 && (
        findstr /b /c:"%%V=replace-me" ".env" >nul 2>&1 && echo %%V: PLACEHOLDER >> "!DIR!\configuration-check.txt" || echo %%V: SET >> "!DIR!\configuration-check.txt"
    ) || echo %%V: MISSING >> "!DIR!\configuration-check.txt"
)
for %%V in (DASHBOARD_PORT API_PORT AI_PORT POSTGRES_PORT) do (
    for /f "tokens=2 delims==" %%b in ('findstr /b /c:"%%V=" ".env" 2^>nul') do echo %%V: %%b>> "!DIR!\configuration-check.txt"
)

echo.
echo [OK] Diagnostics collected in:  !DIR!
echo      Zip that folder and send it to support.
echo      No passwords or API keys are inside it.
echo.
pause
exit /b 0
