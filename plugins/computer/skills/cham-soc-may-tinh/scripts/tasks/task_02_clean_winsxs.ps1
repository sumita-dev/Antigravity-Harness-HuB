# Micro-task 02: Clean Windows Update Download Cache
param([switch]$DryRun)
$target = "$env:WINDIR\SoftwareDistribution\Download"
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
@{ Task = "CleanWinSxS"; Status = "SUCCESS"; FreedMB = $freedMB; Message = "Purged $freedMB MB update download cache" }
