"""
Localizacion de recursos que viajan dentro del ejecutable empaquetado.

En desarrollo los archivos estan junto al codigo fuente; en un ejecutable de
PyInstaller estan en una carpeta temporal cuya ruta llega en `sys._MEIPASS`.
Este modulo aisla esa diferencia para que el resto del codigo no la note.
"""

import shutil
import sys
from pathlib import Path


def esta_empaquetado() -> bool:
    """True si la aplicacion corre como ejecutable de PyInstaller."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def raiz_recursos() -> Path:
    """Carpeta base desde la que resolver los archivos incluidos."""
    if esta_empaquetado():
        return Path(sys._MEIPASS)
    # Este modulo vive en la raiz del proyecto, junto a `recursos/`
    return Path(__file__).resolve().parent


def ruta_recurso(nombre_relativo: str) -> Path:
    """Ruta absoluta a un archivo incluido en el paquete."""
    return raiz_recursos() / nombre_relativo


def ruta_ffmpeg() -> str | None:
    """
    Devuelve la ruta al ejecutable de FFmpeg que debe usarse.

    Prioridad:
      1. La copia empaquetada dentro de la aplicacion (caso normal del usuario
         final: no tiene que instalar nada).
      2. Un FFmpeg instalado en el PATH del sistema (caso del desarrollador, o
         de una compilacion ligera sin FFmpeg incluido).

    Devuelve None si no hay ninguno disponible.
    """
    nombre = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    incluido = ruta_recurso(f"recursos/{nombre}")
    if incluido.is_file():
        return str(incluido)

    return shutil.which("ffmpeg")
