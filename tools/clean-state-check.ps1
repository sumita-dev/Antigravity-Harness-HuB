<#
.SYNOPSIS
    Clean State Protocol Verifier (Harness 2.0 - 5-Dimension Clock-Out Verifier).

.DESCRIPTION
    Script PowerShell độc lập và tất định (idempotent) kiểm toán 5 chiều chất lượng
    của dự án trên môi trường Windows. Trả về exit code 0 khi PASS, 1 khi FAIL.

.PARAMETER Strict
    Dừng ngay khi có 1 chiều bị FAIL.

.PARAMETER Json
    Xuất kết quả nguyên bản dạng JSON.

.PARAMETER OutputFile
    Đường dẫn tệp tin để lưu báo cáo JSON.

.PARAMETER ProjectRoot
    Đường dẫn thư mục dự án cần kiểm toán (mặc định: thư mục hiện tại).

.PARAMETER BootCmd
    Lệnh khởi động tùy chỉnh cho chiều D5.

.PARAMETER TestCmd
    Lệnh test suite tùy chỉnh cho chiều D2.

.PARAMETER FeatureList
    Đường dẫn tệp feature_list.json cụ thể.

.EXAMPLE
    .\tools\clean-state-check.ps1
    .\tools\clean-state-check.ps1 -Strict
    .\tools\clean-state-check.ps1 -Json -OutputFile reports\clean-state.json
#>

[CmdletBinding()]
param (
    [switch]$Strict,
    [switch]$Json,
    [switch]$Fast,
    [string]$OutputFile = "",
    [string]$ProjectRoot = ".",
    [string]$BootCmd = "",
    [string]$TestCmd = "",
    [string]$FeatureList = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Xác định đường dẫn script python
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = Get-Location }
$RunnerScript = Join-Path $RepoRoot "scripts\clean_state_check.py"

if (-not (Test-Path $RunnerScript)) {
    Write-Error "Không tìm thấy runner script tại: $RunnerScript"
    exit 1
}

# Xây dựng danh sách tham số
$PyArgs = @($RunnerScript, "--project-root", $ProjectRoot, "--json")
if ($Strict) { $PyArgs += "--strict" }
if ($Fast) { $PyArgs += "--fast" }
if ($OutputFile) { $PyArgs += @("--output", $OutputFile) }
if ($BootCmd) { $PyArgs += @("--boot-cmd", $BootCmd) }
if ($TestCmd) { $PyArgs += @("--test-cmd", $TestCmd) }
if ($FeatureList) { $PyArgs += @("--feature-list", $FeatureList) }

# Tìm python executable
$PythonExe = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    # Ưu tiên python trong môi trường hiện tại
    $PythonExe = "python"
}

# Thực thi tiến trình kiểm toán
$OutputJson = & $PythonExe $PyArgs | Out-String

if ($Json) {
    Write-Output $OutputJson
    # Phân tích sơ bộ để trả mã thoát
    try {
        $Report = $OutputJson | ConvertFrom-Json
        if ($Report.overall_status -eq "PASS") { exit 0 } else { exit 1 }
    } catch {
        exit 1
    }
}

# Định dạng bảng màu trực quan cho người dùng / terminal
try {
    $Report = $OutputJson | ConvertFrom-Json
} catch {
    Write-Host "Lỗi thực thi kiểm toán Clean State:" -ForegroundColor Red
    Write-Host $OutputJson
    exit 1
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "             CLEAN STATE PROTOCOL: 5-DIMENSION CLOCK-OUT AUDIT                  " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " Project: $($Report.project_root)"
Write-Host " Time   : $($Report.timestamp)"
Write-Host " Total  : $([math]::Round($Report.total_duration_ms, 1)) ms"
Write-Host "--------------------------------------------------------------------------------"

$DimNames = $Report.dimensions.PSObject.Properties.Name
foreach ($dimKey in $DimNames) {
    $dim = $Report.dimensions.$dimKey
    $statusColor = switch ($dim.status) {
        "PASS"    { "Green" }
        "FAIL"    { "Red" }
        "SKIPPED" { "Yellow" }
        Default   { "White" }
    }

    $StatusTag = "[$($dim.status)]".PadRight(10)
    $DimTag = "$($dim.dimension):".PadRight(20)
    $DurTag = "($([math]::Round($dim.duration_ms, 1)) ms)".PadLeft(12)

    Write-Host "  " -NoNewline
    Write-Host $StatusTag -ForegroundColor $statusColor -NoNewline
    Write-Host " $DimTag" -ForegroundColor White -NoNewline
    Write-Host " $($dim.message) " -NoNewline
    Write-Host $DurTag -ForegroundColor Gray

    if ($dim.violations -and $dim.violations.Count -gt 0) {
        foreach ($violation in $dim.violations | Select-Object -First 3) {
            Write-Host "      * $violation" -ForegroundColor Red
        }
        if ($dim.violations.Count -gt 3) {
            Write-Host "      * ... and $($dim.violations.Count - 3) more violations" -ForegroundColor DarkRed
        }
    }
}

Write-Host "--------------------------------------------------------------------------------"
if ($Report.overall_status -eq "PASS") {
    Write-Host " VERDICT: PASS - READY FOR CLOCK-OUT / COMMIT" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host " VERDICT: FAIL - WORKSPACE DIRTY OR BROKEN (FIX ISSUES BEFORE CLOCK-OUT)" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Cyan
    exit 1
}
