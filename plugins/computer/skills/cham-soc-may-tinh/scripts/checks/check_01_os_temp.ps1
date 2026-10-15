# Micro-check 01: OS & App Temp Cache
$paths = @($env:LOCALAPPDATA + "\Temp", $env:WINDIR + "\Temp")
$totalBytes = 0; $fileCount = 0
foreach ($p in $paths) {
    if (Test-Path $p) {
        $m = Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
        if ($m.Sum) { $totalBytes += $m.Sum }
        $fileCount += $m.Count
    }
}
[PSCustomObject]@{
    Domain = "OS_Temp"
    SizeMB = [math]::Round($totalBytes / 1MB, 2)
    Files  = $fileCount
    Status = if ($totalBytes -gt 100MB) { "CLEANABLE" } else { "OPTIMAL" }
}
