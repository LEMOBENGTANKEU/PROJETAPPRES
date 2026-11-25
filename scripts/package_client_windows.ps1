param(
    [ValidateSet("pyinstaller", "flet")]
    [string]$Mode = "pyinstaller",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== CampusShare packaging ==" -ForegroundColor Cyan
Write-Host "Root: $Root"
Write-Host "Mode: $Mode"

if ($Mode -eq "pyinstaller") {
    Write-Host "Installing packaging dependencies..." -ForegroundColor Yellow
    & $Python -m pip install --upgrade pip pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

    Write-Host "Building executable with PyInstaller..." -ForegroundColor Yellow
    & $Python -m PyInstaller packaging/campusshare_client.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    Write-Host "Build output: $Root\dist\CampusShare" -ForegroundColor Green
    Write-Host "Test on a target Windows machine with same/compatible architecture." -ForegroundColor DarkYellow
}
elseif ($Mode -eq "flet") {
    Write-Host "Building with Flet..." -ForegroundColor Yellow
    & $Python -m pip install --upgrade flet
    if ($LASTEXITCODE -ne 0) { throw "pip install flet failed" }
    # Flet 1.x desktop build command. Requires Flutter SDK on build machine.
    & $Python -m flet build windows --project . --output dist\flet-windows
    if ($LASTEXITCODE -ne 0) { throw "flet build windows failed. Ensure Flutter SDK and Flet desktop requirements are installed." }
    Write-Host "Build output: $Root\dist\flet-windows" -ForegroundColor Green
}
