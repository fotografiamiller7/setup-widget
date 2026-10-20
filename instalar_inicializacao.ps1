# Registra o widget para abrir automaticamente no logon, já como administrador (sem pedir UAC toda vez).
# Execute com botão direito > "Executar com o PowerShell". Ele pede elevação sozinho.
$ErrorActionPreference = 'Stop'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
$pasta = Split-Path -Parent $PSCommandPath
$pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pyw) { $pyw = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\*\pythonw.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1 -ExpandProperty FullName }
if (-not $pyw) { Write-Host "pythonw.exe não encontrado. Instale o Python 3 e rode o setup.ps1." -ForegroundColor Red; Start-Sleep 5; exit 1 }
$nome = 'SetupWidget'
$acao = New-ScheduledTaskAction -Execute $pyw -Argument "`"$pasta\widget.py`"" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$gatilho.Delay = 'PT10S'
$cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
Unregister-ScheduledTask -TaskName $nome -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Settings $cfg -Principal $principal -Description 'Widget de métricas do PC na área de trabalho' | Out-Null
Write-Host "Tarefa '$nome' registrada: o widget abre no logon como administrador." -ForegroundColor Green
Start-ScheduledTask -TaskName $nome
Write-Host "Widget iniciado agora." -ForegroundColor Green
Start-Sleep 3
