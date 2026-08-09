@echo off
setlocal
REM Clear MSys vars
set MSYSTEM=
set TERM=
set SHELL=
set MSYSTEM_CHOST=
set MSYSTEM_CARCH=
set MSYSTEM_PREFIX=
set MINGW_CHOST=
set MINGW_PREFIX=

set IDF_PATH=E:\x-tool\espidf
set IDF_TOOLS_PATH=E:\x-tool\Espressif
set VENV=E:\x-tool\Espressif\python_env\idf5.5_py3.12_env\Scripts\python.exe

cd /d E:\x-tool\personal-assistant\scripts\xiaozhi-esp32

echo === Build Local ESP32 Firmware ===
echo IDF_PATH=%IDF_PATH%
echo.

if not exist build\sdkconfig (
    echo === Step 1: set-target esp32s3 ===
    "%VENV%" "%IDF_PATH%\tools\idf.py" set-target esp32s3
    if errorlevel 1 (
        echo CONFIG FAILED
        exit /b 1
    )
)

echo === Step 2: build ===
"%VENV%" "%IDF_PATH%\tools\idf.py" build
if errorlevel 1 (
    echo BUILD FAILED
    exit /b 1
)

echo === BUILD SUCCESS ===
dir /s /b build\*.bin 2>nul
endlocal
