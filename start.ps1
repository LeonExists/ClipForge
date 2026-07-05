<#
.SYNOPSIS
    Install any missing prerequisites, set up ClipForge, build the UI, and launch it.

.DESCRIPTION
    Idempotent. On each run it:
      1. Ensures Python 3.12+, Node.js, and ffmpeg/ffprobe are present
         (installs missing ones via winget and records them in a manifest so
         uninstall.ps1 can reverse EXACTLY what this script added).
      2. Creates a project-local .venv and installs the Python package (yt-dlp
         comes with it as a dependency).
      3. Installs frontend deps and builds the React SPA into web/dist.
      4. Starts FastAPI on one port serving BOTH the UI and the API, and opens
         the browser.

    Nothing is installed system-wide except tools that were already missing;
    pre-existing tools are left untouched and are NOT recorded for removal.

.PARAMETER Port
    Port for the combined UI + API server (default 8000).

.PARAMETER NoBrowser
    Don't auto-open the browser.

.PARAMETER SkipBuild
    Reuse an existing web/dist instead of rebuilding the SPA.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\start.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot
$ManifestPath = Join-Path $RepoRoot '.clipforge-install.json'
Set-Location $RepoRoot

# Keep the window open if anything fails, so the error is readable when this
# script is launched by double-clicking / "Run with PowerShell" (which otherwise
# closes the window the instant the script ends). Skipped when -NoBrowser is set
# (used for automated/headless runs where a blocking prompt would hang).
trap {
    Write-Host "`nClipForge start failed:" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoBrowser) {
        Write-Host "`nPress Enter to close this window..." -ForegroundColor Yellow
        try { Read-Host | Out-Null } catch {}
    }
    exit 1
}

# ---------------------------------------------------------------- helpers ----

