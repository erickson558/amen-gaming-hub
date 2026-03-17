$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { 'python' }
Write-Host "Usando Python: $pythonExe"

$pythonBase = (& $pythonExe -c "import sys; print(sys.base_prefix)").Trim()
$tclSource = Join-Path $pythonBase 'tcl\tcl8.6'
$tkSource = Join-Path $pythonBase 'tcl\tk8.6'

if (-not (Test-Path $tclSource) -or -not (Test-Path $tkSource)) {
    throw "No se encontraron fuentes Tcl/Tk en: $pythonBase\tcl"
}

Write-Host "Tcl fuente: $tclSource"
Write-Host "Tk fuente:  $tkSource"

& $pythonExe -c "from amen_hub.tk_runtime import configure_tk_runtime; configure_tk_runtime(); import tkinter as tk; root=tk.Tk(); root.destroy()"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo inicializar tkinter con el runtime de compatibilidad."
}

$iconPath = Join-Path $projectRoot 'app.ico'
if (-not (Test-Path $iconPath)) {
    $firstIco = Get-ChildItem -Path $projectRoot -Filter '*.ico' -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $firstIco) {
        $iconPath = $firstIco.FullName
    }
}
$iconArgs = @()
if (Test-Path $iconPath) {
    $iconArgs = @('--icon', $iconPath)
    Write-Host "Usando icono: $iconPath"
} else {
    Write-Host 'No se encontro .ico; compilando sin icono personalizado.'
}

$dataArgs = @(
    '--add-data', "$tclSource;tcl/tcl8.6",
    '--add-data', "$tkSource;tcl/tk8.6"
)

& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --uac-admin `
    --name "AmenGamingHub" `
    --distpath $projectRoot `
    --workpath (Join-Path $projectRoot 'build') `
    --specpath $projectRoot `
    @dataArgs `
    @iconArgs `
    (Join-Path $projectRoot 'app.py')
