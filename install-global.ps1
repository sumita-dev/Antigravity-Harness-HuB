<#
.SYNOPSIS
    Cài đặt Antigravity Harness Hub thành cấu hình Toàn cục (Global) cho Antigravity.
.DESCRIPTION
    Script này sao chép toàn bộ bộ luật (rules), các plugin (skills), vai trò (agents),
    rubrics và scripts từ Antigravity-Harness-Hub vào thư mục cấu hình toàn cục
    của người dùng (~/.gemini/config/), giúp mọi dự án trên Antigravity tự động áp dụng
    khung điều phối Maker-Checker và 36 kỹ năng.
.EXAMPLE
    pwsh -File .\install-global.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$GlobalConfigDir = Join-Path $HOME ".gemini\config"
$GlobalRulesDir = Join-Path $GlobalConfigDir "rules"
$GlobalPluginsDir = Join-Path $GlobalConfigDir "plugins"
$GlobalAgentsDir = Join-Path $GlobalConfigDir "agents"
$GlobalRubricsDir = Join-Path $GlobalConfigDir "rubrics"
$GlobalScriptsDir = Join-Path $GlobalConfigDir "scripts"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Antigravity Harness Hub - Cài Đặt Toàn Cục (Global)    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Thư mục nguồn (Repo): $RepoRoot" -ForegroundColor Gray
Write-Host "Thư mục đích (Global): $GlobalConfigDir" -ForegroundColor Gray
Write-Host ""

# 1. Đảm bảo các thư mục đích tồn tại
$DirsToCreate = @($GlobalConfigDir, $GlobalRulesDir, $GlobalPluginsDir, $GlobalAgentsDir, $GlobalRubricsDir, $GlobalScriptsDir)
foreach ($dir in $DirsToCreate) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "[+] Tạo thư mục: $dir" -ForegroundColor Green
    }
}

# 2. Cài đặt Quy Chuẩn Toàn Cục (Global Rules)
$SourceGemini = Join-Path $RepoRoot "GEMINI.md"
$DestRule = Join-Path $GlobalRulesDir "harness_orchestrator.md"
if (Test-Path $SourceGemini) {
    Copy-Item -Path $SourceGemini -Destination $DestRule -Force
    Write-Host "[OK] Đã cài đặt Rule Toàn cục: $DestRule" -ForegroundColor Green
} else {
    Write-Warning "Không tìm thấy file GEMINI.md tại $SourceGemini"
}

# 3. Đồng bộ Plugins & Skills
$SourcePlugins = Join-Path $RepoRoot "plugins"
if (Test-Path $SourcePlugins) {
    Write-Host "[...] Đang đồng bộ Plugins & Skills vào $GlobalPluginsDir..." -ForegroundColor Yellow
    robocopy $SourcePlugins $GlobalPluginsDir /E /XO /NP /NFL /NDL | Out-Null
    Write-Host "[OK] Đồng bộ Plugins & Skills thành công!" -ForegroundColor Green
}

# 4. Đồng bộ Agents, Rubrics & Scripts
$SyncPairs = @(
    @{ Src = (Join-Path $RepoRoot "agents");  Dest = $GlobalAgentsDir;  Label = "Agents" },
    @{ Src = (Join-Path $RepoRoot "rubrics"); Dest = $GlobalRubricsDir; Label = "Rubrics" },
    @{ Src = (Join-Path $RepoRoot "scripts"); Dest = $GlobalScriptsDir; Label = "Scripts" }
)

foreach ($pair in $SyncPairs) {
    if (Test-Path $pair.Src) {
        Write-Host "[...] Đang đồng bộ $($pair.Label)..." -ForegroundColor Yellow
        robocopy $pair.Src $pair.Dest /E /XO /NP /NFL /NDL | Out-Null
        Write-Host "[OK] Đồng bộ $($pair.Label) thành công!" -ForegroundColor Green
    }
}

# 5. Đồng bộ cấu hình harness_config.json
$SourceConfig = Join-Path $RepoRoot "configs\harness_config.json"
$DestConfig = Join-Path $GlobalConfigDir "harness_config.json"
if (Test-Path $SourceConfig) {
    Copy-Item -Path $SourceConfig -Destination $DestConfig -Force
    Write-Host "[OK] Đã cài đặt cấu hình định tuyến: $DestConfig" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " HOÀN TẤT! Antigravity giờ đây sẽ tự động nạp Harness Hub " -ForegroundColor Cyan
Write-Host " cho MỌI DỰ ÁN mở trên máy tính này.                      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
