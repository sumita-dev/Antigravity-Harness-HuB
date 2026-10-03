@echo off
setlocal
chcp 65001 >nul
title Antigravity - Sao luu phien lam viec
echo ========================================================
echo   Antigravity Harness Hub - 1-Click Save Sessions
echo ========================================================
cd /d "%~dp0"

python "%~dp0scripts\session_manager.py" --action export --repo-dir "%~dp0."

echo.
echo ========================================================
echo   HOAN TAT!
echo   Tat ca phien lam viec da duoc sao luu vao thu muc .sessions/
echo   Ban co the copy thu muc du an sang may khac va chay resume.bat!
echo ========================================================
pause
