@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=%LocalAppData%\Programs\Python\Python313\python.exe"
if exist "%PYTHON%" goto localpython
py -3.13-64 -c "import tkinter" >nul 2>&1
if not errorlevel 1 goto launcher
echo Installing 64-bit Python 3.13 for your Windows account...
winget install --id Python.Python.3.13 --exact --scope user --architecture x64 --source winget
if errorlevel 1 goto failed
if exist "%PYTHON%" goto localpython
:launcher
py -3.13-64 -m venv diagnostics-venv
goto checkenv
:localpython
"%PYTHON%" -m venv diagnostics-venv
:checkenv
if errorlevel 1 goto failed
diagnostics-venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed
diagnostics-venv\Scripts\python.exe -B -c "import struct,tkinter,frida,PIL,theme_switch; assert struct.calcsize('P') == 8"
if errorlevel 1 goto failed
echo Installed. Open Dark Mode.vbs in this folder to use the switch.
if /i "%~1"=="--verify-only" exit /b 0
start "" wscript.exe "%~dp0Dark Mode.vbs"
exit /b 0
:failed
echo Setup failed. Install 64-bit Python 3.13 with Tk and the Python launcher, then retry.
if /i not "%~1"=="--verify-only" pause
exit /b 1
