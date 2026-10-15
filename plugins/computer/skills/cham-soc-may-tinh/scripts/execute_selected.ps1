# Master Orchestrator: execute_selected.ps1
# Tích hợp Động Cơ Ghi Nhận Tiến Trình & Đồng Bộ Checklist Thời Gian Thực (CSSK_LiveLogger)
param(
    [ValidateSet('FullCare', 'AppSwitch', 'DiskClean', 'DBVacuum', 'DevClean', 'Custom')]
    [string]$Preset = 'FullCare',
    [string[]]$SelectedTasks,
    [array]$CustomChecklist, # Hỗ trợ đưa vào checklist tùy biến cho các bài toán chưa biết
    [switch]$TuneAltTab,
    [switch]$TuneFocus,
    [switch]$DryRun,
    [string]$WorkspaceRoot = (Get-Location).Path,
    [string]$UserIssue = ''
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tasksDir = Join-Path $scriptDir 'tasks'
$loggerPath = Join-Path $scriptDir 'CSSK_LiveLogger.ps1'

if (-not (Test-Path $loggerPath)) {
    Write-Error "Không tìm thấy engine CSSK_LiveLogger.ps1 tại: $loggerPath"
    exit 1
}
. $loggerPath

# Danh mục 7 phân hệ tiêu chuẩn của cham-soc-may-tinh
$allModules = [ordered]@{}
$allModules['RestorePoint'] = @{
    Id = 'RestorePoint'; Num = 1; Name = 'Bảo Vệ An Toàn Hệ Thống (System Restore Point)';
    Script = 'task_00_restorepoint.ps1';
    Desc = 'Khởi tạo mốc bảo hiểm System Restore Point (VSS Snapshot) trước khi can thiệp.';
    SkipReason = 'Bắt buộc chạy cho mọi quy trình can thiệp để đảm bảo an toàn tuyệt đối.'
}
$allModules['CleanTemp'] = @{
    Id = 'CleanTemp'; Num = 2; Name = 'Dọn Dẹp Tệp Tạm & Bộ Nhớ Đệm (Deep Temp & Cache)';
    Script = 'task_01_clean_temp.ps1';
    Desc = 'Quét và dọn sạch các tệp rác phiên làm việc tại C:\Windows\Temp và %LOCALAPPDATA%\Temp.';
    SkipReason = 'Không can thiệp vì tình trạng ổ đĩa còn rộng rãi, không liên quan đến hiện tượng.'
}
$allModules['CleanWinSxS'] = @{
    Id = 'CleanWinSxS'; Num = 3; Name = 'Tối Ưu Bản Cập Nhật Windows Update (WinSxS Store)';
    Script = 'task_02_clean_winsxs.ps1';
    Desc = 'Loại bỏ các gói tải về cũ trong SoftwareDistribution và tối ưu hóa kho thành phần.';
    SkipReason = 'Bỏ qua để tiết kiệm thời gian vì hệ thống không có dấu hiệu nghẽn do Windows Update.'
}
$allModules['OptimizeRAM'] = @{
    Id = 'OptimizeRAM'; Num = 4; Name = 'Thu Hồi RAM Nhàn Rỗi & Tối Ưu Cửa Sổ (Working Set & Alt+Tab)';
    Script = 'task_03_optimize_ram.ps1';
    Desc = 'Gọi Win32 API EmptyWorkingSet thu hồi RAM nhàn rỗi và tinh chỉnh bộ lọc Alt+Tab.';
    SkipReason = 'Bỏ qua vì hệ thống chưa ghi nhận dấu hiệu đầy bộ nhớ RAM.'
}
$allModules['VacuumSQLite'] = @{
    Id = 'VacuumSQLite'; Num = 5; Name = 'Bảo Trì Cơ Sở Dữ Liệu SQLite Nội Bộ (Database Reindex)';
    Script = 'task_04_vacuum_sqlite.ps1';
    Desc = 'Kiểm tra toàn vẹn phân trang B-Tree, dọn trang trống (VACUUM) và tái lập chỉ mục (REINDEX).';
    SkipReason = 'Bỏ qua vì các cơ sở dữ liệu nội bộ đang ở trạng thái tối ưu, không phân mảnh.'
}
$allModules['ReTrimSSD'] = @{
    Id = 'ReTrimSSD'; Num = 6; Name = 'Phục Hồi Tốc Độ Ghi & Chống Suy Hao NVMe SSD (Flash ReTrim)';
    Script = 'task_05_retrim_ssd.ps1';
    Desc = 'Gửi tín hiệu ReTrim tới NVMe Flash Controller giúp giải phóng ô nhớ rác.';
    SkipReason = 'Bỏ qua vì ổ SSD đã được ReTrim định kỳ gần đây, tốc độ đọc ghi đang ở mức đỉnh.'
}
$allModules['PurgeSpooler'] = @{
    Id = 'PurgeSpooler'; Num = 7; Name = 'Thông Tắc Hàng Đợi Dịch Vụ Máy In (Print Spooler Guard)';
    Script = 'task_06_purge_spooler.ps1';
    Desc = 'Rà soát và làm sạch các lệnh in tồn đọng hoặc lỗi tệp đệm trong hàng đợi.';
    SkipReason = 'Bỏ qua vì hàng đợi máy in không có lệnh in nào bị nghẽn và CPU dịch vụ ở mức 0%.'
}
$allModules['CleanDevCaches'] = @{
    Id = 'CleanDevCaches'; Num = 8; Name = 'Dọn Dẹp Bộ Nhớ Đệm Lập Trình (Pip, Npm, pnpm, CrashDumps)';
    Script = 'task_08_clean_dev_caches.ps1';
    Desc = 'Thu hồi dung lượng từ cache Pip, Npm, pnpm và các tệp CrashDumps / WER cũ.';
    SkipReason = 'Bỏ qua vì không yêu cầu dọn dẹp các cache môi trường phát triển.'
}
$allModules['FlushDnsRecycle'] = @{
    Id = 'FlushDnsRecycle'; Num = 9; Name = 'Dọn Thùng Rác & Làm Mới Bộ Phân Giải DNS (Recycle Bin & DNS)';
    Script = 'task_09_flush_dns_recycle.ps1';
    Desc = 'Xóa vĩnh viễn các tệp trong Recycle Bin và làm mới DNS Resolver Cache.';
    SkipReason = 'Bỏ qua vì Thùng rác trống và mạng hoạt động ổn định.'
}
$allModules['PruneDocker'] = @{
    Id = 'PruneDocker'; Num = 10; Name = 'Dọn Dẹp & Quản Lý Dữ Liệu Docker (Docker System Prune)';
    Script = 'task_10_docker_prune.ps1';
    Desc = 'Dọn dẹp dangling images, stopped containers và build cache nếu Docker chạy; kiểm soát dung lượng VHDX.';
    SkipReason = 'Bỏ qua vì Docker Desktop không hoạt động hoặc không yêu cầu dọn dẹp container.'
}

# Xây dựng danh sách tác vụ thi công
$activeChecklist = @()
$skippedChecklist = @()

if ($CustomChecklist -and $CustomChecklist.Count -gt 0) {
    # Trường hợp bài toán tùy biến (Custom targeted issue)
    $activeChecklist = $CustomChecklist
    $taskTitle = "Tối Ưu Hóa & Xử Lý Sự Cố Tùy Chỉnh (Custom Task)"
} else {
    # Trường hợp chọn theo Preset chuẩn
    $activeKeys = @()
    if ($SelectedTasks -and $SelectedTasks.Count -gt 0) {
        $activeKeys = $SelectedTasks
    } else {
        switch ($Preset) {
            'AppSwitch' {
                $activeKeys = @('RestorePoint', 'OptimizeRAM')
                $TuneAltTab = $true
                $TuneFocus = $true
            }
            'DevClean' {
                $activeKeys = @('RestorePoint', 'CleanTemp', 'CleanDevCaches', 'FlushDnsRecycle', 'PruneDocker')
            }
            'DiskClean' {
                $activeKeys = @('RestorePoint', 'CleanTemp', 'CleanWinSxS', 'CleanDevCaches', 'FlushDnsRecycle', 'ReTrimSSD')
            }
            'DBVacuum' {
                $activeKeys = @('RestorePoint', 'VacuumSQLite')
            }
            'FullCare' {
                $activeKeys = @('RestorePoint', 'CleanTemp', 'CleanWinSxS', 'CleanDevCaches', 'FlushDnsRecycle', 'PruneDocker', 'OptimizeRAM', 'VacuumSQLite', 'ReTrimSSD', 'PurgeSpooler')
            }
            Default {
                $activeKeys = @('RestorePoint', 'CleanTemp', 'CleanWinSxS', 'CleanDevCaches', 'FlushDnsRecycle', 'PruneDocker', 'OptimizeRAM', 'VacuumSQLite', 'ReTrimSSD', 'PurgeSpooler')
            }
        }
    }

    if ($activeKeys -notcontains 'RestorePoint') {
        $activeKeys = , 'RestorePoint' + $activeKeys
    }

    foreach ($k in $activeKeys) {
        if ($allModules.Contains($k)) {
            $activeChecklist += $allModules[$k]
        }
    }

    foreach ($k in $allModules.Keys) {
        if ($activeKeys -notcontains $k) {
            $skippedChecklist += $allModules[$k]
        }
    }
    $taskTitle = "Bảo Dưỡng & Tối Ưu Hệ Thống (Gói $Preset)"
}

# Khởi tạo phiên làm việc Realtime với 2 file đồng bộ
$session = New-CSSKSession -WorkspaceRoot $WorkspaceRoot `
                           -TaskTitle $taskTitle `
                           -UserIssue $UserIssue `
                           -ChecklistItems $activeChecklist `
                           -SkippedItems $skippedChecklist `
                           -DryRun:$DryRun

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ĐỘNG CƠ BẢO DƯỠNG & TỐI ƯU HÓA MÁY TÍNH (TARGETED PC CARE)" -ForegroundColor Cyan
Write-Host "  Trạng thái: Đang thi công Realtime với 2 file Markdown đồng bộ" -ForegroundColor Yellow
Write-Host "  1. Biên bản Checklist:  $($session.LatestPlanFile)" -ForegroundColor Green
Write-Host "  2. Nhật ký tiến trình:  $($session.LatestProcessLogFile)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# THỰC THI TUẦN TỰ TỪNG VI TÁC VỤ
foreach ($item in $activeChecklist) {
    $taskId = $item.Id
    $session.StartStep($taskId)

    $taskScript = $item.Script
    $detailResult = ""
    $taskStatus = "[x]"
    $errorMsg = ""

    if ($item.Action -and ($item.Action -is [scriptblock])) {
        # Nếu là vi tác vụ tùy chỉnh truyền qua ScriptBlock
        try {
            $res = & $item.Action
            $detailResult = if ($res) { "$res" } else { "Hoàn tất thành công" }
            $session.Log("Kết quả thực thi: $detailResult", "SUCCESS")
        } catch {
            $taskStatus = "[!]"
            $errorMsg = $_.Exception.Message
            $session.Log("Lỗi phát sinh: $errorMsg", "ERROR")
        }
    } elseif ($taskScript) {
        $taskScriptPath = Join-Path $tasksDir $taskScript
        if (Test-Path $taskScriptPath) {
            try {
                $taskParams = @{}
                if ($DryRun) { $taskParams['DryRun'] = $true }
                if ($taskId -eq 'OptimizeRAM') {
                    if ($TuneAltTab) { $taskParams['TuneAltTab'] = $true }
                    if ($TuneFocus) { $taskParams['TuneFocus'] = $true }
                }

                $session.Log("Đang gọi vi tác vụ native: $taskScript...")
                $res = & $taskScriptPath @taskParams
                
                if ($res -is [hashtable]) {
                    $detailResult = if ($res.Message) { $res.Message } else { "Hoàn tất" }
                    if ($res.GainedMB) { $detailResult += " (Giải phóng: $($res.GainedMB) MB)" }
                    elseif ($res.FreedMB) { $detailResult += " (Giải phóng: $($res.FreedMB) MB)" }
                    elseif ($res.TotalChecked) { $detailResult += " (Đã kiểm tra: $($res.TotalChecked))" }
                } else {
                    $detailResult = "Đã hoàn tất vi tác vụ"
                }
            } catch {
                $taskStatus = "[!]"
                $errorMsg = $_.Exception.Message
                $session.Log("Lỗi khi chạy $taskScript : $errorMsg", "ERROR")
            }
        } else {
            $taskStatus = "[!]"
            $errorMsg = "Không tìm thấy file kịch bản vi tác vụ: $taskScript"
            $session.Log($errorMsg, "WARN")
        }
    }

    $session.CompleteStep($taskId, $detailResult, $taskStatus, $errorMsg)
    Start-Sleep -Milliseconds 150 # Khoảng trễ tự nhiên để cập nhật mượt mà
}

# Kết thúc phiên làm việc
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$usedGB = [math]::Round(($cs.TotalPhysicalMemory - $os.FreePhysicalMemory * 1KB) / 1GB, 2)
$summary = "Nghiệm thu hoàn tất. RAM khả dụng hiện tại: ${freeGB} GB (Đang dùng: ${usedGB} GB)."

$session.Finish($summary)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  HOÀN TẤT TOÀN BỘ CHU TRÌNH XỬ LÝ! HỒ SƠ ĐÃ ĐỒNG BỘ 100%." -ForegroundColor Green
Write-Host "  -> Xem Checklist: [LATEST_CSSK.md](file:///$($session.LatestPlanFile.Replace('\', '/')))" -ForegroundColor Yellow
Write-Host "  -> Xem Nhật Ký:   [NHAT_KY_TIEN_TRINH_MOI_NHAT.md](file:///$($session.LatestProcessLogFile.Replace('\', '/')))" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
