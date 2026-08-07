[CmdletBinding()]
param(
    [string]$At = '07:00',
    [string]$TaskName = 'AtlasForge AI'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Executable = Join-Path $ProjectRoot '.venv\Scripts\atlasforge.exe'
if (-not (Test-Path -LiteralPath $Executable)) {
    throw 'Virtual environment not found. Run scripts\install.ps1 first.'
}

$Action = New-ScheduledTaskAction -Execute $Executable -Argument 'run' -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 6)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null

Write-Host "Registered '$TaskName' for $At daily." -ForegroundColor Green
Write-Host "Working directory: $ProjectRoot"
