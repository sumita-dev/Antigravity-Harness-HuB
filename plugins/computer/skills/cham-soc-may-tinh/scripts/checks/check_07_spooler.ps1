# Micro-check 07: Print Spooler Queue
$spoolDir = "$env:WINDIR\System32\spool\PRINTERS"
$stuck = (Get-ChildItem -Path $spoolDir -ErrorAction SilentlyContinue).Count
[PSCustomObject]@{
    Domain     = "Print_Spooler"
    StuckJobs  = $stuck
    Status     = if ($stuck -gt 0) { "STUCK_FILES" } else { "CLEAR" }
}
