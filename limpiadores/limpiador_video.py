import subprocess
from pathlib import Path

from recursos import ruta_ffmpeg

from .base import OPCIONES_POR_DEFECTO, LimpiadorBase, OpcionesLimpieza


class LimpiadorVideo(LimpiadorBase):
    """
    Elimina metadatos globales, por stream y capitulos de un video mediante FFmpeg.

    Tiene dos modos:

      - Sin comprimir (por defecto): remux con `-c copy`. Copia los flujos tal
        cual, sin recodificar. Un archivo de varios GB se procesa en segundos y
        sin ninguna perdida de calidad.

      - Comprimiendo: recodifica el video a un bitrate objetivo calculado segun
        su resolucion. Reduce el tamaño de forma notable, tarda bastante mas y
        pierde algo de calidad.

    Requiere el ejecutable de FFmpeg, incrustado en la aplicacion o del sistema.
    """

    def esta_disponible(self) -> tuple[bool, str]:
        if ruta_ffmpeg():
            return True, ""
        return False, (
            "FFmpeg no esta disponible. Esta compilacion no lo incluye y "
            "tampoco se encontro en el sistema."
        )

    def limpiar(
        self,
        ruta_entrada: Path,
        ruta_salida: Path,
        opciones: OpcionesLimpieza = OPCIONES_POR_DEFECTO,
    ) -> bool:
        ejecutable = ruta_ffmpeg()
        if not ejecutable:
            print(f"No se puede procesar {ruta_entrada.name}: FFmpeg no disponible")
            return False

        if opciones.comprimir_video:
            argumentos = self._argumentos_compresion(ruta_entrada)
        else:
            argumentos = ["-map", "0", "-c", "copy"]

        comando = [
            ejecutable,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(ruta_entrada),
            *argumentos,
            "-map_metadata", "-1",   # descarta metadatos del contenedor
            "-map_chapters", "-1",   # descarta capitulos
            # Al recodificar, libx264 y AAC firman su stream con el nombre del
            # codificador ("encoder: Lavc libx264"), que -map_metadata no toca
            # porque lo escribe el codificador, no el contenedor de entrada.
            "-metadata:s:v:0", "encoder=",
            "-metadata:s:a:0", "encoder=",
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
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proceso.returncode != 0:
                print(f"FFmpeg fallo en {ruta_entrada.name}: {proceso.stderr.strip()}")
                return False
            return True
        except Exception as error:
            print(f"Error procesando el video {ruta_entrada.name}: {error}")
            return False

    @staticmethod
    def _argumentos_compresion(ruta_entrada: Path) -> list[str]:
        """
        Argumentos de recodificacion a bitrate objetivo.

        Se usa bitrate objetivo y no calidad constante (CRF) por una razon de
        interfaz: con CRF el tamaño final es impredecible, y la aplicacion
        promete al usuario una estimacion antes de procesar. Con bitrate
        objetivo esa estimacion es fiable.
        """
        # Importacion diferida: `nucleo` depende de `limpiadores`, y hacerla
        # arriba crearia un ciclo entre ambos paquetes.
        from nucleo.medios import BITRATE_AUDIO_KBPS, bitrate_objetivo, info_video

        info = info_video(ruta_entrada)
        if info is None:
            # Sin datos para calcular el objetivo, se remuxea sin comprimir en
            # vez de arriesgar un bitrate arbitrario sobre un archivo del usuario.
            return ["-map", "0", "-c", "copy"]

        kbps = bitrate_objetivo(info)
        return [
            "-map", "0:v:0",              # una sola pista de video
            "-map", "0:a?",               # el audio, si lo hay
            "-c:v", "libx264",
            "-b:v", f"{kbps}k",
            "-maxrate", f"{int(kbps * 1.5)}k",
            "-bufsize", f"{kbps * 2}k",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",        # compatibilidad amplia de reproduccion
            "-c:a", "aac",
            "-b:a", f"{BITRATE_AUDIO_KBPS}k",
            "-movflags", "+faststart",    # permite reproducir mientras se descarga
        ]
