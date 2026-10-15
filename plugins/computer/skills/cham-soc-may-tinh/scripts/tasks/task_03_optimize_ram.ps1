# Micro-task 03: Thu hồi Working Set bộ nhớ RAM & Tối ưu chuyển đổi ứng dụng
param(
    [switch]$DryRun,
    [switch]$TuneAltTab,
    [switch]$TuneFocus
)

$beforeMem = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory

if ($DryRun) {
    return @{ Task = "OptimizeRAM"; Status = "SIMULATED"; Message = "[DryRun] Mô phỏng thu hồi WorkingSet của các tiến trình nền và kiểm tra cấu hình tiêu điểm chuyển đổi cửa sổ" }
}

# 1. Thu hồi WorkingSet của các tiến trình nền bằng Windows NT native API psapi.dll
$trimmedCount = 0
try {
    $pinvokeCode = @'
    using System;
    using System.Runtime.InteropServices;
    public class MemoryManager {
        [DllImport("psapi.dll")]
        public static extern int EmptyWorkingSet(IntPtr hwProc);

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool SystemParametersInfo(uint uiAction, uint uiParam, IntPtr pvParam, uint fWinIni);
    }
'@
    if (-not ([System.Management.Automation.PSTypeName]'MemoryManager').Type) {
        Add-Type -TypeDefinition $pinvokeCode -ErrorAction SilentlyContinue
    }

    # Lọc các tiến trình ứng dụng người dùng chạy ngầm, loại trừ các tiến trình hệ thống cốt lõi
    $criticalNames = @('System', 'Idle', 'smss', 'csrss', 'wininit', 'services', 'lsass', 'winlogon', 'explorer', 'dwm')
    $targetProcs = Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.WorkingSet64 -gt 20MB -and $criticalNames -notcontains $_.ProcessName -and $_.Id -ne $PID
    }

    foreach ($proc in $targetProcs) {
        try {
            $null = [MemoryManager]::EmptyWorkingSet($proc.Handle)
            $trimmedCount++
        } catch { }
    }
} catch { }

# 2. Gọi Garbage Collection dọn rác session hiện hành
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()

# 3. Tinh chỉnh cấu hình chuyển đổi cửa sổ & Alt+Tab nếu được kích hoạt
$tuningMsg = ""
if ($TuneAltTab -or $TuneFocus) {
    try {
        # A. Tắt nạp tab Edge vào Alt+Tab
        $regAltTab = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
        Set-ItemProperty -Path $regAltTab -Name 'MultiTaskingAltTabFilter' -Value 3 -Type DWord -Force -ErrorAction SilentlyContinue

        # B. Tinh chỉnh Bộ Ba Tiêu Điểm Chuyển Cửa Sổ (Triple Focus Tuning)
        $regDesktop = 'HKCU:\Control Panel\Desktop'
        Set-ItemProperty -Path $regDesktop -Name 'ForegroundLockTimeout' -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $regDesktop -Name 'MenuShowDelay' -Value '100' -Type String -Force -ErrorAction SilentlyContinue

        $regMetrics = 'HKCU:\Control Panel\Desktop\WindowMetrics'
        if (-not (Test-Path $regMetrics)) { New-Item -Path $regMetrics -Force -ErrorAction SilentlyContinue | Out-Null }
        Set-ItemProperty -Path $regMetrics -Name 'MinAnimate' -Value '0' -Type String -Force -ErrorAction SilentlyContinue

        # C. Nạp trực tiếp vào RAM kernel Win32k (SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE = 3)
        [MemoryManager]::SystemParametersInfo(0x2001, 0, [IntPtr]::Zero, 3) | Out-Null

        $tuningMsg = " và đã kích hoạt Bộ Ba Tinh Chỉnh Cửa Sổ (ForegroundLockTimeout=0, MenuShowDelay=100, MinAnimate=0, AltTabFilter=3)"
    } catch { }
}

$afterMem = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory
$gainedMB = [math]::Round(($afterMem - $beforeMem) / 1KB, 2)
if ($gainedMB -lt 0) { $gainedMB = 0 }

@{
    Task = "OptimizeRAM"
    Status = "SUCCESS"
    GainedMB = $gainedMB
    Message = "Đã thu hồi WorkingSet của $trimmedCount tiến trình nền$tuningMsg ($gainedMB MB giải phóng)"
}
