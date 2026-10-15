# Micro-check 05: SSD Drive C:
$vol = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$sizeGB = [math]::Round($vol.Size / 1GB, 2)
$freeGB = [math]::Round($vol.FreeSpace / 1GB, 2)
$freePct = [math]::Round(($vol.FreeSpace / $vol.Size) * 100, 1)
[PSCustomObject]@{
    Domain      = "Disk_SSD_C"
    SizeGB      = $sizeGB
    FreeGB      = $freeGB
    FreePercent = $freePct
    Status      = if ($freePct -lt 15) { "CRITICAL_LOW" } else { "HEALTHY" }
}
