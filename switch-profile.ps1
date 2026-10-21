<#
.SYNOPSIS
    Chuyển đổi profile plugin cho Antigravity để tối ưu token theo nhu cầu dự án.
.DESCRIPTION
    Profiles:
      all       : Bật đầy đủ toàn bộ plugin (Code, Marketing, Second-Brain, Design, Tools, Data...)
      code      : Chuyên lập trình App/Web (Tắt Marketing, tắt GCP DataKit, giữ Code + Design + Tools)
      marketing : Chuyên sáng tạo nội dung & tăng trưởng (Tắt Code dev nặng & DataKit, giữ Marketing + Second Brain)
      data      : Chuyên xử lý dữ liệu GCP/BigQuery (Bật Code + DataKit, tắt Marketing, Design)
.EXAMPLE
    pwsh -File .\switch-profile.ps1 -Profile code
    pwsh -File .\switch-profile.ps1 -Profile marketing
    pwsh -File .\switch-profile.ps1 -Profile data
    pwsh -File .\switch-profile.ps1 -Profile all
    pwsh -File .\switch-profile.ps1 -Profile code -DataKit $true
#>

param (
    [Parameter(Mandatory = $false)]
    [ValidateSet("all", "code", "marketing", "data")]
    [string]$Profile = "code",

    [Parameter(Mandatory = $false)]
    [Nullable[bool]]$DataKit = $null,

    [Parameter(Mandatory = $false)]
    [Nullable[bool]]$DevTools = $null
)

$ConfigPath = Join-Path $HOME ".gemini\config\config.json"
if (-not (Test-Path $ConfigPath)) {
    Write-Error "Không tìm thấy file cấu hình tại $ConfigPath"
    exit 1
}

$rawJson = Get-Content $ConfigPath -Raw -Encoding utf8
$config = $rawJson | ConvertFrom-Json

if ($null -eq $config.plugins) {
    $config | Add-Member -MemberType NoteProperty -Name "plugins" -Value ([PSCustomObject]@{})
}

function Set-PluginState($pluginName, [bool]$enabled) {
    $existing = $config.plugins.$pluginName
    if ($null -eq $existing) {
        $config.plugins | Add-Member -MemberType NoteProperty -Name $pluginName -Value ([PSCustomObject]@{ enabled = $enabled }) -Force
    } else {
        $existing | Add-Member -MemberType NoteProperty -Name "enabled" -Value $enabled -Force
    }
}

switch ($Profile) {
    "all" {
        Write-Host "--> Kích hoạt Profile: ALL (Bật toàn bộ plugin)" -ForegroundColor Cyan
        Set-PluginState "code" $true
        Set-PluginState "marketing" $true
        Set-PluginState "second-brain" $true
        Set-PluginState "apple-inspired-design" $true
        Set-PluginState "impeccable" $true
        Set-PluginState "chrome-devtools-plugin" $true
        Set-PluginState "data-agent-kit-plugin" $true
    }
    "code" {
        Write-Host "--> Kích hoạt Profile: CODE (Tối ưu cho Lập trình App / Web)" -ForegroundColor Green
        Write-Host "    [+] Bật: code, apple-inspired-design, impeccable, chrome-devtools" -ForegroundColor Gray
        Write-Host "    [-] Tắt: marketing, data-agent-kit (giải phóng ~12.000 tokens)" -ForegroundColor Gray
        Set-PluginState "code" $true
        Set-PluginState "apple-inspired-design" $true
        Set-PluginState "impeccable" $true
        Set-PluginState "chrome-devtools-plugin" $true
        Set-PluginState "marketing" $false
        Set-PluginState "data-agent-kit-plugin" $false
    }
    "marketing" {
        Write-Host "--> Kích hoạt Profile: MARKETING (Tối ưu cho Viết Content / Chiến dịch)" -ForegroundColor Yellow
        Write-Host "    [+] Bật: marketing, second-brain" -ForegroundColor Gray
        Write-Host "    [-] Tắt: code, apple-inspired-design, data-agent-kit (giải phóng ~15.000 tokens)" -ForegroundColor Gray
        Set-PluginState "code" $false
        Set-PluginState "apple-inspired-design" $false
        Set-PluginState "impeccable" $false
        Set-PluginState "marketing" $true
        Set-PluginState "second-brain" $true
        Set-PluginState "data-agent-kit-plugin" $false
    }
    "data" {
        Write-Host "--> Kích hoạt Profile: DATA (Tối ưu cho BigQuery, PySpark & GCP Pipeline)" -ForegroundColor Magenta
        Write-Host "    [+] Bật: code, data-agent-kit-plugin" -ForegroundColor Gray
        Write-Host "    [-] Tắt: marketing, apple-inspired-design, impeccable" -ForegroundColor Gray
        Set-PluginState "code" $true
        Set-PluginState "data-agent-kit-plugin" $true
        Set-PluginState "marketing" $false
        Set-PluginState "apple-inspired-design" $false
        Set-PluginState "impeccable" $false
    }
}

# Override riêng lẻ nếu người dùng chỉ định
if ($null -ne $DataKit) {
    Set-PluginState "data-agent-kit-plugin" $DataKit
    Write-Host "    [*] Override data-agent-kit-plugin: enabled = $DataKit" -ForegroundColor Yellow
}
if ($null -ne $DevTools) {
    Set-PluginState "chrome-devtools-plugin" $DevTools
    Write-Host "    [*] Override chrome-devtools-plugin: enabled = $DevTools" -ForegroundColor Yellow
}

$newJson = $config | ConvertTo-Json -Depth 10
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($ConfigPath, $newJson, $utf8NoBom)

Write-Host "[OK] Đã cập nhật profile thành công vào $ConfigPath!" -ForegroundColor Green
Write-Host "     F5 hoặc mở lại dự án để thấy lượng token giảm rõ rệt trong Customizations." -ForegroundColor Cyan
