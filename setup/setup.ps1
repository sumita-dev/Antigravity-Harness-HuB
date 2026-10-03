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
    Write-Host "[1/5] Tao thu muc dich: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
} else {
    Write-Host "[1/5] Thu muc dich da ton tai: $targetDir" -ForegroundColor Green
}

if (Test-Path $targetFile) {
    $backupFile = Join-Path $targetDir "config.json.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "[2/5] Sao luu file config cu sang: $backupFile" -ForegroundColor Yellow
    Copy-Item -Path $targetFile -Destination $backupFile -Force
} else {
    Write-Host "[2/5] Chua co file config cu, tien hanh tao moi" -ForegroundColor Green
}

Write-Host "[3/5] Sao chep file cau hinh (cai de)..." -ForegroundColor Yellow
Copy-Item -Path $sourceFile -Destination $targetFile -Force

Write-Host "[4/5] Cai dat toan bo plugins (code, marketing), quy chuan Maker-Checker, agents va rubrics vao global..." -ForegroundColor Yellow
$pluginsTargetDir = Join-Path $targetDir "plugins"
if (-not (Test-Path $pluginsTargetDir)) {
    New-Item -ItemType Directory -Force -Path $pluginsTargetDir | Out-Null
}

$repoRoot = Join-Path $PSScriptRoot ".."
$repoPluginsDir = Join-Path $repoRoot "plugins"

if (Test-Path $repoPluginsDir) {
    Get-ChildItem -Path $repoPluginsDir -Directory | ForEach-Object {
        $srcPlugin = $_.FullName
        $dstPlugin = Join-Path $pluginsTargetDir $_.Name
        Copy-Item -Path $srcPlugin -Destination $dstPlugin -Recurse -Force
        Write-Host "  + Da nap plugin: $($_.Name)" -ForegroundColor DarkGreen
    }
}

# Sao chep AGENTS.md, GEMINI.md, agents, rubrics va scripts vao global config
Copy-Item -Path (Join-Path $repoRoot "AGENTS.md") -Destination (Join-Path $targetDir "AGENTS.md") -Force
Copy-Item -Path (Join-Path $repoRoot "GEMINI.md") -Destination (Join-Path $targetDir "GEMINI.md") -Force
Copy-Item -Path (Join-Path $repoRoot "agents\*") -Destination (Join-Path $targetDir "agents") -Recurse -Force
Copy-Item -Path (Join-Path $repoRoot "rubrics\*") -Destination (Join-Path $targetDir "rubrics") -Recurse -Force
$scriptsTargetDir = Join-Path $targetDir "scripts"
if (-not (Test-Path $scriptsTargetDir)) {
    New-Item -ItemType Directory -Force -Path $scriptsTargetDir | Out-Null
}
Copy-Item -Path (Join-Path $repoRoot "scripts\*") -Destination $scriptsTargetDir -Recurse -Force
Write-Host "  + Da dong bo quy chuan Maker-Checker, AGENTS.md, GEMINI.md, agents, rubrics va scripts vao global config!" -ForegroundColor DarkGreen

# 5. Tu dong nap phien lam viec neu co thu muc .sessions (Zero-Friction Portable Session Sync)
$sessionsDir = Join-Path $repoRoot ".sessions"
if (Test-Path $sessionsDir) {
    Write-Host "[5/5] Phat hien thu muc .sessions, dang tu dong nap phien lam viec (Portable Session Sync)..." -ForegroundColor Yellow
    $sessionScript = Join-Path $repoRoot "scripts\session_manager.py"
    if (Test-Path $sessionScript) {
        python $sessionScript --action import --repo-dir $repoRoot
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  + Da khoi phuc va nap cac phien lam viec thanh cong vao Antigravity!" -ForegroundColor DarkGreen
        } else {
            Write-Warning "Co loi khi nap phien lam viec tu .sessions"
        }
    }
} else {
    Write-Host "[5/5] Khong phat hien thu muc .sessions, bo qua buoc nap phien." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Da cai dat cau hinh va dong bo toan bo he thong Antigravity 2.0 thanh cong!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
