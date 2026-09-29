"""
Traduccion de fallos tecnicos a causas que el usuario pueda identificar.

FFmpeg y Pillow informan de sus errores en ingles y con vocabulario interno
("moov atom not found", "Invalid data found when processing input"). Este
modulo reconoce los casos frecuentes y devuelve una frase que dice que le pasa
al archivo y que se puede hacer, conservando aparte el volcado original para
quien quiera verlo en la consola.
"""

import re
from typing import NamedTuple


class Causa(NamedTuple):
    """Diagnostico de un fallo: que paso y que hacer."""

    resumen: str      # cabe en la fila de la lista
    explicacion: str  # una frase mas, para la consola


# El orden importa: se devuelve la primera que encaje, asi que las causas mas
# especificas van antes que las genericas.
PATRONES = (
    # --- La aplicacion no puede ejecutar FFmpeg ---
    (r"permission denied|errno 13|not permitted to execute|no se puede ejecutar",
     Causa("FFmpeg no se puede ejecutar",
           "El sistema no permite ejecutar el FFmpeg incluido en la aplicacion. "
           "Suele ser un problema de permisos del propio programa, no del archivo.")),
    (r"bad cpu type|cannot execute binary|exec format error",
     Causa("FFmpeg no es compatible con este equipo",
           "El FFmpeg incluido esta compilado para otro procesador. Descarga la "
           "version mas reciente de la aplicacion, que ya trae una compilacion "
           "nativa. Como solucion inmediata, en un Mac con chip Apple puedes "
           "instalar Rosetta 2 ejecutando en la Terminal: "
           "softwareupdate --install-rosetta --agree-to-license")),

    # --- El archivo esta dañado ---
    (r"moov atom not found",
     Causa("Video incompleto o dañado",
           "Al archivo le falta el indice interno (atomo moov). Suele pasar con "
           "grabaciones interrumpidas o descargas a medias.")),
    (r"invalid data found when processing input",
     Causa("El archivo esta dañado o no es un video",
           "FFmpeg no reconoce el contenido. Comprueba que se abre en un "
           "reproductor normal.")),
    (r"could not find codec parameters|unknown format|invalid argument",
     Causa("Formato interno no reconocido",
           "El contenedor se abre pero su contenido no se puede interpretar.")),
    (r"does not contain any stream|no streams",
     Causa("El archivo no contiene video ni audio",
           "El contenedor esta vacio.")),
    (r"truncat|unexpected end of file|premature end",
     Causa("El archivo esta cortado",
           "Termina antes de lo que declara su cabecera.")),

    # --- Problemas de codec ---
    (r"unknown encoder|encoder not found|unknown decoder|decoder not found",
     Causa("Codec no disponible",
           "Esta compilacion de FFmpeg no incluye el codec que necesita el archivo.")),
    (r"codec not currently supported in container|could not write header",
     Causa("El contenido no cabe en un MP4",
           "Alguna pista (a menudo subtitulos o un audio poco comun) no es "
           "compatible con el formato de salida. Prueba a comprimir el video.")),

    # --- Problemas de acceso al disco ---
    (r"no such file or directory|cannot find the (file|path)",
     Causa("El archivo ya no esta donde estaba",
           "Se movio, se renombro o se desconecto la unidad despues de agregarlo.")),
    (r"no space left|disk full|not enough space",
     Causa("No queda espacio en el disco",
           "La carpeta destino no tiene sitio para el archivo resultante.")),
    (r"read-only file system|acceso denegado|operation not permitted",
     Causa("Sin permiso para escribir en la carpeta destino",
           "Elige otra carpeta, o concede acceso a la aplicacion en los ajustes "
           "de privacidad del sistema.")),
    (r"resource temporarily unavailable|device or resource busy",
     Causa("El archivo esta en uso",
           "Otro programa lo tiene abierto. Cierralo e intentalo de nuevo.")),
)

GENERICA = Causa(
    "No se pudo procesar",
    "FFmpeg termino con error. El detalle tecnico esta en la consola.",
)


def interpretar(texto: str) -> Causa:
    """
    Reconoce la causa en la salida de error de FFmpeg o en el texto de una
    excepcion. Si nada encaja, devuelve la causa generica: preferible a
    inventar un diagnostico que podria mandar al usuario por mal camino.
    """
    if not texto:
        return GENERICA

    plano = texto.lower()
    for patron, causa in PATRONES:
        if re.search(patron, plano):
            return causa

    return GENERICA


def resumir_salida(texto: str, maximo_lineas: int = 12) -> str:
    """
    Recorta el volcado de FFmpeg para la consola.

    Se queda con las ultimas lineas, que son donde esta el error: las primeras
    suelen ser la descripcion de los streams de entrada, que no aporta nada
    cuando algo ha fallado.
    """
    lineas = [l.rstrip() for l in texto.strip().splitlines() if l.strip()]
    if len(lineas) <= maximo_lineas:
        return "\n".join(lineas)
    return "\n".join([f"(... {len(lineas) - maximo_lineas} lineas mas arriba)"]
                     + lineas[-maximo_lineas:])
