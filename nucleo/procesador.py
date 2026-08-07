from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from limpiadores.proveedor import ProveedorLimpiadores


@dataclass(frozen=True)
class ResultadoArchivo:
    """Resultado del procesamiento de un unico archivo de la cola."""

    ruta_origen: Path
    ruta_salida: Path | None
    exito: bool
    mensaje: str


class ProcesadorEnLote:
    """
    Administra la cola de procesamiento en paralelo mediante un grupo de hilos.

    El trabajo real (Pillow y FFmpeg) libera el GIL en su mayor parte, por lo
    que los hilos aportan paralelismo efectivo sin el coste de procesos.
    """

    def __init__(self, max_hilos: int = 4):
        self.max_hilos = max(1, max_hilos)

    def procesar_archivos(
        self,
        lista_archivos: List[Path],
        carpeta_destino: Path,
        notificar_progreso: Callable[[ResultadoArchivo, int, int], None],
    ) -> List[ResultadoArchivo]:
        """
        Limpia cada archivo de `lista_archivos` y deja el resultado en
        `carpeta_destino`. Llama a `notificar_progreso` una vez por archivo
        terminado, desde un hilo trabajador.

        Devuelve la lista completa de resultados al finalizar la cola.
        """
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        total = len(lista_archivos)
        resultados: List[ResultadoArchivo] = []
        completados = 0

        with ThreadPoolExecutor(max_workers=self.max_hilos) as ejecutor:
            futuros = {
                ejecutor.submit(self._tarea_individual, ruta, carpeta_destino): ruta
                for ruta in lista_archivos
            }
            for futuro in as_completed(futuros):
                ruta = futuros[futuro]
                try:
                    resultado = futuro.result()
                except Exception as error:  # red de seguridad: la cola nunca se rompe
                    resultado = ResultadoArchivo(ruta, None, False, f"Error inesperado: {error}")

                resultados.append(resultado)
                completados += 1
                notificar_progreso(resultado, completados, total)

        return resultados

    @staticmethod
    def _tarea_individual(ruta: Path, carpeta_destino: Path) -> ResultadoArchivo:
        """Resuelve el limpiador de un archivo, lo ejecuta y describe el desenlace."""
        if not ruta.is_file():
            return ResultadoArchivo(ruta, None, False, "El archivo ya no existe")

        limpiador = ProveedorLimpiadores.obtener_segun_archivo(ruta)
        if limpiador is None:
            return ResultadoArchivo(ruta, None, False, "Formato no soportado")

        disponible, motivo = limpiador.esta_disponible()
        if not disponible:
            return ResultadoArchivo(ruta, None, False, motivo)

        ruta_salida = ProcesadorEnLote._ruta_salida_libre(ruta, carpeta_destino)
        exito = limpiador.limpiar(ruta, ruta_salida)
        mensaje = "Limpiado" if exito else "Fallo al limpiar (ver consola)"
        return ResultadoArchivo(ruta, ruta_salida if exito else None, exito, mensaje)

    @staticmethod
    def _ruta_salida_libre(ruta: Path, carpeta_destino: Path) -> Path:
        """
        Construye `sin_meta_<nombre>` en la carpeta destino y, si ya existe,
        añade un sufijo numerico para no sobrescribir resultados anteriores.
        """
        candidata = carpeta_destino / f"sin_meta_{ruta.name}"
        contador = 1
        while candidata.exists():
            candidata = carpeta_destino / f"sin_meta_{ruta.stem}_{contador}{ruta.suffix}"
            contador += 1
        return candidata
