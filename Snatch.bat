@echo off
setlocal EnableDelayedExpansion

echo Starting Snatch...

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not found in PATH
    echo Please install Python and make sure it's added to your PATH
    pause
    exit /b 1
)

REM Get the directory containing this batch file
set "SCRIPT_DIR=%~dp0"

REM Run as module using pythonpath to ensure imports work correctly
set "PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%"
python -m modules.cli %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error occurred during execution
    pause
    exit /b 1
)

exit /b 0
