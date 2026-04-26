@echo off
title FTMO Bot - Live Trading
cd /d C:\ftmo-scalper
call .venv\Scripts\activate.bat
echo.
echo  Arrancando FTMO Bot...
echo  Para pararlo: cierra esta ventana o Ctrl+C
echo.
python -m src.live.run_live --live --confirm "I UNDERSTAND"
echo.
echo  Bot detenido.
pause
