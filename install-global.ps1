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

# 2. Xóa bỏ file rule rời rạc cũ và dọn dẹp .agent thừa (tránh trùng lặp)
$LegacyLooseRule = Join-Path $GlobalRulesDir "harness_orchestrator.md"
if (Test-Path $LegacyLooseRule) {
    Remove-Item -Path $LegacyLooseRule -Force -ErrorAction SilentlyContinue
}
$LegacyGlobalAgent = Join-Path $GlobalConfigDir ".agent"
if (Test-Path $LegacyGlobalAgent) {
    Remove-Item -Path $LegacyGlobalAgent -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Đã dọn dẹp thư mục .agent dư thừa trong Global" -ForegroundColor Green
}
$LegacyPluginRule = Join-Path $GlobalPluginsDir "code\rules\AGENTS.md"
if (Test-Path $LegacyPluginRule) {
    Remove-Item -Path $LegacyPluginRule -Force -ErrorAction SilentlyContinue
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

# 6. Cài đặt Rule Toàn cục tinh gọn vào Global Config (Context Budget Economics < 8KB)
$GlobalGeminiTemplate = Join-Path $RepoRoot "configs\global_gemini.md"
$DestGlobalGemini = Join-Path $GlobalConfigDir "GEMINI.md"
if (Test-Path $GlobalGeminiTemplate) {
    Copy-Item -Path $GlobalGeminiTemplate -Destination $DestGlobalGemini -Force
    Write-Host "[OK] Đã cài đặt Rule Toàn cục tinh gọn (< 8KB): $DestGlobalGemini" -ForegroundColor Green
}

# 7. Chuẩn hóa .agents trong Global (tránh duplicate skills qua plugins.json)
$DotAgentsDir = Join-Path $GlobalConfigDir ".agents"
if (-not (Test-Path $DotAgentsDir)) {
    New-Item -ItemType Directory -Path $DotAgentsDir -Force | Out-Null
}
$GlobalSkillsJson = Join-Path $DotAgentsDir "skills.json"
'{"entries": []}' | Out-File -FilePath $GlobalSkillsJson -Encoding utf8 -Force
if (Test-Path (Join-Path $RepoRoot ".agents\plugins.json")) {
    Copy-Item -Path (Join-Path $RepoRoot ".agents\plugins.json") -Destination (Join-Path $DotAgentsDir "plugins.json") -Force
}
if (Test-Path (Join-Path $RepoRoot ".agents\hooks.json")) {
    Copy-Item -Path (Join-Path $RepoRoot ".agents\hooks.json") -Destination (Join-Path $DotAgentsDir "hooks.json") -Force
}
Write-Host "[OK] Đã chuẩn hóa .agents Toàn cục (skills.json rỗng để nạp qua plugins)" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " HOÀN TẤT! Antigravity giờ đây sẽ tự động nạp Harness Hub " -ForegroundColor Cyan
Write-Host " cho MỌI DỰ ÁN mở trên máy tính này (qua Global Plugin).  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan


