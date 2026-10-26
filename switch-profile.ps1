<#
.SYNOPSIS
    Chuyển đổi profile plugin cho Antigravity để tối ưu token theo nhu cầu dự án.
.DESCRIPTION
    Profiles:
      all       : Bật đầy đủ toàn bộ plugin (Code, Marketing, Second-Brain, Design, Tools)
      code      : Chuyên lập trình App/Web (Tắt Marketing, giữ Code + Design + Second-Brain + Tools)
      marketing : Chuyên sáng tạo nội dung & tăng trưởng (Tắt Code dev nặng, giữ Marketing + Second-Brain + Tools)
.EXAMPLE
    pwsh -File .\switch-profile.ps1 -Profile code
    pwsh -File .\switch-profile.ps1 -Profile marketing
    pwsh -File .\switch-profile.ps1 -Profile all
#>

param (
    [Parameter(Mandatory = $false)]
    [ValidateSet("all", "code", "marketing")]
    [string]$Profile = "all",

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
        Write-Host "--> Kích hoạt Profile: ALL (Bật Code, Marketing, Second-Brain, Design & Tools)" -ForegroundColor Cyan
        Set-PluginState "code" $true
        Set-PluginState "marketing" $true
        Set-PluginState "second-brain" $true
        Set-PluginState "apple-inspired-design" $true
        Set-PluginState "impeccable" $true
        Set-PluginState "chrome-devtools-plugin" $true
        Set-PluginState "computer" $true
    }
    "code" {
        Write-Host "--> Kích hoạt Profile: CODE (Tối ưu cho Lập trình App / Web)" -ForegroundColor Green
        Write-Host "    [+] Bật: code, apple-inspired-design, impeccable, chrome-devtools, second-brain, computer" -ForegroundColor Gray
        Write-Host "    [-] Tắt: marketing" -ForegroundColor Gray
        Set-PluginState "code" $true
        Set-PluginState "apple-inspired-design" $true
        Set-PluginState "impeccable" $true
        Set-PluginState "chrome-devtools-plugin" $true
        Set-PluginState "marketing" $false
        Set-PluginState "computer" $true
        Set-PluginState "second-brain" $true
    }
    "marketing" {
        Write-Host "--> Kích hoạt Profile: MARKETING (Tối ưu cho Viết Content / Chiến dịch)" -ForegroundColor Yellow
        Write-Host "    [+] Bật: marketing, second-brain, computer" -ForegroundColor Gray
        Write-Host "    [-] Tắt: code, apple-inspired-design, impeccable" -ForegroundColor Gray
        Set-PluginState "code" $false
        Set-PluginState "apple-inspired-design" $false
        Set-PluginState "impeccable" $false
        Set-PluginState "marketing" $true
        Set-PluginState "second-brain" $true
        Set-PluginState "computer" $true
    }
}

# Override riêng lẻ nếu người dùng chỉ định
if ($null -ne $DevTools) {
    Set-PluginState "chrome-devtools-plugin" $DevTools
    Write-Host "    [*] Override chrome-devtools-plugin: enabled = $DevTools" -ForegroundColor Yellow
}

$newJson = $config | ConvertTo-Json -Depth 10
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($ConfigPath, $newJson, $utf8NoBom)

Write-Host "[OK] Đã cập nhật profile thành công vào $ConfigPath!" -ForegroundColor Green
Write-Host "     F5 hoặc mở lại dự án để thấy lượng token giảm rõ rệt trong Customizations." -ForegroundColor Cyan
