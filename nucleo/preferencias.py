"""
Preferencias que sobreviven al cierre de la aplicacion.

Se guardan en un JSON dentro de la carpeta de configuracion del usuario, la
que cada sistema destina a esto:

    Windows   %APPDATA%\\LimpiadorMetadatos\\preferencias.json
    macOS     ~/Library/Application Support/LimpiadorMetadatos/preferencias.json
    Linux     ~/.config/LimpiadorMetadatos/preferencias.json

No se guardan junto al ejecutable a proposito: en Windows suele estar en una
ruta sin permiso de escritura, y en macOS dentro del propio paquete .app, que
no debe modificarse.

Ninguna operacion de este modulo puede tumbar la aplicacion. Si el archivo no
se puede leer o escribir —permisos, disco lleno, JSON corrupto— se sigue
adelante con los valores por defecto: perder una preferencia es un
inconveniente, no arrancar es un fallo.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

NOMBRE_APLICACION = "LimpiadorMetadatos"
NOMBRE_ARCHIVO = "preferencias.json"

CARPETA_DESTINO_POR_DEFECTO = Path.home() / "Archivos_Limpiados"

POR_DEFECTO: Dict[str, Any] = {
    "carpeta_destino": str(CARPETA_DESTINO_POR_DEFECTO),
    "modo_vista": "lista",
}


def carpeta_configuracion() -> Path:
    """Carpeta donde el sistema espera que la aplicacion guarde sus ajustes."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")

    return Path(base) / NOMBRE_APLICACION


def ruta_archivo() -> Path:
    return carpeta_configuracion() / NOMBRE_ARCHIVO


def cargar() -> Dict[str, Any]:
    """
    Lee las preferencias guardadas, completadas con los valores por defecto.

    Un archivo ausente o ilegible no es un error: significa primera ejecucion.
    """
    valores = dict(POR_DEFECTO)

    try:
        with open(ruta_archivo(), encoding="utf-8") as archivo:
            guardadas = json.load(archivo)
        if isinstance(guardadas, dict):
            # Solo se aceptan claves conocidas: un archivo de una version
            # posterior no debe inyectar ajustes que esta no entiende.
            valores.update(
                {k: v for k, v in guardadas.items() if k in POR_DEFECTO}
            )
    except (OSError, ValueError):
        pass

    return valores


def guardar(valores: Dict[str, Any]) -> bool:
    """
    Escribe las preferencias. Devuelve si lo consiguio, para quien quiera
    avisar; nadie esta obligado a comprobarlo.

    Escribe primero en un archivo temporal y luego lo reemplaza, de modo que un
    corte a mitad de la escritura no deje el JSON a medias e ilegible.
    """
    destino = ruta_archivo()
    temporal = destino.with_suffix(".tmp")

    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(valores, archivo, indent=2, ensure_ascii=False)
        os.replace(temporal, destino)
        return True
    except OSError:
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def carpeta_destino_valida(valores: Dict[str, Any]) -> Path:
    """
    Devuelve la carpeta destino guardada, o la de por defecto si ya no sirve.

    La carpeta pudo desaparecer entre dos sesiones: un disco externo
    desconectado, una unidad de red caida, una carpeta borrada. En ese caso se
    vuelve a la de por defecto en vez de arrancar apuntando a una ruta muerta.
    """
    guardada = Path(valores.get("carpeta_destino", ""))

    try:
        if guardada.is_dir():
            return guardada
    except OSError:
        # Rutas de red inaccesibles pueden lanzar en vez de devolver False
        pass

    return CARPETA_DESTINO_POR_DEFECTO
