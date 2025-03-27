@echo off
echo Starting Snatch...
REM Use python from PATH and pass all arguments to the script
python "%~dp0Snatch.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo Error occurred. Press any key to exit.
    pause > nul
)
