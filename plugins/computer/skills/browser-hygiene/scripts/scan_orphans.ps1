# Scan script for automated browsers and orphaned development servers
[CmdletBinding()]
param(
    [switch]$JsonOutput
)

$ErrorActionPreference = 'SilentlyContinue'

$allProcesses = Get-CimInstance Win32_Process
$procDict = @{}
foreach ($p in $allProcesses) {
    $procDict[[int]$p.ProcessId] = $p
}

# 1. SCAN BROWSERS
$browserNames = @('chrome.exe', 'chromium.exe', 'chrome-headless-shell.exe', 'msedge.exe')
$browsers = $allProcesses | Where-Object { $browserNames -contains $_.Name }

$flaggedBrowsers = @()
$normalBrowsersCount = 0

foreach ($b in $browsers) {
    $cmd = $b.CommandLine
    if ([string]::IsNullOrWhiteSpace($cmd)) { continue }

    $isHeadless = $cmd -match '--headless'
    $hasDebugPort = $cmd -match '--remote-debugging-port'
    $hasUserDataDir = $cmd -match '--user-data-dir'
    $hasTempProfile = $cmd -match '(?i)(temp|tmp|\.agent|playwright|puppeteer|scoped_dir|\.brain|scratch)'
    $isTestShell = ($b.Name -eq 'chrome-headless-shell.exe') -or ($cmd -match 'chrome-headless-shell')

    if ($isHeadless -or $hasDebugPort -or ($hasUserDataDir -and $hasTempProfile) -or $isTestShell) {
        $parentPid = [int]$b.ParentProcessId
        $parentAlive = $procDict.ContainsKey($parentPid)
        $parentName = if ($parentAlive) { $procDict[$parentPid].Name } else { 'DEAD / NOT FOUND' }

        $proc = Get-Process -Id $b.ProcessId -ErrorAction SilentlyContinue
        $wsMB = if ($proc) { [math]::Round($proc.WorkingSet64 / 1MB, 2) } else { 0 }
        $cpuSec = if ($proc) { [math]::Round($proc.CPU, 2) } else { 0 }
        $startTime = if ($proc) { $proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'N/A' }

        $profileDir = 'N/A'
        if ($cmd -match '--user-data-dir=([^\s]+)') {
            $profileDir = $matches[1].Trim('"''')
        }

        $reasons = [System.Collections.Generic.List[string]]::new()
        if ($isHeadless) { $reasons.Add("Headless") }
        if ($hasDebugPort) { $reasons.Add("DebugPort") }
        if ($hasTempProfile) { $reasons.Add("TempProfile") }
        if ($isTestShell) { $reasons.Add("TestShell") }

        $flaggedBrowsers += [PSCustomObject]@{
            PID = $b.ProcessId
            Name = $b.Name
            ParentPID = $parentPid
            ParentStatus = if ($parentAlive) { "Alive ($parentName)" } else { "Dead (Orphaned)" }
            StartTime = $startTime
            MemoryMB = $wsMB
            CPUSec = $cpuSec
            ProfileDir = $profileDir
            Reason = ($reasons -join ", ")
            CommandLine = $cmd
        }
    } else {
        $normalBrowsersCount++
    }
}

# 2. SCAN DEV RUNTIMES / SERVERS
$devNames = @('node.exe', 'python.exe', 'pythonw.exe', 'uvicorn.exe')
$devProcesses = $allProcesses | Where-Object { $devNames -contains $_.Name }

$flaggedDev = @()

