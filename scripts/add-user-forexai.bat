@echo off
setlocal enabledelayedexpansion
REM ===========================================================================
REM ForexAI - create a dashboard account (Windows, no commands needed)
REM
REM Double-click this file, answer the three questions, and a new login for
REM the dashboard is created. The app must already be running (start it with
REM scripts\start-forexai.bat first).
REM ===========================================================================
cd /d "%~dp0.."

echo.
echo ============================================
echo   ForexAI - create a dashboard account
echo ============================================
echo.

REM --- Read the API port from .env (default 8080) ----------------------------
set "API_PORT=8080"
for /f "tokens=1,2 delims==" %%a in ('findstr /b /c:"API_PORT=" ".env" 2^>nul') do set "API_PORT=%%b"
if not defined API_PORT set "API_PORT=8080"

REM --- Is the app running? ----------------------------------------------------
curl.exe -fsS -m 5 "http://127.0.0.1:%API_PORT%/health" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The app does not appear to be running.
    echo.
    echo         1. Double-click  scripts\start-forexai.bat  and wait until
    echo            it says everything is healthy.
    echo         2. Then run this script again.
    echo.
    pause
    exit /b 1
)

REM --- Ask for the details ----------------------------------------------------
set "AU_EMAIL="
set /p "AU_EMAIL= Email address (used to sign in):    "
if not defined AU_EMAIL goto MISSING_INPUT

set "AU_NAME="
set /p "AU_NAME=  Display name (shown in the app):     "
if not defined AU_NAME set "AU_NAME=!AU_EMAIL!"

echo.
echo Password rules: at least 6 characters, with an uppercase letter, a
echo lowercase letter, a number and a symbol. Example: Summer-2026#
echo.
set "AU_PASS="
set /p "AU_PASS=  Password:                            "
set "AU_PASS2="
set /p "AU_PASS2= Password again:                     "

if not defined AU_PASS (
    echo.
    echo [ERROR] The password was empty. Run this script again.
    echo.
    pause
    exit /b 1
)

if not "!AU_PASS!"=="!AU_PASS2!" (
    echo.
    echo [ERROR] The two passwords do not match. Run this script again.
    echo.
    pause
    exit /b 1
)

echo.
echo Creating the account, please wait...

REM --- Call the API; PowerShell builds the JSON safely ------------------------
set "RESULT="
for /f "usebackq delims=" %%r in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$body = @{ email = $env:AU_EMAIL; displayName = $env:AU_NAME; password = $env:AU_PASS } | ConvertTo-Json; try { Invoke-RestMethod -Uri ('http://127.0.0.1:' + $env:API_PORT + '/api/Auth/register') -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 30 | Out-Null; 'OK' } catch { $resp = $_.Exception.Response; if ($resp) { $sr = New-Object IO.StreamReader($resp.GetResponseStream()); $txt = $sr.ReadToEnd(); $msg = ''; try { $msg = ($txt | ConvertFrom-Json).message } catch { }; if (-not $msg) { $msg = $txt }; if (-not $msg) { $msg = 'The server did not explain the problem.' }; 'ERR|' + $msg } else { 'ERR|' + $_.Exception.Message } }"`) do set "RESULT=%%r"

if "!RESULT!"=="OK" (
    echo.
    echo [OK] Account created.
    echo.
    echo      Sign-in email:  !AU_EMAIL!
    echo      They can now sign in at  http://localhost  with this
    echo      email and the password you just typed.
    echo.
    pause
    exit /b 0
)

if defined RESULT if not "!RESULT!"=="" (
    for /f "tokens=1,* delims=|" %%a in ("!RESULT!") do set "ERRMSG=%%b"
)

if defined ERRMSG (
    echo.
    echo [ERROR] The account was not created:
    echo.
    echo         !ERRMSG!
    echo.
    echo         Fix the problem and run this script again.
    echo.
    pause
    exit /b 1
)

echo.
echo [ERROR] Something went wrong and the server did not answer.
echo         Make sure the app is running (scripts\status-forexai.bat)
echo         and run this script again.
echo.
pause
exit /b 1

:MISSING_INPUT
echo.
echo [ERROR] No email address was entered. Run this script again.
echo.
pause
exit /b 1