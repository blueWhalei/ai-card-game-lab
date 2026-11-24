param([switch]$BackendOnly)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonExe = Join-Path $repoRoot 'server/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Install the project Python dependencies in server/.venv first.' }
function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}
Push-Location $repoRoot
try {
    # The desktop build always uses same-origin API URLs.
    $priorApiUrl = $env:VITE_API_BASE_URL
    $env:VITE_API_BASE_URL = '/'
    try { Invoke-Checked 'npm.cmd' @('--prefix', 'web', 'run', 'build') }
    finally { $env:VITE_API_BASE_URL = $priorApiUrl }
    Invoke-Checked $pythonExe @('-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', 'desktop/src-tauri', '--workpath', 'desktop/.build/python', 'scripts/desktop/backend.spec')
    if (-not $BackendOnly) {
        Push-Location (Join-Path $repoRoot 'desktop')
        try {
            Invoke-Checked 'npm.cmd' @('exec', '--', 'tauri', 'icon', '../web/public/logo.png', '--output', 'src-tauri/icons')
            Invoke-Checked 'npm.cmd' @('run', 'build', '--', '--bundles', 'nsis')
        }
        finally { Pop-Location }
    }
} finally { Pop-Location }
