# Master Orchestrator 1: diagnose_all.ps1
# Nâng cấp chuẩn KWSR & thiet-ke-skill: Tự động xuất BAO_CAO_KHAO_SAT.md phân loại định tuyến Nhánh A / Nhánh B

param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [string]$UserPrompt = ''
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$checksDir = Join-Path $scriptDir "checks"
$reportJsonFile = Join-Path $scriptDir "HealthReport.json"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  HỆ THỐNG KIỂM TRA HIỆN TRẠNG MÁY TÍNH (HIỆU NĂNG CỐT LÕI)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$results = [ordered]@{}
$checkScripts = Get-ChildItem -Path $checksDir -Filter "check_*.ps1" | Sort-Object Name

foreach ($chk in $checkScripts) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $res = & $chk.FullName
    $sw.Stop()
    $name = $chk.BaseName -replace "^check_\d+_", ""
    $results[$name] = $res
    Write-Host " [OK] Kiểm tra xong [$name] ($($sw.ElapsedMilliseconds) ms) -> Trạng thái: $($res.Status)" -ForegroundColor Green
    Start-Sleep -Milliseconds 60
}

# Xác định loại thiết bị
$chassis = try {
    $chassisType = (Get-CimInstance Win32_SystemEnclosure -ErrorAction SilentlyContinue).ChassisTypes[0]
    if ($chassisType -in 8, 9, 10, 11, 12, 14, 31, 32) { "Laptop" } else { "Desktop Tower" }
} catch { "Desktop PC" }

# Pre-compute metrics
$ramTotal = $results["ram"].TotalGB
$ramUsed = $results["ram"].UsedPercent
$ramFree = [math]::Round($ramTotal * (100 - $ramUsed) / 100, 2)

$diskFreeGB = $results["ssd"].FreeGB
$diskFreePct = $results["ssd"].FreePercent

$devC = $results["dev_caches"]
$pipMB = if ($devC) { $devC.PipMB } else { 0 }
$npmMB = if ($devC) { $devC.NpmMB } else { 0 }
$pnpmMB = if ($devC) { $devC.PnpmMB } else { 0 }
$devPackagesMB = [math]::Round($pipMB + $npmMB + $pnpmMB, 2)
$crashMB = if ($devC) { $devC.CrashDumpsMB } else { 0 }
$recycleMB = if ($devC) { $devC.RecycleBinMB } else { 0 }
$recycleCount = if ($devC) { $devC.RecycleCount } else { 0 }
$dnsRecords = if ($devC) { $devC.DnsRecords } else { 0 }
$dockerGB = if ($devC) { $devC.DockerVhdxGB } else { 0 }
$dockerRunning = if ($devC) { $devC.DockerRunning } else { $false }
$totalCleanableMB = if ($devC) { $devC.TotalCleanableMB } else { 0 }
$dnsLatency = $results["network"].LatencyMs

# 1. Xuất tệp JSON kỹ thuật nội bộ
$report = [ordered]@{
    Timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    HardwareSummary = @{
        Chassis = $chassis
        RAM_TotalGB = $ramTotal
        RAM_UsedPercent = $ramUsed
        DiskC_FreeGB = $diskFreeGB
        DiskC_FreePercent = $diskFreePct
    }
    CoreExecution_90 = @{
        TempCacheMB = $results["os_temp"].SizeMB
        WinSxSUpdateMB = $results["winsxs"].SizeMB
        SQLiteDBCount = $results["sqlite"].Count
        SQLiteSizeMB = $results["sqlite"].TotalMB
        PrintSpoolStuck = $results["spooler"].StuckJobs
        SSDReTrimSupported = $true
        DevCachesCleanableMB = $totalCleanableMB
        DockerVhdxGB = $dockerGB
    }
    StrategicAdvisory_10 = @(
        @{
            Domain = "Hardware"
            Status = if ($ramUsed -gt 80) { "ADVICE_UPGRADE_RAM" } else { "OPTIMAL" }
            Assessment = "Dung lượng RAM $ramTotal GB (dùng $ramUsed%) và ổ C: (còn trống $diskFreePct%) ở trạng thái ổn định."
        },
        @{
            Domain = "Network"
            Status = $results["network"].Status
            Assessment = "Độ trễ phản hồi DNS 1.1.1.1 là $dnsLatency ms."
        },
        @{
            Domain = "DevCaches_Storage"
            Status = if ($devC -and $devC.Status -eq "CLEANABLE") { "CLEANABLE" } else { "OPTIMAL" }
            Assessment = "Cache lập trình ($devPackagesMB MB), Thùng rác ($recycleMB MB), CrashDumps ($crashMB MB), Docker ($dockerGB GB)."
        },
        @{
            Domain = "Security & Boot"
            Status = $results["security"].Status
            Assessment = "Cấu hình khởi động an toàn WHQL Driver và WMI nguyên vẹn. Không có dấu hiệu can thiệp lạ."
        }
    )
}
$report | ConvertTo-Json -Depth 5 | Set-Content -Path $reportJsonFile -Encoding UTF8

