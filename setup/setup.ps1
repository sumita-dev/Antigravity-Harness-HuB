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

Write-Host "[4/4] Cài đặt các kỹ năng nhánh Marketing vào thư mục global..." -ForegroundColor Yellow
$skillsTargetDir = Join-Path $targetDir "skills"
if (-not (Test-Path $skillsTargetDir)) {
    New-Item -ItemType Directory -Force -Path $skillsTargetDir | Out-Null
}

$marketingSkills = @(
    "boc-phot-storytelling",
    "check-youtube-policy",
    "yt-competitor-analyzer",
    "alex-hormozi-offer-builder",
    "alex-hormozi-money-models",
    "kahneman-creative-ads",
    "traffic-secrets-playbook",
    "cong-thuc-viet-content-by-noti-v4",
    "viet-content-seo-geo-v5",
    "meta-ads-analyzer-mod-by-noti",
    "fb-admin"
)

$repoSkillsDir = Join-Path $PSScriptRoot "..\skills"
foreach ($s in $marketingSkills) {
    $srcSkill = Join-Path $repoSkillsDir $s
    $dstSkill = Join-Path $skillsTargetDir $s
    if (Test-Path $srcSkill) {
        Copy-Item -Path $srcSkill -Destination $dstSkill -Recurse -Force
        Write-Host "  + Đã nạp skill: $s" -ForegroundColor DarkGreen
    }
}

Write-Host "
Đã cài đặt cấu hình và kỹ năng Marketing thành công!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
