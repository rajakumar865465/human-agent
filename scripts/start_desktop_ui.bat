@echo off
setlocal
cd /d "%~dp0.."

echo ============================================
echo  Autonomous Visual Supervisor UI
echo ============================================
echo.

:: ── 1. Verify Python 3.11 64-bit is available ──────────────────────────────
set PY311=
for /f "tokens=*" %%i in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set PY311=%%i

if "%PY311%"=="" (
    echo ERROR: Python 3.11 64-bit not found.
    echo.
    echo Please install Python 3.11 ^(64-bit^) from:
    echo   https://www.python.org/downloads/release/python-3110/
    echo.
    echo When installing, tick:
    echo   [x] Add python.exe to PATH
    echo   [x] Install for all users  ^(recommended^)
    echo.
    echo Do NOT fall back to Python 3.13 — some dependencies
    echo ^(tiktoken, greenlet, psutil^) require source builds on 3.13
    echo and will cause the installer to fail.
    echo.
    pause
    exit /b 1
)

echo Using Python 3.11: %PY311%
echo.

:: ── 2. Check if existing .venv was made with the wrong Python ───────────────
if exist ".venv\Scripts\activate.bat" (
    for /f "tokens=*" %%v in ('".venv\Scripts\python.exe" -c "import sys; print(sys.version_info[:2])" 2^>nul') do set VENV_VER=%%v
    if not "%VENV_VER%"=="(3, 11)" (
        echo WARNING: .venv was created with a different Python version: %VENV_VER%
        echo Deleting and recreating .venv with Python 3.11...
        rmdir /s /q .venv
    )
)

:: ── 3. Create .venv with Python 3.11 if missing ────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment with Python 3.11...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
    echo.
)

:: ── 4. Activate ─────────────────────────────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── 5. Upgrade pip and install UI dependencies only ─────────────────────────
echo Installing UI dependencies (requirements-ui.txt)...
python -m pip install --upgrade pip setuptools wheel --quiet
pip install -r requirements-ui.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed.
    echo Check your internet connection and try again.
    echo For proxy environments set: set HTTPS_PROXY=http://proxy:port
    pause
    exit /b 1
)

echo.
echo All dependencies installed.
echo.

:: ── 6. Start target demo app on port 8000 ───────────────────────────────────
echo Starting target demo app on port 8000...
start "Target Demo App" /d "%CD%\sandbox\demo_app" "%CD%\.venv\Scripts\uvicorn.exe" app:app --host 127.0.0.1 --port 8000
echo Target demo app launching in background...
echo.

:: ── 7. Start dashboard server and open browser ───────────────────────────────
echo Starting dashboard server...
echo Dashboard will open at: http://127.0.0.1:8080
echo Press Ctrl+C to stop.
echo.

start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8080"

python ui/dashboard_server.py

echo.
echo Server stopped.
pause
