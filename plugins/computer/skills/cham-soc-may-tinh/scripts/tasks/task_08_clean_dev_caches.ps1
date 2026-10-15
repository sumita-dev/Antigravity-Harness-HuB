# Micro-task 08: Clean Developer Tool Caches (Pip, Npm, pnpm, Crash Dumps)
param([switch]$DryRun)

$totalFreedBytes = 0
$messages = [System.Collections.Generic.List[string]]::new()

# 1. Python Pip Cache Purge
$pipPath = "$env:LOCALAPPDATA\pip\cache"
if (Test-Path $pipPath) {
    $before = (Get-ChildItem -Path $pipPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if (-not $DryRun) {
        $null = pip cache purge 2>&1
    }
    $after = if (Test-Path $pipPath) { (Get-ChildItem -Path $pipPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum } else { 0 }
    $diff = [math]::Max(0, ($before - $after))
    $totalFreedBytes += $diff
    $messages.Add("Pip cache: -$([math]::Round($diff/1MB, 2)) MB")
}

# 2. NodeJS Npm Cache Clean
$npmPath = "$env:LOCALAPPDATA\npm-cache"
if (Test-Path $npmPath) {
    $before = (Get-ChildItem -Path $npmPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if (-not $DryRun) {
        $null = npm cache clean --force 2>&1
    }
    $after = if (Test-Path $npmPath) { (Get-ChildItem -Path $npmPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum } else { 0 }
    $diff = [math]::Max(0, ($before - $after))
    $totalFreedBytes += $diff
    $messages.Add("Npm cache: -$([math]::Round($diff/1MB, 2)) MB")
}

# 3. pnpm Store Prune
$pnpmPath = "$env:LOCALAPPDATA\pnpm\store"
if (Test-Path $pnpmPath) {
    $before = (Get-ChildItem -Path $pnpmPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if (-not $DryRun) {
        $null = pnpm store prune 2>&1
    }
    $after = if (Test-Path $pnpmPath) { (Get-ChildItem -Path $pnpmPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum } else { 0 }
    $diff = [math]::Max(0, ($before - $after))
    $totalFreedBytes += $diff
    $messages.Add("pnpm store: -$([math]::Round($diff/1MB, 2)) MB")
}

# 4. Crash Dumps & Windows Error Reporting (WER)
$crashPaths = @("$env:LOCALAPPDATA\CrashDumps", "$env:LOCALAPPDATA\Microsoft\Windows\WER\ReportQueue", "$env:LOCALAPPDATA\Microsoft\Windows\WER\ReportArchive")
foreach ($cp in $crashPaths) {
    if (Test-Path $cp) {
        $items = Get-ChildItem -Path $cp -Force -ErrorAction SilentlyContinue
        foreach ($item in $items) {
            try {
                $sz = (Get-Item $item.FullName -Force -ErrorAction SilentlyContinue).Length
                if (-not $DryRun) {
                    Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
                }
                if ($sz) { $totalFreedBytes += $sz }
            } catch { }
        }
    }
}
$messages.Add("CrashDumps/WER: Đã làm sạch")

$freedMB = [math]::Round($totalFreedBytes / 1MB, 2)
@{
    Task    = "CleanDevCaches"
    Status  = "SUCCESS"
    FreedMB = $freedMB
    Message = "Đã dọn dẹp dev caches ($($messages -join ', '))"
}
