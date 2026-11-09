@echo off
rem Sets up the Task Scheduler for CleanX (double-click me).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_scheduler.ps1" %*
pause
