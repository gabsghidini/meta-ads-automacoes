@echo off
setlocal
cd /d "%~dp0" || exit /b 2
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
    echo Python local nao encontrado. Siga a instalacao do guia WINDOWS.md. 1>&2
    exit /b 2
)
".venv\Scripts\python.exe" -u "%~dp0semanal.py" %* >> "%~dp0cron.log" 2>&1
exit /b %errorlevel%
