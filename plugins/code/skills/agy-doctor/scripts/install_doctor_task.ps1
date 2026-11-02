# Antigravity Doctor - Windows Scheduled Task Installer
# Tuân thủ: Chạy mỗi 2 giờ, Zero-Token, 100% Read-Only

$ErrorActionPreference = "Stop"

$taskName = "Antigravity-Doctor-Watcher"
$pythonPath = (Get-Command python.exe).Source
$scriptPath = Join-Path $PSScriptRoot "doctor_cron_runner.py"
$workspaceRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.Parent.FullName

Write-Host "Dang cai dat Windows Scheduled Task: $taskName..." -ForegroundColor Cyan
Write-Host "Python: $pythonPath"
Write-Host "Script: $scriptPath"

# Tạo Action
$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $workspaceRoot

# Tạo Trigger: Lặp lại mỗi 2 giờ bắt đầu từ thời điểm hiện tại
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 2)

# Cấu hình Settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

# Đăng ký Task
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Antigravity 2.0 Doctor Periodic Health Watcher (Zero-Token, Run every 2 hours)" `
    -Force | Out-Null

Write-Host "Da cai dat thanh cong Scheduled Task '$taskName'!" -ForegroundColor Green
Write-Host "Tan suat: Moi 2 gio tu dong chay va cap nhat bao cao vao Obsidian Vault." -ForegroundColor Green
