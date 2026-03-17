$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$iconPath = Join-Path $projectRoot 'app.ico'
$iconArgs = @()
if (Test-Path $iconPath) {
    $iconArgs = @('--icon', $iconPath)
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
