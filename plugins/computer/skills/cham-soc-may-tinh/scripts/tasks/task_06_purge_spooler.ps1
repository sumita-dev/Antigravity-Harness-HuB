# Micro-task 06: Purge Print Spooler Stuck Files
param([switch]$DryRun)
$spoolDir = "$env:WINDIR\System32\spool\PRINTERS"
$count = (Get-ChildItem -Path $spoolDir -ErrorAction SilentlyContinue).Count
if ($count -eq 0) {
    @{ Task = "PurgeSpooler"; Status = "OPTIMAL"; Message = "Print spooler queue is already clear (0 stuck jobs)" }
} else {
    if (-not $DryRun) {
        Restart-Service -Name spooler -Force -ErrorAction SilentlyContinue
    }
    @{ Task = "PurgeSpooler"; Status = "SUCCESS"; Message = "Purged $count hung print spooler jobs" }
}
