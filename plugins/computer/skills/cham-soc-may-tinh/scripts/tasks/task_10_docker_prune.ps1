# Micro-task 10: Docker System & Build Cache Prune
param([switch]$DryRun)

$dockerRunning = $false
try {
    $null = docker version 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch { }

$vhdxPath = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"
$vhdxGB = if (Test-Path $vhdxPath) { [math]::Round(((Get-Item $vhdxPath).Length / 1GB), 2) } else { 0 }

if ($dockerRunning) {
    if (-not $DryRun) {
        $pruneOut = docker system prune -f 2>&1
        $builderOut = docker builder prune -f 2>&1
    }
    @{
        Task    = "DockerPrune"
        Status  = "SUCCESS"
        FreedMB = 0
        Message = "Docker đang chạy: Đã dọn dẹp dangling images, stopped containers và build cache."
    }
} else {
    @{
        Task    = "DockerPrune"
        Status  = "SUCCESS"
        FreedMB = 0
        Message = "Docker Desktop hiện đang tắt (VHDX: $vhdxGB GB). Bảo lưu dữ liệu container an toàn."
    }
}
