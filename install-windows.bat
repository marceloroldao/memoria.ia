@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Memoria.ia - Native Windows installer
echo ========================================

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo.
    echo ERROR: Python 3.10 or newer was not found.
    echo Install Python from https://www.python.org/downloads/windows/
    echo Enable "Add python.exe to PATH" during installation.
    exit /b 1
  )
  set "PY=python"
)

%PY% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10 or newer is required'"
if errorlevel 1 exit /b 1

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
