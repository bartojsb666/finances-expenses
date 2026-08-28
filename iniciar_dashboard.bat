@echo off
title Sistema de Finanzas BBVA
echo ====================================================
echo    Iniciando Sistema Inteligente de Gastos BBVA
echo ====================================================
echo.

echo [1/2] Verificando e instalando dependencias (esto puede tardar unos segundos)...
pip install -r requirements.txt >nul 2>&1

echo.
echo [2/2] Arrancando el servidor local...
echo.
echo ====================================================
echo  El Dashboard esta corriendo exitosamente!
echo  Abre tu navegador y entra a: http://localhost:8000
echo ====================================================
echo.
echo ATENCION: Puedes minimizar esta ventana negra, pero NO la cierres.
echo Si la cierras, el Dashboard dejara de funcionar.
echo.

start http://localhost:8000
python main.py

pause
