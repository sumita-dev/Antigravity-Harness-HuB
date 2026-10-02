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
    Write-Host "[1/4] Tạo thư mục đích: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
} else {
    Write-Host "[1/4] Thư mục đích đã tồn tại: $targetDir" -ForegroundColor Green
}

if (Test-Path $targetFile) {
    $backupFile = Join-Path $targetDir "config.json.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "[2/4] Sao lưu file config cũ sang: $backupFile" -ForegroundColor Yellow
    Copy-Item -Path $targetFile -Destination $backupFile -Force
} else {
    Write-Host "[2/4] Chưa có file config cũ, tiến hành tạo mới" -ForegroundColor Green
}

Write-Host "[3/4] Sao chép file cấu hình (cài đè)..." -ForegroundColor Yellow
Copy-Item -Path $sourceFile -Destination $targetFile -Force

Write-Host "[4/4] Cài đặt toàn bộ kỹ năng, quy chuẩn Maker-Checker, agents và rubrics vào global..." -ForegroundColor Yellow
$skillsTargetDir = Join-Path $targetDir "skills"
if (-not (Test-Path $skillsTargetDir)) {
    New-Item -ItemType Directory -Force -Path $skillsTargetDir | Out-Null
}

$repoRoot = Join-Path $PSScriptRoot ".."
$repoSkillsDir = Join-Path $repoRoot "skills"

Get-ChildItem -Path $repoSkillsDir -Directory | ForEach-Object {
    $srcSkill = $_.FullName
    $dstSkill = Join-Path $skillsTargetDir $_.Name
    Copy-Item -Path $srcSkill -Destination $dstSkill -Recurse -Force
    Write-Host "  + Đã nạp skill: $($_.Name)" -ForegroundColor DarkGreen
}

# Sao chép AGENTS.md, GEMINI.md, agents và rubrics vào global config
Copy-Item -Path (Join-Path $repoRoot "AGENTS.md") -Destination (Join-Path $targetDir "AGENTS.md") -Force
Copy-Item -Path (Join-Path $repoRoot "GEMINI.md") -Destination (Join-Path $targetDir "GEMINI.md") -Force
Copy-Item -Path (Join-Path $repoRoot "agents") -Destination (Join-Path $targetDir "agents") -Recurse -Force
Copy-Item -Path (Join-Path $repoRoot "rubrics") -Destination (Join-Path $targetDir "rubrics") -Recurse -Force
Write-Host "  + Đã đồng bộ quy chuẩn Maker-Checker, AGENTS.md, GEMINI.md, agents và rubrics vào global config!" -ForegroundColor DarkGreen

Write-Host "`nĐã cài đặt cấu hình và đồng bộ toàn bộ hệ thống Antigravity 2.0 thành công!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan

