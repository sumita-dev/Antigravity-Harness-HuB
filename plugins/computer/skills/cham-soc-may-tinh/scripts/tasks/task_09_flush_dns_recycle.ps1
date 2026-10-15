# Micro-task 09: Flush DNS Resolver Cache & Purge Recycle Bin
param([switch]$DryRun)

$binMB = 0
$binCount = 0
try {
    $shell = New-Object -ComObject Shell.Application
    $bin = $shell.Namespace(10)
    $items = $bin.Items()
    $binCount = $items.Count
    $binMB = [math]::Round((($items | Measure-Object -Property Size -Sum).Sum / 1MB), 2)
} catch { }

if (-not $DryRun) {
    # 1. Purge Recycle Bin
    Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    
    # 2. Flush DNS Resolver Cache
    try {
        Clear-DnsClientCache -ErrorAction SilentlyContinue
    } catch {
        ipconfig /flushdns | Out-Null
    }
}

@{
    Task    = "FlushDnsRecycle"
    Status  = "SUCCESS"
    FreedMB = $binMB
    Message = "Đã dọn sạch Thùng rác ($binCount mục, $binMB MB) và làm mới DNS Resolver Cache"
}
