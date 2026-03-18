$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetDir = Join-Path $projectRoot 'tools\omenmon'
$exePath = Join-Path $targetDir 'OmenMon.exe'
$zipPath = Join-Path $targetDir 'OmenMon-latest.zip'

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

if (Test-Path $exePath) {
    Write-Host "OmenMon ya existe en: $exePath"
    exit 0
}

$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/OmenMon/OmenMon/releases/latest'
$asset = $release.assets | Where-Object { $_.name -match 'Release\.zip$' } | Select-Object -First 1

if ($null -eq $asset) {
    throw 'No se encontro un asset Release.zip en la ultima release de OmenMon.'
}

Write-Host "Descargando OmenMon: $($asset.name)"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath
tar -xf $zipPath -C $targetDir
Remove-Item $zipPath -Force

if (-not (Test-Path $exePath)) {
    throw 'La descarga finalizo, pero OmenMon.exe no quedo disponible en tools\omenmon.'
}

Write-Host "OmenMon instalado en: $exePath"
Write-Host 'Requisito recomendado: mantener instalados OMEN Gaming Hub y HP Omen Driver para equipos Victus/OMEN.'
