param(
    [string]$TargetDirectory = (Join-Path $env:USERPROFILE ".gemini\config"),
    [switch]$SkipSessionRestore
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
# Validate the complete plan before any cleanup or configuration write.
foreach ($name in ($directoryNames + $fileNames + @("config.json", "hooks.json"))) {
    Assert-TargetChild (Join-Path $targetDir $name)
}
$sourceFile = Join-Path $PSScriptRoot "config.json"
$defaults = ConvertTo-Map (Get-Content -LiteralPath $sourceFile -Raw | ConvertFrom-Json)
$targetFile = Join-Path $targetDir "config.json"
$merged = @{}
if (Test-Path -LiteralPath $targetFile) {
    $merged = ConvertTo-Map (Get-Content -LiteralPath $targetFile -Raw | ConvertFrom-Json)
    if ($merged -isnot [hashtable]) { throw "Existing config must be a JSON object" }
}
Merge-Defaults $merged $defaults
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
if (Test-Path -LiteralPath $targetFile) {
    Copy-Item -LiteralPath $targetFile -Destination (Join-Path $targetDir ("config.json.bak_" + [Guid]::NewGuid().ToString("N")))
}
[IO.File]::WriteAllText($targetFile, ($merged | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
foreach ($name in $directoryNames) {
    $source = Join-Path $repoRoot $name
    $destination = Join-Path $targetDir $name
    if (-not (Test-Path -LiteralPath $source)) { continue }
    Assert-TargetChild $destination
    if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}
foreach ($name in $fileNames) {
    $source = Join-Path $repoRoot $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $targetDir $name) -Force }
}
$hooksSource = Join-Path $repoRoot ".agent\hooks.json"
if (Test-Path -LiteralPath $hooksSource) { Copy-Item -LiteralPath $hooksSource -Destination (Join-Path $targetDir "hooks.json") -Force }
# Portable destinations never import sessions into the user's global profile.
if (-not $SkipSessionRestore -and -not $PSBoundParameters.ContainsKey("TargetDirectory") -and
    (Test-Path -LiteralPath (Join-Path $repoRoot ".sessions"))) {
    python (Join-Path $repoRoot "scripts\session_manager.py") --action import --repo-dir $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "Session restore failed (exit $LASTEXITCODE)" }
}
Write-Host "Installed to $targetDir; existing user choices preserved."
Write-Host "Runtime tools, permissions, plugin availability and native execution must be verified in Antigravity."
