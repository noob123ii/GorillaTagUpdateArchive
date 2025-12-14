@echo off
echo Installing Python dependencies for Gorilla Tag Update Archive...
echo.

REM Upgrade pip first
echo [1/3] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    pause
    exit /b 1
)

echo.
echo [2/3] Installing build tools (if needed)...
python -m pip install --upgrade setuptools wheel
if errorlevel 1 (
    echo WARNING: Failed to upgrade setuptools/wheel, continuing anyway...
)

echo.
echo [3/3] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install some dependencies
    echo.
    echo Trying to install cryptography separately...
    python -m pip install cryptography
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install cryptography
        echo.
        echo If you continue to have issues, try:
        echo 1. Make sure you have Python 3.8 or higher
        echo 2. Update pip: python -m pip install --upgrade pip
        echo 3. Install cryptography manually: python -m pip install cryptography
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo You can now run the server with: python app.py
echo.
pause

