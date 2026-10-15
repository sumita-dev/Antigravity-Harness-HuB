# bootstrap_workspace.ps1: Tạo launcher 1 chạm care.cmd và care.ps1 tại thư mục làm việc
param(
    [string]$TargetDir = (Get-Location).Path
)

$skillScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$execScript = Join-Path $skillScriptsDir "execute_selected.ps1"

# 1. Tạo care.cmd
$cmdContent = @"
@echo off
chcp 65001 >nul
echo [Antigravity PC Care] Dang khoi dong Dong co Bao Duong & Toi Uu May Tinh...
pwsh -NoProfile -ExecutionPolicy Bypass -File "$execScript" -WorkspaceRoot "%~dp0" %*
"@
Set-Content -Path (Join-Path $TargetDir "care.cmd") -Value $cmdContent -Encoding UTF8

# 2. Tạo care.ps1
$psContent = @"
# Antigravity PC Care Launcher for PowerShell Terminal
param(
    [ValidateSet('FullCare', 'AppSwitch', 'DiskClean', 'DBVacuum', 'Custom')]
    [string]`$Preset = 'FullCare',
    [string[]]`$SelectedTasks,
    [switch]`$TuneAltTab,
    [switch]`$DryRun,
    [string]`$UserIssue = '',
    [switch]`$Help
)

if (`$Help) {
    Write-Host "Cách sử dụng Antigravity PC Care:" -ForegroundColor Cyan
    Write-Host "  .\care                              : Thi công bảo dưỡng toàn diện (FullCare)" -ForegroundColor Green
    Write-Host "  .\care -Preset AppSwitch            : Tối ưu chuyển đổi ứng dụng Alt+Tab & RAM" -ForegroundColor Green
    Write-Host "  .\care -Preset DiskClean            : Dọn dẹp ổ C: và tệp tạm" -ForegroundColor Green
    Write-Host "  .\care -Preset DBVacuum             : Tối ưu 243 cơ sở dữ liệu SQLite" -ForegroundColor Green
    Write-Host "  .\care -DryRun                      : Chạy kiểm thử an toàn, không thay đổi hệ thống" -ForegroundColor Yellow
    return
}

`$params = @{
    WorkspaceRoot = `$PSScriptRoot
    Preset = `$Preset
}
if (`$SelectedTasks) { `$params['SelectedTasks'] = `$SelectedTasks }
if (`$TuneAltTab) { `$params['TuneAltTab'] = `$true }
if (`$DryRun) { `$params['DryRun'] = `$true }
if (`$UserIssue) { `$params['UserIssue'] = `$UserIssue }

& "$execScript" @params
"@
Set-Content -Path (Join-Path $TargetDir "care.ps1") -Value $psContent -Encoding UTF8

Write-Host "Đã khởi tạo thành công care.cmd và care.ps1 tại: $TargetDir" -ForegroundColor Green
