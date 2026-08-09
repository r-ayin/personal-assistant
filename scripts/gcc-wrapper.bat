@echo off
REM GCC wrapper: convert @E:/... to @/e/... in @response file args
REM Required because MinGW GCC @ syntax doesn't support Windows drive letters

setlocal enabledelayedexpansion

set REAL_GCC=E:\x-tool\Espressif\tools\xtensa-esp-elf\esp-14.2.0_20260121\xtensa-esp-elf\bin\xtensa-esp32s3-elf-gcc.exe

set ARGS=
:loop
if "%~1"=="" goto run
set "arg=%~1"
REM Convert @"X:/path" to @"/x/path"
REM Pattern: starts with @" followed by a drive letter and :/
echo !arg! | findstr /r "^@\"[A-Za-z]:/" >nul
if !errorlevel! equ 0 (
    set "drive=!arg:~2,1!"
    rem Convert drive to lowercase
    for %%d in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
        if /i "!drive!"=="%%d" set "drive=%%d"
    )
    set "rest=!arg:~4!"
    set "arg=@\"/!drive!/!rest!"
)
set "ARGS=!ARGS! !arg!"
shift
goto loop

:run
"%REAL_GCC%" %ARGS%
exit /b %ERRORLEVEL%
