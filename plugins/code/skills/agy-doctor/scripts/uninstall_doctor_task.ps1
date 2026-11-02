# Antigravity Doctor - Windows Scheduled Task Uninstaller

$ErrorActionPreference = "SilentlyContinue"
$taskName = "Antigravity-Doctor-Watcher"

Write-Host "Dang go bo Scheduled Task: $taskName..." -ForegroundColor Yellow
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "Da go bo thanh cong Scheduled Task '$taskName'!" -ForegroundColor Green
