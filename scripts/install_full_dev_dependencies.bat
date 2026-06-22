@echo off
setlocal
cd /d "%~dp0.."

echo ============================================
echo  Full Developer Install
echo ============================================
echo.
echo This installs ALL packages including AI libraries,
echo Playwright, and other heavy dev dependencies.
echo This may take several minutes.
echo.

:: ── 1. Require Python 3.11 64-bit ───────────────────────────────────────────
set PY311=
for /f "tokens=*" %%i in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set PY311=%%i

if "%PY311%"=="" (
    echo ERROR: Python 3.11 64-bit not found.
    echo.
    echo Please install Python 3.11 ^(64-bit^) from:
    echo   https://www.python.org/downloads/release/python-3110/
    echo When installing tick: [x] Add python.exe to PATH
    echo.
    pause
    exit /b 1
)

echo Using Python 3.11: %PY311%
echo.

:: ── 2. Recreate .venv if wrong version ──────────────────────────────────────
if exist ".venv\Scripts\activate.bat" (
    for /f "tokens=*" %%v in ('".venv\Scripts\python.exe" -c "import sys; print(sys.version_info[:2])" 2^>nul') do set VENV_VER=%%v
    if not "%VENV_VER%"=="(3, 11)" (
        echo Removing .venv created with %VENV_VER%, recreating with Python 3.11...
        rmdir /s /q .venv
    )
)

if not exist ".venv\Scripts\activate.bat" (
    echo Creating .venv with Python 3.11...
    py -3.11 -m venv .venv
    if errorlevel 1 ( echo ERROR: venv creation failed. & pause & exit /b 1 )
)

call .venv\Scripts\activate.bat

:: ── 3. Upgrade pip ───────────────────────────────────────────────────────────
python -m pip install --upgrade pip setuptools wheel

:: ── 4. Install full requirements ─────────────────────────────────────────────
echo.
echo Installing requirements.txt (full dev set)...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Full install failed.
    echo Some packages may need Visual C++ Build Tools.
    echo Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)

:: ── 5. Install Playwright browsers ──────────────────────────────────────────
echo.
echo Installing Playwright browsers...
playwright install chromium
if errorlevel 1 ( echo WARNING: Playwright install failed — UI tests will be skipped. )

echo.
echo ============================================
echo  Full dev install complete.
echo ============================================
echo.
echo To start the dashboard:   scripts\start_desktop_ui.bat
echo To run tests:             python -m pytest tests -v
echo To run full supervisor:   python main.py visual-supervisor
echo.
pause
