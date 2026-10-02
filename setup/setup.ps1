# Antigravity Harness Hub - Cài đặt cấu hình môi trường mới
$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " Antigravity Harness Hub - Setup Configuration   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$sourceFile = Join-Path $PSScriptRoot "config.json"
if (-not (Test-Path $sourceFile)) {
    Write-Error "Không tìm thấy file nguồn: $sourceFile"
    exit 1
}

$targetDir = Join-Path $env:USERPROFILE ".gemini\config"
$targetFile = Join-Path $targetDir "config.json"

if (-not (Test-Path $targetDir)) {
    Write-Host "[1/3] Tạo thư mục đích: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
} else {
    Write-Host "[1/3] Thư mục đích đã tồn tại: $targetDir" -ForegroundColor Green
}

if (Test-Path $targetFile) {
    $backupFile = Join-Path $targetDir "config.json.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "[2/3] Sao lưu file config cũ sang: $backupFile" -ForegroundColor Yellow
    Copy-Item -Path $targetFile -Destination $backupFile -Force
} else {
    Write-Host "[2/3] Chưa có file config cũ, tiến hành tạo mới" -ForegroundColor Green
}

Write-Host "[3/3] Sao chép file cấu hình (cài đè)..." -ForegroundColor Yellow
Copy-Item -Path $sourceFile -Destination $targetFile -Force

Write-Host "
Đã cài đặt cấu hình thành công vào: $targetFile" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan

