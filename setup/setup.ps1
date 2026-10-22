param(
    [string]$TargetDirectory = (Join-Path $env:USERPROFILE ".gemini\config"),
    [switch]$SkipSessionRestore,
    [switch]$SkipWatcher
)
$ErrorActionPreference = "Stop"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$targetDir = [IO.Path]::GetFullPath($TargetDirectory)
$separator = [IO.Path]::DirectorySeparatorChar

function Assert-NoReparsePoint([string]$Path) {
    $current = [IO.Path]::GetFullPath($Path)
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Symlink or junction is not allowed: $current"
            }
        }
        $parent = [IO.Directory]::GetParent($current)
        if ($null -eq $parent) { break }
        $current = $parent.FullName
    }
}

function Assert-TargetChild([string]$Path) {
    $absolute = [IO.Path]::GetFullPath($Path)
    if (-not $absolute.StartsWith($targetDir.TrimEnd($separator) + $separator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Copy target escapes destination: $absolute"
    }
    Assert-NoReparsePoint $absolute
    if (Test-Path -LiteralPath $absolute -PathType Container) {
        foreach ($item in (Get-ChildItem -LiteralPath $absolute -Force -Recurse)) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Symlink or junction in cleanup target: $($item.FullName)"
            }
        }
    }
}

function ConvertTo-Map($Value) {
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $map = @{}
        foreach ($property in $Value.PSObject.Properties) { $map[$property.Name] = ConvertTo-Map $property.Value }
        return $map
    }
    return $Value
}

function Merge-Defaults([hashtable]$Existing, [hashtable]$Defaults) {
    foreach ($key in $Defaults.Keys) {
        if (-not $Existing.ContainsKey($key)) { $Existing[$key] = $Defaults[$key] }
        elseif ($Existing[$key] -is [hashtable] -and $Defaults[$key] -is [hashtable]) {
            Merge-Defaults $Existing[$key] $Defaults[$key]
        }
    }
}

function Get-ContentHash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-RelativeFileMap([string]$SourceRoot, [string]$DestinationPrefix) {
    $map = @{}
    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) { return $map }
    $sourceRootFull = [IO.Path]::GetFullPath($SourceRoot).TrimEnd($separator) + $separator
    foreach ($file in Get-ChildItem -LiteralPath $SourceRoot -File -Recurse -Force) {
        if ($file.FullName -match '[\\/](__pycache__|\.pytest_cache|\.git|\.sessions|\.brain)[\\/]' -or
            $file.Extension -in @('.pyc', '.pyo', '.pyd') -or
            $file.Name -in @('.DS_Store', 'Thumbs.db')) {
            continue
        }
        $sourcePath = [IO.Path]::GetFullPath($file.FullName)
        $relative = $sourcePath.Substring($sourceRootFull.Length).Replace('\', '/')
        $targetRelative = (($DestinationPrefix.TrimEnd('/') + '/' + $relative).TrimStart('/'))
        $map[$targetRelative] = $sourcePath
    }
    return $map
}

