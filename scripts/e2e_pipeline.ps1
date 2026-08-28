# AI Card Game Lab — E2E pipeline wrapper (Windows)
# Usage:
#   .\scripts\e2e_pipeline.ps1 guide
#   .\scripts\e2e_pipeline.ps1 check
#   .\scripts\e2e_pipeline.ps1 all -Count 1
param(
    [Parameter(Position = 0)]
    [ValidateSet("guide", "check", "collect", "export", "train", "deploy-hints", "all")]
    [string]$Command = "guide",

    [string]$BaseUrl = "http://localhost:8000",
    [int]$Count = 1,
    [switch]$NoMock,
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Server = Join-Path $Root "server"
$Script = Join-Path $Server "scripts\e2e_pipeline.py"

if (-not (Test-Path $Script)) {
    Write-Error "Missing $Script"
}

Push-Location $Server
try {
    $argv = @($Command, "--base-url", $BaseUrl, "--count", "$Count")
    if ($NoMock) { $argv += "--no-mock" }
    if ($NoWait) { $argv += "--no-wait" }
    poetry run python scripts/e2e_pipeline.py @argv
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
