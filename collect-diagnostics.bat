@echo off
REM ForexAI - double-click launcher. Forwards to scripts\collect-diagnostics.bat
cd /d "%~dp0"
call "scripts\collect-diagnostics.bat"
