@echo off
if "%~1"=="" (
    echo Drag your grid capture folder onto this file to stitch it.
    echo Install the dependency once with: py -m pip install Pillow
    pause
    exit /b 1
)
py "%~dp0stitch_map.py" "%~1"
pause
