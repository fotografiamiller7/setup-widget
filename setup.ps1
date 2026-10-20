# Instala tudo que o Setup Widget precisa:
#   1. pacotes Python (pythonnet, psutil)
#   2. LibreHardwareMonitorLib + dependências (NuGet) em .\lib
#   3. driver PawnIO (winget) - necessário para ler temperatura da CPU e sensores da placa-mãe
#
# Uso: botão direito > "Executar com o PowerShell"  (ou: powershell -ExecutionPolicy Bypass -File setup.ps1)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Base = Split-Path -Parent $PSCommandPath
$Lib  = Join-Path $Base 'lib'
$Dl   = Join-Path $env:TEMP 'SetupWidget_dl'   # caminho curto, evita o limite de 260 caracteres
New-Item -ItemType Directory -Force $Lib, $Dl | Out-Null

# ---------- 1. Python ----------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "Python não encontrado. Instale o Python 3.10+ (python.org ou 'winget install Python.Python.3.12') e rode de novo." -ForegroundColor Red; exit 1 }
Write-Host "[1/3] Instalando pythonnet e psutil..." -ForegroundColor Cyan
& python -m pip install --quiet --upgrade pythonnet psutil

# ---------- 2. DLLs do NuGet ----------
Write-Host "[2/3] Baixando LibreHardwareMonitorLib e dependências..." -ForegroundColor Cyan
$done = @{}
$queue = New-Object System.Collections.Queue
$queue.Enqueue(@('LibreHardwareMonitorLib', '0.9.6'))
$prefs = @('net472','net48','net481','net47','net462','net461','net46','net45','net40','net35','netstandard2.0','netstandard1.6','netstandard1.3','netstandard1.1','netstandard1.0')
while ($queue.Count -gt 0) {
    $pv = $queue.Dequeue(); $p = $pv[0]; $v = $pv[1]
    if ($done.ContainsKey($p.ToLower())) { continue }
    $done[$p.ToLower()] = $v
    $zip = "$Dl\$p-$v.zip"; $dir = "$Dl\$p-$v"
    if (-not (Test-Path $dir)) {
        try { Invoke-WebRequest "https://www.nuget.org/api/v2/package/$p/$v" -OutFile $zip } catch { Write-Host "  falha ao baixar $p $v" -ForegroundColor Yellow; continue }
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $dir)
    }
    $copied = $false
    foreach ($tf in $prefs) {
        foreach ($b in @("$dir\runtimes\win-x64\lib\$tf", "$dir\lib\$tf")) {
            if (Test-Path $b) {
                $dlls = Get-ChildItem $b -Filter *.dll -File -ErrorAction SilentlyContinue
                if ($dlls) { $dlls | ForEach-Object { Copy-Item $_.FullName $Lib -Force }; Write-Host "  $p $v ($tf)"; $copied = $true; break }
            }
        }
        if ($copied) { break }
    }
    $nuspec = Get-ChildItem $dir -Filter *.nuspec | Select-Object -First 1
    if (-not $nuspec) { continue }
    [xml]$x = Get-Content $nuspec.FullName
    $groups = $x.package.metadata.dependencies.group
    $deps = $null
    if ($groups) {
        foreach ($tf in @('.NETFramework4.7.2','net472','.NETFramework4.8','.NETFramework4.6.2','.NETFramework4.6.1','.NETFramework4.5','.NETStandard2.0','')) {
            $g = $groups | Where-Object { ($_.targetFramework -as [string]) -eq $tf } | Select-Object -First 1
            if ($g) { $deps = $g.dependency; break }
        }
        if (-not $deps) { $deps = ($groups | Select-Object -First 1).dependency }
    } else { $deps = $x.package.metadata.dependencies.dependency }
    foreach ($d in $deps) {
        if (-not $d) { continue }
        $ver = ($d.version -replace '[\[\]\(\)]', '').Split(',')[0].Trim()
        if ($ver) { $queue.Enqueue(@($d.id, $ver)) }
    }
}
# System.Management já existe no .NET Framework; a versão NuGet (netstandard) conflita.
Remove-Item "$Lib\System.Management.dll" -Force -ErrorAction SilentlyContinue
Remove-Item $Dl -Recurse -Force -ErrorAction SilentlyContinue

# ---------- 3. PawnIO ----------
Write-Host "[3/3] Verificando driver PawnIO..." -ForegroundColor Cyan
$pawn = (Test-Path "$env:ProgramFiles\PawnIO") -or (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'PawnIO')
if ($pawn) { Write-Host "  PawnIO já instalado." }
else {
    Write-Host "  Instalando PawnIO via winget (vai pedir permissão de administrador)..."
    winget install --id namazso.PawnIO --exact --silent --accept-package-agreements --accept-source-agreements
}

Write-Host ""
Write-Host "Pronto! Abra o widget com 'Iniciar Widget.vbs'." -ForegroundColor Green
Write-Host "Para abrir automaticamente no logon, execute 'instalar_inicializacao.ps1'."
Start-Sleep 4
