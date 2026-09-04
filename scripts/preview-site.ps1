$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "screenshots"
$dst = Join-Path $root "site\screenshots"

if (-not (Test-Path $dst)) {
    cmd /c mklink /J "$dst" "$src" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Copy-Item $src $dst -Recurse -Force
    }
}

Write-Host "http://localhost:4173"
Set-Location (Join-Path $root "site")
npx --yes serve -p 4173 --no-clipboard
