<#
.SYNOPSIS
    Chuyển đổi profile plugin cho Antigravity để tối ưu token theo nhu cầu dự án.
.DESCRIPTION
    Profiles:
      all       : Bật đầy đủ toàn bộ plugin (Code, Marketing, Second-Brain, Design...)
      code      : Chuyên lập trình App/Web (Tắt Marketing, giữ Code + Design + Tools)
      marketing : Chuyên sáng tạo nội dung & tăng trưởng (Tắt Code dev nặng, giữ Marketing + Second Brain)
.EXAMPLE
    pwsh -File .\switch-profile.ps1 -Profile code
    pwsh -File .\switch-profile.ps1 -Profile marketing
    pwsh -File .\switch-profile.ps1 -Profile all
#>

param (
    [Parameter(Mandatory = $false)]
    [ValidateSet("all", "code", "marketing")]
    [string]$Profile = "code"
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

switch ($Profile) {
    "all" {
        Write-Host "--> Kích hoạt Profile: ALL (Bật toàn bộ plugin)" -ForegroundColor Cyan
        $config.plugins.code.enabled = $true
        $config.plugins.marketing.enabled = $true
        if ($config.plugins."second-brain") { $config.plugins."second-brain".enabled = $true }
        if ($config.plugins."apple-inspired-design") { $config.plugins."apple-inspired-design".enabled = $true }
        if ($config.plugins.impeccable) { $config.plugins.impeccable.enabled = $true }
    }
    "code" {
        Write-Host "--> Kích hoạt Profile: CODE (Tối ưu cho Lập trình App / Web)" -ForegroundColor Green
        Write-Host "    [+] Bật: code, apple-inspired-design, impeccable" -ForegroundColor Gray
        Write-Host "    [-] Tắt: marketing (giải phóng ~5.000 tokens)" -ForegroundColor Gray
        $config.plugins.code.enabled = $true
        $config.plugins.marketing.enabled = $false
        if ($config.plugins."apple-inspired-design") { $config.plugins."apple-inspired-design".enabled = $true }
        if ($config.plugins.impeccable) { $config.plugins.impeccable.enabled = $true }
    }
    "marketing" {
        Write-Host "--> Kích hoạt Profile: MARKETING (Tối ưu cho Viết Content / Chiến dịch)" -ForegroundColor Yellow
        Write-Host "    [+] Bật: marketing, second-brain" -ForegroundColor Gray
        Write-Host "    [-] Tắt: code (giải phóng ~7.000 tokens)" -ForegroundColor Gray
        $config.plugins.code.enabled = $false
        $config.plugins.marketing.enabled = $true
    }
}

$newJson = $config | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($ConfigPath, $newJson, [System.Text.Encoding]::UTF8)

Write-Host "[OK] Đã cập nhật profile thành công vào $ConfigPath!" -ForegroundColor Green
Write-Host "     F5 hoặc mở lại dự án để thấy lượng token giảm rõ rệt trong Customizations." -ForegroundColor Cyan
