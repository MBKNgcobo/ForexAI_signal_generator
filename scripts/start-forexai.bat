@echo off
setlocal enabledelayedexpansion
REM ===========================================================================
REM ForexAI - start the Docker stack (Windows)
REM
REM   1. Checks that Docker is installed and running
REM   2. Checks that .env exists and has no leftover "replace-me" values
REM   3. Builds the images and starts the stack
REM   4. Waits until every service reports healthy
REM   5. Opens the dashboard in your browser
REM ===========================================================================
cd /d "%~dp0.."

echo.
echo ============================================
echo   ForexAI - starting the Docker stack
echo ============================================
echo.

REM --- Docker installed? ------------------------------------------------------
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed.
    echo         Install Docker Desktop first:
    echo         https://docs.docker.com/get-docker/
    echo.
    pause
    exit /b 1
)

REM --- Docker daemon running? -------------------------------------------------
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is installed but not running.
    echo         Start Docker Desktop, wait until it has finished starting,
    echo         then run this script again.
    echo.
    pause
    exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose v2 is not available.
    echo         Update Docker Desktop to a current version.
    echo.
    pause
    exit /b 1
)

REM --- .env present? ----------------------------------------------------------
if not exist ".env" (
    if not exist ".env.example" (
        echo [ERROR] Neither .env nor .env.example found in this folder.
        echo         This does not look like a complete ForexAI package.
        echo.
        pause
        exit /b 1
    )
    copy /y ".env.example" ".env" >nul
    echo [SETUP] Created .env from .env.example.
    echo.
    echo         Notepad will open. Set at least these four values:
    echo           POSTGRES_PASSWORD       any long random string
    echo           JWT_KEY                 any long random string
    echo           TWELVE_DATA_API_KEY     key from https://twelvedata.com
    echo           OPENROUTER_API_KEY      key from https://openrouter.ai
    echo.
    echo         Save the file, close Notepad, run this script again.
    echo.
    notepad ".env"
    pause
    exit /b 1
)

REM --- Leftover placeholders? -------------------------------------------------
set "PLACEHOLDERS="
findstr /b /c:"POSTGRES_PASSWORD=replace-me" ".env" >nul 2>&1 && set "PLACEHOLDERS=!PLACEHOLDERS! POSTGRES_PASSWORD"
findstr /b /c:"JWT_KEY=replace-me" ".env" >nul 2>&1 && set "PLACEHOLDERS=!PLACEHOLDERS! JWT_KEY"
findstr /b /c:"TWELVE_DATA_API_KEY=replace-me" ".env" >nul 2>&1 && set "PLACEHOLDERS=!PLACEHOLDERS! TWELVE_DATA_API_KEY"
findstr /b /c:"OPENROUTER_API_KEY=replace-me" ".env" >nul 2>&1 && set "PLACEHOLDERS=!PLACEHOLDERS! OPENROUTER_API_KEY"

if defined PLACEHOLDERS (
    echo [ERROR] These values in .env are still placeholders:%PLACEHOLDERS%
    echo         Edit .env, replace them with real values, save it,
    echo         then run this script again.
    echo.
    notepad ".env"
    pause
    exit /b 1
)

REM --- Read the dashboard port (default 80) -----------------------------------
set "DASH_PORT=80"
for /f "tokens=1,2 delims==" %%a in ('findstr /b /c:"DASHBOARD_PORT=" ".env" 2^>nul') do set "DASH_PORT=%%b"
if not defined DASH_PORT set "DASH_PORT=80"
docker ps --filter "name=forexai-dashboard" --format "{{.Names}}" 2>nul | findstr /c:"forexai-dashboard" >nul
if errorlevel 1 (
    netstat -ano | findstr "LISTENING" | findstr /c:":%DASH_PORT% " >nul 2>&1
    if not errorlevel 1 (
        echo [WARNING] Port %DASH_PORT% is already in use by another program.
        echo           If the next step fails, edit .env and set
        echo           DASHBOARD_PORT to a free port, for example 8080.
        echo.
    )
)

REM --- Build and start --------------------------------------------------------
echo Building images and starting the stack.
echo First run can take several minutes - please wait.
echo.
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo [ERROR] docker compose up failed - see the output above.
    echo         Most common causes:
    echo           - a port is already in use: change DASHBOARD_PORT,
    echo             API_PORT, AI_PORT or POSTGRES_PORT in .env
    echo           - a wrong value in .env
    echo.
    pause
    exit /b 1
)

REM --- Wait until all four services are healthy -------------------------------
echo Waiting for the services to become healthy...
set /a WAITED=0
:WAIT_LOOP
REM timeout needs a real console; fall back to a ~2s ping delay when stdin
REM is redirected (CI, piped input) so the loop cannot spin and time out early.
timeout /t 2 /nobreak >nul 2>&1 || ping -n 3 127.0.0.1 >nul
set /a WAITED+=2
set "ALL_HEALTHY=1"
docker inspect -f "{{.State.Health.Status}}" forexai-postgres 2>nul | findstr /c:"healthy" >nul || set "ALL_HEALTHY=0"
docker inspect -f "{{.State.Health.Status}}" forexai-python-ai 2>nul | findstr /c:"healthy" >nul || set "ALL_HEALTHY=0"
docker inspect -f "{{.State.Health.Status}}" forexai-csharp-api 2>nul | findstr /c:"healthy" >nul || set "ALL_HEALTHY=0"
docker inspect -f "{{.State.Health.Status}}" forexai-dashboard 2>nul | findstr /c:"healthy" >nul || set "ALL_HEALTHY=0"
if "!ALL_HEALTHY!"=="1" goto ALL_UP
if %WAITED% geq 180 goto TIMEOUT
goto WAIT_LOOP

:ALL_UP
echo.
echo [OK] All services are healthy.
echo.
docker compose ps
echo.
echo   Open the dashboard at:  http://localhost:%DASH_PORT%
echo.
start "" "http://localhost:%DASH_PORT%"
pause
exit /b 0

:TIMEOUT
echo.
echo [WARNING] Services did not all become healthy within %WAITED% seconds.
echo.
docker compose ps
echo.
echo   See recent logs with:   docker compose logs --tail 50
echo   Or run:                 scripts\status-forexai.bat
echo.
pause
exit /b 1