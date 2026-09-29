"""
Autocomprobacion del paquete compilado.

Se compila con la misma configuracion que la aplicacion real, pero en modo
consola, y valida desde DENTRO del ejecutable que todo lo incrustado funciona:
Pillow, CustomTkinter, el FFmpeg empaquetado y la limpieza real de un archivo.

Su otro cometido es medir cuanto tarda el arranque, que en un ejecutable de un
solo archivo incluye descomprimir todo el contenido a una carpeta temporal.

No forma parte de la aplicacion que recibe el usuario.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

INICIO = time.time()


def main() -> int:
    fallos = []

    print("== Autocomprobacion del paquete ==")
    print(f"Empaquetado: {getattr(sys, 'frozen', False)}")

    from recursos import esta_empaquetado, raiz_recursos, ruta_ffmpeg

    print(f"Raiz de recursos: {raiz_recursos()}")

    # 1. Dependencias graficas
    try:
        import customtkinter
        from PIL import Image
        print(f"OK  Pillow y CustomTkinter {customtkinter.__version__} disponibles")
    except Exception as error:
        print(f"FALLO  Dependencias graficas: {error}")
        return 1

    # 2. FFmpeg incrustado
    #
    # Se comprueba el bit de ejecucion aparte de que arranque. Es la
    # comprobacion que faltaba cuando FFmpeg viajaba como dato y no como
    # binario: en macOS llegaba sin permiso de ejecucion, el paquete parecia
    # correcto, y fallaban todos los videos en cuanto lo usaba un usuario.
    ff = ruta_ffmpeg()
    if ff and os.name != "nt":
        if os.access(ff, os.X_OK):
            print(f"OK  FFmpeg tiene permiso de ejecucion ({oct(os.stat(ff).st_mode)[-3:]})")
        else:
            fallos.append("FFmpeg sin permiso de ejecucion")
            print(f"FALLO  FFmpeg existe pero NO es ejecutable: {ff}")

    if not ff:
        fallos.append("FFmpeg no resuelto")
        print("FALLO  FFmpeg no encontrado")
    else:
        dentro = esta_empaquetado() and str(raiz_recursos()) in ff
        version = subprocess.run([ff, "-version"], capture_output=True, text=True)
        etiqueta = "incrustado" if dentro else "del sistema"
        print(f"OK  FFmpeg {etiqueta}: {version.stdout.splitlines()[0][:60]}")
        if esta_empaquetado() and not dentro:
            fallos.append("FFmpeg no viaja dentro del paquete")

    # 3. Limpieza real de una imagen y un video
    from nucleo.procesador import ProcesadorEnLote

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        entradas = []

        jpg = tmp / "prueba.jpg"
        img = Image.new("RGB", (32, 32), (10, 120, 200))
        exif = img.getexif()
        exif[271] = "MarcaSecreta"
        img.save(jpg, exif=exif)
        entradas.append(jpg)

        if ff:
            mp4 = tmp / "prueba.mp4"
            subprocess.run([
                ff, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=1",
                "-metadata", "artist=Secreto", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(mp4),
            ], check=True)
            entradas.append(mp4)

        resultados = ProcesadorEnLote(max_hilos=2).procesar_archivos(
            entradas, tmp / "salida", lambda r, a, t: None
        )

        for r in resultados:
            estado = "OK " if r.exito else "FALLO"
            print(f"{estado} Limpieza de {r.ruta_origen.name}: {r.mensaje}")
            if not r.exito:
                fallos.append(f"limpieza de {r.ruta_origen.name}")

        limpio = next((r.ruta_salida for r in resultados
                       if r.exito and r.ruta_origen.suffix == ".jpg"), None)
        if limpio:
            with Image.open(limpio) as im:
                if dict(im.getexif()):
                    fallos.append("el EXIF sobrevivio a la limpieza")
                    print("FALLO  Quedo EXIF residual")
                else:
                    print("OK  EXIF eliminado y verificado")

    print(f"\nComprobaciones ejecutadas en {time.time() - INICIO:.1f}s")

    if fallos:
        print(f"\nRESULTADO: {len(fallos)} fallo(s): {', '.join(fallos)}")
        return 1

    print("\nRESULTADO: todo correcto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
