param(
    [switch]$NoDesktopShortcut
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$source = Join-Path $root "dist\windows\Clipoteca"
$exe = Join-Path $source "Clipoteca.exe"
$target = Join-Path $env:LOCALAPPDATA "Programs\Clipoteca"
$targetExe = Join-Path $target "Clipoteca.exe"
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$desktop = [Environment]::GetFolderPath("Desktop")

if (-not (Test-Path $exe)) {
    throw "No existe dist\windows\Clipoteca\Clipoteca.exe. Ejecuta .\packaging\build.ps1 primero."
}

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "Clipoteca.exe" -and $_.ExecutablePath -eq $targetExe
}
if ($running) {
    throw "Cierra Clipoteca antes de actualizar la instalación."
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force

New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
$shell = New-Object -ComObject WScript.Shell
$startLink = $shell.CreateShortcut((Join-Path $startMenu "Clipoteca.lnk"))
$startLink.TargetPath = $targetExe
$startLink.WorkingDirectory = $target
$startLink.Description = "Preparar y gestionar descargas autorizadas con Clipoteca"
$startLink.IconLocation = "$targetExe,0"
$startLink.Save()

if (-not $NoDesktopShortcut) {
    $desktopLink = $shell.CreateShortcut((Join-Path $desktop "Clipoteca.lnk"))
    $desktopLink.TargetPath = $targetExe
    $desktopLink.WorkingDirectory = $target
    $desktopLink.Description = "Clipoteca"
    $desktopLink.IconLocation = "$targetExe,0"
    $desktopLink.Save()
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "FFmpeg no está en PATH. MP3 y la unión de pistas necesitarán una instalación externa."
}

Write-Host "Clipoteca instalada en: $target"
Write-Host "Acceso directo: $startMenu\Clipoteca.lnk"
if (-not $NoDesktopShortcut) {
    Write-Host "Acceso directo del escritorio: $desktop\Clipoteca.lnk"
}
