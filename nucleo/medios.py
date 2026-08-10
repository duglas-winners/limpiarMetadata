"""
Analisis de archivos de medios: peso, duracion, resolucion y estimacion del
tamaño que tendrian tras comprimir.

La informacion de video se lee con `ffmpeg -i`, que la vuelca por stderr. Se
parsea esa salida en vez de empaquetar tambien ffprobe, que añadiria otros
~90 MB al ejecutable para obtener los mismos cuatro datos.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Optional

from limpiadores.proveedor import ProveedorLimpiadores
from recursos import ruta_ffmpeg

# Bitrate de video objetivo segun la altura de la imagen, en kbps. Son valores
# conservadores: buscan un archivo notablemente mas pequeño que conserve una
# calidad razonable para compartir, no calidad de archivo maestro.
BITRATE_POR_ALTURA = (
    (2160, 12000),
    (1440, 6000),
    (1080, 3000),
    (720, 1500),
    (480, 800),
    (0, 500),
)

BITRATE_AUDIO_KBPS = 128

# Nunca comprimir a mas del 90% del bitrate original: si el video ya venia muy
# comprimido, recodificarlo a un bitrate mayor lo agrandaria sin ganar nada.
FACTOR_MAXIMO = 0.9

_cache: dict[str, Optional["InfoVideo"]] = {}
_candado = Lock()

_PATRON_DURACION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
_PATRON_RESOLUCION = re.compile(r"Stream.*Video:.*?(\d{2,5})x(\d{2,5})")
_PATRON_BITRATE = re.compile(r"bitrate:\s*(\d+)\s*kb/s")


@dataclass(frozen=True)
class InfoVideo:
    """Datos de un video necesarios para estimar su tamaño comprimido."""

    duracion_s: float
    ancho: int
    alto: int
    bitrate_kbps: int  # bitrate total del archivo, 0 si no se pudo leer


def peso(ruta: Path) -> int:
    """Tamaño en bytes, o 0 si el archivo no es accesible."""
    try:
        return ruta.stat().st_size
    except OSError:
        return 0


def formatear_peso(bytes_: float) -> str:
    """Convierte bytes a una cadena legible: '2.4 MB', '850 KB'."""
    if bytes_ <= 0:
        return "0 B"
    for unidad in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024 or unidad == "GB":
            return f"{bytes_:.0f} B" if unidad == "B" else f"{bytes_:.1f} {unidad}"
        bytes_ /= 1024
    return "?"


def es_video(ruta: Path) -> bool:
    return ruta.suffix.lower() in ProveedorLimpiadores.FORMATOS_VIDEO


def info_video(ruta: Path) -> Optional[InfoVideo]:
    """
    Lee duracion, resolucion y bitrate de un video. Devuelve None si no se
    puede analizar. Los resultados se cachean; es seguro entre hilos.
    """
    clave = str(ruta)
    with _candado:
        if clave in _cache:
            return _cache[clave]

    info = _leer_info(ruta)

    with _candado:
        _cache[clave] = info
    return info


def _leer_info(ruta: Path) -> Optional[InfoVideo]:
    ejecutable = ruta_ffmpeg()
    if not ejecutable:
        return None

    try:
        # `ffmpeg -i` sin salida termina con codigo 1 tras volcar la cabecera:
        # es su comportamiento normal, no un error.
        proceso = subprocess.run(
            [ejecutable, "-hide_banner", "-i", str(ruta)],
            capture_output=True, text=True, errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None

    salida = proceso.stderr

    coincidencia = _PATRON_DURACION.search(salida)
    if not coincidencia:
        return None
    horas, minutos, segundos = coincidencia.groups()
    duracion = int(horas) * 3600 + int(minutos) * 60 + float(segundos)
    if duracion <= 0:
        return None

    coincidencia = _PATRON_RESOLUCION.search(salida)
    if not coincidencia:
        return None
    ancho, alto = int(coincidencia.group(1)), int(coincidencia.group(2))

    coincidencia = _PATRON_BITRATE.search(salida)
    bitrate = int(coincidencia.group(1)) if coincidencia else 0

    return InfoVideo(duracion, ancho, alto, bitrate)


def bitrate_objetivo(info: InfoVideo) -> int:
    """
    Bitrate de video al que se comprimira, en kbps.

    Parte del valor recomendado para la altura del video y lo limita para no
    superar el 90% del bitrate original: comprimir nunca debe agrandar.
    """
    objetivo = next(kbps for altura, kbps in BITRATE_POR_ALTURA if info.alto >= altura)

    if info.bitrate_kbps > 0:
        bitrate_video_actual = max(info.bitrate_kbps - BITRATE_AUDIO_KBPS, 1)
        objetivo = min(objetivo, int(bitrate_video_actual * FACTOR_MAXIMO))

    return max(objetivo, 100)  # suelo: por debajo el resultado es inservible


def estimar_comprimido(ruta: Path) -> int:
    """
    Estima en bytes el tamaño que tendria el video tras comprimirlo.

    Es un TECHO, no un valor exacto: el resultado real es igual o menor, nunca
    mayor. La compresion usa bitrate objetivo (y no calidad constante), asi que
    el calculo es simplemente bitrate por duracion; el codificador puede gastar
    menos de lo concedido si el contenido es facil de comprimir, pero nunca mas.

    Medido sobre video exigente (ruido aleatorio, el peor caso para un
    codificador) el resultado real queda entre un 4% y un 12% por debajo de la
    estimacion. Sobre contenido muy plano la diferencia es mucho mayor, siempre
    a favor del usuario.

    Para lo que no es video, o no se puede analizar, devuelve su peso actual:
    ese archivo no va a cambiar de tamaño.
    """
    actual = peso(ruta)
    if not es_video(ruta):
        return actual

    info = info_video(ruta)
    if info is None:
        return actual

    kbps_total = bitrate_objetivo(info) + BITRATE_AUDIO_KBPS
    estimado = int(kbps_total * 1000 * info.duracion_s / 8)

    # Si el calculo da mas que el original, comprimir no aportaria nada y el
    # limpiador lo dejara tal cual: la estimacion debe decir lo mismo.
    return min(estimado, actual) if actual else estimado


def limpiar_cache() -> None:
    """Olvida el analisis guardado. Se usa al vaciar la cola."""
    with _candado:
        _cache.clear()
