# Micro-check 02: Windows Update Download Cache
$path = "$env:WINDIR\SoftwareDistribution\Download"
$totalBytes = 0; $fileCount = 0
if (Test-Path $path) {
    $m = Get-ChildItem -Path $path -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
    if ($m.Sum) { $totalBytes += $m.Sum }
    $fileCount = $m.Count
}
[PSCustomObject]@{
    Domain = "WinSxS_Update"
    SizeMB = [math]::Round($totalBytes / 1MB, 2)
    Files  = $fileCount
    Status = if ($totalBytes -gt 200MB) { "CLEANABLE" } else { "OPTIMAL" }
}
