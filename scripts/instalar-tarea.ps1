# Prepara este computador y programa la actualización automática de Santander, BancoEstado y BICE.
# Ejecutar UNA vez, desde la carpeta del repositorio:
#     powershell -ExecutionPolicy Bypass -File scripts\instalar-tarea.ps1
#
# Requisitos: Python 3.10+ (python.org, marcar "Add python.exe to PATH") y Git for Windows.

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Repo ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Tarea = "Descuentos Chile - Santander, BancoEstado y BICE"

Write-Host "1/4  Revisando Python y Git..."
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) { throw "No se encontró Python. Instálalo desde https://www.python.org/downloads/ marcando 'Add python.exe to PATH'." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "No se encontró Git. Instálalo desde https://git-scm.com/download/win" }

Write-Host "2/4  Creando entorno de Python e instalando dependencias (unos minutos)..."
if (-not (Test-Path $Python)) { & $py.Source -m venv $Venv }
& $Python -m pip install --quiet --upgrade pip
& $Python -m pip install --quiet -r (Join-Path $Repo "requirements.txt")
& $Python -m playwright install chromium

Write-Host "3/4  Programando la tarea (todos los días a las 9:00; actualiza el día 1 y cada 3 días)..."
$script = Join-Path $Repo "scripts\actualizar-local.ps1"
$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" -WorkingDirectory $Repo
# Todos los días a las 9:00; el script decide si hace falta actualizar (día 1 o 3+ días sin actualizar)
$diario = New-ScheduledTaskTrigger -Daily -At "09:00"
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $Tarea -Action $accion -Trigger $diario -Settings $ajustes `
    -Description "Lee los descuentos de Santander, BancoEstado y BICE y los sube a GitHub (descuentos-chile)." -Force | Out-Null

Write-Host "4/4  Primera ejecución de prueba..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script -Forzar
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nListo. La tarea '$Tarea' quedó programada." -ForegroundColor Green
    Write-Host "Si el computador está apagado a la hora programada, se ejecuta apenas se encienda."
    Write-Host "Registro de cada ejecución: scripts\actualizar-local.log"
} else {
    Write-Host "`nLa tarea quedó programada, pero la prueba falló. Revisa scripts\actualizar-local.log" -ForegroundColor Yellow
}
