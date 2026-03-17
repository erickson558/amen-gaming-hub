$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetDir = Join-Path $projectRoot 'tools\nbfc'
$exePath = Join-Path $targetDir 'nbfc.exe'

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

if (Test-Path $exePath) {
    Write-Host "NBFC ya existe en: $exePath"
    exit 0
}

$globalCandidates = @(
    'C:\Program Files (x86)\NoteBook FanControl\nbfc.exe',
    'C:\Program Files\NoteBook FanControl\nbfc.exe'
)

foreach ($candidate in $globalCandidates) {
    if (Test-Path $candidate) {
        Copy-Item $candidate $exePath -Force
        Write-Host "NBFC copiado a carpeta local: $exePath"
        exit 0
    }
}

Write-Host 'NBFC no está instalado globalmente. Instalando con winget...'
winget install --id Hirschmann.NotebookFanControl --accept-source-agreements --accept-package-agreements --silent

foreach ($candidate in $globalCandidates) {
    if (Test-Path $candidate) {
        Copy-Item $candidate $exePath -Force
        Write-Host "NBFC instalado y copiado localmente: $exePath"
        Write-Host 'Opcional: en config.json fija "nbfc_executable": "tools/nbfc/nbfc.exe"'
        exit 0
    }
}

throw 'No se encontró nbfc.exe después de instalar. Revisa instalación manual de NBFC.'
