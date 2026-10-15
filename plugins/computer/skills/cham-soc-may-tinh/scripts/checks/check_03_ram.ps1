# Micro-check 03: RAM & Working Set
$os = Get-CimInstance Win32_OperatingSystem
$total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$usedPct = [math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100, 1)
[PSCustomObject]@{
    Domain       = "Memory_RAM"
    TotalGB      = $total
    FreeGB       = $free
    UsedPercent  = $usedPct
    Status       = if ($usedPct -gt 80) { "HIGH_USAGE" } else { "OPTIMAL" }
}
