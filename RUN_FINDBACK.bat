@echo off
setlocal EnableExtensions
title FindBack - Complete Project Startup
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"

echo ================================================
echo FindBack - complete project startup
echo Project: %ROOT%
echo Backend: %BACKEND%
echo ================================================

if not exist "%BACKEND%\run.py" (
  echo ERROR: backend\run.py is missing.
  echo Extract the COMPLETE ZIP into C:\LostProject.
  pause
  exit /b 1
)
if not exist "%BACKEND%\requirements.txt" (
  echo ERROR: backend\requirements.txt is missing.
  echo This complete package should include that file.
  pause
  exit /b 1
)

cd /d "%BACKEND%"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating backend virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto failed
) else (
  echo [1/3] Existing virtual environment found.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto failed

echo [2/3] Installing/checking backend requirements...
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 goto failed

echo [3/3] Starting FindBack...
python "%BACKEND%\run.py"
if errorlevel 1 goto failed
goto end

:failed
echo.
echo STARTUP FAILED. Keep this window open and send a screenshot.
pause
:end
endlocal