function Write-Step($msg)  { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Info($msg)  { Write-Host "    $msg" -ForegroundColor Gray }
function Write-Warn2($msg) { Write-Host "    !   $msg" -ForegroundColor Yellow }

function Test-Cmd($name) {
    [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Test-PortFree([int]$p) {
    # True if nothing is already listening on this TCP port.
    try {
        $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
        return -not $conns
    } catch {
        # Get-NetTCPConnection unavailable (rare): fall back to a bind probe.
        try {
            $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
            $l.Start(); $l.Stop(); return $true
        } catch { return $false }
    }
}

function Resolve-FreePort([int]$preferred) {
    if (Test-PortFree $preferred) { return $preferred }
    Write-Warn2 "Port $preferred is already in use (another app is listening there)."
    for ($p = $preferred + 1; $p -lt $preferred + 20; $p++) {
        if (Test-PortFree $p) {
            Write-Info "Using the next free port: $p"
            return $p
        }
    }
    throw "No free port found in range $preferred-$($preferred + 19). Free one up or pass -Port <n>."
}

function Refresh-Path {
    # winget puts new tools on PATH, but the current process env is stale.
    $machine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

function Load-Manifest {
    if (Test-Path $ManifestPath) {
        try { return Get-Content $ManifestPath -Raw | ConvertFrom-Json } catch {}
    }
    return [pscustomobject]@{ installedWinget = @(); createdVenv = $false }
}

function Save-Manifest($m) {
    $m | ConvertTo-Json -Depth 5 | Set-Content -Path $ManifestPath -Encoding UTF8
}

function Add-WingetToManifest($m, $id) {
    $list = @($m.installedWinget) | Where-Object { $_ }
    if ($list -notcontains $id) { $list += $id }
    $m.installedWinget = $list
    Save-Manifest $m
}

function Install-WingetPackage($id, $friendly) {
    if (-not (Test-Cmd 'winget')) {
        throw "winget is not available, so '$friendly' can't be auto-installed. " +
              "Install '$friendly' manually (or install 'App Installer' from the Microsoft Store) and re-run."
    }
    Write-Info "Installing $friendly via winget ($id)..."
    winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install '$friendly' (id=$id, exit=$LASTEXITCODE)."
    }
    Refresh-Path
}

# Resolve a Python launcher that reports >= 3.12.
# Returns a pscustomobject { Exe = <string>; PyArgs = <string[]> } or $null.
# (Structured object avoids two PowerShell array traps: single-element arrays
#  auto-unwrap to a scalar on return, and $a[1..0] produces a descending range.)
function Resolve-Python312 {
    $candidates = @(
        @{ Exe = 'py';      PyArgs = @('-3.12') },
        @{ Exe = 'py';      PyArgs = @('-3')    },
        @{ Exe = 'python';  PyArgs = @()        },
        @{ Exe = 'python3'; PyArgs = @()        }
    )
    foreach ($c in $candidates) {
        if (-not (Test-Cmd $c.Exe)) { continue }
        try {
            $v = & $c.Exe @($c.PyArgs) -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $v) {
            $parts = $v.Trim().Split('.')
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 12) {
                return [pscustomobject]@{ Exe = $c.Exe; PyArgs = @($c.PyArgs) }
            }
        }
    }
    return $null
}

# --------------------------------------------------------------- prereqs ----

$manifest = Load-Manifest

Write-Step "Checking prerequisites"

# --- Python 3.12+ ---
$py = Resolve-Python312
if (-not $py) {
    Write-Warn2 "Python 3.12+ not found."
    Install-WingetPackage 'Python.Python.3.12' 'Python 3.12'
    Add-WingetToManifest $manifest 'Python.Python.3.12'
    $py = Resolve-Python312
    if (-not $py) {
        throw "Python 3.12 was installed but isn't on PATH yet. Close this terminal, open a new one, and re-run .\start.ps1"
    }
}
Write-Ok ("Python: " + ((& $py.Exe @($py.PyArgs) --version) 2>&1))

# --- Node.js ---
if (-not (Test-Cmd 'node')) {
    Write-Warn2 "Node.js not found."
    Install-WingetPackage 'OpenJS.NodeJS.LTS' 'Node.js LTS'
    Add-WingetToManifest $manifest 'OpenJS.NodeJS.LTS'
    if (-not (Test-Cmd 'node')) {
        throw "Node.js was installed but isn't on PATH yet. Close this terminal, open a new one, and re-run .\start.ps1"
    }
}
Write-Ok ("Node: " + (node --version))

# --- ffmpeg / ffprobe ---
if (-not (Test-Cmd 'ffmpeg') -or -not (Test-Cmd 'ffprobe')) {
    Write-Warn2 "ffmpeg/ffprobe not found."
    Install-WingetPackage 'Gyan.FFmpeg' 'ffmpeg'
    Add-WingetToManifest $manifest 'Gyan.FFmpeg'
    if (-not (Test-Cmd 'ffmpeg')) {
        throw "ffmpeg was installed but isn't on PATH yet. Close this terminal, open a new one, and re-run .\start.ps1"
    }
}
Write-Ok ("ffmpeg: " + ((ffmpeg -version 2>&1 | Select-Object -First 1)))

# ------------------------------------------------------------ python venv ----

Write-Step "Setting up the Python environment (.venv)"
$VenvDir = Join-Path $RepoRoot '.venv'
$VenvPy  = Join-Path $VenvDir 'Scripts\python.exe'

if (-not (Test-Path $VenvPy)) {
    Write-Info "Creating virtual environment..."
    & $py.Exe @($py.PyArgs) -m venv $VenvDir
    $manifest.createdVenv = $true
    Save-Manifest $manifest
} else {
    Write-Info "Reusing existing .venv"
}

Write-Info "Installing the clipforge package + dependencies (this can take a minute)..."
& $VenvPy -m pip install --upgrade pip --quiet
& $VenvPy -m pip install -e '.[dev]' --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
Write-Ok "Python dependencies installed (includes yt-dlp)."

# --------------------------------------------------------------- frontend ----

Write-Step "Building the web UI"
Push-Location (Join-Path $RepoRoot 'web')
try {
    if (-not (Test-Path 'node_modules')) {
        Write-Info "Installing frontend dependencies (npm install)..."
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
    } else {
        Write-Info "Reusing existing node_modules"
    }

    if ($SkipBuild -and (Test-Path 'dist')) {
        Write-Info "Skipping build (--SkipBuild); reusing web/dist"
    } else {
        Write-Info "Building the SPA (npm run build)..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
    }
} finally {
    Pop-Location
}
Write-Ok "UI built into web/dist"

# ------------------------------------------------------------------ launch ----

# If the requested port is taken (e.g. another local app), move to the next free one.
$Port = Resolve-FreePort $Port
$Url = "http://localhost:$Port"

Write-Step "Starting ClipForge on $Url"
Write-Info "FastAPI serves the UI and the API on this one port."
Write-Info "This window stays open while the server runs. Press Ctrl+C to stop."

if (-not $NoBrowser) {
    # Open the browser shortly after the server comes up.
    Start-Job -ScriptBlock {
        param($url)
        Start-Sleep -Seconds 3
        Start-Process $url
    } -ArgumentList $Url | Out-Null
}

try {
    & $VenvPy -m uvicorn server.app:app --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "The server exited unexpectedly (uvicorn exit code $LASTEXITCODE). See the output above."
    }
} finally {
    Get-Job -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
    Write-Host "`nClipForge stopped." -ForegroundColor Cyan
}