if ($targetDir.TrimEnd($separator) -eq $repoRoot.TrimEnd($separator) -or
    $repoRoot.StartsWith($targetDir.TrimEnd($separator) + $separator, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Target must not be the repository or an ancestor of the repository"
}
Assert-NoReparsePoint $targetDir
if ((Test-Path -LiteralPath $targetDir) -and -not (Test-Path -LiteralPath $targetDir -PathType Container)) {
    throw "TargetDirectory must be a directory"
}

$directoryNames = @("plugins", "harness", "configs", "agents", "rubrics", "scripts", ".agent", ".agents", "docs", "tests")
$fileNames = @("AGENTS.md", "GEMINI.md", "requirements.txt", ".env.example", "run_harness.py", "README.md", ".gitignore")
foreach ($name in $directoryNames) {
    $packagedSource = [IO.Path]::GetFullPath((Join-Path $repoRoot $name)).TrimEnd($separator)
    if ($targetDir.TrimEnd($separator).Equals($packagedSource, [StringComparison]::OrdinalIgnoreCase) -or
        $targetDir.StartsWith($packagedSource + $separator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target must not be inside a packaged source directory: $packagedSource"
    }
}
# Inventory the source files and validate every target before changing the profile.
$sourceFiles = @{}
foreach ($name in $directoryNames) {
    $sourceFiles += Get-RelativeFileMap (Join-Path $repoRoot $name) $name
}
foreach ($name in $fileNames) {
    $source = Join-Path $repoRoot $name
    if (Test-Path -LiteralPath $source -PathType Leaf) { $sourceFiles[$name] = $source }
}
$hooksSource = Join-Path $repoRoot ".agent\hooks.json"
if (Test-Path -LiteralPath $hooksSource -PathType Leaf) { $sourceFiles["hooks.json"] = $hooksSource }
$manifestPath = Join-Path $targetDir ".harness-hub-managed.json"
$previousManifest = @{ schemaVersion = 1; files = @{} }
if (Test-Path -LiteralPath $manifestPath) {
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Ownership manifest path conflict: $manifestPath" }
    $previousManifest = ConvertTo-Map ([IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json)
    if ($previousManifest -isnot [hashtable] -or $previousManifest.schemaVersion -ne 1 -or $previousManifest.files -isnot [hashtable]) {
        throw "Invalid harness ownership manifest: $manifestPath"
    }
}
$previousFiles = $previousManifest.files
$nextFiles = @{}
$staleFiles = @()
foreach ($relative in $sourceFiles.Keys) {
    $destination = Join-Path $targetDir ($relative.Replace('/', [string]$separator))
    Assert-TargetChild $destination
    if (Test-Path -LiteralPath $destination -PathType Container) { throw "File/directory conflict: $relative" }
    $sourceHash = Get-ContentHash $sourceFiles[$relative]
    $unownedIdentical = $false
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        if (-not $previousFiles.ContainsKey($relative)) {
            if ((Get-ContentHash $destination) -ne $sourceHash) { throw "Unowned file conflict: $relative" }
            $unownedIdentical = $true
        }
    }
    if (-not $unownedIdentical) { $nextFiles[$relative] = $sourceHash }
}
foreach ($relative in $previousFiles.Keys) {
    if ($sourceFiles.ContainsKey($relative)) { continue }
    $destination = Join-Path $targetDir ($relative.Replace('/', [string]$separator))
    Assert-TargetChild $destination
    if ((Test-Path -LiteralPath $destination -PathType Leaf) -and (Get-ContentHash $destination) -eq [string]$previousFiles[$relative]) {
        $staleFiles += $relative
    }
}
foreach ($name in @("config.json", ".harness-hub-managed.json")) { Assert-TargetChild (Join-Path $targetDir $name) }
$sourceFile = Join-Path $PSScriptRoot "config.json"
$defaults = ConvertTo-Map ([IO.File]::ReadAllText($sourceFile, [Text.Encoding]::UTF8) | ConvertFrom-Json)
$targetFile = Join-Path $targetDir "config.json"
$merged = @{}
if (Test-Path -LiteralPath $targetFile) {
    $merged = ConvertTo-Map ([IO.File]::ReadAllText($targetFile, [Text.Encoding]::UTF8) | ConvertFrom-Json)
    if ($merged -isnot [hashtable]) { throw "Existing config must be a JSON object" }
}
Merge-Defaults $merged $defaults
$configBytes = [Text.UTF8Encoding]::new($false).GetBytes(($merged | ConvertTo-Json -Depth 100))
$newManifest = @{ schemaVersion = 1; files = $nextFiles } | ConvertTo-Json -Depth 20
$stageRoot = Join-Path $targetDir (".harness-hub-stage-" + [Guid]::NewGuid().ToString("N"))
$backupRoot = Join-Path $stageRoot "backup"
$stageFilesRoot = Join-Path $stageRoot "files"
$changed = @()
foreach ($relative in $sourceFiles.Keys) {
    $destination = Join-Path $targetDir ($relative.Replace('/', [string]$separator))
    if (-not (Test-Path -LiteralPath $destination -PathType Leaf) -or (Get-ContentHash $destination) -ne (Get-ContentHash $sourceFiles[$relative])) {
        $changed += $relative
    }
}
New-Item -ItemType Directory -Force -Path $stageFilesRoot, $backupRoot | Out-Null
try {
    foreach ($relative in $sourceFiles.Keys) {
        $staged = Join-Path $stageFilesRoot ($relative.Replace('/', [string]$separator))
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $staged) | Out-Null
        Copy-Item -LiteralPath $sourceFiles[$relative] -Destination $staged
    }
    $manifestStaged = Join-Path $stageRoot "manifest.json"
    [IO.File]::WriteAllText($manifestStaged, $newManifest, [Text.UTF8Encoding]::new($false))
    $configStaged = Join-Path $stageRoot "config.json"
    [IO.File]::WriteAllBytes($configStaged, $configBytes)
    if (Test-Path -LiteralPath $targetFile -PathType Leaf) {
        Copy-Item -LiteralPath $targetFile -Destination (Join-Path $targetDir ("config.json.bak_" + [Guid]::NewGuid().ToString("N")))
    }
    $rollback = @{}
    foreach ($relative in ($changed + $staleFiles + @("config.json", ".harness-hub-managed.json"))) {
        $destination = Join-Path $targetDir ($relative.Replace('/', [string]$separator))
        if (Test-Path -LiteralPath $destination -PathType Leaf) {
            $backup = Join-Path $backupRoot ($relative.Replace('/', [string]$separator))
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
            Copy-Item -LiteralPath $destination -Destination $backup
            $rollback[$relative] = $backup
        } elseif (Test-Path -LiteralPath $destination) { throw "File/directory conflict during commit: $relative" }
    }
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    try {
        # Deterministic failure injection is used only by the isolated installer rollback test.
        $failureThreshold = 0
        if ($env:HARNESS_SETUP_TEST_FAIL_AFTER_COPY) {
            if ($env:HARNESS_SETUP_TEST_FAIL_AFTER_COPY -notmatch '^\d+$') { throw "Invalid test failure threshold" }
            $failureThreshold = [int]$env:HARNESS_SETUP_TEST_FAIL_AFTER_COPY
        }
        $committedCopies = 0
        foreach ($relative in $changed) {
            $destination = Join-Path $targetDir ($relative.Replace('/', [string]$separator))
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath (Join-Path $stageFilesRoot ($relative.Replace('/', [string]$separator))) -Destination $destination -Force
            $committedCopies++
            if ($failureThreshold -gt 0 -and $committedCopies -ge $failureThreshold) {
                throw "Injected test failure after $committedCopies committed file copy/copies"
            }
        }
        foreach ($relative in $staleFiles) { Remove-Item -LiteralPath (Join-Path $targetDir ($relative.Replace('/', [string]$separator))) -Force }
        Copy-Item -LiteralPath $configStaged -Destination $targetFile -Force
        Copy-Item -LiteralPath $manifestStaged -Destination $manifestPath -Force
    } catch {
        foreach ($relative in ($changed + $staleFiles + @("config.json", ".harness-hub-managed.json"))) {
            $destination = Join-Path $targetDir ($relative.Replace('/', [string]$separator))
            if ($rollback.ContainsKey($relative)) {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
                Copy-Item -LiteralPath $rollback[$relative] -Destination $destination -Force
            } elseif (Test-Path -LiteralPath $destination -PathType Leaf) { Remove-Item -LiteralPath $destination -Force }
        }
        throw
    }
} finally {
    if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
}
# Portable destinations never import sessions into the user's global profile.
if (-not $SkipSessionRestore -and -not $PSBoundParameters.ContainsKey("TargetDirectory") -and
    (Test-Path -LiteralPath (Join-Path $repoRoot ".sessions"))) {
    python (Join-Path $repoRoot "scripts\session_manager.py") --action import --repo-dir $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "Session restore failed (exit $LASTEXITCODE)" }
}
if (-not $SkipWatcher -and -not $PSBoundParameters.ContainsKey("TargetDirectory")) {
    python (Join-Path $repoRoot "scripts\auto_session_sync.py") --install-startup --repo-dir $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "Watcher startup installation failed (exit $LASTEXITCODE)" }
    Write-Host "Đã tự động tạo và khởi chạy watcher chạy ngầm trong Windows Startup."
}
Write-Host "Installed to $targetDir; existing user choices preserved."
Write-Host "Runtime tools, permissions, plugin availability and native execution must be verified in Antigravity."
