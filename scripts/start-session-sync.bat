@echo off
setlocal
title Antigravity Session Sync Watcher

:: Chuyen ve thu muc goc cua repo
cd /d "%~dp0\.."

:: Kiem tra Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Khong tim thay Python trong PATH!
    pause
    exit /b 1
)

:: Neu chua chay o che do thu nho (minimized), tu dong khoi chay lai o che do minimized
if "%1" neq "minimized" (
    start "Antigravity Session Sync" /min "%~f0" minimized
    exit /b 0
)

echo ============================================================
echo   Antigravity Central Session Sync Watcher
echo ============================================================
echo [*] Dang khoi chay Watcher che do Watch-All...
echo [*] Debounce: 60s ^| Hard Timeout: 180s
echo [*] Nhan Ctrl+C de dung an toan (Graceful Shutdown).
echo ------------------------------------------------------------

python scripts\auto_session_sync.py --watch-all --debounce-seconds 60 --max-timeout 180

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Watcher da dung voi ma loi %ERRORLEVEL%.
    pause
)
