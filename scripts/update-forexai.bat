@echo off
cd /d "%~dp0.."

echo.
echo ============================================
echo   ForexAI - update (code + images)
echo ============================================
echo.
echo Database data is preserved. The stack will be rebuilt and restarted.
echo.

REM --- Pull new code when this is a git checkout (skip for ZIP installs) -----
if exist ".git" (
    where git >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Git is not installed - skipping the code update.
    ) else (
        echo Pulling the latest code...
        git pull --ff-only
        if errorlevel 1 (
            echo [WARNING] git pull failed - local changes or a network issue.
            echo           Continuing with the files that are already here.
        )
        echo.
    )
) else (
    echo [INFO] No .git folder found - installed from a ZIP.
    echo        Unpack the new ZIP over this folder to update the code.
    echo.
)

REM --- Rebuild images (pull fresh base images) and restart --------------------
echo Rebuilding images and restarting the stack...
docker compose build --pull
if errorlevel 1 (
    echo.
    echo [ERROR] Image build failed - see the output above.
    echo         Your current stack keeps running untouched.
    echo.
    pause
    exit /b 1
)

docker compose up -d --remove-orphans
if errorlevel 1 (
    echo.
    echo [ERROR] docker compose up failed - see the output above.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Update finished. Verify with:  scripts\status-forexai.bat
echo      Roll back: restore your backups\*.sql from before the update and
echo      unpack the previous ZIP over this folder, then run start.bat.
echo      Keep your .env file - it is never overwritten by an update.
echo.
pause
exit /b 0