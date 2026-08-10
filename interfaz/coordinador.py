"""
Puente entre los hilos de trabajo y la interfaz.

Tkinter solo tolera llamadas desde el hilo principal, y eso incluye `after()`,
que registra un comando en el interprete Tcl. Por eso ningun hilo de aqui toca
widgets: cada uno deposita su resultado en una cola, y esta clase la vacia
desde el hilo principal a intervalos regulares, despachando a los manejadores
que le registro la ventana.

Concentrar ese mecanismo en un sitio es lo que garantiza que la regla se
cumpla: quien añada trabajo en segundo plano mas adelante usa `ejecutar` y no
tiene que acordarse de la restriccion.
"""

import queue
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List

from limpiadores.base import OpcionesLimpieza
from nucleo import medios
from nucleo.procesador import ProcesadorEnLote, ResultadoArchivo

from .estilos import INTERVALO_EVENTOS_MS


class CoordinadorTrabajo:
    """
    Lanza tareas en hilos y entrega sus resultados en el hilo principal.

    `manejadores` asocia el nombre de un evento con la funcion que lo atiende.
    """

    def __init__(self, widget, procesador: ProcesadorEnLote,
                 manejadores: Dict[str, Callable]):
        self._widget = widget
        self._procesador = procesador
        self._manejadores = manejadores
        self._cola: queue.Queue = queue.Queue()

        # Numera las peticiones de estimacion para descartar las obsoletas: si
        # la cola cambia mientras se calcula, el resultado ya no corresponde.
        self._peticion_estimacion = 0

        self._widget.after(INTERVALO_EVENTOS_MS, self._consumir)

    # -------------------------------------------------------------- Tareas --

    def ejecutar(self, funcion: Callable[[], None]) -> None:
        """Corre `funcion` en un hilo suelto que no sobrevive al cierre."""
        threading.Thread(target=funcion, daemon=True).start()

    def emitir(self, tipo: str, carga) -> None:
        """Encola un evento para que lo atienda el hilo principal."""
        self._cola.put((tipo, carga))

    def procesar_lote(
        self,
        archivos: List[Path],
        carpeta_destino: Path,
        opciones: OpcionesLimpieza,
    ) -> None:
        """
        Limpia el lote en segundo plano, emitiendo:

          'parcial'  avance del archivo en curso, muchas veces por archivo
          'avance'   un archivo terminado
          'fin'      la cola completa, o 'error' si algo la tumba entera
        """

        def trabajo():
            ultimo_envio = [0.0]

            def parcial(ruta: Path, fraccion: float):
                # FFmpeg publica su avance varias veces por segundo. Reenviarlo
                # todo llenaria la cola de eventos con actualizaciones que el
                # ojo no distingue, asi que se limita a una cada 100 ms; el 1.0
                # final siempre pasa, para que la barra cierre exacta.
                ahora = time.monotonic()
                if fraccion >= 1.0 or ahora - ultimo_envio[0] >= 0.1:
                    ultimo_envio[0] = ahora
                    self.emitir("parcial", (ruta, fraccion))

            def progreso(resultado: ResultadoArchivo, actual: int, total: int):
                self.emitir("avance", (resultado, actual, total))

            try:
                resultados = self._procesador.procesar_archivos(
                    archivos, carpeta_destino, progreso, opciones, parcial
                )
            except Exception as error:
                self.emitir("error", str(error))
                return

            self.emitir("fin", resultados)

        self.ejecutar(trabajo)

    def estimar_peso(self, rutas: List[Path], peso_actual: int) -> None:
        """
        Calcula en segundo plano el techo de peso tras comprimir, y emite
        'peso' con (peticion, actual, estimado).

        Analizar cada video exige invocar a FFmpeg; hacerlo en el hilo de la
        interfaz congelaria la ventana con lotes grandes.
        """
        self._peticion_estimacion += 1
        peticion = self._peticion_estimacion

        def trabajo():
            estimado = sum(medios.estimar_comprimido(r) for r in rutas)
            self.emitir("peso", (peticion, peso_actual, estimado))

        self.ejecutar(trabajo)

    def estimacion_vigente(self, peticion: int) -> bool:
        """True si esa estimacion sigue correspondiendo a la cola actual."""
        return peticion == self._peticion_estimacion

    def invalidar_estimacion(self) -> None:
        """Descarta cualquier estimacion en vuelo."""
        self._peticion_estimacion += 1

    # -------------------------------------------------------------- Bombeo --

    def _consumir(self) -> None:
        """Vacia la cola de eventos y se reprograma mientras la ventana exista."""
        try:
            while True:
                tipo, carga = self._cola.get_nowait()
                manejador = self._manejadores.get(tipo)
                if manejador:
                    manejador(carga)
        except queue.Empty:
            pass

        if self._widget.winfo_exists():
            self._widget.after(INTERVALO_EVENTOS_MS, self._consumir)
