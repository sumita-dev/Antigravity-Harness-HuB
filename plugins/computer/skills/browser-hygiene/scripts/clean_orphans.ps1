# Safe cleanup script for confirmed orphaned processes and temporary profiles
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [int[]]$TargetPids,

    [string[]]$TempProfilesToClean
)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host "================================================================="
Write-Host "SAFE PROCESS CLEANUP EXECUTION"
Write-Host "================================================================="

foreach ($pidToStop in $TargetPids) {
    $proc = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue
    if ($proc) {
        $pName = $proc.ProcessName
        Write-Host "Stopping PID $pidToStop ($pName)..."
        
        # Stop process
        Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
        
        $verify = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue
        if (-not $verify) {
            Write-Host "  -> SUCCESS: PID $pidToStop ($pName) stopped." -ForegroundColor Green
        } else {
            Write-Host "  -> WARNING: Failed to stop PID $pidToStop ($pName)." -ForegroundColor Red
        }
    } else {
        Write-Host "PID $pidToStop is already terminated or not found." -ForegroundColor Yellow
    }
}

if ($TempProfilesToClean) {
    Write-Host ""
    Write-Host "Cleaning confirmed unused temp profiles..."
    foreach ($dir in $TempProfilesToClean) {
        if (Test-Path $dir) {
            try {
                Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
                Write-Host "  -> SUCCESS: Removed profile dir $dir" -ForegroundColor Green
            } catch {
                Write-Host "  -> WARNING: Cannot remove $dir (may still be in use): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
}
Write-Host "Cleanup completed."
