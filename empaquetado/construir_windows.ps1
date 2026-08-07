# Compila el ejecutable de Windows.
#
#   powershell -ExecutionPolicy Bypass -File empaquetado\construir_windows.ps1
#
# Resultado: dist\LimpiadorMetadatos.exe  (autocontenido, doble clic)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

Write-Host "== 1/4 Dependencias ==" -ForegroundColor Cyan
python -m pip install -q -r requerimientos.txt
python -m pip install -q pyinstaller

Write-Host "== 2/4 FFmpeg ==" -ForegroundColor Cyan
python empaquetado\obtener_ffmpeg.py
if ($LASTEXITCODE -ne 0) { throw "No se pudo obtener FFmpeg" }

Write-Host "== 3/4 Limpieza de compilaciones previas ==" -ForegroundColor Cyan
foreach ($carpeta in @("build", "dist")) {
    if (Test-Path $carpeta) { Remove-Item $carpeta -Recurse -Force }
}

Write-Host "== 4/4 PyInstaller ==" -ForegroundColor Cyan
python -m PyInstaller empaquetado\limpiador.spec --noconfirm --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo" }

$exe = Join-Path $raiz "dist\LimpiadorMetadatos.exe"
if (-not (Test-Path $exe)) { throw "No se genero el ejecutable" }

$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "Listo: $exe ($mb MB)" -ForegroundColor Green
