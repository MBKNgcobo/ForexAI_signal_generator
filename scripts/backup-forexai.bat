@echo off
cd /d "%~dp0.."

if not exist "backups" mkdir "backups"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%i"
set "FILE=backups\forexai-%TS%.sql"

echo.
echo Creating a database backup (schema + data)...
echo Output: %FILE%
echo.

REM pg_dump runs inside the postgres container and uses the container's
REM POSTGRES_USER / POSTGRES_DB values, so it always matches .env.
docker exec forexai-postgres sh -c "pg_dump -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" --clean --if-exists" > "%FILE%"
if errorlevel 1 (
    echo.
    echo [ERROR] Backup failed - see the message above.
    if exist "%FILE%" del "%FILE%" 2>nul
    pause
    exit /b 1
)

echo.
echo [OK] Backup written to %FILE%
echo.
echo      Restore it later with:
echo        docker exec -i forexai-postgres psql -U postgres -d forexai ^< %FILE%
echo.
pause
exit /b 0