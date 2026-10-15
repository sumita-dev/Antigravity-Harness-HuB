# Micro-check 09: Developer Tool Caches & System Junk
# Rà soát bộ nhớ đệm lập trình (Pip, Npm, pnpm, Docker), Thùng rác, CrashDumps và DNS

# 1. Python Pip Cache
$pipPath = "$env:LOCALAPPDATA\pip\cache"
$pipMB = if (Test-Path $pipPath) {
    [math]::Round(((Get-ChildItem $pipPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
} else { 0 }

# 2. NodeJS Npm Cache
$npmPath = "$env:LOCALAPPDATA\npm-cache"
$npmMB = if (Test-Path $npmPath) {
    [math]::Round(((Get-ChildItem $npmPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
} else { 0 }

# 3. pnpm Store
$pnpmPath = "$env:LOCALAPPDATA\pnpm\store"
$pnpmMB = if (Test-Path $pnpmPath) {
    [math]::Round(((Get-ChildItem $pnpmPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
} else { 0 }

# 4. Crash Dumps & Windows Error Reporting (WER)
$crashPath = "$env:LOCALAPPDATA\CrashDumps"
$crashMB = if (Test-Path $crashPath) {
    [math]::Round(((Get-ChildItem $crashPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
} else { 0 }

$werPath = "$env:LOCALAPPDATA\Microsoft\Windows\WER"
$werMB = if (Test-Path $werPath) {
    [math]::Round(((Get-ChildItem $werPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB), 2)
} else { 0 }
$totalCrashMB = [math]::Round($crashMB + $werMB, 2)

# 5. Recycle Bin (Thùng rác)
$binMB = 0
$binCount = 0
try {
    $shell = New-Object -ComObject Shell.Application
    $bin = $shell.Namespace(10)
    $items = $bin.Items()
    $binCount = $items.Count
    $binMB = [math]::Round((($items | Measure-Object -Property Size -Sum).Sum / 1MB), 2)
} catch { }

# 6. DNS Resolver Cache
$dnsRecords = try { (Get-DnsClientCache -ErrorAction SilentlyContinue).Count } catch { 0 }

# 7. Docker Desktop VHDX & Daemon Status
$dockerVhdx = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"
$dockerGB = if (Test-Path $dockerVhdx) {
    [math]::Round(((Get-Item $dockerVhdx).Length / 1GB), 2)
} else { 0 }

$dockerRunning = $false
try {
    $null = docker version 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch { }

$totalCleanableMB = [math]::Round($pipMB + $npmMB + $pnpmMB + $totalCrashMB + $binMB, 2)

[PSCustomObject]@{
    Domain           = "DevCaches_And_SystemClean"
    PipMB            = $pipMB
    NpmMB            = $npmMB
    PnpmMB           = $pnpmMB
    CrashDumpsMB     = $totalCrashMB
    RecycleBinMB     = $binMB
    RecycleCount     = $binCount
    DnsRecords       = $dnsRecords
    DockerVhdxGB     = $dockerGB
    DockerRunning    = $dockerRunning
    TotalCleanableMB = $totalCleanableMB
    Status           = if ($totalCleanableMB -gt 150) { "CLEANABLE" } else { "OPTIMAL" }
}
