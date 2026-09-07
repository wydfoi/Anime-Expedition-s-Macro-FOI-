@echo off
setlocal
cd /d "%~dp0"

rem Prefer the py launcher pinned to 3.12 (what build_pyinstaller.py is
rem actually built/tested against -- see that file's own header comment),
rem falling back to plain "python" if py isn't on PATH.
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYCMD=py -3.12"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYCMD=python"
    ) else (
        echo Python not found on PATH. Install Python from python.org and try again.
        pause
        endlocal
        exit /b 1
    )
)

echo Installing app dependencies...
%PYCMD% -m pip install -r requirements.txt
if not "%errorlevel%"=="0" (
    echo.
    echo Couldn't install requirements.txt. Check your internet connection and try again.
    pause
    endlocal
    exit /b 1
)

echo.
echo Installing/upgrading PyInstaller...
%PYCMD% -m pip install --upgrade pyinstaller
if not "%errorlevel%"=="0" (
    echo.
    echo Couldn't install PyInstaller. Check your internet connection and try again.
    pause
    endlocal
    exit /b 1
)

echo.
echo Building the exe (this can take a minute)...
%PYCMD% build_pyinstaller.py
set BUILD_EXIT=%errorlevel%

if not "%BUILD_EXIT%"=="0" (
    echo.
    echo Build FAILED ^(code %BUILD_EXIT%^). See the output above for details.
    pause
    endlocal
    exit /b 1
)

echo.
echo Build succeeded! Check the dist\ folder for "Anime Expeditions.exe".
pause
endlocal
