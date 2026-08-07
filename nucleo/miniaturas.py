"""
Generacion de miniaturas para la vista de detalle.

Las imagenes se reducen con Pillow; de los videos se extrae un fotograma con
FFmpeg. Ambas operaciones son lentas comparadas con dibujar la interfaz, asi
que se ejecutan en hilos y el resultado se guarda en cache.
"""

import io
import subprocess
from pathlib import Path
from threading import Lock
from typing import Optional

from PIL import Image

from limpiadores.proveedor import ProveedorLimpiadores
from recursos import ruta_ffmpeg

LADO_MINIATURA = 64

# Cache compartida entre hilos: la misma miniatura no se genera dos veces
_cache: dict[tuple[str, int], Image.Image] = {}
_candado = Lock()


def obtener(ruta: Path, lado: int = LADO_MINIATURA) -> Optional[Image.Image]:
    """
    Devuelve una miniatura cuadrada de `lado` pixeles, o None si el archivo no
    admite vista previa (formato no soportado, archivo dañado, FFmpeg ausente).

    Es seguro llamarla desde varios hilos.
    """
    clave = (str(ruta), lado)
    with _candado:
        if clave in _cache:
            return _cache[clave]

    imagen = _generar(ruta, lado)

    if imagen is not None:
        with _candado:
            _cache[clave] = imagen
    return imagen


def _generar(ruta: Path, lado: int) -> Optional[Image.Image]:
    extension = ruta.suffix.lower()
    try:
        if extension in ProveedorLimpiadores.FORMATOS_IMAGEN:
            return _desde_imagen(ruta, lado)
        if extension in ProveedorLimpiadores.FORMATOS_VIDEO:
            return _desde_video(ruta, lado)
    except Exception:
        # Una vista previa que falla no debe impedir procesar el archivo:
        # la interfaz mostrara un marcador generico en su lugar.
        return None
    return None


def _encajar(imagen: Image.Image, lado: int) -> Image.Image:
    """
    Reduce la imagen y la centra sobre un lienzo cuadrado transparente, para
    que todas las filas de la lista queden alineadas sea cual sea la proporcion.
    """
    imagen = imagen.convert("RGBA")
    imagen.thumbnail((lado, lado), Image.Resampling.LANCZOS)

    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    lienzo.paste(
        imagen,
        ((lado - imagen.width) // 2, (lado - imagen.height) // 2),
    )
    return lienzo


def _desde_imagen(ruta: Path, lado: int) -> Image.Image:
    with Image.open(ruta) as imagen:
        imagen.load()
        return _encajar(imagen, lado)


def _desde_video(ruta: Path, lado: int) -> Optional[Image.Image]:
    """
    Extrae un fotograma del video y lo devuelve como imagen.

    Busca en el segundo 1 para evitar los fundidos de entrada en negro que
    abren muchos videos; si el clip es mas corto, reintenta desde el inicio.
    """
    ejecutable = ruta_ffmpeg()
    if not ejecutable:
        return None

    for desplazamiento in ("1", "0"):
        proceso = subprocess.run(
            [
                ejecutable, "-hide_banner", "-loglevel", "error",
                "-ss", desplazamiento,
                "-i", str(ruta),
                "-frames:v", "1",
                "-f", "image2", "-vcodec", "png",
                "-",
            ],
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proceso.returncode == 0 and proceso.stdout:
            with Image.open(io.BytesIO(proceso.stdout)) as fotograma:
                fotograma.load()
                return _encajar(fotograma, lado)

    return None


def limpiar_cache() -> None:
    """Libera las miniaturas guardadas. Se usa al vaciar la cola."""
    with _candado:
        _cache.clear()
