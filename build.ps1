$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

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

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --uac-admin `
    --name "AmenGamingHub" `
    --distpath $projectRoot `
    --workpath (Join-Path $projectRoot 'build') `
    --specpath $projectRoot `
    @iconArgs `
    (Join-Path $projectRoot 'app.py')
