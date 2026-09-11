@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"

echo ============================================
echo   Airfare Price Index (APIx) - starting up
echo ============================================
echo.

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment not found at:
    echo   %ROOT%backend\.venv
    echo Set it up first with:
    echo   cd "%ROOT%backend"
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
    echo [ERROR] Frontend dependencies not installed. Set them up first with:
    echo   cd "%ROOT%frontend"
    echo   npm install
    pause
    exit /b 1
)

echo Starting backend  (http://127.0.0.1:8001) ...
start "APIx - Backend" cmd /k ""%ROOT%backend\.venv\Scripts\python.exe" "%ROOT%backend\serve.py""

echo Waiting for the backend to be ready (this can take a little while the first time)...
set "READY=0"
for /l %%i in (1,1,40) do (
    if "!READY!"=="0" (
        powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200 } catch { $false }" | findstr /c:"True" >nul
        if not errorlevel 1 (
            set "READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
if "%READY%"=="1" (
    echo Backend is up.
) else (
    echo [WARNING] Backend didn't respond within 40 seconds - continuing anyway.
    echo           Check the "APIx - Backend" window for errors if the dashboard looks empty.
)

echo Starting frontend (http://127.0.0.1:5173) ...
start "APIx - Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev -- --host 127.0.0.1 --port 5173"

echo Waiting for the frontend to be ready...
set "FRONT_READY=0"
for /l %%i in (1,1,30) do (
    if "!FRONT_READY!"=="0" (
        powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200 } catch { $false }" | findstr /c:"True" >nul
        if not errorlevel 1 (
            set "FRONT_READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)

start "" "http://127.0.0.1:5173"

echo.
echo Both servers are running in their own windows.
echo   - Backend:  http://127.0.0.1:8001/docs
echo   - Frontend: http://127.0.0.1:5173
echo.
echo To stop the app, close (or Ctrl+C in) the two new windows that opened.
echo This window can be closed now.
echo.
pause
