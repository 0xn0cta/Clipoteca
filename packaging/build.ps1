param(
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') {
    throw 'Este script crea ejecutables de Windows y debe ejecutarse en Windows.'
}

$project = Split-Path -Parent $PSScriptRoot
$pythonCommand = (Get-Command $Python -ErrorAction Stop).Source
$frontend = Join-Path $project 'frontend'
$output = Join-Path $project 'dist/windows'

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

& $pythonCommand -m PyInstaller --noconfirm --distpath $output `
    --workpath (Join-Path $project 'build/pyinstaller') (Join-Path $PSScriptRoot 'clipoteca.spec')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminó con código $LASTEXITCODE. Instala packaging/requirements-build.txt en el entorno de compilación." }

Write-Output (Join-Path $output 'Clipoteca/Clipoteca.exe')
Write-Output (Join-Path $output 'clipoteca-cli/clipoteca-cli.exe')
