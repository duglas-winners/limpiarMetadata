import subprocess
from pathlib import Path

from recursos import ruta_ffmpeg

from .base import LimpiadorBase


class LimpiadorVideo(LimpiadorBase):
    """
    Elimina metadatos globales, por stream y capitulos de un video mediante FFmpeg.
    Realiza remuxing (-c copy) para procesar el archivo en milisegundos sin recodificar.

    Usa el FFmpeg empaquetado dentro de la aplicacion si existe; si no, recurre
    al que haya instalado en el sistema.
    """

    def esta_disponible(self) -> tuple[bool, str]:
        if ruta_ffmpeg():
            return True, ""
        return False, (
            "FFmpeg no esta disponible. Esta compilacion no lo incluye y "
            "tampoco se encontro en el sistema."
        )

    def limpiar(self, ruta_entrada: Path, ruta_salida: Path) -> bool:
        ejecutable = ruta_ffmpeg()
        if not ejecutable:
            print(f"No se puede procesar {ruta_entrada.name}: FFmpeg no disponible")
            return False

        comando = [
            ejecutable,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(ruta_entrada),
            "-map", "0",             # conserva todos los streams (video, audio, subtitulos)
            "-map_metadata", "-1",   # descarta metadatos del contenedor
            "-map_chapters", "-1",   # descarta capitulos
            "-c", "copy",            # remux sin recodificar
            # Sin bitexact, FFmpeg firma el archivo con su propia version
            # ("encoder: Lavf..."), delatando que el archivo fue procesado.
            "-fflags", "+bitexact",
            "-flags:v", "+bitexact",
            "-flags:a", "+bitexact",
            str(ruta_salida),
        ]

        try:
            proceso = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proceso.returncode != 0:
                print(f"FFmpeg fallo en {ruta_entrada.name}: {proceso.stderr.strip()}")
                return False
            return True
        except Exception as error:
            print(f"Error procesando el video {ruta_entrada.name}: {error}")
            return False
