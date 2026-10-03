@echo off
setlocal
chcp 65001 >nul
title Antigravity - Khoi phuc va dong bo phien lam viec
echo ========================================================
echo   Antigravity Harness Hub - 1-Click Resume & Setup
echo ========================================================
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\setup.ps1"

echo.
echo ========================================================
echo   HOAN TAT!
echo   Moi phien lam viec va cau hinh da duoc nap thanh cong.
echo   Ban co the mo Antigravity va tiep tuc cong viec ngay!
echo ========================================================
pause
