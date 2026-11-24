# Actualiza desde este computador los bancos que bloquean a los servidores de GitHub
# (Santander, BancoEstado y los beneficios de BICE fuera de restaurantes) y sube los datos
# al repositorio. Vercel publica solo.
#
# Uso manual:  powershell -ExecutionPolicy Bypass -File scripts\actualizar-local.ps1
# Para dejarlo automático, ejecutar una vez scripts\instalar-tarea.ps1

param([switch]$Forzar)  # -Forzar: actualizar aunque no toque

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$Bancos = @("santander", "bancoestado")
$Log = Join-Path $Repo "scripts\actualizar-local.log"
$env:PYTHONUTF8 = "1"
$env:NAVEGADOR_VISIBLE = "1"   # Santander, BancoEstado y BICE bloquean el navegador invisible
$env:PYTHONIOENCODING = "utf-8"

function Escribir($msg) {
    $linea = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $linea
    Add-Content -Path $Log -Value $linea -Encoding UTF8
}

function Invoke-Git { & git.exe -C $Repo @args; if ($LASTEXITCODE -ne 0) { throw "git $args falló" } }

function Leer-Bancos {
    Push-Location $Repo
    # BICE (sitio oficial, navegador visible): beneficios fuera de restaurantes. Si falla, se sigue igual.
    $ErrorActionPreference = "Continue"
    & $Python -m scraper.bice_sitio 2>&1 | ForEach-Object { Escribir $_ }
    # Python escribe avisos en stderr; no deben detener el script
    $ErrorActionPreference = "Continue"
    try {
        & $Python -m scraper.run @Bancos 2>&1 | ForEach-Object { Escribir $_ }
        if ($LASTEXITCODE -ne 0) { throw "scraper.run terminó con código $LASTEXITCODE" }
    } finally { Pop-Location }
}

$Marca = Join-Path $Repo "scripts\ultima-actualizacion.txt"

try {
    # La tarea corre todos los días; solo se actualiza el día 1 de cada mes o si pasaron 3 días o más
    if (-not $Forzar -and (Test-Path $Marca) -and (Get-Date).Day -ne 1) {
        $ultima = [datetime]::ParseExact((Get-Content $Marca -Raw).Trim(), "yyyy-MM-dd", $null)
        if (((Get-Date).Date - $ultima).TotalDays -lt 3) {
            Escribir "Última actualización: $($ultima.ToString('yyyy-MM-dd')). Nada que hacer hoy."
            exit 0
        }
    }
    if (-not (Test-Path $Python)) { throw "No existe $Python. Ejecuta primero scripts\instalar-tarea.ps1" }
    Escribir "Inicio: $($Bancos -join ', ')"

    # Partir siempre desde la última versión publicada
    Invoke-Git fetch --quiet origin main
    Invoke-Git checkout --quiet main
    Invoke-Git reset --quiet --hard origin/main

    for ($intento = 1; $intento -le 2; $intento++) {
        Leer-Bancos
        Invoke-Git add data web/data
        & git -C $Repo diff --cached --quiet
        if ($LASTEXITCODE -eq 0) { Escribir "Sin cambios en los datos."; break }
        Invoke-Git commit --quiet -m ("Actualizar {0} (computador local) {1}" -f ($Bancos -join " y "), (Get-Date -Format "yyyy-MM-dd"))
        & git -C $Repo push --quiet origin main
        if ($LASTEXITCODE -eq 0) { Escribir "Datos subidos a GitHub."; break }
        # Alguien (la actualización de GitHub) subió datos mientras tanto: repetir sobre lo nuevo
        Escribir "El repositorio cambió mientras se leían los bancos; se reintenta."
        Invoke-Git fetch --quiet origin main
        Invoke-Git reset --quiet --hard origin/main
        if ($intento -eq 2) { throw "No se pudo subir después de 2 intentos" }
    }
    Set-Content -Path $Marca -Value (Get-Date -Format "yyyy-MM-dd") -Encoding ASCII
    Escribir "Fin."
} catch {
    Escribir "ERROR: $_"
    exit 1
}
