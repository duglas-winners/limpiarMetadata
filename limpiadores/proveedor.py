from pathlib import Path
from typing import Optional

from .base import LimpiadorBase
from .limpiador_imagen import LimpiadorImagen
from .limpiador_video import LimpiadorVideo


class ProveedorLimpiadores:
    """
    Resuelve y entrega la instancia del limpiador adecuado evaluando
    la extension del archivo.

    Las instancias se crean una sola vez y se reutilizan: los limpiadores
    no guardan estado, asi que son seguros de compartir entre hilos.
    """

    FORMATOS_IMAGEN = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    FORMATOS_VIDEO = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".m4v"}

    _limpiador_imagen = LimpiadorImagen()
    _limpiador_video = LimpiadorVideo()

    @classmethod
    def obtener_segun_archivo(cls, ruta_archivo: Path) -> Optional[LimpiadorBase]:
        extension = ruta_archivo.suffix.lower()

        if extension in cls.FORMATOS_IMAGEN:
            return cls._limpiador_imagen
        if extension in cls.FORMATOS_VIDEO:
            return cls._limpiador_video

        return None

    @classmethod
    def extensiones_soportadas(cls) -> set[str]:
        """Conjunto completo de extensiones que la aplicacion puede procesar."""
        return cls.FORMATOS_IMAGEN | cls.FORMATOS_VIDEO

    @classmethod
    def patron_dialogo(cls) -> str:
        """Cadena de comodines para el filtro del dialogo de seleccion de archivos."""
        return " ".join(f"*{ext}" for ext in sorted(cls.extensiones_soportadas()))
