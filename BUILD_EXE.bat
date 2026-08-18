@echo off
title Build Civ V Hotseat Converter

echo.
echo ============================================
echo  Civ V Hotseat Converter - EXE Builder
echo ============================================
echo.

python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: Could not install/run PyInstaller.
    pause
    exit /b 1
)

python -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name Civ5HotseatConverter ^
  Civ5HotseatConverter.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo BUILD COMPLETE.
echo.
echo Your EXE is:
echo   dist\Civ5HotseatConverter.exe
echo.
pause
