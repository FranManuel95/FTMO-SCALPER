# bot_control.ps1
# Control rapido del bot desde PowerShell normal (no necesita Administrador para start/stop).
#
# Uso:
#   .\scripts\services\bot_control.ps1 start
#   .\scripts\services\bot_control.ps1 stop
#   .\scripts\services\bot_control.ps1 status
#   .\scripts\services\bot_control.ps1 logs

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start","stop","restart","status","logs","logs-dashboard")]
    [string]$Action
)

$nssmInPath = Get-Command nssm -ErrorAction SilentlyContinue
$NSSM = if ($nssmInPath) { $nssmInPath.Source } else { "C:\ftmo-scalper\scripts\services\nssm.exe" }
$LOGS = "C:\ftmo-scalper\logs"

switch ($Action) {
    "start" {
        Write-Host "Arrancando bot..." -ForegroundColor Cyan
        & $NSSM start ftmo-bot
        Start-Sleep -Seconds 2
        $s = & $NSSM status ftmo-bot
        Write-Host "Estado: $s" -ForegroundColor $(if ($s -eq "SERVICE_RUNNING") {"Green"} else {"Red"})
    }
    "stop" {
        Write-Host "Parando bot..." -ForegroundColor Yellow
        & $NSSM stop ftmo-bot
        $s = & $NSSM status ftmo-bot
        Write-Host "Estado: $s"
    }
    "restart" {
        Write-Host "Reiniciando bot..." -ForegroundColor Yellow
        & $NSSM restart ftmo-bot
        Start-Sleep -Seconds 3
        $s = & $NSSM status ftmo-bot
        Write-Host "Estado: $s" -ForegroundColor $(if ($s -eq "SERVICE_RUNNING") {"Green"} else {"Red"})
    }
    "status" {
        $bot  = & $NSSM status ftmo-bot       2>$null
        $dash = & $NSSM status ftmo-dashboard 2>$null
        Write-Host "ftmo-bot:       $bot"
        Write-Host "ftmo-dashboard: $dash"
    }
    "logs" {
        Write-Host "Mostrando logs del bot (Ctrl+C para salir)..." -ForegroundColor Cyan
        Get-Content "$LOGS\bot-service.log" -Wait -Tail 50
    }
    "logs-dashboard" {
        Write-Host "Mostrando logs del dashboard (Ctrl+C para salir)..." -ForegroundColor Cyan
        Get-Content "$LOGS\dashboard-service.log" -Wait -Tail 50
    }
}
