# Micro-task 01: Clean Temp & Prefetch
param([switch]$DryRun)
$target = "$env:LOCALAPPDATA\Temp"
$freed = 0
if (Test-Path $target) {
    $items = Get-ChildItem -Path $target -Force -ErrorAction SilentlyContinue
    foreach ($item in $items) {
        try {
            $sz = (Get-Item $item.FullName -Force -ErrorAction SilentlyContinue).Length
            if (-not $DryRun) {
                Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
            }
            if ($sz) { $freed += $sz }
        } catch { }
    }
}
$freedMB = [math]::Round($freed / 1MB, 2)
@{ Task = "CleanTemp"; Status = "SUCCESS"; FreedMB = $freedMB; Message = "Cleaned $freedMB MB temporary files" }
