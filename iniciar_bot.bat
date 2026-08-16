@echo off
setlocal

title NerO IA - WhatsApp Bot
color 0B
cls

echo ============================================
echo   INICIANDO BOT DE WHATSAPP
echo ============================================

echo Activando entorno virtual...
call .\.venv\Scripts\activate.bat

echo Iniciando servidor del Bot...
python run.py

endlocal
pause
