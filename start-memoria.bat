@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Memoria.ia is not installed yet.
  echo Run install-windows.bat first.
  exit /b 1
)
if not exist ".env" (
  echo ERROR: .env was not found.
  echo Run install-windows.bat first.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  call :setenv "%%A" "%%B"
)

if not defined MEMORIA_DATA_DIR set "MEMORIA_DATA_DIR=%CD%\data"
if "%MEMORIA_DATA_DIR%"=="/data" set "MEMORIA_DATA_DIR=%CD%\data"
if not exist "%MEMORIA_DATA_DIR%" mkdir "%MEMORIA_DATA_DIR%"

rem Native Windows rule: once the UI has persisted an LLM configuration,
rem that local product configuration becomes authoritative on restart.
rem Docker/server deployments keep their existing environment-override behavior.
if exist "%MEMORIA_DATA_DIR%\product-config.json" (
  set "MEMORIA_LLM_PROVIDER="
  set "MEMORIA_LLM_MODEL="
  set "OPENAI_API_KEY="
  set "GEMINI_API_KEY="
  echo Using persisted local LLM configuration.
)

if not defined MEMORIA_API_KEY (
  echo ERROR: MEMORIA_API_KEY is empty in .env
  exit /b 1
)
if /I "%MEMORIA_API_KEY%"=="replace-with-a-long-random-secret" (
  echo ERROR: replace the placeholder MEMORIA_API_KEY in .env before starting.
  exit /b 1
)
if /I "%MEMORIA_API_KEY%"=="troque-por-uma-chave-grande-e-dificil" (
  echo ERROR: replace the placeholder MEMORIA_API_KEY in .env before starting.
  exit /b 1
)

if not defined MEMORIA_HOST set "MEMORIA_HOST=127.0.0.1"
if not defined MEMORIA_PORT set "MEMORIA_PORT=8080"

echo ========================================
echo Memoria.ia Native Windows Product Alpha
echo Organization: %MEMORIA_ORGANIZATION_ID%
echo Data: %MEMORIA_DATA_DIR%
echo URL: http://%MEMORIA_HOST%:%MEMORIA_PORT%
echo Press Ctrl+C to stop.
echo ========================================

".venv\Scripts\python.exe" -m uvicorn memoria_resolutiva.product_server:app --host "%MEMORIA_HOST%" --port "%MEMORIA_PORT%"
exit /b %errorlevel%

:setenv
set "key=%~1"
set "value=%~2"
if "%key%"=="" goto :eof
if "%key:~0,1%"=="#" goto :eof
set "%key%=%value%"
goto :eof