foreach ($d in $devProcesses) {
    $cmd = $d.CommandLine
    if ([string]::IsNullOrWhiteSpace($cmd)) { continue }

    $parentPid = [int]$d.ParentProcessId
    $parentAlive = $procDict.ContainsKey($parentPid)
    $parentName = if ($parentAlive) { $procDict[$parentPid].Name } else { 'DEAD / NOT FOUND' }

    $isServerOrDev = $cmd -match '(?i)(vite|next|preview|serve|http-server|uvicorn|fastapi|flask|streamlit|playwright|puppeteer|browser)'
    $isOrphan = -not $parentAlive

    if ($isServerOrDev -or $isOrphan) {
        $proc = Get-Process -Id $d.ProcessId -ErrorAction SilentlyContinue
        $wsMB = if ($proc) { [math]::Round($proc.WorkingSet64 / 1MB, 2) } else { 0 }
        $cpuSec = if ($proc) { [math]::Round($proc.CPU, 2) } else { 0 }
        $startTime = if ($proc) { $proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'N/A' }

        $flaggedDev += [PSCustomObject]@{
            PID = $d.ProcessId
            Name = $d.Name
            ParentPID = $parentPid
            ParentStatus = if ($parentAlive) { "Alive ($parentName)" } else { "Dead (Orphaned)" }
            StartTime = $startTime
            MemoryMB = $wsMB
            CPUSec = $cpuSec
            IsServer = $isServerOrDev
            IsOrphan = $isOrphan
            CommandLine = $cmd
        }
    }
}

# 3. LISTENING DEV PORTS
$commonPorts = @(3000, 3001, 4173, 5000, 5173, 5174, 8000, 8080, 8081, 8888, 9222, 9229, 9323)
$activePorts = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {
    $_.LocalPort -in $commonPorts
}

$portResults = @()
if ($activePorts) {
    foreach ($pt in $activePorts) {
        $ownerName = if ($procDict.ContainsKey([int]$pt.OwningProcess)) { $procDict[[int]$pt.OwningProcess].Name } else { "UNKNOWN" }
        $portResults += [PSCustomObject]@{
            Port = $pt.LocalPort
            PID = $pt.OwningProcess
            ProcessName = $ownerName
        }
    }
}

# 4. TEMP DIRECTORIES
$tempDirs = Get-ChildItem -Path $env:TEMP -Directory -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '(?i)(playwright|puppeteer|chrome-test|scoped_dir|headless)'
} | Select-Object FullName, LastWriteTime

if ($JsonOutput) {
    [PSCustomObject]@{
        FlaggedBrowsers = $flaggedBrowsers
        NormalBrowsersCount = $normalBrowsersCount
        FlaggedDev = $flaggedDev
        ActiveDevPorts = $portResults
        TempAutomationProfiles = $tempDirs
    } | ConvertTo-Json -Depth 4
} else {
    Write-Host "================================================================="
    Write-Host "1. AUTOMATED / HEADLESS BROWSERS"
    Write-Host "================================================================="
    Write-Host "Normal daily browsers protected: $normalBrowsersCount"
    Write-Host "Automated/flagged browsers found: $($flaggedBrowsers.Count)"
    if ($flaggedBrowsers.Count -gt 0) {
        $flaggedBrowsers | Format-Table PID, Name, ParentPID, ParentStatus, MemoryMB, StartTime, Reason, ProfileDir -AutoSize
    }

    Write-Host ""
    Write-Host "================================================================="
    Write-Host "2. DEV RUNTIMES / SERVERS & ORPHANED PROCESSES"
    Write-Host "================================================================="
    Write-Host "Flagged dev runtimes / orphans: $($flaggedDev.Count)"
    if ($flaggedDev.Count -gt 0) {
        $flaggedDev | Format-Table PID, Name, ParentPID, ParentStatus, MemoryMB, StartTime, IsServer, IsOrphan -AutoSize
    }

    Write-Host ""
    Write-Host "================================================================="
    Write-Host "3. ACTIVE DEV LISTENING PORTS"
    Write-Host "================================================================="
    if ($portResults.Count -gt 0) {
        $portResults | Format-Table Port, PID, ProcessName -AutoSize
    } else {
        Write-Host "No dev ports (3000, 5173, 8000, 9222...) are currently listening."
    }

    Write-Host ""
    Write-Host "================================================================="
    Write-Host "4. LEFTOVER TEMP PROFILES"
    Write-Host "================================================================="
    if ($tempDirs) {
        $tempDirs | Format-Table FullName, LastWriteTime -AutoSize
    } else {
        Write-Host "No leftover browser automation temp profiles found."
    }
}
