@echo off
color 0B
echo ===================================================
echo       E.K. LOGISTICA - SISTEMA EN LA NUBE
echo ===================================================
echo.
echo 1. Cerrando el sistema viejo para liberar archivos...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo 2. Forzando la actualizacion desde el servidor...
cd C:\EK-Logistica

:: Esto borra cualquier traba local y trae la version de GitHub SI o SI
git fetch --all
git reset --hard HEAD
git pull

echo.
echo 3. Actualizacion completada. Iniciando plataforma...
timeout /t 2 /nobreak >nul
start pythonw main_logistica.py
exit