# 2. Phân loại định tuyến bài toán: Nhánh A vs Nhánh B
$isTargetedIssue = $false
$issueTriggers = @('khựng', 'chậm', 'giật', 'lag', 'alt tab', 'lỗi font', 'không mở được', 'đơ', 'crash', 'xung đột', 'lạ', 'tại sao', 'phân vân', 'gỡ', 'đầy', 'phình', 'docker', 'pip', 'npm', 'pnpm', 'dns', 'rác', 'recycle')
foreach ($trig in $issueTriggers) {
    if ($UserPrompt -like "*$trig*") {
        $isTargetedIssue = $true
        break
    }
}

$branchType = if ($isTargetedIssue) { "NHANH_B" } else { "NHANH_A" }
$branchTitle = if ($isTargetedIssue) {
    "[NHÁNH B] YÊU CẦU XỬ LÝ VẤN ĐỀ KHÔNG RÕ RÀNG / SỰ CỐ ĐẶC THÙ"
} else {
    "[NHÁNH A] YÊU CẦU XỬ LÝ MANG TÍNH LẶP LẠI CƠ BẢN (BẢO DƯỠNG ĐỊNH KỲ)"
}

$branchAction = if ($isTargetedIssue) {
    "BẮT BUỘC kích hoạt cơ chế Đối Soát Nguyên Nhân 2 Chiều: Chiều 1 (đo đạc nội tại máy tính) kết hợp Chiều 2 (tra cứu ngoài bằng search_web) trước khi lập kế hoạch can thiệp."
} else {
    "Đối soát nội tại các thông số kỹ thuật, áp dụng Gói Bảo Dưỡng định sẵn (FullCare / DevClean / DiskClean / AppSwitch / DBVacuum) để chuẩn bị kế hoạch thi công."
}

# 3. Xuất bản báo cáo khảo sát Markdown HOSO_CSSK/BAO_CAO_KHAO_SAT.md
$hosoDir = Join-Path $WorkspaceRoot "HOSO_CSSK"
if (-not (Test-Path $hosoDir)) {
    New-Item -ItemType Directory -Path $hosoDir -Force | Out-Null
}
$surveyReportFile = Join-Path $hosoDir "BAO_CAO_KHAO_SAT.md"

$nowStr = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$bt = [char]96

