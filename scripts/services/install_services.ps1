# install_services.ps1
# Registra el bot y el dashboard como servicios de Windows usando NSSM.
#
# Requisitos: ejecutar como Administrador
#   Click derecho en PowerShell -> "Run as administrator"
#   cd C:\ftmo-scalper
#   .\scripts\services\install_services.ps1

$ErrorActionPreference = "Stop"

# ── Verificar que corre como Administrador ─────────────────────────────────────

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Error "ERROR: Este script necesita permisos de Administrador. Click derecho en PowerShell -> 'Run as administrator'"
    exit 1
}

# ── Rutas ──────────────────────────────────────────────────────────────────────

$ROOT      = "C:\ftmo-scalper"
$VENV      = "$ROOT\.venv\Scripts"
$LOGS      = "$ROOT\logs"

# ── Crear directorio de logs ───────────────────────────────────────────────────

New-Item -ItemType Directory -Force -Path $LOGS | Out-Null

# ── Localizar NSSM (winget/choco/PATH o descarga) ─────────────────────────────

$NSSM = "$ROOT\scripts\services\nssm.exe"

# Primero buscar en PATH (instalado via winget o choco)
$nssmInPath = Get-Command nssm -ErrorAction SilentlyContinue
if ($nssmInPath) {
    $NSSM = $nssmInPath.Source
    Write-Host "NSSM encontrado en PATH: $NSSM" -ForegroundColor Green
} elseif (-not (Test-Path $NSSM)) {
    Write-Host "Descargando NSSM..." -ForegroundColor Cyan
    $zip = "$env:TEMP\nssm.zip"
    $extract = "$env:TEMP\nssm-extract"
    try {
        Invoke-WebRequest "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zip
        Expand-Archive $zip -DestinationPath $extract -Force
        Copy-Item "$extract\nssm-2.24\win64\nssm.exe" $NSSM
        Remove-Item $zip, $extract -Recurse -Force
        Write-Host "NSSM descargado." -ForegroundColor Green
    } catch {
        Write-Error "No se pudo descargar NSSM. Instálalo con: winget install nssm"
        exit 1
    }
} else {
    Write-Host "NSSM encontrado en: $NSSM" -ForegroundColor Green
}

# ── Función auxiliar ───────────────────────────────────────────────────────────

function Remove-ServiceIfExists($name) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($svc) {
        Write-Host "Eliminando servicio existente '$name'..." -ForegroundColor Yellow
        & $NSSM stop $name 2>$null
        Start-Sleep -Seconds 2
        & $NSSM remove $name confirm
    }
}

# ── Servicio: ftmo-dashboard ───────────────────────────────────────────────────
# Arranca automáticamente con Windows. El dashboard es solo lectura — siempre
# puede estar corriendo sin riesgo.

Remove-ServiceIfExists "ftmo-dashboard"
Write-Host "Instalando ftmo-dashboard..." -ForegroundColor Cyan

& $NSSM install ftmo-dashboard "$VENV\streamlit.exe" `
    "run dashboard/app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false"

& $NSSM set ftmo-dashboard AppDirectory          $ROOT
& $NSSM set ftmo-dashboard AppStdout             "$LOGS\dashboard-service.log"
& $NSSM set ftmo-dashboard AppStderr             "$LOGS\dashboard-service-error.log"
& $NSSM set ftmo-dashboard AppRotateFiles        1
& $NSSM set ftmo-dashboard AppRotateOnline       1
& $NSSM set ftmo-dashboard AppRotateBytes        10485760   # rota a 10 MB
& $NSSM set ftmo-dashboard Start                 SERVICE_AUTO_START
& $NSSM set ftmo-dashboard AppRestartDelay       5000       # reinicia a los 5s si cae

Write-Host "ftmo-dashboard instalado (arranque automatico)." -ForegroundColor Green

# ── Servicio: ftmo-bot ─────────────────────────────────────────────────────────
# Arranque MANUAL — el bot de trading solo corre cuando tú decides activarlo.
# Esto es intencional: no queremos que el bot arranque solo tras un reinicio
# inesperado del PC sin que lo hayas revisado primero.

Remove-ServiceIfExists "ftmo-bot"
Write-Host "Instalando ftmo-bot..." -ForegroundColor Cyan

& $NSSM install ftmo-bot "$VENV\python.exe" `
    "-m src.live.run_live --live --confirm `"I UNDERSTAND`""

& $NSSM set ftmo-bot AppDirectory          $ROOT
& $NSSM set ftmo-bot AppStdout             "$LOGS\bot-service.log"
& $NSSM set ftmo-bot AppStderr             "$LOGS\bot-service-error.log"
& $NSSM set ftmo-bot AppRotateFiles        1
& $NSSM set ftmo-bot AppRotateOnline       1
& $NSSM set ftmo-bot AppRotateBytes        10485760
& $NSSM set ftmo-bot Start                 SERVICE_DEMAND_START  # arranque manual
& $NSSM set ftmo-bot AppRestartDelay       30000      # espera 30s antes de reintentar

Write-Host "ftmo-bot instalado (arranque manual)." -ForegroundColor Green

# ── Arrancar dashboard ahora ───────────────────────────────────────────────────

Write-Host ""
Write-Host "Arrancando dashboard..." -ForegroundColor Cyan
& $NSSM start ftmo-dashboard
Start-Sleep -Seconds 3

$status = & $NSSM status ftmo-dashboard
Write-Host "Estado dashboard: $status" -ForegroundColor $(if ($status -eq "SERVICE_RUNNING") {"Green"} else {"Yellow"})

# ── Resumen ────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Servicios instalados correctamente" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host " Dashboard (auto):  http://localhost:8501"
Write-Host ""
Write-Host " Comandos utiles:"
Write-Host "   Iniciar bot:      nssm start ftmo-bot"
Write-Host "   Parar bot:        nssm stop ftmo-bot"
Write-Host "   Estado bot:       nssm status ftmo-bot"
Write-Host "   Estado dashboard: nssm status ftmo-dashboard"
Write-Host "   Ver logs bot:     Get-Content $LOGS\bot-service.log -Wait"
Write-Host ""
Write-Host " O abre 'services.msc' para gestionar con interfaz grafica."
Write-Host ""
