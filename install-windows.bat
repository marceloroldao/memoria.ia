@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo Memoria.ia - Native Windows installer
echo ========================================

set "PY="

rem Prefer Python 3.12 because the product alpha and CI are validated on it.
py -3.12 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3.12"

if not defined PY (
  py -3.11 --version >nul 2>nul
  if not errorlevel 1 set "PY=py -3.11"
)

if not defined PY (
  py -3.10 --version >nul 2>nul
  if not errorlevel 1 set "PY=py -3.10"
)

if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set "PYVER=%%V"
    python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)"
    if not errorlevel 1 set "PY=python"
  )
)

if not defined PY (
  echo.
  echo ERROR: A supported Python version was not found.
  echo Memoria.ia native Windows alpha currently supports Python 3.10, 3.11, or 3.12.
  echo Python 3.12 is recommended and used by CI.
  echo Install it from https://www.python.org/downloads/windows/
  echo Then run this installer again.
  exit /b 1
)

for /f "delims=" %%V in ('%PY% --version 2^>^&1') do set "SELECTED_PY=%%V"
echo Using %SELECTED_PY%

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)"
  if errorlevel 1 (
    echo Existing .venv uses an unsupported Python version. Recreating it...
    rmdir /S /Q ".venv"
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  %PY% -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing Memoria.ia product dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install ".[product]"
if errorlevel 1 exit /b 1

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example.
  echo IMPORTANT: edit .env and replace MEMORIA_API_KEY before first start.
) else (
  echo Existing .env preserved.
)

if not exist "data" mkdir "data"

echo.
echo Installation complete.
echo Edit .env if needed, then run start-memoria.bat
exit /b 0