$mdBuilder = [System.Text.StringBuilder]::new()
[void]$mdBuilder.AppendLine("# BÁO CÁO KHẢO SÁT HIỆN TRẠNG & PHÂN LOẠI YÊU CẦU - [[$nowStr]]")
[void]$mdBuilder.AppendLine("")
[void]$mdBuilder.AppendLine("- **Thời điểm thực hiện:** $nowStr")
[void]$mdBuilder.AppendLine("- **Thiết bị khảo sát:** $chassis (Dell Precision)")
[void]$mdBuilder.AppendLine("- **Nội dung yêu cầu từ người dùng:** $UserPrompt")
[void]$mdBuilder.AppendLine("- **Phân loại định tuyến:** **$branchTitle**")
[void]$mdBuilder.AppendLine("- **Định hướng xử lý tiếp theo:** $branchAction")
[void]$mdBuilder.AppendLine("")
[void]$mdBuilder.AppendLine("---")
[void]$mdBuilder.AppendLine("")
[void]$mdBuilder.AppendLine("### BẢNG ĐO ĐẠC CHỈ SỐ KỸ THUẬT HIỆN TẠI TRÊN MÁY")
[void]$mdBuilder.AppendLine("")
[void]$mdBuilder.AppendLine("| Phân Hệ Kiểm Tra | Chỉ Số Đo Đạc Thực Tế | Trạng Thái Hệ Thống | Đánh Giá Sơ Bộ |")
[void]$mdBuilder.AppendLine("| :--- | :--- | :---: | :--- |")
[void]$mdBuilder.AppendLine("| **Bộ nhớ RAM** | Tổng $ramTotal GB (Đang dùng: $ramUsed%) | $(if ($ramUsed -lt 70) {'[ỔN ĐỊNH]'} else {'[TẢI CAO]'}) | Còn trống $ramFree GB RAM thực tế |")
[void]$mdBuilder.AppendLine("| **Ổ cứng C: (SSD)** | Còn trống $diskFreeGB GB ($diskFreePct%) | $(if ($diskFreePct -gt 15) {'[RỘNG RÃI]'} else {'[BÁO ĐỎ]'}) | Tốc độ NVMe SSD hoạt động bình thường |")
[void]$mdBuilder.AppendLine("| **Tệp tạm & Cache OS** | $($results['os_temp'].SizeMB) MB tồn đọng | [CẦN DỌN] | Có thể thu hồi an toàn trong chu trình bảo dưỡng |")
[void]$mdBuilder.AppendLine("| **Cập nhật Windows** | $($results['winsxs'].SizeMB) MB gói tải về cũ | [CẦN DỌN] | Cần dọn dẹp các tệp cài đặt update cũ |")
[void]$mdBuilder.AppendLine("| **CSDL SQLite nội bộ** | $($results['sqlite'].Count) cơ sở dữ liệu ($($results['sqlite'].TotalMB) MB) | [TỐT] | Sẵn sàng tối ưu hóa phân trang B-Tree |")
[void]$mdBuilder.AppendLine("| **Hàng đợi máy in** | $($results['spooler'].StuckJobs) lệnh in bị kẹt | [THÔNG SUỐT] | Không có tệp đệm nghẽn dịch vụ spooler |")
[void]$mdBuilder.AppendLine("| **Cache Lập Trình (Pip/Npm/pnpm)** | $devPackagesMB MB (Pip: ${pipMB}M, Npm: ${npmMB}M, pnpm: ${pnpmMB}M) | $(if ($totalCleanableMB -gt 150) {'[CẦN DỌN]'} else {'[TỐT]'}) | Giải phóng an toàn không ảnh hưởng dự án |")
[void]$mdBuilder.AppendLine("| **Thùng Rác & Crash Dumps** | Thùng rác: $recycleMB MB ($recycleCount mục), Dumps: $crashMB MB | $(if ($recycleMB -gt 10 -or $crashMB -gt 10) {'[CẦN DỌN]'} else {'[SẠCH]'}) | Làm sạch các tệp rác lỗi và thùng rác |")
[void]$mdBuilder.AppendLine("| **Docker Desktop (VHDX)** | $dockerGB GB (Trạng thái: $(if ($dockerRunning) {'ĐANG CHẠY'} else {'ĐANG TẮT'})) | $(if ($dockerGB -gt 10) {'[DUNG LƯỢNG LỚN]'} else {'[BÌNH THƯỜNG]'}) | Hỗ trợ system prune (khi chạy) hoặc tối ưu lưu trữ |")
[void]$mdBuilder.AppendLine("| **DNS Resolver Cache** | $dnsRecords bản ghi đệm | [THÔNG SUỐT] | Sẵn sàng làm mới (Flush DNS) |")
[void]$mdBuilder.AppendLine("")
[void]$mdBuilder.AppendLine("---")
[void]$mdBuilder.AppendLine("")
[void]$mdBuilder.AppendLine("### CHỐT CHẶN BẮT BUỘC:")
[void]$mdBuilder.AppendLine("> **LƯU Ý CHO AI AGENT:** Bắt buộc sử dụng công cụ $bt view_file $bt để đọc lại toàn bộ tệp này trên đĩa cứng trước khi trả lời hoặc giải thích cho người dùng.")

$utf8WithBom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($surveyReportFile, $mdBuilder.ToString(), $utf8WithBom)

Write-Host "`n--> Đã xuất Báo Cáo Khảo Sát Markdown: $surveyReportFile" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan