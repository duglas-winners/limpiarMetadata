"""
Descarga el ejecutable de FFmpeg y lo deja en `recursos/` para que PyInstaller
lo incruste en la aplicacion final.

Se ejecuta solo en la maquina que compila, nunca en la del usuario final.
Si el binario ya existe, no vuelve a descargarlo.

Uso:
    python empaquetado/obtener_ffmpeg.py
"""

import io
import os
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "recursos"

# Compilaciones estaticas y autocontenidas: no arrastran librerias del sistema,
# que es justo lo que necesita un binario incrustado en otra aplicacion.
#
# En macOS la fuente depende de la arquitectura. evermeet.cx, que se usaba
# antes, solo publica binarios Intel: en un Mac con chip Apple el sistema los
# rechaza con "Bad CPU type in executable" salvo que Rosetta 2 este instalado.
# Como no lo esta por defecto, todos los videos fallaban. ffmpeg-static publica
# builds nativos para las dos arquitecturas.
FUENTES = {
    ("Windows", "*"): (
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "zip", "ffmpeg.exe",
    ),
    ("Darwin", "arm64"): (
        "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-darwin-arm64",
        "crudo", "ffmpeg",
    ),
    ("Darwin", "x86_64"): (
        "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-darwin-x64",
        "crudo", "ffmpeg",
    ),
    ("Linux", "*"): (
        "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        "tar", "ffmpeg",
    ),
}


def elegir_fuente() -> tuple:
    """
    Fuente que corresponde a este sistema y procesador.

    La arquitectura solo distingue en macOS; en el resto se usa la entrada
    comodin. `arm64` y `aarch64` son el mismo procesador con dos nombres.
    """
    sistema = platform.system()
    maquina = platform.machine().lower()
    if maquina in ("aarch64", "arm64"):
        maquina = "arm64"
    elif maquina in ("amd64", "x86_64"):
        maquina = "x86_64"

    if (sistema, maquina) in FUENTES:
        return FUENTES[(sistema, maquina)]
    if (sistema, "*") in FUENTES:
        return FUENTES[(sistema, "*")]
    raise RuntimeError(f"Sistema no soportado: {sistema} {maquina}")


def descargar(url: str) -> bytes:
    print(f"Descargando FFmpeg desde {url}")
    peticion = urllib.request.Request(url, headers={"User-Agent": "limpiador-metadatos"})
    with urllib.request.urlopen(peticion, timeout=300) as respuesta:
        datos = respuesta.read()
    print(f"  {len(datos) / 1_048_576:.1f} MB descargados")
    return datos


def extraer(datos: bytes, tipo: str, nombre_binario: str, destino: Path) -> Path:
    """
    Busca el ejecutable dentro del archivo comprimido, sin importar en que
    subcarpeta lo haya colocado quien publica la compilacion.
    """
    destino.mkdir(parents=True, exist_ok=True)
    ruta_final = destino / nombre_binario

    if tipo == "crudo":
        # Algunas fuentes publican el ejecutable directamente, sin comprimir
        ruta_final.write_bytes(datos)
    elif tipo == "zip":
        with zipfile.ZipFile(io.BytesIO(datos)) as archivo:
            interno = next(
                (n for n in archivo.namelist() if Path(n).name == nombre_binario), None
            )
            if interno is None:
                raise RuntimeError(f"No se encontro {nombre_binario} dentro del ZIP")
            ruta_final.write_bytes(archivo.read(interno))
    else:
        with tarfile.open(fileobj=io.BytesIO(datos), mode="r:xz") as archivo:
            interno = next(
                (m for m in archivo.getmembers() if Path(m.name).name == nombre_binario),
                None,
            )
            if interno is None:
                raise RuntimeError(f"No se encontro {nombre_binario} dentro del TAR")
            extraido = archivo.extractfile(interno)
            if extraido is None:
                raise RuntimeError(f"No se pudo leer {nombre_binario} del TAR")
            ruta_final.write_bytes(extraido.read())

    # En macOS y Linux el permiso de ejecucion no sobrevive al comprimido
    if os.name != "nt":
        ruta_final.chmod(ruta_final.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return ruta_final


def main() -> int:
    try:
        url, tipo, nombre = elegir_fuente()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    print(f"Plataforma: {platform.system()} {platform.machine()}")
    ruta_final = DESTINO / nombre

    if ruta_final.is_file():
        print(f"FFmpeg ya presente en {ruta_final} ({ruta_final.stat().st_size / 1_048_576:.1f} MB)")
        return 0

    try:
        ruta = extraer(descargar(url), tipo, nombre, DESTINO)
    except Exception as error:
        print(f"Error obteniendo FFmpeg: {error}", file=sys.stderr)
        return 1

    print(f"FFmpeg listo en {ruta} ({ruta.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
