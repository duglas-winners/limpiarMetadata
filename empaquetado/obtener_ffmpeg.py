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
import struct
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


# Constantes de Mach-O, el formato ejecutable de macOS (mach-o/loader.h)
MACHO_64 = 0xFEEDFACF
MACHO_UNIVERSAL = 0xCAFEBABE
CPU_MACOS = {0x0100000C: "arm64", 0x01000007: "x86_64"}


def arquitectura_macho(ruta: Path):
    """
    Lee del binario para que procesador esta compilado, sin ejecutarlo.

    Se necesita porque un FFmpeg de la arquitectura equivocada se ejecuta
    igualmente si Rosetta 2 esta instalado —como ocurre en los runners de
    GitHub—, de modo que probarlo no distingue. La cabecera si.

    Devuelve "arm64", "x86_64", "universal" o None si no es un Mach-O.
    """
    try:
        with open(ruta, "rb") as archivo:
            cabecera = archivo.read(8)
    except OSError:
        return None

    if len(cabecera) < 8:
        return None

    magia = struct.unpack("<I", cabecera[:4])[0]
    if magia == MACHO_64:
        return CPU_MACOS.get(struct.unpack("<I", cabecera[4:8])[0])

    # Los binarios universales se guardan en big endian
    if struct.unpack(">I", cabecera[:4])[0] == MACHO_UNIVERSAL:
        return "universal"

    return None


def sirve_lo_que_hay(ruta: Path) -> bool:
    """
    Decide si el FFmpeg ya presente vale o hay que volver a descargarlo.

    Fuera de macOS basta con que exista. En macOS se comprueba ademas la
    arquitectura: la cache de la compilacion puede conservar un binario de
    una version anterior, y sin esta comprobacion se daria por bueno. Fue
    exactamente lo que ocurrio al pasar de binarios Intel a nativos.
    """
    if not ruta.is_file():
        return False

    if platform.system() != "Darwin":
        return True

    propia = platform.machine().lower()
    propia = "arm64" if propia in ("arm64", "aarch64") else "x86_64"
    encontrada = arquitectura_macho(ruta)

    if encontrada in (propia, "universal"):
        return True

    print(f"  El FFmpeg presente es {encontrada or 'de formato desconocido'}, "
          f"pero hace falta {propia}. Se descarga de nuevo.")
    return False


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

    if sirve_lo_que_hay(ruta_final):
        print(f"FFmpeg ya presente en {ruta_final} "
              f"({ruta_final.stat().st_size / 1_048_576:.1f} MB)")
        return 0

    try:
        ruta = extraer(descargar(url), tipo, nombre, DESTINO)
    except Exception as error:
        print(f"Error obteniendo FFmpeg: {error}", file=sys.stderr)
        return 1

    detalle = f"{ruta.stat().st_size / 1_048_576:.1f} MB"
    if platform.system() == "Darwin":
        detalle += f", {arquitectura_macho(ruta) or 'formato desconocido'}"
    print(f"FFmpeg listo en {ruta} ({detalle})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
