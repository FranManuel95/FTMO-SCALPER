# uninstall_services.ps1
# Elimina los servicios de Windows del bot y el dashboard.
# Ejecutar como Administrador.

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Error "Necesita permisos de Administrador."
    exit 1
}

$NSSM = "C:\ftmo-scalper\scripts\services\nssm.exe"

foreach ($name in @("ftmo-bot", "ftmo-dashboard")) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($svc) {
        Write-Host "Parando y eliminando '$name'..." -ForegroundColor Yellow
        & $NSSM stop $name 2>$null
        Start-Sleep -Seconds 2
        & $NSSM remove $name confirm
        Write-Host "'$name' eliminado." -ForegroundColor Green
    } else {
        Write-Host "'$name' no existe, nada que hacer." -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Servicios eliminados. Puedes volver a instalarlos con install_services.ps1" -ForegroundColor Green
