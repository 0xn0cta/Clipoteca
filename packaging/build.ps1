param(
    [string]$Python = 'python',
    [string]$OutputPath = '',
    [string]$WorkPath = ''
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') {
    throw 'Este script crea ejecutables de Windows y debe ejecutarse en Windows.'
}

$project = Split-Path -Parent $PSScriptRoot
$pythonCommand = (Get-Command $Python -ErrorAction Stop).Source
$frontend = Join-Path $project 'frontend'
$distPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    Join-Path $project 'dist/windows'
} else {
    [System.IO.Path]::GetFullPath($OutputPath)
}
$pyinstallerWorkPath = if ([string]::IsNullOrWhiteSpace($WorkPath)) {
    Join-Path $project 'build/pyinstaller'
} else {
    [System.IO.Path]::GetFullPath($WorkPath)
}

Push-Location $frontend
try {
    if (-not (Test-Path -LiteralPath 'node_modules/.bin/vite.cmd')) {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci terminó con código $LASTEXITCODE." }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "La compilación de la interfaz terminó con código $LASTEXITCODE." }
} finally {
    Pop-Location
}

& $pythonCommand (Join-Path $PSScriptRoot 'generate_icon.py')
if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el icono de Windows. Comprueba Pillow en el entorno de compilación." }

New-Item -ItemType Directory -Force -Path $distPath, $pyinstallerWorkPath | Out-Null
& $pythonCommand -m PyInstaller --noconfirm --distpath $distPath `
    --workpath $pyinstallerWorkPath (Join-Path $PSScriptRoot 'clipoteca.spec')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminó con código $LASTEXITCODE. Instala packaging/requirements-build.txt en el entorno de compilación." }

Write-Output (Join-Path $distPath 'Clipoteca/Clipoteca.exe')
Write-Output (Join-Path $distPath 'clipoteca-cli/clipoteca-cli.exe')
