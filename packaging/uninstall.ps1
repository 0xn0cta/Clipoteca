$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Programs\Clipoteca"
$startMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Clipoteca.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Clipoteca.lnk"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "Clipoteca.exe" -and $_.ExecutablePath -like "$target*"
}
if ($running) {
    throw "Cierra Clipoteca antes de desinstalarla."
}

if (Test-Path $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
Remove-Item -LiteralPath $startMenuShortcut, $desktopShortcut -Force -ErrorAction SilentlyContinue

Write-Host "Clipoteca se ha desinstalado. La base de datos, preferencias, logs y descargas del usuario se conservaron."
