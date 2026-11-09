@echo off
rem Builds CleanX.exe with the Visual Studio C++ compiler (MSVC).
rem Just double-click it, or run it from any terminal.
setlocal
cd /d "%~dp0"

where cl >nul 2>nul
if %errorlevel%==0 goto build

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq tokens=*" %%i in (`call "%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSDIR=%%i"
if not defined VSDIR (
    echo Visual Studio with the C++ workload was not found.
    exit /b 1
)
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul

:build
if not exist build mkdir build
rc /nologo /fo build\cleanx.res src\cleanx.rc || goto fail
cl /nologo /utf-8 /std:c++17 /O1 /MT /EHsc /W4 /DUNICODE /D_UNICODE /Fobuild\ /Fe:CleanX.exe src\cleanx.cpp build\cleanx.res /link /SUBSYSTEM:WINDOWS /OPT:REF /OPT:ICF || goto fail
rmdir /s /q build
echo.
echo SUCCESSFULLY built CleanX.exe
exit /b 0

:fail
echo.
echo ERROR building CleanX.exe
exit /b 1
