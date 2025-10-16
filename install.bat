:: Isaac Sim Extension Installer (Windows)
:: Uses built-in python.bat

@echo off
setlocal

:: Get script directory
set "SCRIPT_DIR=%~dp0"

:: Change to script directory
cd /d "%SCRIPT_DIR%"

:: Locate python.bat in parent directory
for %%I in (..) do set "ROOT_DIR=%%~fI"
if exist "%ROOT_DIR%\python.bat" (
    set "PYTHON_EXE=%ROOT_DIR%\python.bat"
) else (
    echo Error: python.bat not found. Ensure this extension is in Isaac Sim root directory.
    goto error
)

:: Check for install.py
if not exist "install.py" (
    echo Error: install.py not found.
    goto error
)

echo Using %PYTHON_EXE% to install extension...
call "%PYTHON_EXE%" "install.py"
goto end

:error
echo Installation failed.
pause
exit /b 1

:end
if errorlevel 1 (
    echo Installation failed.
    pause
    exit /b 1
)

echo Installation completed.
pause
exit /b 0