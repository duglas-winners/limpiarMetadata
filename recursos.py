"""
Localizacion de recursos que viajan dentro del ejecutable empaquetado.

En desarrollo los archivos estan junto al codigo fuente; en un ejecutable de
PyInstaller estan en una carpeta temporal cuya ruta llega en `sys._MEIPASS`.
Este modulo aisla esa diferencia para que el resto del codigo no la note.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional


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


def _asegurar_ejecutable(ruta: Path) -> bool:
    """
    Comprueba que el archivo se puede ejecutar y, si no, intenta concederlo.

    Hace falta porque PyInstaller copia los recursos declarados como datos sin
    el bit de ejecucion. En Windows da igual, pero en macOS y Linux deja el
    FFmpeg incrustado inservible: existe, pesa lo que debe, y al lanzarlo
    devuelve "Permission denied".
    """
    if os.name == "nt":
        return True

    if os.access(ruta, os.X_OK):
        return True

    try:
        modo = ruta.stat().st_mode
        ruta.chmod(modo | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return os.access(ruta, os.X_OK)
    except OSError:
        return False


def ruta_ffmpeg() -> Optional[str]:
    """
    Devuelve la ruta al ejecutable de FFmpeg que debe usarse.

    Prioridad:
      1. La copia empaquetada dentro de la aplicacion (caso normal del usuario
         final: no tiene que instalar nada).
      2. Un FFmpeg instalado en el PATH del sistema (caso del desarrollador, o
         de una compilacion ligera sin FFmpeg incluido).

    Devuelve None si no hay ninguno utilizable. No basta con que el archivo
    exista: tiene que poder ejecutarse, y si la copia incrustada no puede, se
    recurre a la del sistema en vez de fallar archivo por archivo.
    """
    nombre = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    incluido = ruta_recurso(f"recursos/{nombre}")

    if incluido.is_file() and _asegurar_ejecutable(incluido):
        return str(incluido)

    return shutil.which("ffmpeg")


def comprobar_ffmpeg() -> tuple[bool, str]:
    """
    Verifica que FFmpeg no solo esta, sino que arranca de verdad.

    Se lanza `ffmpeg -version`, que es inmediato. Comprobar solo que el archivo
    existe dejaba pasar el caso en que esta pero no se puede ejecutar, y
    entonces el fallo aparecia mucho despues, repetido en cada archivo del lote
    y sin explicacion.

    Devuelve (funciona, detalle). `detalle` lleva la version cuando funciona y
    el motivo cuando no.
    """
    ruta = ruta_ffmpeg()
    if not ruta:
        nombre = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        incluido = ruta_recurso(f"recursos/{nombre}")
        if incluido.is_file():
            return False, (
                f"El FFmpeg incluido existe en {incluido} pero el sistema no "
                f"permite ejecutarlo, y no hay otro instalado."
            )
        return False, "No se encontro FFmpeg ni incrustado ni en el sistema."

    # macOS ejecuta las aplicaciones descargadas desde una copia temporal de
    # solo lectura (App Translocation) mientras no se muevan a Aplicaciones.
    # Ahi no se puede corregir ningun permiso, asi que conviene decirlo.
    trasladada = "/AppTranslocation/" in str(ruta)

    try:
        proceso = subprocess.run(
            [ruta, "-version"],
            capture_output=True, text=True, errors="replace", timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as error:
        detalle = f"No se pudo ejecutar {ruta}: {error}"
        if trasladada:
            detalle += (
                "\n\nAdemas, la aplicacion se esta ejecutando desde una copia "
                "temporal de macOS. Arrastrala a la carpeta Aplicaciones y "
                "abrela desde ahi."
            )
        return False, detalle

    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout or "").strip()
        return False, f"{ruta} devolvio codigo {proceso.returncode}: {detalle[:300]}"

    primera = (proceso.stdout or "").splitlines()
    return True, (primera[0] if primera else "FFmpeg disponible")
