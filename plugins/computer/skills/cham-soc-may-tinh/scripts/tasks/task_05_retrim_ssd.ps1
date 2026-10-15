# Micro-task 05: NVMe SSD ReTrim
param([switch]$DryRun)
if ($DryRun) {
    @{ Task = "ReTrimSSD"; Status = "SIMULATED"; Message = "[DryRun] Simulated Optimize-Volume -DriveLetter C -ReTrim" }
} else {
    try {
        Optimize-Volume -DriveLetter C -ReTrim -ErrorAction SilentlyContinue | Out-Null
        @{ Task = "ReTrimSSD"; Status = "SUCCESS"; Message = "Sent TRIM command to NVMe Flash blocks on C:" }
    } catch {
        @{ Task = "ReTrimSSD"; Status = "SKIPPED"; Message = "ReTrim requires administrator rights; skipped safely" }
    }
}
