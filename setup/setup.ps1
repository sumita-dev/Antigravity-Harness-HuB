# Antigravity Harness Hub - Cai dat cau hinh moi truong moi
$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " Antigravity Harness Hub - Setup Configuration   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$sourceFile = Join-Path $PSScriptRoot "config.json"
if (-not (Test-Path $sourceFile)) {
    Write-Error "Khong tim thay file nguon: $sourceFile"
    exit 1
}

$targetDir = Join-Path $env:USERPROFILE ".gemini\config"
$targetFile = Join-Path $targetDir "config.json"

if (-not (Test-Path $targetDir)) {
    Write-Host "[1/4] Tao thu muc dich: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
} else {
    Write-Host "[1/4] Thu muc dich da ton tai: $targetDir" -ForegroundColor Green
}

if (Test-Path $targetFile) {
    $backupFile = Join-Path $targetDir "config.json.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "[2/4] Sao luu file config cu sang: $backupFile" -ForegroundColor Yellow
    Copy-Item -Path $targetFile -Destination $backupFile -Force
} else {
    Write-Host "[2/4] Chua co file config cu, tien hanh tao moi" -ForegroundColor Green
}

Write-Host "[3/4] Sao chep file cau hinh (cai de)..." -ForegroundColor Yellow
Copy-Item -Path $sourceFile -Destination $targetFile -Force

Write-Host "[4/4] Cai dat toan bo ky nang, quy chuan Maker-Checker, agents va rubrics vao global..." -ForegroundColor Yellow
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
    Write-Host "  + Da nap skill: $($_.Name)" -ForegroundColor DarkGreen
}

# Sao chep AGENTS.md, GEMINI.md, agents va rubrics vao global config
Copy-Item -Path (Join-Path $repoRoot "AGENTS.md") -Destination (Join-Path $targetDir "AGENTS.md") -Force
Copy-Item -Path (Join-Path $repoRoot "GEMINI.md") -Destination (Join-Path $targetDir "GEMINI.md") -Force
Copy-Item -Path (Join-Path $repoRoot "agents\*") -Destination (Join-Path $targetDir "agents") -Recurse -Force
Copy-Item -Path (Join-Path $repoRoot "rubrics\*") -Destination (Join-Path $targetDir "rubrics") -Recurse -Force
Write-Host "  + Da dong bo quy chuan Maker-Checker, AGENTS.md, GEMINI.md, agents va rubrics vao global config!" -ForegroundColor DarkGreen

Write-Host ""
Write-Host "Da cai dat cau hinh va dong bo toan bo he thong Antigravity 2.0 thanh cong!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
