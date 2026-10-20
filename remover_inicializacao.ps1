# Remove a tarefa de inicialização automática do widget.
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""; exit }
Unregister-ScheduledTask -TaskName 'SetupWidget' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Tarefa removida." -ForegroundColor Green; Start-Sleep 2
