<#
.SYNOPSIS
    Registers (or removes) the Windows Task Scheduler task that runs CleanX.

.DESCRIPTION
    The task starts CleanX.exe every few minutes and at logon of the current user.
    CleanX itself decides - using CleanX.ini - whether the reminder is shown, so
    changing the time / days in CleanX.ini needs NO re-run of this script.
    No administrator rights required (the task belongs to the current user).

.EXAMPLE
    .\setup_scheduler.ps1                  # install / update
    .\setup_scheduler.ps1 -Uninstall       # remove
    .\setup_scheduler.ps1 -IntervalMinutes 5
#>
param(
    [switch]$Uninstall,
    [string]$TaskName = 'Cleaning LaserLab',
    [ValidateRange(1, 1440)]
    [int]$IntervalMinutes = 15,
    [string]$ExePath = (Join-Path $PSScriptRoot 'CleanX.exe')
)

$ErrorActionPreference = 'Stop'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'." -ForegroundColor Green
    } else {
        Write-Host "There is no scheduled task called '$TaskName'." -ForegroundColor Yellow
    }
    return
}

if (-not (Test-Path $ExePath)) {
    throw "CleanX.exe not found at '$ExePath'. Run build.bat first."
}
$ExePath = (Resolve-Path $ExePath).Path
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$action = New-ScheduledTaskAction -Execute $ExePath -WorkingDirectory (Split-Path $ExePath)

# every N minutes, starting today at midnight, repeating forever
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
# and right after logging in
$logon = New-ScheduledTaskTrigger -AtLogOn -User $user

$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName `
    -Description 'CleanX - monthly LaserLab cleaning reminder. When it pops up is configured in CleanX.ini.' `
    -Action $action -Trigger @($repeat, $logon) -Principal $principal -Settings $settings -Force | Out-Null

Write-Host ""
Write-Host "Scheduled task '$TaskName' installed for $user." -ForegroundColor Green
Write-Host "  Program : $ExePath"
Write-Host "  Checks  : every $IntervalMinutes min and at logon"
Write-Host "  Rules   : $(Join-Path (Split-Path $ExePath) 'CleanX.ini')"
Write-Host ""
Write-Host "Current decision:"
& $ExePath --status | Out-Host
