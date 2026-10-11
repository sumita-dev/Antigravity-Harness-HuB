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

# 2. Xóa bỏ file rule rời rạc cũ nếu có (tránh trùng lặp)
$LegacyLooseRule = Join-Path $GlobalRulesDir "harness_orchestrator.md"
if (Test-Path $LegacyLooseRule) {
    Remove-Item -Path $LegacyLooseRule -Force -ErrorAction SilentlyContinue
}
$SourceGemini = Join-Path $RepoRoot "GEMINI.md"

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

# 6. Cài đặt Rule vào Global Plugin Code (Đảm bảo Antigravity nạp rule qua Plugin engine)
$PluginCodeRulesDir = Join-Path $GlobalPluginsDir "code\rules"
if (-not (Test-Path $PluginCodeRulesDir)) {
    New-Item -ItemType Directory -Path $PluginCodeRulesDir -Force | Out-Null
}
Copy-Item -Path $SourceGemini -Destination (Join-Path $PluginCodeRulesDir "AGENTS.md") -Force
Write-Host "[OK] Đã cài đặt Rule vào Global Plugin Code: $PluginCodeRulesDir\AGENTS.md" -ForegroundColor Green

# 7. Tự động nạp GEMINI.md vào toàn bộ Projects hiện có trên Antigravity
$ProjectsJsonDir = Join-Path $GlobalConfigDir "projects"
if (Test-Path $ProjectsJsonDir) {
    Write-Host "[...] Đang quét và đồng bộ GEMINI.md vào các dự án hiện có..." -ForegroundColor Yellow
    Get-ChildItem -Path (Join-Path $ProjectsJsonDir "*.json") | ForEach-Object {
        try {
            $proj = Get-Content $_.FullName -Raw | ConvertFrom-Json
            $uri = $null
            if ($proj.projectResources.resources.Count -gt 0) {
                $r = $proj.projectResources.resources[0]
                if ($r.folderUri) { $uri = $r.folderUri }
                elseif ($r.gitFolder.folderUri) { $uri = $r.gitFolder.folderUri }
            }
            if ($uri) {
                $localPath = [System.Uri]::UnescapeDataString($uri.Replace("file:///", "").Replace("/", "\"))
                if (Test-Path $localPath) {
                    $targetRule = Join-Path $localPath "GEMINI.md"
                    Copy-Item -Path $SourceGemini -Destination $targetRule -Force
                    Write-Host "  -> [OK] Đã nạp rule vào project: $($proj.name) ($localPath)" -ForegroundColor Green
                }
            }
        } catch {}
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " HOÀN TẤT! Antigravity giờ đây sẽ tự động nạp Harness Hub " -ForegroundColor Cyan
Write-Host " cho MỌI DỰ ÁN mở trên máy tính này.                      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

