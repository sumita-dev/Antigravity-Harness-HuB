# Micro-check 04: Local SQLite Databases
$gemini = "$env:USERPROFILE\.gemini"
$dbFiles = Get-ChildItem -Path $gemini -Filter "*.db" -Recurse -ErrorAction SilentlyContinue
$totalBytes = ($dbFiles | Measure-Object -Property Length -Sum).Sum
[PSCustomObject]@{
    Domain     = "Database_SQLite"
    Count      = $dbFiles.Count
    TotalMB    = [math]::Round(($totalBytes / 1MB), 2)
    Status     = if ($dbFiles.Count -gt 50) { "NEEDS_VACUUM" } else { "OPTIMAL" }
}
