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
FUENTES = {
    "Windows": (
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "zip",
        "ffmpeg.exe",
    ),
    "Darwin": (
        "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
        "zip",
        "ffmpeg",
    ),
    "Linux": (
        "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        "tar",
        "ffmpeg",
    ),
}


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

    if tipo == "zip":
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
    sistema = platform.system()
    if sistema not in FUENTES:
        print(f"Sistema no soportado: {sistema}", file=sys.stderr)
        return 1

    url, tipo, nombre = FUENTES[sistema]
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
