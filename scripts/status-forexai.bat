@echo off
cd /d "%~dp0.."

echo.
echo ============================================
echo   ForexAI - stack status
echo ============================================
echo.

docker compose ps
echo.

REM --- Health endpoints (ports read from .env, defaults shown) ---------------
set "DASH_PORT=80"
for /f "tokens=1,2 delims==" %%a in ('findstr /b /c:"DASHBOARD_PORT=" ".env" 2^>nul') do set "DASH_PORT=%%b"
if not defined DASH_PORT set "DASH_PORT=80"
set "API_PORT=8080"
for /f "tokens=1,2 delims==" %%a in ('findstr /b /c:"API_PORT=" ".env" 2^>nul') do set "API_PORT=%%b"
if not defined API_PORT set "API_PORT=8080"
set "AI_PORT=8001"
for /f "tokens=1,2 delims==" %%a in ('findstr /b /c:"AI_PORT=" ".env" 2^>nul') do set "AI_PORT=%%b"
if not defined AI_PORT set "AI_PORT=8001"

where curl >nul 2>&1
if errorlevel 1 (
    echo [INFO] curl not found - skipping endpoint checks.
    goto ENDPOINT_DONE
)

echo Health endpoints:
curl -fsS "http://localhost:%DASH_PORT%/health" >nul 2>&1 && echo   [OK]   dashboard  http://localhost:%DASH_PORT%/health || echo   [FAIL] dashboard  http://localhost:%DASH_PORT%/health
curl -fsS "http://127.0.0.1:%API_PORT%/health" >nul 2>&1 && echo   [OK]   API        http://127.0.0.1:%API_PORT%/health || echo   [FAIL] API        http://127.0.0.1:%API_PORT%/health
curl -fsS "http://127.0.0.1:%API_PORT%/health/ready" >nul 2>&1 && echo   [OK]   API ready  http://127.0.0.1:%API_PORT%/health/ready || echo   [FAIL] API ready  http://127.0.0.1:%API_PORT%/health/ready
curl -fsS "http://127.0.0.1:%AI_PORT%/health" >nul 2>&1 && echo   [OK]   AI         http://127.0.0.1:%AI_PORT%/health || echo   [FAIL] AI         http://127.0.0.1:%AI_PORT%/health
curl -fsS "http://127.0.0.1:%AI_PORT%/ready" >nul 2>&1 && echo   [OK]   AI ready   http://127.0.0.1:%AI_PORT%/ready || echo   [FAIL] AI ready   http://127.0.0.1:%AI_PORT%/ready

:ENDPOINT_DONE
echo.
echo Stopped containers - forexai-db-migrate showing Exited 0 is NORMAL:
echo it is the one-shot migration job. Any other non-zero exit is not:
docker compose ps -a --filter "status=exited"
echo.
echo Full logs:  docker compose logs --tail 100
echo.
pause
exit /b 0