<#
.SYNOPSIS
    Remove everything ClipForge created: project data, the Whisper model cache, and
    ONLY the system tools that start.ps1 itself installed.

.DESCRIPTION
    Reverses start.ps1 using the manifest it wrote (.clipforge-install.json):
      * Deletes project-local artifacts: .venv, web/node_modules, web/dist,
        out/, tmp/, smoke_out/, *.egg-info, __pycache__, .pytest_cache.
      * Deletes the ClipForge faster-whisper model download from the Hugging Face
        cache (~/.cache/huggingface/hub/models--Systran--faster-whisper-*).
      * Uninstalls (via winget) ONLY the tools that start.ps1 installed because
        they were missing. Tools that pre-existed were never recorded, so a
        pre-existing ffmpeg / Python / Node is left untouched.

    Your source code is NOT deleted. Pass -KeepModels to keep the Whisper cache,
    or -KeepTools to keep even the tools start.ps1 installed.

.PARAMETER KeepModels
    Don't delete the downloaded Whisper model cache.

.PARAMETER KeepTools
    Don't uninstall system tools, even ones start.ps1 installed.

.PARAMETER Yes
    Skip the confirmation prompt.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
#>
[CmdletBinding()]
param(
    [switch]$KeepModels,
    [switch]$KeepTools,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot
$ManifestPath = Join-Path $RepoRoot '.clipforge-install.json'
Set-Location $RepoRoot

function Write-Step($msg)  { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    removed $msg" -ForegroundColor Green }
function Write-Info($msg)  { Write-Host "    $msg" -ForegroundColor Gray }
function Write-Warn2($msg) { Write-Host "    !   $msg" -ForegroundColor Yellow }

function Test-Cmd($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

function Remove-IfExists($path, $label) {
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
        if (-not (Test-Path $path)) { Write-Ok $label } else { Write-Warn2 "could not fully remove $label (in use?)" }
    } else {
        Write-Info "$label - not present, skipping"
    }
}

# ------------------------------------------------------------- load manifest ----

$manifest = $null
if (Test-Path $ManifestPath) {
    try { $manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json } catch {}
}
$installedTools = @()
if ($manifest -and $manifest.installedWinget) {
    $installedTools = @($manifest.installedWinget) | Where-Object { $_ }
}

# ------------------------------------------------------------- confirmation ----

Write-Host "This will remove ClipForge's installed data:" -ForegroundColor Yellow
Write-Host "  - .venv, web/node_modules, web/dist, out/, tmp/, smoke_out/, caches"
if (-not $KeepModels) { Write-Host "  - the downloaded Whisper model cache (Systran/faster-whisper-*)" }
if (-not $KeepTools -and $installedTools.Count -gt 0) {
    Write-Host "  - these system tools that start.ps1 installed: $($installedTools -join ', ')"
} else {
    Write-Host "  - no system tools (none were auto-installed, or -KeepTools set)"
}
Write-Host "  Your source code is NOT touched." -ForegroundColor Gray

if (-not $Yes) {
    $ans = Read-Host "`nProceed? (y/N)"
    if ($ans -notin @('y', 'Y', 'yes', 'Yes')) { Write-Host "Aborted."; exit 0 }
}

# ------------------------------------------------------------- project data ----

Write-Step "Removing project-local data"
Remove-IfExists (Join-Path $RepoRoot '.venv')            '.venv'
Remove-IfExists (Join-Path $RepoRoot 'web\node_modules') 'web/node_modules'
Remove-IfExists (Join-Path $RepoRoot 'web\dist')         'web/dist'
Remove-IfExists (Join-Path $RepoRoot 'web\.vite')        'web/.vite'
Remove-IfExists (Join-Path $RepoRoot 'out')              'out/'
Remove-IfExists (Join-Path $RepoRoot 'tmp')              'tmp/'
Remove-IfExists (Join-Path $RepoRoot 'smoke_out')        'smoke_out/'
Remove-IfExists (Join-Path $RepoRoot '.pytest_cache')    '.pytest_cache'

# egg-info + __pycache__ trees
Get-ChildItem -Path $RepoRoot -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '__pycache__' -or $_.Name -like '*.egg-info' } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
Write-Ok "Python caches (__pycache__, *.egg-info)"

# ---------------------------------------------------------- whisper model cache ----

if (-not $KeepModels) {
    Write-Step "Removing the Whisper model cache"
    $hubRoots = @()
    if ($env:HF_HOME) { $hubRoots += (Join-Path $env:HF_HOME 'hub') }
    $hubRoots += (Join-Path $env:USERPROFILE '.cache\huggingface\hub')
    $found = $false
    foreach ($hub in ($hubRoots | Select-Object -Unique)) {
        if (Test-Path $hub) {
            Get-ChildItem -Path $hub -Directory -Filter 'models--Systran--faster-whisper-*' -ErrorAction SilentlyContinue |
                ForEach-Object {
                    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
                    Write-Ok "model cache $($_.Name)"
                    $found = $true
                }
        }
    }
    if (-not $found) { Write-Info "no ClipForge Whisper model cache found" }
} else {
    Write-Info "Keeping Whisper model cache (-KeepModels)"
}

# ------------------------------------------------------------- system tools ----

if (-not $KeepTools -and $installedTools.Count -gt 0) {
    Write-Step "Uninstalling system tools that start.ps1 installed"
    if (-not (Test-Cmd 'winget')) {
        Write-Warn2 "winget not available; skipping. Uninstall manually if desired: $($installedTools -join ', ')"
    } else {
        foreach ($id in $installedTools) {
            Write-Info "winget uninstall $id ..."
            winget uninstall --id $id -e --silent 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "tool $id" }
            else { Write-Warn2 "could not uninstall $id (exit=$LASTEXITCODE) - remove manually if needed" }
        }
    }
} elseif ($KeepTools) {
    Write-Info "Keeping system tools (-KeepTools)"
} else {
    Write-Info "No auto-installed system tools to remove"
}

# ------------------------------------------------------------- manifest ----

Remove-IfExists $ManifestPath '.clipforge-install.json (install manifest)'

Write-Host "`nClipForge uninstalled. Source code left intact." -ForegroundColor Cyan
