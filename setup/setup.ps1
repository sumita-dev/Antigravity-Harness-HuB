# Antigravity Harness Hub - Cai dat cau hinh moi truong moi
# Chay lai nhieu lan duoc (idempotent): khong tao tang long, khong nhan ban thu muc.
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
$repoRoot = Join-Path $PSScriptRoot ".."

if (-not (Test-Path $targetDir)) {
    Write-Host "[1/6] Tao thu muc dich: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
} else {
    Write-Host "[1/6] Thu muc dich da ton tai: $targetDir" -ForegroundColor Green
}

if (Test-Path $targetFile) {
    $backupFile = Join-Path $targetDir "config.json.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "[2/6] Sao luu file config cu sang: $backupFile" -ForegroundColor Yellow
    Copy-Item -Path $targetFile -Destination $backupFile -Force
} else {
    Write-Host "[2/6] Chua co file config cu, tien hanh tao moi" -ForegroundColor Green
}

Write-Host "[3/6] Sao chep file cau hinh (cai de)..." -ForegroundColor Yellow
Copy-Item -Path $sourceFile -Destination $targetFile -Force

# --- [4/6] Plugins: xoa dich truoc khi copy de TRANH tao tang long plugins/<ten>/<ten>
Write-Host "[4/6] Cai dat plugins (code, marketing) vao global..." -ForegroundColor Yellow
$pluginsTargetDir = Join-Path $targetDir "plugins"
if (-not (Test-Path $pluginsTargetDir)) {
    New-Item -ItemType Directory -Force -Path $pluginsTargetDir | Out-Null
}
$repoPluginsDir = Join-Path $repoRoot "plugins"
if (Test-Path $repoPluginsDir) {
    Get-ChildItem -Path $repoPluginsDir -Directory | ForEach-Object {
        $srcPlugin = $_.FullName
        $dstPlugin = Join-Path $pluginsTargetDir $_.Name
        if (Test-Path $dstPlugin) {
            Remove-Item -Path $dstPlugin -Recurse -Force
        }
        Copy-Item -Path $srcPlugin -Destination $dstPlugin -Recurse -Force
        Write-Host "  + Da nap plugin: $($_.Name)" -ForegroundColor DarkGreen
    }
}

# --- [5/6] Loi harness (de CLI chay duoc ngay tai global config) + quy chuan
Write-Host "[5/6] Dong bo harness, configs, agents, rubrics, scripts, hooks..." -ForegroundColor Yellow
$copyMap = @{
    "harness"          = "harness"
    "configs"          = "configs"
    "agents"           = "agents"
    "rubrics"          = "rubrics"
    "scripts"          = "scripts"
    ".agent"           = ".agent"
    ".agents"          = ".agents"
}
foreach ($pair in $copyMap.GetEnumerator()) {
    $src = Join-Path $repoRoot $pair.Key
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $targetDir $pair.Value
    if (Test-Path $dst) { Remove-Item -Path $dst -Recurse -Force }
    Copy-Item -Path $src -Destination $dst -Recurse -Force
    Write-Host "  + Da dong bo: $($pair.Key)" -ForegroundColor DarkGreen
}
foreach ($f in @("AGENTS.md", "GEMINI.md", "requirements.txt", ".env.example")) {
    $src = Join-Path $repoRoot $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $targetDir $f) -Force
        Write-Host "  + Da dong bo: $f" -ForegroundColor DarkGreen
    }
}
$hooksSrc = Join-Path $repoRoot ".agent\hooks.json"
if (Test-Path $hooksSrc) {
    Copy-Item -Path $hooksSrc -Destination (Join-Path $targetDir "hooks.json") -Force
    Write-Host "  + Da dong bo: hooks.json (global)" -ForegroundColor DarkGreen
}

# --- Kiem tra hau kiem: khong duoc co thu muc skill long chinh no
$nested = Get-ChildItem -Path $pluginsTargetDir -Directory -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq $_.Parent.Name -and $_.Parent.Parent.Name -eq "skills" }
if ($nested) {
    Write-Warning "Phat hien thu muc long (can kiem tra): $($nested.FullName -join ', ')"
} else {
    Write-Host "  + Kiem tra: khong co thu muc skill long chinh no." -ForegroundColor Green
}

# --- [6/6] Tu dong nap phien lam viec neu co .sessions
$sessionsDir = Join-Path $repoRoot ".sessions"
if (Test-Path $sessionsDir) {
    Write-Host "[6/6] Phat hien .sessions, dang nap phien lam viec (Portable Session Sync)..." -ForegroundColor Yellow
    $sessionScript = Join-Path $repoRoot "scripts\session_manager.py"
    if (Test-Path $sessionScript) {
        python $sessionScript --action import --repo-dir $repoRoot
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  + Da khoi phuc phien lam viec thanh cong!" -ForegroundColor DarkGreen
        } else {
            Write-Warning "Co loi khi nap phien lam viec tu .sessions"
        }
    }
} else {
    Write-Host "[6/6] Khong co .sessions, bo qua buoc nap phien." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Da cai dat cau hinh va dong bo he thong Antigravity 2.0 thanh cong!" -ForegroundColor Green
Write-Host "Chay lai script nay bat cu luc nao de dong bo lai (an toan, khong nhan ban)." -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
