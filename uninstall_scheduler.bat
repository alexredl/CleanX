@echo off
rem Removes the CleanX task from the Task Scheduler (double-click me).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_scheduler.ps1" -Uninstall %*
pause
