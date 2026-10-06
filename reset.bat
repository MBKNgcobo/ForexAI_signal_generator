@echo off
REM ForexAI - double-click launcher. Forwards to scripts\reset-forexai.bat
REM WARNING: reset deletes ALL data. The script asks for confirmation.
cd /d "%~dp0"
call "scripts\reset-forexai.bat"
