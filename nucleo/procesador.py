from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from limpiadores.base import OPCIONES_POR_DEFECTO, OpcionesLimpieza
from limpiadores.proveedor import ProveedorLimpiadores

from . import diagnostico
from .registro import registro


class DestinoInvalido(Exception):
    """La ruta de salida calculada pondria en riesgo el archivo original."""


@dataclass(frozen=True)
class ResultadoArchivo:
    """
    Resultado del procesamiento de un unico archivo de la cola.

    `codigo` distingue tres desenlaces que la interfaz presenta de forma
    distinta, porque para el usuario no significan lo mismo:

      "limpiado"  el archivo se proceso correctamente
      "omitido"   no habia nada que hacer con el (formato no soportado)
      "error"     se intento y fallo

    `exito` se conserva como atajo para "hay un archivo de salida".
    """

    ruta_origen: Path
    ruta_salida: Path | None
    exito: bool
    mensaje: str
    codigo: str = "error"


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
        opciones: OpcionesLimpieza = OPCIONES_POR_DEFECTO,
        notificar_avance_archivo: Optional[Callable[[Path, float], None]] = None,
    ) -> List[ResultadoArchivo]:
        """
        Limpia cada archivo de `lista_archivos` y deja el resultado en
        `carpeta_destino`. Llama a `notificar_progreso` una vez por archivo
        terminado, y a `notificar_avance_archivo` muchas veces mientras cada uno
        se procesa. Ambas desde hilos trabajadores.

        Devuelve la lista completa de resultados al finalizar la cola.
        """
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        total = len(lista_archivos)
        resultados: List[ResultadoArchivo] = []
        completados = 0
        hilos = self._hilos_para(opciones)

        with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
            futuros = {
                ejecutor.submit(
                    self._tarea_individual, ruta, carpeta_destino, opciones,
                    notificar_avance_archivo,
                ): ruta
                for ruta in lista_archivos
            }
            for futuro in as_completed(futuros):
                ruta = futuros[futuro]
                try:
                    resultado = futuro.result()
                except Exception as error:  # red de seguridad: la cola nunca se rompe
                    resultado = ResultadoArchivo(
                        ruta, None, False, f"Error inesperado: {error}", "error"
                    )

                resultados.append(resultado)
                completados += 1
                notificar_progreso(resultado, completados, total)

        return resultados

    def _hilos_para(self, opciones: OpcionesLimpieza) -> int:
        """
        Cuantos archivos procesar a la vez.

        Al comprimir se baja a uno solo, por dos razones. La primera es de
        rendimiento: x264 ya reparte su trabajo entre todos los nucleos, asi
        que lanzar varias compresiones a la vez las hace competir y no acelera
        nada. La segunda es de interfaz: con un unico archivo en curso, el
        progreso individual que se muestra es inequivoco.
        """
        return 1 if opciones.comprimir_video else self.max_hilos

    @staticmethod
    def _tarea_individual(
        ruta: Path,
        carpeta_destino: Path,
        opciones: OpcionesLimpieza,
        notificar_avance: Optional[Callable[[Path, float], None]] = None,
    ) -> ResultadoArchivo:
        """Resuelve el limpiador de un archivo, lo ejecuta y describe el desenlace."""
        if not ruta.is_file():
            registro.error("El archivo ya no existe",
                           f"No se encontro en {ruta.parent}", archivo=ruta.name)
            return ResultadoArchivo(ruta, None, False, "El archivo ya no existe", "error")

        # Se comprueba aqui y no por el error de FFmpeg porque su diagnostico
        # para un archivo vacio ("falta el atomo moov") describe otra cosa y
        # mandaria al usuario a buscar una corrupcion que no existe.
        if ruta.stat().st_size == 0:
            registro.error("El archivo esta vacio",
                           "Ocupa 0 bytes. Probablemente la copia o la descarga "
                           "no llego a completarse.", archivo=ruta.name)
            return ResultadoArchivo(ruta, None, False, "El archivo esta vacio", "error")

        limpiador = ProveedorLimpiadores.obtener_segun_archivo(ruta)
        if limpiador is None:
            return ResultadoArchivo(
                ruta, None, False, "No es una imagen ni un video", "omitido"
            )

        disponible, motivo = limpiador.esta_disponible()
        if not disponible:
            return ResultadoArchivo(ruta, None, False, motivo, "omitido")

        try:
            ruta_salida = ProcesadorEnLote._ruta_salida_libre(ruta, carpeta_destino)
        except DestinoInvalido as error:
            return ResultadoArchivo(ruta, None, False, str(error), "error")

        al_progresar = None
        if notificar_avance:
            def al_progresar(fraccion: float, _ruta=ruta):
                notificar_avance(_ruta, fraccion)

        exito, volcado = limpiador.limpiar(ruta, ruta_salida, opciones, al_progresar)

        if exito:
            mensaje = "Metadatos eliminados"
            if opciones.comprimir_video and ruta.suffix.lower() in ProveedorLimpiadores.FORMATOS_VIDEO:
                antes, despues = ruta.stat().st_size, ruta_salida.stat().st_size
                if despues < antes:
                    ahorro = 100 * (antes - despues) / antes
                    mensaje = f"Metadatos eliminados y comprimido ({ahorro:.0f}% menos)"
            registro.info(mensaje, archivo=ruta.name)
            return ResultadoArchivo(ruta, ruta_salida, True, mensaje, "limpiado")

        # El volcado tecnico se traduce a una causa reconocible y se guarda
        # entero en el registro, que es lo que muestra la consola.
        causa = diagnostico.interpretar(volcado)
        registro.error(
            causa.resumen,
            f"{causa.explicacion}\n\n{diagnostico.resumir_salida(volcado)}",
            archivo=ruta.name,
        )
        return ResultadoArchivo(ruta, None, False, causa.resumen, "error")

    @staticmethod
    def _ruta_salida_libre(ruta: Path, carpeta_destino: Path) -> Path:
        """
        La copia limpia conserva el nombre original del archivo.

        Dos salvaguardas, porque sin prefijo el nombre de salida puede coincidir
        con el de entrada:

        1. Si la ruta de destino es exactamente el archivo de origen, se rechaza.
           Escribir ahi destruiria el original, y toda la aplicacion se apoya en
           la promesa de no tocarlo.
        2. Si ya existe otro archivo con ese nombre en el destino (por ejemplo,
           de una corrida anterior), se añade un sufijo numerico en vez de
           sobrescribirlo.
        """
        candidata = carpeta_destino / ruta.name

        if candidata.resolve() == ruta.resolve():
            raise DestinoInvalido(
                "La carpeta destino es la del original; elige otra para no sobrescribirlo"
            )

        contador = 1
        while candidata.exists():
            candidata = carpeta_destino / f"{ruta.stem}_{contador}{ruta.suffix}"
            contador += 1
        return candidata
