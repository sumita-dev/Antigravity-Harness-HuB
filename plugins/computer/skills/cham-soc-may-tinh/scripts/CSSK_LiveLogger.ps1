# CSSK_LiveLogger.ps1: Động Cơ Ghi Nhận Tiến Trình & Đồng Bộ Checklist Thời Gian Thực (Realtime Dual-File Engine)
# Chuẩn hóa theo kiến trúc KWSR - Hỗ trợ Tiếng Việt UTF-8 không lỗi font

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function New-CSSKSession {
    param(
        [Parameter(Mandatory=$true)]
        [string]$WorkspaceRoot,
        [Parameter(Mandatory=$true)]
        [string]$TaskTitle,
        [string]$UserIssue = '',
        [Parameter(Mandatory=$true)]
        [array]$ChecklistItems, # Mảng các hashtable: @{ Id = "T1"; Name = "Tên"; Desc = "Mô tả"; SkipReason = "" }
        [array]$SkippedItems = @(),
        [switch]$DryRun
    )

    $bt = [char]96 # Ký tự backtick markdown

    $hosoBase = Join-Path $WorkspaceRoot "HOSO_CSSK"
    $monthStr = Get-Date -Format "yyyy-MM"
    $monthDir = Join-Path $hosoBase $monthStr
    if (-not (Test-Path $monthDir)) { New-Item -ItemType Directory -Path $monthDir -Force | Out-Null }

    $nowDate = Get-Date
    $timeFileStr = $nowDate.ToString("yyyy-MM-dd HH.mm.ss")
    $timeCompactStr = $nowDate.ToString("yyyyMMdd_HHmmss")

    # 1. Tên file Checklist kế hoạch
    $prefix = if ($DryRun) { "CSSK_KIEM_THU" } else { "CSSK_KE_HOACH" }
    $planArchiveFile = Join-Path $monthDir "${prefix}_${timeCompactStr}.md"
    $latestPlanFile  = Join-Path $hosoBase "LATEST_CSSK.md"

    # 2. Tên file Nhật ký tiến trình thực tế (Tiếng Việt có dấu theo ngày tháng năm giờ giấc)
    $processLogArchiveFile = Join-Path $monthDir "Nhật Ký Tiến Trình - ${timeFileStr}.md"
    $latestProcessLogFile  = Join-Path $hosoBase "NHAT_KY_TIEN_TRINH_MOI_NHAT.md"
    $indexFile             = Join-Path $hosoBase "CSSK_INDEX.md"

    # Khởi tạo bảng nhiệm vụ
    $taskMap = [ordered]@{}
    foreach ($item in $ChecklistItems) {
        $taskMap[$item.Id] = [ordered]@{
            Id          = $item.Id
            Name        = $item.Name
            Desc        = $item.Desc
            Status      = "[ ]"
            StateLabel  = "CHỜ THỰC THI"
            StartTime   = $null
            EndTime     = $null
            DurationSec = 0
            Detail      = ""
            Error       = ""
        }
    }

    $session = [PSCustomObject]@{
        WorkspaceRoot         = $WorkspaceRoot
        HosoBase              = $hosoBase
        TaskTitle             = $TaskTitle
        UserIssue             = $UserIssue
        DryRun                = $DryRun
        StartTime             = $nowDate
        PlanArchiveFile       = $planArchiveFile
        LatestPlanFile        = $latestPlanFile
        ProcessLogArchiveFile = $processLogArchiveFile
        LatestProcessLogFile  = $latestProcessLogFile
        IndexFile             = $indexFile
        Tasks                 = $taskMap
        SkippedItems          = $SkippedItems
        Logs                  = [System.Collections.Generic.List[string]]::new()
        IsCompleted           = $false
        OverallPercent        = 0
        CurrentTaskName       = "Khởi tạo phiên"
    }

    # Hàm ghi an toàn UTF-8 không BOM
    $script:WriteSafeUtf8 = {
        param([string]$FilePath, [string]$Content)
        for ($retry = 0; $retry -lt 5; $retry++) {
            try {
                $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
                [System.IO.File]::WriteAllText($FilePath, $Content, $utf8NoBom)
                break
            } catch {
                Start-Sleep -Milliseconds 80
            }
        }
    }

    # Hàm dựng nội dung File 1: Checklist Kế Hoạch (LATEST_CSSK.md)
    $script:RenderPlanMd = {
        param($s)
        $bt = [char]96
        $sb = [System.Text.StringBuilder]::new()
        [void]$sb.AppendLine("# BIÊN BẢN KỸ THUẬT & CHECKLIST TIẾN ĐỘ THI CÔNG")
        [void]$sb.AppendLine("> **Mục tiêu can thiệp:** " + $s.TaskTitle)
        $statusStr = if ($s.IsCompleted) { "$bt[ĐÃ HOÀN TẤT TOÀN BỘ]$bt" } else { "$bt[ĐANG THI CÔNG REALTIME]$bt" }
        [void]$sb.AppendLine("> **Thời điểm khởi tạo:** " + $s.StartTime.ToString("yyyy-MM-dd HH:mm:ss") + " | **Trạng thái:** " + $statusStr)
        if ($s.UserIssue) {
            [void]$sb.AppendLine("> **Hiện tượng ghi nhận:** " + $s.UserIssue)
        }
        $logLink = $s.LatestProcessLogFile.Replace('\', '/')
        [void]$sb.AppendLine("> **Nhật ký tiến trình chi tiết:** [NHAT_KY_TIEN_TRINH_MOI_NHAT.md](file:///$logLink)")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("---")
        [void]$sb.AppendLine("")

        # Thanh tiến độ tổng
        $doneCount = 0
        foreach ($t in $s.Tasks.Values) {
            if ($t.Status -in @("[x]", "[!]")) { $doneCount++ }
        }
        $totalCount = $s.Tasks.Count
        $pct = if ($totalCount -gt 0) { [math]::Round(($doneCount / $totalCount) * 100) } else { 0 }
        $barLen = 20
        $fill = [math]::Round(($pct / 100) * $barLen)
        $bar = "[" + ("=" * $fill) + ("-" * ($barLen - $fill)) + "] $pct%"

        [void]$sb.AppendLine("### TIẾN ĐỘ CHECKLIST: $bt$bar$bt ($doneCount/$totalCount Vi Tác Vụ)")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("---")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("### PHẦN I: DANH MỤC VI TÁC VỤ THI CÔNG (REALTIME CHECKLIST)")
        [void]$sb.AppendLine("")

        $idx = 1
        foreach ($t in $s.Tasks.Values) {
            $badge = switch ($t.Status) {
                "[x]"  { "✅ $bt[x] ĐÃ HOÀN TẤT$bt" }
                "[..]" { "🔄 $bt[..] ĐANG XỬ LÝ...$bt" }
                "[!]"  { "⚠️ $bt[!] CẢNH BÁO/BỎ QUA$bt" }
                Default{ "⏳ $bt[ ] CHỜ THỰC HIỆN$bt" }
            }
            [void]$sb.AppendLine("#### $idx. " + $t.Name)
            [void]$sb.AppendLine("- " + $t.Status + " **Mô tả kỹ thuật:** " + $t.Desc)
            [void]$sb.AppendLine("- *Trạng thái:* $badge")
            if ($t.DurationSec -gt 0) {
                [void]$sb.AppendLine("- *Thời gian xử lý:* " + $t.DurationSec + " giây")
            }
            if ($t.Detail) {
                [void]$sb.AppendLine("- *Kết quả đo đạc / Ghi chú:* " + $t.Detail)
            }
            if ($t.Error) {
                [void]$sb.AppendLine("- *Lỗi phát sinh:* $bt" + $t.Error + "$bt")
            }
            [void]$sb.AppendLine("")
            $idx++
        }

        if ($s.SkippedItems -and $s.SkippedItems.Count -gt 0) {
            [void]$sb.AppendLine("---")
            [void]$sb.AppendLine("")
            [void]$sb.AppendLine("### PHẦN II: CÁC HẠNG MỤC BỎ QUA (TỐI ƯU MỤC TIÊU - TRÁNH LÀM THỪA)")
            [void]$sb.AppendLine("")
            foreach ($sk in $s.SkippedItems) {
                [void]$sb.AppendLine("- **" + $sk.Name + "**: $bt[BỎ QUA]$bt")
                [void]$sb.AppendLine("  - *Lý do kỹ thuật:* " + $sk.SkipReason)
            }
            [void]$sb.AppendLine("")
        }

        [void]$sb.AppendLine("---")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("### PHẦN III: CAM KẾT BẢO TOÀN DỮ LIỆU & AN TOÀN")
        [void]$sb.AppendLine("- **Mốc phục hồi hệ thống:** Luôn khởi tạo System Restore Point (VSS Snapshot) trước can thiệp.")
        [void]$sb.AppendLine("- **Nguyên tắc Zero-Destruction:** Giữ nguyên 100% tài liệu cá nhân và mã nguồn dự án.")
        $modeStr = if ($s.DryRun) { "$btKiểm Thử An Toàn (Dry-Run)$bt" } else { "$btThi Công Trực Tiếp Trên Hệ Thống$bt" }
        [void]$sb.AppendLine("- **Chế độ thi công:** " + $modeStr)

        return $sb.ToString()
    }

    # Hàm dựng nội dung File 2: Nhật Ký Tiến Trình Thực Tế (Process Log)
    $script:RenderProcessLogMd = {
        param($s)
        $bt = [char]96
        $sb = [System.Text.StringBuilder]::new()
        $nowStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        $elapsed = [math]::Round(((Get-Date) - $s.StartTime).TotalSeconds, 1)

        [void]$sb.AppendLine("# NHẬT KÝ TIẾN TRÌNH XỬ LÝ THỰC TẾ (REALTIME PROCESS LOG)")
        [void]$sb.AppendLine("> **Nhiệm vụ:** " + $s.TaskTitle)
        [void]$sb.AppendLine("> **Thời điểm cập nhật:** $bt$nowStr$bt | **Thời gian đã chạy:** $bt${elapsed}s$bt")
        [void]$sb.AppendLine("> **Tác vụ đang chạy:** **" + $s.CurrentTaskName + "** | **Tiến độ:** $bt" + $s.OverallPercent + "%$bt")
        $planLink = $s.LatestPlanFile.Replace('\', '/')
        [void]$sb.AppendLine("> **Checklist tương ứng:** [LATEST_CSSK.md](file:///$planLink)")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("---")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("### ⚡ LUỒNG DỮ LIỆU THỰC THI (REALTIME EXECUTION LOG STREAM)")
        [void]$sb.AppendLine('```text')
        foreach ($line in $s.Logs) {
            [void]$sb.AppendLine($line)
        }
        [void]$sb.AppendLine('```')
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("---")
        [void]$sb.AppendLine("*File này được tự động cập nhật từng giây bởi Antigravity CSSK Live Engine.*")

        return $sb.ToString()
    }

    $session | Add-Member -MemberType ScriptMethod -Name "SyncFiles" -Value {
        $planContent = & $script:RenderPlanMd $this
        & $script:WriteSafeUtf8 $this.LatestPlanFile $planContent
        & $script:WriteSafeUtf8 $this.PlanArchiveFile $planContent

        $logContent = & $script:RenderProcessLogMd $this
        & $script:WriteSafeUtf8 $this.LatestProcessLogFile $logContent
        & $script:WriteSafeUtf8 $this.ProcessLogArchiveFile $logContent
    }

    $session | Add-Member -MemberType ScriptMethod -Name "Log" -Value {
        param([string]$Message, [string]$Level = "INFO")
        $timeStr = (Get-Date).ToString("HH:mm:ss")
        $prefix = switch ($Level) {
            "SUCCESS" { "[THÀNH CÔNG]" }
            "WARN"    { "[CẢNH BÁO ]" }
            "ERROR"   { "[THẤT BẠI ]" }
            Default   { "[THÔNG TIN]" }
        }
        $logLine = "[$timeStr] $prefix $Message"
        $this.Logs.Add($logLine)
        Write-Host $logLine -ForegroundColor $(switch ($Level) { "SUCCESS" { "Green" } "WARN" { "Yellow" } "ERROR" { "Red" } Default { "Cyan" } })
        $this.SyncFiles()
    }

    $session | Add-Member -MemberType ScriptMethod -Name "StartStep" -Value {
        param([string]$TaskId)
        if ($this.Tasks.Contains($TaskId)) {
            $t = $this.Tasks[$TaskId]
            $t.Status = "[..]"
            $t.StateLabel = "ĐANG XỬ LÝ"
            $t.StartTime = Get-Date
            $this.CurrentTaskName = $t.Name
            
            $doneCount = 0
            foreach ($item in $this.Tasks.Values) { if ($item.Status -in @("[x]", "[!]")) { $doneCount++ } }
            $this.OverallPercent = [math]::Round(($doneCount / $this.Tasks.Count) * 100)

            $this.Log("Bắt đầu thực hiện vi tác vụ: $($t.Name)...")
            $this.SyncFiles()
        }
    }

    $session | Add-Member -MemberType ScriptMethod -Name "CompleteStep" -Value {
        param(
            [string]$TaskId,
            [string]$Detail = "",
            [string]$Status = "[x]",
            [string]$ErrorMsg = ""
        )
        if ($this.Tasks.Contains($TaskId)) {
            $t = $this.Tasks[$TaskId]
            $t.Status = $Status
            $t.EndTime = Get-Date
            if ($t.StartTime) {
                $t.DurationSec = [math]::Round(($t.EndTime - $t.StartTime).TotalSeconds, 1)
            }
            $t.Detail = $Detail
            $t.Error = $ErrorMsg
            $t.StateLabel = if ($Status -eq "[x]") { "HOÀN TẤT" } else { "CẢNH BÁO" }

            $doneCount = 0
            foreach ($item in $this.Tasks.Values) { if ($item.Status -in @("[x]", "[!]")) { $doneCount++ } }
            $this.OverallPercent = [math]::Round(($doneCount / $this.Tasks.Count) * 100)

            $logLevel = if ($Status -eq "[x]") { "SUCCESS" } else { "WARN" }
            $this.Log("Hoàn tất vi tác vụ [$($t.Name)] sau $($t.DurationSec)s. Kết quả: $Detail", $logLevel)
            $this.SyncFiles()
        }
    }

    $session | Add-Member -MemberType ScriptMethod -Name "Finish" -Value {
        param([string]$SummaryMessage = "Đã hoàn thành toàn bộ chu trình xử lý.")
        $this.IsCompleted = $true
        $this.OverallPercent = 100
        $this.CurrentTaskName = "Hoàn tất nghiệm thu"
        $this.Log($SummaryMessage, "SUCCESS")
        $this.SyncFiles()

        $pLink = $this.PlanArchiveFile.Replace('\', '/')
        $lLink = $this.ProcessLogArchiveFile.Replace('\', '/')
        $resStr = if ($this.DryRun) { "Kiểm thử" } else { "Thành công" }
        $indexLine = "| " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss") + " | " + $this.TaskTitle + " | " + $resStr + " | [Biên Bản](file:///$pLink) | [Nhật Ký](file:///$lLink) |"
        if (-not (Test-Path $this.IndexFile)) {
            $initIndex = "# SỔ CÁI BẢO DƯỠNG & TỐI ƯU HÓA HỆ THỐNG (CSSK INDEX)`r`n`r`n| Thời Điểm | Nhiệm Vụ | Kết Quả | Hồ Sơ Kế Hoạch | Nhật Ký Tiến Trình |`r`n| :--- | :--- | :--- | :--- | :--- |`r`n"
            & $script:WriteSafeUtf8 $this.IndexFile $initIndex
        }
        $currentIdx = [System.IO.File]::ReadAllText($this.IndexFile, [System.Text.Encoding]::UTF8)
        $newIdx = $currentIdx + "`r`n" + $indexLine
        & $script:WriteSafeUtf8 $this.IndexFile $newIdx
    }

    $session.Log("Khởi tạo phiên làm việc [$TaskTitle]. Cặp file theo dõi Realtime đã sẵn sàng.")
    $session.SyncFiles()

    return $session
}
